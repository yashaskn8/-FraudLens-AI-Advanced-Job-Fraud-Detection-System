"""
TrustHire — FastAPI Application Entry Point
AI-Powered Job Fraud Detection System
With startup model verification, auto-training, and enhanced health check.
"""
import json
import logging
import subprocess
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import settings
from backend.database import init_db
from backend.middleware import RequestLoggingMiddleware
from backend.rate_limiter import limiter
from backend.routers import scan, reports, auth, analytics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
)
logger = logging.getLogger("trusthire")


def _start_background_training():
    """
    Starts BERT training in a background thread.
    Uses subprocess so it does not block the FastAPI event loop.
    Training output is written to logs/training.log.
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / "training.log"

    def run():
        logger.info(
            "\n═══ BACKGROUND TRAINING STARTED ═══\n"
            "  BERT model is not trained. Starting automatic training.\n"
            f"  Progress: tail -f {log_path}\n"
            "  The application is fully operational during training.\n"
            "  NLP scores will improve automatically when training completes.\n"
            "═══════════════════════════════════"
        )
        with open(log_path, "w") as log_file:
            result = subprocess.run(
                ["python", "scripts/train_all_models.py"],
                stdout=log_file, stderr=subprocess.STDOUT,
                text=True
            )
        if result.returncode == 0:
            logger.info("═══ BACKGROUND TRAINING COMPLETE — BERT model now active ═══")
            # Invalidate LRU caches so new model is loaded on next inference
            try:
                from backend.services.nlp_classifier import (
                    _load_model_info, _load_bert, _load_baseline
                )
                _load_model_info.cache_clear()
                _load_bert.cache_clear()
                _load_baseline.cache_clear()
            except Exception as e:
                logger.warning(f"Cache clear failed (models will reload on restart): {e}")
        else:
            logger.error("Background training failed. Check logs/training.log.")

    thread = threading.Thread(target=run, daemon=True, name="bert-training")
    thread.start()


def verify_models_on_startup():
    """
    Check model status on startup and log actionable warnings.
    This does NOT block the application — it degrades gracefully.
    """
    bert_path = Path(settings.BERT_MODEL_PATH)
    info_path = bert_path / "model_info.json"

    if not bert_path.exists():
        logger.warning(
            "\n═══════════════════════════════════════════════════════════\n"
            "  TRUSTHIRE: BERT model not found.\n"
            "  NLP Classification will use baseline/heuristic model.\n"
            "  The system will attempt auto-training if data is available.\n"
            "═══════════════════════════════════════════════════════════"
        )
        return False

    if info_path.exists():
        try:
            with open(info_path) as f:
                info = json.load(f)
            if info.get("trained"):
                f1 = info.get("test_f1_at_threshold", info.get("test_f1", "?"))
                auc = info.get("test_roc_auc", "?")
                thresh = info.get("optimal_threshold", 0.5)
                logger.info(
                    f"BERT model ready — F1={f1}, "
                    f"ROC-AUC={auc}, "
                    f"Threshold={thresh}"
                )
                return True
            else:
                logger.warning(
                    "BERT model file exists but is not fine-tuned."
                )
                return False
        except Exception as e:
            logger.warning(f"Could not read model_info.json: {e}")
            return False
    else:
        logger.warning("model_info.json not found.")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    # Startup
    logger.info("Starting TrustHire API...")
    init_db()
    logger.info("Database tables initialized.")

    # Sentry integration (optional)
    if settings.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=settings.SENTRY_DSN, traces_sample_rate=0.1)
            logger.info("Sentry error tracking enabled.")
        except Exception:
            pass

    # Verify model status
    bert_trained = verify_models_on_startup()

    # Check FAISS and baseline
    faiss_path = Path(settings.FAISS_INDEX_PATH)
    if faiss_path.exists():
        logger.info("FAISS duplicate-detection index ready.")
    else:
        logger.warning("FAISS index not found. Duplicate detection will be disabled.")

    baseline_path = Path(settings.BASELINE_MODEL_PATH) / "classifier.pkl"
    if baseline_path.exists():
        logger.info("TF-IDF baseline model ready (NLP fallback active).")
    else:
        logger.warning("Baseline model not found.")

    # Auto-training: start background training if BERT is not trained
    if not bert_trained:
        data_ready = (
            Path("data/processed/train.csv").exists() and
            Path("data/processed/url_train.csv").exists()
        )
        if data_ready:
            _start_background_training()
        else:
            logger.warning(
                "Training data not found. Run: python scripts/download_all_datasets.py\n"
                "Then restart the application to trigger automatic BERT training."
            )

    logger.info(f"TrustHire v{settings.APP_VERSION} is ready.")
    yield
    # Shutdown cleanup (if needed)
    logger.info("TrustHire shutting down.")


# Create FastAPI app with lifespan
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "TrustHire analyses job postings across 7 signals — URL, company registration, "
        "AI classification, duplicate detection — and returns a Trust Score (0-100)."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.state.limiter = limiter

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(scan.router)
app.include_router(reports.router)
app.include_router(auth.router)
app.include_router(analytics.router)


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with model status."""
    bert_trained = False
    info_path = Path(settings.BERT_MODEL_PATH) / "model_info.json"
    if info_path.exists():
        try:
            with open(info_path) as f:
                info = json.load(f)
            bert_trained = info.get("trained", False)
        except Exception:
            pass

    # Check if training is active
    training_active = False
    log_path = Path("logs/training.log")
    if log_path.exists():
        try:
            import time
            training_active = (time.time() - log_path.stat().st_mtime) < 60
        except Exception:
            pass

    return {
        "status": "healthy",
        "models": {
            "bert_trained": bert_trained,
            "training_active": training_active,
            "faiss_available": Path(settings.FAISS_INDEX_PATH).exists(),
            "baseline_available": (
                Path(settings.BASELINE_MODEL_PATH) / "classifier.pkl"
            ).exists(),
        },
        "version": settings.APP_VERSION,
    }
