"""
scripts/download_datasets.py

Downloads and verifies every dataset required for TrustHire model training.

Datasets acquired:
  A. EMSCAD          - 17,880 labelled job postings (primary NLP training set)
  B. PhiUSIIL        - 235,795 phishing/legitimate URLs
  C. URLhaus         - Live malicious URL feed from abuse.ch
  D. OpenPhish       - Active phishing URLs (updated every 12 hours)
  E. Majestic Million - Top 1M legitimate domains
  F. ISCX URL 2016   - 35,300 multi-class URLs
  G. Job Scam URLs   - Synthetic job-specific fraud URL patterns
  H. Legitimate Job  - Real job board URL patterns (scraped structure)
  I. Scam Phrases    - Weighted phrase dictionary for NLP scoring
  J. Domain Whitelist - Verified legitimate employer domains
"""

import os, sys, re, json, csv, gzip, zipfile, shutil, time
import subprocess, hashlib, logging
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from tqdm import tqdm
import tldextract

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("download")

BASE  = Path("data")
RAW   = BASE / "raw"
PROC  = BASE / "processed"
CACHE = BASE / "cache"

for d in [RAW, PROC, CACHE, RAW/"jobs", RAW/"urls", RAW/"domains"]:
    d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def fetch(url: str, dest: Path, desc: str = "", timeout: int = 90) -> bool:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                      "Gecko/20100101 Firefox/120.0",
        "Accept": "text/html,application/xhtml+xml,*/*",
    }
    try:
        r = requests.get(url, stream=True, timeout=timeout, headers=headers)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f, tqdm(desc=f"  {desc}", total=total,
                                          unit="B", unit_scale=True, ncols=90) as bar:
            for chunk in r.iter_content(8192):
                f.write(chunk)
                bar.update(len(chunk))
        log.info(f"Downloaded {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        log.warning(f"Download failed [{desc}]: {e}")
        return False


def unzip(src: Path, dest: Path):
    with zipfile.ZipFile(src, "r") as z:
        z.extractall(dest)
    src.unlink()


def ungzip(src: Path) -> Path:
    out = src.with_suffix("")
    with gzip.open(src, "rb") as fi, open(out, "wb") as fo:
        shutil.copyfileobj(fi, fo)
    src.unlink()
    return out


# ---------------------------------------------------------------------------
# A. EMSCAD - Primary Job Fraud Dataset
# ---------------------------------------------------------------------------

def get_emscad() -> Path:
    targets = [
        RAW / "jobs" / "fake_job_postings.csv",
        RAW / "jobs" / "EMSCAD.csv",
    ]
    for t in targets:
        if t.exists() and t.stat().st_size > 200_000:
            log.info(f"EMSCAD found: {t}")
            return t

    log.info("Downloading EMSCAD dataset...")

    # Try Kaggle CLI
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "download",
             "-d", "shivamb/real-or-fake-fake-jobposting-prediction",
             "-p", str(RAW / "jobs"), "--unzip", "--quiet"],
            capture_output=True, text=True, timeout=300
        )
        for t in targets:
            if t.exists():
                log.info(f"EMSCAD via Kaggle: {t}")
                return t
        log.warning(f"Kaggle CLI returned code {result.returncode}: {result.stderr[:200]}")
    except Exception as e:
        log.warning(f"Kaggle CLI unavailable: {e}")

    # Direct mirrors
    for url in [
        "https://zenodo.org/records/5945271/files/EMSCAD.csv",
        "https://github.com/aashari/fake-job-posting/raw/master/data/fake_job_postings.csv",
    ]:
        dest = RAW / "jobs" / "fake_job_postings.csv"
        if fetch(url, dest, "EMSCAD direct"):
            return dest

    # Generate synthetic EMSCAD-equivalent
    log.warning("All EMSCAD sources failed. Generating synthetic training data.")
    return _generate_synthetic_emscad()


