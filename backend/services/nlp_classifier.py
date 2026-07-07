"""
backend/services/nlp_classifier.py
NLP fraud classification with guaranteed score output.

Priority chain:
  1. Fine-tuned DistilBERT (if model_info.json confirms training complete)
  2. TF-IDF + XGBoost baseline (if vectorizer.pkl exists)
  3. Structural heuristics + scam phrase scoring (always available, zero dependencies)

A score is always returned. "Not available" is never an acceptable output.
"""
import re
import json
import math
import pickle
import asyncio
import logging
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import numpy as np
import torch

from backend.config import settings

logger = logging.getLogger("trusthire.nlp")


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class NLPClassificationResult:
    bert_fraud_probability: float       # Raw fraud probability from primary model [0,1]
    bert_confidence: float              # Confidence of primary model prediction [0,1]
    used_trained_model: bool            # Backward compat — True if BERT fine-tuned
    model_source: str                   # "bert_finetuned" | "baseline_xgb" | "heuristic" | "no_input"
    optimal_threshold: float            # Learned threshold (0.5 default if unknown)
    duplicate_found: bool
    duplicate_similarity: float
    duplicate_excerpt: str
    scam_phrase_score: float            # Weighted scam phrase score [0,1]
    scam_phrases_found: list
    structural_score: float             # Structural heuristic score [0,1]
    combined_nlp_score: float           # FINAL score fed to trust scorer [0,1]
    has_active_fraud_evidence: bool = False  # True only when fraud positively detected
    flags: list = field(default_factory=list)


# ── Model loading ─────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_model_info() -> dict:
    path = Path(settings.BERT_MODEL_PATH) / "model_info.json"
    try:
        with open(path) as f:
            info = json.load(f)
        if info.get("trained"):
            logger.info(
                f"BERT fine-tuned model active — "
                f"F1={info.get('test_f1_at_threshold', info.get('test_f1', '?'))}, "
                f"threshold={info.get('optimal_threshold', 0.5):.3f}"
            )
            return info
    except Exception:
        pass
    logger.info("BERT not fine-tuned — baseline/heuristic model will be used for NLP scoring.")
    return {"trained": False, "optimal_threshold": 0.5}


@lru_cache(maxsize=1)
def _load_bert():
    info = _load_model_info()
    if not info.get("trained"):
        return None, None, None
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        path = str(Path(settings.BERT_MODEL_PATH))
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForSequenceClassification.from_pretrained(path)
        model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        logger.info(f"BERT loaded on {device}")
        return tok, model, device
    except Exception as e:
        logger.error(f"BERT load failed: {e}")
        return None, None, None


@lru_cache(maxsize=1)
def _load_baseline():
    bl_dir = Path(settings.BASELINE_MODEL_PATH)
    try:
        with open(bl_dir / "vectorizer.pkl", "rb") as f:
            vec = pickle.load(f)
        with open(bl_dir / "classifier.pkl", "rb") as f:
            clf = pickle.load(f)
        logger.info("TF-IDF baseline model loaded.")
        return vec, clf
    except Exception as e:
        logger.warning(f"Baseline model not found ({e}) — heuristics will be used.")
        return None, None


@lru_cache(maxsize=1)
def _load_sbert_faiss():
    try:
        import faiss
        from sentence_transformers import SentenceTransformer
        sbert = SentenceTransformer("all-MiniLM-L6-v2")
        fake_idx = faiss.read_index(settings.FAISS_INDEX_PATH)
        real_idx_path = str(
            Path(settings.FAISS_INDEX_PATH).parent / "real_jobs.index"
        )
        real_idx = (
            faiss.read_index(real_idx_path)
            if Path(real_idx_path).exists() else None
        )
        with open(settings.FAISS_METADATA_PATH) as f:
            meta = json.load(f)
        return sbert, fake_idx, real_idx, meta
    except Exception as e:
        logger.warning(f"SBERT/FAISS unavailable: {e}")
        return None, None, None, []


