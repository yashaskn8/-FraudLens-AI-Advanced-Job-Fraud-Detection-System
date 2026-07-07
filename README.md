# 🛡️ FraudLens-AI: Advanced Job Fraud Detection System

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=FFD62B)](https://vitejs.dev)

FraudLens-AI is a production-grade, end-to-end intelligent security platform that protects job seekers by scanning job listings across **7 distinct analysis signals**. It computes an aggregated **Trust Score (0–100)** and generates an AI-powered, plain-English explanation outlining exactly why a job posting is flagged or trusted.

---

## 🏗️ System Architecture

![FraudLens-AI System Architecture](docs/architecture.png)

FraudLens-AI is built around a high-performance **FastAPI backend** that routes job posting data through a multi-layer analysis pipeline combining rule-based heuristics, fine-tuned deep learning classifiers, and vector-similarity search. A **React/Tailwind CSS dashboard** provides full visibility into scan results, history, and analytics. A lightweight **Chrome Extension** enables one-click in-browser scanning directly on LinkedIn, Naukri, and Indeed.

---

## 🔍 The Multi-Signal Analysis Pipeline

FraudLens-AI evaluates job postings using a multi-signal analysis pipeline. While the UI and scorer group these into **3 primary Core Engines** for weight redistribution, the system processes **7 distinct signal categories** under the hood:

### 1. Primary Core Engines & Scorer Weights
The primary engines are configured in [`backend/config.py`](backend/config.py) and consolidated in the trust score fusion engine ([`backend/services/trust_scorer.py`](backend/services/trust_scorer.py)):

* **URL Analysis** (Configured base weight: **35%**) — Evaluates domain age, security certificates, registration records, and checks threat feeds.
* **NLP Classification** (Configured base weight: **30%**) — Classifies text using fine-tuned deep learning models and aggregates duplicate template searches and scam phrase dictionaries.
* **Company Verification** (Configured base weight: **25%**) — Validates the hiring entity against official registries and analyzes recruiter email domain legitimacy.

*Note: In the scorer settings, the remaining **10%** weight budget is allocated to supplementary signals (Duplicate Detection and Scam Phrases) which are processed inside the NLP Classification pipeline.*

---

## ⚙️ Trust Score Engine — How Scoring Works

The trust score is computed by [`backend/services/trust_scorer.py`](backend/services/trust_scorer.py) using a **dynamic weight redistribution** model. The key design principle is distinguishing between **signals with no data** (missing input — excluded neutrally) and **signals with active fraud evidence** (positively detected problems — penalised).

### Dynamic Weight Scaling
When a signal is excluded (e.g. no URL provided or no company details entered), its weight is proportionally redistributed across the remaining reliable signals. For instance, when all three primary engines are active, the base weight budget of `0.90` (35% + 30% + 25%) is scaled up to `1.00`:

* **URL Analysis:** 0.35 / 0.90 = **38.9%** effective weight
* **NLP Classification:** 0.30 / 0.90 = **33.3%** effective weight
* **Company Verification:** 0.25 / 0.90 = **27.8%** effective weight

### Three Safety Corrections
After the weighted average is calculated, three evidence-gated corrections are applied:

1. **Score Floor** — If any signal with active fraud evidence (i.e. has a verified penalty) scores below the weighted average by more than 20 points, the final score is capped at `lowest_fraud_signal + 20`. This correction is *not* applied when a low score comes from API unavailability or missing data.

2. **Multi-Warning Penalty** — If 2+ signals with active fraud evidence score below 35/100 (danger zone), a 40% penalty is applied (`score × 0.60`). Combinations of 1 danger + 2 warnings apply a 28% penalty. Two warnings without danger signals apply an 18% penalty.

3. **Red Flag Hard Cap** — If 2 or more high-severity flags are detected (e.g. "phishing", "malware", "registration fee", "IP address in URL", "known fraudulent"), the trust score is hard-capped at **48** regardless of other signal scores.

### Verdict Thresholds

| Trust Score | Verdict | Colour |
|:-----------:|---------|:------:|
| ≥ 70 | `SAFE` | 🟢 Green |
| 45 – 69 | `SUSPICIOUS` | 🟡 Yellow |
| 25 – 44 | `LIKELY_FRAUD` | 🟠 Orange |
| < 25 | `FRAUD` | 🔴 Red |

*Example calibration: A legitimate job with URL score=100, Company score=80, and NLP signal excluded computes as: (100×0.35 + 80×0.25) / (0.35+0.25) = **91.7 → SAFE***

---

## 🧠 NLP Classifier — Priority Chain

The NLP pipeline in [`backend/services/nlp_classifier.py`](backend/services/nlp_classifier.py) follows a strict priority chain to guarantee a score is always returned, regardless of model availability:

```
Priority 1: Fine-tuned DistilBERT
  → Requires: models/bert_fraud_classifier/final/ (trained by train_models.py)
  → Uses learned optimal threshold from model_info.json
  → Effective NLP weight: 100% of configured weight

Priority 2: TF-IDF + Logistic Regression Baseline
  → Requires: models/baseline/vectorizer.pkl + classifier.pkl
  → Effective NLP weight: 85% of configured weight

Priority 3: Structural Heuristics (always available, zero dependencies)
  → Rule-based scam phrase scoring + structural pattern analysis
  → Effective NLP weight: 70% of configured weight
```

The `model_source` field in every scan response indicates which tier was used (`bert_finetuned`, `baseline_xgb` (representing the TF-IDF baseline), or `heuristic`). On first startup, if no trained BERT model is found, the app **automatically launches background training** in a non-blocking daemon thread, keeping the API fully operational while BERT trains — and hot-swapping the model when training completes without requiring a restart.

---

## 🌐 URL Analyser — Sub-Signals

The URL analyser in [`backend/services/url_analyser.py`](backend/services/url_analyser.py) extracts and combines the following sub-signals into a single `url_trust_score`:

| Sub-Signal | Source |
|---|---|
| HTTPS & SSL certificate validity | Live socket probe |
| Domain age (days since registration) | WHOIS lookup |
| Registrar country | WHOIS |
| Free hosting provider detection | 23-domain blocklist (Wix, GitHub Pages, Netlify, etc.) |
| URL shortener detection | 12-provider blocklist (bit.ly, t.co, etc.) |
| Redirect chain length & final URL | HTTP follow-redirect trace |
| Google Safe Browsing lookup | External API (optional key) |
| VirusTotal malicious count | External API (optional key) |
| URL entropy (character randomness) | Shannon entropy calculation |
| IP address in URL | Regex detection |
| Random subdomain detection | Entropy threshold |
| Typosquatting against 17 major brands | Edit-distance fuzzy match |
| Suspicious TLD detection | `.tk`, `.ml`, `.ga`, `.xyz`, `.click`, and 18 others |
| Fraud keywords in URL path | 25-keyword dictionary |
| Live page content scan | HTML title, meta-description, scam keyword count, login form presence |
| XGBoost ML URL classifier | Trained on PhiUSIIL + URLHaus + ISCX datasets |

---

## 🏢 Company Verifier — Key Principles

The company verifier in [`backend/services/company_verifier.py`](backend/services/company_verifier.py) is built on one critical design principle:

> **Brand name presence in a domain is a RED FLAG — not a positive signal — unless the domain exactly matches the brand's registered root domain.**

The verifier maintains a **verified global employer whitelist** of 60+ exact root domains (e.g. `google.com`, `tcs.com`, `barclays.com`), grouped by region (India IT, Global Tech, UK, Australia, Canada, Germany, Singapore, UAE, Indian Startups, Job Boards, and ATS platforms). A domain like `google-career-verification.org` does **not** pass — it triggers a brand impersonation flag.

Verification checks performed:
- Exact root domain match against verified whitelist
- Career subdomain validation (`careers.`, `jobs.`, `hiring.`)
- Brand token impersonation detection across 50+ known brand tokens
- MX record presence check (does the domain have a mail server?)
- Domain active/live check via HTTP probe

---

## 🚦 Job Relevance Gate

Every scan request first passes through the **Job Relevance Gate** (`backend/services/job_relevance_detector.py`) before any fraud analysis begins. This pre-check determines whether the submitted URL or text is actually a job posting.

Detected types:
- `job_board` — URL is from a known job board (LinkedIn, Naukri, Indeed, etc.)
- `employer_career` — URL has a career subdomain on a legitimate employer domain
- `job_description` — Free text contains sufficient job-posting signals
- `not_job` — Input is not job-related (e.g. `gemini.google.com`, `chat.openai.com`, `bing.com`)
- `unknown` — Insufficient data to classify

If the gate classifies input as `not_job`, the scan returns `is_job_content: false` with a human-readable `rejection_reason` and actionable `suggestions` rather than running the full 7-signal pipeline.

---

## 🤖 LLM Explanation Engine

After scoring, FraudLens-AI generates a plain-English explanation using one of two LLM backends configured via the `LLM_PROVIDER` environment variable:

| Provider | Config | Notes |
|----------|:------:|-------|
| `ollama` (default) | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | Free, runs locally. Default model: `mistral`. |
| `openai` | `OPENAI_API_KEY` | Cloud-based, uses `gpt-4o-mini`. Higher quality. |
| Fallback | None | Rule-based explanation generated if both LLMs are unavailable. |

The explanation prompt instructs the model to write 3–4 flowing paragraphs (no bullet points) covering: what the overall verdict means, the 2–3 most significant red flags and why they matter, and specific actions the job seeker should take next. The model is instructed not to repeat raw flag text verbatim — it must translate technical signals into human terms.

---

## 📦 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend API** | Python 3.11, FastAPI, Uvicorn, SQLAlchemy, Alembic |
| **Async Tasks** | Celery, Redis Broker |
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide React |
| **ML / NLP** | DistilBERT (HuggingFace Transformers), Sentence-BERT, FAISS, PyTorch, Scikit-learn, XGBoost, LightGBM |
| **Database** | PostgreSQL (primary data store), SQLite (local dev) |
| **LLM Engine** | Ollama (Mistral-7B) / OpenAI GPT-4o-mini |
| **External APIs** | Google Safe Browsing, VirusTotal, WhoisXML |
| **Auth** | JWT (python-jose), bcrypt (passlib) |
| **Rate Limiting** | SlowAPI |

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
Ensure the following are installed on your system:
* **Python 3.11+**
* **Node.js v18+ & npm**
* **PostgreSQL** (running locally)
* **Redis** (running locally)

### Step 1 — Install Dependencies & Setup
Run the comprehensive setup script to install all Python and Node dependencies, configure the database, and download/train all ML models:

```bash
chmod +x setup.sh
./setup.sh
```

> **Note:** This runs Alembic migrations, downloads EMSCAD and supplementary fraud datasets from multiple sources, and trains the DistilBERT, SBERT+FAISS, URL, and baseline classifiers. Estimated time: 30–90 minutes depending on hardware.

### Step 2 — Configure Environment
Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys for Google Safe Browsing, VirusTotal, WhoisXML, and optionally OpenAI.

### Step 3 — Start Services (4 separate terminals)

**Terminal 1 — FastAPI Backend:**
```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Celery Worker:**
```bash
source venv/bin/activate
celery -A backend.celery_app worker --loglevel=info
```

**Terminal 3 — React Frontend:**
```bash
cd frontend
npm run dev
```

**Access Points:**
| Service | URL |
|---------|-----|
| React Dashboard | http://localhost:3000 |
| FastAPI Backend | http://localhost:8000 |
| Interactive API Docs | http://localhost:8000/docs |

---

## ⚡ Graceful Degradation

FraudLens-AI is designed to always produce a result, even with incomplete inputs or untrained models:

| Condition | Behaviour |
|-----------|----------|
| No URL provided | URL Analysis signal excluded; weight redistributed to remaining signals |
| No description provided | NLP signal marked `is_reliable=False` and excluded from score fusion |
| No company name provided | Company Verification excluded; zero impact on score |
| BERT not trained | Falls back to TF-IDF baseline (85% weight), then to heuristics (70% weight) |
| BERT model missing on startup | Background training launches automatically in a daemon thread |
| LLM (Ollama/OpenAI) unavailable | Rule-based fallback explanation is generated |
| VirusTotal / Safe Browsing API key missing | URL analyser runs without threat-intel (heuristic mode) |
| No reliable signals at all | Score defaults to 50 (`SUSPICIOUS`) with `confidence=0` |

---

## 🔑 Environment Variables

All configuration is managed via `.env` (copy from `.env.example`):

```env
# Database
DATABASE_URL=postgresql://trusthire_user:trusthire_pass@localhost/trusthire

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# External APIs (all optional — system degrades gracefully without them)
GOOGLE_SAFE_BROWSING_API_KEY=
VIRUSTOTAL_API_KEY=
WHOISXML_API_KEY=

# LLM Provider: "ollama" (default, free) or "openai"
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OPENAI_API_KEY=

# Security
SECRET_KEY=your-secret-key-change-in-production

# Rate Limits
RATE_LIMIT_FREE=10/minute
RATE_LIMIT_REGISTERED=60/minute
```

---

## 🔌 Chrome Extension Installation

Scan any job listing on LinkedIn, Naukri, or Indeed in one click:

1. Navigate to `chrome://extensions/` in your browser.
2. Enable **Developer mode** (toggle in the top-right corner).
3. Click **Load unpacked**.
4. Select the `chrome-extension/` directory from this project.
5. Click the FraudLens icon on any job listing page and hit **Scan Job**.

---

## 📡 API Reference

| Method | Endpoint | Auth | Description |
|:------:|:---------|:----:|:------------|
| `POST` | `/api/v1/scan` | Optional | Submit a job posting URL and/or description for trust evaluation. |
| `GET` | `/api/v1/scan/{id}` | No | Retrieve full signal breakdown and verdict for a scan by ID. |
| `GET` | `/api/v1/history` | Optional | Get paginated history of recent scans. |
| `POST` | `/api/v1/report` | Optional | Submit a community fraud report for a job posting. |
| `GET` | `/api/v1/reports` | No | Retrieve all community-submitted fraud reports. |
| `GET` | `/api/v1/analytics/dashboard` | No | Fetch aggregate analytics (scan counts, verdict distributions, top flags). |
| `POST` | `/api/v1/auth/register` | No | Register a new user account. |
| `POST` | `/api/v1/auth/login` | No | Authenticate and receive a JWT session token. |

### Sample Scan Request
```json
{
  "url": "https://careers.google.com/jobs/results/987654321",
  "description": "We are seeking a senior software architect for cloud systems...",
  "job_title": "Senior Cloud Architect",
  "company_name": "Google LLC",
  "recruiter_email": "hr@google.com"
}
```

### Sample Scan Response
```json
{
  "scan_id": "8f3b201a-8c7d-4bfa-9e32-c51d6f1a8c9b",
  "trust_score": 92,
  "verdict": "SAFE",
  "verdict_color": "green",
  "confidence": 0.95,
  "recommendation": "Strong signals found. Verified corporate email, official domain, high NLP confidence.",
  "flags": [],
  "signal_scores": {
    "URL Analysis": 95,
    "NLP Classification": 90,
    "Company Verification": 100,
    "Duplicate Detection": 92,
    "Email Validation": 100,
    "Consistency Check": 85,
    "Scam Phrases": 100
  },
  "explanation": "The posting originates from an official Google domain with active SSL and verified WHOIS credentials..."
}
```

---

## 📂 Complete Project Structure

```
FraudLens-AI/
│
├── .env.example                         # Environment variable template
├── .gitignore                           # Git exclusions (venv, data, models, db)
├── README.md                            # Project documentation
├── alembic.ini                          # Alembic database migration configuration
├── requirements.txt                     # Production Python dependencies
├── setup.sh                             # Full local environment setup script
├── trusthire.db                         # SQLite database (local dev only)
│
├── docs/
│   └── architecture.png                 # System architecture diagram
│
├── backend/                             # FastAPI Application
│   ├── __init__.py
│   ├── main.py                          # App entry point, router registration, CORS, startup
│   ├── config.py                        # Pydantic settings (env vars, signal weights, thresholds)
│   ├── database.py                      # SQLAlchemy engine and session factory
│   ├── middleware.py                    # Request logging and error handling middleware
│   ├── celery_app.py                    # Celery instance and broker configuration
│   │
│   ├── ml/                              # ML Model Loaders
│   │   ├── __init__.py
│   │   ├── bert_model.py                # DistilBERT inference loader and predictor
│   │   ├── baseline_model.py            # TF-IDF + Logistic Regression baseline inference
│   │   ├── sbert_faiss.py               # Sentence-BERT encoder + FAISS index search
│   │   └── constants.py                 # Shared label maps, threshold constants
│   │
│   ├── models/                          # SQLAlchemy Database Models
│   │   ├── __init__.py
│   │   └── job_scan.py                  # JobScan, Report, User ORM models
│   │
│   ├── routers/                         # API Route Controllers
│   │   ├── __init__.py
│   │   ├── scan.py                      # POST /scan, GET /scan/{id}
│   │   ├── auth.py                      # POST /auth/register, POST /auth/login
│   │   ├── reports.py                   # POST /report, GET /reports
│   │   └── analytics.py                 # GET /analytics/dashboard
│   │
│   ├── schemas/                         # Pydantic Request/Response Schemas
│   │   ├── __init__.py
│   │   └── scan.py                      # ScanRequest, ScanResponse, SignalScores schemas
│   │
│   ├── services/                        # Core Business Logic — 7 Signal Analysers
│   │   ├── __init__.py
│   │   ├── url_analyser.py              # Signal 1: URL heuristics, WHOIS, phishing DB lookup
│   │   ├── nlp_classifier.py            # Signal 2: DistilBERT inference wrapper
│   │   ├── company_verifier.py          # Signal 3: Registry lookup, domain/MX validation
│   │   ├── trust_scorer.py              # Signal 4: SBERT+FAISS duplicate detection + score aggregation
│   │   ├── consistency_checker.py       # Signal 6: Salary/title/experience consistency
│   │   ├── explainer.py                 # LLM-powered plain-English explanation generator
│   │   ├── job_relevance_detector.py    # Pre-check: confirms input is an actual job posting
│   │   └── url_cache.py                 # Redis-backed URL result caching layer
│   │
│   └── tasks/                           # Celery Async Background Tasks
│       ├── __init__.py
│       └── scan_tasks.py                # Async scan pipeline task definitions
│
├── frontend/                            # React Application (Vite + Tailwind CSS)
│   ├── index.html                       # HTML entry point
│   ├── package.json                     # npm dependencies and scripts
│   ├── package-lock.json
│   ├── postcss.config.js                # PostCSS configuration
│   ├── tailwind.config.js               # Tailwind CSS theme customization
│   ├── vite.config.js                   # Vite bundler configuration
│   │
│   ├── public/
│   │   └── vite.svg
│   │
│   └── src/
│       ├── main.jsx                     # React app bootstrap and router
│       ├── App.jsx                      # Root component with route definitions
│       ├── index.css                    # Global styles and Tailwind directives
│       │
│       ├── api/
│       │   └── client.js                # Axios API client with base URL and interceptors
│       │
│       ├── components/                  # Reusable UI Components
│       │   ├── Navbar.jsx               # Navigation bar with links and auth state
│       │   ├── ScanInput.jsx            # Job posting URL/text input form
│       │   ├── TrustScoreGauge.jsx      # Animated circular trust score meter
│       │   ├── SignalBreakdown.jsx      # Per-signal score bars with labels
│       │   ├── RedFlagsList.jsx         # Collapsible list of detected fraud flags
│       │   ├── ExplainerPanel.jsx       # LLM explanation display panel
│       │   ├── ScanHistory.jsx          # Paginated history table
│       │   ├── MagicCard.jsx            # Animated glassmorphism card component
│       │   ├── LoadingState.jsx         # Scanning animation / loading skeleton
│       │   ├── NotJobContentResult.jsx  # Result when input is not a job posting
│       │   └── ReportButton.jsx         # Community fraud report submission button
│       │
│       ├── hooks/
│       │   ├── useScan.js               # Custom hook: scan submission and state
│       │   └── useAnalytics.js          # Custom hook: dashboard analytics fetch
│       │
│       ├── pages/                       # Page-Level Route Components
│       │   ├── Home.jsx                 # Landing page with scan input
│       │   ├── Results.jsx              # Full scan result with signal breakdown
│       │   ├── Dashboard.jsx            # Analytics charts and aggregate metrics
│       │   ├── Reports.jsx              # Community fraud reports browser
│       │   └── About.jsx                # Project info and team page
│       │
│       └── styles/
│           └── tokens.css               # CSS design tokens (colors, spacing, typography)
│
├── chrome-extension/                    # Browser Extension
│   ├── manifest.json                    # Extension manifest (v3)
│   ├── background.js                    # Service worker — API communication
│   ├── content.js                       # Content script — extracts job data from page DOM
│   ├── icons/                           # Extension icons (16px, 48px, 128px)
│   └── popup/
│       ├── popup.html                   # Extension popup UI
│       ├── popup.css                    # Popup styles
│       └── popup.js                     # Popup interaction logic
│
├── scripts/                             # Data & Model Utilities
│   ├── download_data.py                 # Downloads EMSCAD dataset (Kaggle CLI + direct URL fallback + synthetic generation)
│   ├── download_datasets.py             # Downloads supplementary job fraud datasets
│   ├── download_all_datasets.py         # Orchestrates all dataset downloads in sequence
│   ├── download_global_datasets.py      # Downloads worldwide fraud report datasets (FTC, Action Fraud UK, ACCC)
│   ├── download_worldwide_datasets.py   # Extended global dataset download with multilingual sources
│   ├── train_models.py                  # Trains DistilBERT, SBERT+FAISS, and URL classifier
│   ├── train_all_models.py              # Full training pipeline for all model variants
│   ├── test_global_features.py          # Integration test runner for worldwide detection features
│   ├── full_setup.sh                    # Complete one-command setup: install + download + train
│   ├── install_all.sh                   # Installs all Python and frontend dependencies
│   ├── install_backend.sh               # Installs backend-only Python ML stack
│   └── install_worldwide.sh             # Installs worldwide/multilingual NLP dependencies
│
├── migrations/                          # Alembic Database Migrations
│   ├── env.py                           # Alembic migration environment configuration
│   ├── script.py.mako                   # Migration script template
│   └── versions/
│       └── 001_initial.py               # Initial schema: job_scans, reports, users tables
│
├── data/                                # Training Datasets (auto-generated by scripts)
│   ├── raw/
│   │   ├── fake_job_postings.csv        # EMSCAD dataset (18K labelled job postings)
│   │   ├── jobs/
│   │   │   └── fake_job_postings.csv
│   │   ├── urls/
│   │   │   ├── openphish.txt            # OpenPhish live phishing URL feed
│   │   │   ├── urlhaus.csv              # URLHaus malicious URL database
│   │   │   ├── urlhaus_recent.csv       # Recent URLHaus additions
│   │   │   ├── PhiUSIIL.csv             # PhiUSIIL phishing dataset
│   │   │   ├── iscx_urls.csv            # ISCX URL dataset
│   │   │   ├── job_url_patterns.csv     # Job-specific URL pattern analysis
│   │   │   └── global_job_url_patterns.csv
│   │   ├── domains/
│   │   │   ├── majestic_million.csv     # Majestic Million trusted domain whitelist
│   │   │   └── whitelist.csv            # Custom trusted domain whitelist
│   │   ├── fraud_reports/
│   │   │   ├── ftc_sentinel_job_fraud.csv    # FTC Sentinel job fraud reports (USA)
│   │   │   ├── action_fraud_uk.csv           # Action Fraud UK reports
│   │   │   ├── accc_scamwatch.csv            # ACCC Scamwatch reports (Australia)
│   │   │   └── regional_fraud_vocabulary.csv # Multilingual fraud vocabulary
│   │   └── multilingual/                # Multilingual job scam dataset (8 languages)
│   └── processed/
│       ├── train.csv                    # Training split for NLP classifier
│       ├── val.csv                      # Validation split for NLP classifier
│       ├── test.csv                     # Test split for NLP classifier
│       ├── url_train.csv                # URL classifier training split
│       ├── url_val.csv                  # URL classifier validation split
│       ├── url_test.csv                 # URL classifier test split
│       ├── scam_phrases.csv             # English scam phrase dictionary
│       ├── scam_phrases_global.csv      # Multilingual scam phrase dictionary
│       └── global_registry_index.json   # Company registry lookup index
│
└── models/                              # Trained Model Weights (auto-created by training scripts)
    ├── bert_fraud_classifier/
    │   ├── final/                       # Final trained DistilBERT model
    │   │   ├── config.json
    │   │   ├── model.safetensors        # Model weights (~265 MB)
    │   │   ├── tokenizer.json
    │   │   ├── tokenizer_config.json
    │   │   ├── training_args.bin
    │   │   └── model_info.json
    │   ├── checkpoint-313/              # Training checkpoint at step 313
    │   └── checkpoint-626/              # Training checkpoint at step 626
    ├── faiss_index/
    │   ├── fake_jobs.index              # FAISS index of fraud job embeddings
    │   ├── real_jobs.index              # FAISS index of legitimate job embeddings
    │   ├── metadata.json                # Index metadata (size, dimension)
    │   └── index_info.json
    ├── baseline/
    │   ├── classifier.pkl               # Logistic Regression baseline model
    │   ├── vectorizer.pkl               # TF-IDF feature vectorizer
    │   ├── scaler.pkl                   # Feature scaler
    │   └── features.json                # Feature list for inference
    └── url_classifier/
        ├── xgb_model.pkl                # XGBoost URL classifier
        ├── lgb_model.pkl                # LightGBM URL classifier
        ├── scaler.pkl                   # URL feature scaler
        ├── feature_names.json           # URL feature names
        └── model_info.json
```

---

## 📄 License & Disclaimer

Distributed under the **MIT License**.

> **Disclaimer:** FraudLens-AI is a decision support tool built for educational and research purposes. While it leverages state-of-the-art ML models and heuristics, it should be used as one factor in evaluating job postings and is not a guarantee of legitimacy or fraud.
