// ─── ResearchKit AI · content.js ──────────────────────────────────────────────
// Extracts paper metadata from arXiv, PubMed, and Semantic Scholar pages.
// Injects a floating "Save Paper" button when a supported paper page is detected.

(function () {
  "use strict";

  const DEFAULT_BACKEND = "http://localhost:8000";
  let API_BASE = `${DEFAULT_BACKEND}/api`;

  // ── Extractors ──────────────────────────────────────────────────────────────

  function extractArxiv() {
    const title =
      document.querySelector(".title.mathjax")?.innerText.replace("Title:", "").trim() ||
      document.querySelector("h1.title")?.innerText.trim();

    const abstract =
      document.querySelector(".abstract.mathjax")?.innerText.replace("Abstract:", "").trim() ||
      document.querySelector("blockquote.abstract")?.innerText.trim();

    const authors = Array.from(
      document.querySelectorAll(".authors a")
    ).map((a) => a.innerText.trim());

    const arxivId = window.location.pathname.split("/abs/")[1];

    return {
      title,
      abstract,
      authors,
      url: window.location.href,
      source: "arxiv",
      paper_id: arxivId,
    };
  }

  function extractPubMed() {
    const title = document.querySelector(".heading-title")?.innerText.trim();

    const abstract = document.querySelector(".abstract-content")?.innerText.trim();

    const authors = Array.from(
      document.querySelectorAll(".authors-list .full-name")
    ).map((a) => a.innerText.trim());

    const pmid = document.querySelector(".current-id")?.innerText.trim() ||
      window.location.pathname.replace("/", "");

    return {
      title,
      abstract,
      authors,
      url: window.location.href,
      source: "pubmed",
      paper_id: pmid,
    };
  }

  function extractSemanticScholar() {
    const title = document.querySelector('[data-test-id="paper-detail-title"]')?.innerText.trim()
      || document.querySelector("h1")?.innerText.trim();

    const abstract = document.querySelector('[data-test-id="truncated-text"]')?.innerText.trim()
      || document.querySelector(".abstract")?.innerText.trim();

    const authors = Array.from(
      document.querySelectorAll('[data-test-id="author-list"] .author-list__link')
    ).map((a) => a.innerText.trim());

    const pathParts = window.location.pathname.split("/");
    const paperId = pathParts[pathParts.length - 1];

    return {
      title,
      abstract,
      authors,
      url: window.location.href,
      source: "semantic_scholar",
      paper_id: paperId,
    };
  }

  function getPaperData() {
    const host = window.location.hostname;
    if (host.includes("arxiv.org")) return extractArxiv();
    if (host.includes("pubmed.ncbi.nlm.nih.gov")) return extractPubMed();
    if (host.includes("semanticscholar.org")) return extractSemanticScholar();
    return null;
  }

  // ── Floating Save Button ────────────────────────────────────────────────────

  function injectButton(paper) {
    if (document.getElementById("rk-save-btn")) return;

    const btn = document.createElement("button");
    btn.id = "rk-save-btn";
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
        <polyline points="17 21 17 13 7 13 7 21"/>
        <polyline points="7 3 7 8 15 8"/>
      </svg>
      Save to ResearchKit
    `;

    Object.assign(btn.style, {
      position: "fixed",
      bottom: "24px",
      right: "24px",
      zIndex: "999999",
      background: "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
      color: "#fff",
      border: "none",
      borderRadius: "12px",
      padding: "12px 20px",
      fontSize: "14px",
      fontWeight: "600",
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      gap: "8px",
      boxShadow: "0 8px 32px rgba(0,212,255,0.3)",
      transition: "all 0.2s ease",
      fontFamily: "'DM Sans', system-ui, sans-serif",
    });

    btn.onmouseenter = () => { btn.style.transform = "translateY(-2px)"; btn.style.boxShadow = "0 12px 40px rgba(0,212,255,0.4)"; };
    btn.onmouseleave = () => { btn.style.transform = "translateY(0)"; btn.style.boxShadow = "0 8px 32px rgba(0,212,255,0.3)"; };

    btn.onclick = () => savePaper(paper, btn);
    document.body.appendChild(btn);
  }

  async function savePaper(paper, btn) {
    if (!paper.title || !paper.abstract) {
      showToast("⚠️ Could not extract paper content.", "error");
      return;
    }

    btn.innerHTML = `<span style="animation: spin 1s linear infinite; display:inline-block">⟳</span> Saving...`;
    btn.disabled = true;

    try {
      const response = await fetch(`${API_BASE}/papers/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(paper),
      });

      if (!response.ok) throw new Error(await response.text());

      btn.innerHTML = `✓ Saved!`;
      btn.style.background = "linear-gradient(135deg, #10b981, #059669)";
      showToast(`✓ "${paper.title?.substring(0, 50)}…" saved!`, "success");
      setTimeout(() => btn.remove(), 2000);
    } catch (err) {
      btn.innerHTML = `✕ Failed`;
      btn.style.background = "linear-gradient(135deg, #ef4444, #dc2626)";
      showToast("Backend not running. Start with: docker-compose up", "error");
      setTimeout(() => {
        btn.innerHTML = `Save to ResearchKit`;
        btn.style.background = "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)";
        btn.disabled = false;
      }, 3000);
    }
  }

  // ── Toast Notification ──────────────────────────────────────────────────────

  function showToast(message, type = "success") {
    const toast = document.createElement("div");
    toast.innerText = message;
    Object.assign(toast.style, {
      position: "fixed",
      bottom: "80px",
      right: "24px",
      zIndex: "999998",
      background: type === "success" ? "#10b981" : "#ef4444",
      color: "#fff",
      padding: "10px 16px",
      borderRadius: "8px",
      fontSize: "13px",
      fontFamily: "'DM Sans', system-ui, sans-serif",
      maxWidth: "300px",
      boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
      transition: "opacity 0.3s ease",
    });
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = "0"; setTimeout(() => toast.remove(), 300); }, 3000);
  }

  // ── Init ────────────────────────────────────────────────────────────────────

  // Load configurable backend URL, then inject the save button
  chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND }, ({ backendUrl }) => {
    API_BASE = `${backendUrl}/api`;
    const paper = getPaperData();
    if (paper && paper.title) {
      injectButton(paper);
    }
  });

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg.type === "GET_PAPER_DATA") {
      sendResponse(getPaperData());
    }
  });
})();
