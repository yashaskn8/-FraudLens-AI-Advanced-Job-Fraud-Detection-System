from types import SimpleNamespace

import pytest

from backend.services.trust_scorer import compute_trust_score


def score(url=None, nlp=None, company=None):
    return compute_trust_score(url, nlp, company)


@pytest.mark.parametrize(
    "url,nlp,company,effective",
    [
        (True, False, True, 2),
        (True, True, False, 2),
        (True, False, False, 1),
    ],
)
def test_redistributes_all_configured_weight_to_reliable_signals(
    signal_factory, url, nlp, company, effective
):
    result = score(
        signal_factory("url") if url else None,
        signal_factory("nlp", reliable=nlp),
        signal_factory("company", reliable=company),
    )
    assert result.effective_signals == effective
    assert sum(result.signal_weights.values()) == pytest.approx(100.0)


def test_all_primary_signals_display_readme_calibrated_effective_weights(signal_factory):
    result = score(
        signal_factory("url"), signal_factory("nlp"), signal_factory("company")
    )
    assert result.signal_weights == {
        "URL Analysis": 38.9,
        "NLP Classification": 33.3,
        "Company Verification": 27.8,
    }


def test_all_three_unavailable_uses_documented_graceful_degradation():
    result = score()
    assert (result.trust_score, result.verdict, result.confidence) == (50, "SUSPICIOUS", 0.0)
    assert result.effective_signals == 0


def test_score_floor_caps_only_positive_fraud_evidence(signal_factory):
    low_fraud = signal_factory("url", 0.10, flags=["confirmed phishing"])
    high_nlp = signal_factory("nlp", 0.90)
    high_company = signal_factory("company", 0.90)

    result = score(low_fraud, high_nlp, high_company)
    assert result.trust_score == 30  # lowest fraud-evidence signal (10) + 20


def test_score_floor_does_not_treat_missing_data_as_fraud_evidence(signal_factory):
    low_without_flags = signal_factory("url", 0.10, flags=[])
    result = score(low_without_flags, signal_factory("nlp", 0.90), signal_factory("company", 0.90))
    assert result.trust_score == 59
    assert result.trust_score > 30


@pytest.mark.parametrize(
    "scores,expected",
    [
        ((0.30, 0.30, 1.00), 29),  # two danger signals: 40% penalty
        ((0.30, 0.50, 0.50), 30),  # one danger plus two warnings: 28% penalty
        ((0.49, 0.50, 0.90), 50),  # two warnings: 18% penalty
        ((0.90, 0.90, 0.50), 70),  # one warning: no multi-warning penalty
    ],
)
def test_multi_warning_penalty_tiers(signal_factory, scores, expected):
    url_score, nlp_score, company_score = scores
    result = score(
        signal_factory("url", url_score, flags=["phishing"]),
        signal_factory("nlp", nlp_score, evidence=True),
        signal_factory("company", company_score, evidence=True),
    )
    assert result.trust_score == expected


def test_two_critical_flags_hard_cap_high_score(signal_factory):
    result = score(signal_factory("url", 0.90, flags=["phishing detected", "malware detected"]))
    assert result.trust_score == 48


def test_two_critical_flags_do_not_raise_already_low_score(signal_factory):
    result = score(signal_factory("url", 0.20, flags=["phishing detected", "malware detected"]))
    assert result.trust_score == 20
    assert result.trust_score < 48


@pytest.mark.parametrize(
    "raw_score, verdict",
    [(.24, "FRAUD"), (.25, "LIKELY_FRAUD"), (.44, "LIKELY_FRAUD"),
     (.45, "SUSPICIOUS"), (.69, "SUSPICIOUS"), (.70, "SAFE")],
)
def test_verdict_thresholds_are_inclusive_at_documented_boundaries(signal_factory, raw_score, verdict):
    assert score(signal_factory("url", raw_score)).verdict == verdict


def test_confidence_tracks_reliable_signal_fraction(signal_factory):
    all_reliable = score(signal_factory("url"), signal_factory("nlp"), signal_factory("company"))
    one_excluded = score(signal_factory("url"), signal_factory("nlp", reliable=False), signal_factory("company"))
    only_url = score(signal_factory("url"), signal_factory("nlp", reliable=False), signal_factory("company", reliable=False))

    assert all_reliable.confidence == 1.0
    assert one_excluded.confidence == pytest.approx(2 / 3)
    assert only_url.confidence == pytest.approx(1 / 3)
