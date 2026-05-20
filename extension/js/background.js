// ─── ResearchKit AI · background.js ───────────────────────────────────────────
// Service worker — handles badge updates and cross-tab messaging.

const API_BASE = "http://localhost:8000/api";

// Update extension badge with paper count on install / startup
chrome.runtime.onInstalled.addListener(() => {
  updateBadge();
});

chrome.runtime.onStartup.addListener(() => {
  updateBadge();
});

async function updateBadge() {
  try {
    const resp = await fetch(`${API_BASE}/papers/count`);
    if (resp.ok) {
      const { count } = await resp.json();
      chrome.action.setBadgeText({ text: count > 0 ? String(count) : "" });
      chrome.action.setBadgeBackgroundColor({ color: "#00d4ff" });
    }
  } catch {
    // Backend not running — clear badge
    chrome.action.setBadgeText({ text: "" });
  }
}

// Listen for badge refresh requests from popup/content
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "REFRESH_BADGE") {
    updateBadge();
    sendResponse({ ok: true });
  }
});