def _generate_synthetic_emscad() -> Path:
    """
    Generate a labelled job posting dataset from documented fraud patterns.
    """
    import random
    random.seed(42)

    FAKE = [
        ("Work From Home Data Entry Operator Earn 40000 Monthly",
         "Earn Rs 40,000-80,000 per month working from home. No experience needed. "
         "Simple typing and data entry. Pay Rs 499 registration fee to activate your account. "
         "WhatsApp 9876543210. Limited seats. Apply immediately. No target no pressure.",
         "", "10th pass. Mobile required.", "Weekly payment. Be your own boss.", "", 1, 0, 0),

        ("Urgent Requirement Direct Joining No Interview",
         "No interview required. Direct selection. Salary 35000 fixed. Immediate joining. "
         "Send resume on WhatsApp now. 100 percent job guarantee. Last date today.",
         "Global Recruitment Consultancy", "Any graduate freshers", "PF ESI medical", "35000", 0, 0, 0),

        ("Network Marketing Business Partner Earn Unlimited",
         "Join our growing network. Earn unlimited passive income. Build your downline team. "
         "Investment Rs 2000 to start. Refer and earn commission. Be your own boss. "
         "Multi level marketing opportunity. No boss no target.",
         "MLM Direct Sales", "Anyone 18-60 interested", "Residual income commission", "", 1, 0, 0),

        ("Online Survey Work Earn 1000 Per Day From Home",
         "Fill online surveys and earn Rs 1000-2000 per day. Work from mobile. "
         "Pay Rs 299 activation charge. Daily payout to bank. Unlimited earning potential. "
         "No experience no target. Work 2-3 hours daily from anywhere.",
         "", "Smartphone internet connection", "Daily bank payment", "", 1, 0, 0),

        ("Ad Posting Job Work From Home Earn Daily",
         "Post ads online and earn. Data entry ad posting typing work. "
         "Rs 800-1500 per day guaranteed. Registration fee Rs 199 only. "
         "Send details on WhatsApp. Immediate start today. No experience required.",
         "", "Any device internet", "Immediate payment", "", 1, 0, 0),

        ("Captcha Solving Work Earn 500 Daily No Experience",
         "Solve captchas online and earn Rs 500-800 daily. Work from mobile or computer. "
         "Rs 99 joining fee. Payout weekly. No experience needed. Anyone can do this work. "
         "Limited time offer. Apply today only.",
         "", "Mobile or computer", "Weekly payout", "", 1, 0, 0),

        ("Guaranteed Placement Software Engineer Training Program",
         "100 percent placement guarantee after 3 month training. Pay course fee Rs 15000. "
         "Top MNC companies hiring after training. Get placed in TCS Infosys Wipro. "
         "Limited batch size. Register now. Money back guarantee if not placed.",
         "IT Training and Placement Center", "BE BTech freshers", "Job guarantee", "300000-600000", 0, 0, 0),
    ]

    REAL = [
        ("Senior Software Engineer Backend Systems",
         "We are looking for a Senior Software Engineer to build scalable distributed systems. "
         "You will own key backend services, collaborate with product and design teams, "
         "participate in architecture discussions, and mentor junior engineers. "
         "We follow agile practices with two-week sprints and continuous deployment.",
         "Series B SaaS company, 300 employees, B2B HR automation",
         "5+ years Python or Go. PostgreSQL. AWS or GCP. Distributed systems experience. "
         "Strong communication skills. Computer science degree or equivalent.",
         "CTC 20-28 LPA. ESOP. Health insurance family. 30 days leave. MacBook. "
         "Remote friendly with optional office access.",
         "2000000-2800000", 0, 1, 1),

        ("Product Manager Growth and Acquisition",
         "As PM for Growth, you will own the acquisition funnel from first touch to activation. "
         "You will define the roadmap, run experiments, analyse cohort data, and ship features "
         "with a dedicated engineering and design squad. You will present weekly to the CEO.",
         "Consumer fintech, Series B, Sequoia backed, 400 employees",
         "3-5 years product management. A/B testing expertise. SQL proficiency. "
         "Experience with consumer mobile products. MBA or engineering background preferred.",
         "Competitive CTC with ESOP. Flexible work policy. Annual learning budget Rs 50,000.",
         "2500000-3800000", 0, 1, 1),

        ("Data Analyst Business Intelligence Team",
         "Join our BI team to build dashboards, analyse product metrics, and support "
         "strategic decisions. You will work with large datasets in Snowflake and dbt, "
         "build Tableau dashboards, and present findings to senior leadership weekly.",
         "Public listed e-commerce company, 2000 employees",
         "2+ years data analysis. SQL mandatory. Python preferred. Tableau or Looker. "
         "Degree in statistics, mathematics, or computer science.",
         "Competitive salary. PF. Health insurance. Annual bonus. Hybrid work.",
         "900000-1400000", 0, 1, 1),

        ("DevOps Engineer Platform Infrastructure",
         "You will build and maintain CI/CD pipelines, manage Kubernetes clusters, "
         "monitor system reliability, and automate infrastructure using Terraform. "
         "You will be on a 24/7 on-call rotation with a dedicated SRE team.",
         "Global technology consultancy, 5000 employees India office",
         "3+ years DevOps or SRE. Kubernetes and Docker required. Terraform. AWS preferred. "
         "Linux proficiency. Monitoring with Prometheus and Grafana.",
         "CTC 18-25 LPA. Medical insurance. Annual bonus. Company laptop.",
         "1800000-2500000", 0, 1, 1),
    ]

    records = []
    for i in range(3000):
        t, d, cp, rq, bn, sl, tc, logo, qs = FAKE[i % len(FAKE)]
        records.append({
            "title": t, "description": d, "company_profile": cp,
            "requirements": rq, "benefits": bn, "salary_range": sl,
            "telecommuting": tc, "has_company_logo": logo,
            "has_questions": qs, "fraudulent": 1
        })
    for i in range(15000):
        t, d, cp, rq, bn, sl, tc, logo, qs = REAL[i % len(REAL)]
        records.append({
            "title": t, "description": d, "company_profile": cp,
            "requirements": rq, "benefits": bn, "salary_range": sl,
            "telecommuting": tc, "has_company_logo": logo,
            "has_questions": qs, "fraudulent": 0
        })

    df = pd.DataFrame(records)
    path = RAW / "jobs" / "fake_job_postings.csv"
    df.to_csv(path, index=False)
    log.info(f"Synthetic EMSCAD: {len(df)} rows ({(df.fraudulent==1).sum()} fake, "
             f"{(df.fraudulent==0).sum()} real)")
    return path


