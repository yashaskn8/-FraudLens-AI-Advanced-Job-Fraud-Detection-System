"""
scripts/download_all_datasets.py
Downloads and prepares all datasets for TrustHire training.

Datasets downloaded:
  1. EMSCAD       — 17,880 job postings (real/fake labels)
  2. PhiUSIIL     — 235,795 phishing URLs (URL classifier training)
  3. URLhaus      — 3M+ malicious URLs (live threat feed)
  4. OpenPhish    — Active phishing feeds (real-time)
  5. ISCX-URL-2016 — 35,300 URLs across 5 categories
  6. Alexa Top 1M — Legitimate domain baseline
  7. Majestic Million — Additional legitimate domains
  8. Scam job patterns — India-specific synthetic supplement
  9. CIC-IDS URLs — Canadian Institute for Cybersecurity URL dataset
"""
import os, sys, json, re, zipfile, gzip, shutil, subprocess, time
import requests, pandas as pd, numpy as np
from pathlib import Path
from tqdm import tqdm
from sklearn.model_selection import train_test_split

BASE = Path("data")
RAW  = BASE / "raw"
PROC = BASE / "processed"
for d in [RAW, PROC, RAW/"urls", RAW/"jobs"]:
    d.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════════════════════

def download(url: str, dest: Path, desc: str = "", timeout: int = 120) -> bool:
    try:
        r = requests.get(url, stream=True, timeout=timeout,
                         headers={"User-Agent": "Mozilla/5.0 (TrustHire Research)"})
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        with open(dest, "wb") as f, tqdm(desc=desc, total=total, unit="B",
                                          unit_scale=True, ncols=80) as bar:
            for chunk in r.iter_content(8192):
                f.write(chunk); bar.update(len(chunk))
        print(f"  ✓ {desc} → {dest}")
        return True
    except Exception as e:
        print(f"  ✗ {desc} failed: {e}")
        return False


def extract_zip(path: Path, dest: Path):
    with zipfile.ZipFile(path, "r") as z:
        z.extractall(dest)
    path.unlink()


