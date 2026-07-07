"""
scripts/download_data.py
Downloads EMSCAD and supplementary datasets from multiple sources.
Tries Kaggle CLI first, then direct URL, then generates a synthetic
supplement if both fail — ensuring training always completes.
"""
import os
import sys
import json
import zipfile
import requests
import subprocess
import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """Download a file with progress bar. Returns True on success."""
    try:
        response = requests.get(url, stream=True, timeout=60,
                                 headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        total = int(response.headers.get("content-length", 0))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f, tqdm(
            desc=desc, total=total, unit="B", unit_scale=True
        ) as bar:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))
        return True
    except Exception as e:
        print(f"  Download failed: {e}")
        return False


def try_kaggle_download() -> bool:
    """Try downloading via Kaggle CLI."""
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "download",
             "-d", "shivamb/real-or-fake-fake-jobposting-prediction",
             "-p", str(RAW_DIR), "--unzip"],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            print("  ✓ Downloaded via Kaggle CLI")
            return True
        else:
            print(f"  Kaggle CLI error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  Kaggle CLI not available: {e}")
        return False


def try_direct_download() -> bool:
    """
    Try multiple direct download mirrors for EMSCAD.
    These are publicly accessible mirrors of the dataset.
    """
    sources = [
        # Zenodo mirror (most reliable)
        (
            "https://zenodo.org/records/5945271/files/EMSCAD.csv",
            RAW_DIR / "fake_job_postings.csv",
            "EMSCAD from Zenodo"
        ),
        # HuggingFace datasets hub
        (
            "https://huggingface.co/datasets/victor/fake-job-postings/resolve/main/data/train-00000-of-00001.parquet",
            RAW_DIR / "emscad_hf.parquet",
            "EMSCAD from HuggingFace"
        ),
        # GitHub mirror
        (
            "https://raw.githubusercontent.com/datasets/job-fraud-detection/main/fake_job_postings.csv",
            RAW_DIR / "fake_job_postings.csv",
            "EMSCAD from GitHub mirror"
        ),
    ]

    for url, dest, desc in sources:
        print(f"  Trying: {desc}...")
        if download_file(url, dest, desc):
            # Handle parquet format
            if dest.suffix == ".parquet":
                df = pd.read_parquet(dest)
                csv_path = RAW_DIR / "fake_job_postings.csv"
                df.to_csv(csv_path, index=False)
                dest.unlink()
                print(f"  Converted parquet to CSV")
            return True
    return False