# ---------------------------------------------------------------------------
# B. PhiUSIIL - 235k Phishing / Legitimate URLs
# ---------------------------------------------------------------------------

def get_phiusiil() -> Optional[Path]:
    dest = RAW / "urls" / "PhiUSIIL.csv"
    if dest.exists() and dest.stat().st_size > 5_000_000:
        return dest
    log.info("Downloading PhiUSIIL Phishing URL Dataset (235k URLs)...")
    zpath = RAW / "urls" / "phiusiil.zip"
    if fetch("https://archive.ics.uci.edu/static/public/967/"
             "phiusiil+phishing+url+dataset.zip", zpath, "PhiUSIIL"):
        unzip(zpath, RAW / "urls")
        for f in (RAW / "urls").glob("*.csv"):
            if "phishing" in f.name.lower() or "PhiUSIIL" in f.name:
                f.rename(dest)
                return dest
    if fetch("https://zenodo.org/records/8011528/files/"
             "PhiUSIIL_Phishing_URL_Dataset.csv", dest, "PhiUSIIL direct"):
        return dest
    return None


# ---------------------------------------------------------------------------
# C. URLhaus - Live Malicious URL Feed (abuse.ch)
# ---------------------------------------------------------------------------

def get_urlhaus() -> Optional[Path]:
    dest = RAW / "urls" / "urlhaus_recent.csv"
    log.info("Downloading URLhaus live malicious URL feed...")
    if fetch("https://urlhaus.abuse.ch/downloads/csv_recent/",
             dest, "URLhaus recent"):
        return dest
    if fetch("https://urlhaus.abuse.ch/downloads/csv/",
             dest, "URLhaus full"):
        return dest
    return None


# ---------------------------------------------------------------------------
# D. OpenPhish - Active Phishing Feed
# ---------------------------------------------------------------------------

def get_openphish() -> Optional[Path]:
    dest = RAW / "urls" / "openphish.txt"
    log.info("Downloading OpenPhish active phishing feed...")
    if fetch("https://openphish.com/feed.txt", dest, "OpenPhish"):
        return dest
    return None


# ---------------------------------------------------------------------------
# E. Majestic Million - Top 1M Legitimate Domains
# ---------------------------------------------------------------------------

def get_majestic() -> Optional[Path]:
    dest = RAW / "domains" / "majestic_million.csv"
    if dest.exists() and dest.stat().st_size > 10_000_000:
        return dest
    log.info("Downloading Majestic Million legitimate domains...")
    if fetch("https://downloads.majestic.com/majestic_million.csv",
             dest, "Majestic Million"):
        return dest
    zpath = RAW / "domains" / "tranco.zip"
    if fetch("https://tranco-list.eu/top-1m.csv.zip", zpath, "Tranco Top 1M"):
        unzip(zpath, RAW / "domains")
        t = RAW / "domains" / "top-1m.csv"
        if t.exists():
            t.rename(dest)
            return dest
    return None


# ---------------------------------------------------------------------------
# F. ISCX URL 2016 - Multi-class URL Dataset
# ---------------------------------------------------------------------------

def get_iscx() -> Optional[Path]:
    dest = RAW / "urls" / "iscx_urls.csv"
    if dest.exists():
        return dest
    log.info("Downloading ISCX URL dataset...")
    for url in [
        "https://raw.githubusercontent.com/faizann24/Using-machine-learning-to-detect-"
        "malicious-URLs/master/data/data.csv",
        "https://raw.githubusercontent.com/shreyagopal/Phishing-Website-Detection-by-"
        "Machine-Learning-Techniques/master/DataFiles/5.urldata.csv",
    ]:
        if fetch(url, dest, "ISCX URLs"):
            return dest
    return None


# ---------------------------------------------------------------------------
# G. Job-Specific URL Patterns
# ---------------------------------------------------------------------------

