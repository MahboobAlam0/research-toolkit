// ─── ResearchKit AI · popup.js ────────────────────────────────────────────────
"use strict";

const DEFAULT_BACKEND = "http://localhost:8000";
let API = `${DEFAULT_BACKEND}/api`;

// ── State ──────────────────────────────────────────────────────────────────────
let papers      = [];
let chatHistory = [];
let interests   = [];   // digest interest strings

// ── DOM refs ───────────────────────────────────────────────────────────────────
const statusDot     = document.getElementById("statusDot");
const papersList    = document.getElementById("papersList");
const paperCount    = document.getElementById("paperCount");
const chatMessages  = document.getElementById("chatMessages");
const chatInput     = document.getElementById("chatInput");
const btnSend       = document.getElementById("btnSend");
const btnAnalyze    = document.getElementById("btnAnalyze");
const jdText        = document.getElementById("jdText");
const resumeText    = document.getElementById("resumeText");
const jdResults     = document.getElementById("jdResults");
const scoreRing     = document.getElementById("scoreRing");
const scoreNum      = document.getElementById("scoreNum");
const matchedSkills = document.getElementById("matchedSkills");
const missingSkills = document.getElementById("missingSkills");
const suggestions   = document.getElementById("suggestions");

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await new Promise((resolve) => {
    chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND }, ({ backendUrl }) => {
      API = `${backendUrl}/api`;
      resolve();
    });
  });

  await checkBackend();
  await loadPapers();
  loadStoredResume();
  loadStoredInterests();
  setupTabs();
  setupChat();
  setupSynth();
  setupJD();
  setupPDFUpload();
  setupDigest();
  document.getElementById("btnRefreshPapers").addEventListener("click", loadPapers);
});

// ── Health Check ───────────────────────────────────────────────────────────────
async function checkBackend() {
  try {
    const r = await fetch(`${API}/health`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      statusDot.classList.add("online");
      statusDot.title = "Backend online";
    }
  } catch {
    statusDot.classList.remove("online");
    statusDot.title = "Backend offline — run: docker compose up";
  }
}

// ── Tab Logic ──────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
    });
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// PAPERS
// ══════════════════════════════════════════════════════════════════════════════

async function loadPapers() {
  try {
    const r = await fetch(`${API}/papers/list`);
    if (!r.ok) throw new Error();
    papers = await r.json();
    renderPapers();
    paperCount.textContent = papers.length;
    chrome.runtime.sendMessage({ type: "REFRESH_BADGE" });
  } catch {
    renderOfflineState();
  }
}