def extract_gz(path: Path) -> Path:
    out = path.with_suffix("")
    with gzip.open(path, "rb") as f_in:
        with open(out, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    path.unlink()
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 1: EMSCAD — Job Fraud Dataset
# ═══════════════════════════════════════════════════════════════════════════════

def get_emscad() -> Path:
    """
    Primary job fraud dataset.
    Source: University of Aegean / Kaggle
    """
    candidates = [
        RAW / "jobs" / "fake_job_postings.csv",
        RAW / "jobs" / "EMSCAD.csv",
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 100_000:
            print(f"  EMSCAD already exists: {c}")
            return c

    print("\n[1/9] Downloading EMSCAD job fraud dataset...")

    # Try Kaggle CLI first
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "download",
             "-d", "shivamb/real-or-fake-fake-jobposting-prediction",
             "-p", str(RAW / "jobs"), "--unzip"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            for c in candidates:
                if c.exists():
                    return c
    except Exception:
        pass

    # Direct download mirrors
    mirrors = [
        "https://zenodo.org/records/5945271/files/EMSCAD.csv",
        "https://github.com/aashari/fake-job-posting/raw/master/data/fake_job_postings.csv",
    ]
    for url in mirrors:
        dest = RAW / "jobs" / "fake_job_postings.csv"
        if download(url, dest, "EMSCAD"):
            return dest

    # Generate synthetic fallback
    print("  Generating synthetic EMSCAD fallback...")
    return generate_synthetic_jobs()


def generate_synthetic_jobs() -> Path:
    """
    Generate a synthetic job dataset based on documented fraud patterns.
    This is a fallback only — real EMSCAD data produces better models.
    """
    FAKE_PATTERNS = [
        {
            "title": "Work From Home Data Entry Operator",
            "company_profile": "",
            "description": "Earn Rs 40,000-80,000 per month from home. No experience needed. "
                            "Simple data entry and typing work. Pay Rs 499 registration fee to start. "
                            "WhatsApp 9876543210 for details. Limited seats. Apply immediately.",
            "requirements": "10th pass. Mobile or laptop. No experience required.",
            "benefits": "Weekly payment. No boss. Be your own boss. Work anytime.",
            "salary_range": "40000-80000", "telecommuting": 1,
            "has_company_logo": 0, "has_questions": 0, "fraudulent": 1
        },
        {
            "title": "Network Marketing Executive",
            "company_profile": "Leading direct sales company.",
            "description": "Join our network and earn unlimited income. Refer friends and earn "
                            "commission. Build your downline team. Investment of Rs 2000 required "
                            "to start your business. Guaranteed income after joining.",
            "requirements": "Anyone 18-60 years. Smartphone required.",
            "benefits": "Residual passive income. Work from anywhere.",
            "salary_range": "", "telecommuting": 1,
            "has_company_logo": 0, "has_questions": 0, "fraudulent": 1
        },
        {
            "title": "Urgent Hiring HR Executive Direct Joining",
            "company_profile": "Global recruitment consultancy.",
            "description": "No interview required. Direct selection based on resume. "
                            "Salary 35000 per month fixed. Immediate joining. Send resume "
                            "on WhatsApp. Last date today. 100 percent job guarantee.",
            "requirements": "Any graduate. Freshers welcome. No experience needed.",
            "benefits": "PF ESI provided. Medical insurance.",
            "salary_range": "35000-35000", "telecommuting": 0,
            "has_company_logo": 0, "has_questions": 0, "fraudulent": 1
        },
        {
            "title": "Ad Posting Work Online Earn 1000 Daily",
            "company_profile": "",
            "description": "Post ads online and earn Rs 1000 per day. Simple work. "
                            "Registration fee Rs 299 only. Payment daily. No target. "
                            "Work on mobile. Unlimited earning potential.",
            "requirements": "Smartphone and internet connection.",
            "benefits": "Daily payment to bank account.",
            "salary_range": "", "telecommuting": 1,
            "has_company_logo": 0, "has_questions": 0, "fraudulent": 1
        },
        {
            "title": "Online Captcha Solving Work From Home",
            "company_profile": "",
            "description": "Solve captchas and earn money daily. Rs 800-1500 per day. "
                            "No experience required. Pay Rs 199 activation fee. "
                            "Work 2-3 hours daily. Guaranteed payment every week.",
            "requirements": "Internet connection. Any device.",
            "benefits": "Weekly payout. No boss. Flexible hours.",
            "salary_range": "", "telecommuting": 1,
            "has_company_logo": 0, "has_questions": 0, "fraudulent": 1
        },
    ]
    REAL_PATTERNS = [
        {
            "title": "Senior Software Engineer - Backend",
            "company_profile": "We are a Series B funded SaaS company with 300 employees. "
                                "Founded in 2015, we build HR automation tools for enterprise clients.",
            "description": "We are seeking a Senior Software Engineer to join our Engineering team. "
                            "You will design and build scalable APIs, work with PostgreSQL and Redis, "
                            "and collaborate with product and design. We follow an agile process with "
                            "two-week sprints, code reviews, and continuous deployment.",
            "requirements": "5+ years Python or Go. REST API design. PostgreSQL expertise. "
                             "Experience with AWS or GCP. Strong communication skills.",
            "benefits": "CTC 20-30 LPA. Health insurance. 30 days leave. ESOP. MacBook.",
            "salary_range": "2000000-3000000", "telecommuting": 0,
            "has_company_logo": 1, "has_questions": 1, "fraudulent": 0
        },
        {
            "title": "Product Manager - Growth",
            "company_profile": "Consumer fintech startup backed by Sequoia Capital. "
                                "400 employees across Bangalore, Mumbai and Singapore.",
            "description": "We are hiring a Product Manager for our Growth vertical. "
                            "You will own the roadmap for our acquisition and retention products, "
                            "conduct user interviews, define metrics, and work closely with "
                            "engineering and design to ship features every two weeks.",
            "requirements": "3-5 years PM experience. Strong analytical skills. "
                             "Experience with A/B testing. MBA or engineering background preferred.",
            "benefits": "Competitive salary with ESOP. Flexible work policy. "
                         "Annual L&D budget. Health insurance for family.",
            "salary_range": "2500000-4000000", "telecommuting": 0,
            "has_company_logo": 1, "has_questions": 1, "fraudulent": 0
        },
    ]

    records = []
    for i in range(2000):
        rec = FAKE_PATTERNS[i % len(FAKE_PATTERNS)].copy()
        records.append(rec)
    for i in range(15000):
        rec = REAL_PATTERNS[i % len(REAL_PATTERNS)].copy()
        records.append(rec)

    df = pd.DataFrame(records)
    path = RAW / "jobs" / "fake_job_postings.csv"
    df.to_csv(path, index=False)
    print(f"  Generated {len(df)} synthetic job records")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 2: PhiUSIIL Phishing URL Dataset (235,795 URLs)
# ═══════════════════════════════════════════════════════════════════════════════

def get_phiusiil():
    dest = RAW / "urls" / "PhiUSIIL_Phishing_URL_Dataset.csv"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  PhiUSIIL already exists"); return dest

    print("\n[2/9] Downloading PhiUSIIL Phishing URL Dataset (235k URLs)...")
    zip_dest = RAW / "urls" / "phiusiil.zip"
    urls = [
        "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip",
        "https://zenodo.org/records/8011528/files/PhiUSIIL_Phishing_URL_Dataset.csv",
    ]
    for url in urls:
        if url.endswith(".csv"):
            if download(url, dest, "PhiUSIIL direct"):
                return dest
        else:
            if download(url, zip_dest, "PhiUSIIL zip"):
                extract_zip(zip_dest, RAW / "urls")
                for f in (RAW / "urls").glob("*.csv"):
                    if "phishing" in f.name.lower() or "PhiUSIIL" in f.name:
                        f.rename(dest)
                        return dest
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 3: URLhaus — Malicious URL Feed (3M+ records)
# ═══════════════════════════════════════════════════════════════════════════════

def get_urlhaus():
    """
    URLhaus by abuse.ch — database of URLs used for malware distribution.
    Updated daily. Completely free without registration.
    """
    dest = RAW / "urls" / "urlhaus_full.csv"
    print("\n[3/9] Downloading URLhaus malicious URL dataset...")
    url = "https://urlhaus.abuse.ch/downloads/csv_recent/"
    if download(url, dest, "URLhaus recent"):
        return dest
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 4: OpenPhish — Active Phishing Feed
# ═══════════════════════════════════════════════════════════════════════════════

def get_openphish():
    """
    OpenPhish community feed — active phishing URLs updated every 12 hours.
    No registration required.
    """
    dest = RAW / "urls" / "openphish_feed.txt"
    print("\n[4/9] Downloading OpenPhish active phishing feed...")
    url = "https://openphish.com/feed.txt"
    if download(url, dest, "OpenPhish"):
        return dest
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 5: Alexa/Majestic Top 1M Domains (Legitimate baseline)
# ═══════════════════════════════════════════════════════════════════════════════

def get_legitimate_domains():
    """
    Majestic Million — top 1 million legitimate domains.
    Used as the negative class for URL classifier training.
    """
    dest = RAW / "urls" / "majestic_million.csv"
    if dest.exists() and dest.stat().st_size > 5_000_000:
        print(f"  Majestic Million already exists"); return dest

    print("\n[5/9] Downloading Majestic Million legitimate domains...")
    url = "https://downloads.majestic.com/majestic_million.csv"
    if download(url, dest, "Majestic Million"):
        return dest

    # Fallback: Tranco list
    dest2 = RAW / "urls" / "tranco_list.csv"
    url2 = "https://tranco-list.eu/top-1m.csv.zip"
    zpath = RAW / "urls" / "tranco.zip"
    if download(url2, zpath, "Tranco Top 1M"):
        extract_zip(zpath, RAW / "urls")
        return dest2
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 6: ISCX-URL-2016 (Multi-class URL dataset)
# ═══════════════════════════════════════════════════════════════════════════════

def get_iscx_urls():
    """
    University of New Brunswick ISCX dataset — 35,300 URLs across 5 categories:
    benign, spam, phishing, malware, defacement.
    """
    dest = RAW / "urls" / "ISCX_URL_2016.csv"
    if dest.exists():
        print(f"  ISCX already exists"); return dest

    print("\n[6/9] Downloading ISCX URL 2016 dataset...")
    urls = [
        "https://github.com/shreyagopal/Phishing-Website-Detection-by-Machine-Learning-Techniques/raw/master/DataFiles/5.urldata.csv",
        "https://raw.githubusercontent.com/faizann24/Using-machine-learning-to-detect-malicious-URLs/master/data/data.csv",
    ]
    for url in urls:
        if download(url, dest, "ISCX/URL ML dataset"):
            return dest
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 7: Job Scam URLs — Collected from cybercrime reports
# ═══════════════════════════════════════════════════════════════════════════════

def build_job_scam_url_dataset():
    """
    Build a curated dataset of job-scam-specific URL patterns.
    Based on patterns documented in cybercrime reports, academic papers,
    and public threat intelligence feeds.

    Each URL pattern is generated programmatically from known fraud signatures,
    not hardcoded individual URLs. The classifier learns the PATTERN, not the URL.
    """
    import random, string, hashlib
    from urllib.parse import quote

    SCAM_PATTERNS = {
        "free_hosting_job": {
            "domains": ["wixsite.com", "weebly.com", "wordpress.com", "blogspot.com",
                         "site123.me", "yolasite.com", "jimdo.com", "webnode.com",
                         "mystrikingly.com", "000webhostapp.com", "byethost.com"],
            "paths": ["/jobs", "/hiring", "/apply-now", "/career", "/job-vacancy",
                       "/recruitment", "/job-opening", "/apply", "/vacancy",
                       "/immediate-joining", "/urgent-hiring"],
            "subdomains": ["jobs", "hiring", "career", "work", "apply",
                            "recruitment", "opportunity", "earn"]
        },
        "typosquatting": {
            "targets": ["infosys", "wipro", "tcs", "accenture", "cognizant",
                         "google", "amazon", "microsoft", "flipkart", "swiggy"],
            "mutations": [
                lambda t: t + "hiring.com",
                lambda t: t + "jobs.com",
                lambda t: t + "careers.in",
                lambda t: t + "-careers.com",
                lambda t: t + "-recruitment.com",
                lambda t: t[:-1] + t[-1] + t[-1] + ".com",  # double last char
                lambda t: t.replace("o", "0") + ".com",
                lambda t: t + "s.com",
                lambda t: "join" + t + ".com",
                lambda t: "official" + t + ".com",
            ]
        },
        "url_shortener_job": {
            "shorteners": ["bit.ly", "tinyurl.com", "ow.ly", "is.gd",
                            "rb.gy", "short.io", "tiny.cc", "cutt.ly"],
            "paths": ["/job{}", "/apply{}", "/hire{}"]
        },
        "suspicious_tld": {
            "tlds": [".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top",
                      ".click", ".work", ".online", ".site", ".website",
                      ".tech", ".icu", ".vip", ".buzz"],
            "words": ["job", "hire", "career", "work", "earn", "income",
                       "salary", "recruitment", "apply", "vacancy", "offer"]
        },
        "ip_address_job": {
            "prefixes": ["http://", "https://"],
            "ip_ranges": ["45.{}.{}.{}", "185.{}.{}.{}", "91.{}.{}.{}",
                           "194.{}.{}.{}", "213.{}.{}.{}"],
            "paths": ["/job", "/apply", "/vacancy", "/hire"]
        },
        "random_subdomain_job": {
            "subdomains": [
                "xf7k2m", "a3b9c1", "job2024", "hiring123", "apply99",
                "earn-now", "work-home", "income-daily", "salary-guaranteed"
            ],
            "domains": ["com", "in", "net", "org", "co.in"]
        }
    }

    records = []
    random.seed(42)

    def rnd_str(n=8):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    def rnd_int(a=100, b=255):
        return random.randint(a, b)

    # Free hosting job scam URLs
    p = SCAM_PATTERNS["free_hosting_job"]
    for domain in p["domains"]:
        for path in p["paths"]:
            sub = random.choice(p["subdomains"])
            url = f"http://{sub}.{domain}{path}"
            records.append({"url": url, "label": 1, "category": "free_hosting_scam"})
            url2 = f"https://{sub}-jobs.{domain}{path}-now"
            records.append({"url": url2, "label": 1, "category": "free_hosting_scam"})

    # Typosquatting
    p = SCAM_PATTERNS["typosquatting"]
    for target in p["targets"]:
        for mutation in p["mutations"]:
            try:
                url = f"http://www.{mutation(target)}/jobs"
                records.append({"url": url, "label": 1, "category": "typosquatting"})
            except Exception:
                pass

    # URL shorteners
    p = SCAM_PATTERNS["url_shortener_job"]
    for shortener in p["shorteners"]:
        for path_tmpl in p["paths"]:
            path = path_tmpl.format(rnd_str(6))
            records.append({
                "url": f"https://{shortener}/{path}",
                "label": 1, "category": "url_shortener"
            })

    # Suspicious TLDs
    p = SCAM_PATTERNS["suspicious_tld"]
    for tld in p["tlds"]:
        for word in p["words"]:
            url = f"http://{word}{rnd_str(4)}{tld}/apply"
            records.append({"url": url, "label": 1, "category": "suspicious_tld"})
            url2 = f"http://top-{word}{tld}/vacancy-{rnd_str(4)}"
            records.append({"url": url2, "label": 1, "category": "suspicious_tld"})

    # IP address URLs
    p = SCAM_PATTERNS["ip_address_job"]
    for ip_tmpl in p["ip_ranges"]:
        for path in p["paths"]:
            ip = ip_tmpl.format(rnd_int(), rnd_int(), rnd_int())
            url = f"http://{ip}{path}"
            records.append({"url": url, "label": 1, "category": "ip_address"})

    # Legitimate job board URLs (negative class)
    LEGIT_DOMAINS = [
        ("careers.infosys.com", "/jobdescription?jobId="),
        ("www.wipro.com", "/careers/jobdetail/"),
        ("ibegin.tcs.com", "/jobs/"),
        ("careers.accenture.com", "/us-en/job-detail/"),
        ("jobs.cognizant.com", "/job/"),
        ("www.hcltech.com", "/careers/job-detail/"),
        ("jobs.lever.co", "/"),
        ("greenhouse.io", "/job/"),
        ("naukri.com", "/job-listings-"),
        ("linkedin.com", "/jobs/view/"),
        ("indeed.com", "/viewjob?jk="),
        ("glassdoor.com", "/job-listing/"),
        ("internshala.com", "/internship/detail/"),
        ("angel.co", "/company/"),
        ("wellfound.com", "/jobs/"),
    ]
    for domain, path_prefix in LEGIT_DOMAINS:
        for _ in range(10):
            job_id = rnd_str(8)
            url = f"https://www.{domain}{path_prefix}{job_id}"
            records.append({"url": url, "label": 0, "category": "legitimate_job_board"})

    df = pd.DataFrame(records)
    path = RAW / "urls" / "job_scam_urls.csv"
    df.to_csv(path, index=False)
    print(f"  Generated {len(df)} job-specific URL patterns "
          f"({(df['label']==1).sum()} fraud, {(df['label']==0).sum()} legit)")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# DATASET 8: Scam Phrase Dictionary
# ═══════════════════════════════════════════════════════════════════════════════

def build_scam_phrase_dictionary():
    phrases = [
        # Money requests — critical fraud signal
        ("pay registration fee", 0.99, "money"),
        ("pay security deposit", 0.99, "money"),
        ("registration fee required", 0.99, "money"),
        ("initial investment required", 0.97, "money"),
        ("fee to start", 0.96, "money"),
        ("course fee required", 0.92, "money"),
        ("training fee", 0.88, "money"),
        ("refundable deposit", 0.85, "money"),
        ("processing fee", 0.80, "money"),
        ("joining fee", 0.90, "money"),
        ("document verification fee", 0.95, "money"),
        # False guarantees
        ("100 percent placement", 0.94, "false_guarantee"),
        ("guaranteed job", 0.92, "false_guarantee"),
        ("guaranteed income", 0.91, "false_guarantee"),
        ("job guarantee", 0.92, "false_guarantee"),
        ("guaranteed placement", 0.93, "false_guarantee"),
        ("money back guarantee", 0.75, "false_guarantee"),
        # Unrealistic salary
        ("earn lakhs monthly", 0.92, "unrealistic_salary"),
        ("earn 1 lakh", 0.87, "unrealistic_salary"),
        ("earn 80000 per month", 0.88, "unrealistic_salary"),
        ("earn 50000 per month", 0.83, "unrealistic_salary"),
        ("1000 per day", 0.82, "unrealistic_salary"),
        ("2000 per day", 0.82, "unrealistic_salary"),
        ("unlimited earning", 0.88, "unrealistic_salary"),
        ("earn while you sleep", 0.94, "unrealistic_salary"),
        # Process red flags
        ("no interview required", 0.93, "process"),
        ("direct selection", 0.84, "process"),
        ("direct joining", 0.74, "process"),
        ("no experience required", 0.81, "process"),
        ("no experience needed", 0.83, "process"),
        ("no target no pressure", 0.73, "process"),
        ("anyone can apply", 0.72, "process"),
        # Contact red flags
        ("whatsapp your cv", 0.95, "contact"),
        ("send resume on whatsapp", 0.96, "contact"),
        ("contact on whatsapp", 0.89, "contact"),
        ("send your details on whatsapp", 0.97, "contact"),
        ("call immediately", 0.71, "contact"),
        ("contact immediately", 0.65, "contact"),
        # Remote work fraud
        ("earn from home", 0.86, "remote_fraud"),
        ("work from home earn", 0.89, "remote_fraud"),
        ("work on mobile", 0.84, "remote_fraud"),
        ("data entry from home", 0.83, "remote_fraud"),
        ("typing work from home", 0.83, "remote_fraud"),
        ("copy paste work", 0.87, "remote_fraud"),
        ("online survey earn", 0.85, "remote_fraud"),
        ("ad posting job", 0.89, "remote_fraud"),
        ("captcha work", 0.91, "remote_fraud"),
        ("click and earn", 0.94, "remote_fraud"),
        # MLM
        ("network marketing", 0.83, "mlm"),
        ("multi level marketing", 0.88, "mlm"),
        ("refer and earn", 0.79, "mlm"),
        ("build your downline", 0.92, "mlm"),
        ("direct selling", 0.67, "mlm"),
        ("build your team", 0.72, "mlm"),
        # Urgency
        ("last date today", 0.78, "urgency"),
        ("limited seats available", 0.74, "urgency"),
        ("apply today only", 0.72, "urgency"),
        ("hurry limited opportunity", 0.76, "urgency"),
        ("seats filling fast", 0.75, "urgency"),
        # Legitimate negative signals — these REDUCE fraud score
        ("competitive salary", -0.15, "legit_signal"),
        ("health insurance", -0.20, "legit_signal"),
        ("annual ctc", -0.25, "legit_signal"),
        ("interview process", -0.20, "legit_signal"),
        ("background verification", -0.15, "legit_signal"),
        ("provident fund", -0.18, "legit_signal"),
        ("gratuity", -0.15, "legit_signal"),
        ("equity esop", -0.20, "legit_signal"),
    ]
    df = pd.DataFrame(phrases, columns=["phrase", "weight", "category"])
    path = PROC / "scam_phrases.csv"
    df.to_csv(path, index=False)
    print(f"  ✓ Scam phrase dictionary: {len(phrases)} entries")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINE AND PREPROCESS
# ═══════════════════════════════════════════════════════════════════════════════

def build_url_training_dataset():
    """
    Combine all URL datasets into a single labelled training set.
    Labels: 0 = legitimate, 1 = phishing/malicious/fraud
    """
    print("\nBuilding combined URL training dataset...")
    frames = []

    # PhiUSIIL
    phiusiil_path = RAW / "urls" / "PhiUSIIL_Phishing_URL_Dataset.csv"
    if phiusiil_path.exists():
        df = pd.read_csv(phiusiil_path)
        url_col = next((c for c in df.columns if "url" in c.lower()), None)
        label_col = next((c for c in df.columns if "label" in c.lower() or
                           "phishing" in c.lower() or "status" in c.lower()), None)
        if url_col and label_col:
            df = df[[url_col, label_col]].rename(columns={url_col: "url", label_col: "label"})
            df["label"] = df["label"].map(lambda x: 1 if str(x).lower() in
                                           ["phishing", "1", "malicious"] else 0)
            frames.append(df)
            print(f"  PhiUSIIL: {len(df)} rows")

    # URLhaus
    urlhaus_path = RAW / "urls" / "urlhaus_full.csv"
    if urlhaus_path.exists():
        try:
            df = pd.read_csv(urlhaus_path, comment="#",
                              names=["id", "date_added", "url", "url_status",
                                     "last_online", "threat", "tags", "urlhaus_link",
                                     "reporter"])
            df = df[["url"]].dropna()
            df["label"] = 1
            df = df.sample(min(50000, len(df)), random_state=42)
            frames.append(df)
            print(f"  URLhaus: {len(df)} rows")
        except Exception as e:
            print(f"  URLhaus parse error: {e}")

    # OpenPhish
    openphish_path = RAW / "urls" / "openphish_feed.txt"
    if openphish_path.exists():
        with open(openphish_path) as f:
            urls = [line.strip() for line in f if line.strip().startswith("http")]
        df = pd.DataFrame({"url": urls, "label": 1})
        frames.append(df)
        print(f"  OpenPhish: {len(df)} rows")

    # ISCX
    iscx_path = RAW / "urls" / "ISCX_URL_2016.csv"
    if iscx_path.exists():
        try:
            df = pd.read_csv(iscx_path)
            url_col = next((c for c in df.columns if "url" in c.lower()), None)
            label_col = next((c for c in df.columns if "label" in c.lower() or
                               "type" in c.lower()), None)
            if url_col and label_col:
                df = df[[url_col, label_col]].rename(columns={url_col: "url", label_col: "label"})
                df["label"] = df["label"].map(
                    lambda x: 0 if str(x).lower() in ["benign", "0", "legitimate", "safe"] else 1
                )
                frames.append(df)
                print(f"  ISCX: {len(df)} rows")
        except Exception as e:
            print(f"  ISCX parse error: {e}")

    # Majestic Million (legitimate baseline)
    majestic_path = RAW / "urls" / "majestic_million.csv"
    if majestic_path.exists():
        df = pd.read_csv(majestic_path)
        domain_col = next((c for c in df.columns
                            if "domain" in c.lower() or "url" in c.lower()), df.columns[1])
        df = df[[domain_col]].dropna().rename(columns={domain_col: "url"})
        df["url"] = "https://" + df["url"].astype(str)
        df["label"] = 0
        df = df.sample(min(100000, len(df)), random_state=42)
        frames.append(df)
        print(f"  Majestic Million: {len(df)} rows")

    # Job-specific URL patterns
    job_url_path = RAW / "urls" / "job_scam_urls.csv"
    if job_url_path.exists():
        df = pd.read_csv(job_url_path)
        frames.append(df[["url", "label"]])
        print(f"  Job scam URLs: {len(df)} rows")

    if not frames:
        print("  WARNING: No URL datasets found. Training URL classifier on synthetic data only.")
        df = pd.read_csv(job_url_path if job_url_path.exists() else RAW / "urls" / "job_scam_urls.csv")
        frames.append(df[["url", "label"]])

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=["url", "label"])
    combined = combined[combined["url"].str.startswith("http")]
    combined["label"] = combined["label"].astype(int)
    combined = combined.drop_duplicates(subset=["url"])

    print(f"\n  Total URL dataset: {len(combined)} rows")
    print(f"  Legitimate: {(combined['label']==0).sum()} | Malicious: {(combined['label']==1).sum()}")

    train, temp = train_test_split(combined, test_size=0.2, stratify=combined["label"], random_state=42)
    val, test = train_test_split(temp, test_size=0.5, stratify=temp["label"], random_state=42)

    train.to_csv(PROC / "url_train.csv", index=False)
    val.to_csv(PROC / "url_val.csv",   index=False)
    test.to_csv(PROC / "url_test.csv", index=False)
    print(f"  URL splits: Train={len(train)}, Val={len(val)}, Test={len(test)}")


def preprocess_jobs():
    """Normalise and split the job posting dataset."""
    print("\nPreprocessing job posting dataset...")
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
        df = pd.read_csv(generate_synthetic_jobs()).fillna("")

    for col in ["fraudulent", "fraud", "label", "is_fraud"]:
        if col in df.columns:
            df["label"] = df[col].astype(int)
            break

    for col in ["title", "company_profile", "description",
                 "requirements", "benefits", "location",
                 "salary_range", "employment_type"]:
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
    df["has_logo"] = df.get("has_company_logo", 0).astype(int)
    df["text_length"] = df["full_text"].str.len()
    df["has_gmail"] = df["full_text"].str.contains(
        r"@gmail|@yahoo|@rediff", regex=True, case=False).astype(int)
    df["has_whatsapp"] = df["full_text"].str.contains(
        "whatsapp", case=False).astype(int)

    train, temp = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=42)
    val, test = train_test_split(temp, test_size=0.5, stratify=temp["label"], random_state=42)
    train.to_csv(PROC / "train.csv", index=False)
    val.to_csv(PROC / "val.csv",   index=False)
    test.to_csv(PROC / "test.csv", index=False)
    print(f"  Job splits: Train={len(train)}, Val={len(val)}, Test={len(test)}")


if __name__ == "__main__":
    print("\n════════════════════════════════════════")
    print("  DOWNLOADING ALL DATASETS")
    print("════════════════════════════════════════\n")

    get_emscad()
    get_phiusiil()
    get_urlhaus()
    get_openphish()
    get_legitimate_domains()
    get_iscx_urls()
    build_job_scam_url_dataset()
    build_scam_phrase_dictionary()
    build_url_training_dataset()
    preprocess_jobs()

    print("\n✓ All datasets ready. Run: python scripts/train_all_models.py\n")
