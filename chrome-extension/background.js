/**
 * TrustHire Background Service Worker
 * Handles communication between popup, content scripts, and API.
 */

const API_BASE = "http://localhost:8000";

// Listen for messages from popup or content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SCAN_URL") {
    fetch(`${API_BASE}/api/v1/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: message.url,
        description: message.description || "",
        job_title: message.jobTitle || "",
        company_name: message.companyName || "",
      }),
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));

    return true; // Keep message channel open for async response
  }

  if (message.type === "GET_HISTORY") {
    fetch(`${API_BASE}/api/v1/history`)
      .then((r) => r.json())
      .then((data) => sendResponse({ success: true, data }))
      .catch((err) => sendResponse({ success: false, error: err.message }));

    return true;
  }
});

// On install, open onboarding page
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.tabs.create({ url: "http://localhost:5173/about" });
  }
});
