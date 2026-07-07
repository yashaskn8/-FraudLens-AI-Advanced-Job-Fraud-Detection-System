"""
backend/services/company_verifier.py

Global company verification service with verified domain fast-pass
and impersonation detection.

Key principle: brand name presence in a domain is NOT a positive signal —
it is a RED FLAG unless the domain is the brand's registered domain.
"""

import re
import logging
import os
from pydantic import BaseModel
from typing import Optional, List
import tldextract
from backend.config import settings

logger = logging.getLogger(__name__)


# ── Verified global employer whitelist ────────────────────────────────────────
# EXACT root domain match only. "google.com" passes. "google-career-verification.org" does NOT.
VERIFIED_DOMAINS = frozenset([
    # India — major IT and consulting
    "infosys.com", "wipro.com", "tcs.com", "hcltech.com", "techm.com",
    "cognizant.com", "capgemini.com", "mphasis.com", "hexaware.com",
    "persistent.com", "ltimindtree.com", "mindtree.com",
    # Global consulting and technology
    "accenture.com", "ibm.com", "oracle.com", "sap.com", "siemens.com",
    "deloitte.com", "kpmg.com", "pwc.com", "ey.com", "mckinsey.com",
    "bcg.com", "bain.com",
    # Global tech
    "google.com", "microsoft.com", "amazon.com", "apple.com", "meta.com",
    "netflix.com", "adobe.com", "salesforce.com", "workday.com",
    "servicenow.com", "snowflake.com", "atlassian.com", "twilio.com",
    "stripe.com", "shopify.com",
    # UK companies
    "bbc.co.uk", "hsbc.com", "lloyds.com", "barclays.com", "bp.com",
    "unilever.com", "vodafone.com", "bt.com", "rolls-royce.com",
    # Australia
    "commbank.com.au", "westpac.com.au", "anz.com.au",
    "woolworths.com.au", "telstra.com.au", "nab.com.au",
    # Canada
    "rbc.com", "td.com", "scotiabank.com", "bmo.com",
    # Germany
    "bmw.com", "volkswagen.com", "bosch.com", "allianz.com",
    "mercedes-benz.com", "basf.com", "bayer.com",
    # Singapore/SEA
    "dbs.com", "grab.com", "sea.com", "singtel.com", "ocbc.com",
    # UAE/Gulf
    "emirates.com", "etisalat.ae", "adnoc.ae",
    # India startups (publicly verifiable)
    "flipkart.com", "paytm.com", "swiggy.in", "zomato.com",
    "razorpay.com", "freshworks.com", "zoho.com", "byju.com",
    "unacademy.com", "ola.com", "phonepe.com",
    # Job boards
    "naukri.com", "linkedin.com", "indeed.com", "glassdoor.com",
    "reed.co.uk", "totaljobs.com", "seek.com.au", "monster.com",
    "internshala.com", "shine.com", "timesjobs.com", "wellfound.com",
    "angel.co", "instahyre.com", "foundit.in",
    # ATS platforms
    "lever.co", "greenhouse.io", "icims.com",
    "smartrecruiters.com", "workable.com",
    # Additional well-known job/ATS
    "amazon.jobs", "aboutamazon.com", "ibegin.tcs.com",
])

# Career-related subdomains that indicate a legitimate employer portal
CAREER_SUBDOMAINS = frozenset([
    "careers", "jobs", "hiring", "talent",
    "apply", "work", "join", "recruit",
])

# ── Brand impersonation detection data ────────────────────────────────────────

# Known brand tokens — scammers embed these in fraud domains
BRAND_TOKENS = frozenset([
    # India IT
    "infosys", "wipro", "tcs", "hcl", "techm", "cognizant",
    "capgemini", "mphasis", "hexaware", "persistent",
    # Global tech
    "google", "microsoft", "amazon", "apple", "meta", "facebook",
    "netflix", "adobe", "salesforce", "oracle", "ibm", "sap",
    "uber", "airbnb", "stripe", "shopify", "atlassian",
    # Consulting
    "accenture", "deloitte", "kpmg", "mckinsey", "pwc", "ey",
    # UK companies
    "bbc", "hsbc", "lloyds", "barclays", "vodafone",
    # Australia
    "commbank", "westpac", "telstra", "woolworths",
    # Gulf
    "emirates", "etisalat",
    # Singapore/SEA
    "grab", "dbs", "singtel",
    # Indian startups
    "flipkart", "paytm", "swiggy", "zomato", "razorpay",
    "freshworks", "zoho", "byju", "phonepe", "ola",
    # Job boards
    "naukri", "linkedin", "indeed", "glassdoor", "monster",
    "internshala", "shine", "wellfound",
])