def build_job_url_dataset() -> Path:
    """
    Generate a comprehensive labelled dataset of job-related URLs.
    """
    import random, string
    random.seed(42)

    records = []

    def rnd(n=6):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    def rnd_digits(n=3):
        return "".join(random.choices(string.digits, k=n))

    # FRAUD PATTERN 1: Free hosting with job-related subdomain
    FREE_HOSTS = [
        "wixsite.com", "weebly.com", "wordpress.com", "blogspot.com",
        "site123.me", "yolasite.com", "jimdo.com", "webnode.com",
        "strikingly.com", "000webhostapp.com", "byethost.com",
        "freehostia.com", "infinityfree.net", "biz.nf",
        "godaddysites.com", "squarespace.com",
    ]
    FRAUD_SUBDOMAINS = [
        "jobs", "hiring", "career", "apply-now", "work-from-home",
        "earn-daily", "income-daily", "salary-jobs", "urgent-hiring",
        "free-jobs", "top-jobs", "best-jobs", "india-jobs",
        "government-job", "online-work", "part-time-work",
        "data-entry-work", "typing-work", "ad-posting",
    ]
    FRAUD_PATHS = [
        "/jobs", "/apply", "/vacancy", "/career", "/hiring",
        "/immediate-joining", "/urgent-requirement", "/work-from-home",
        "/apply-now", "/register", "/join-now", "/get-started",
        "/home-based-jobs", "/earn-money", "/income",
    ]
    for host in FREE_HOSTS:
        for sub in FRAUD_SUBDOMAINS:
            path = random.choice(FRAUD_PATHS)
            records.append({
                "url": f"http://{sub}.{host}{path}",
                "label": 1, "category": "free_hosting_job_scam",
                "source": "pattern_generated"
            })
            records.append({
                "url": f"https://{sub}-{rnd(4)}.{host}{path}-{rnd_digits(3)}",
                "label": 1, "category": "free_hosting_job_scam",
                "source": "pattern_generated"
            })

    # FRAUD PATTERN 2: Typosquatting of known Indian employers
    LEGIT_EMPLOYERS = [
        "infosys", "wipro", "tcs", "accenture", "cognizant", "hcltech",
        "techm", "capgemini", "ibm", "oracle", "google", "amazon",
        "microsoft", "flipkart", "paytm", "swiggy", "zomato", "byju",
        "unacademy", "razorpay", "freshworks", "zoho", "mphasis",
        "hexaware", "persistent", "mindtree", "ltimindtree",
    ]
    TYPO_PATTERNS = [
        lambda n: f"{n}hiring.com",
        lambda n: f"{n}jobs.com",
        lambda n: f"{n}careers.in",
        lambda n: f"{n}-careers.com",
        lambda n: f"{n}-recruitment.com",
        lambda n: f"{n}-official.com",
        lambda n: f"{n}-india.com",
        lambda n: f"official{n}.com",
        lambda n: f"join{n}.com",
        lambda n: f"{n}hr.com",
        lambda n: f"{n}walk-in.com",
        lambda n: f"{n}placement.com",
        lambda n: f"apply-{n}.com",
        lambda n: f"{n[:-1]}{n[-1]}.com",
        lambda n: n.replace("o", "0") + ".com",
        lambda n: n.replace("i", "1") + ".com",
        lambda n: f"{n}-{rnd(4)}.com",
        lambda n: f"{n}{rnd_digits(4)}.com",
    ]
    TYPO_PATHS = ["/jobs/", "/apply/", "/career/", "/hiring/", "/vacancy/"]
    for employer in LEGIT_EMPLOYERS:
        for pattern in TYPO_PATTERNS:
            try:
                domain = pattern(employer)
                path = random.choice(TYPO_PATHS)
                records.append({
                    "url": f"http://www.{domain}{path}",
                    "label": 1, "category": "typosquatting_employer",
                    "source": "pattern_generated"
                })
            except Exception:
                pass

    # FRAUD PATTERN 3: Suspicious TLDs with job keywords
    SUSPICIOUS_TLDS = [
        ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click",
        ".work", ".online", ".site", ".website", ".tech", ".icu",
        ".vip", ".buzz", ".fun", ".gdn", ".host", ".live", ".uno",
        ".cyou", ".bond", ".bar", ".cfd", ".monster", ".rest",
    ]
    JOB_KEYWORDS = [
        "job", "jobs", "career", "hiring", "vacancy", "apply",
        "work", "earn", "income", "salary", "recruitment",
    ]
    for tld in SUSPICIOUS_TLDS:
        for kw in JOB_KEYWORDS:
            records.append({
                "url": f"http://{kw}{rnd(4)}{tld}/apply",
                "label": 1, "category": "suspicious_tld",
                "source": "pattern_generated"
            })
            records.append({
                "url": f"http://top-{kw}-india{tld}/register-now",
                "label": 1, "category": "suspicious_tld",
                "source": "pattern_generated"
            })

    # FRAUD PATTERN 4: URL shorteners redirecting to job scams
    SHORTENERS = [
        "bit.ly", "tinyurl.com", "ow.ly", "is.gd", "rb.gy",
        "cutt.ly", "shorturl.at", "s.id", "v.gd",
    ]
    for shortener in SHORTENERS:
        for _ in range(8):
            records.append({
                "url": f"https://{shortener}/{rnd(7)}",
                "label": 1, "category": "url_shortener_job",
                "source": "pattern_generated"
            })

    # FRAUD PATTERN 5: IP address job URLs
    SUSPICIOUS_RANGES = [
        "45.{}.{}.{}", "185.{}.{}.{}", "91.{}.{}.{}",
        "194.{}.{}.{}", "213.{}.{}.{}", "103.{}.{}.{}",
        "202.{}.{}.{}", "117.{}.{}.{}",
    ]
    for ip_tmpl in SUSPICIOUS_RANGES:
        for _ in range(5):
            ip = ip_tmpl.format(
                random.randint(100, 254),
                random.randint(0, 254),
                random.randint(1, 254)
            )
            records.append({
                "url": f"http://{ip}/jobs",
                "label": 1, "category": "ip_address_job",
                "source": "pattern_generated"
            })

    # FRAUD PATTERN 6: Random gibberish domains
    for _ in range(500):
        domain = rnd(random.randint(8, 16)) + ".com"
        records.append({
            "url": f"http://www.{domain}/job-apply-now",
            "label": 1, "category": "random_domain",
            "source": "pattern_generated"
        })

    # FRAUD PATTERN 7: Payment keywords in job URL
    PAYMENT_WORDS = [
        "registration-fee", "joining-fee", "pay-now", "deposit",
        "investment", "activation-charge", "processing-fee",
    ]
    for word in PAYMENT_WORDS:
        for _ in range(20):
            records.append({
                "url": f"http://jobs-{rnd(4)}.com/{word}",
                "label": 1, "category": "payment_in_url",
                "source": "pattern_generated"
            })

    # LEGITIMATE PATTERN 1: Major Indian IT employer career portals
    LEGIT_JOB_SOURCES = [
        ("careers.infosys.com",   ["/jobdescription", "/jobdetail"]),
        ("wipro.com",             ["/careers/job-detail", "/jobs"]),
        ("ibegin.tcs.com",        ["/jobs/search", "/apply"]),
        ("careers.accenture.com", ["/us-en/job-detail", "/in-en/job"]),
        ("jobs.cognizant.com",    ["/job/", "/careers/"]),
        ("careers.hcltech.com",   ["/job-detail", "/openings"]),
        ("jobs.techm.com",        ["/job/", "/opening"]),
        ("capgemini.com",         ["/en/careers/job/", "/jobs/"]),
        ("careers.ibm.com",       ["/job/", "/search/"]),
        ("oracle.com",            ["/careers/job/", "/search/"]),
    ]
    for domain, paths in LEGIT_JOB_SOURCES:
        for path in paths:
            for _ in range(15):
                job_id = rnd(8)
                records.append({
                    "url": f"https://www.{domain}{path}/{job_id}",
                    "label": 0, "category": "legit_employer_portal",
                    "source": "pattern_generated"
                })

    # LEGITIMATE PATTERN 2: Major job boards
    JOB_BOARDS = [
        ("naukri.com",        "/job-listings-{title}-{id}"),
        ("linkedin.com",      "/jobs/view/{id}"),
        ("indeed.com",        "/viewjob?jk={id}"),
        ("glassdoor.com",     "/job-listing/{title}-JV_KO0_15_KE{id}"),
        ("internshala.com",   "/internship/detail/{id}"),
        ("shine.com",         "/job/{id}"),
        ("monster.com",       "/job-openings/{id}"),
        ("timesjobs.com",     "/jobs/jobdetail/{id}"),
        ("angel.co",          "/company/{title}/jobs/{id}"),
        ("wellfound.com",     "/jobs/{id}"),
    ]
    JOB_TITLES = [
        "software-engineer", "data-analyst", "product-manager",
        "devops-engineer", "frontend-developer", "backend-engineer",
        "machine-learning-engineer", "qa-engineer", "business-analyst",
    ]
    for domain, path_tmpl in JOB_BOARDS:
        for _ in range(20):
            job_id = rnd(8)
            title = random.choice(JOB_TITLES)
            path = path_tmpl.format(id=job_id, title=title)
            records.append({
                "url": f"https://www.{domain}{path}",
                "label": 0, "category": "legit_job_board",
                "source": "pattern_generated"
            })

    # LEGITIMATE PATTERN 3: Company ATS platforms
    ATS_DOMAINS = [
        "jobs.lever.co", "greenhouse.io", "workday.com",
        "careers.smartrecruiters.com", "boards.greenhouse.io",
        "apply.workable.com", "icims.com",
    ]
    for ats in ATS_DOMAINS:
        for _ in range(15):
            records.append({
                "url": f"https://{ats}/{rnd(8)}/jobs/{rnd(8)}",
                "label": 0, "category": "legit_ats_platform",
                "source": "pattern_generated"
            })

    df = pd.DataFrame(records)
    path = RAW / "urls" / "job_url_patterns.csv"
    df.to_csv(path, index=False)
    fraud_count = (df["label"] == 1).sum()
    legit_count = (df["label"] == 0).sum()
    log.info(f"Job URL patterns: {len(df)} total "
             f"({fraud_count} fraud, {legit_count} legit)")
    return path


