"""
backend/services/trust_scorer.py
Dynamic weight redistribution trust score engine.
Unreliable or unavailable signals are excluded and their weight redistributed.

Key design: The `has_active_fraud_evidence` flag distinguishes between signals
that have positively detected fraud and signals that simply lack data. Score
floor and multi-warning penalties only fire when actual fraud evidence exists.
"""
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from backend.config import settings

logger = logging.getLogger("trusthire.scorer")


@dataclass
class SignalInput:
    name: str
    raw_score: float              # 0.0 = fraud, 1.0 = legitimate
    weight: float                 # Configured weight (will be redistributed)
    is_reliable: bool             # False = exclude from fusion
    has_active_fraud_evidence: bool  # True only if signal positively detected fraud
    reliability_reason: str       # Why it is or is not reliable
    flags: list


@dataclass
class TrustScoreResult:
    trust_score: int
    verdict: str
    verdict_color: str
    confidence: float
    effective_signals: int  # How many signals actually contributed
    recommendation: str
    all_flags: list
    signal_scores: dict
    signal_weights: dict    # Redistributed weights actually used
    configured_weights: dict # Original configured weights (for display)
    explanation_context: dict
    model_trained: bool


def _is_bert_trained() -> bool:
    """Check whether BERT has been fine-tuned on EMSCAD."""
    info_path = Path(settings.BERT_MODEL_PATH) / "model_info.json"
    try:
        with open(info_path) as f:
            info = json.load(f)
        return bool(info.get("trained", False))
    except Exception:
        return False


def _get_bert_threshold() -> float:
    info_path = Path(settings.BERT_MODEL_PATH) / "model_info.json"
    try:
        with open(info_path) as f:
            info = json.load(f)
        return float(info.get("optimal_threshold", 0.5))
    except Exception:
        return 0.5


def _generate_recommendation(
    verdict: str,
    trust_score: int,
    all_flags: list[str],
) -> str:
    """
    Generates recommendation text dynamically based on the specific flags
    detected, ensuring the text never contradicts the score or flags.
    """
    high_severity_patterns = [
        "phishing", "malware", "virustotal", "ip address",
        "confirmed", "known fraudulent", "registration fee",
        "pay to", "deposit", "impersonation", "invalid or expired",
    ]

    has_critical = any(
        any(p in f.lower() for p in high_severity_patterns)
        for f in all_flags
    )

    if has_critical:
        return (
            "CRITICAL WARNING: This job posting contains severe fraud indicators "
            "consistent with known scams. Do not apply. Never pay any fees, "
            "deposit funds, or share sensitive identity documents."
        )

    if verdict in ("FRAUD", "LIKELY_FRAUD"):
        return (
            "Proceed with extreme caution. This posting exhibits multiple "
            "suspicious patterns. Verify the company independently before "
            "submitting any personal information."
        )

    if verdict == "SUSPICIOUS" or (len(all_flags) > 0 and trust_score < 70):
        return (
            "Exercise normal caution. While no severe fraud signals were detected, "
            "some minor anomalies are present. Verify the employer's official "
            "website before applying."
        )

    return (
        "This posting has passed all available fraud checks and appears legitimate. "
        "Standard precautions always apply — verify the company through official "
        "channels and never pay any fees during the application process."
    )