# Keywords that combined with a brand token indicate impersonation
JOB_IMPERSONATION_WORDS = frozenset([
    "job", "jobs", "career", "careers", "hiring", "hire",
    "vacancy", "vacancies", "apply", "application", "recruit",
    "recruitment", "opening", "openings", "opportunity",
])

# High-risk action words — critical fraud signals when combined with a brand
HIGH_RISK_ACTION_WORDS = frozenset([
    "verification", "verify", "validate", "validation", "confirm",
    "confirmation", "activation", "activate", "register", "registration",
    "fee", "payment", "pay", "deposit", "charge", "official", "portal",
    "login", "signin", "secure", "security", "account", "update",
    "upgrade", "process", "processing",
])

# Known legitimate brand domains — the ONLY domains where these brands are real
BRAND_LEGITIMATE_DOMAINS = {
    "google": ["google.com", "google.co.in", "google.co.uk", "google.com.au",
               "google.ca", "google.de", "google.fr", "google.es",
               "google.com.br", "google.co.jp", "google.sg"],
    "microsoft": ["microsoft.com", "linkedin.com"],
    "amazon": ["amazon.com", "amazon.in", "amazon.co.uk", "amazon.com.au",
               "amazon.jobs", "aboutamazon.com"],
    "apple": ["apple.com"],
    "meta": ["meta.com", "facebook.com"],
    "facebook": ["facebook.com", "meta.com"],
    "infosys": ["infosys.com"],
    "wipro": ["wipro.com"],
    "tcs": ["tcs.com", "ibegin.tcs.com"],
    "accenture": ["accenture.com"],
    "cognizant": ["cognizant.com"],
    "capgemini": ["capgemini.com"],
    "ibm": ["ibm.com"],
    "oracle": ["oracle.com"],
    "sap": ["sap.com"],
    "deloitte": ["deloitte.com"],
    "kpmg": ["kpmg.com"],
    "pwc": ["pwc.com"],
    "ey": ["ey.com"],
    "mckinsey": ["mckinsey.com"],
    "netflix": ["netflix.com"],
    "adobe": ["adobe.com"],
    "salesforce": ["salesforce.com"],
    "shopify": ["shopify.com"],
    "linkedin": ["linkedin.com"],
    "naukri": ["naukri.com"],
    "indeed": ["indeed.com"],
    "glassdoor": ["glassdoor.com"],
    "flipkart": ["flipkart.com"],
    "paytm": ["paytm.com"],
    "swiggy": ["swiggy.in"],
    "zomato": ["zomato.com"],
    "hsbc": ["hsbc.com"],
    "barclays": ["barclays.com"],
    "bbc": ["bbc.co.uk", "bbc.com"],
    "vodafone": ["vodafone.com"],
    "commbank": ["commbank.com.au"],
    "westpac": ["westpac.com.au"],
    "telstra": ["telstra.com.au"],
    "grab": ["grab.com"],
    "dbs": ["dbs.com"],
    "emirates": ["emirates.com"],
    "uber": ["uber.com"],
    "airbnb": ["airbnb.com"],
    "stripe": ["stripe.com"],
    "atlassian": ["atlassian.com"],
    "razorpay": ["razorpay.com"],
    "freshworks": ["freshworks.com"],
    "zoho": ["zoho.com"],
    "phonepe": ["phonepe.com"],
}


# ── Impersonation detection functions ─────────────────────────────────────────

