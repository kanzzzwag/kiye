const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (t) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const fmt1 = (t) => `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;
const mb = (b) => `${(b / 1048576).toFixed(1).replace(".", ",")} МБ`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- API key ----------
let apiKey = "";
try { apiKey = localStorage.getItem("apiKey") || ""; } catch {}
const headers = () => ({ "X-API-Key": apiKey });
function askKey() {
  return new Promise((resolve) => {
    const d = $("#keyDialog");
    $("#key").value = apiKey;
    d.onclose = () => {
      if (d.returnValue === "save") {
        apiKey = $("#key").value.trim();
        try { localStorage.setItem("apiKey", apiKey); } catch {}
      }
      resolve(!!apiKey);
    };
    d.showModal();
  });
}
$("#keyBtn").onclick = askKey;

// ---------- views ----------
const VIEWS = ["upload", "progress", "result", "journal", "types"];
function show(v) {
  VIEWS.forEach((x) => { $(`#view-${x}`).hidden = x !== v; });
  const result = v === "result";
  $("#nav").hidden = result;
  $("#againBtn").hidden = !result;
  $("#footNote").hidden = result;
  window.scrollTo(0, 0);
  if (v === "journal") { loadTypesFilter(); loadJournal(); }
}
document.querySelectorAll("[data-go]").forEach((a) => a.onclick = (e) => { e.preventDefault(); history.replaceState(null, "", a.dataset.go === "upload" ? location.pathname : `#${a.dataset.go}`); show(a.dataset.go); });
$("#againBtn").onclick = () => { resetUpload(); show("upload"); };

// ---------- what the service checks (public list) ----------
let TYPES = [];
fetch("/api/public/types").then((r) => r.json()).then((types) => {
  TYPES = types;
  $("#typesCount").textContent = `${types.length} типов нарушений, видимых на записи`;
  $("#typesList").innerHTML = types.map((t) => `<li><span>${esc(t.name)}</span><span class="ref">${esc(t.ref)}</span></li>`).join("");
  $("#typesGrid").innerHTML = types.map((t) => `<div class="card"><b>${esc(t.name)}</b>
    <div class="muted small">${esc(t.description || "")}</div>
    ${t.why ? `<div class="small">${esc(t.why)}</div>` : ""}<div class="ref">${esc(t.ref)}</div></div>`).join("");
}).catch(() => {});

// ---------- upload ----------
let file = null, meta = { duration: 0, w: 0, h: 0 }, fileUrl = null;
function resetUpload() {
  file = null; $("#filerow").hidden = true; $("#file").value = ""; showError("");
}
function showError(msg) { const e = $("#error"); e.textContent = msg; e.hidden = !msg; }
function setFile(f) {
  if (!f) return;
  if (!/\.(mov|mp4)$/i.test(f.name)) { showError("Нужен файл .mov или .mp4"); return; }
  showError("");
  file = f;
  if (fileUrl) URL.revokeObjectURL(fileUrl);
  fileUrl = URL.createObjectURL(f);
  $("#fname").textContent = f.name;
  $("#fmeta").textContent = mb(f.size);
  $("#filerow").hidden = false;
  const v = document.createElement("video");
  v.preload = "metadata"; v.muted = true; v.src = fileUrl;
  v.onloadedmetadata = () => {
    meta = { duration: v.duration || 0, w: v.videoWidth, h: v.videoHeight };
    $("#fmeta").textContent = `${mb(f.size)} · ${fmt(meta.duration)} · ${meta.w}×${meta.h}`;
  };
}
$("#file").onchange = (e) => setFile(e.target.files[0]);
const drop = $("#drop");
drop.ondragover = (e) => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); setFile(e.dataTransfer.files[0]); };
drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("#file").click(); } };

function upload(fd, onProgress) {
  return new Promise((resolve, reject) => {
    const x = new XMLHttpRequest();
    x.open("POST", "/api/v1/analyze");
    x.setRequestHeader("X-API-Key", apiKey);
    x.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    x.onload = () => {
      let body = {};
      try { body = JSON.parse(x.responseText); } catch {}
      if (x.status === 200) resolve(body);
      else reject(Object.assign(new Error(body.detail || `HTTP ${x.status}`), { status: x.status }));
    };
    x.onerror = () => reject(new Error("Сервер недоступен"));
    x.send(fd);
  });
}

