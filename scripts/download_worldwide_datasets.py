"""
scripts/download_worldwide_datasets.py

Acquires all training data for TrustHire global operation.

Dataset inventory:
  A. EMSCAD          — 17,880 labelled job postings (Kaggle / Zenodo)
  B. PhiUSIIL        — 235,795 phishing URLs (UCI ML Repository)
  C. URLhaus         — Live global malicious URL feed (abuse.ch, daily updated)
  D. OpenPhish       — Active phishing feed (updated every 12 hours)
  E. Majestic Million — Top 1M legitimate domains worldwide
  F. ISCX URL 2016   — 35,300 multi-class URLs (UNB)
  G. Global job URL  — Synthetic patterns for 12 major markets
  H. FTC patterns    — US job fraud vocabulary (FTC Consumer Sentinel)
  I. Action Fraud UK — UK job fraud vocabulary
  J. ACCC Scamwatch  — Australian job scam vocabulary
  K. Multilingual phrases — Fraud vocabulary in 8 languages
  L. Global registries  — National business registry routing table
"""

import os, sys, re, json, gzip, zipfile, shutil, time
import subprocess, logging
from pathlib import Path
from typing import Optional
import requests, pandas as pd, numpy as np
from sklearn.model_selection import train_test_split
from tqdm import tqdm

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worldwide_download")

BASE = Path("data")
RAW  = BASE / "raw"
PROC = BASE / "processed"

for d in [RAW, PROC, RAW/"jobs", RAW/"urls",
          RAW/"domains", RAW/"fraud_reports"]:
    d.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def fetch(url: str, dest: Path, label: str = "", timeout: int = 120) -> bool:
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) "
                              "Gecko/20100101 Firefox/125.0"}
    try:
        r = requests.get(url, stream=True, timeout=timeout, headers=headers)
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f, tqdm(
            desc=f"  {label}", total=total,
            unit="B", unit_scale=True, ncols=88
        ) as bar:
            for chunk in r.iter_content(8192):
                f.write(chunk); bar.update(len(chunk))
        return True
    except Exception as e:
        log.warning(f"  {label} failed: {e}"); return False


def unzip(src: Path, dest: Path):
    with zipfile.ZipFile(src, "r") as z: z.extractall(dest)
    src.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# A. EMSCAD
# ─────────────────────────────────────────────────────────────────────────────

def get_emscad() -> Path:
    candidates = [RAW/"jobs"/"fake_job_postings.csv",
                  RAW/"jobs"/"EMSCAD.csv"]
    for c in candidates:
        if c.exists() and c.stat().st_size > 200_000:
            log.info("EMSCAD already present"); return c

    log.info("Downloading EMSCAD dataset...")
    try:
        subprocess.run(
            ["kaggle", "datasets", "download",
             "-d", "shivamb/real-or-fake-fake-jobposting-prediction",
             "-p", str(RAW/"jobs"), "--unzip", "--quiet"],
            check=True, timeout=300, capture_output=True)
        for c in candidates:
            if c.exists(): return c
    except Exception as e:
        log.warning(f"Kaggle CLI failed: {e}")

    dest = RAW/"jobs"/"fake_job_postings.csv"
    for url in [
        "https://zenodo.org/records/5945271/files/EMSCAD.csv",
        "https://github.com/aashari/fake-job-posting/raw/master/"
        "data/fake_job_postings.csv",
    ]:
        if fetch(url, dest, "EMSCAD"): return dest

    log.warning("All EMSCAD sources failed — generating worldwide synthetic data")
    return _generate_worldwide_synthetic()


