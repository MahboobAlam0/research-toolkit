// ─── ResearchKit AI · Web Frontend ────────────────────────────────────────────
"use strict";

// ── Config ────────────────────────────────────────────────────────────────────
const DEFAULT_BACKEND = "https://research-toolkit-production.up.railway.app";
let API = `${localStorage.getItem("backendUrl") || DEFAULT_BACKEND}/api`;

// ── State ─────────────────────────────────────────────────────────────────────
let papers      = [];
let chatHistory = [];
let interests   = JSON.parse(localStorage.getItem("interests") || "[]");

// ── DOM ───────────────────────────────────────────────────────────────────────
const statusDot   = document.getElementById("statusDot");
const statusLabel = document.getElementById("statusLabel");

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("backendUrlInput").value =
    localStorage.getItem("backendUrl") || DEFAULT_BACKEND;

  setupNav();
  setupBackendConnect();
  setupPapers();
  setupChat();
  setupSynth();
  setupDigest();
  setupJD();

  checkBackend();
  loadPapers();
  renderInterestTags();
});

// ═════════════════════════════════════════════════════════════════════════════
// BACKEND STATUS
// ═════════════════════════════════════════════════════════════════════════════

async function checkBackend() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      statusDot.className = "status-dot online";
      statusLabel.textContent = "Online";
      return true;
    }
  } catch { /* fall through */ }
  statusDot.className = "status-dot";
  statusLabel.textContent = "Offline";
  return false;
}

function setupBackendConnect() {
  document.getElementById("btnConnect").addEventListener("click", () => {
    const url = document.getElementById("backendUrlInput").value.trim().replace(/\/+$/, "");
    if (!url) return;
    localStorage.setItem("backendUrl", url);
    API = `${url}/api`;
    checkBackend();
    loadPapers();
  });
  document.getElementById("backendUrlInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("btnConnect").click();
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// NAVIGATION
// ═════════════════════════════════════════════════════════════════════════════

function setupNav() {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
    });
  });
}

// ═════════════════════════════════════════════════════════════════════════════
// PAPERS
// ═════════════════════════════════════════════════════════════════════════════

function setupPapers() {
  document.getElementById("btnRefresh").addEventListener("click", loadPapers);
  document.getElementById("btnUploadPdf").addEventListener("click", () => {
    document.getElementById("pdfFileInput").click();
  });
  document.getElementById("pdfFileInput").addEventListener("change", handlePdfUpload);
}

async function loadPapers() {
  try {
    const r = await fetch(`${API}/papers/list`);
    if (!r.ok) throw new Error();
    papers = await r.json();
    renderPapers();
    document.getElementById("paperCount").textContent = papers.length;
  } catch {
    document.getElementById("papersGrid").innerHTML =
      `<div class="empty-state"><div class="empty-icon">⚡</div>
       <p>Backend offline.<br/>Start with: <strong>docker compose up backend</strong></p></div>`;
  }
}

function renderPapers() {
  const grid = document.getElementById("papersGrid");
  if (!papers.length) {
    grid.innerHTML = `<div class="empty-state">
      <div class="empty-icon">📄</div>
      <p>No papers saved yet.<br/>
      Use <strong>Upload PDF</strong> above, or install the Chrome extension<br/>
      to save from arXiv / PubMed / Semantic Scholar.</p></div>`;
    return;
  }
  grid.innerHTML = papers.map((p) => `
    <div class="paper-card">
      <span class="paper-source-badge badge-${p.source}">${p.source.replace(/_/g," ")}</span>
      <div class="paper-title">${esc(p.title)}</div>
      <div class="paper-authors">${esc((p.authors||[]).join(", ") || "Unknown authors")}</div>
      <div class="paper-actions">
        <button class="btn-chip ask" onclick="askPaper('${esc(p.title.substring(0,60))}')">💬 Ask</button>
        <a class="btn-chip" href="${p.url}" target="_blank" rel="noopener">🔗 Open</a>
        <button class="btn-chip delete" onclick="deletePaper('${p.id}')">🗑 Delete</button>
      </div>
    </div>`).join("");
}

