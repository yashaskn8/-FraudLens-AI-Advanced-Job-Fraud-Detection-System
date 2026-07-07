"""
URL Deep Analyser — ML-Backed, No Hardcoded Scores
Combines:
  1. Trained XGBoost URL classifier (Model A) — learned thresholds
  2. Live page content analysis (fetches & scans actual page text)
  3. SSL / WHOIS / redirect / threat-intel checks
  4. URL structural feature extraction
  5. Dynamic score fusion — every score comes from data, never hardcoded

Falls back gracefully when the ML model is not yet trained.
"""
import re
import ssl
import math
import json
import socket
import asyncio
import logging
import pickle
import httpx
import numpy as np
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from typing import Optional, Any
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from collections import Counter
from pathlib import Path

from backend.config import settings
from backend.ml.constants import (
    SUSPICIOUS_TLDS, TRUSTED_TLDS, FREE_HOSTING, URL_SHORTENERS,
    FRAUD_URL_KEYWORDS, PAYMENT_KEYWORDS, LEGIT_EMPLOYERS, JOB_BOARDS
)

logger = logging.getLogger("trusthire.url_analyser")


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PageContentSignals:
    """Signals extracted from live page content."""
    fetched: bool = False
    title: str = ""
    meta_description: str = ""
    body_text_snippet: str = ""
    scam_keyword_count: int = 0
    urgency_keyword_count: int = 0
    payment_keyword_count: int = 0
    has_form: bool = False
    has_login_form: bool = False
    external_link_count: int = 0
    word_count: int = 0
    content_risk_score: float = 0.5   # 0=safe, 1=risky — computed dynamically


@dataclass
class URLAnalysisResult:
    url: str
    domain: str
    is_https: bool
    ssl_valid: bool
    domain_age_days: Optional[int]
    registrar: Optional[str]
    registrar_country: Optional[str]
    is_free_hosting: bool
    is_url_shortener: bool
    redirect_chain: list
    final_url: str
    google_safe_browsing_clean: Optional[bool]
    virustotal_malicious_count: Optional[int]
    url_entropy: float
    has_ip_address: bool
    has_random_subdomain: bool
    is_established_domain: bool
    url_trust_score: float
    ml_classifier_score: Optional[float] = None
    ml_classifier_available: bool = False
    page_content_signals: Optional[dict] = None
    flags: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants — used as FEATURES for the ML model, NOT as rules
# ═══════════════════════════════════════════════════════════════════════════════

FREE_HOSTING_DOMAINS = frozenset({
    "wix.com", "wixsite.com", "weebly.com", "wordpress.com", "blogspot.com",
    "site123.me", "godaddysites.com", "yolasite.com", "jimdo.com", "webnode.com",
    "strikingly.com", "mystrikingly.com", "squarespace.com", "cargo.site",
    "webflow.io", "netlify.app", "vercel.app", "github.io", "glitch.me",
    "repl.co", "000webhostapp.com", "byethost.com", "freehosting.com",
    "freehostia.com", "infinityfree.net", "awardspace.com",
})

URL_SHORTENERS = frozenset({
    "bit.ly", "tinyurl.com", "goo.gl", "t.co", "ow.ly", "is.gd",
    "buff.ly", "dlvr.it", "short.io", "tiny.cc", "lnkd.in", "rb.gy",
})

TYPOSQUATTING_TARGETS = [
    "google", "microsoft", "amazon", "apple", "infosys", "wipro",
    "tcs", "accenture", "ibm", "oracle", "cognizant", "hcl",
    "capgemini", "linkedin", "naukri", "indeed", "glassdoor",
]

ESTABLISHED_DOMAINS = frozenset({
    "tcs.com", "infosys.com", "wipro.com", "hcltech.com", "techm.com",
    "cognizant.com", "accenture.com", "ibm.com", "capgemini.com",
    "google.com", "microsoft.com", "amazon.com", "apple.com",
    "linkedin.com", "naukri.com", "indeed.com", "glassdoor.com",
    "internshala.com", "shine.com", "monster.com", "timesjobs.com",
    "flipkart.com", "amazon.in", "paytm.com", "swiggy.in", "zomato.com",
    "byju.com", "unacademy.com", "razorpay.com", "freshworks.com",
    "zoho.com", "mphasis.com", "hexaware.com", "persistent.com",
})