function renderPapers() {
  if (!papers.length) {
    papersList.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">📄</div>
        <p>No papers saved yet.<br/>
        Visit <strong>arXiv</strong>, <strong>PubMed</strong>, or <strong>Semantic Scholar</strong>
        and click <strong>Save to ResearchKit</strong> — or use <strong>⬆ PDF</strong> above.</p>
      </div>`;
    return;
  }
  papersList.innerHTML = papers.map((p) => `
    <div class="paper-card" data-id="${p.id}">
      <span class="paper-source-badge badge-${p.source}">${p.source.replace("_", " ")}</span>
      <div class="paper-title">${escapeHtml(p.title)}</div>
      <div class="paper-authors">${escapeHtml((p.authors || []).join(", ") || "Unknown authors")}</div>
      <div class="paper-actions">
        <button class="btn-icon ask" onclick="askAboutPaper('${escapeHtml(p.title.substring(0, 60))}')">💬 Ask</button>
        <a href="${p.url}" target="_blank" class="btn-icon" style="text-decoration:none">🔗 Open</a>
        <button class="btn-icon" onclick="deletePaper('${p.id}')">🗑</button>
      </div>
    </div>`
  ).join("");
}

function renderOfflineState() {
  papersList.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">⚡</div>
      <p>Backend not running.<br/>Start with:<br/><strong>docker compose up</strong></p>
    </div>`;
}

async function deletePaper(id) {
  try {
    await fetch(`${API}/papers/${id}`, { method: "DELETE" });
    await loadPapers();
  } catch { showError("Could not delete paper."); }
}

function askAboutPaper(title) {
  document.querySelector('[data-tab="chat"]').click();
  // Switch to chat mode
  activateChatMode("chat");
  chatInput.value = `Summarize the paper: "${title}"`;
  chatInput.focus();
}

// ── PDF Upload ─────────────────────────────────────────────────────────────────
function setupPDFUpload() {
  const fileInput = document.getElementById("pdfFileInput");
  const btnUpload = document.getElementById("btnUploadPdf");
  const uploadBar = document.getElementById("uploadBar");
  const barInner  = document.getElementById("uploadBarInner");
  const barLabel  = document.getElementById("uploadBarLabel");

  btnUpload.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    fileInput.value = "";  // allow re-upload of same file

    // Show progress bar (indeterminate — just animate)
    uploadBar.classList.add("show");
    barInner.style.width = "30%";
    barLabel.textContent = `Uploading ${file.name.substring(0, 30)}…`;

    const formData = new FormData();
    formData.append("file", file);

    try {
      barInner.style.width = "60%";
      const r = await fetch(`${API}/papers/upload-pdf`, { method: "POST", body: formData });
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(err.detail || `HTTP ${r.status}`);
      }
      const data = await r.json();
      barInner.style.width = "100%";

      if (data.status === "duplicate") {
        barLabel.textContent = "Already in library.";
      } else {
        barLabel.textContent = `✓ Saved "${data.title.substring(0, 35)}" — ${data.chunks} chunks`;
        await loadPapers();
      }
    } catch (err) {
      barInner.style.background = "#ef4444";
      barLabel.textContent = `✕ ${err.message}`;
    }

    setTimeout(() => {
      uploadBar.classList.remove("show");
      barInner.style.width  = "0%";
      barInner.style.background = "";
    }, 3000);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// CHAT (RAG)
// ══════════════════════════════════════════════════════════════════════════════

function setupChat() {
  btnSend.addEventListener("click", sendMessage);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
}

async function sendMessage() {
  const query = chatInput.value.trim();
  if (!query) return;

  chatInput.value = "";
  appendMessage("user", query);
  chatHistory.push({ role: "user", content: query });

  const thinkingEl = appendThinking();
  btnSend.disabled = true;

  try {
    const r = await fetch(`${API}/chat/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, history: chatHistory.slice(-10) }),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    thinkingEl.remove();
    appendAIMessage(data.answer, data.sources || []);
    chatHistory.push({ role: "assistant", content: data.answer });
  } catch {
    thinkingEl.remove();
    appendAIMessage("⚠️ Could not connect to backend. Make sure it's running with `docker compose up`.", []);
  } finally {
    btnSend.disabled = false;
  }
}

function appendMessage(role, text) {
  const div = document.createElement("div");
  div.className = `msg msg-${role === "user" ? "user" : "ai"}`;
  div.textContent = text;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

function appendAIMessage(text, sources) {
  const div = document.createElement("div");
  div.className = "msg msg-ai";
  let html = `<div class="msg-label">⚡ ResearchKit AI</div>`;
  html += `<div>${escapeHtml(text).replace(/\n/g, "<br/>")}</div>`;
  if (sources.length) {
    html += `<div class="msg-sources"><p>📎 Sources</p>`;
    sources.forEach((s) => {
      html += `<a class="source-chip" href="${s.url}" target="_blank" title="${escapeHtml(s.title)}">${escapeHtml(s.title.substring(0, 35))}…</a>`;
    });
    html += `</div>`;
  }
  div.innerHTML = html;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendThinking() {
  const div = document.createElement("div");
  div.className = "msg msg-ai";
  div.innerHTML = `<div class="msg-label">⚡ ResearchKit AI</div>
    <div class="thinking-dots"><span></span><span></span><span></span></div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// ══════════════════════════════════════════════════════════════════════════════
// SYNTHESIS
// ══════════════════════════════════════════════════════════════════════════════

function setupSynth() {
  document.getElementById("btnModeChat").addEventListener("click", () => activateChatMode("chat"));
  document.getElementById("btnModeSynth").addEventListener("click", () => activateChatMode("synth"));
  document.getElementById("btnSynthesize").addEventListener("click", runSynthesis);
}

function activateChatMode(mode) {
  const isChat = mode === "chat";
  document.getElementById("btnModeChat").classList.toggle("active", isChat);
  document.getElementById("btnModeSynth").classList.toggle("active", !isChat);
  document.getElementById("chatView").style.display  = isChat  ? "" : "none";
  document.getElementById("synthView").style.display = !isChat ? "" : "none";
}

async function runSynthesis() {
  const question = document.getElementById("synthQuestion").value.trim();
  if (!question) { document.getElementById("synthQuestion").focus(); return; }

  const btn = document.getElementById("btnSynthesize");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Synthesizing…`;

  const resultsEl = document.getElementById("synthResults");
  resultsEl.style.display = "none";

  try {
    const r = await fetch(`${API}/papers/synthesize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, top_k: 15 }),
    });

    if (r.status === 404) {
      const d = await r.json();
      showError(d.detail || "No relevant papers found.");
      return;
    }
    if (!r.ok) throw new Error(await r.text());

    const data = await r.json();
    renderSynthResults(data);
  } catch (err) {
    showError("Synthesis failed: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Synthesize Literature →";
  }
}