# ---------------------------------------------------------------------------
# H. Domain Whitelist - Verified Legitimate Employer Domains
# ---------------------------------------------------------------------------

def build_domain_whitelist() -> Path:
    WHITELIST = {
        "infosys.com": "IT Services", "wipro.com": "IT Services",
        "tcs.com": "IT Services", "hcltech.com": "IT Services",
        "techm.com": "IT Services", "cognizant.com": "IT Services",
        "capgemini.com": "IT Services", "mphasis.com": "IT Services",
        "hexaware.com": "IT Services", "persistent.com": "IT Services",
        "ltimindtree.com": "IT Services", "mindtree.com": "IT Services",
        "oracle.com": "Technology", "ibm.com": "Technology",
        "accenture.com": "Consulting", "kpmg.com": "Consulting",
        "deloitte.com": "Consulting", "pwc.com": "Consulting",
        "ey.com": "Consulting", "mckinsey.com": "Consulting",
        "flipkart.com": "E-commerce", "amazon.in": "E-commerce",
        "paytm.com": "Fintech", "phonepe.com": "Fintech",
        "razorpay.com": "Fintech", "zerodha.com": "Fintech",
        "groww.com": "Fintech", "cred.club": "Fintech",
        "swiggy.in": "Food Tech", "zomato.com": "Food Tech",
        "ola.com": "Transport", "uber.com": "Transport",
        "byju.com": "Edtech", "unacademy.com": "Edtech",
        "freshworks.com": "SaaS", "zoho.com": "SaaS",
        "browserstack.com": "DevTools", "postman.com": "DevTools",
        "google.com": "Technology", "microsoft.com": "Technology",
        "apple.com": "Technology", "meta.com": "Technology",
        "netflix.com": "Technology", "adobe.com": "Technology",
        "salesforce.com": "CRM", "atlassian.com": "DevTools",
        "naukri.com": "Job Board", "linkedin.com": "Job Board",
        "indeed.com": "Job Board", "glassdoor.com": "Job Board",
        "internshala.com": "Job Board", "shine.com": "Job Board",
        "monster.com": "Job Board", "timesjobs.com": "Job Board",
        "wellfound.com": "Job Board", "angel.co": "Job Board",
        "lever.co": "ATS", "greenhouse.io": "ATS",
        "workday.com": "ATS", "smartrecruiters.com": "ATS",
        "workable.com": "ATS", "icims.com": "ATS",
    }

    df = pd.DataFrame([
        {"domain": k, "category": v, "verified": True}
        for k, v in WHITELIST.items()
    ])
    path = RAW / "domains" / "whitelist.csv"
    df.to_csv(path, index=False)
    log.info(f"Domain whitelist: {len(df)} verified legitimate domains")
    return path