// ---------- progress ----------
const stage = (k, state) => { const li = $(`#stages li[data-s="${k}"]`); li.classList.toggle("done", state === "done"); li.classList.toggle("active", state === "active"); };
const sampleFps = (d) => Math.min(4, Math.max(d <= 180 ? 2 : 0.5, 360 / Math.max(d, 1)));
let preview = null, lastDraw = -1;
function drawFrame(t) {
  if (!preview || Math.abs(t - lastDraw) < 0.4) return;
  lastDraw = t;
  preview.currentTime = Math.min(t, Math.max(0, (meta.duration || 0) - 0.1));
}
function setupPreview() {
  preview = document.createElement("video");
  preview.muted = true; preview.preload = "auto"; preview.src = fileUrl; lastDraw = -1;
  const c = $("#frameCanvas"), ctx = c.getContext("2d");
  preview.onloadedmetadata = () => {
    const w = preview.videoWidth || 16, h = preview.videoHeight || 9, s = Math.min(640 / w, 360 / h);
    c.width = Math.round(w * s); c.height = Math.round(h * s);
  };
  preview.onseeked = () => ctx.drawImage(preview, 0, 0, c.width, c.height);
}

$("#go").onclick = async () => {
  if (!file) return;
  if (!apiKey && !(await askKey())) return;
  const fd = new FormData();
  fd.append("file", file);
  if ($("#desk").value) fd.append("desk_id", $("#desk").value);
  if ($("#recorded").value) fd.append("recorded_at", new Date($("#recorded").value).toISOString());
  $("#go").disabled = true; showError("");
  const started = Date.now();
  const nFrames = Math.max(1, Math.round((meta.duration || 0) * sampleFps(meta.duration || 0)));
  $("#pName").textContent = file.name; $("#pJob").textContent = "загрузка…";
  [0, 1, 2, 3, 4].forEach((k) => stage(k, k === 0 ? "active" : ""));
  $("#sUp").textContent = ""; $("#sFrames").textContent = ""; $("#sModel").textContent = "";
  $("#openResult").disabled = true; setOverall(0); setupPreview();
  show("progress");
  let jobId;
  try {
    const r = await upload(fd, (p) => { setOverall(0.1 * p); $("#sUp").textContent = `${Math.round(p * 100)}%`; });
    jobId = r.job_id;
  } catch (e) {
    $("#go").disabled = false; show("upload");
    if (e.status === 401) { showError("Неверный ключ API"); askKey(); } else showError("Ошибка загрузки: " + e.message);
    return;
  }
  stage(0, "done"); $("#sUp").textContent = mb(file.size);
  $("#pJob").textContent = `задача ${jobId.slice(0, 8)}`;
  let fails = 0, p = { status: "processing", progress: 0 };
  for (;;) {
    await sleep(1500);
    try {
      const r = await fetch(`/api/internal/jobs/${jobId}`, { headers: headers() });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      p = await r.json(); fails = 0;
    } catch (e) { if (++fails > 8) { show("upload"); showError("Сервер не отвечает"); $("#go").disabled = false; return; } continue; }
    const sec = (Date.now() - started) / 1000;
    if (p.status === "failed") { show("upload"); showError("Не удалось обработать видео"); $("#go").disabled = false; return; }
    const prog = p.status === "done" ? 1 : p.progress;
    const overall = 0.1 + 0.9 * prog;
    setOverall(overall);
    const left = prog > 0.05 && prog < 1 ? ` · осталось около ${fmt(sec * (1 - overall) / overall)}` : "";
    $("#pTime").textContent = `Прошло ${fmt(sec)}${left}`;
    // stage display from the job's progress: 0-0.8 first pass (frames + model), 0.8-0.99 key frames and rules
    const model = Math.min(1, prog / 0.8);
    stage(1, prog > 0 ? "done" : "active");
    if (prog > 0) $("#sFrames").textContent = `${nFrames} кадр.`;
    stage(2, model >= 1 ? "done" : prog > 0 ? "active" : "");
    $("#sModel").textContent = `${Math.round(model * nFrames)} / ${nFrames}`;
    stage(3, prog >= 0.99 ? "done" : prog >= 0.8 ? "active" : "");
    stage(4, p.status === "done" ? "done" : prog >= 0.99 ? "active" : "");
    const t = (meta.duration || 0) * model;
    $("#frameT").textContent = `${fmt(t)} / ${fmt(meta.duration || 0)}`;
    $("#screenFill").style.width = `${model * 100}%`;
    drawFrame(t);
    if (p.status === "done") break;
  }
  $("#go").disabled = false;
  const btn = $("#openResult");
  btn.disabled = false;
  const open = async () => { btn.onclick = null; await openResult(jobId, p.elapsed_sec || (Date.now() - started) / 1000); };
  btn.onclick = open;
  setTimeout(() => { if (!$("#view-progress").hidden) open(); }, 1200);
};
function setOverall(x) { $("#pPct").textContent = `${Math.round(x * 100)}%`; $("#barFill").style.width = `${x * 100}%`; }