function renderSynthResults(data) {
  document.getElementById("synthText").textContent = data.synthesis || "–";

  // Contradictions
  const contradEl = document.getElementById("synthContrad");
  const contradCard = document.getElementById("synthContradCard");
  if (data.contradictions && data.contradictions.length) {
    contradEl.innerHTML = data.contradictions
      .map((c) => `<div class="synth-list-item contradiction">${escapeHtml(c)}</div>`)
      .join("");
    contradCard.style.display = "";
  } else {
    contradCard.style.display = "none";
  }

  // Gaps
  const gapsEl = document.getElementById("synthGaps");
  gapsEl.innerHTML = (data.gaps || [])
    .map((g) => `<div class="synth-list-item gap">${escapeHtml(g)}</div>`)
    .join("") || `<span style="color:var(--text-3);font-size:12px">None identified.</span>`;

  // Sources
  const sourcesEl   = document.getElementById("synthSources");
  const sourcesCard = document.getElementById("synthSourcesCard");
  if (data.sources && data.sources.length) {
    sourcesEl.innerHTML = data.sources
      .map((s) => `<a class="source-chip" href="${s.url}" target="_blank">${escapeHtml(s.title.substring(0, 40))}…</a>`)
      .join(" ");
    sourcesCard.style.display = "";
  } else {
    sourcesCard.style.display = "none";
  }

  document.getElementById("synthResults").style.display = "flex";

  // Scroll synthesis view to results
  const sv = document.getElementById("synthView");
  sv.scrollTop = sv.scrollHeight;
}

// ══════════════════════════════════════════════════════════════════════════════
// DIGEST
// ══════════════════════════════════════════════════════════════════════════════

function loadStoredInterests() {
  chrome.storage.local.get("interests", ({ interests: stored }) => {
    interests = stored || [];
    renderInterestTags();
  });
}

function saveInterests() {
  chrome.storage.local.set({ interests });
}

function setupDigest() {
  const input    = document.getElementById("interestInput");
  const btnAdd   = document.getElementById("btnAddInterest");
  const btnFetch = document.getElementById("btnFetchDigest");

  const addInterest = () => {
    const val = input.value.trim().toLowerCase();
    if (!val || interests.includes(val) || interests.length >= 10) return;
    interests.push(val);
    saveInterests();
    renderInterestTags();
    input.value = "";
  };

  btnAdd.addEventListener("click", addInterest);
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") addInterest(); });
  btnFetch.addEventListener("click", runDigest);
}

function renderInterestTags() {
  const container = document.getElementById("interestTags");
  if (!interests.length) {
    container.innerHTML = `<span class="no-interests">No interests added yet.</span>`;
    return;
  }
  container.innerHTML = interests.map((t, i) => `
    <span class="interest-tag">
      ${escapeHtml(t)}
      <button onclick="removeInterest(${i})" title="Remove">×</button>
    </span>`
  ).join("");
}

function removeInterest(idx) {
  interests.splice(idx, 1);
  saveInterests();
  renderInterestTags();
}