async function deletePaper(id) {
  try {
    await fetch(`${API}/papers/${id}`, { method: "DELETE" });
    await loadPapers();
    toast("Paper deleted.", "success");
  } catch { toast("Could not delete paper.", "error"); }
}

function askPaper(title) {
  document.querySelector('[data-view="chat"]').click();
  document.getElementById("chatInput").value = `Summarize the paper: "${title}"`;
  document.getElementById("chatInput").focus();
}

async function handlePdfUpload() {
  const file = document.getElementById("pdfFileInput").files[0];
  if (!file) return;
  document.getElementById("pdfFileInput").value = "";

  const progress  = document.getElementById("uploadProgress");
  const barFill   = document.getElementById("uploadBarFill");
  const label     = document.getElementById("uploadLabel");

  progress.style.display = "flex";
  barFill.style.width = "30%";
  label.textContent = `Uploading ${file.name.substring(0, 40)}…`;

  const form = new FormData();
  form.append("file", file);

  try {
    barFill.style.width = "60%";
    const r = await fetch(`${API}/papers/upload-pdf`, { method: "POST", body: form });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.detail || `HTTP ${r.status}`);
    }
    const data = await r.json();
    barFill.style.width = "100%";
    label.textContent = data.status === "duplicate"
      ? "Already in library."
      : `✓ Saved "${data.title.substring(0,40)}" — ${data.chunks} chunks`;
    await loadPapers();
  } catch (err) {
    barFill.style.background = "#ef4444";
    label.textContent = `✕ ${err.message}`;
  }

  setTimeout(() => {
    progress.style.display = "none";
    barFill.style.width = "0%";
    barFill.style.background = "";
  }, 3000);
}

// ═════════════════════════════════════════════════════════════════════════════
// CHAT
// ═════════════════════════════════════════════════════════════════════════════

function setupChat() {
  document.getElementById("btnSend").addEventListener("click", sendMessage);
  document.getElementById("btnClearChat").addEventListener("click", () => {
    chatHistory = [];
    document.getElementById("chatMessages").innerHTML = `
      <div class="msg msg-ai">
        <div class="msg-label">⚡ ResearchKit AI</div>
        <p>Chat cleared. Ask me anything about your saved papers.</p>
      </div>`;
  });
  document.getElementById("chatInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const query = input.value.trim();
  if (!query) return;

  input.value = "";
  appendMsg("user", query);
  chatHistory.push({ role: "user", content: query });

  const thinking = appendThinking();
  document.getElementById("btnSend").disabled = true;

  try {
    const r = await fetch(`${API}/chat/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, history: chatHistory.slice(-10) }),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    thinking.remove();
    appendAIMsg(data.answer, data.sources || []);
    chatHistory.push({ role: "assistant", content: data.answer });
  } catch {
    thinking.remove();
    appendAIMsg("⚠️ Could not reach the backend. Make sure it's running.", []);
  } finally {
    document.getElementById("btnSend").disabled = false;
  }
}

function appendMsg(role, text) {
  const msgs = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `msg msg-${role === "user" ? "user" : "ai"}`;
  div.textContent = text;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

function appendAIMsg(text, sources) {
  const msgs = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "msg msg-ai";
  let html = `<div class="msg-label">⚡ ResearchKit AI</div>
    <p>${esc(text).replace(/\n/g, "<br/>")}</p>`;
  if (sources.length) {
    html += `<div class="msg-sources">` +
      sources.map((s) =>
        `<a class="source-chip" href="${s.url}" target="_blank" rel="noopener">${esc(s.title.substring(0,40))}…</a>`
      ).join("") + `</div>`;
  }
  div.innerHTML = html;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
}

function appendThinking() {
  const msgs = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "msg msg-ai";
  div.innerHTML = `<div class="msg-label">⚡ ResearchKit AI</div>
    <div class="thinking-dots"><span></span><span></span><span></span></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

// ═════════════════════════════════════════════════════════════════════════════
// SYNTHESIS
// ═════════════════════════════════════════════════════════════════════════════

function setupSynth() {
  document.getElementById("btnSynthesize").addEventListener("click", runSynthesis);
}

async function runSynthesis() {
  const question = document.getElementById("synthQuestion").value.trim();
  if (!question) { document.getElementById("synthQuestion").focus(); return; }

  const topK = parseInt(document.getElementById("synthTopK").value, 10);
  const btn  = document.getElementById("btnSynthesize");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Synthesizing…`;
  document.getElementById("synthResults").style.display = "none";

  try {
    const r = await fetch(`${API}/papers/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: topK }),
    });
    if (r.status === 404) { toast((await r.json()).detail, "error"); return; }
    if (!r.ok) throw new Error(await r.text());
    renderSynth(await r.json());
  } catch (err) {
    toast("Synthesis failed: " + err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Synthesize Literature →";
  }
}