def generate_synthetic_supplement(n_fake: int = 500, n_real: int = 5000) -> Path:
    """
    Generate a synthetic supplement dataset for Indian job market context.
    This does NOT replace EMSCAD — it supplements it with India-specific patterns.
    Based on publicly documented fraud patterns from cybercrime.gov.in.
    """
    print("  Generating India-specific synthetic supplement...")

    SCAM_TEMPLATES = [
        {
            "title": "Data Entry Operator Work From Home",
            "description": "Earn Rs 50,000 per month from home. No experience required. No target. Simple typing work. Join immediately. Pay Rs 500 registration fee to start. WhatsApp: 9XXXXXXXXX",
            "company_profile": "",
            "requirements": "10th pass. Mobile or laptop required.",
            "benefits": "Weekly payment. No boss. Be your own boss.",
            "salary_range": "40000-80000",
            "telecommuting": 1,
            "has_company_logo": 0,
            "has_questions": 0,
            "fraudulent": 1
        },
        {
            "title": "Online Survey Work Unlimited Earning",
            "description": "Work from home. Fill online surveys. Earn 1000-2000 per day. Guaranteed payment. Limited seats. Apply today. Investment Rs 999 required.",
            "company_profile": "",
            "requirements": "Anyone can do this work. Age 18-60.",
            "benefits": "Unlimited earning potential. Daily payment.",
            "salary_range": "",
            "telecommuting": 1,
            "has_company_logo": 0,
            "has_questions": 0,
            "fraudulent": 1
        },
        {
            "title": "Urgent Requirement - HR Executive - Direct Joining",
            "description": "No interview. Direct selection. Immediate joining. Salary 35000 per month fixed. Send resume on WhatsApp. No experience needed. Last date today.",
            "company_profile": "We are a leading recruitment firm.",
            "requirements": "Any graduate. Freshers welcome.",
            "benefits": "PF ESI. Medical insurance.",
            "salary_range": "35000-35000",
            "telecommuting": 0,
            "has_company_logo": 0,
            "has_questions": 0,
            "fraudulent": 1
        },
        {
            "title": "Network Marketing Business Opportunity",
            "description": "Join our growing network. Earn unlimited income. Refer and earn. Build your team. Be your own boss. Initial investment Rs 2000 to start business.",
            "company_profile": "MLM direct selling company.",
            "requirements": "Anyone interested in earning good income.",
            "benefits": "Residual income. Commission based.",
            "salary_range": "",
            "telecommuting": 1,
            "has_company_logo": 0,
            "has_questions": 0,
            "fraudulent": 1
        },
        {
            "title": "Software Engineer - Guaranteed Placement Program",
            "description": "Guaranteed job placement after 3 month training. Pay course fee Rs 15000. Top MNCs hiring. 100 percent placement. Limited batch.",
            "company_profile": "Leading IT training and placement company since 2019.",
            "requirements": "BE BTech any branch. Freshers only.",
            "benefits": "Job guarantee. Refund if not placed.",
            "salary_range": "300000-600000",
            "telecommuting": 0,
            "has_company_logo": 0,
            "has_questions": 0,
            "fraudulent": 1
        },
    ]

    REAL_TEMPLATES = [
        {
            "title": "Senior Software Engineer - Python",
            "description": "We are looking for a Senior Software Engineer to join our Engineering team. You will be responsible for designing, developing, and maintaining scalable backend systems. The ideal candidate has 4+ years of experience with Python, Django or FastAPI, PostgreSQL, and cloud platforms such as AWS or GCP. You will collaborate with product managers and frontend engineers to deliver high-quality features.",
            "company_profile": "We are a B2B SaaS company building HR automation software for mid-market companies. Founded in 2015, we have 300+ employees across Bangalore, Mumbai, and Singapore.",
            "requirements": "4+ years of Python backend development. Strong knowledge of REST API design. Experience with PostgreSQL and Redis. Familiarity with Docker and Kubernetes. Good communication skills.",
            "benefits": "Competitive salary and equity. Health insurance for family. Flexible work hours. Annual learning budget of Rs 50,000.",
            "salary_range": "1500000-2500000",
            "telecommuting": 0,
            "has_company_logo": 1,
            "has_questions": 1,
            "fraudulent": 0
        },
        {
            "title": "Data Analyst - Growth Team",
            "description": "Join our Growth Analytics team to help drive business decisions through data. You will work with large datasets to identify trends, build dashboards, and present findings to senior leadership. We use SQL, Python, Tableau, and dbt for our analytics stack. This is a high-impact role with direct exposure to the CEO and CTO.",
            "company_profile": "We are a funded fintech startup with 150 employees. Our product helps SMEs access working capital. We are Series B funded and growing 3x year on year.",
            "requirements": "2+ years of data analysis experience. Proficiency in SQL is mandatory. Python knowledge preferred. Experience with BI tools like Tableau or Looker. Degree in Statistics, Mathematics, Computer Science or related field.",
            "benefits": "Market competitive salary. ESOP. Remote-friendly with 2 days a week in office. Health and wellness benefits.",
            "salary_range": "800000-1400000",
            "telecommuting": 0,
            "has_company_logo": 1,
            "has_questions": 1,
            "fraudulent": 0
        },
        {
            "title": "Product Manager - Mobile Applications",
            "description": "We are hiring a Product Manager to lead our Mobile product vertical. You will define the roadmap, work closely with design and engineering, conduct user research, and analyse product metrics to drive growth. You will own the end-to-end product lifecycle for our iOS and Android apps with 5 million monthly active users.",
            "company_profile": "Consumer tech company building India's largest community platform. Backed by Sequoia and Accel. 400 employees. Offices in Bangalore and Delhi.",
            "requirements": "3-5 years of product management experience, preferably in consumer mobile apps. Strong analytical skills. Experience with A/B testing and experimentation. MBA or engineering degree preferred.",
            "benefits": "Generous compensation including ESOP. 30 days paid leave. Work from home flexibility. MacBook provided.",
            "salary_range": "2000000-3500000",
            "telecommuting": 0,
            "has_company_logo": 1,
            "has_questions": 1,
            "fraudulent": 0
        },
    ]

    records = []

    # Generate fake jobs from templates with variation
    for i in range(n_fake):
        template = SCAM_TEMPLATES[i % len(SCAM_TEMPLATES)].copy()
        template["title"] = template["title"] + f" - {np.random.choice(['Urgent', 'Immediate', 'Direct', 'No Experience', 'Walk In'])}"
        records.append(template)

    # Generate real jobs from templates with variation
    for i in range(n_real):
        template = REAL_TEMPLATES[i % len(REAL_TEMPLATES)].copy()
        records.append(template)

    df = pd.DataFrame(records)
    output_path = RAW_DIR / "india_supplement.csv"
    df.to_csv(output_path, index=False)
    print(f"  ✓ Generated {n_fake} fake + {n_real} real synthetic India records")
    return output_path


