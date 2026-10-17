const $ = (s) => document.querySelector(s);
const keyInput = $("#key");
try { keyInput.value = localStorage.getItem("apiKey") || ""; } catch {}
keyInput.addEventListener("change", () => { try { localStorage.setItem("apiKey", keyInput.value); } catch {} });
const headers = () => ({ "X-API-Key": keyInput.value });

document.querySelectorAll("nav button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll("main section").forEach((s) => s.hidden = s.id !== b.dataset.tab);
  if (b.dataset.tab === "journal") { loadTypes(); loadJournal(); }
});

let file = null;
const setFile = (f) => { file = f; $("#dropText").textContent = f ? f.name + " · " : "Перетащите .mov сюда или "; $("#go").disabled = !f; };
$("#file").onchange = (e) => setFile(e.target.files[0]);
const drop = $("#drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); setFile(e.dataTransfer.files[0]); };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const showError = (msg) => { const e = $("#error"); e.textContent = msg; e.hidden = !msg; };
const setProgress = (p, text) => { $("#progress").hidden = false; $("#barFill").style.width = `${Math.round(p * 100)}%`; $("#status").textContent = text; };

// upload with real upload progress (fetch has none), then poll the job
function upload(fd) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/v1/analyze");
    x.setRequestHeader("X-API-Key", keyInput.value);
    x.upload.onprogress = (e) => e.lengthComputable && setProgress(0.3 * e.loaded / e.total, `Загрузка ${Math.round(100 * e.loaded / e.total)}%`);
    x.onload = () => {
      let body = {};
      try { body = JSON.parse(x.responseText); } catch {}
      x.status === 200 ? resolve(body) : reject(new Error(body.detail || `HTTP ${x.status}`));
    };
    x.onerror = () => reject(new Error("Сеть недоступна"));
    x.send(fd);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

$("#go").onclick = async () => {
  const fd = new FormData();
  fd.append("file", file);
  if ($("#desk").value) fd.append("desk_id", $("#desk").value);
  if ($("#recorded").value) fd.append("recorded_at", new Date($("#recorded").value).toISOString());
  $("#go").disabled = true; $("#result").innerHTML = ""; showError("");
  try {
    const { job_id } = await upload(fd);
    const started = Date.now();
    let fails = 0;
    for (;;) {
      await sleep(1500);
      let p;
      try {
        const r = await fetch(`/api/internal/jobs/${job_id}`, { headers: headers() });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        p = await r.json(); fails = 0;
      } catch (e) { if (++fails > 5) throw e; continue; }  // tolerate short network drops
      const sec = Math.round((Date.now() - started) / 1000);
      if (p.status === "processing") { setProgress(0.3 + 0.7 * p.progress, `Анализ ${Math.round(100 * p.progress)}% · ${sec} с`); continue; }
      if (p.status === "failed") throw new Error("Не удалось обработать видео");
      setProgress(1, `Готово за ${sec} с`);
      const j = await (await fetch(`/api/v1/jobs/${job_id}`, { headers: headers() })).json();
      render(j, p);
      break;
    }
  } catch (e) {
    showError("Ошибка: " + e.message);
  } finally {
    $("#go").disabled = !file;
  }
};

function render(j, extra) {
  const url = URL.createObjectURL(file);
  const bad = j.verdict === "violation";
  const legal = (extra.violations || []).map((v) => v.legal);
  let html = `<div class="card"><div class="verdict ${bad ? "bad" : "good"}">${bad ? `Обнаружены признаки возможных нарушений: ${j.violations.length}` : "Нарушений не обнаружено"}</div>
    <div id="timeline" class="timeline" aria-label="Таймлайн нарушений"></div>
    <video id="player" src="${url}" controls playsinline preload="metadata"></video></div>`;
  j.violations.forEach((v, i) => {
    const desc = v.description.replace(/\s*Норма:.*$/s, "");
    html += `<div class="card vcard" id="v${i}"><div class="vhead"><b>${esc(v.type)}</b><button class="tc" data-t="${v.timecode_sec}">${fmt(v.timecode_sec)}</button></div>
      <p>${esc(desc)}</p><p class="norm">${esc(legal[i] || (v.description.match(/Норма:.*$/s) || [""])[0])}</p>
      <div class="frames">${v.evidence_frames.map((f) =>
        `<img src="data:image/jpeg;base64,${f.image_base64}" alt="кадр ${fmt(f.timestamp_sec)}" title="${fmt(f.timestamp_sec)}" data-t="${f.timestamp_sec}">`).join("")}</div></div>`;
  });
  $("#result").innerHTML = html;
  const player = $("#player");
  const seek = (t) => { player.currentTime = +t; player.play().catch(() => {}); player.scrollIntoView({ behavior: "smooth", block: "center" }); };
  document.querySelectorAll(".tc, .frames img").forEach((e) => e.onclick = () => seek(e.dataset.t));
  player.onloadedmetadata = () => {
    const tl = $("#timeline");
    const dur = player.duration || 1;
    j.violations.forEach((v, i) => {
      const m = document.createElement("button");
      m.className = "mark";
      m.title = `${fmt(v.timecode_sec)} · ${v.type}`;
      m.setAttribute("aria-label", m.title);
      m.style.left = `${Math.min(100, 100 * v.timecode_sec / dur)}%`;
      m.onclick = () => { seek(v.timecode_sec); document.getElementById(`v${i}`).classList.add("flash"); setTimeout(() => document.getElementById(`v${i}`).classList.remove("flash"), 1200); };
      tl.appendChild(m);
    });
    const cur = document.createElement("div");
    cur.className = "cursor";
    tl.appendChild(cur);
    player.ontimeupdate = () => { cur.style.left = `${100 * player.currentTime / dur}%`; };
    tl.onclick = (e) => { if (e.target === tl) seek(dur * (e.offsetX / tl.clientWidth)); };
  };
}

// ---- journal ----
let typesLoaded = false;
async function loadTypes() {
  if (typesLoaded) return;
  const r = await fetch("/api/internal/types", { headers: headers() });
  if (!r.ok) return;
  const types = await r.json();
  $("#fType").insertAdjacentHTML("beforeend", types.map((t) => `<option value="${esc(t.code)}">${esc(t.name)}</option>`).join(""));
  typesLoaded = true;
}

const filterQuery = () => {
  const q = new URLSearchParams();
  if ($("#fFrom").value) q.set("date_from", $("#fFrom").value);
  if ($("#fTo").value) q.set("date_to", $("#fTo").value);
  if ($("#fType").value) q.set("type", $("#fType").value);
  if ($("#fStatus").value) q.set("status", $("#fStatus").value);
  return q.toString();
};

const STATUS = { new: "Новое", confirmed: "Подтверждено", rejected: "Отклонено" };
async function loadJournal() {
  const r = await fetch(`/api/internal/violations?${filterQuery()}`, { headers: headers() });
  if (!r.ok) { $("#rows").innerHTML = `<tr><td colspan="6">Введите API-ключ на вкладке «Анализ видео»</td></tr>`; return; }
  const rows = await r.json();
  $("#rows").innerHTML = rows.map((v) => `<tr>
    <td data-h="Дата">${esc(new Date(v.occurred_at || v.created_at).toLocaleString("ru-RU"))}</td><td data-h="Тип">${esc(v.type)}</td>
    <td data-h="Таймкод">${fmt(v.timecode_sec)}</td><td data-h="Норма" class="normcell">${esc(v.legal) || "—"}</td><td data-h="Кассир">${esc(v.teller) || "—"}</td>
    <td data-h="Статус"><select data-id="${v.id}" aria-label="Статус">${Object.entries(STATUS).map(([s, n]) =>
      `<option value="${s}" ${s === v.review_status ? "selected" : ""}>${n}</option>`).join("")}</select></td></tr>`).join("")
    || `<tr><td colspan="6">Ничего не найдено</td></tr>`;
  document.querySelectorAll("#rows select").forEach((s) => s.onchange = () =>
    fetch(`/api/internal/violations/${s.dataset.id}`, { method: "PATCH", headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: s.value }) }));
}
$("#reload").onclick = loadJournal;

$("#csv").onclick = async () => {
  const r = await fetch(`/api/internal/violations.csv?${filterQuery()}`, { headers: headers() });
  if (!r.ok) return;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = `violations-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
};
