#!/bin/bash
set -e

echo "Installing all TrustHire dependencies..."

# System packages
sudo apt-get update -qq && sudo apt-get install -y -qq \
  python3.11 python3.11-pip python3.11-venv \
  postgresql redis-server nodejs npm \
  chromium-browser chromium-chromedriver \
  build-essential libpq-dev libssl-dev \
  libxml2-dev libxslt1-dev libffi-dev \
  wget curl git unzip tesseract-ocr \
  libmagic1 whois dnsutils nmap

# Python environment
python3.11 -m venv venv && source venv/bin/activate
pip install --upgrade pip setuptools wheel

pip install \
  fastapi==0.111.0 uvicorn[standard]==0.29.0 gunicorn==22.0.0 \
  pydantic==2.7.1 pydantic-settings==2.2.1 \
  sqlalchemy==2.0.30 alembic==1.13.1 psycopg2-binary==2.9.9 \
  celery==5.4.0 redis==5.0.4 \
  httpx==0.27.0 aiohttp==3.9.5 \
  beautifulsoup4==4.12.3 lxml==5.2.2 \
  playwright==1.44.0 \
  python-whois==0.9.4 dnspython==2.6.1 \
  tldextract==5.1.2 \
  python-jose[cryptography]==3.3.0 passlib[bcrypt]==1.7.4 \
  python-multipart==0.0.9 python-dotenv==1.0.1 \
  slowapi==0.1.9 sentry-sdk[fastapi]==2.5.1 \
  torch==2.3.0 torchvision==0.18.0 \
  transformers==4.41.1 tokenizers==0.19.1 \
  datasets==2.19.2 accelerate==0.30.0 evaluate==0.4.2 \
  sentence-transformers==3.0.0 \
  faiss-cpu==1.8.0 \
  scikit-learn==1.5.0 scipy==1.13.1 \
  xgboost==2.0.3 lightgbm==4.3.0 \
  pandas==2.2.2 numpy==1.26.4 \
  spacy==3.7.4 \
  mlflow==2.13.0 \
  scrapy==2.11.2 \
  requests==2.32.3 tqdm==4.66.4 \
  joblib==1.4.2 shap==0.45.1 \
  imbalanced-learn==0.12.3 \
  langdetect==1.0.9 \
  Pillow==10.3.0 \
  cryptography==42.0.8 pyOpenSSL==24.1.0 \
  certifi==2024.6.2 \
  whois==0.9.27 \
  ipwhois==1.2.0 \
  validators==0.28.3 \
  urllib3==2.2.1 \
  chardet==5.2.0 \
  python-magic==0.4.27 \
  optuna==3.6.1

# spaCy models
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_lg  # Better NER

# Playwright
playwright install chromium
playwright install-deps chromium

# Frontend
cd frontend && npm install && cd ..

echo "All dependencies installed."