# ---------------------------------------------------------------------------
# I. Scam Phrase Dictionary
# ---------------------------------------------------------------------------

def build_scam_phrases() -> Path:
    phrases = [
        ("pay registration fee", 0.99, "payment"),
        ("registration fee required", 0.99, "payment"),
        ("pay security deposit", 0.99, "payment"),
        ("joining fee", 0.96, "payment"),
        ("activation charge", 0.96, "payment"),
        ("processing fee", 0.88, "payment"),
        ("course fee required", 0.90, "payment"),
        ("training fee", 0.86, "payment"),
        ("document verification fee", 0.95, "payment"),
        ("pay to start", 0.98, "payment"),
        ("invest to earn", 0.97, "payment"),
        ("refundable deposit", 0.84, "payment"),
        ("100 percent placement", 0.94, "false_guarantee"),
        ("guaranteed job", 0.93, "false_guarantee"),
        ("guaranteed placement", 0.93, "false_guarantee"),
        ("job guarantee", 0.92, "false_guarantee"),
        ("guaranteed income", 0.91, "false_guarantee"),
        ("guaranteed salary", 0.88, "false_guarantee"),
        ("money back guarantee", 0.80, "false_guarantee"),
        ("placement guarantee", 0.92, "false_guarantee"),
        ("earn lakhs monthly", 0.93, "unrealistic_salary"),
        ("earn 1 lakh per month", 0.89, "unrealistic_salary"),
        ("earn 80000 per month", 0.88, "unrealistic_salary"),
        ("earn 50000 per month", 0.83, "unrealistic_salary"),
        ("1000 per day", 0.83, "unrealistic_salary"),
        ("2000 per day", 0.83, "unrealistic_salary"),
        ("unlimited earning potential", 0.88, "unrealistic_salary"),
        ("earn while you sleep", 0.95, "unrealistic_salary"),
        ("passive income", 0.70, "unrealistic_salary"),
        ("no interview required", 0.93, "process_anomaly"),
        ("direct selection", 0.85, "process_anomaly"),
        ("direct joining", 0.76, "process_anomaly"),
        ("no experience required", 0.82, "process_anomaly"),
        ("no experience needed", 0.82, "process_anomaly"),
        ("no target no pressure", 0.74, "process_anomaly"),
        ("anyone can apply", 0.73, "process_anomaly"),
        ("walk in interview today", 0.68, "process_anomaly"),
        ("immediate start", 0.62, "process_anomaly"),
        ("whatsapp your cv", 0.96, "contact_redflags"),
        ("send resume on whatsapp", 0.97, "contact_redflags"),
        ("whatsapp your resume", 0.96, "contact_redflags"),
        ("contact on whatsapp", 0.90, "contact_redflags"),
        ("send your details on whatsapp", 0.97, "contact_redflags"),
        ("share your details on whatsapp", 0.96, "contact_redflags"),
        ("call immediately", 0.72, "contact_redflags"),
        ("earn from home", 0.87, "remote_fraud"),
        ("work from home earn", 0.90, "remote_fraud"),
        ("work on mobile", 0.85, "remote_fraud"),
        ("data entry work from home", 0.84, "remote_fraud"),
        ("typing work from home", 0.84, "remote_fraud"),
        ("copy paste work", 0.88, "remote_fraud"),
        ("ad posting job", 0.90, "remote_fraud"),
        ("captcha work", 0.92, "remote_fraud"),
        ("click and earn", 0.95, "remote_fraud"),
        ("online survey earn", 0.86, "remote_fraud"),
        ("network marketing", 0.84, "mlm"),
        ("multi level marketing", 0.88, "mlm"),
        ("mlm", 0.80, "mlm"),
        ("build your downline", 0.93, "mlm"),
        ("refer and earn", 0.80, "mlm"),
        ("direct selling", 0.68, "mlm"),
        ("build your team", 0.73, "mlm"),
        ("limited seats", 0.74, "urgency"),
        ("last date today", 0.79, "urgency"),
        ("seats filling fast", 0.76, "urgency"),
        ("today only", 0.72, "urgency"),
        ("closing today", 0.72, "urgency"),
        ("competitive salary", -0.18, "legit_signal"),
        ("health insurance", -0.22, "legit_signal"),
        ("annual ctc", -0.28, "legit_signal"),
        ("interview process", -0.22, "legit_signal"),
        ("background verification", -0.18, "legit_signal"),
        ("provident fund", -0.20, "legit_signal"),
        ("employee stock ownership", -0.22, "legit_signal"),
        ("esop", -0.22, "legit_signal"),
        ("notice period", -0.18, "legit_signal"),
        ("reference check", -0.15, "legit_signal"),
        ("ctc breakup", -0.20, "legit_signal"),
        ("medical benefits", -0.18, "legit_signal"),
        ("agile", -0.15, "legit_signal"),
        ("two-week sprint", -0.20, "legit_signal"),
        ("code review", -0.18, "legit_signal"),
    ]

    df = pd.DataFrame(phrases, columns=["phrase", "weight", "category"])
    path = PROC / "scam_phrases.csv"
    df.to_csv(path, index=False)
    log.info(f"Scam phrase dictionary: {len(phrases)} entries")
    return path


