from datetime import datetime
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from backend.models.job_scan import JobScan
from backend.rate_limiter import limiter
from backend.routers import scan as scan_router
from backend.services.job_relevance_detector import JobRelevanceResult
from backend.services.nlp_classifier import NLPClassificationResult


def _patch_scan_pipeline(monkeypatch):
    def offline_extract(url):
        host = (urlparse(url if "://" in url else f"//{url}").hostname or "").lower()
        labels = host.split(".")
        return SimpleNamespace(
            subdomain=".".join(labels[:-2]),
            domain=labels[-2] if len(labels) >= 2 else host,
            suffix=labels[-1] if len(labels) >= 2 else "",
        )

    async def job_relevance(**kwargs):
        return JobRelevanceResult(True, 0.95, "job_description", None, None)

    async def analyse_url(url):
        return SimpleNamespace(
            url=url, domain="example.com", url_trust_score=0.85,
            ml_classifier_available=True, page_content_signals={}, flags=[],
        )

    async def classify(text):
        return NLPClassificationResult(
            bert_fraud_probability=0.10, bert_confidence=0.90,
            used_trained_model=True, model_source="bert_finetuned",
            optimal_threshold=0.5, duplicate_found=False, duplicate_similarity=0.0,
            duplicate_excerpt="", scam_phrase_score=0.0, scam_phrases_found=[],
            structural_score=0.90, combined_nlp_score=0.90,
        )

    async def company(**kwargs):
        return SimpleNamespace(
            company_trust_score=0.80, signals_checked=2,
            has_active_fraud_evidence=False, flags=[], company_name="Example",
        )

    async def explanation(*args):
        return "Independent checks found no high-severity fraud indicators."

    monkeypatch.setattr(scan_router, "detect_job_relevance", job_relevance)
    monkeypatch.setattr(scan_router, "analyse_url", analyse_url)
    monkeypatch.setattr(scan_router, "classify_description", classify)
    monkeypatch.setattr(scan_router, "verify_company_global", company)
    monkeypatch.setattr(scan_router, "generate_explanation", explanation)
    monkeypatch.setattr(scan_router, "get_cached_result", lambda url: None)
    monkeypatch.setattr(scan_router, "cache_result", lambda *args: None)
    monkeypatch.setattr(scan_router.tldextract, "extract", offline_extract)


def test_scan_returns_complete_response_for_valid_job_posting(client, monkeypatch):
    _patch_scan_pipeline(monkeypatch)
    response = client.post("/api/v1/scan", json={
        "url": "https://jobs.example.com/engineering", "job_title": "Backend Engineer",
        "company_name": "Example", "description": "Build reliable services with a collaborative engineering team.",
    })

    body = response.json()
    assert response.status_code == 200
    assert body["scan_id"]
    assert body["is_job_content"] is True
    assert 0 <= body["trust_score"] <= 100
    assert body["verdict"] in {"SAFE", "SUSPICIOUS", "LIKELY_FRAUD", "FRAUD"}
    assert body["signal_scores"]["URL Analysis"] == 85
    assert body["explanation"]


def test_scan_degrades_gracefully_when_all_optional_fields_are_missing(client, monkeypatch):
    _patch_scan_pipeline(monkeypatch)
    response = client.post("/api/v1/scan", json={})

    body = response.json()
    assert response.status_code == 200
    assert body["scan_id"]
    assert body["trust_score"] is not None
    assert body["effective_signals"] >= 1


def test_scan_rejects_malformed_url_with_4xx(client, monkeypatch):
    _patch_scan_pipeline(monkeypatch)
    response = client.post("/api/v1/scan", json={"url": "not a valid URL"})
    assert response.status_code == 422
    assert "valid absolute HTTP(S) URL" in response.json()["detail"][0]["msg"]


def test_scan_accepts_job_board_url_with_query_string_and_fragment(client, monkeypatch):
    _patch_scan_pipeline(monkeypatch)
    job_url = "https://www.linkedin.com/jobs/view/1234567890/?trackingId=campaign#job-details"
    response = client.post("/api/v1/scan", json={"url": job_url, "description": "Detailed engineering role."})
    assert response.status_code == 200
    assert response.json()["url_details"]["url"].startswith("https://www.linkedin.com/jobs/view/")


def test_get_scan_by_id_returns_saved_scan_and_missing_id_is_404(client, db_session):
    db_session.add(JobScan(
        id="scan-known", url="https://example.com/jobs/1", job_title="Engineer",
        company_name="Example", description="Job", trust_score=76, verdict="SAFE",
        flags=["minor anomaly"], signal_scores={"URL Analysis": 85},
        explanation="Looks legitimate.", created_at=datetime(2026, 1, 1),
    ))
    db_session.commit()

    found = client.get("/api/v1/scan/scan-known")
    missing = client.get("/api/v1/scan/does-not-exist")

    assert found.status_code == 200
    assert found.json()["trust_score"] == 76
    assert found.json()["flags"] == ["minor anomaly"]
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Scan not found"


@pytest.mark.timeout(30)
def test_scan_rate_limit_enforces_free_tier(client, monkeypatch):
    _patch_scan_pipeline(monkeypatch)
    limiter.reset()
    requests_to_exceed_free_limit = 11  # settings.RATE_LIMIT_FREE = 10/minute
    responses = [
        client.post("/api/v1/scan", json={"description": "A detailed job posting."})
        for _ in range(requests_to_exceed_free_limit)
    ]
    assert all(response.status_code == 200 for response in responses[:-1])
    assert responses[-1].status_code == 429