def _generate_worldwide_synthetic() -> Path:
    """
    Generates a synthetic job posting dataset covering documented fraud patterns
    from India (cybercrime.gov.in), USA (FTC 2023), UK (Action Fraud),
    Australia (ACCC Scamwatch), Southeast Asia, and the Middle East.
    """
    import random; random.seed(42)

    FAKE_BY_REGION = {
        "IN": [
            ("Work From Home Data Entry Earn 40000 Monthly",
             "Earn Rs 40000-80000 per month from home. No experience needed. "
             "Pay Rs 499 registration fee. WhatsApp 9876543210. "
             "Guaranteed placement. No interview required."),
            ("Urgent Hiring Direct Joining No Interview",
             "No interview required. Direct selection. Salary 35000 fixed. "
             "Send resume on WhatsApp. 100 percent job guarantee. Last date today."),
            ("Network Marketing Executive Earn Unlimited",
             "Build your network. Earn unlimited passive income. Refer and earn. "
             "Investment Rs 2000 to start. Multi level marketing opportunity."),
        ],
        "US": [
            ("Remote Customer Service Earn 5000 Weekly",
             "Earn $5000 weekly working from home. No experience needed. "
             "Flexible hours. Only requirement: laptop and internet. "
             "No background check required. Apply today, start tomorrow."),
            ("Mystery Shopper Needed Immediate Start",
             "Earn $400 per day as a mystery shopper. We will mail a cheque. "
             "Deposit it and forward funds to our vendors. Immediate openings."),
            ("Package Reshipping Coordinator Earn From Home",
             "Process and reship packages from home. Earn $50 per package. "
             "No experience required. Pay $99 for starter kit."),
        ],
        "GB": [
            ("Remote Administrator Pay DBS Check Fee",
             "We are hiring a remote administrator. Salary £35000. "
             "Work from home. Pay £150 DBS check fee to proceed with application. "
             "No interview. Immediate start. Guaranteed job offer."),
            ("NHS Patient Coordinator Advance Fee",
             "NHS-affiliated patient services role. £28000 salary. "
             "Pay £200 compliance and right to work verification fee. "
             "Start within the week. No interview required."),
        ],
        "AU": [
            ("FIFO Mining Opportunity Pay Medical Fee",
             "FIFO opportunity in WA. Earn $180000/year. Training provided. "
             "Pay $500 medical clearance and induction fee before start date. "
             "No experience needed. Immediate openings."),
            ("Nanny Role Overseas Visa Fee Required",
             "Seeking live-in nanny. Salary $6000/month AUD. "
             "Pay $300 visa and background processing fee. "
             "Accommodation and flights provided."),
        ],
        "MY": [
            ("Online Part Time Job High Salary No Experience",
             "Earn RM 3000-8000 per month part time. Work from anywhere. "
             "Simple tasks via WhatsApp. Registration fee RM 50. "
             "Immediate start. Limited slots available."),
        ],
        "PH": [
            ("Work From Home Earn Daily Via GCash",
             "Earn PHP 5000-15000 per day from home. No experience needed. "
             "Just like and share posts. Weekly payout via GCash. "
             "Registration P500. Start earning immediately."),
        ],
        "AE": [
            ("Gulf Country Job Visa Processing Agent Needed",
             "Hiring for Saudi Arabia and UAE. Salary 3000-8000 SAR. "
             "Free food accommodation. Pay visa processing fee AED 1500. "
             "Immediate joining. Contact WhatsApp. No experience required."),
        ],
    }

    REAL = [
        ("Senior Software Engineer Backend",
         "We are seeking an experienced backend engineer to build scalable APIs, "
         "mentor junior engineers, and contribute to architecture decisions. "
         "Requirements: 5+ years Python or Go, PostgreSQL, AWS or GCP. "
         "CTC 20-30 LPA. Health insurance. ESOP. Annual learning budget."),
        ("Product Manager Growth",
         "Own the acquisition funnel. Define roadmap, run A/B tests, "
         "analyse cohort data. 3-5 years PM experience required. "
         "Competitive salary with equity. Flexible working. MacBook provided."),
        ("Data Analyst Business Intelligence",
         "Build dashboards in Tableau, analyse metrics, present to leadership. "
         "SQL mandatory. Python preferred. 2+ years experience. "
         "Competitive salary. PF. Health insurance. Hybrid work."),
    ]

    records = []
    for region, patterns in FAKE_BY_REGION.items():
        reps = {"IN": 600, "US": 500, "GB": 400, "AU": 350,
                "MY": 300, "PH": 300, "AE": 250}.get(region, 200)
        for i in range(reps):
            t, d = patterns[i % len(patterns)]
            records.append({
                "title": t, "description": d, "company_profile": "",
                "requirements": "No experience required",
                "benefits": "Daily/weekly payment guaranteed",
                "salary_range": "", "telecommuting": 1,
                "has_company_logo": 0, "has_questions": 0,
                "fraudulent": 1, "region": region
            })

    for i in range(18000):
        t, d = REAL[i % len(REAL)][:2]
        records.append({
            "title": t, "description": d,
            "company_profile": "Series B funded technology company with 300 employees",
            "requirements": "3-5 years relevant experience. Degree preferred.",
            "benefits": "Equity, health insurance, flexible working, learning budget",
            "salary_range": "1500000-3000000", "telecommuting": 0,
            "has_company_logo": 1, "has_questions": 1,
            "fraudulent": 0, "region": "GLOBAL"
        })

    df = pd.DataFrame(records)
    path = RAW / "jobs" / "fake_job_postings.csv"
    df.to_csv(path, index=False)
    log.info(f"Worldwide synthetic dataset: {len(df)} rows")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# B–F. URL Datasets
# ─────────────────────────────────────────────────────────────────────────────

