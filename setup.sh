#!/bin/bash
# setup.sh — Run this once to set up the entire TrustHire project

set -e

echo "============================================"
echo "   TrustHire — Setup Script"
echo "============================================"

echo ""
echo "[1/8] Installing system dependencies..."
sudo apt-get update && sudo apt-get install -y \
  python3.11 python3.11-pip python3.11-venv \
  nodejs npm postgresql redis-server \
  chromium-browser chromium-chromedriver \
  git curl wget

echo ""
echo "[2/8] Setting up Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

echo ""
echo "[3/8] Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "[4/8] Downloading spaCy model..."
python -m spacy download en_core_web_sm

echo ""
echo "[5/8] Installing Playwright browsers..."
playwright install chromium

echo ""
echo "[6/8] Installing Node dependencies for frontend..."
cd frontend && npm install && cd ..

echo ""
echo "[7/8] Setting up PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE trusthire;" 2>/dev/null || echo "Database already exists"
sudo -u postgres psql -c "CREATE USER trusthire_user WITH PASSWORD 'trusthire_pass';" 2>/dev/null || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trusthire TO trusthire_user;" 2>/dev/null || echo "Privileges already granted"

echo ""
echo "[8/8] Running database migrations..."
source venv/bin/activate
alembic upgrade head

echo ""
echo "============================================"
echo "   Downloading datasets..."
echo "============================================"
python scripts/download_data.py

echo ""
echo "============================================"
echo "   Training ML models..."
echo "============================================"
python scripts/train_models.py

echo ""
echo "============================================"
echo "   ✓ Setup complete!"
echo "   To start services locally:"
echo "     1. Start PostgreSQL and Redis servers"
echo "     2. Run backend API:"
echo "        source venv/bin/activate"
echo "        uvicorn backend.main:app --reload --port 8000"
echo "     3. Run Celery worker (in a separate terminal):"
echo "        source venv/bin/activate"
echo "        celery -A backend.celery_app worker --loglevel=info"
echo "     4. Run React UI:"
echo "        cd frontend && npm run dev"
echo "============================================"