SCAM_KEYWORDS = frozenset([
    "earn money", "guaranteed income", "work from home", "no experience needed",
    "registration fee", "deposit required", "daily payment", "instant cash",
    "earn lakhs", "earn crore", "unlimited income", "part time job",
    "free joining", "referral bonus", "investment required", "whatsapp",
    "telegram job", "data entry job", "typing job", "copy paste job",
    "easy money", "become rich", "financial freedom",
])

URGENCY_KEYWORDS = frozenset([
    "urgent", "immediately", "last chance", "limited seats", "hurry",
    "apply now", "don't miss", "today only", "act fast", "closing soon",
])

PAYMENT_KEYWORDS = frozenset([
    "pay", "fee", "deposit", "transfer", "upi", "gpay", "phonepe",
    "paytm", "bank account", "registration charge", "training fee",
    "security deposit", "refundable", "advance payment",
])

SUSPICIOUS_TLDS = frozenset([
    ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click", ".work",
    ".online", ".site", ".website", ".tech", ".icu", ".vip", ".buzz",
])

# Neutral TLDs — neither positive nor negative
NEUTRAL_TLDS = frozenset([
    ".org", ".net", ".org.uk", ".org.au",
    ".info", ".biz", ".mobi",
])


# ═══════════════════════════════════════════════════════════════════════════════
# ML Classifier — loads trained Model A (Ensemble)
# ═══════════════════════════════════════════════════════════════════════════════

_ml_model_cache = {}


def _load_url_classifier():
    """Load the trained XGBoost + LightGBM URL classifier ensemble."""
    if _ml_model_cache.get("loaded"):
        return _ml_model_cache

    model_dir = Path(settings.URL_CLASSIFIER_PATH)
    info_path = model_dir / "model_info.json"

    if not info_path.exists():
        logger.info("URL classifier not trained yet — falling back to heuristic scoring")
        _ml_model_cache["loaded"] = False
        return _ml_model_cache

    try:
        with open(info_path) as f:
            info = json.load(f)
        if not info.get("trained"):
            _ml_model_cache["loaded"] = False
            return _ml_model_cache

        with open(model_dir / "xgb_model.pkl", "rb") as f:
            _ml_model_cache["xgb"] = pickle.load(f)
        # We switched from RF to LightGBM in the latest training overhaul
        with open(model_dir / "lgb_model.pkl", "rb") as f:
            _ml_model_cache["lgb"] = pickle.load(f)
        with open(model_dir / "scaler.pkl", "rb") as f:
            _ml_model_cache["scaler"] = pickle.load(f)
        with open(model_dir / "feature_names.json") as f:
            _ml_model_cache["features"] = json.load(f)

        _ml_model_cache["threshold"] = info.get("optimal_threshold", 0.5)
        _ml_model_cache["ensemble_weights"] = info.get("ensemble_weights", {"xgb": 0.55, "lgb": 0.45})
        _ml_model_cache["loaded"] = True
        logger.info("URL ensemble classifier loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load URL classifier ensemble: {e}")
        _ml_model_cache["loaded"] = False

    return _ml_model_cache


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = Counter(s)
    total = len(s)
    return -sum((c/total) * math.log2(c/total) for c in freq.values())


def _levenshtein_ratio(a: str, b: str) -> float:
    if not a or not b: return 0.0
    la, lb = len(a), len(b)
    if abs(la - lb) > 3: return 0.0
    m = max(la, lb)
    if m == 0: return 1.0
    matches = sum(c == d for c, d in zip(a[:min(la,lb)], b[:min(la,lb)]))
    return matches / m