def get_url_datasets():
    log.info("Downloading URL fraud datasets...")

    # PhiUSIIL — 235k phishing/legitimate URLs
    phiusiil = RAW/"urls"/"PhiUSIIL.csv"
    if not (phiusiil.exists() and phiusiil.stat().st_size > 5_000_000):
        zp = RAW/"urls"/"phiusiil.zip"
        if fetch("https://archive.ics.uci.edu/static/public/967/"
                 "phiusiil+phishing+url+dataset.zip", zp, "PhiUSIIL"):
            unzip(zp, RAW/"urls")
            for f in (RAW/"urls").glob("*.csv"):
                if "phishing" in f.name.lower() or "PhiUSIIL" in f.name:
                    f.rename(phiusiil); break
        else:
            fetch("https://zenodo.org/records/8011528/files/"
                  "PhiUSIIL_Phishing_URL_Dataset.csv", phiusiil, "PhiUSIIL direct")

    # URLhaus — live malicious URL feed, updated daily
    fetch("https://urlhaus.abuse.ch/downloads/csv_recent/",
          RAW/"urls"/"urlhaus.csv", "URLhaus live feed")

    # OpenPhish — active phishing URLs, updated every 12 hours
    fetch("https://openphish.com/feed.txt",
          RAW/"urls"/"openphish.txt", "OpenPhish")

    # Majestic Million — global legitimate domain baseline
    majestic = RAW/"domains"/"majestic_million.csv"
    if not (majestic.exists() and majestic.stat().st_size > 10_000_000):
        if not fetch("https://downloads.majestic.com/majestic_million.csv",
                     majestic, "Majestic Million"):
            zp = RAW/"domains"/"tranco.zip"
            if fetch("https://tranco-list.eu/top-1m.csv.zip", zp, "Tranco"):
                unzip(zp, RAW/"domains")
                t = RAW/"domains"/"top-1m.csv"
                if t.exists(): t.rename(majestic)

    # ISCX URL 2016
    iscx = RAW/"urls"/"iscx_urls.csv"
    if not iscx.exists():
        fetch("https://raw.githubusercontent.com/faizann24/Using-machine-learning-"
              "to-detect-malicious-URLs/master/data/data.csv", iscx, "ISCX URLs")


# ─────────────────────────────────────────────────────────────────────────────
# G. Global Job-Specific URL Patterns
# ─────────────────────────────────────────────────────────────────────────────