def compute_trust_score(
    url_result=None,
    nlp_result=None,
    company_result=None,
) -> TrustScoreResult:
    """
    Dynamic weighted trust score with safety corrections that distinguish
    between "no data" and "bad data":
      1. Score floor: only applies when the low signal has active fraud evidence
      2. Multi-warning penalty: only counts signals with fraud evidence
      3. Red flag override: 2+ high-severity flags cap score at 48
    """
    bert_trained = _is_bert_trained()
    all_flags = []
    signals: list = []

    # ── Signal 1: URL Analysis ────────────────────────────────────────────────
    if url_result is not None:
        url_score = url_result.url_trust_score if hasattr(url_result, 'url_trust_score') else 0.5
        ml_available = getattr(url_result, 'ml_classifier_available', False)
        has_page_content = getattr(url_result, 'page_content_signals', None) is not None

        reliability_parts = []
        if ml_available:
            reliability_parts.append("ML classifier active")
        else:
            reliability_parts.append("Heuristic mode (ML not trained)")
        if has_page_content:
            reliability_parts.append("live page content analysed")

        # URL signal has fraud evidence if it detected actual problems
        url_flags = url_result.flags if hasattr(url_result, 'flags') else []
        url_has_fraud = url_score < 0.50 and len(url_flags) > 0

        signals.append(SignalInput(
            name="URL Analysis",
            raw_score=float(url_score),
            weight=settings.WEIGHT_URL_ANALYSIS,
            is_reliable=True,
            has_active_fraud_evidence=url_has_fraud,
            reliability_reason=" + ".join(reliability_parts),
            flags=url_flags
        ))
        all_flags.extend(url_flags)

    # ── Signal 2: NLP Classification ─────────────────────────────────────────
    if nlp_result is not None:
        nlp_score = getattr(nlp_result, "combined_nlp_score", 0.5)
        model_source = getattr(nlp_result, "model_source", "heuristic")
        nlp_has_fraud = getattr(nlp_result, "has_active_fraud_evidence", False)

        # If no description was provided, model_source will be "no_input"
        # Mark as unreliable so it gets excluded from fusion entirely
        if model_source == "no_input":
            signals.append(SignalInput(
                name="NLP Classification",
                raw_score=float(nlp_score),
                weight=settings.WEIGHT_NLP_CLASSIFICATION,
                is_reliable=False,
                has_active_fraud_evidence=False,
                reliability_reason="No job description provided — signal excluded",
                flags=getattr(nlp_result, "flags", [])
            ))
            all_flags.extend(getattr(nlp_result, "flags", []))
        else:
            if model_source == "bert_finetuned":
                effective_weight = settings.WEIGHT_NLP_CLASSIFICATION
                reliability_reason = "Fine-tuned BERT classifier active"
            elif model_source == "baseline_xgb":
                effective_weight = settings.WEIGHT_NLP_CLASSIFICATION * 0.85
                reliability_reason = "Baseline TF-IDF classifier active"
            else:
                effective_weight = settings.WEIGHT_NLP_CLASSIFICATION * 0.70
                reliability_reason = "Structural heuristics active — run train_models.py to improve"

            signals.append(SignalInput(
                name="NLP Classification",
                raw_score=float(nlp_score),
                weight=effective_weight,
                is_reliable=True,
                has_active_fraud_evidence=nlp_has_fraud,
                reliability_reason=reliability_reason,
                flags=getattr(nlp_result, "flags", [])
            ))
            all_flags.extend(getattr(nlp_result, "flags", []))

    # ── Signal 3: Company Verification ───────────────────────────────────────
    if company_result is not None:
        company_score = (
            company_result.company_trust_score
            if hasattr(company_result, 'company_trust_score')
            else (company_result.get("company_trust_score", 0.5)
                  if isinstance(company_result, dict) else 0.5)
        )
        signals_checked = (
            getattr(company_result, 'signals_checked', 0)
            if not isinstance(company_result, dict)
            else company_result.get("signals_checked", 0)
        )
        company_flags = (
            company_result.flags
            if hasattr(company_result, 'flags')
            else (company_result.get("flags", [])
                  if isinstance(company_result, dict) else [])
        )
        company_has_fraud = getattr(
            company_result, 'has_active_fraud_evidence', False
        )

        if signals_checked == 0:
            signals.append(SignalInput(
                name="Company Verification",
                raw_score=0.5,
                weight=settings.WEIGHT_COMPANY_VERIFICATION,
                is_reliable=False,
                has_active_fraud_evidence=False,
                reliability_reason="No company information provided — signal excluded",
                flags=[]
            ))
        else:
            signals.append(SignalInput(
                name="Company Verification",
                raw_score=float(company_score),
                weight=settings.WEIGHT_COMPANY_VERIFICATION,
                is_reliable=True,
                has_active_fraud_evidence=company_has_fraud,
                reliability_reason=f"{signals_checked} company verification checks ran",
                flags=company_flags
            ))
            all_flags.extend(company_flags)

    # ── Dynamic Weight Redistribution ────────────────────────────────────────
    reliable = [s for s in signals if s.is_reliable]
    excluded = [s for s in signals if not s.is_reliable]

    redistributed_weights = {}

    if not reliable:
        logger.warning("No reliable signals available for trust score computation")
        trust_score = 50
        effective_signals = 0
    else:
        total_reliable_weight = sum(s.weight for s in reliable)
        total_excluded_weight = sum(s.weight for s in excluded)

        for signal in reliable:
            proportion = signal.weight / total_reliable_weight
            redistributed_weights[signal.name] = (
                signal.weight + (total_excluded_weight * proportion)
            )

        weighted_sum = sum(
            s.raw_score * redistributed_weights[s.name]
            for s in reliable
        )
        total_weight = sum(redistributed_weights.values())
        raw_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        trust_score = round(raw_score * 100)
        effective_signals = len(reliable)

        logger.info(
            f"Trust score computed from {effective_signals} reliable signals "
            f"(excluded: {[s.name for s in excluded]}). "
            f"Raw score: {raw_score:.3f} → {trust_score}/100"
        )

        # ── CORRECTION 1: Score Floor (only when fraud evidence exists) ────
        # Do NOT apply the floor when the low score comes from API
        # unavailability or missing data.
        signals_with_evidence = [
            s for s in reliable if s.has_active_fraud_evidence
        ]
        if signals_with_evidence:
            lowest_with_evidence = min(
                s.raw_score * 100 for s in signals_with_evidence
            )
            if trust_score > lowest_with_evidence + 20:
                logger.info(
                    f"Score floor applied (fraud evidence): "
                    f"raw={trust_score}, floor={lowest_with_evidence + 20:.0f}"
                )
                trust_score = int(lowest_with_evidence + 20)

        # ── CORRECTION 2: Multi-Warning Penalty (evidence-based only) ─────
        evidence_warnings = [
            s for s in reliable
            if s.raw_score * 100 < 60 and s.has_active_fraud_evidence
        ]
        evidence_danger = [
            s for s in reliable
            if s.raw_score * 100 < 35 and s.has_active_fraud_evidence
        ]

        danger_count = len(evidence_danger)
        warning_count = len(evidence_warnings)

        if danger_count >= 2:
            trust_score = int(trust_score * 0.60)
        elif danger_count >= 1 and warning_count >= 2:
            trust_score = int(trust_score * 0.72)
        elif warning_count >= 2:
            trust_score = int(trust_score * 0.82)

        if danger_count > 0 or warning_count > 1:
            logger.info(
                f"Multi-signal penalty: danger={danger_count}, "
                f"warning={warning_count} (evidence-based only)"
            )

        # ── CORRECTION 3: Red Flag Hard Cap ───────────────────────────────
        high_severity_patterns = [
            "phishing", "malware", "virustotal", "ip address",
            "confirmed", "known fraudulent", "registration fee",
            "pay to", "deposit", "impersonation", "invalid or expired",
            "free hosting", "free website",
        ]
        unique_flags = list(dict.fromkeys(all_flags))
        critical_flag_count = sum(
            1 for flag in unique_flags
            for pattern in high_severity_patterns
            if pattern in flag.lower()
        )

        if critical_flag_count >= 2 and trust_score > 48:
            logger.info(f"Red flag hard cap: {critical_flag_count} high-severity flags")
            trust_score = 48

    trust_score = max(0, min(100, trust_score))

    # ── Verdict ───────────────────────────────────────────────────────────────
    thresholds = settings.VERDICT_THRESHOLDS
    if trust_score >= thresholds["safe"]:
        verdict = "SAFE"
        verdict_color = "green"
    elif trust_score >= thresholds["suspicious"]:
        verdict = "SUSPICIOUS"
        verdict_color = "yellow"
    elif trust_score >= thresholds["likely_fraud"]:
        verdict = "LIKELY_FRAUD"
        verdict_color = "orange"
    else:
        verdict = "FRAUD"
        verdict_color = "red"

    # ── Flag-aware recommendation ────────────────────────────────────────────
    unique_flags = list(dict.fromkeys(all_flags))
    recommendation = _generate_recommendation(verdict, trust_score, unique_flags)

    # Signal scores for display
    signal_scores_display = {}
    signal_weights_display = {}
    configured_weights = {}
    effective_weight_total = sum(redistributed_weights.values())

    for s in signals:
        display_score = round(s.raw_score * 100) if s.is_reliable else None
        signal_scores_display[s.name] = display_score
        signal_weights_display[s.name] = (
            round(
                (redistributed_weights.get(s.name, 0) / effective_weight_total) * 100,
                1,
            )
            if s.is_reliable else 0
        )
        configured_weights[s.name] = round(s.weight * 100, 1)

    # Confidence
    confidence = min(1.0, effective_signals / max(len(signals), 1)) if signals else 0.0

    return TrustScoreResult(
        trust_score=trust_score,
        verdict=verdict,
        verdict_color=verdict_color,
        confidence=confidence,
        effective_signals=effective_signals,
        recommendation=recommendation,
        all_flags=unique_flags,
        signal_scores=signal_scores_display,
        signal_weights=signal_weights_display,
        configured_weights=configured_weights,
        explanation_context={
            "bert_trained": bert_trained,
            "excluded_signals": [s.name for s in excluded],
            "excluded_reasons": {s.name: s.reliability_reason for s in excluded},
            "effective_signals": effective_signals,
        },
        model_trained=bert_trained,
    )