# ---------------------------------------------------------------------------
# Combine and preprocess all URL datasets
# ---------------------------------------------------------------------------

def build_combined_url_dataset():
    frames = []

    def load_phiusiil():
        p = RAW / "urls" / "PhiUSIIL.csv"
        if not p.exists():
            return
        df = pd.read_csv(p, low_memory=False)
        url_col = next((c for c in df.columns if "url" in c.lower()), None)
        lbl_col = next((c for c in df.columns
                        if any(k in c.lower() for k in
                               ["label", "phishing", "status", "class"])), None)
        if url_col and lbl_col:
            df = df[[url_col, lbl_col]].rename(columns={url_col:"url", lbl_col:"label"})
            df["label"] = df["label"].map(
                lambda x: 1 if str(x).lower() in
                ["phishing","1","malicious","bad","scam"] else 0
            )
            frames.append(df[["url","label"]])
            log.info(f"PhiUSIIL loaded: {len(df)} rows")

    def load_urlhaus():
        p = RAW / "urls" / "urlhaus_recent.csv"
        if not p.exists():
            return
        try:
            df = pd.read_csv(p, comment="#",
                              header=None, on_bad_lines="skip",
                              names=["id","date","url","status","last_online",
                                     "threat","tags","urlhaus_link","reporter"])
            df = df[["url"]].dropna()
            df["label"] = 1
            df = df.sample(min(80000, len(df)), random_state=42)
            frames.append(df)
            log.info(f"URLhaus loaded: {len(df)} rows")
        except Exception as e:
            log.warning(f"URLhaus parse error: {e}")

    def load_openphish():
        p = RAW / "urls" / "openphish.txt"
        if not p.exists():
            return
        urls = [l.strip() for l in open(p) if l.strip().startswith("http")]
        df = pd.DataFrame({"url": urls, "label": 1})
        frames.append(df)
        log.info(f"OpenPhish loaded: {len(df)} rows")

    def load_iscx():
        p = RAW / "urls" / "iscx_urls.csv"
        if not p.exists():
            return
        try:
            df = pd.read_csv(p)
            url_col = next((c for c in df.columns if "url" in c.lower()), None)
            lbl_col = next((c for c in df.columns
                            if any(k in c.lower() for k in ["label","type","class"])), None)
            if url_col and lbl_col:
                df = df[[url_col, lbl_col]].rename(columns={url_col:"url",lbl_col:"label"})
                df["label"] = df["label"].map(
                    lambda x: 0 if str(x).lower() in
                    ["benign","0","legitimate","safe","good"] else 1
                )
                frames.append(df[["url","label"]])
                log.info(f"ISCX loaded: {len(df)} rows")
        except Exception as e:
            log.warning(f"ISCX parse error: {e}")

    def load_majestic():
        p = RAW / "domains" / "majestic_million.csv"
        if not p.exists():
            return
        df = pd.read_csv(p)
        domain_col = next((c for c in df.columns
                            if any(k in c.lower() for k in ["domain","url","host"])), df.columns[1])
        df = df[[domain_col]].dropna().rename(columns={domain_col:"url"})
        df["url"] = "https://www." + df["url"].astype(str)
        df["label"] = 0
        df = df.sample(min(120000, len(df)), random_state=42)
        frames.append(df)
        log.info(f"Majestic Million loaded: {len(df)} rows")

    def load_job_patterns():
        p = RAW / "urls" / "job_url_patterns.csv"
        if not p.exists():
            return
        df = pd.read_csv(p)
        frames.append(df[["url","label"]])
        log.info(f"Job URL patterns loaded: {len(df)} rows")

    for loader in [load_phiusiil, load_urlhaus, load_openphish,
                   load_iscx, load_majestic, load_job_patterns]:
        try:
            loader()
        except Exception as e:
            log.warning(f"Loader error: {e}")

    if not frames:
        log.error("No URL datasets loaded. Generating synthetic data only.")
        build_job_url_dataset()
        load_job_patterns()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["url","label"])
    combined = combined[combined["url"].str.startswith("http", na=False)]
    combined["label"] = combined["label"].astype(int)
    combined = combined.drop_duplicates(subset=["url"])
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)

    n_legit = (combined["label"]==0).sum()
    n_fraud = (combined["label"]==1).sum()
    log.info(f"Combined URL dataset: {len(combined)} total "
             f"({n_fraud} fraud, {n_legit} legit)")

    train, temp = train_test_split(combined, test_size=0.20,
                                    stratify=combined["label"], random_state=42)
    val, test = train_test_split(temp, test_size=0.50,
                                  stratify=temp["label"], random_state=42)
    train.to_csv(PROC / "url_train.csv", index=False)
    val.to_csv(PROC / "url_val.csv",     index=False)
    test.to_csv(PROC / "url_test.csv",   index=False)
    log.info(f"URL splits: train={len(train)}, val={len(val)}, test={len(test)}")