def _tokenise_domain(domain: str) -> list:
    """
    Split a domain name into its constituent tokens.
    "google-career-verification.org" → ["google", "career", "verification"]
    "infosys-hiring.wixsite.com"     → ["infosys", "hiring", "wixsite"]
    "tcs-official-jobs.xyz"          → ["tcs", "official", "jobs"]
    """
    domain = domain.replace("www.", "")
    parts = domain.split(".")
    known_tld_parts = {"com", "org", "net", "in", "io", "co",
                       "gov", "edu", "uk", "au", "ca", "de", "fr",
                       "es", "it", "sg", "ae", "jp", "br", "ph",
                       "xyz", "site", "online", "work", "top",
                       "click", "tech", "me", "info", "biz"}
    domain_name_parts = []
    for part in parts:
        if part.lower() not in known_tld_parts:
            domain_name_parts.append(part)

    domain_name = "-".join(domain_name_parts)
    tokens = re.split(r"[-_]", domain_name.lower())
    return [t for t in tokens if len(t) >= 2]


def _check_impersonation(domain: str, url: str = "") -> dict:
    """
    Checks whether a domain is impersonating a known brand.

    Returns:
      is_impersonation: bool
      flag: str (human-readable explanation)
      severity: "critical" | "high" | "medium" | "none"
      impersonated_brand: str

    Logic:
      1. Tokenise the domain by hyphens and dots.
      2. Check if any token exactly matches a known brand.
      3. If a brand token is found, verify the full domain against
         the brand's list of legitimate domains.
      4. If the domain is NOT a legitimate brand domain but CONTAINS
         a brand token, it is impersonation.
      5. Apply severity based on co-occurring risk/job words.
    """
    if not domain:
        return {"is_impersonation": False, "flag": "", "severity": "none",
                "impersonated_brand": ""}

    # Get full root domain for legitimate domain comparison
    try:
        ext = tldextract.extract(url or domain)
        root_domain = f"{ext.domain}.{ext.suffix}".lower()
        subdomain = ext.subdomain.lower()
        full_domain_with_sub = (
            f"{subdomain}.{root_domain}" if subdomain and subdomain != "www"
            else root_domain
        )
    except Exception:
        root_domain = domain
        full_domain_with_sub = domain

    tokens = _tokenise_domain(domain)

    for token in tokens:
        if token in BRAND_TOKENS:
            brand = token

            # Check if this is a legitimate brand domain
            legitimate_domains = BRAND_LEGITIMATE_DOMAINS.get(brand, [])
            if any(root_domain == legit or full_domain_with_sub == legit
                   for legit in legitimate_domains):
                # This IS a legitimate brand domain — no impersonation
                return {"is_impersonation": False, "flag": "",
                        "severity": "none", "impersonated_brand": ""}

            # Brand token found in a non-legitimate domain — this IS impersonation
            remaining_tokens = [t for t in tokens if t != brand]

            has_job_word = any(t in JOB_IMPERSONATION_WORDS
                              for t in remaining_tokens)
            has_high_risk = any(t in HIGH_RISK_ACTION_WORDS
                                for t in remaining_tokens)

            if has_high_risk:
                risk_word = next(t for t in remaining_tokens
                                if t in HIGH_RISK_ACTION_WORDS)
                severity = "critical"
                legit_domain = BRAND_LEGITIMATE_DOMAINS.get(
                    brand, [brand + ".com"])[0]
                flag = (
                    f"Domain impersonates {brand.capitalize()} and contains "
                    f"a high-risk keyword ('{risk_word}') — a classic "
                    f"credential-harvesting or advance-fee fraud pattern. "
                    f"{brand.capitalize()}'s legitimate domain is {legit_domain}."
                )
            elif has_job_word:
                severity = "high"
                legit_domain = BRAND_LEGITIMATE_DOMAINS.get(
                    brand, [brand + ".com"])[0]
                flag = (
                    f"Domain impersonates {brand.capitalize()} with a "
                    f"job-related keyword — likely a fake recruitment site. "
                    f"{brand.capitalize()}'s legitimate careers page is at "
                    f"{legit_domain}."
                )
            else:
                severity = "high"
                legit_domain = BRAND_LEGITIMATE_DOMAINS.get(
                    brand, [brand + ".com"])[0]
                flag = (
                    f"Domain contains the brand name '{brand.capitalize()}' "
                    f"but is not {brand.capitalize()}'s legitimate domain "
                    f"({legit_domain}). "
                    f"This domain may be impersonating {brand.capitalize()}."
                )

            return {
                "is_impersonation": True,
                "flag": flag,
                "severity": severity,
                "impersonated_brand": brand,
            }

    return {"is_impersonation": False, "flag": "", "severity": "none",
            "impersonated_brand": ""}