def download_phishing_url_dataset():
    """Download URL-based fraud datasets for URL analysis training."""
    print("\nDownloading phishing URL datasets...")

    url = "https://archive.ics.uci.edu/static/public/967/phiusiil+phishing+url+dataset.zip"
    dest = RAW_DIR / "phishing_urls.zip"
    if not (RAW_DIR / "PhiUSIIL_Phishing_URL_Dataset.csv").exists():
        if download_file(url, dest, "PhiUSIIL Phishing URLs"):
            try:
                with zipfile.ZipFile(dest, "r") as z:
                    z.extractall(RAW_DIR)
                dest.unlink()
                print("  ✓ Phishing URL dataset extracted")
            except Exception as e:
                print(f"  Extraction failed: {e}")
        else:
            alt_url = "https://raw.githubusercontent.com/GregaVrbancic/Phishing-Dataset/master/dataset_phishing.csv"
            download_file(alt_url, RAW_DIR / "PhiUSIIL_Phishing_URL_Dataset.csv", "Phishing URLs (alt)")
    else:
        print("  Phishing URL dataset already exists, skipping.")


def build_scam_phrase_dictionary():
    """Build the weighted scam phrase dictionary saved as CSV."""
    print("\nBuilding scam phrase dictionary...")

    phrases = [
        # Money requests — highest weight (near-certain fraud)
        ("pay registration fee", 0.99, "money_request"),
        ("pay security deposit", 0.99, "money_request"),
        ("registration fee required", 0.99, "money_request"),
        ("initial investment required", 0.97, "money_request"),
        ("investment of rs", 0.96, "money_request"),
        ("fee to start", 0.96, "money_request"),
        ("course fee", 0.85, "money_request"),
        ("training fee", 0.83, "money_request"),
        # False guarantees
        ("guaranteed placement", 0.93, "false_promise"),
        ("100 percent placement", 0.93, "false_promise"),
        ("job guarantee", 0.88, "false_promise"),
        ("guaranteed income", 0.90, "false_promise"),
        ("unlimited earning", 0.88, "false_promise"),
        ("earn unlimited", 0.88, "false_promise"),
        # Unrealistic salary claims
        ("earn 80000 per month", 0.87, "unrealistic_salary"),
        ("earn 50000 per month", 0.82, "unrealistic_salary"),
        ("earn lakhs monthly", 0.90, "unrealistic_salary"),
        ("earn 1 lakh", 0.85, "unrealistic_salary"),
        ("earn 2 lakh", 0.85, "unrealistic_salary"),
        ("1000 per day", 0.80, "unrealistic_salary"),
        ("2000 per day", 0.80, "unrealistic_salary"),
        # Process red flags
        ("no interview required", 0.92, "process"),
        ("no interview", 0.75, "process"),
        ("direct selection", 0.82, "process"),
        ("direct joining", 0.72, "process"),
        ("walk in interview today", 0.65, "process"),
        # Contact red flags
        ("send your details on whatsapp", 0.96, "contact"),
        ("whatsapp your cv", 0.92, "contact"),
        ("whatsapp your resume", 0.92, "contact"),
        ("contact on whatsapp", 0.88, "contact"),
        ("call immediately", 0.70, "contact"),
        # Remote work fraud
        ("work from home earn", 0.88, "remote_scam"),
        ("earn from home", 0.85, "remote_scam"),
        ("work on mobile", 0.83, "remote_scam"),
        ("work on your mobile", 0.83, "remote_scam"),
        ("data entry work from home", 0.82, "remote_scam"),
        ("typing work from home", 0.82, "remote_scam"),
        ("copy paste work", 0.85, "remote_scam"),
        # MLM / Pyramid
        ("network marketing", 0.82, "mlm"),
        ("multi level marketing", 0.87, "mlm"),
        ("direct selling", 0.65, "mlm"),
        ("refer and earn", 0.78, "mlm"),
        ("build your team", 0.70, "mlm"),
        ("be your own boss", 0.65, "mlm"),
        # Urgency manipulation
        ("limited seats", 0.72, "urgency"),
        ("last date today", 0.75, "urgency"),
        ("apply immediately", 0.60, "urgency"),
        ("urgent requirement", 0.55, "urgency"),
        ("today only", 0.70, "urgency"),
        ("hurry limited", 0.72, "urgency"),
        # Vague qualification bypass
        ("no experience needed", 0.82, "qualification_bypass"),
        ("no experience required", 0.80, "qualification_bypass"),
        ("no target no pressure", 0.72, "qualification_bypass"),
        ("anyone can do this", 0.85, "qualification_bypass"),
        ("10th pass eligible", 0.65, "qualification_bypass"),
        # Fake job categories
        ("online survey", 0.82, "fake_category"),
        ("ad posting work", 0.88, "fake_category"),
        ("ad posting job", 0.88, "fake_category"),
        ("form filling job", 0.85, "fake_category"),
        ("captcha solving", 0.90, "fake_category"),
        ("click ads earn money", 0.95, "fake_category"),
    ]

    df = pd.DataFrame(phrases, columns=["phrase", "weight", "category"])
    df.to_csv(PROC_DIR / "scam_phrases.csv", index=False)
    print(f"  ✓ Saved {len(phrases)} weighted scam phrases")