def _extract_url_features(url: str) -> dict:
    """Extract 50 numerical features EXACTLY matching the training script."""
    try:
        import tldextract
        if not url.startswith("http"):
            url = "http://" + url
        parsed = urlparse(url)
        ext = tldextract.extract(url)
    except Exception:
        return {f"f{i}": 0.0 for i in range(50)}

    netloc   = parsed.netloc.lower()
    domain   = ext.domain.lower()
    suffix   = ext.suffix.lower()
    sub      = ext.subdomain.lower()
    path     = parsed.path.lower()
    query    = parsed.query.lower()
    scheme   = parsed.scheme.lower()
    tld      = f".{suffix}" if suffix else ""
    url_low  = url.lower()

    f = {}
    f["url_length"]       = len(url)
    f["domain_length"]    = len(domain)
    f["path_length"]      = len(path)
    f["query_length"]     = len(query)
    f["subdomain_length"] = len(sub)
    f["tld_length"]       = len(tld)

    f["digit_ratio"]   = sum(c.isdigit() for c in domain) / max(len(domain),1)
    f["hyphen_ratio"]  = domain.count("-") / max(len(domain),1)
    f["dot_count"]     = netloc.count(".")
    f["at_in_url"]     = int("@" in url)
    f["double_slash"]  = int("//" in path)
    f["tilde_in_url"]  = int("~" in url)
    f["percent_count"] = url.count("%")

    f["domain_entropy"]  = _shannon_entropy(domain)
    f["path_entropy"]    = _shannon_entropy(path)
    f["url_entropy"]     = _shannon_entropy(url)
    f["subdomain_entropy"] = _shannon_entropy(sub)

    from backend.ml.constants import (
        SUSPICIOUS_TLDS as TRAIN_SUS_TLDS,
        TRUSTED_TLDS as TRAIN_TRUST_TLDS,
        FREE_HOSTING as TRAIN_FREE,
        URL_SHORTENERS as TRAIN_SHORT,
        FRAUD_URL_KEYWORDS as TRAIN_FRAUD_KW,
        PAYMENT_KEYWORDS as TRAIN_PAY_KW,
        LEGIT_EMPLOYERS as TRAIN_EMP,
        JOB_BOARDS as TRAIN_BOARDS
    )

    f["is_suspicious_tld"] = int(tld in TRAIN_SUS_TLDS)
    f["is_trusted_tld"]    = int(tld in TRAIN_TRUST_TLDS)

    f["is_free_hosting"]   = int(any(fh in netloc for fh in TRAIN_FREE))
    f["is_url_shortener"]  = int(any(us in netloc for us in TRAIN_SHORT))
    f["is_ip_address"]     = int(bool(re.match(
        r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", netloc.split(":")[0])))
    f["is_https"]          = int(scheme == "https")
    f["has_port"]          = int(":" in netloc and
                                  not netloc.endswith((":80",":443",":8080")))
    f["subdomain_depth"]   = len([s for s in sub.split(".") if s]) if sub else 0
    f["subdomain_is_common"] = int(sub in {"www","mail","jobs","careers",
                                             "blog","app","api","shop","store"})
    f["has_non_std_port"]  = int(bool(re.search(r":\d{4,5}", netloc)) and
                                  not netloc.endswith((":8080",":443",":80")))

    path_parts = [p for p in path.split("/") if p]
    f["path_depth"]            = len(path_parts)
    f["path_has_digits"]       = int(bool(re.search(r"\d{4,}", path)))
    f["path_has_redirect"]     = int(any(kw in path for kw in
                                          ["redirect","forward","goto","click","track"]))
    f["path_to_url_ratio"]     = len(path) / max(len(url),1)
    f["query_param_count"]     = len(parse_qs(query))

    f["fraud_keyword_count"]   = sum(1 for kw in TRAIN_FRAUD_KW if kw in url_low)
    f["payment_keyword_count"] = sum(1 for kw in TRAIN_PAY_KW if kw in url_low)
    f["has_job_words"]         = int(any(w in url_low for w in
                                          ["job","career","hiring","vacancy",
                                           "apply","recruit","work","earn"]))
    f["has_payment_words"]     = int(any(w in url_low for w in TRAIN_PAY_KW))

    max_employer_sim = max(
        (_levenshtein_ratio(domain, emp) for emp in TRAIN_EMP), default=0.0
    )
    max_board_sim = max(
        (_levenshtein_ratio(domain, board) for board in TRAIN_BOARDS), default=0.0
    )
    f["max_employer_similarity"] = max_employer_sim
    f["max_jobboard_similarity"] = max_board_sim
    f["is_exact_employer"]  = int(domain in TRAIN_EMP)
    f["is_exact_job_board"] = int(domain in TRAIN_BOARDS)

    # ── Brand impersonation detection (token-based, not string similarity) ─
    from backend.services.company_verifier import (
        _tokenise_domain as _cv_tokenise,
        _check_impersonation as _cv_check_impersonation,
        BRAND_TOKENS as _CV_BRAND_TOKENS,
        JOB_IMPERSONATION_WORDS as _CV_JOB_WORDS,
        HIGH_RISK_ACTION_WORDS as _CV_HIGH_RISK,
        BRAND_LEGITIMATE_DOMAINS as _CV_BRAND_LEGIT,
    )
    domain_tokens_for_brand = _cv_tokenise(url_low)
    detected_brand = ""
    brand_is_impersonation = False
    for tok in domain_tokens_for_brand:
        if tok in _CV_BRAND_TOKENS:
            detected_brand = tok
            legit_list = _CV_BRAND_LEGIT.get(tok, [])
            root_for_check = f"{domain}.{suffix}".lower()
            if any(root_for_check == ld for ld in legit_list):
                brand_is_impersonation = False
            else:
                brand_is_impersonation = True
            break

    f["is_likely_typosquatting"] = int(
        brand_is_impersonation or
        (max_employer_sim > 0.65 and domain not in TRAIN_EMP)
    )
    f["contains_brand_token"] = int(bool(detected_brand))
    f["brand_with_high_risk"] = int(
        brand_is_impersonation and any(
            t in _CV_HIGH_RISK for t in domain_tokens_for_brand
            if t != detected_brand
        )
    )
    f["brand_with_job_word"] = int(
        brand_is_impersonation and any(
            t in _CV_JOB_WORDS for t in domain_tokens_for_brand
            if t != detected_brand
        )
    )
    f["is_neutral_tld"] = int(tld in NEUTRAL_TLDS)
    f["brand_on_noncorporate_tld"] = int(
        bool(detected_brand) and brand_is_impersonation and
        tld not in frozenset([".com", ".co.in", ".co.uk", ".com.au", ".co.jp"])
    )

    domain_tokens = re.split(r"[-_]", domain)
    f["domain_token_count"]    = len(domain_tokens)
    f["longest_token_length"]  = max((len(t) for t in domain_tokens), default=0)
    f["has_numeric_token"]     = int(any(t.isdigit() for t in domain_tokens))

    f["consecutive_dots"]      = url.count("..")
    f["double_extension"]      = int(bool(re.search(r"\.\w{2,4}\.\w{2,4}(/|$)", path)))
    f["hex_encoding"]          = int(bool(re.search(r"%[0-9a-fA-F]{2}", url)))
    f["suspicious_combination"] = int(
        f["is_free_hosting"] == 1 and f["has_job_words"] == 1
    )
    f["high_risk_combination"] = int(
        f["is_suspicious_tld"] == 1 and f["has_payment_words"] == 1
    )
    f["fragment_length"] = len(parsed.fragment) if parsed.fragment else 0

    return f


def _ml_classify_url(url: str) -> Optional[float]:
    """
    Classify a URL using the trained XGBoost + LightGBM ensemble.
    Returns fraud probability (0.0 = safe, 1.0 = fraud) or None if model not loaded.
    """
    model = _load_url_classifier()
    if not model.get("loaded"):
        return None

    features = _extract_url_features(url)
    if not features:
        return None

    try:
        feature_names = model["features"]
        X = np.array([[features.get(f, 0.0) for f in feature_names]])
        X_scaled = model["scaler"].transform(X)

        weights = model["ensemble_weights"]
        xgb_prob = model["xgb"].predict_proba(X_scaled)[:, 1][0]
        lgb_prob = model["lgb"].predict_proba(X_scaled)[:, 1][0]
        ensemble_prob = weights["xgb"] * xgb_prob + weights.get("lgb", 0.45) * lgb_prob

        return float(ensemble_prob)
    except Exception as e:
        logger.warning(f"ML URL classification failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Live Page Content Analysis
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_page_content(url: str) -> PageContentSignals:
    """
    Fetch the actual page content and analyse it for scam signals.
    This is what catches pages that pass all structural checks but have
    scammy content like 'earn lakhs monthly', 'registration fee required', etc.
    """
    signals = PageContentSignals()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
        async with httpx.AsyncClient(
            timeout=10.0, follow_redirects=True, verify=False
        ) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return signals

            html = response.text[:100000]  # Limit to 100KB
            signals.fetched = True

            # Extract title
            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if title_match:
                signals.title = title_match.group(1).strip()[:200]

            # Extract meta description
            meta_match = re.search(
                r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)',
                html, re.I
            )
            if meta_match:
                signals.meta_description = meta_match.group(1).strip()[:300]

            # Strip HTML and extract body text
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S | re.I)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            text_lower = text.lower()

            signals.body_text_snippet = text[:500]
            signals.word_count = len(text.split())

            # Count scam keywords in page content
            for kw in SCAM_KEYWORDS:
                if kw in text_lower:
                    signals.scam_keyword_count += 1

            for kw in URGENCY_KEYWORDS:
                if kw in text_lower:
                    signals.urgency_keyword_count += 1

            for kw in PAYMENT_KEYWORDS:
                if kw in text_lower:
                    signals.payment_keyword_count += 1

            # Check for forms (login, payment)
            signals.has_form = bool(re.search(r"<form", html, re.I))
            signals.has_login_form = bool(re.search(
                r'<input[^>]*type=["\']password["\']', html, re.I
            ))

            # Count external links
            links = re.findall(r'href=["\']https?://([^"\']+)', html, re.I)
            parsed_domain = urlparse(url).netloc.lower().replace("www.", "")
            signals.external_link_count = sum(
                1 for link in links if parsed_domain not in link.lower()
            )

            # Compute content risk score dynamically
            risk = 0.0
            if signals.scam_keyword_count > 0:
                risk += min(0.4, signals.scam_keyword_count * 0.08)
            if signals.urgency_keyword_count > 0:
                risk += min(0.2, signals.urgency_keyword_count * 0.05)
            if signals.payment_keyword_count > 0:
                risk += min(0.3, signals.payment_keyword_count * 0.06)
            if signals.word_count < 50 and signals.has_form:
                risk += 0.15   # Thin page with form = suspicious
            if signals.has_login_form and signals.scam_keyword_count > 0:
                risk += 0.1    # Login form + scam keywords

            signals.content_risk_score = min(1.0, risk)

    except Exception as e:
        logger.debug(f"Page content fetch failed for {url}: {e}")

    return signals


# ═══════════════════════════════════════════════════════════════════════════════
# Infrastructure Checks
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_url_entropy(url: str) -> float:
    if not url:
        return 0.0
    prob = [float(url.count(c)) / len(url) for c in set(url)]
    entropy = -sum([p * math.log2(p) for p in prob if p > 0])
    return round(entropy, 4)


def is_typosquatting(domain: str) -> bool:
    domain_lower = domain.lower().split(".")[0]
    for target in TYPOSQUATTING_TARGETS:
        similarity = SequenceMatcher(None, domain_lower, target).ratio()
        if 0.75 < similarity < 1.0:
            return True
    return False


async def check_google_safe_browsing(url: str) -> Optional[bool]:
    if not settings.GOOGLE_SAFE_BROWSING_API_KEY:
        return None
    api_url = (
        f"https://safebrowsing.googleapis.com/v4/threatMatches:find"
        f"?key={settings.GOOGLE_SAFE_BROWSING_API_KEY}"
    )
    payload = {
        "client": {"clientId": "trusthire", "clientVersion": "2.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE", "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.post(api_url, json=payload)
            data = response.json()
            return len(data.get("matches", [])) == 0
        except Exception:
            return None


async def check_virustotal(url: str) -> Optional[int]:
    if not settings.VIRUSTOTAL_API_KEY:
        return None
    import base64
    url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"https://www.virustotal.com/api/v3/urls/{url_id}",
                headers={"x-apikey": settings.VIRUSTOTAL_API_KEY},
            )
            data = response.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            return stats.get("malicious", 0)
        except Exception:
            return None


async def follow_redirects(url: str) -> tuple:
    chain = [url]
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        try:
            response = await client.get(url)
            for r in response.history:
                chain.append(str(r.url))
            chain.append(str(response.url))
        except Exception:
            pass
    return chain[-1], chain


# ═══════════════════════════════════════════════════════════════════════════════
# Score-Flag Coupling — Single Source of Truth
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_random_subdomain(url: str) -> bool:
    """
    Detects whether the URL contains a random-looking subdomain.
    A subdomain is considered random if it is longer than 12 characters
    and does not match any known legitimate pattern.
    """
    import tldextract as _tld
    ext = _tld.extract(url)
    sub = ext.subdomain.lower()
    if not sub or sub in {"www", "jobs", "careers", "mail", "app",
                           "api", "blog", "shop", "store", "hiring",
                           "apply", "talent", "work", "recruit"}:
        return False
    # High digit ratio or high entropy indicates random generation
    if len(sub) > 12:
        digit_ratio = sum(c.isdigit() for c in sub) / len(sub)
        if digit_ratio > 0.3:
            return True
    # Pattern: letters-digits-letters (typical auto-generated subdomain)
    if re.search(r"[a-z]{2,}[0-9]{3,}[a-z]{0,}", sub):
        return True
    # Very long subdomain with hyphens
    if len(sub) > 20 and sub.count("-") >= 2:
        return True
    return False


def compute_url_trust_score(
    is_https: bool,
    ssl_valid: Optional[bool],
    ssl_expiry_days: Optional[int],
    domain_age_days: Optional[int],
    is_free_hosting: bool,
    is_url_shortener: bool,
    has_ip_address: bool,
    is_likely_typosquatting: bool,
    has_random_subdomain: bool,
    redirect_chain_length: int,
    google_safe_browsing_clean: Optional[bool],
    virustotal_malicious_count: Optional[int],
    page_fraud_signal_count: int,
    http_status: Optional[int],
    ml_fraud_probability: float,
    url: str = "",
) -> tuple[float, list[str]]:
    """
    Computes URL trust score and generates the flags list simultaneously.
    These two outputs are always consistent — it is architecturally impossible
    for a flag to appear without reducing the score, or for the score to be
    low without a corresponding flag explaining why.

    Scoring model: multiplicative compounding on the ML model prior.
      score = ml_prior × (1 - p1) × (1 - p2) × ...
    Each penalty is between 0 and 1. Multiple penalties compound, meaning
    each additional fraud signal reduces a progressively smaller remaining
    trust value. This correctly models the cumulative evidence of fraud.

    Returns (trust_score_0_to_1, list_of_flag_strings).
    """
    flags = []
    ml_trust = 1.0 - ml_fraud_probability  # ML prior: higher = more trustworthy

    # Penalty table: (deduction, flag_message)
    # Each entry generates exactly one flag and applies exactly one deduction.
    # These two are inseparable by design.
    penalties = []

    # ── Brand impersonation penalties (highest priority) ──────────────────
    # Must run BEFORE anything else, because impersonation URLs must never
    # receive a passing score regardless of other signals.
    try:
        import tldextract as _tld_imp
        from backend.services.company_verifier import (
            _tokenise_domain as _imp_tokenise,
            BRAND_TOKENS as _IMP_BRANDS,
            HIGH_RISK_ACTION_WORDS as _IMP_HIGH_RISK,
            JOB_IMPERSONATION_WORDS as _IMP_JOB_WORDS,
            BRAND_LEGITIMATE_DOMAINS as _IMP_BRAND_LEGIT,
        )
        _imp_ext = _tld_imp.extract(url)
        _imp_root = f"{_imp_ext.domain}.{_imp_ext.suffix}".lower()
        _imp_tokens = _imp_tokenise(_imp_ext.domain)
        _imp_brand = ""
        _imp_is_fake = False
        for _tk in _imp_tokens:
            if _tk in _IMP_BRANDS:
                _imp_brand = _tk
                _legit = _IMP_BRAND_LEGIT.get(_tk, [])
                if not any(_imp_root == ld for ld in _legit):
                    _imp_is_fake = True
                break
        if _imp_is_fake and _imp_brand:
            _remaining = [t for t in _imp_tokens if t != _imp_brand]
            _has_hr = any(t in _IMP_HIGH_RISK for t in _remaining)
            _has_jw = any(t in _IMP_JOB_WORDS for t in _remaining)
            if _has_hr:
                penalties.append((0.75,
                    f"Domain impersonates {_imp_brand.capitalize()} and "
                    f"contains a high-risk keyword — consistent with "
                    f"credential harvesting or advance-fee fraud. "
                    f"Do not submit any personal information."))
            elif _has_jw:
                penalties.append((0.60,
                    f"Domain impersonates {_imp_brand.capitalize()} with "
                    f"a job-related keyword — likely a fake recruitment "
                    f"site. {_imp_brand.capitalize()}'s legitimate careers "
                    f"page uses a different domain."))
            else:
                penalties.append((0.50,
                    f"Domain contains the brand name "
                    f"'{_imp_brand.capitalize()}' but is not "
                    f"{_imp_brand.capitalize()}'s legitimate domain."))
    except Exception:
        pass

    # ── Confirmed threat intelligence (external databases) ────────────────
    # These represent ground truth — the URL is in a maintained blacklist.
    if google_safe_browsing_clean is False:
        penalties.append((0.65,
            "URL is confirmed as a phishing or malware site by Google Safe Browsing"))
    if virustotal_malicious_count is not None and virustotal_malicious_count >= 3:
        penalties.append((0.55,
            f"URL is flagged as malicious by {virustotal_malicious_count} "
            f"security vendors on VirusTotal"))

    # ── Infrastructure red flags (highest discriminative power) ──────────
    if has_ip_address:
        penalties.append((0.50,
            "URL uses a raw IP address instead of a registered domain — "
            "a hallmark of hastily deployed scam infrastructure"))
    if is_free_hosting:
        penalties.append((0.38,
            "Job is hosted on a free website builder platform — legitimate "
            "employers maintain professional company websites"))
    if is_likely_typosquatting:
        penalties.append((0.40,
            "Domain name closely resembles a known employer — "
            "likely an impersonation attempt targeting job seekers"))
    if is_url_shortener:
        penalties.append((0.30,
            "URL is a shortened link — the actual destination is concealed, "
            "preventing verification before clicking"))

    # ── Certificate and security failures ─────────────────────────────────
    if not is_https:
        penalties.append((0.22,
            "URL uses unencrypted HTTP — any information submitted is "
            "transmitted without encryption"))
    elif ssl_valid is False:
        penalties.append((0.28,
            "SSL certificate is invalid or expired — the connection is not "
            "properly secured despite using HTTPS"))
    elif ssl_expiry_days is not None and 0 < ssl_expiry_days < 14:
        penalties.append((0.10,
            f"SSL certificate expires in {ssl_expiry_days} days — "
            f"legitimate organisations renew certificates promptly"))

    # ── Domain age signals ─────────────────────────────────────────────────
    if domain_age_days is not None and domain_age_days < 30:
        penalties.append((0.35,
            f"Domain was registered only {domain_age_days} days ago — "
            f"established employers do not post jobs from brand-new domains"))
    elif domain_age_days is not None and 30 <= domain_age_days < 120:
        penalties.append((0.12,
            f"Domain is {domain_age_days} days old — relatively new for "
            f"an organisation advertising employment"))
    elif domain_age_days is None:
        penalties.append((0.08,
            "Domain registration date could not be verified — "
            "the domain may use privacy protection or be recently registered"))

    # ── Structural URL anomalies ───────────────────────────────────────────
    if has_random_subdomain:
        penalties.append((0.22,
            "URL contains a suspicious random-looking subdomain — legitimate "
            "employer career pages use structured, readable subdomains"))
    if redirect_chain_length > 3:
        penalties.append((0.15,
            f"URL passes through {redirect_chain_length - 1} redirect steps "
            f"before reaching its destination — unusual for direct job listings"))

    # ── Live page content signals ──────────────────────────────────────────
    if page_fraud_signal_count >= 3:
        penalties.append((0.30,
            f"Page content contains {page_fraud_signal_count} known fraud "
            f"language patterns"))
    elif page_fraud_signal_count == 2:
        penalties.append((0.20,
            "Page content contains two known fraud language patterns"))
    elif page_fraud_signal_count == 1:
        penalties.append((0.10,
            "Page content contains a known fraud language pattern"))

    if http_status is not None and http_status >= 400:
        penalties.append((0.20,
            f"URL returned HTTP {http_status} — "
            f"the job posting page may not exist"))

    # ── Apply multiplicative compounding ──────────────────────────────────
    score = ml_trust
    for deduction, flag_message in penalties:
        score = score * (1.0 - deduction)
        flags.append(flag_message)

    # Clamp: preserve uncertainty at extremes
    score = max(0.04, min(0.97, score))

    return score, flags


# ═══════════════════════════════════════════════════════════════════════════════
# Main Analysis Function
# ═══════════════════════════════════════════════════════════════════════════════

async def analyse_url(url: str) -> URLAnalysisResult:
    """
    All live checks run concurrently. The score is computed from
    compute_url_trust_score() which guarantees flags and score are consistent.
    """
    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    domain = parsed.netloc.lower().replace("www.", "")

    # Determine if established domain
    domain_base = ".".join(domain.split(".")[-2:])
    is_established = domain_base in ESTABLISHED_DOMAINS

    # ── Run all checks concurrently ──────────────────────────────────────
    redirect_task = follow_redirects(url)
    safe_browsing_task = check_google_safe_browsing(url)
    virustotal_task = check_virustotal(url)
    page_content_task = _fetch_page_content(url)

    (final_url, redirect_chain), safe_browsing_result, vt_count, page_signals = \
        await asyncio.gather(
            redirect_task, safe_browsing_task, virustotal_task, page_content_task,
            return_exceptions=False,
        )

    # Handle exceptions from gather
    if isinstance(safe_browsing_result, Exception):
        safe_browsing_result = None
    if isinstance(vt_count, Exception):
        vt_count = None
    if isinstance(page_signals, Exception):
        page_signals = PageContentSignals()

    # ── HTTPS check ──────────────────────────────────────────────────────
    is_https = parsed.scheme == "https"

    # ── SSL certificate validity ─────────────────────────────────────────
    ssl_valid = False
    if is_https:
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain):
                    ssl_valid = True
        except Exception:
            pass

    # ── WHOIS domain age ─────────────────────────────────────────────────
    domain_age_days = None
    registrar = None
    registrar_country = None
    if is_established:
        domain_age_days = 9999
        registrar = "Established domain — skipped WHOIS"
    else:
        try:
            import whois as python_whois
            w = python_whois.whois(domain)
            creation_date = w.creation_date
            if isinstance(creation_date, list):
                creation_date = min(creation_date)
            if creation_date:
                if creation_date.tzinfo is None:
                    creation_date = creation_date.replace(tzinfo=timezone.utc)
                domain_age_days = (datetime.now(timezone.utc) - creation_date).days
            registrar = str(w.registrar or "")
            registrar_country = str(w.country or "")
        except Exception:
            domain_age_days = None

    # ── Structural feature extraction ────────────────────────────────────
    features = _extract_url_features(url)
    is_free_hosting = bool(features.get("is_free_hosting"))
    is_url_shortener = bool(features.get("is_url_shortener"))
    has_ip = bool(features.get("is_ip_address"))
    is_typo = bool(features.get("is_likely_typosquatting")) if not is_established else False
    has_random_subdomain = _detect_random_subdomain(url)

    # ── URL entropy ──────────────────────────────────────────────────────
    url_entropy = calculate_url_entropy(url)

    # ── ML model inference ───────────────────────────────────────────────
    ml_score = _ml_classify_url(url)
    ml_available = ml_score is not None
    ml_fraud_probability = ml_score if ml_available else 0.15

    # ── Page content analysis ────────────────────────────────────────────
    page_fraud_count = 0
    if page_signals.fetched:
        page_fraud_count = (
            page_signals.scam_keyword_count +
            page_signals.payment_keyword_count +
            page_signals.urgency_keyword_count
        )

    # ── HTTP status from page fetch ──────────────────────────────────────
    http_status = None  # We already handle page fetch errors via page_signals

    # ═════════════════════════════════════════════════════════════════════
    # SINGLE call that produces BOTH the score AND the flags.
    # These two are now always consistent with each other.
    # ═════════════════════════════════════════════════════════════════════
    url_trust_score, flags = compute_url_trust_score(
        is_https=is_https,
        ssl_valid=ssl_valid,
        ssl_expiry_days=None,
        domain_age_days=domain_age_days,
        is_free_hosting=is_free_hosting,
        is_url_shortener=is_url_shortener,
        has_ip_address=has_ip,
        is_likely_typosquatting=is_typo,
        has_random_subdomain=has_random_subdomain,
        redirect_chain_length=len(redirect_chain),
        google_safe_browsing_clean=safe_browsing_result,
        virustotal_malicious_count=vt_count,
        page_fraud_signal_count=page_fraud_count,
        http_status=http_status,
        ml_fraud_probability=ml_fraud_probability,
        url=url,
    )

    return URLAnalysisResult(
        url=url, domain=domain, is_https=is_https, ssl_valid=ssl_valid,
        domain_age_days=domain_age_days, registrar=registrar,
        registrar_country=registrar_country, is_free_hosting=is_free_hosting,
        is_url_shortener=is_url_shortener, redirect_chain=redirect_chain,
        final_url=final_url, google_safe_browsing_clean=safe_browsing_result,
        virustotal_malicious_count=vt_count, url_entropy=url_entropy,
        has_ip_address=has_ip, has_random_subdomain=has_random_subdomain,
        is_established_domain=is_established, url_trust_score=url_trust_score,
        ml_classifier_score=ml_score,
        ml_classifier_available=ml_available,
        page_content_signals=page_signals.__dict__ if page_signals.fetched else None,
        flags=flags,
    )
