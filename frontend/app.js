const $ = (s) => document.querySelector(s);
const keyInput = $("#key");
try { keyInput.value = localStorage.getItem("apiKey") || ""; } catch {}
keyInput.addEventListener("change", () => { try { localStorage.setItem("apiKey", keyInput.value); } catch {} });
const headers = () => ({ "X-API-Key": keyInput.value });

document.querySelectorAll("nav button").forEach((b) => b.onclick = () => {
  document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll("main section").forEach((s) => s.hidden = s.id !== b.dataset.tab);
  if (b.dataset.tab === "journal") loadJournal();
});

let file = null;
const setFile = (f) => { file = f; $("#drop").firstChild.textContent = f ? f.name + " · " : "Перетащите .mov сюда или "; $("#go").disabled = !f; };
$("#file").onchange = (e) => setFile(e.target.files[0]);
const drop = $("#drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); setFile(e.dataTransfer.files[0]); };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;

$("#go").onclick = async () => {
  const fd = new FormData();
  fd.append("file", file);
  if ($("#desk").value) fd.append("desk_id", $("#desk").value);
  if ($("#recorded").value) fd.append("recorded_at", new Date($("#recorded").value).toISOString());
  $("#go").disabled = true; $("#result").innerHTML = ""; $("#status").textContent = "Загрузка…";
  const r = await fetch("/api/v1/analyze", { method: "POST", headers: headers(), body: fd });
  if (!r.ok) { $("#status").textContent = "Ошибка: " + (await r.text()); $("#go").disabled = false; return; }
  const { job_id } = await r.json();
  const started = Date.now();
  const poll = async () => {
    const j = await (await fetch(`/api/v1/jobs/${job_id}`, { headers: headers() })).json();
    if (j.status === "processing") {
      $("#status").textContent = `Анализ… ${Math.round((Date.now() - started) / 1000)} с`;
      return setTimeout(poll, 2000);
    }
    $("#go").disabled = false;
    $("#status").textContent = j.status === "failed" ? "Не удалось обработать видео" : "";
    if (j.status === "done") render(j);
  };
  poll();
};

function render(j) {
  const url = URL.createObjectURL(file);
  const bad = j.verdict === "violation";
  let html = `<div class="card"><div class="verdict ${bad ? "bad" : "good"}">${bad ? "Обнаружены признаки возможных нарушений" : "Нарушений не обнаружено"}</div>
    <video id="player" src="${url}" controls></video></div>`;
  for (const v of j.violations) {
    html += `<div class="card"><b>${esc(v.type)}</b> · <span class="tc" data-t="${v.timecode_sec}">${fmt(v.timecode_sec)}</span>
      <p>${esc(v.description)}</p><div class="frames">${v.evidence_frames.map((f) =>
        `<img src="data:image/jpeg;base64,${f.image_base64}" title="${fmt(f.timestamp_sec)}">`).join("")}</div></div>`;
  }
  $("#result").innerHTML = html;
  document.querySelectorAll(".tc").forEach((e) => e.onclick = () => { const p = $("#player"); p.currentTime = +e.dataset.t; p.play(); });
}

async function loadJournal() {
  const r = await fetch("/api/internal/violations", { headers: headers() });
  if (!r.ok) { $("#rows").innerHTML = `<tr><td colspan="6">Введите API-ключ на вкладке «Анализ видео»</td></tr>`; return; }
  const rows = await r.json();
  $("#rows").innerHTML = rows.map((v) => `<tr>
    <td>${esc(new Date(v.occurred_at || v.created_at).toLocaleString("ru-RU"))}</td><td>${esc(v.type)}</td>
    <td>${fmt(v.timecode_sec)}</td><td>${esc(v.legal) || "—"}</td><td>${esc(v.teller) || "—"}</td>
    <td><select data-id="${v.id}">${["new", "confirmed", "rejected"].map((s) =>
      `<option value="${s}" ${s === v.review_status ? "selected" : ""}>${{ new: "Новое", confirmed: "Подтверждено", rejected: "Отклонено" }[s]}</option>`).join("")}</select></td></tr>`).join("")
    || `<tr><td colspan="6">Пока пусто</td></tr>`;
  document.querySelectorAll("#rows select").forEach((s) => s.onchange = () =>
    fetch(`/api/internal/violations/${s.dataset.id}`, { method: "PATCH", headers: { ...headers(), "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: s.value }) }));
}
$("#reload").onclick = loadJournal;