// ---------- result ----------
const ICO_WARN = '<svg viewBox="0 0 24 24"><path d="M12 3l9.5 17h-19z"/><path d="M12 10v4M12 17.5v.01"/></svg>';
const ICO_OK = '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.8 2.8L16 10"/></svg>';
let RES = null, selected = 0;

async function openResult(jobId, elapsed) {
  const [jr, dr] = await Promise.all([
    fetch(`/api/v1/jobs/${jobId}`, { headers: headers() }).then((r) => r.json()),
    fetch(`/api/internal/jobs/${jobId}`, { headers: headers() }).then((r) => r.json()),
  ]);
  RES = { job: jr, det: dr, jobId };
  const bad = jr.verdict === "violation", n = jr.violations.length;
  $("#banner").classList.toggle("ok", !bad);
  $("#bannerIco").innerHTML = bad ? ICO_WARN : ICO_OK;
  $("#bTitle").textContent = bad ? "Обнаружены признаки возможных нарушений" : "Нарушений не обнаружено";
  const word = n === 1 ? "событие" : n >= 2 && n <= 4 ? "события" : "событий";
  $("#bSub").textContent = `${bad ? `${n} ${word} · ` : ""}${file ? file.name : ""} · ${fmt(meta.duration || 0)} · проверено за ${fmt(elapsed)}`;
  $("#bChip").textContent = `verdict: ${jr.verdict}`;
  // player
  const pl = $("#player");
  pl.src = fileUrl;
  pl.onloadedmetadata = () => { renderTimeline(); select(0, false); };
  pl.ontimeupdate = () => updateTime();
  pl.onplay = pl.onpause = () => $("#playBtn").classList.toggle("paused", !pl.paused);
  $("#playBtn").onclick = () => { if (pl.paused) pl.play().catch(() => {}); else pl.pause(); };
  pl.onclick = () => $("#playBtn").click();
  // API json (images shortened for reading; copy gives the full answer)
  $("#apiPath").textContent = `/api/v1/jobs/${jobId.slice(0, 8)}`;
  const short = JSON.parse(JSON.stringify(jr));
  short.violations.forEach((v) => v.evidence_frames.forEach((f) => { f.image_base64 = `<jpeg, ${Math.round(f.image_base64.length * 0.75 / 1024)} КБ>`; }));
  $("#json").textContent = JSON.stringify(short, null, 2);
  $("#copyJson").onclick = async () => {
    try { await navigator.clipboard.writeText(JSON.stringify(jr, null, 2)); $("#copyJson").textContent = "Скопировано"; }
    catch { $("#copyJson").textContent = "Не удалось"; }
    setTimeout(() => { $("#copyJson").textContent = "Скопировать JSON"; }, 1500);
  };
  renderCards();
  show("result");
}

function renderCards() {
  const { job, det } = RES;
  if (!job.violations.length) {
    $("#cards").innerHTML = `<div class="empty">На записи не найдено моментов, похожих на нарушение. Это не исключает нарушений,
      которые не видны камере.</div>`;
    return;
  }
  $("#cards").innerHTML = job.violations.map((v, i) => {
    const d = det.violations[i] || {};
    const law = d.law;
    const quote = law && law.quote ? (law.quote.length > 170 ? law.quote.slice(0, 170).replace(/\s+\S*$/, "") + "…" : law.quote) : "";
    return `<article class="vcard" id="vc${i}">
      <div class="vhead"><div><div class="vnum">НАРУШЕНИЕ ${i + 1}</div><div class="vtitle">${esc(v.type)}</div></div>
        <button type="button" class="tc" data-i="${i}" data-t="${v.timecode_sec}">${fmt1(v.timecode_sec)}</button></div>
      <div class="thumbs">${v.evidence_frames.map((f) => `<button type="button" data-i="${i}" data-t="${f.timestamp_sec}">
        <img src="data:image/jpeg;base64,${f.image_base64}" alt="кадр ${fmt(f.timestamp_sec)}"><span>кадр ${fmt(f.timestamp_sec)}</span></button>`).join("")}</div>
      <div class="vsec">Что видно</div><p class="vtext">${esc(d.seen || v.description.replace(/\s*Норма:.*$/s, ""))}</p>
      ${d.why ? `<div class="vsec">Почему это может быть нарушением</div><p class="vtext">${esc(d.why)}</p>` : ""}
      <div class="law"><b>${esc(law ? law.act : "Норма")}</b>
        ${law && law.clause ? `${esc(law.clause)}${quote ? " — " : ""}` : ""}${esc(quote) || esc(d.legal || "")}
        ${law && !law.verified ? `<br><span class="warn">пункт требует проверки юристом</span>` : ""}
        ${law && law.url ? `<br><a href="${esc(law.url)}" target="_blank" rel="noopener">Открыть на adilet.zan.kz</a>` : ""}</div>
    </article>`;
  }).join("");
  document.querySelectorAll("#cards [data-t]").forEach((b) => b.onclick = () => select(+b.dataset.i, true, +b.dataset.t));
}