function renderSynth(data) {
  document.getElementById("synthText").textContent = data.synthesis || "–";

  // Contradictions
  const contradCard = document.getElementById("contradCard");
  const contradEl   = document.getElementById("synthContrad");
  if (data.contradictions?.length) {
    contradEl.innerHTML = data.contradictions
      .map((c) => `<div class="list-item contradiction">${esc(c)}</div>`).join("");
    contradCard.style.display = "";
  } else {
    contradCard.style.display = "none";
  }

  // Gaps
  document.getElementById("synthGaps").innerHTML = (data.gaps || [])
    .map((g) => `<div class="list-item gap">${esc(g)}</div>`).join("") ||
    `<span style="color:var(--text-3);font-size:12px">None identified.</span>`;

  // Sources
  document.getElementById("synthSources").innerHTML = (data.sources || [])
    .map((s) => `<a class="source-chip" href="${s.url}" target="_blank" rel="noopener"
      style="margin:2px">${esc(s.title.substring(0,50))}…</a>`).join("");

  document.getElementById("synthResults").style.display = "flex";
}

// ═════════════════════════════════════════════════════════════════════════════
// DIGEST
// ═════════════════════════════════════════════════════════════════════════════

function setupDigest() {
  const input  = document.getElementById("interestInput");
  const btnAdd = document.getElementById("btnAddInterest");

  const add = () => {
    const val = input.value.trim().toLowerCase();
    if (!val || interests.includes(val) || interests.length >= 10) return;
    interests.push(val);
    localStorage.setItem("interests", JSON.stringify(interests));
    renderInterestTags();
    input.value = "";
  };

  btnAdd.addEventListener("click", add);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") add(); });
  document.getElementById("btnFetchDigest").addEventListener("click", runDigest);
}

function renderInterestTags() {
  const container = document.getElementById("interestTags");
  if (!interests.length) {
    container.innerHTML = `<span class="no-tags">No interests yet</span>`;
    return;
  }
  container.innerHTML = interests.map((t, i) => `
    <span class="interest-tag">
      ${esc(t)}
      <button onclick="removeInterest(${i})" title="Remove">×</button>
    </span>`).join("");
}

function removeInterest(idx) {
  interests.splice(idx, 1);
  localStorage.setItem("interests", JSON.stringify(interests));
  renderInterestTags();
}

