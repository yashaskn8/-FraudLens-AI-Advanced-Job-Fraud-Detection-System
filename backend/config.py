from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TrustHire"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "your-secret-key-change-in-production"

    # Database
    DATABASE_URL: str = "postgresql://trusthire_user:trusthire_pass@localhost/trusthire"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # External APIs
    GOOGLE_SAFE_BROWSING_API_KEY: str = ""
    VIRUSTOTAL_API_KEY: str = ""
    WHOISXML_API_KEY: str = ""

    # LLM
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OPENAI_API_KEY: str = ""

    # Model paths
    BERT_MODEL_PATH: str = "models/bert_fraud_classifier/final"
    FAISS_INDEX_PATH: str = "models/faiss_index/fake_jobs.index"
    FAISS_METADATA_PATH: str = "models/faiss_index/metadata.json"
    BASELINE_MODEL_PATH: str = "models/baseline"
    URL_CLASSIFIER_PATH: str = "models/url_classifier"

    # Rate limiting
    RATE_LIMIT_FREE: str = "10/minute"
    RATE_LIMIT_REGISTERED: str = "60/minute"

    # Trust Score Signal Weights
    # These are the CONFIGURED weights. The score engine redistributes them
    # dynamically when signals are unavailable or unreliable.
    WEIGHT_URL_ANALYSIS: float = 0.35          # Most reliable — rule-based
    WEIGHT_NLP_CLASSIFICATION: float = 0.30    # High when BERT trained, reduced otherwise
    WEIGHT_COMPANY_VERIFICATION: float = 0.25  # Strong when company info available
    WEIGHT_DUPLICATE_DETECTION: float = 0.05   # Supplementary
    WEIGHT_SCAM_PHRASES: float = 0.05          # Supplementary

    # Verdict Thresholds (trust_score out of 100)
    # Tuned so that a legitimate URL with URL=100, Company=80, NLP=excluded
    # scores approximately: (100*0.35 + 80*0.25) / (0.35+0.25) = 91.7 → SAFE
    VERDICT_THRESHOLDS: dict = {
        "safe": 70,          # >= 70 → SAFE
        "suspicious": 45,    # >= 45 → SUSPICIOUS
        "likely_fraud": 25,  # >= 25 → LIKELY_FRAUD
                             # <  25 → FRAUD
    }

    # Sentry
    SENTRY_DSN: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
