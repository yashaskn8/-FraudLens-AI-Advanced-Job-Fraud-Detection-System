#!/bin/bash
set -e  # Exit on any error

echo ""
echo "════════════════════════════════════════════════════════"
echo "  TRUSTHIRE — FULL SETUP & MODEL TRAINING"
echo "  This script will install dependencies and train BERT."
echo "  Estimated time: 30–90 minutes depending on hardware."
echo "════════════════════════════════════════════════════════"
echo ""

# ── Step 1: System packages ───────────────────────────────────────────────────
echo "[1/9] Installing system packages..."
if command -v apt-get &> /dev/null; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq \
        python3.11 python3.11-pip python3.11-venv \
        postgresql postgresql-contrib redis-server \
        nodejs npm git curl wget unzip \
        build-essential libpq-dev libssl-dev \
        chromium-browser chromium-chromedriver \
        tesseract-ocr libmagic1
elif command -v brew &> /dev/null; then
    brew install python@3.11 postgresql redis node
fi

# ── Step 2: Python virtual environment ───────────────────────────────────────
echo "[2/9] Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel

# ── Step 3: Python packages — ALL required ────────────────────────────────────
echo "[3/9] Installing Python packages..."
pip install \
    fastapi==0.111.0 \
    uvicorn[standard]==0.29.0 \
    gunicorn==22.0.0 \
    pydantic==2.7.1 \
    pydantic-settings==2.2.1 \
    sqlalchemy==2.0.30 \
    alembic==1.13.1 \
    psycopg2-binary==2.9.9 \
    celery==5.4.0 \
    redis==5.0.4 \
    httpx==0.27.0 \
    aiohttp==3.9.5 \
    beautifulsoup4==4.12.3 \
    playwright==1.44.0 \
    lxml==5.2.2 \
    python-whois==0.9.4 \
    python-jose[cryptography]==3.3.0 \
    passlib[bcrypt]==1.7.4 \
    python-multipart==0.0.9 \
    python-dotenv==1.0.1 \
    slowapi==0.1.9 \
    sentry-sdk[fastapi]==2.5.1 \
    torch==2.3.0 \
    torchvision==0.18.0 \
    transformers==4.41.1 \
    tokenizers==0.19.1 \
    datasets==2.19.2 \
    accelerate==0.30.0 \
    evaluate==0.4.2 \
    sentence-transformers==3.0.0 \
    faiss-cpu==1.8.0 \
    scikit-learn==1.5.0 \
    scipy==1.13.1 \
    pandas==2.2.2 \
    numpy==1.26.4 \
    spacy==3.7.4 \
    mlflow==2.13.0 \
    wandb==0.17.0 \
    scrapy==2.11.2 \
    streamlit==1.35.0 \
    plotly==5.22.0 \
    requests==2.32.3 \
    tqdm==4.66.4 \
    joblib==1.4.2 \
    optuna==3.6.1 \
    shap==0.45.1 \
    imbalanced-learn==0.12.3 \
    langdetect==1.0.9

# ── Step 4: spaCy language models ────────────────────────────────────────────
echo "[4/9] Downloading spaCy language models..."
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_md  # Better NER for company names

# ── Step 5: Playwright browsers ───────────────────────────────────────────────
echo "[5/9] Installing Playwright browsers..."
playwright install chromium
playwright install-deps chromium

# ── Step 6: Node.js frontend dependencies ─────────────────────────────────────
echo "[6/9] Installing frontend dependencies..."
cd frontend
npm install \
    react@18.3.1 \
    react-dom@18.3.1 \
    react-router-dom@6.23.1 \
    axios@1.7.2 \
    @tanstack/react-query@5.40.0 \
    lucide-react@0.383.0 \
    recharts@2.12.7 \
    tailwindcss@3.4.4 \
    @tailwindcss/forms@0.5.7 \
    autoprefixer@10.4.19 \
    postcss@8.4.38 \
    vite@5.2.13 \
    @vitejs/plugin-react@4.3.1 \
    framer-motion@11.2.10 \
    react-hot-toast@2.4.1 \
    clsx@2.1.1
cd ..

# ── Step 7: Database setup ─────────────────────────────────────────────────────
echo "[7/9] Setting up PostgreSQL database..."
sudo service postgresql start 2>/dev/null || true
sudo -u postgres psql -c "DROP DATABASE IF EXISTS trusthire;" 2>/dev/null || true
sudo -u postgres psql -c "DROP USER IF EXISTS trusthire_user;" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE trusthire;"
sudo -u postgres psql -c "CREATE USER trusthire_user WITH PASSWORD 'trusthire_pass';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trusthire TO trusthire_user;"

# Copy .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit API keys if needed."
fi

# Run migrations
alembic upgrade head

# ── Step 8: Download datasets ─────────────────────────────────────────────────
echo "[8/9] Downloading training datasets..."
python scripts/download_data.py

# ── Step 9: Train ALL models ──────────────────────────────────────────────────
echo "[9/9] Training models (this is the longest step)..."
python scripts/train_models.py

echo ""
echo "════════════════════════════════════════════════════════"
echo "  SETUP COMPLETE
  To run manually:
    1. Start PostgreSQL & Redis services
    2. Start Backend: source venv/bin/activate && uvicorn backend.main:app --reload --port 8000
    3. Start Celery: source venv/bin/activate && celery -A backend.celery_app worker --loglevel=info
    4. Start React UI: cd frontend && npm run dev
  App: http://localhost:3000
  API: http://localhost:8000/docs"
echo "════════════════════════════════════════════════════════"