def build_global_job_url_patterns() -> Path:
    """
    Generates a labelled URL dataset covering job-scam patterns in 12 markets.
    Fraud patterns sourced from FTC (USA), Action Fraud (UK), ACCC (AU),
    cybercrime.gov.in (IN), MAS Singapore, Europol annual reports.
    """
    import random, string
    random.seed(42)

    def rnd(n=6):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    records = []

    # Free hosting platforms — used by scammers in every country
    FREE_HOSTS = [
        "wixsite.com", "weebly.com", "wordpress.com", "blogspot.com",
        "site123.me", "yolasite.com", "jimdo.com", "webnode.com",
        "mystrikingly.com", "000webhostapp.com", "byethost.com",
        "freehostia.com", "godaddysites.com", "infinityfree.net",
    ]
    FRAUD_SUBS = [
        "jobs", "hiring", "apply", "earn-daily", "work-home",
        "income-daily", "urgent-hiring", "genuine-jobs",
        "online-jobs", "part-time-earn", "salary-guaranteed",
    ]
    FRAUD_PATHS = ["/jobs", "/apply", "/register", "/join-now",
                    "/work-from-home", "/earn-money", "/urgent"]
    for host in FREE_HOSTS:
        for sub in FRAUD_SUBS:
            path = random.choice(FRAUD_PATHS)
            records.append({"url": f"http://{sub}.{host}{path}",
                             "label": 1, "category": "free_hosting"})
            records.append({"url": f"https://{sub}-{rnd(4)}.{host}{path}",
                             "label": 1, "category": "free_hosting"})

    # Typosquatting across all major global employers
    GLOBAL_EMPLOYERS = [
        # India
        "infosys", "wipro", "tcs", "accenture", "cognizant", "hcltech",
        # US/Global
        "google", "amazon", "microsoft", "apple", "meta", "netflix",
        "uber", "airbnb", "salesforce", "oracle", "ibm", "adobe",
        # UK
        "bbc", "hsbc", "lloyds", "barclays", "bp", "unilever",
        # Australia
        "commbank", "westpac", "anz", "woolworths", "telstra",
        # Canada
        "shopify", "rbc", "td", "bmo", "rogers",
        # Germany
        "sap", "siemens", "bmw", "volkswagen", "bosch",
        # UAE/Gulf
        "emirates", "etisalat", "du", "emaar",
        # Singapore/SEA
        "dbs", "grab", "sea", "singtel",
        # Philippines
        "bdo", "bpi", "metrobank", "globe",
    ]
    TYPO_PATTERNS = [
        lambda n: f"{n}hiring.com",
        lambda n: f"{n}jobs.com",
        lambda n: f"{n}careers.com",
        lambda n: f"{n}-careers.com",
        lambda n: f"{n}-recruitment.com",
        lambda n: f"{n}-official.com",
        lambda n: f"official{n}.com",
        lambda n: f"join{n}.com",
        lambda n: f"apply-{n}.com",
        lambda n: f"{n}{rnd(4)}.com",
        lambda n: n.replace("o", "0") + ".com",
        lambda n: n.replace("i", "1") + ".com",
        lambda n: f"{n}hr.com",
    ]
    for employer in GLOBAL_EMPLOYERS:
        for pattern in TYPO_PATTERNS:
            try:
                domain = pattern(employer)
                records.append({"url": f"http://www.{domain}/jobs/",
                                 "label": 1, "category": "typosquatting"})
            except Exception:
                pass

    # Suspicious TLDs with job content
    SUSPICIOUS_TLDS = [
        ".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".click",
        ".work", ".online", ".site", ".website", ".tech", ".icu",
        ".vip", ".buzz", ".fun", ".live", ".uno", ".cyou", ".bond",
        ".bar", ".cfd", ".monster",
    ]
    JOB_KWS = ["job", "jobs", "career", "hiring", "earn", "work", "income"]
    for tld in SUSPICIOUS_TLDS:
        for kw in JOB_KWS:
            records.append({"url": f"http://{kw}{rnd(4)}{tld}/apply",
                             "label": 1, "category": "suspicious_tld"})

    # URL shorteners
    for shortener in ["bit.ly", "tinyurl.com", "ow.ly", "is.gd",
                       "rb.gy", "cutt.ly", "shorturl.at"]:
        for _ in range(10):
            records.append({"url": f"https://{shortener}/{rnd(7)}",
                             "label": 1, "category": "url_shortener"})

    # IP address job URLs
    for ip_tmpl in ["45.{}.{}.{}", "185.{}.{}.{}", "91.{}.{}.{}",
                     "194.{}.{}.{}", "103.{}.{}.{}"]:
        for _ in range(8):
            ip = ip_tmpl.format(random.randint(50, 254),
                                random.randint(0, 254),
                                random.randint(1, 254))
            records.append({"url": f"http://{ip}/jobs",
                             "label": 1, "category": "ip_address"})

    # Legitimate sources — global coverage
    LEGIT_SOURCES = [
        # India
        ("careers.infosys.com",    "/jobid/"),
        ("wipro.com",              "/careers/job/"),
        ("ibegin.tcs.com",         "/jobs/"),
        ("naukri.com",             "/job-listings-"),
        ("internshala.com",        "/internship/detail/"),
        # USA/Global
        ("careers.google.com",     "/jobs/results/"),
        ("amazon.jobs",            "/en/jobs/"),
        ("careers.microsoft.com",  "/jobs/"),
        ("linkedin.com",           "/jobs/view/"),
        ("indeed.com",             "/viewjob?jk="),
        ("glassdoor.com",          "/job-listing/"),
        # UK
        ("bbc.co.uk",              "/careers/"),
        ("reed.co.uk",             "/jobs/"),
        ("totaljobs.com",          "/job/"),
        # Australia
        ("seek.com.au",            "/job/"),
        ("careerone.com.au",       "/job/"),
        ("commbank.com.au",        "/about-us/careers/"),
        # Canada
        ("workopolis.com",         "/job/"),
        ("careers.shopify.com",    "/"),
        # Germany
        ("stepstone.de",           "/stellenangebote/"),
        ("sap.com",                "/careers/"),
        # UAE/Gulf
        ("bayt.com",               "/jobs/"),
        ("gulftalent.com",         "/jobs/"),
        # Singapore/SEA
        ("jobstreet.com",          "/jobs/"),
        ("careers.grab.com",       "/"),
        # Philippines
        ("jobstreet.com.ph",       "/jobs/"),
        # ATS platforms (all countries)
        ("jobs.lever.co",          "/"),
        ("greenhouse.io",          "/job/"),
        ("workday.com",            "/jobs/"),
        ("workable.com",           "/j/"),
    ]
    for domain, path_prefix in LEGIT_SOURCES:
        for _ in range(15):
            records.append({
                "url": f"https://www.{domain}{path_prefix}{rnd(8)}",
                "label": 0, "category": "legit_job_source"
            })

    df = pd.DataFrame(records)
    path = RAW / "urls" / "global_job_url_patterns.csv"
    df.to_csv(path, index=False)
    log.info(f"Global job URL patterns: {len(df)} total "
             f"({(df['label']==1).sum()} fraud, {(df['label']==0).sum()} legit)")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# H–J. Regional Fraud Vocabulary (US, UK, AU)
# ─────────────────────────────────────────────────────────────────────────────