async function runDigest() {
  if (!interests.length) { toast("Add at least one interest first.", "error"); return; }

  const btn  = document.getElementById("btnFetchDigest");
  const days = parseInt(document.getElementById("digestDays").value, 10);
  const meta = document.getElementById("digestMeta");
  const results = document.getElementById("digestResults");

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Fetching…`;
  results.innerHTML = "";
  meta.textContent  = "";

  try {
    const r = await fetch(`${API}/digest/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interests, days, max_results: 20 }),
    });
    if (!r.ok) throw new Error(await r.text());
    renderDigest(await r.json());
  } catch (err) {
    results.innerHTML = `<div class="empty-state"><p>⚠️ ${esc(err.message)}</p></div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Check New Papers →";
  }
}

function renderDigest(data) {
  const meta    = document.getElementById("digestMeta");
  const results = document.getElementById("digestResults");

  meta.textContent = `${data.papers.length} relevant / ${data.total_fetched} fetched from arXiv`;

  if (!data.papers.length) {
    results.innerHTML = `<div class="empty-state"><p>No new papers matched your interests in this period.</p></div>`;
    return;
  }

  results.innerHTML = data.papers.map((p) => {
    const pct       = Math.round(p.relevance_score * 100);
    const cls       = pct >= 70 ? "score-high" : pct >= 40 ? "score-medium" : "score-low";
    const dateStr   = p.published ? new Date(p.published).toLocaleDateString() : "";
    const paperJson = esc(JSON.stringify(p));

    return `<div class="digest-card">
      <div class="digest-card-top">
        <div class="digest-title">${esc(p.title)}</div>
        <span class="digest-score ${cls}">${pct}% match</span>
      </div>
      <span class="digest-interest">${esc(p.matched_interest)}</span>
      <div class="digest-abstract">${esc(p.abstract.substring(0, 200))}…</div>
      <div class="digest-actions">
        <button class="btn-chip" onclick='saveDigestPaper(${paperJson})'>💾 Save</button>
        <a class="btn-chip" href="${p.url}" target="_blank" rel="noopener">🔗 Open</a>
        <span class="digest-date">${dateStr}</span>
      </div>
    </div>`;
  }).join("");
}

async function saveDigestPaper(paper) {
  try {
    const r = await fetch(`${API}/papers/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: paper.title, abstract: paper.abstract,
        authors: paper.authors || [], url: paper.url,
        source: "arxiv", paper_id: paper.paper_id,
      }),
    });
    if (!r.ok) throw new Error();
    const data = await r.json();
    if (data.status === "duplicate") { toast("Already in library.", "error"); return; }
    await loadPapers();
    toast(`Saved "${paper.title.substring(0,40)}…"`, "success");
  } catch { toast("Could not save paper.", "error"); }
}

// ═════════════════════════════════════════════════════════════════════════════
// JD ANALYZER
// ═════════════════════════════════════════════════════════════════════════════

function setupJD() {
  const savedResume = localStorage.getItem("resume");
  if (savedResume) document.getElementById("resumeText").value = savedResume;

  document.getElementById("btnAnalyze").addEventListener("click", analyzeJD);
}

async function analyzeJD() {
  const jd     = document.getElementById("jdText").value.trim();
  const resume = document.getElementById("resumeText").value.trim();
  if (!jd) { document.getElementById("jdText").focus(); return; }
  if (resume) localStorage.setItem("resume", resume);

  const btn = document.getElementById("btnAnalyze");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Analyzing…`;
  document.getElementById("jdResults").style.display = "none";

  try {
    const r = await fetch(`${API}/jd/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jd, resume_text: resume }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({}));
      throw new Error(e.detail || `HTTP ${r.status}`);
    }
    renderJD(await r.json());
  } catch (err) {
    toast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Analyze Skill Gap →";
  }
}

function renderJD(data) {
  const pct = Math.round(data.score * 100);
  const ring = document.getElementById("scoreRing");
  const color = pct >= 70 ? "#10b981" : pct >= 45 ? "#f59e0b" : "#ef4444";
  ring.style.background =
    `conic-gradient(${color} ${pct * 3.6}deg, var(--bg-3) 0)`;
  document.getElementById("scoreNum").textContent = `${pct}%`;
  document.getElementById("scoreSummary").textContent = data.summary || "";

  document.getElementById("matchedSkills").innerHTML =
    (data.matched_skills || []).map((s) =>
      `<span class="skill-chip chip-match">${esc(s)}</span>`).join("") ||
    `<span style="color:var(--text-3);font-size:12px">None found</span>`;

  document.getElementById("missingSkills").innerHTML =
    (data.missing_skills || []).map((s) =>
      `<span class="skill-chip chip-gap">${esc(s)}</span>`).join("") ||
    `<span style="color:var(--text-3);font-size:12px">None — great match!</span>`;

  document.getElementById("suggestions").innerHTML =
    (data.suggestions || []).map((s) =>
      `<div class="list-item action">${esc(s)}</div>`).join("") ||
    `<span style="color:var(--text-3);font-size:12px">No suggestions</span>`;

  document.getElementById("jdResults").style.display = "flex";
}

// ═════════════════════════════════════════════════════════════════════════════
// UTILS
// ═════════════════════════════════════════════════════════════════════════════

function esc(str = "") {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

let _toastTimer;
function toast(msg, type = "") {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.className = `toast show ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = "toast"; }, 3000);
}