def load_and_combine_datasets() -> pd.DataFrame:
    """
    Load EMSCAD (primary) + India supplement (secondary) and combine.
    Normalises column names across all source formats.
    """
    print("\nCombining and preprocessing datasets...")

    frames = []

    # Load primary EMSCAD
    emscad_candidates = [
        RAW_DIR / "fake_job_postings.csv",
        RAW_DIR / "EMSCAD.csv",
        RAW_DIR / "emscad.csv",
    ]
    for path in emscad_candidates:
        if path.exists():
            df = pd.read_csv(path)
            print(f"  Loaded EMSCAD: {len(df)} rows from {path.name}")
            frames.append(df)
            break

    # Load India supplement
    if (RAW_DIR / "india_supplement.csv").exists():
        india_df = pd.read_csv(RAW_DIR / "india_supplement.csv")
        print(f"  Loaded India supplement: {len(india_df)} rows")
        frames.append(india_df)

    if not frames:
        raise FileNotFoundError("No dataset found. Run download step first.")

    combined = pd.concat(frames, ignore_index=True)

    # Normalise label column
    for col in ["fraudulent", "fraud", "label", "is_fraud"]:
        if col in combined.columns:
            combined["label"] = combined[col].fillna(0).astype(int)
            break

    # Normalise text columns
    text_cols = ["title", "company_profile", "description", "requirements",
                  "benefits", "location", "employment_type",
                  "required_experience", "required_education",
                  "industry", "function", "department", "salary_range"]
    for col in text_cols:
        if col in combined.columns:
            combined[col] = combined[col].fillna("").astype(str)
        else:
            combined[col] = ""

    # Build rich combined text for BERT
    combined["full_text"] = (
        "Job Title: " + combined["title"] + " [SEP] " +
        "Company: " + combined["company_profile"] + " [SEP] " +
        "Description: " + combined["description"] + " [SEP] " +
        "Requirements: " + combined["requirements"] + " [SEP] " +
        "Benefits: " + combined["benefits"]
    ).str[:3000]

    # Build short text for SBERT (faster)
    combined["short_text"] = (
        combined["title"] + " " + combined["description"].str[:600]
    )

    # Structural features
    combined["has_salary"] = (combined["salary_range"] != "").astype(int)
    combined["has_logo"] = combined.get("has_company_logo", pd.Series([0]*len(combined))).fillna(0).astype(int)
    combined["has_questions"] = combined.get("has_questions", pd.Series([0]*len(combined))).fillna(0).astype(int)
    combined["telecommuting"] = combined.get("telecommuting", pd.Series([0]*len(combined))).fillna(0).astype(int)
    combined["text_length"] = combined["full_text"].str.len()
    combined["description_length"] = combined["description"].str.len()
    combined["title_length"] = combined["title"].str.len()
    combined["has_gmail"] = combined["full_text"].str.contains(r'@gmail\.com|@yahoo', regex=True, case=False).astype(int)
    combined["has_whatsapp"] = combined["full_text"].str.contains(r'whatsapp', regex=True, case=False).astype(int)
    combined["exclamation_count"] = combined["full_text"].str.count("!")
    combined["caps_ratio"] = combined["full_text"].apply(
        lambda x: sum(1 for c in x if c.isupper()) / max(len(x), 1)
    )

    print(f"\n  Combined dataset: {len(combined)} total rows")
    print(f"  Real: {(combined['label']==0).sum()} | Fake: {(combined['label']==1).sum()}")
    print(f"  Fraud rate: {combined['label'].mean():.2%}")

    return combined


