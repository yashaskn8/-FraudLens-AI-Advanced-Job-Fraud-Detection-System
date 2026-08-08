import pytest
import pandas as pd
import numpy as np

from backend.services import nlp_classifier
from backend.services.trust_scorer import compute_trust_score


def _patch_common(monkeypatch, *, bert_model, baseline_model):
    monkeypatch.setattr(nlp_classifier, "_load_model_info", lambda: {"trained": bool(bert_model), "optimal_threshold": 0.5})
    monkeypatch.setattr(nlp_classifier, "_load_bert", lambda: (object(), bert_model, "cpu"))
    monkeypatch.setattr(nlp_classifier, "_load_baseline", lambda: (object(), baseline_model))
    monkeypatch.setattr(nlp_classifier, "_bert_score", lambda text: (0.80, 0.90))
    monkeypatch.setattr(nlp_classifier, "_baseline_score", lambda text: (0.80, 0.60))
    monkeypatch.setattr(nlp_classifier, "_duplicate_check", lambda text: (False, 0.0, ""))
    monkeypatch.setattr(nlp_classifier, "_scam_phrase_score", lambda text: (0.20, ["pay registration fee"]))
    monkeypatch.setattr(nlp_classifier, "_structural_score", lambda text: (0.60, ["brief description"]))


def test_nlp_loaders_and_scoring_fallbacks_are_safe_when_models_are_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(nlp_classifier.settings, "BERT_MODEL_PATH", str(tmp_path / "bert"))
    monkeypatch.setattr(nlp_classifier.settings, "BASELINE_MODEL_PATH", str(tmp_path / "baseline"))
    nlp_classifier._load_model_info.cache_clear()
    nlp_classifier._load_bert.cache_clear()
    nlp_classifier._load_baseline.cache_clear()

    assert nlp_classifier._load_model_info()["trained"] is False
    assert nlp_classifier._load_bert() == (None, None, None)
    assert nlp_classifier._load_baseline() == (None, None)
    assert nlp_classifier._bert_score("description") == (0.5, 0.0)
    assert nlp_classifier._baseline_score("description") == (0.5, 0.0)


def test_structural_rules_and_phrase_scoring_expose_observable_fraud_evidence(monkeypatch):
    risky = (
        "Pay 5000 registration fee now. WhatsApp your CV today. Earn INR 100000. "
        "No interview required. Urgent apply now, limited seats."
    )
    risky_score, risky_flags = nlp_classifier._structural_score(risky)
    professional_score, professional_flags = nlp_classifier._structural_score(
        ("Responsibilities qualifications experience required key skills about us benefits "
         "health insurance interview process provident fund. ") * 20
    )
    phrases = pd.DataFrame([
        ("pay registration fee", 0.99, "payment", "en", "global"),
        ("health insurance", -0.20, "legit", "en", "global"),
    ], columns=["phrase", "weight", "category", "language", "region"])
    monkeypatch.setattr(nlp_classifier, "_load_scam_phrases", lambda: phrases)
    fraud_phrase_score, found = nlp_classifier._scam_phrase_score("Pay registration fee; health insurance included")
    monkeypatch.setattr(nlp_classifier, "_load_scam_phrases", lambda: [("advance fee", 1.0), ("benefits", -0.2)])
    legacy_score, legacy_found = nlp_classifier._scam_phrase_score("advance fee and benefits")

    assert risky_score < 0.20 and len(risky_flags) >= 5
    assert professional_score > 0.60 and professional_flags == []
    assert fraud_phrase_score > 0 and found == ["pay registration fee"]
    assert legacy_score > 0 and legacy_found == ["advance fee"]


def test_duplicate_check_compares_fake_and_real_neighbours(monkeypatch):
    class Encoder:
        def encode(self, texts, normalize_embeddings): return np.array([[1.0, 0.0]], dtype=np.float32)
    class Index:
        def __init__(self, score): self.score = score
        def search(self, embeddings, k): return np.array([[self.score, 0.0, 0.0]]), np.array([[0, 1, 2]])

    monkeypatch.setattr(nlp_classifier, "_load_sbert_faiss", lambda: (Encoder(), Index(.93), Index(.70), [{"text": "known scam"}]))
    assert nlp_classifier._duplicate_check("suspicious post") == (True, .93, "known scam")
    monkeypatch.setattr(nlp_classifier, "_load_sbert_faiss", lambda: (None, None, None, []))
    assert nlp_classifier._duplicate_check("anything") == (False, 0.0, "")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bert_model,baseline_model,source,expected_score",
    [
        (object(), object(), "bert_finetuned", 0.45),
        (None, object(), "baseline_xgb", 0.50),
        (None, None, "heuristic", 0.70),
    ],
)
async def test_priority_chain_falls_through_and_uses_its_documented_composite(
    monkeypatch, bert_model, baseline_model, source, expected_score
):
    _patch_common(monkeypatch, bert_model=bert_model, baseline_model=baseline_model)
    result = await nlp_classifier.classify_description("A real job description with enough text.")

    assert result.model_source == source
    assert result.combined_nlp_score == pytest.approx(expected_score)
    assert result.flags  # Sub-signal evidence survives the selected tier.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bert_model,baseline_model,expected_weight",
    [(object(), object(), 30.0), (None, object(), 25.5), (None, None, 21.0)],
)
async def test_tier_selects_the_nlp_weight_consumed_by_the_fusion_engine(
    monkeypatch, bert_model, baseline_model, expected_weight
):
    _patch_common(monkeypatch, bert_model=bert_model, baseline_model=baseline_model)
    nlp_result = await nlp_classifier.classify_description("A real job description with enough text.")
    fusion_result = compute_trust_score(nlp_result=nlp_result)

    # `configured_weights` retains the tier-adjusted fusion input; the display
    # weight is normalized to 100% because this is the only active signal.
    assert fusion_result.configured_weights["NLP Classification"] == expected_weight
    assert fusion_result.signal_weights["NLP Classification"] == 100.0


@pytest.mark.asyncio
async def test_empty_input_is_neutral_and_bert_warning_thresholds_are_visible(monkeypatch):
    empty = await nlp_classifier.classify_description("   ")
    assert empty.model_source == "no_input"
    assert empty.combined_nlp_score == 0.60 and empty.has_active_fraud_evidence is False

    _patch_common(monkeypatch, bert_model=object(), baseline_model=object())
    monkeypatch.setattr(nlp_classifier, "_bert_score", lambda text: (0.55, 0.8))
    suspicious = await nlp_classifier.classify_description("A complete description for an advertised role.")
    assert any("suspicious patterns" in flag for flag in suspicious.flags)
