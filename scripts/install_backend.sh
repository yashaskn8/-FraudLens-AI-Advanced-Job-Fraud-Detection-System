#!/bin/bash
set -e

echo "Installing all TrustHire backend dependencies..."

pip install --upgrade pip

# Core ML stack
pip install \
  torch torchvision \
  transformers tokenizers \
  datasets accelerate \
  sentence-transformers \
  faiss-cpu \
  scikit-learn scipy \
  xgboost lightgbm \
  imbalanced-learn \
  optuna \
  shap

# URL analysis
pip install \
  tldextract \
  python-whois \
  dnspython \
  validators \
  certifi

# Web scraping and HTTP
pip install \
  httpx \
  beautifulsoup4 \
  lxml \
  requests \
  aiohttp \
  fake-useragent

# NLP
pip install \
  spacy \
  langdetect

# Data
pip install \
  pandas numpy \
  pyarrow \
  tqdm

# Backend
pip install \
  fastapi "uvicorn[standard]" \
  sqlalchemy alembic \
  psycopg2-binary

echo "All dependencies installed."
