const API_BASE = "http://localhost:8000";

const scanBtn = document.getElementById("scan-btn");
const scanUrl = document.getElementById("scan-url");
const resultDiv = document.getElementById("result");
const loadingDiv = document.getElementById("loading");
const errorDiv = document.getElementById("error");
const scoreValue = document.getElementById("score-value");
const verdictBadge = document.getElementById("verdict-badge");
const flagsList = document.getElementById("flags-list");
const fullReportLink = document.getElementById("full-report-link");

const VERDICT_COLORS = {
  SAFE: { color: "#22C55E", bg: "#22C55E20" },
  SUSPICIOUS: { color: "#EAB308", bg: "#EAB30820" },
  LIKELY_FRAUD: { color: "#F97316", bg: "#F9731620" },
  FRAUD: { color: "#EF4444", bg: "#EF444420" },
};

// Auto-fill current tab URL
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0]?.url) {
    scanUrl.value = tabs[0].url;
  }
});

scanBtn.addEventListener("click", async () => {
  const url = scanUrl.value.trim();
  if (!url) return;

  resultDiv.classList.add("hidden");
  errorDiv.classList.add("hidden");
  loadingDiv.classList.remove("hidden");
  scanBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/api/v1/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) throw new Error("Scan failed");

    const data = await response.json();
    const vc = VERDICT_COLORS[data.verdict] || VERDICT_COLORS.SUSPICIOUS;

    scoreValue.textContent = data.trust_score;
    scoreValue.style.color = vc.color;

    verdictBadge.textContent = data.verdict.replace("_", " ");
    verdictBadge.style.color = vc.color;
    verdictBadge.style.background = vc.bg;

    flagsList.innerHTML = "";
    (data.flags || []).slice(0, 5).forEach((flag) => {
      const div = document.createElement("div");
      div.className = "flag-item";
      div.textContent = `⚠ ${flag}`;
      flagsList.appendChild(div);
    });

    fullReportLink.href = `http://localhost:5173/results/${data.scan_id}`;

    loadingDiv.classList.add("hidden");
    resultDiv.classList.remove("hidden");
  } catch (err) {
    loadingDiv.classList.add("hidden");
    errorDiv.textContent = "Scan failed. Make sure the TrustHire API is running.";
    errorDiv.classList.remove("hidden");
  } finally {
    scanBtn.disabled = false;
  }
});

// Enter key support
scanUrl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") scanBtn.click();
});
