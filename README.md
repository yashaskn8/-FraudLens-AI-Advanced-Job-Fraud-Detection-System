# 🛡️ FraudLens-AI: Advanced Job Fraud Detection System

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)](https://pytorch.org)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=for-the-badge&logo=vite&logoColor=FFD62B)](https://vitejs.dev)

FraudLens-AI is a production-grade, end-to-end intelligent security system that protects job seekers by scanning job listings across **7 distinct analysis signals**. It computes an aggregated **Trust Score (0–100)** and generates an AI-powered plain-English explanation outlining exactly why a job posting is flagged or trusted.

---

## 🏗️ System Architecture

FraudLens-AI consists of a **FastAPI backend** processing data through deep learning and rule-based pipelines, a **React/Tailwind CSS frontend dashboard**, and a **Chrome Extension** for real-time scanning on job boards (LinkedIn, Naukri, Indeed, etc.).

```
                          ┌────────────────────────┐
                          │   Chrome Extension     │
                          └───────────┬────────────┘
                                      │ (Scan API)
                                      ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   React UI   │────▶│  FastAPI API  │────▶│  PostgreSQL  │
│  (Tailwind)  │     │  (Python 3.11)│     │  (Scan Logs) │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │DistilBERT│   │SBERT+FAISS│   │  Ollama  │
      │Classifier│   │ Similarity│   │  (LLM)   │
      └──────────┘   └──────────┘   └──────────┘
```

---

## 🔍 The 7-Signal Verification Engine

FraudLens-AI evaluates job postings using a multi-layered analysis pipeline. Scores are dynamically weighted based on signal availability:

| # | Signal | Base Weight | Description |
|---|--------|-------------|-------------|
| **1** | **URL Analysis** | 20% | Domain age, SSL details, WHOIS records, redirect chains, and lookup against known phishing databases. |
| **2** | **NLP Classification** | 25% | A DistilBERT model fine-tuned on 18,000+ job listings to classify scam vs. legitimate descriptions. |
| **3** | **Company Verification** | 20% | Validation against government registries (e.g., India's MCA21), active domain checks, and MX record presence. |
| **4** | **Duplicate Detection** | 15% | Uses Sentence-BERT embeddings paired with a local FAISS index to find highly similar or reposted scam templates. |
| **5** | **Email Validation** | 10% | Scoring contact addresses based on generic vs. corporate domains, checking matching domain records. |
| **6** | **Consistency Check** | 5% | Cross-checks specified salaries, job titles, and experience requirements against statistical norms. |
| **7** | **Scam Phrases** | 5% | Scan for high-frequency patterns, weighted keywords, and suspicious language layouts. |

---

## 📦 Tech Stack

* **Backend:** Python 3.11, FastAPI, SQLAlchemy, Alembic, Celery
* **Frontend:** React 18, Vite, Tailwind CSS, Lucide React, Recharts
* **Machine Learning & Indexing:** DistilBERT, Sentence-BERT, FAISS, PyTorch, Scikit-learn
* **Database & Queue:** PostgreSQL (data storage), Redis (Celery broker)
* **LLM Engine:** Ollama (Mistral-7B) / OpenAI GPT-4o-mini (for natural language explanation)

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
Make sure you have the following installed on your host system:
* Python 3.11+
* Node.js & npm (v18+)
* PostgreSQL & Redis Server

### Step 1: Install Dependencies & Run Setup
Run the main setup script to prepare the virtual environment, install python libraries, setup the database, and download/train the model components:

```bash
# Give execution permissions (on Linux/Mac)
chmod +x setup.sh

# Run the setup script
./setup.sh
```

> [!NOTE]
> The setup script will automatically download the required datasets, initialize your local database migrations via Alembic, and trigger the training process for the ML classifiers.

### Step 2: Start PostgreSQL and Redis
Ensure your local PostgreSQL database and Redis servers are running:
```bash
# Example (Linux)
sudo service postgresql start
sudo service redis-server start
```

### Step 3: Run the FastAPI Backend
Activate the virtual environment and start the uvicorn API server:
```bash
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```
The API documentation will be available at: http://localhost:8000/docs

### Step 4: Start the Celery Worker (In a separate terminal)
Activate the virtual environment and start Celery to process backend tasks asynchronously:
```bash
source venv/bin/activate
celery -A backend.celery_app worker --loglevel=info
```

### Step 5: Start the Frontend UI (In a separate terminal)
Navigate to the frontend directory and start the Vite dev server:
```bash
cd frontend
npm run dev
```
The React dashboard will be accessible at: http://localhost:3000

---

## 🔌 Chrome Extension Integration

Instantly scan job listings directly on LinkedIn, Naukri, or Indeed:

1. Open your browser and navigate to `chrome://extensions/`
2. Turn on **Developer mode** (top-right toggle switch).
3. Click on **Load unpacked** in the top left.
4. Select the `chrome-extension/` directory from this project workspace.
5. Open any job board, click the FraudLens icon, and hit **Scan Job**!

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|:---|:---|:---|
| `POST` | `/api/v1/scan` | Submits a job description and/or URL for trust evaluation. |
| `GET` | `/api/v1/scan/{id}` | Fetches detailed signal scores and verdicts for a specific scan ID. |
| `GET` | `/api/v1/history` | Retrieves a historical feed of recent job scans. |
| `POST` | `/api/v1/report` | Enables community reporting of newly encountered scams. |
| `GET` | `/api/v1/reports` | Retrieves user-reported scams database. |
| `GET` | `/api/v1/analytics/dashboard` | Fetches aggregate system-wide analytics. |
| `POST` | `/api/v1/auth/register` | Registers a new user. |
| `POST` | `/api/v1/auth/login` | Logins user and generates JWT session tokens. |

### Sample Scan Request (`POST /api/v1/scan`)
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
  "recommendation": "Strong signals found. Verified corporate email, official domain registration, and high consistency scores.",
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
  "explanation": "The posting originates from an official Google domain with active SSL and verified WHOIS credentials. The description matches standards, and recruiter's corporate address is validated against registered DNS records."
}
```

---

## 📂 Project Directory Structure

```
FraudLens-AI/
├── backend/            # FastAPI Application & Celery Setup
│   ├── main.py         # App Entry Point & Middleware
│   ├── config.py       # Pydantic Settings Schema
│   ├── services/       # 7-Signal Analysers & Score Engine
│   ├── routers/        # API Routers & Controllers
│   ├── models/         # SQLAlchemy DB Models
│   ├── schemas/        # Pydantic Schemas for Validation
│   ├── ml/             # ML Loaders and Transformers
│   └── tasks/          # Celery Async Background Tasks
├── frontend/           # React App (Vite + Tailwind)
│   └── src/
│       ├── pages/      # Dashboard, Scan Logs, Submissions, About
│       ├── components/ # Reusable UI Components
│       └── api/        # Axios API Client Modules
├── chrome-extension/   # Chrome Extension Source Files
├── scripts/            # Model Training and Dataset Utilities
├── models/             # Trained Weights (BERT, SBERT, FAISS Index)
├── data/               # Raw and Processed Kaggle/Scraped Data
└── requirements.txt    # Production Python Requirements
```

---

## 📄 License & Disclaimer

Distributed under the MIT License. See `LICENSE` for more information.

*Disclaimer: FraudLens-AI is a decision support tool built for educational and research purposes. While it leverages advanced ML, it is not a guarantee of job security or legitimacy.*