@lru_cache(maxsize=1)
def _load_scam_phrases():
    """
    Loads the global multilingual scam phrase dictionary.
    Falls back to English-only embedded list if the file is unavailable.
    """
    try:
        import pandas as pd
        global_path = Path("data/processed/scam_phrases_global.csv")
        legacy_path = Path("data/processed/scam_phrases.csv")
        if global_path.exists():
            df = pd.read_csv(global_path)
            logger.info(f"Global phrase dictionary loaded: {len(df)} phrases "
                        f"in {df['language'].nunique()} languages")
            return df
        elif legacy_path.exists():
            df = pd.read_csv(legacy_path)
            df["language"] = "en"
            df["region"] = "global"
            return df
    except Exception as e:
        logger.warning(f"Phrase dictionary load failed: {e}")

    # Embedded minimal multilingual fallback — always available
    import pandas as pd
    minimal = [
        ("pay registration fee", 0.99, "payment", "en", "global"),
        ("earn from home", 0.86, "remote_fraud", "en", "global"),
        ("guaranteed placement", 0.93, "guarantee", "en", "global"),
        ("no experience required", 0.80, "process", "en", "global"),
        ("whatsapp your cv", 0.96, "contact", "en", "global"),
        ("no interview required", 0.93, "process", "en", "global"),
        ("pay security deposit", 0.99, "payment", "en", "global"),
        ("direct selection", 0.84, "process", "en", "global"),
        ("network marketing", 0.83, "mlm", "en", "global"),
        ("multi level marketing", 0.88, "mlm", "en", "global"),
        ("رسوم التسجيل", 0.99, "payment", "ar", "MENA"),
        ("bayaran pendaftaran", 0.99, "payment", "ms", "SEA"),
        ("frais d'inscription", 0.99, "payment", "fr", "global"),
        ("pago de inscripción", 0.99, "payment", "es", "global"),
        ("taxa de cadastro", 0.99, "payment", "pt", "BR"),
        # Legitimate signals
        ("competitive salary", -0.15, "legit", "en", "global"),
        ("health insurance", -0.20, "legit", "en", "global"),
        ("annual ctc", -0.25, "legit", "en", "global"),
        ("interview process", -0.20, "legit", "en", "global"),
        ("provident fund", -0.18, "legit", "en", "IN"),
    ]
    return pd.DataFrame(minimal, columns=["phrase", "weight", "category",
                                           "language", "region"])


# ── Inference functions ───────────────────────────────────────────────────────

def _bert_score(text: str) -> tuple:
    """Returns (fraud_probability, confidence) from fine-tuned BERT."""
    tok, model, device = _load_bert()
    if model is None:
        return 0.5, 0.0
    inputs = tok(
        text[:2000], truncation=True, padding="max_length",
        max_length=512, return_tensors="pt"
    ).to(device)
    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=1)[0]
    return float(probs[1]), float(probs.max())


def _baseline_score(text: str) -> tuple:
    """Returns (fraud_probability, confidence) from TF-IDF baseline."""
    vec, clf = _load_baseline()
    if vec is None:
        return 0.5, 0.0
    X = vec.transform([text])
    prob = float(clf.predict_proba(X)[0][1])
    confidence = abs(prob - 0.5) * 2   # 0 at decision boundary, 1 at extremes
    return prob, confidence