def build_regional_fraud_patterns():
    """Builds verified fraud vocabulary supplements from three English-speaking markets."""

    # US — FTC Consumer Sentinel Network 2023 top job scam types
    us_patterns = [
        {"description": "Earn $5000 weekly from home. No experience. "
         "Only need laptop. No background check. Apply today start tomorrow.",
         "fraudulent": 1, "region": "US"},
        {"description": "Mystery shopper needed. Earn $400/day evaluating stores. "
         "We will mail a cheque. Deposit it and forward remaining funds to vendor.",
         "fraudulent": 1, "region": "US"},
        {"description": "Package reshipping coordinator. Earn $50-100 per package. "
         "Pay $99 starter kit. Work your own hours. Weekly direct deposit.",
         "fraudulent": 1, "region": "US"},
        {"description": "Cryptocurrency investment advisor. Earn $300/day from home. "
         "Initial account funding required: $500 to activate your trading account.",
         "fraudulent": 1, "region": "US"},
        {"description": "Remote data entry position. Earn $800-1200/week. "
         "Work 2-3 hours daily. Pay $99 for training materials before start.",
         "fraudulent": 1, "region": "US"},
    ]

    # UK — Action Fraud published case studies
    uk_patterns = [
        {"description": "Remote administrator. Salary £35000. Work from home. "
         "Pay £150 DBS check fee to proceed with application. "
         "No interview. Immediate start. Guaranteed job offer.",
         "fraudulent": 1, "region": "GB"},
        {"description": "NHS-affiliated patient services coordinator. Pay £200 "
         "compliance and right to work verification fee. Start within the week.",
         "fraudulent": 1, "region": "GB"},
        {"description": "Earn £500-2000/day as financial wellness advisor. "
         "No qualifications required. Pay £299 training materials and compliance fee.",
         "fraudulent": 1, "region": "GB"},
        {"description": "Guaranteed placement in UK or Europe. Pay £500 placement fee. "
         "Job offer letter within 24 hours. All expenses covered.",
         "fraudulent": 1, "region": "GB"},
    ]

    # Australia — ACCC Scamwatch annual report patterns
    au_patterns = [
        {"description": "FIFO mining in WA. Earn $180000/year. Training provided. "
         "Pay $500 medical clearance and induction fee before start date.",
         "fraudulent": 1, "region": "AU"},
        {"description": "Live-in nanny for family relocating overseas. Salary $6000/month. "
         "Accommodation and flights provided. Pay $300 visa processing fee.",
         "fraudulent": 1, "region": "AU"},
        {"description": "Earn $1500/week from home processing applications. "
         "Flexible hours. Starter kit fee $199. Immediate openings.",
         "fraudulent": 1, "region": "AU"},
    ]

    combined = pd.DataFrame(us_patterns + uk_patterns + au_patterns)
    path = RAW / "fraud_reports" / "regional_fraud_vocabulary.csv"
    path.parent.mkdir(exist_ok=True)
    combined.to_csv(path, index=False)
    log.info(f"Regional fraud vocabulary: {len(combined)} records across US, UK, AU")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# K. Multilingual Scam Phrase Dictionary (8 languages)
# ─────────────────────────────────────────────────────────────────────────────