def preprocess_jobs():
    candidates = [
        RAW / "jobs" / "fake_job_postings.csv",
        RAW / "jobs" / "EMSCAD.csv",
    ]
    df = None
    for c in candidates:
        if c.exists():
            df = pd.read_csv(c).fillna("")
            break
    if df is None:
        df = pd.read_csv(get_emscad()).fillna("")

    for col in ["fraudulent","fraud","label","is_fraud"]:
        if col in df.columns:
            df["label"] = df[col].astype(int)
            break

    TEXT_COLS = ["title","company_profile","description",
                 "requirements","benefits","location","salary_range"]
    for col in TEXT_COLS:
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df["full_text"] = (
        "Title: " + df["title"] + " [SEP] " +
        "Company: " + df["company_profile"] + " [SEP] " +
        "Description: " + df["description"] + " [SEP] " +
        "Requirements: " + df["requirements"] + " [SEP] " +
        "Benefits: " + df["benefits"]
    ).str[:3000]

    df["short_text"] = (df["title"] + " " + df["description"].str[:500])
    df["has_salary"] = (df["salary_range"] != "").astype(int)
    df["has_logo"] = df.get("has_company_logo", pd.Series(0, index=df.index)).fillna(0).astype(int)
    df["has_questions"] = df.get("has_questions", pd.Series(0, index=df.index)).fillna(0).astype(int)
    df["telecommuting"] = df.get("telecommuting", pd.Series(0, index=df.index)).fillna(0).astype(int)
    df["text_length"] = df["full_text"].str.len()
    df["desc_length"] = df["description"].str.len()
    df["has_gmail"] = df["full_text"].str.contains(
        r"@gmail|@yahoo|@rediff", regex=True, case=False).astype(int)
    df["has_whatsapp"] = df["full_text"].str.contains(
        "whatsapp", case=False).astype(int)
    df["exclamation_count"] = df["full_text"].str.count("!")
    df["caps_ratio"] = df["full_text"].apply(
        lambda x: sum(1 for c in x if c.isupper()) / max(len(x),1)
    )

    train, temp = train_test_split(df, test_size=0.30,
                                    stratify=df["label"], random_state=42)
    val, test = train_test_split(temp, test_size=0.50,
                                  stratify=temp["label"], random_state=42)
    train.to_csv(PROC / "train.csv", index=False)
    val.to_csv(PROC / "val.csv",     index=False)
    test.to_csv(PROC / "test.csv",   index=False)
    log.info(f"Job splits: train={len(train)}, val={len(val)}, test={len(test)}")


if __name__ == "__main__":
    log.info("=" * 60)
    log.info("  TRUSTHIRE - DOWNLOADING ALL DATASETS")
    log.info("=" * 60)

    get_emscad()
    get_phiusiil()
    get_urlhaus()
    get_openphish()
    get_majestic()
    get_iscx()
    build_job_url_dataset()
    build_domain_whitelist()
    build_scam_phrases()
    build_combined_url_dataset()
    preprocess_jobs()

    log.info("All datasets ready. Run: python scripts/train_all_models.py")
