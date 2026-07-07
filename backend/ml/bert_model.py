"""
BERT Model Loader — wraps the DistilBERT classifier for inference.
"""
import torch
from pathlib import Path
from backend.config import settings

_model = None
_tokenizer = None


def get_model():
    """Load and cache BERT model for inference."""
    global _model, _tokenizer
    if _model is not None:
        return _tokenizer, _model

    model_path = Path(settings.BERT_MODEL_PATH)
    if not model_path.exists():
        print(f"WARNING: BERT model not found at {model_path}")
        return None, None

    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    _tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    _model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    _model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model.to(device)
    return _tokenizer, _model


def predict(text: str) -> dict:
    """Run inference on a single text."""
    tokenizer, model = get_model()
    if tokenizer is None:
        return {"fraud_probability": 0.5, "confidence": 0.5, "label": "unknown"}

    device = next(model.parameters()).device
    inputs = tokenizer(
        text, truncation=True, padding="max_length",
        max_length=512, return_tensors="pt",
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=1)[0]

    fraud_prob = probs[1].item()
    return {
        "fraud_probability": fraud_prob,
        "confidence": max(probs).item(),
        "label": "fake" if fraud_prob > 0.5 else "real",
    }