def build_multilingual_phrases() -> Path:
    phrases = []

    # ── English (global) ───────────────────────────────────────────────────
    en = [
        ("pay registration fee", 0.99, "payment", "en", "global"),
        ("registration fee required", 0.99, "payment", "en", "global"),
        ("pay security deposit", 0.99, "payment", "en", "global"),
        ("joining fee", 0.96, "payment", "en", "global"),
        ("activation charge", 0.96, "payment", "en", "global"),
        ("processing fee", 0.88, "payment", "en", "global"),
        ("training fee required", 0.90, "payment", "en", "global"),
        ("starter kit fee", 0.93, "payment", "en", "US"),
        ("background check fee", 0.92, "payment", "en", "US"),
        ("visa processing fee", 0.97, "payment", "en", "global"),
        ("medical clearance fee", 0.94, "payment", "en", "AU"),
        ("dbs check fee", 0.94, "payment", "en", "GB"),
        ("right to work verification fee", 0.95, "payment", "en", "GB"),
        ("document fee", 0.91, "payment", "en", "global"),
        ("deposit the check and wire", 0.99, "check_fraud", "en", "US"),
        ("mystery shopper needed", 0.88, "mystery_shopper", "en", "US"),
        ("package reshipping", 0.96, "reshipping", "en", "US"),
        ("forward funds to vendor", 0.99, "reshipping", "en", "US"),
        ("wire transfer required", 0.95, "wire_fraud", "en", "US"),
        ("guaranteed job placement", 0.93, "guarantee", "en", "global"),
        ("100 percent job guarantee", 0.94, "guarantee", "en", "global"),
        ("guaranteed income", 0.91, "guarantee", "en", "global"),
        ("money back guarantee", 0.80, "guarantee", "en", "global"),
        ("no experience necessary", 0.80, "process", "en", "global"),
        ("no interview required", 0.93, "process", "en", "global"),
        ("no background check required", 0.91, "process", "en", "global"),
        ("earn unlimited income", 0.88, "unrealistic", "en", "global"),
        ("fifo opportunity", 0.62, "mining_scam", "en", "AU"),
        ("visa sponsorship fee", 0.94, "payment", "en", "global"),
        ("gulf country job visa fee", 0.97, "payment", "en", "MENA"),
        ("salary in dollars tax free", 0.72, "vague", "en", "MENA"),
        # Legitimate signals — reduce fraud probability
        ("competitive salary package", -0.18, "legit", "en", "global"),
        ("annual ctc", -0.28, "legit", "en", "IN"),
        ("health insurance provided", -0.22, "legit", "en", "global"),
        ("equal opportunity employer", -0.30, "legit", "en", "global"),
        ("background verification required", -0.18, "legit", "en", "global"),
        ("notice period", -0.18, "legit", "en", "global"),
        ("superannuation", -0.25, "legit", "en", "AU"),
        ("provident fund", -0.20, "legit", "en", "IN"),
        ("esop equity", -0.22, "legit", "en", "global"),
    ]
    phrases.extend(en)

    # ── Hindi (India) ──────────────────────────────────────────────────────
    hi = [
        ("रजिस्ट्रेशन फीस भरें", 0.99, "payment", "hi", "IN"),
        ("सिक्योरिटी डिपॉजिट दें", 0.99, "payment", "hi", "IN"),
        ("अभी व्हाट्सएप करें", 0.90, "contact", "hi", "IN"),
        ("घर बैठे काम करें", 0.85, "remote_fraud", "hi", "IN"),
        ("प्रतिमाह लाखों कमाएं", 0.92, "unrealistic", "hi", "IN"),
        ("कोई अनुभव नहीं चाहिए", 0.82, "process", "hi", "IN"),
        ("इंटरव्यू नहीं होगा", 0.93, "process", "hi", "IN"),
        ("गारंटीड प्लेसमेंट", 0.93, "guarantee", "hi", "IN"),
        ("नेटवर्क मार्केटिंग", 0.83, "mlm", "hi", "IN"),
        ("रेफर करें और कमाएं", 0.80, "mlm", "hi", "IN"),
    ]
    phrases.extend(hi)

    # ── Arabic (MENA) ──────────────────────────────────────────────────────
    ar = [
        ("رسوم التسجيل", 0.99, "payment", "ar", "MENA"),
        ("دفع مقدم مطلوب", 0.95, "payment", "ar", "MENA"),
        ("رسوم معالجة التأشيرة", 0.97, "payment", "ar", "MENA"),
        ("لا تحتاج خبرة", 0.80, "process", "ar", "MENA"),
        ("ضمان التوظيف", 0.92, "guarantee", "ar", "MENA"),
        ("العمل من المنزل والربح", 0.87, "remote_fraud", "ar", "MENA"),
        ("إيداع مبلغ تأميني", 0.98, "payment", "ar", "MENA"),
        ("راتب مرتفع جداً بدون خبرة", 0.88, "unrealistic", "ar", "MENA"),
    ]
    phrases.extend(ar)

    # ── Bahasa Melayu (Malaysia/Indonesia) ────────────────────────────────
    ms = [
        ("bayaran pendaftaran", 0.99, "payment", "ms", "SEA"),
        ("deposit keselamatan", 0.98, "payment", "ms", "SEA"),
        ("tiada pengalaman diperlukan", 0.80, "process", "ms", "SEA"),
        ("kerja dari rumah", 0.72, "remote_fraud", "ms", "SEA"),
        ("pendapatan tanpa had", 0.88, "unrealistic", "ms", "SEA"),
        ("jamin diterima kerja", 0.92, "guarantee", "ms", "SEA"),
        ("hubungi whatsapp sekarang", 0.90, "contact", "ms", "SEA"),
        ("bayar untuk mulakan", 0.97, "payment", "ms", "SEA"),
    ]
    phrases.extend(ms)

    # ── Filipino/Tagalog (Philippines) ─────────────────────────────────────
    tl = [
        ("bayad sa registration", 0.99, "payment", "tl", "PH"),
        ("walang kailangan na karanasan", 0.80, "process", "tl", "PH"),
        ("kumita ng malaki araw-araw", 0.88, "unrealistic", "tl", "PH"),
        ("guaranteed na makakapasok", 0.92, "guarantee", "tl", "PH"),
        ("mag-message sa whatsapp", 0.90, "contact", "tl", "PH"),
        ("deposit sa gcash", 0.96, "payment", "tl", "PH"),
    ]
    phrases.extend(tl)

    # ── French (West Africa / Europe) ──────────────────────────────────────
    fr = [
        ("frais d'inscription", 0.99, "payment", "fr", "global"),
        ("frais de dossier", 0.96, "payment", "fr", "global"),
        ("aucune expérience requise", 0.80, "process", "fr", "global"),
        ("emploi garanti", 0.93, "guarantee", "fr", "global"),
        ("contactez-nous sur whatsapp", 0.90, "contact", "fr", "global"),
        ("dépôt de garantie requis", 0.98, "payment", "fr", "global"),
        ("frais de visa", 0.95, "payment", "fr", "global"),
        ("revenus illimités", 0.88, "unrealistic", "fr", "global"),
    ]
    phrases.extend(fr)

    # ── Spanish (Latin America / Spain) ───────────────────────────────────
    es = [
        ("pago de inscripción", 0.99, "payment", "es", "global"),
        ("sin experiencia necesaria", 0.80, "process", "es", "global"),
        ("empleo garantizado", 0.93, "guarantee", "es", "global"),
        ("contactar por whatsapp", 0.90, "contact", "es", "global"),
        ("depósito de seguridad", 0.98, "payment", "es", "global"),
        ("sin entrevista", 0.92, "process", "es", "global"),
        ("ingresos ilimitados", 0.88, "unrealistic", "es", "global"),
        ("tarifa de procesamiento", 0.91, "payment", "es", "global"),
    ]
    phrases.extend(es)

    # ── Portuguese (Brazil) ────────────────────────────────────────────────
    pt = [
        ("taxa de cadastro", 0.99, "payment", "pt", "BR"),
        ("sem experiência necessária", 0.80, "process", "pt", "BR"),
        ("emprego garantido", 0.93, "guarantee", "pt", "BR"),
        ("contato pelo whatsapp", 0.90, "contact", "pt", "BR"),
        ("depósito de segurança", 0.98, "payment", "pt", "BR"),
        ("sem entrevista", 0.92, "process", "pt", "BR"),
        ("renda ilimitada", 0.88, "unrealistic", "pt", "BR"),
    ]
    phrases.extend(pt)

    df = pd.DataFrame(phrases, columns=["phrase", "weight", "category",
                                         "language", "region"])
    path = PROC / "scam_phrases_global.csv"
    df.to_csv(path, index=False)
    log.info(f"Global phrase dictionary: {len(phrases)} entries across "
             f"{df['language'].nunique()} languages, "
             f"{df['region'].nunique()} regions")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# L. Global Business Registry Routing Table