# ── Result model ──────────────────────────────────────────────────────────────

class CompanyVerificationResult(BaseModel):
    company_name: str
    country_detected: str
    registry_used: str
    is_registered: bool
    registration_number: Optional[str] = None
    company_status: Optional[str] = None
    company_trust_score: float  # 0.0 to 1.0
    flags: List[str]
    signals_checked: int
    has_active_fraud_evidence: bool = False


def _detect_country(job_url: str, job_description: str) -> str:
    """
    Detects the likely country of the job posting.
    Returns ISO 3166-1 alpha-2 country code or 'GLOBAL'.
    """
    desc_lower = job_description.lower()
    url_lower = job_url.lower()

    if "united states" in desc_lower or "/us-en/" in url_lower:
        return "US"
    if "united kingdom" in desc_lower or "/uk-en/" in url_lower:
        return "GB"
    if "australia" in desc_lower:
        return "AU"
    if "india" in desc_lower or "/in-en/" in url_lower:
        return "IN"

    if job_url:
        ext = tldextract.extract(job_url)
        if ext.suffix:
            tld_map = {
                "in": "IN", "co.in": "IN",
                "uk": "GB", "co.uk": "GB",
                "au": "AU", "com.au": "AU",
                "ca": "CA", "de": "DE",
                "fr": "FR", "sg": "SG", "ae": "AE",
            }
            if ext.suffix in tld_map:
                return tld_map[ext.suffix]

    return "GLOBAL"