def _structural_score(text: str) -> tuple:
    """
    Score based on observable structural properties of the job description.
    Returns (trust_score 0–1, list of flags).
    This always runs regardless of model availability.

    Scoring philosophy:
      - Start at 0.60 (slight positive prior — most posted jobs are real)
      - Apply additive/subtractive modifiers based on measurable features
      - Cap at [0.10, 0.95] to avoid extreme certainty from heuristics alone
    """
    score = 0.60
    flags = []
    text_lower = text.lower()
    words = text.split()
    word_count = len(words)

    # ── Length signals ────────────────────────────────────────────────────────
    if word_count < 20:
        score -= 0.25
        flags.append(
            f"Job description is extremely short ({word_count} words) — "
            "legitimate postings typically contain detailed role information"
        )
    elif word_count < 60:
        score -= 0.12
        flags.append(
            f"Job description is brief ({word_count} words) — "
            "most legitimate employers provide detailed responsibilities and requirements"
        )
    elif word_count > 150:
        score += 0.08   # Detailed descriptions correlate with legitimacy

    # ── Contact method signals ────────────────────────────────────────────────
    gmail_present = bool(re.search(
        r"@gmail\.com|@yahoo\.com|@rediffmail\.com|@hotmail\.com", text_lower
    ))
    if gmail_present:
        score -= 0.22
        flags.append(
            "Job description contains a personal email address — "
            "legitimate employers use corporate email domains"
        )

    whatsapp_cta = bool(re.search(
        r"(?:whatsapp|watsapp)\s+(?:your|us|cv|resume|now|immediately|on)",
        text_lower
    ))
    if whatsapp_cta:
        score -= 0.20
        flags.append(
            "Job directs applicants to WhatsApp rather than a formal application process"
        )

    # ── Salary and financial signals ──────────────────────────────────────────
    unrealistic_salary = bool(re.search(
        r"(?:earn|salary|income|pay)\s*(?:rs\.?\s*|inr\s*|₹\s*)?(?:"
        r"(?:[5-9]\d|[1-9]\d{2})[,\s]?000|lakh|crore|unlimited)",
        text_lower
    ))
    if unrealistic_salary:
        score -= 0.18
        flags.append(
            "Salary claim appears disproportionately high relative to the described role"
        )

    fee_demand = bool(re.search(
        r"(?:pay|deposit|invest|fee|registration|joining)\s+(?:rs\.?\s*)?(?:\d+)",
        text_lower
    ))
    if fee_demand:
        score -= 0.35
        flags.append(
            "Description requests financial payment — legitimate employers never charge applicants"
        )

    # ── Process signals ───────────────────────────────────────────────────────
    no_interview = bool(re.search(
        r"no\s+interview|direct\s+(?:selection|joining)|without\s+interview",
        text_lower
    ))
    if no_interview:
        score -= 0.20
        flags.append(
            "Posting claims no interview is required — legitimate companies always conduct interviews"
        )

    urgency_count = len(re.findall(
        r"urgent|immediate|asap|today\s+only|last\s+date|limited\s+seats|"
        r"hurry|apply\s+now|don.t\s+miss|closing\s+soon",
        text_lower
    ))
    if urgency_count >= 2:
        score -= 0.10
        flags.append(
            f"Description contains {urgency_count} urgency phrases — "
            "artificial pressure is a common manipulation technique"
        )

    # ── Legitimacy signals (positive) ─────────────────────────────────────────
    professional_terms = [
        "responsibilities", "qualifications", "experience required",
        "key skills", "about us", "about the company", "annual ctc",
        "interview process", "benefits", "provident fund", "health insurance",
        "background check", "reference check", "notice period",
    ]
    pro_count = sum(1 for t in professional_terms if t in text_lower)
    if pro_count >= 4:
        score += 0.12
    elif pro_count >= 2:
        score += 0.06

    return max(0.10, min(0.95, score)), flags