function select(i, play, t) {
  const { job } = RES;
  selected = i;
  document.querySelectorAll(".vcard").forEach((c, k) => c.classList.toggle("sel", k === i));
  document.querySelectorAll(".tl .pin").forEach((p, k) => p.classList.toggle("sel", k === i));
  renderSegments();
  const v = job.violations[i];
  if (!v) return;
  const pl = $("#player");
  pl.currentTime = t ?? v.timecode_sec;
  if (play) { pl.play().catch(() => {}); if (window.innerWidth < 900) pl.scrollIntoView({ behavior: "smooth", block: "center" }); }
}

const NSEG = 48;
function renderTimeline() {
  const dur = $("#player").duration || meta.duration || 1, tl = $("#timeline");
  tl.innerHTML = Array.from({ length: NSEG }, () => '<span class="seg"></span>').join("") + '<span class="cur"></span>';
  RES.job.violations.forEach((v, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.className = "pin"; b.textContent = i + 1;
    b.style.left = `${Math.min(100, 100 * v.timecode_sec / dur)}%`;
    b.title = `${fmt1(v.timecode_sec)} · ${v.type}`;
    b.onclick = (e) => { e.stopPropagation(); select(i, true); document.getElementById(`vc${i}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }); };
    tl.appendChild(b);
  });
  tl.onclick = (e) => { const r = tl.getBoundingClientRect(); $("#player").currentTime = dur * Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)); };
  $("#tlAxis").innerHTML = [0, 0.25, 0.5, 0.75, 1].map((k) => `<span>${fmt(dur * k)}</span>`).join("");
  renderSegments(); updateTime();
}
function renderSegments() {
  const dur = $("#player").duration || meta.duration || 1, segs = document.querySelectorAll(".tl .seg");
  const span = 6; // seconds shaded after each event start
  segs.forEach((s, k) => {
    const a = dur * k / NSEG, b = dur * (k + 1) / NSEG;
    let cls = "";
    RES.job.violations.forEach((v, i) => {
      if (b > v.timecode_sec && a < v.timecode_sec + span) cls = i === selected ? "hot" : (cls || "warm");
    });
    s.className = "seg" + (cls ? " " + cls : "");
  });
}
function updateTime() {
  const pl = $("#player"), dur = pl.duration || meta.duration || 0;
  const txt = `${fmt1(pl.currentTime || 0)} / ${fmt(dur)}`;
  $("#tTag").textContent = txt; $("#tlTime").textContent = txt;
  const cur = $(".tl .cur"); if (cur && dur) cur.style.left = `${100 * pl.currentTime / dur}%`;
}

// ---------- journal ----------
let typesLoaded = false;
async function loadTypesFilter() {
  if (typesLoaded) return;
  const types = TYPES.length ? TYPES : await fetch("/api/public/types").then((r) => r.json()).catch(() => []);
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
  if (!apiKey && !(await askKey())) { $("#rows").innerHTML = `<tr><td colspan="6">Нужен ключ API</td></tr>`; return; }
  const r = await fetch(`/api/internal/violations?${filterQuery()}`, { headers: headers() });
  if (!r.ok) { $("#rows").innerHTML = `<tr><td colspan="6">${r.status === 401 ? "Неверный ключ API — нажмите «Ключ» в шапке" : "Ошибка загрузки"}</td></tr>`; return; }
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

// open #types / #journal directly by link
window.addEventListener("hashchange", () => { const h = location.hash.slice(1); if (["types", "journal", "upload"].includes(h)) show(h); });
if (["types", "journal"].includes(location.hash.slice(1))) show(location.hash.slice(1));