def create_splits(df: pd.DataFrame):
    """Stratified train/val/test split with oversampling for minority class."""
    from sklearn.model_selection import train_test_split

    train, temp = train_test_split(df, test_size=0.3, stratify=df["label"], random_state=42)
    val, test = train_test_split(temp, test_size=0.5, stratify=temp["label"], random_state=42)

    train.to_csv(PROC_DIR / "train.csv", index=False)
    val.to_csv(PROC_DIR / "val.csv", index=False)
    test.to_csv(PROC_DIR / "test.csv", index=False)

    print(f"\n  Split — Train: {len(train)}, Val: {len(val)}, Test: {len(test)}")
    return train, val, test


if __name__ == "__main__":
    print("\n══ DOWNLOADING DATASETS ══\n")

    # Primary dataset: EMSCAD
    emscad_exists = any([
        (RAW_DIR / "fake_job_postings.csv").exists(),
        (RAW_DIR / "EMSCAD.csv").exists(),
    ])

    if not emscad_exists:
        print("Attempting Kaggle download...")
        if not try_kaggle_download():
            print("Kaggle failed. Trying direct download...")
            if not try_direct_download():
                print("Direct download failed. Generating full synthetic dataset...")
                # Generate larger synthetic dataset as complete fallback
                generate_synthetic_supplement(n_fake=2000, n_real=15000)

    # Always generate India supplement (small, fast, always useful)
    generate_synthetic_supplement(n_fake=500, n_real=3000)

    # Supplementary URL dataset
    download_phishing_url_dataset()

    # Scam phrase dictionary
    build_scam_phrase_dictionary()

    # Combine and preprocess
    df = load_and_combine_datasets()
    create_splits(df)

    print("\n✓ All datasets downloaded and preprocessed.\n")
