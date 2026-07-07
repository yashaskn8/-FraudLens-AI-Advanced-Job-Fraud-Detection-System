#!/bin/bash
set -e

echo "Installing TrustHire worldwide dependencies..."
source venv/bin/activate || (python3.11 -m venv venv && source venv/bin/activate)

pip install --upgrade pip setuptools wheel

# Core ML and NLP
pip install \
  torch==2.3.0 torchvision==0.18.0 \
  transformers==4.41.1 tokenizers==0.19.1 \
  datasets==2.19.2 accelerate==0.30.0 \
  sentence-transformers==3.0.0 \
  faiss-cpu==1.8.0 \
  scikit-learn==1.5.0 scipy==1.13.1 \
  xgboost==2.0.3 lightgbm==4.3.0 \
  imbalanced-learn==0.12.3 \
  optuna==3.6.1 shap==0.45.1

# Multilingual NLP — required for 8-language fraud phrase detection
pip install \
  langdetect==1.0.9 \
  langid==1.1.6 \
  pycld2==0.41 \
  spacy==3.7.4

# URL and domain analysis
pip install \
  tldextract==5.1.2 \
  python-whois==0.9.4 \
  dnspython==2.6.1 \
  ipwhois==1.2.0 \
  pyOpenSSL==24.1.0 \
  cryptography==42.0.8 \
  certifi==2024.6.2 \
  validators==0.28.3

# HTTP and scraping
pip install \
  httpx==0.27.0 aiohttp==3.9.5 \
  playwright==1.44.0 \
  beautifulsoup4==4.12.3 lxml==5.2.2 \
  scrapy==2.11.2 \
  fake-useragent==1.5.1

# Country and geolocation detection
pip install \
  geoip2==4.8.0 \
  pycountry==23.12.11 \
  phonenumbers==8.13.37

# Data handling and backend
pip install \
  pandas==2.2.2 numpy==1.26.4 \
  pyarrow==16.1.0 \
  kaggle==1.6.14 tqdm==4.66.4 \
  requests==2.32.3 \
  fastapi==0.111.0 uvicorn[standard]==0.29.0 \
  celery==5.4.0 redis==5.0.4 \
  sqlalchemy==2.0.30 alembic==1.13.1 \
  psycopg2-binary==2.9.9 \
  mlflow==2.13.0 \
  sentry-sdk[fastapi]==2.5.1

# spaCy language models
python -m spacy download en_core_web_lg
python -m spacy download xx_ent_wiki_sm   # Multilingual NER

# Playwright browser
playwright install chromium
playwright install-deps chromium

echo "All worldwide dependencies installed."
