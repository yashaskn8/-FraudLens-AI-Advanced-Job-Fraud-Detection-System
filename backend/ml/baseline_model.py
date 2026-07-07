"""
Baseline Model — TF-IDF + Logistic Regression fallback classifier.
"""
import pickle
from pathlib import Path
from backend.config import settings

_vectorizer = None
_classifier = None


def get_baseline():
    """Load and cache baseline model."""
    global _vectorizer, _classifier
    if _vectorizer is not None:
        return _vectorizer, _classifier

    base_path = Path(settings.BASELINE_MODEL_PATH)
    vec_path = base_path / "vectorizer.pkl"
    clf_path = base_path / "classifier.pkl"

    if not vec_path.exists() or not clf_path.exists():
        print(f"WARNING: Baseline model not found at {base_path}")
        return None, None

    with open(vec_path, "rb") as f:
        _vectorizer = pickle.load(f)
    with open(clf_path, "rb") as f:
        _classifier = pickle.load(f)

    return _vectorizer, _classifier


def predict(text: str) -> dict:
    """Run baseline prediction on a single text."""
    vectorizer, classifier = get_baseline()
    if vectorizer is None:
        return {"fraud_probability": 0.5, "label": "unknown"}

    X = vectorizer.transform([text])
    proba = classifier.predict_proba(X)[0]
    fraud_prob = proba[1] if len(proba) > 1 else 0.5

    return {
        "fraud_probability": float(fraud_prob),
        "label": "fake" if fraud_prob > 0.5 else "real",
    }