async function runDigest() {
  if (!interests.length) {
    showError("Add at least one interest topic first.");
    return;
  }

  const btn     = document.getElementById("btnFetchDigest");
  const days    = parseInt(document.getElementById("digestDays").value, 10);
  const meta    = document.getElementById("digestMeta");
  const results = document.getElementById("digestResults");

  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Fetching…`;
  results.innerHTML = "";
  meta.style.display = "none";

  try {
    const r = await fetch(`${API}/digest/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interests, days, max_results: 20 }),
    });
    if (!r.ok) throw new Error(await r.text());
    const data = await r.json();
    renderDigestResults(data);
  } catch (err) {
    results.innerHTML = `<div class="empty-state"><p>⚠️ ${escapeHtml(err.message)}</p></div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = "Check New Papers →";
  }
}

function renderDigestResults(data) {
  const meta    = document.getElementById("digestMeta");
  const results = document.getElementById("digestResults");

  meta.textContent = `${data.papers.length} relevant papers found (${data.total_fetched} fetched from arXiv)`;
  meta.style.display = "block";

  if (!data.papers.length) {
    results.innerHTML = `<div class="empty-state"><p>No new papers matched your interests in this period.</p></div>`;
    return;
  }

  results.innerHTML = data.papers.map((p) => {
    const score    = Math.round(p.relevance_score * 100);
    const relClass = score >= 70 ? "rel-high" : score >= 40 ? "rel-medium" : "rel-low";
    const dateStr  = p.published ? new Date(p.published).toLocaleDateString() : "";

    return `
    <div class="digest-card">
      <div class="digest-card-top">
        <div class="digest-title">${escapeHtml(p.title)}</div>
        <span class="digest-relevance ${relClass}">${score}% match</span>
      </div>
      <span class="digest-interest-tag">${escapeHtml(p.matched_interest)}</span>
      <div class="digest-abstract">${escapeHtml(p.abstract.substring(0, 180))}…</div>
      <div class="digest-actions">
        <button class="btn-icon" onclick="saveDigestPaper(${escapeHtml(JSON.stringify(JSON.stringify(p)))})">💾 Save</button>
        <a href="${p.url}" target="_blank" class="btn-icon" style="text-decoration:none">🔗 Open</a>
        <span class="digest-date">${dateStr}</span>
      </div>
    </div>`;
  }).join("");
}

async function saveDigestPaper(jsonStr) {
  let paper;
  try { paper = JSON.parse(jsonStr); } catch { return; }

  try {
    const r = await fetch(`${API}/papers/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title:    paper.title,
        abstract: paper.abstract,
        authors:  paper.authors || [],
        url:      paper.url,
        source:   "arxiv",
        paper_id: paper.paper_id,
      }),
    });
    if (!r.ok) throw new Error();
    const data = await r.json();
    if (data.status === "duplicate") {
      showError("Already in library.");
    } else {
      await loadPapers();
      showSuccess(`Saved "${paper.title.substring(0, 40)}…"`);
    }
  } catch {
    showError("Could not save paper.");
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// JD ANALYZER
// ══════════════════════════════════════════════════════════════════════════════

function setupJD() {
  btnAnalyze.addEventListener("click", analyzeJD);
}

function loadStoredResume() {
  chrome.storage.local.get("resume", ({ resume }) => {
    if (resume) resumeText.value = resume;
  });
}

async function analyzeJD() {
  const jd = jdText.value.trim();
  if (!jd) { jdText.focus(); return; }
  const resume = resumeText.value.trim();
  if (resume) chrome.storage.local.set({ resume });

  btnAnalyze.disabled = true;
  btnAnalyze.innerHTML = `<span class="spinner"></span>  Analyzing…`;
  jdResults.classList.remove("visible");

  try {
    const r = await fetch(`${API}/jd/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text: jd, resume_text: resume }),
    });
    if (!r.ok) throw new Error(await r.text());
    renderJDResults(await r.json());
  } catch (err) {
    btnAnalyze.innerHTML = "⚠️ " + (err.message.includes("Backend") ? "Backend offline" : "Error");
    setTimeout(() => { btnAnalyze.innerHTML = "Analyze Skill Gap →"; btnAnalyze.disabled = false; }, 3000);
    return;
  }

  btnAnalyze.innerHTML = "Analyze Skill Gap →";
  btnAnalyze.disabled = false;
}

function renderJDResults(data) {
  const pct = Math.round(data.score * 100);
  scoreRing.style.setProperty("--pct", `${pct * 3.6}deg`);
  scoreRing.style.background = `conic-gradient(${scoreColor(pct)} ${pct * 3.6}deg, var(--bg-3) 0)`;
  scoreNum.textContent = `${pct}%`;

  matchedSkills.innerHTML = (data.matched_skills || [])
    .map((s) => `<span class="skill-chip chip-match">${escapeHtml(s)}</span>`)
    .join("") || `<span style='color:var(--text-3);font-size:12px'>None found</span>`;

  missingSkills.innerHTML = (data.missing_skills || [])
    .map((s) => `<span class="skill-chip chip-gap">${escapeHtml(s)}</span>`)
    .join("") || `<span style='color:var(--text-3);font-size:12px'>None — great match!</span>`;

  suggestions.innerHTML = (data.suggestions || [])
    .map((s) => `<div class="suggestion-item">${escapeHtml(s)}</div>`)
    .join("") || `<span style='color:var(--text-3);font-size:12px'>No suggestions</span>`;

  jdResults.classList.add("visible");
  document.getElementById("jdInner").scrollTop = 9999;
}

function scoreColor(pct) {
  if (pct >= 70) return "#10b981";
  if (pct >= 45) return "#f59e0b";
  return "#ef4444";
}

// ══════════════════════════════════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════════════════════════════════

function escapeHtml(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function _toast(msg, color) {
  const t = document.createElement("div");
  t.textContent = msg;
  Object.assign(t.style, {
    position: "fixed", bottom: "14px", left: "50%",
    transform: "translateX(-50%)", background: color,
    color: "#fff", padding: "8px 16px", borderRadius: "8px",
    fontSize: "12px", zIndex: "9999", maxWidth: "340px",
    textAlign: "center", boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
  });
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function showError(msg)   { _toast(msg, "#ef4444"); }
function showSuccess(msg) { _toast(msg, "#10b981"); }
