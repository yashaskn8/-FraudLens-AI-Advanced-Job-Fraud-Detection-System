"""
backend/services/job_relevance_detector.py

The Job Relevance Gate — runs before every analysis pipeline.
Determines whether a submitted URL or description is actually a job posting.

Returns a JobRelevanceResult with:
  is_job_content: bool
  confidence: float (0.0 to 1.0)
  detected_type: str (job_board | employer_career | job_description | not_job | unknown)
  rejection_reason: str | None
  suggestions: list[str]
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse
import httpx
import tldextract
from bs4 import BeautifulSoup

from backend.security.ssrf_guard import get_with_validated_redirects

log = logging.getLogger("trusthire.relevance")


@dataclass
class JobRelevanceResult:
    is_job_content: bool
    confidence: float
    detected_type: str
    rejection_reason: Optional[str]
    detected_entity: Optional[str]   # e.g. "Google Gemini AI assistant page"
    suggestions: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Known domain classifications
# ─────────────────────────────────────────────────────────────────────────────

# Domains that are definitively job boards — any URL on these is job-relevant
JOB_BOARD_DOMAINS = frozenset([
    "naukri.com", "linkedin.com", "indeed.com", "glassdoor.com",
    "internshala.com", "shine.com", "monster.com", "timesjobs.com",
    "wellfound.com", "angel.co", "instahyre.com", "hirist.com",
    "iimjobs.com", "foundit.in", "apna.co",
    "jobs.lever.co", "greenhouse.io", "workday.com", "workable.com",
    "icims.com", "smartrecruiters.com", "recruitcrm.io",
    "ziprecruiter.com", "careerbuilder.com", "dice.com",
    "remoteok.com", "weworkremotely.com", "freshteam.com",
    "cutshort.io", "hirect.in",
])

# Path prefixes on these domains that indicate a job listing page
JOB_BOARD_JOB_PATHS = {
    "linkedin.com": ["/jobs/view/", "/jobs/collections/"],
    "indeed.com": ["/viewjob", "/jobs/"],
    "glassdoor.com": ["/job-listing/", "/jobs/"],
    "naukri.com": ["/job-listings-", "/jobdetail/"],
    "internshala.com": ["/internship/detail/", "/jobs/detail/"],
}

# Subdomains that indicate a company career portal
CAREER_SUBDOMAINS = frozenset([
    "careers", "jobs", "hiring", "work", "talent",
    "recruit", "hr", "apply", "join", "opportunities",
])

# Known non-job domains with human-readable descriptions
NON_JOB_DOMAINS = {
    # AI / Tech products
    "gemini.google.com":   "Google Gemini AI assistant",
    "chat.openai.com":     "ChatGPT AI chatbot",
    "claude.ai":           "Anthropic Claude AI assistant",
    "copilot.microsoft.com": "Microsoft Copilot AI",
    "bard.google.com":     "Google Bard AI",
    "perplexity.ai":       "Perplexity AI search",
    # Search engines
    "bing.com":            "Microsoft Bing Search",
    "duckduckgo.com":      "DuckDuckGo Search",
    "yahoo.com":           "Yahoo",
    "baidu.com":           "Baidu Search",
    # Social media
    "facebook.com":        "Facebook social network",
    "instagram.com":       "Instagram",
    "twitter.com":         "Twitter/X social network",
    "x.com":               "Twitter/X social network",
    "tiktok.com":          "TikTok",
    "snapchat.com":        "Snapchat",
    "pinterest.com":       "Pinterest",
    "reddit.com":          "Reddit",
    "quora.com":           "Quora Q&A platform",
    # Video
    "youtube.com":         "YouTube video platform",
    "youtu.be":            "YouTube video",
    "netflix.com":         "Netflix streaming",
    "hotstar.com":         "Disney+ Hotstar streaming",
    "primevideo.com":      "Amazon Prime Video",
    "twitch.tv":           "Twitch live streaming",
    # E-commerce
    "amazon.com":          "Amazon shopping",
    "amazon.in":           "Amazon India shopping",
    "flipkart.com":        "Flipkart shopping",
    "myntra.com":          "Myntra fashion",
    "meesho.com":          "Meesho shopping",
    "ebay.com":            "eBay marketplace",
    "etsy.com":            "Etsy marketplace",
    # News
    "ndtv.com":            "NDTV news",
    "timesofindia.com":    "Times of India news",
    "hindustantimes.com":  "Hindustan Times news",
    "thehindu.com":        "The Hindu newspaper",
    "bbc.com":             "BBC news",
    "cnn.com":             "CNN news",
    "reuters.com":         "Reuters news agency",
    "techcrunch.com":      "TechCrunch tech news",
    "medium.com":          "Medium blogging platform",
    # Government / Finance
    "wikipedia.org":       "Wikipedia encyclopedia",
    "wikimedia.org":       "Wikimedia foundation",
    "gov.in":              "Indian government portal",
    "nic.in":              "National Informatics Centre",
    "nseindia.com":        "NSE India stock exchange",
    "bseindia.com":        "BSE India stock exchange",
    "rbi.org.in":          "Reserve Bank of India",
    # Banking
    "sbi.co.in":           "State Bank of India",
    "hdfcbank.com":        "HDFC Bank",
    "icicibank.com":       "ICICI Bank",
    "axisbank.com":        "Axis Bank",
    # Maps / Navigation
    "maps.google.com":     "Google Maps",
    "maps.apple.com":      "Apple Maps",
    # Developer tools
    "github.com":          "GitHub code repository",
    "gitlab.com":          "GitLab code repository",
    "stackoverflow.com":   "Stack Overflow developer Q&A",
    "npmjs.com":           "npm package registry",
    "pypi.org":            "Python package index",
    "docs.python.org":     "Python documentation",
}

# URL path keywords that strongly indicate a job posting
JOB_PATH_SIGNALS = frozenset([
    "job", "jobs", "career", "careers", "vacancy", "vacancies",
    "hiring", "hire", "apply", "application", "opening", "openings",
    "position", "role", "opportunity", "opportunities", "recruit",
    "recruitment", "internship", "placement", "joining",
    "job-detail", "job-listing", "job-description", "jobdetail",
])

# Text patterns in page content that strongly indicate a job posting
JOB_CONTENT_PATTERNS = [
    r"(?:job|role)\s+(?:title|description|summary)",
    r"(?:key\s+)?responsibilities",
    r"(?:minimum\s+)?(?:qualifications?|requirements?|experience\s+required)",
    r"(?:annual\s+)?ctc|salary\s+(?:range|package)|lpa|per\s+annum",
    r"apply\s+(?:now|here|online|through)",
    r"(?:years?\s+of\s+)?experience\s+(?:required|preferred|in)",
    r"(?:must\s+have|good\s+to\s+have|nice\s+to\s+have)",
    r"(?:full[\s-]time|part[\s-]time|contract|permanent|temporary)\s+(?:position|role|job)",
    r"equal\s+opportunity\s+employer",
    r"about\s+the\s+(?:role|position|company|team)",
    r"we\s+(?:are\s+)?(?:looking\s+for|hiring|seeking)",
    r"join\s+(?:our\s+)?team",
    r"(?:notice\s+period|immediate\s+joiner)",
]

# Text patterns that strongly indicate NOT a job posting
NON_JOB_CONTENT_PATTERNS = [
    r"(?:chat|talk|ask)\s+(?:with|to)\s+(?:ai|gemini|claude|gpt|bard|copilot)",
    r"(?:search|browse|shop|buy|cart|checkout|order)",
    r"(?:watch|stream|play|download)\s+(?:video|movie|show|episode)",
    r"(?:log\s*in|sign\s*up)\s+to\s+(?:your\s+)?account",
    r"breaking\s+news|latest\s+news|headlines",
    r"(?:stock|share)\s+(?:price|market|exchange)",
    r"weather\s+(?:forecast|today|tomorrow)",
    r"(?:recipe|ingredient|cook|bake)",
]


async def detect_job_relevance(
    url: Optional[str] = None,
    description: Optional[str] = None,
) -> JobRelevanceResult:
    """
    Main entry point for the Job Relevance Gate.
    At least one of url or description must be provided.
    Returns immediately with a clear rejection if content is not job-related.
    """
    if not url and not description:
        return JobRelevanceResult(
            is_job_content=False, confidence=0.99,
            detected_type="no_input",
            rejection_reason="No URL or job description was provided.",
            detected_entity=None,
            suggestions=[
                "Paste the URL of the job posting from Naukri, LinkedIn, or the company website.",
                "Or paste the full job description text into the Description field.",
            ]
        )

    # Run URL check first if URL is provided
    if url:
        url_result = await _check_url_relevance(url)
        if not url_result.is_job_content:
            return url_result
        # If URL is confirmed job-related, return immediately with high confidence
        if url_result.confidence >= 0.85:
            return url_result

    # Run description check if text is provided
    if description:
        desc_result = _check_description_relevance(description)
        if not desc_result.is_job_content:
            return desc_result
        return desc_result

    # Both checks inconclusive — default to allowing analysis with low confidence
    return JobRelevanceResult(
        is_job_content=True, confidence=0.45,
        detected_type="unknown",
        rejection_reason=None,
        detected_entity=None,
        suggestions=["For best results, provide both the job URL and the job description."]
    )


async def _check_url_relevance(url: str) -> JobRelevanceResult:
    """
    Checks a URL for job relevance using three signals:
    1. Domain classification (instant, no network)
    2. Path keyword analysis (instant, no network)
    3. Live page content scan (network call, runs only if 1 and 2 are inconclusive)
    """
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    ext = tldextract.extract(url)
    domain_full = parsed.netloc.lower().replace("www.", "")
    domain_root = f"{ext.domain}.{ext.suffix}".lower()
    subdomain = ext.subdomain.lower()
    path = parsed.path.lower()

    # ── Signal 1: Known non-job domain (with job path exception) ──────────
    path_parts = set(p for p in re.split(r"[/\-_?=&.]", path) if p)
    has_job_path = bool(path_parts & JOB_PATH_SIGNALS)

    for check_domain in [domain_full, domain_root]:
        if check_domain in NON_JOB_DOMAINS:
            # Exception: allow if it's a known job path on this domain
            if has_job_path:
                log.info(f"Allowing non-job domain '{check_domain}' due to job path signals")
                continue
            
            entity_name = NON_JOB_DOMAINS[check_domain]
            return JobRelevanceResult(
                is_job_content=False,
                confidence=0.99,
                detected_type="not_job",
                rejection_reason=(
                    f"The URL you submitted points to {entity_name}, "
                    f"which is not a job posting."
                ),
                detected_entity=entity_name,
                suggestions=[
                    "Please submit the URL of an actual job posting, not a product or service page.",
                    "Example: https://careers.infosys.com/jobid/12345",
                    "Example: https://www.naukri.com/job-listings-software-engineer",
                    "You can also paste the job description text directly into the Description tab.",
                ]
            )

    # ── Signal 2: Known job board domain ─────────────────────────────────
    if domain_root in JOB_BOARD_DOMAINS:
        # Extra check: LinkedIn profile vs job listing
        if domain_root == "linkedin.com":
            if "/jobs/" in path or "/job/" in path:
                return JobRelevanceResult(
                    is_job_content=True, confidence=0.98,
                    detected_type="job_board",
                    rejection_reason=None, detected_entity="LinkedIn job listing",
                    suggestions=[]
                )
            elif "/in/" in path or "/company/" in path:
                return JobRelevanceResult(
                    is_job_content=False, confidence=0.95,
                    detected_type="not_job",
                    rejection_reason=(
                        "The URL points to a LinkedIn profile or company page, "
                        "not a specific job listing."
                    ),
                    detected_entity="LinkedIn profile or company page",
                    suggestions=[
                        "Navigate to the specific job posting on LinkedIn and copy that URL.",
                        "LinkedIn job URLs typically contain '/jobs/view/' followed by a job ID.",
                    ]
                )
        return JobRelevanceResult(
            is_job_content=True, confidence=0.97,
            detected_type="job_board",
            rejection_reason=None, detected_entity=f"{domain_root} job board",
            suggestions=[]
        )

    # ── Signal 2b: Career subdomain on employer website ──────────────────
    if subdomain in CAREER_SUBDOMAINS:
        return JobRelevanceResult(
            is_job_content=True, confidence=0.92,
            detected_type="employer_career",
            rejection_reason=None,
            detected_entity=f"{subdomain}.{domain_root} employer career portal",
            suggestions=[]
        )

    # ── Signal 2c: Job-related path keywords ─────────────────────────────
    path_parts = set(re.split(r"[/\-_?=&]", path))
    path_matches = path_parts & JOB_PATH_SIGNALS
    if path_matches:
        return JobRelevanceResult(
            is_job_content=True, confidence=0.80,
            detected_type="employer_career",
            rejection_reason=None, detected_entity=f"{domain_root}",
            suggestions=[]
        )

    # ── Signal 3: Live page content scan ─────────────────────────────────
    # Only runs when domain and path analysis are inconclusive
    log.info(f"Relevance gate: inconclusive for {domain_root}, fetching page content...")
    title, body_text, status = await _fetch_page_sample(url)

    if status and status >= 400:
        return JobRelevanceResult(
            is_job_content=False, confidence=0.80,
            detected_type="not_job",
            rejection_reason=f"The URL returned an error (HTTP {status}) and could not be accessed.",
            detected_entity=None,
            suggestions=[
                "Check that the URL is correct and the page is publicly accessible.",
                "Some job portals require login — paste the job description text instead.",
            ]
        )

    if not body_text:
        # Cannot fetch content — allow analysis to proceed but with low confidence
        return JobRelevanceResult(
            is_job_content=True, confidence=0.40,
            detected_type="unknown",
            rejection_reason=None, detected_entity=None,
            suggestions=["Could not verify page content. Analysis will proceed with reduced confidence."]
        )

    combined_text = f"{title or ''} {body_text}".lower()

    # Check for non-job content patterns first (stronger signal)
    for pattern in NON_JOB_CONTENT_PATTERNS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return JobRelevanceResult(
                is_job_content=False, confidence=0.88,
                detected_type="not_job",
                rejection_reason=(
                    f"The page at this URL does not appear to be a job posting. "
                    f"The page title is: \"{title or 'unknown'}\"."
                ),
                detected_entity=title,
                suggestions=[
                    "Please submit the URL of the actual job posting, not a homepage or product page.",
                    "You can also paste the job description text into the Description field.",
                ]
            )

    # Check for positive job content signals
    job_matches = sum(
        1 for pattern in JOB_CONTENT_PATTERNS
        if re.search(pattern, combined_text, re.IGNORECASE)
    )

    if job_matches >= 3:
        return JobRelevanceResult(
            is_job_content=True, confidence=0.85,
            detected_type="employer_career",
            rejection_reason=None, detected_entity=title,
            suggestions=[]
        )
    elif job_matches >= 1:
        return JobRelevanceResult(
            is_job_content=True, confidence=0.62,
            detected_type="employer_career",
            rejection_reason=None, detected_entity=title,
            suggestions=["Limited job content detected. For best results, also paste the job description text."]
        )
    else:
        return JobRelevanceResult(
            is_job_content=False, confidence=0.75,
            detected_type="not_job",
            rejection_reason=(
                f"The page at this URL does not appear to contain a job posting. "
                f"Page title: \"{title or 'unknown'}\". "
                "No employment-related content was detected."
            ),
            detected_entity=title,
            suggestions=[
                "Submit the direct URL of a job listing, not a company homepage.",
                "Alternatively, paste the full job description text into the Description field.",
            ]
        )


def _check_description_relevance(description: str) -> JobRelevanceResult:
    """
    Checks whether description text is actually a job posting.
    Rejects product descriptions, news articles, and general web content.
    """
    if len(description.strip()) < 30:
        return JobRelevanceResult(
            is_job_content=False, confidence=0.90,
            detected_type="not_job",
            rejection_reason="The provided text is too short to be a job description.",
            detected_entity=None,
            suggestions=[
                "Paste the complete job description including responsibilities, requirements, and benefits.",
                "A minimum of 50 words is needed for accurate analysis.",
            ]
        )

    text_lower = description.lower()

    # Check for non-job content
    for pattern in NON_JOB_CONTENT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return JobRelevanceResult(
                is_job_content=False, confidence=0.85,
                detected_type="not_job",
                rejection_reason="The text does not appear to be a job description.",
                detected_entity=None,
                suggestions=["Please paste the full text of a job posting, not a product description or article."]
            )

    # Count positive job signals
    job_matches = sum(
        1 for pattern in JOB_CONTENT_PATTERNS
        if re.search(pattern, text_lower, re.IGNORECASE)
    )

    if job_matches >= 2:
        return JobRelevanceResult(
            is_job_content=True, confidence=0.88,
            detected_type="job_description",
            rejection_reason=None, detected_entity=None, suggestions=[]
        )

    # Marginal — allow with warning
    return JobRelevanceResult(
        is_job_content=True, confidence=0.52,
        detected_type="job_description",
        rejection_reason=None, detected_entity=None,
        suggestions=["Limited job-related content detected. Ensure you have pasted the complete job description."]
    )


async def _fetch_page_sample(url: str):
    """
    Fetches a page and returns (title, first_2000_chars_of_body_text, status_code).
    Uses a 6-second timeout and strips all HTML tags.
    """
    try:
        async with httpx.AsyncClient(
            timeout=6.0, follow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 (compatible; TrustHire/1.0 +https://trusthire.app)"}
        ) as client:
            response, _ = await get_with_validated_redirects(client, url)
            soup = BeautifulSoup(response.text, "html.parser")
            title = soup.title.string.strip() if soup.title and soup.title.string else ""
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            body = " ".join(soup.get_text(separator=" ").split())[:2000]
            return title, body, response.status_code
    except Exception as e:
        log.debug(f"Page fetch failed for relevance check: {e}")
        return None, None, None