async def verify_company_global(
    company_name: str = "",
    company_domain: str = "",
    url: str = "",
    description: str = "",
) -> CompanyVerificationResult:
    """
    Global company verification with:
      1. Exact-match verified domain fast-pass
      2. Impersonation detection (runs BEFORE any positive scoring)
      3. Career subdomain detection
      4. National registry fallback
    """
    flags = []
    signals_checked = 0
    trust_score = 0.5
    is_registered = False
    has_fraud_evidence = False
    status = None

    cc = _detect_country(url, description)

    # ── Extract root domain for all checks ────────────────────────────────
    if url:
        try:
            url_ext = tldextract.extract(url)
            url_root_domain = (
                f"{url_ext.domain}.{url_ext.suffix}".lower()
                if url_ext.domain and url_ext.suffix else ""
            )
        except Exception:
            url_root_domain = ""
    else:
        url_root_domain = ""

    clean_domain = (
        company_domain.replace("www.", "").lower().strip()
        if company_domain else ""
    )

    # ── Fast-pass: EXACT full root domain match only ──────────────────────
    # "google.com" is in the whitelist. "google-career-verification.org" is NOT.
    for domain_to_check in [clean_domain, url_root_domain]:
        if domain_to_check and domain_to_check in VERIFIED_DOMAINS:
            logger.info(f"Verified domain fast-pass: {domain_to_check}")
            return CompanyVerificationResult(
                company_name=company_name or domain_to_check.split(".")[0].capitalize(),
                country_detected=cc,
                registry_used="Verified global employer whitelist",
                is_registered=True,
                company_trust_score=0.94,
                flags=[
                    f"Domain {domain_to_check} is a verified legitimate "
                    f"employer — high baseline trust applied"
                ],
                signals_checked=1,
                has_active_fraud_evidence=False,
            )

    # ── CRITICAL: Impersonation check BEFORE any positive scoring ─────────
    impersonation_result = _check_impersonation(
        url_root_domain or clean_domain, url or ""
    )
    if impersonation_result["is_impersonation"]:
        logger.warning(
            f"Impersonation detected: {url_root_domain or clean_domain} "
            f"impersonates {impersonation_result['impersonated_brand']}"
        )
        return CompanyVerificationResult(
            company_name=company_name or "Unknown",
            country_detected=cc,
            registry_used="Impersonation detection",
            is_registered=False,
            company_trust_score=0.06,
            flags=[impersonation_result["flag"]],
            signals_checked=1,
            has_active_fraud_evidence=True,
        )

    # ── No company name — can't proceed to registry ──────────────────────
    if not company_name or len(company_name) < 2:
        return CompanyVerificationResult(
            company_name=company_name or "Unknown",
            country_detected=cc,
            registry_used="None",
            is_registered=False,
            company_trust_score=0.5,
            flags=["No company name provided — paste the description for "
                   "improved company verification"],
            signals_checked=0,
            has_active_fraud_evidence=False,
        )

    # ── Career subdomain detection ────────────────────────────────────────
    if url:
        try:
            url_ext = tldextract.extract(url)
            subdomain = url_ext.subdomain.lower()
            root = f"{url_ext.domain}.{url_ext.suffix}".lower()
            if subdomain in CAREER_SUBDOMAINS and len(root) > 4:
                flags.append(
                    f"URL uses a structured career subdomain ({subdomain}.{root}) — "
                    f"consistent with a legitimate employer career portal"
                )
                trust_score = 0.78
                is_registered = True
                signals_checked = 1
        except Exception:
            pass

    # ── Registry verification (only if fast-pass didn't fire) ─────────────
    if signals_checked == 0:
        if cc == "GB" and not os.getenv("COMPANIES_HOUSE_API_KEY"):
            cc = "GLOBAL"
        if cc == "AU" and not os.getenv("ABN_LOOKUP_GUID"):
            cc = "GLOBAL"

        registry_name = "OpenCorporates Global Registry"

        try:
            if cc == "GB":
                registry_name = "Companies House (UK)"
                signals_checked += 1
                is_registered, status = _verify_uk_companies_house(company_name)
            elif cc == "AU":
                registry_name = "ABN Lookup (Australia)"
                signals_checked += 1
                is_registered, status = _verify_au_abn_lookup(company_name)
            elif cc == "US":
                registry_name = "SEC EDGAR (US) / State Registries"
                signals_checked += 1
                is_registered, status = _verify_us_edgar(company_name)
            elif cc == "IN":
                registry_name = "Ministry of Corporate Affairs (India)"
                signals_checked += 1
                is_registered, status = _verify_india_mca(company_name)
            else:
                registry_name = "OpenCorporates Global Database"
                signals_checked += 1
                is_registered, status = _verify_opencorporates(company_name, cc)

            if is_registered:
                if status and status.lower() not in ["active", "registered", "incorporated"]:
                    trust_score = 0.4
                    flags.append(f"Company is registered but status is '{status}'")
                    has_fraud_evidence = True
                else:
                    trust_score = 0.95
            else:
                trust_score = 0.3
                flags.append(f"Company '{company_name}' could not be found in {registry_name}")
                has_fraud_evidence = True

        except Exception as e:
            logger.error(f"Registry verification failed: {e}")
            flags.append("Company verification service temporarily unavailable")
            trust_score = 0.5
            has_fraud_evidence = False

        return CompanyVerificationResult(
            company_name=company_name,
            country_detected=cc,
            registry_used=registry_name,
            is_registered=is_registered,
            company_status=status,
            company_trust_score=trust_score,
            flags=flags,
            signals_checked=max(1, signals_checked),
            has_active_fraud_evidence=has_fraud_evidence,
        )

    # ── Return from career subdomain path ─────────────────────────────────
    return CompanyVerificationResult(
        company_name=company_name,
        country_detected=cc,
        registry_used="Career subdomain detection",
        is_registered=is_registered,
        company_trust_score=trust_score,
        flags=flags,
        signals_checked=signals_checked,
        has_active_fraud_evidence=False,
    )


# ── Stubbed API calls for national registries ─────────────────────────────────

def _verify_uk_companies_house(name: str) -> tuple:
    return ("ltd" in name.lower() or "plc" in name.lower() or len(name) > 6), "active"

def _verify_au_abn_lookup(name: str) -> tuple:
    return ("pty" in name.lower() or len(name) > 6), "active"

def _verify_us_edgar(name: str) -> tuple:
    return ("inc" in name.lower() or "llc" in name.lower() or len(name) > 6), "active"

def _verify_india_mca(name: str) -> tuple:
    return ("pvt" in name.lower() or "limited" in name.lower() or len(name) > 6), "active"

def _verify_opencorporates(name: str, jurisdiction: str) -> tuple:
    return len(name) > 7, "active"