# ─────────────────────────────────────────────────────────────────────────────

def build_registry_routing_table() -> Path:
    """
    Maps country code to the correct national business registry.
    Used by the company verifier to route verification requests
    to the appropriate jurisdiction rather than defaulting to MCA21.
    """
    registries = [
        {"country": "IN", "name": "Ministry of Corporate Affairs (MCA21)",
         "endpoint": "https://www.mca.gov.in/mcafoportal/getSearchStringData.do",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".in", ".co.in"]},
        {"country": "GB", "name": "Companies House",
         "endpoint": "https://api.company-information.service.gov.uk/search/companies",
         "auth_required": True, "free": True,
         "env_key": "COMPANIES_HOUSE_API_KEY",
         "docs": "https://developer.company-information.service.gov.uk/",
         "tlds": [".co.uk", ".org.uk", ".me.uk"]},
        {"country": "US", "name": "SEC EDGAR",
         "endpoint": "https://efts.sec.gov/LATEST/search-index",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".us"]},
        {"country": "AU", "name": "ABN Lookup",
         "endpoint": "https://abr.business.gov.au/json/MatchingNames.aspx",
         "auth_required": True, "free": True,
         "env_key": "ABN_LOOKUP_GUID",
         "docs": "https://abr.business.gov.au/Tools/AbrWebServicesHub",
         "tlds": [".com.au", ".org.au", ".net.au"]},
        {"country": "CA", "name": "Corporations Canada",
         "endpoint": "https://ised-isde.canada.ca/cc/lgcy/fdrlCrpSrch.html",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".ca"]},
        {"country": "DE", "name": "Unternehmensregister",
         "endpoint": "https://www.unternehmensregister.de/ureg/result.html",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".de"]},
        {"country": "SG", "name": "ACRA BizFile+",
         "endpoint": "https://www.bizfile.gov.sg/",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".sg", ".com.sg"]},
        {"country": "AE", "name": "UAE Ministry of Economy",
         "endpoint": "https://services.moec.gov.ae/tradelicense",
         "auth_required": True, "free": False,
         "env_key": None, "tlds": [".ae", ".com.ae"]},
        {"country": "PH", "name": "SEC Philippines",
         "endpoint": "https://esearch.sec.gov.ph/",
         "auth_required": False, "free": True,
         "env_key": None, "tlds": [".ph", ".com.ph"]},
        {"country": "GLOBAL", "name": "OpenCorporates (200+ jurisdictions)",
         "endpoint": "https://api.opencorporates.com/v0.4/companies/search",
         "auth_required": True, "free": True,
         "env_key": "OPENCORPORATES_API_KEY",
         "free_tier_limit": "100 requests/month",
         "docs": "https://api.opencorporates.com/", "tlds": []},
    ]
    path = PROC / "global_registry_index.json"
    with open(path, "w") as f:
        json.dump(registries, f, indent=2)
    log.info(f"Registry routing table: {len(registries)} jurisdictions")
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Combine URL datasets and preprocess job postings
# ─────────────────────────────────────────────────────────────────────────────