def _scam_phrase_score(text: str) -> tuple:
    """
    Language-aware scam phrase scoring.
    Detects the language of the text and applies weighted matching,
    prioritising phrases from the detected language and region.
    Returns (fraud_contribution 0–1, list of matched phrases).
    """
    text_lower = text.lower()
    phrases_df = _load_scam_phrases()

    # Detect language
    detected_lang = "en"
    try:
        from langdetect import detect, LangDetectException
        detected_lang = detect(text[:500])
    except Exception:
        pass

    import pandas as pd
    found = []
    total_weight = 0.0

    # Support both DataFrame (new global format) and list-of-tuples (legacy)
    if isinstance(phrases_df, pd.DataFrame):
        for _, row in phrases_df.iterrows():
            phrase = str(row["phrase"]).lower()
            weight = float(row["weight"])
            lang = str(row.get("language", "en"))

            if phrase in text_lower:
                # Boost weight for phrases in the detected language
                multiplier = 1.3 if lang == detected_lang else 1.0
                adjusted_weight = weight * multiplier
                found.append(str(row["phrase"]))
                total_weight += adjusted_weight

        normalised = max(0.0, min(1.0, total_weight / 3.5))
        # Only return positive-weight phrases as flags
        positive_found = []
        for p in found:
            match = phrases_df[phrases_df["phrase"].str.lower() == p.lower()]
            if len(match) > 0 and float(match.iloc[0]["weight"]) > 0:
                positive_found.append(p)
        return normalised, positive_found
    else:
        # Legacy list-of-tuples format
        for phrase, weight in phrases_df:
            if phrase.lower() in text_lower:
                found.append(phrase)
                total_weight += weight

        normalised = max(0.0, min(1.0, total_weight / 3.0))
        positive_found = [p for p in found
                          if any(p == ph and w > 0 for ph, w in phrases_df)]
        return normalised, positive_found


def _duplicate_check(text: str) -> tuple:
    """Semantic similarity check against known fake posts using SBERT + FAISS."""
    sbert, fake_idx, real_idx, meta = _load_sbert_faiss()
    if sbert is None or fake_idx is None:
        return False, 0.0, ""

    emb = sbert.encode([text[:500]], normalize_embeddings=True).astype(np.float32)

    fake_dists, fake_idxs = fake_idx.search(emb, k=3)
    top_fake_sim = float(fake_dists[0][0])

    top_real_sim = 0.0
    if real_idx is not None:
        real_dists, _ = real_idx.search(emb, k=3)
        top_real_sim = float(real_dists[0][0])

    is_dup = top_fake_sim >= 0.88 and top_fake_sim > top_real_sim + 0.05
    excerpt = ""
    if is_dup and fake_idxs[0][0] < len(meta):
        excerpt = meta[fake_idxs[0][0]].get("text", "")

    return is_dup, top_fake_sim, excerpt


# ── Main classification function ──────────────────────────────────────────────

