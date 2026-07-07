/**
 * TrustHire Content Script
 * Injected into LinkedIn, Naukri, Indeed, Internshala job pages.
 * Extracts job details and injects trust score badge next to each job listing.
 */

const API_BASE = "http://localhost:8000";
const BADGE_CLASS = "trusthire-badge";
const PROCESSED_CLASS = "trusthire-processed";
const SCAN_DEBOUNCE_MS = 800;

const SITE_CONFIGS = {
  "linkedin.com": {
    jobCards: ".job-card-container, .jobs-search-results__list-item",
    title: ".job-card-list__title, .job-card-container__link",
    company: ".job-card-container__company-name, .artdeco-entity-lockup__subtitle",
    description: ".job-card-container__company-name",
    injectAfter: ".job-card-list__title, .job-card-container__link",
  },
  "naukri.com": {
    jobCards: ".jobTuple, .cust-job-tuple, article.jobTuple, .srp-jobtuple-wrapper",
    title: ".title, .jobTitle a, .row1 .title",
    company: ".companyName, .comp-name, .row2 .subTitle",
    description: ".job-description, .job-desc",
    injectAfter: ".title, .jobTitle",
  },
  "indeed.com": {
    jobCards: ".job_seen_beacon, .tapItem, .resultContent",
    title: ".jobTitle a, h2.jobTitle span",
    company: ".companyName, .company_location span",
    description: ".job-snippet",
    injectAfter: ".jobTitle",
  },
  "internshala.com": {
    jobCards: ".internship_meta, .individual_internship",
    title: ".profile a, h3.job-internship-name",
    company: ".company_name a, .company_and_place a",
    description: ".internship_other_details_container",
    injectAfter: ".profile, h3.job-internship-name",
  },
};

function getSiteConfig() {
  const hostname = window.location.hostname;
  return Object.entries(SITE_CONFIGS).find(([key]) => hostname.includes(key))?.[1];
}

function createBadge(score, verdict, scanId) {
  const colors = {
    SAFE: { bg: "#14532d", border: "#22c55e", text: "#4ade80" },
    SUSPICIOUS: { bg: "#713f12", border: "#eab308", text: "#fde047" },
    LIKELY_FRAUD: { bg: "#7c2d12", border: "#f97316", text: "#fb923c" },
    FRAUD: { bg: "#7f1d1d", border: "#ef4444", text: "#f87171" },
  };
  const c = colors[verdict] || colors.SUSPICIOUS;

  const badge = document.createElement("a");
  badge.href = `http://localhost:5173/results/${scanId}`;
  badge.target = "_blank";
  badge.className = BADGE_CLASS;
  badge.style.textDecoration = "none";
  badge.innerHTML = `
    <span style="
      display: inline-flex; align-items: center; gap: 4px;
      background: ${c.bg}; border: 1px solid ${c.border};
      color: ${c.text}; border-radius: 20px;
      padding: 2px 8px; font-size: 11px; font-weight: 600;
      font-family: -apple-system, sans-serif; cursor: pointer;
      text-decoration: none; margin-left: 8px; vertical-align: middle;
      white-space: nowrap; letter-spacing: 0.02em;
    ">
      🛡 ${score}/100 · ${verdict.replace("_", " ")}
    </span>
  `;
  return badge;
}

function createLoadingBadge() {
  const badge = document.createElement("span");
  badge.className = `${BADGE_CLASS} trusthire-loading`;
  badge.innerHTML = `
    <span style="
      display: inline-flex; align-items: center; gap: 4px;
      background: #1e1b4b; border: 1px solid #4338ca;
      color: #818cf8; border-radius: 20px;
      padding: 2px 8px; font-size: 11px; font-weight: 600;
      font-family: -apple-system, sans-serif; margin-left: 8px;
      vertical-align: middle; white-space: nowrap;
    ">
      🛡 Scanning...
    </span>
  `;
  return badge;
}

async function scanJobCard(card, config) {
  if (card.classList.contains(PROCESSED_CLASS)) return;
  card.classList.add(PROCESSED_CLASS);

  const titleEl = card.querySelector(config.title);
  const companyEl = card.querySelector(config.company);
  const descEl = card.querySelector(config.description);
  const injectTarget = card.querySelector(config.injectAfter) || titleEl;

  if (!titleEl || !injectTarget) return;

  const loadingBadge = createLoadingBadge();
  injectTarget.appendChild(loadingBadge);

  try {
    const payload = {
      url: window.location.href,
      job_title: titleEl?.textContent?.trim() || "",
      company_name: companyEl?.textContent?.trim() || "",
      description: descEl?.textContent?.trim() || "",
    };

    const response = await fetch(`${API_BASE}/api/v1/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      const data = await response.json();
      loadingBadge.remove();
      const badge = createBadge(data.trust_score, data.verdict, data.scan_id);
      injectTarget.appendChild(badge);
    } else {
      loadingBadge.remove();
    }
  } catch (err) {
    loadingBadge.remove();
    console.debug("TrustHire scan failed:", err);
  }
}

function scanVisibleCards() {
  const config = getSiteConfig();
  if (!config) return;
  const cards = document.querySelectorAll(`${config.jobCards}:not(.${PROCESSED_CLASS})`);
  cards.forEach((card) => scanJobCard(card, config));
}

// Observe DOM changes (infinite scroll, SPA navigation)
const observer = new MutationObserver(() => {
  clearTimeout(window._trusthireTimeout);
  window._trusthireTimeout = setTimeout(scanVisibleCards, SCAN_DEBOUNCE_MS);
});
observer.observe(document.body, { childList: true, subtree: true });

// Initial scan
setTimeout(scanVisibleCards, 1500);