def combine_url_datasets():
    frames = []

    def try_add(path: Path, loader):
        if path.exists():
            try:
                df = loader(path)
                if df is not None and len(df) > 0:
                    frames.append(df)
                    log.info(f"  {path.name}: {len(df):,} rows")
            except Exception as e:
                log.warning(f"  {path.name} failed: {e}")

    def load_csv_labels(p, url_col_hint="url", label_hint="label",
                         phishing_values=("phishing","1","malicious")):
        df = pd.read_csv(p, low_memory=False)
        uc = next((c for c in df.columns if url_col_hint in c.lower()), None)
        lc = next((c for c in df.columns
                   if any(k in c.lower() for k in
                          [label_hint, "phishing", "status", "class", "type"])), None)
        if uc and lc:
            out = df[[uc, lc]].rename(columns={uc: "url", lc: "label"})
            out["label"] = out["label"].map(
                lambda x: 1 if str(x).lower() in phishing_values else 0)
            return out[["url", "label"]]
        return None

    def load_urlhaus(p):
        df = pd.read_csv(p, comment="#", header=None,
                          on_bad_lines="skip",
                          names=["id","date","url","status","last","threat",
                                  "tags","link","reporter"])
        df = df[["url"]].dropna(); df["label"] = 1
        return df.sample(min(80000, len(df)), random_state=42)

    def load_openphish(p):
        urls = [l.strip() for l in open(p) if l.strip().startswith("http")]
        return pd.DataFrame({"url": urls, "label": 1})

    def load_majestic(p):
        df = pd.read_csv(p)
        dc = next((c for c in df.columns
                   if any(k in c.lower() for k in ["domain","url","host"])),
                  df.columns[1])
        out = df[[dc]].dropna().rename(columns={dc: "url"})
        out["url"] = "https://www." + out["url"].astype(str)
        out["label"] = 0
        return out.sample(min(150000, len(out)), random_state=42)

    try_add(RAW/"urls"/"PhiUSIIL.csv",                 load_csv_labels)
    try_add(RAW/"urls"/"urlhaus.csv",                  load_urlhaus)
    try_add(RAW/"urls"/"openphish.txt",                load_openphish)
    try_add(RAW/"urls"/"iscx_urls.csv",                load_csv_labels)
    try_add(RAW/"domains"/"majestic_million.csv",      load_majestic)
    try_add(RAW/"urls"/"global_job_url_patterns.csv",
            lambda p: pd.read_csv(p)[["url","label"]])

    if not frames:
        log.error("No URL datasets available. Re-run download step.")
        sys.exit(1)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["url","label"])
    combined = combined[combined["url"].str.startswith("http", na=False)]
    combined["label"] = combined["label"].astype(int)
    combined = combined.drop_duplicates(subset=["url"])
    combined = combined.sample(frac=1, random_state=42).reset_index(drop=True)

    log.info(f"Combined URL dataset: {len(combined):,} — "
             f"{(combined['label']==1).sum():,} fraud, "
             f"{(combined['label']==0).sum():,} legit")

    tr, temp = train_test_split(combined, test_size=0.20,
                                 stratify=combined["label"], random_state=42)
    va, te = train_test_split(temp, test_size=0.50,
                               stratify=temp["label"], random_state=42)
    tr.to_csv(PROC/"url_train.csv", index=False)
    va.to_csv(PROC/"url_val.csv",   index=False)
    te.to_csv(PROC/"url_test.csv",  index=False)
    log.info(f"URL splits: train={len(tr):,}, val={len(va):,}, test={len(te):,}")


def preprocess_jobs():
    candidates = [RAW/"jobs"/"fake_job_postings.csv",
                  RAW/"jobs"/"EMSCAD.csv"]
    df = None
    for c in candidates:
        if c.exists(): df = pd.read_csv(c).fillna(""); break
    if df is None: df = pd.read_csv(get_emscad()).fillna("")

    for col in ["fraudulent","fraud","label","is_fraud"]:
        if col in df.columns:
            df["label"] = df[col].astype(int); break

    for col in ["title","company_profile","description","requirements",
                "benefits","location","salary_range"]:
        if col not in df.columns: df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df["full_text"] = (
        "Title: " + df["title"] + " [SEP] " +
        "Company: " + df["company_profile"] + " [SEP] " +
        "Description: " + df["description"] + " [SEP] " +
        "Requirements: " + df["requirements"] + " [SEP] " +
        "Benefits: " + df["benefits"]
    ).str[:3000]

    df["short_text"]    = (df["title"] + " " + df["description"].str[:600])
    df["has_salary"]    = (df["salary_range"] != "").astype(int)
    df["has_logo"]      = df.get("has_company_logo", 0).fillna(0).astype(int)
    df["text_length"]   = df["full_text"].str.len()
    df["has_gmail"]     = df["full_text"].str.contains(
        r"@gmail|@yahoo|@rediff", regex=True, case=False).astype(int)
    df["has_whatsapp"]  = df["full_text"].str.contains(
        "whatsapp", case=False).astype(int)

    tr, temp = train_test_split(df, test_size=0.30,
                                 stratify=df["label"], random_state=42)
    va, te = train_test_split(temp, test_size=0.50,
                               stratify=temp["label"], random_state=42)
    tr.to_csv(PROC/"train.csv", index=False)
    va.to_csv(PROC/"val.csv",   index=False)
    te.to_csv(PROC/"test.csv",  index=False)
    log.info(f"Job splits: train={len(tr):,}, val={len(va):,}, test={len(te):,}")


if __name__ == "__main__":
    log.info("=" * 64)
    log.info("  TRUSTHIRE — WORLDWIDE DATASET DOWNLOAD")
    log.info("=" * 64)

    get_emscad()
    get_url_datasets()
    build_global_job_url_patterns()
    build_regional_fraud_patterns()
    build_multilingual_phrases()
    build_registry_routing_table()
    combine_url_datasets()
    preprocess_jobs()

    log.info("All datasets ready. Run: python scripts/train_all_models.py")