async def classify_description(text: str) -> NLPClassificationResult:
    """
    Main NLP classification entry point.
    Always returns a score between 0.0 and 1.0.
    Never returns None or raises an exception that suppresses the signal.

    Score composition:
      - BERT fine-tuned:  BERT 55% + Scam phrases 25% + Structural 15% + Duplicate 5%
      - Baseline model:   Baseline 45% + Scam phrases 30% + Structural 20% + Duplicate 5%
      - Heuristic only:   Scam phrases 40% + Structural 55% + Duplicate 5%
    """
    info = _load_model_info()
    threshold = info.get("optimal_threshold", 0.5)
    loop = asyncio.get_event_loop()
    flags = []

    # Guard: empty description — return neutral with no fraud evidence
    if not text or len(text.strip()) < 5:
        return NLPClassificationResult(
            bert_fraud_probability=0.40,
            bert_confidence=0.0,
            used_trained_model=False,
            model_source="no_input",
            optimal_threshold=threshold,
            duplicate_found=False,
            duplicate_similarity=0.0,
            duplicate_excerpt="",
            scam_phrase_score=0.0,
            scam_phrases_found=[],
            structural_score=0.60,
            combined_nlp_score=0.60,
            has_active_fraud_evidence=False,
            flags=["No job description provided — paste the description text "
                   "for full NLP analysis and improved accuracy"]
        )

    # Run all sub-analyses concurrently
    (bert_prob, bert_conf), \
    (bl_prob, bl_conf), \
    (is_dup, dup_sim, dup_excerpt), \
    (scam_score, scam_phrases), \
    (struct_trust, struct_flags) = await asyncio.gather(
        loop.run_in_executor(None, _bert_score, text),
        loop.run_in_executor(None, _baseline_score, text),
        loop.run_in_executor(None, _duplicate_check, text),
        loop.run_in_executor(None, _scam_phrase_score, text),
        loop.run_in_executor(None, _structural_score, text),
    )

    flags.extend(struct_flags)

    # ── Select primary model and compute composite score ──────────────────────
    tok, bert_model, _ = _load_bert()
    vec, clf = _load_baseline()

    if bert_model is not None and info.get("trained"):
        # Path 1: Fine-tuned BERT
        model_source = "bert_finetuned"
        primary_fraud_prob = bert_prob
        primary_confidence = bert_conf
        used_trained = True

        if bert_prob >= threshold + 0.15:
            flags.append(
                f"AI classifier identifies this as highly likely fraudulent "
                f"({bert_prob:.0%} fraud probability)"
            )
        elif bert_prob >= threshold:
            flags.append(
                f"AI classifier detects suspicious patterns "
                f"({bert_prob:.0%} fraud probability)"
            )

        # Composite: BERT 55% + scam phrases 25% + structural 15% + duplicate 5%
        raw_fraud = (
            bert_prob * 0.55 +
            scam_score * 0.25 +
            (1.0 - struct_trust) * 0.15 +
            (dup_sim if is_dup else 0.0) * 0.05
        )

    elif clf is not None:
        # Path 2: TF-IDF baseline
        model_source = "baseline_xgb"
        primary_fraud_prob = bl_prob
        primary_confidence = bl_conf
        used_trained = False

        if bl_prob > 0.70:
            flags.append(
                f"Baseline text classifier identifies suspicious language patterns "
                f"({bl_prob:.0%} fraud probability)"
            )

        # Composite: Baseline 45% + scam phrases 30% + structural 20% + duplicate 5%
        raw_fraud = (
            bl_prob * 0.45 +
            scam_score * 0.30 +
            (1.0 - struct_trust) * 0.20 +
            (dup_sim if is_dup else 0.0) * 0.05
        )

    else:
        # Path 3: Structural heuristics only (always available)
        model_source = "heuristic"
        primary_fraud_prob = 1.0 - struct_trust
        primary_confidence = 0.40
        used_trained = False
        flags.append(
            "AI classifier training in progress — "
            "score based on structural text analysis and fraud phrase detection"
        )

        # Composite: Scam phrases 40% + structural 55% + duplicate 5%
        raw_fraud = (
            scam_score * 0.40 +
            (1.0 - struct_trust) * 0.55 +
            (dup_sim if is_dup else 0.0) * 0.05
        )

    # ── Scam phrase and duplicate flags ───────────────────────────────────────
    if scam_phrases:
        top3 = scam_phrases[:3]
        flags.append(
            f"Found {len(scam_phrases)} fraud phrase"
            f"{'s' if len(scam_phrases) > 1 else ''}: "
            f"'{', '.join(top3)}'"
            f"{'...' if len(scam_phrases) > 3 else ''}"
        )

    if is_dup:
        flags.append(
            f"Job description is {dup_sim:.0%} semantically similar "
            "to a confirmed fraudulent posting in our database"
        )

    combined_nlp_score = max(0.05, min(0.95, 1.0 - raw_fraud))

    # Determine if we have active fraud evidence
    has_fraud = (
        (model_source == "bert_finetuned" and primary_fraud_prob >= threshold) or
        (model_source == "baseline_xgb" and primary_fraud_prob > 0.65) or
        is_dup or
        scam_score > 0.20 or
        len(scam_phrases) > 0
    )

    return NLPClassificationResult(
        bert_fraud_probability=primary_fraud_prob,
        bert_confidence=primary_confidence,
        used_trained_model=used_trained,
        model_source=model_source,
        optimal_threshold=threshold,
        duplicate_found=is_dup,
        duplicate_similarity=dup_sim,
        duplicate_excerpt=dup_excerpt,
        scam_phrase_score=scam_score,
        scam_phrases_found=scam_phrases,
        structural_score=struct_trust,
        combined_nlp_score=combined_nlp_score,
        has_active_fraud_evidence=has_fraud,
        flags=flags,
    )
