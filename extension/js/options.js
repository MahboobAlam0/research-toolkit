// ─── ResearchKit AI · options.js ───────────────────────────────────────────────
"use strict";

const DEFAULT_BACKEND = "http://localhost:8000";

const input     = document.getElementById("backendUrl");
const btnSave   = document.getElementById("btnSave");
const btnTest   = document.getElementById("btnTest");
const btnReset  = document.getElementById("btnReset");
const statusBar = document.getElementById("statusBar");

// ── Load saved URL on open ─────────────────────────────────────────────────────
chrome.storage.sync.get({ backendUrl: DEFAULT_BACKEND }, ({ backendUrl }) => {
  input.value = backendUrl;
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function showStatus(msg, type = "ok") {
  statusBar.textContent = msg;
  statusBar.className = `status-bar show ${type}`;
}

function normalise(url) {
  return url.trim().replace(/\/+$/, "");
}

function originPattern(url) {
  try {
    const { protocol, hostname, port } = new URL(url);
    const portPart = port ? `:${port}` : "";
    return `${protocol}//${hostname}${portPart}/*`;
  } catch {
    return null;
  }
}

// ── Save ──────────────────────────────────────────────────────────────────────
btnSave.addEventListener("click", async () => {
  const url = normalise(input.value) || DEFAULT_BACKEND;
  input.value = url;

  // Localhost is already in host_permissions — no prompt needed
  if (url === DEFAULT_BACKEND || url.startsWith("http://localhost")) {
    chrome.storage.sync.set({ backendUrl: url }, () => {
      showStatus(`Saved. Using ${url}`, "ok");
    });
    return;
  }

  // For any external URL, request optional host permission first
  const pattern = originPattern(url);
  if (!pattern) {
    showStatus("Invalid URL — please enter a valid http/https address.", "err");
    return;
  }

  showStatus("Requesting permission…", "info");

  chrome.permissions.request({ origins: [pattern] }, (granted) => {
    if (granted) {
      chrome.storage.sync.set({ backendUrl: url }, () => {
        showStatus(`Permission granted ✓  Saved. Using ${url}`, "ok");
      });
    } else {
      showStatus(
        "Permission denied. Chrome needs access to that URL for the extension to work. " +
        "Click Save again and allow access when prompted.",
        "err"
      );
    }
  });
});

// ── Test connection ───────────────────────────────────────────────────────────
btnTest.addEventListener("click", async () => {
  const url = normalise(input.value) || DEFAULT_BACKEND;
  showStatus("Testing connection…", "info");
  try {
    const r = await fetch(`${url}/api/health`, { signal: AbortSignal.timeout(5000) });
    if (r.ok) {
      const data = await r.json();
      showStatus(
        `Connected ✓  —  ${data.service || "ResearchKit AI"} v${data.version || "?"}`,
        "ok"
      );
    } else {
      showStatus(`Server responded with HTTP ${r.status}. Is this the right URL?`, "err");
    }
  } catch {
    showStatus(
      `Could not reach ${url}.\n` +
      "• Check the URL is correct\n" +
      "• Make sure the backend is running\n" +
      "• If it's a new external URL, click Save first to grant permission.",
      "err"
    );
  }
});

// ── Reset ─────────────────────────────────────────────────────────────────────
btnReset.addEventListener("click", () => {
  input.value = DEFAULT_BACKEND;
  chrome.storage.sync.set({ backendUrl: DEFAULT_BACKEND }, () => {
    showStatus(`Reset to default (${DEFAULT_BACKEND})`, "info");
  });
});
