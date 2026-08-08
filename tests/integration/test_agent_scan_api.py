"""Scan endpoint integration tests for agent-trace persistence and static fallback."""
from types import SimpleNamespace
from urllib.parse import urlparse

from backend.rate_limiter import limiter
from backend.routers import scan as scan_router
from backend.services.explainer import AgentExplanationResult
from backend.services.investigator_agent import InvestigatorResult
from backend.services.job_relevance_detector import JobRelevanceResult
from backend.services.nlp_classifier import NLPClassificationResult


def _patch_suspicious_pipeline(monkeypatch):
    def offline_extract(url):
        host = (urlparse(url if "://" in url else f"//{url}").hostname or "").lower()
        labels = host.split(".")
        return SimpleNamespace(subdomain="", domain=labels[-2], suffix=labels[-1])

    async def relevance(**kwargs):
        return JobRelevanceResult(True, 0.95, "job_description", None, None)

    async def analyse(url):
        return SimpleNamespace(
            url=url, domain="example.com", url_trust_score=0.55,
            ml_classifier_available=True, page_content_signals={}, flags=[],
        )

    async def classify(text):
        return NLPClassificationResult(
            bert_fraud_probability=0.45, bert_confidence=0.9, used_trained_model=True,
            model_source="bert_finetuned", optimal_threshold=0.5, duplicate_found=False,
            duplicate_similarity=0.0, duplicate_excerpt="", scam_phrase_score=0.0,
            scam_phrases_found=[], structural_score=0.55, combined_nlp_score=0.55,
        )

    async def company(**kwargs):
        return SimpleNamespace(
            company_trust_score=0.6, signals_checked=1, has_active_fraud_evidence=False,
            flags=[], company_name="Example",
        )

    monkeypatch.setattr(scan_router, "detect_job_relevance", relevance)
    monkeypatch.setattr(scan_router, "analyse_url", analyse)
    monkeypatch.setattr(scan_router, "classify_description", classify)
    monkeypatch.setattr(scan_router, "verify_company_global", company)
    monkeypatch.setattr(scan_router, "get_cached_result", lambda url: None)
    monkeypatch.setattr(scan_router, "cache_result", lambda *args: None)
    monkeypatch.setattr(scan_router.tldextract, "extract", offline_extract)


def test_suspicious_scan_persists_and_returns_agent_trace(client, monkeypatch):
    _patch_suspicious_pipeline(monkeypatch)
    limiter.reset()
    monkeypatch.setattr(scan_router, "is_openai_agent_available", lambda: True)

    async def investigate(*args, **kwargs):
        return InvestigatorResult(
            additional_evidence=[{"summary": "Registry evidence was reviewed."}],
            investigator_confidence=0.81,
            tools_called=[{"name": "check_company_registry", "arguments": {}, "result": {"available": True}}],
            reasoning_steps=[{"action": "tool_called", "tool": "check_company_registry"}],
        )

    async def explain(*args, **kwargs):
        return AgentExplanationResult(
            "Evidence-backed caution is recommended.",
            tools_called=[{"name": "check_prior_reports", "arguments": {}, "result": {"report_count": 0}}],
            reasoning_steps=[{"action": "critic_review", "approved": True}],
            critic_passed=True,
            used_agent=True,
        )

    monkeypatch.setattr(scan_router, "investigate_suspicious", investigate)
    monkeypatch.setattr(scan_router, "generate_agentic_explanation", explain)

    created = client.post("/api/v1/scan", json={
        "url": "https://jobs.example.com/role", "company_name": "Example",
        "description": "A detailed engineering position with responsibilities and qualifications.",
    })
    body = created.json()
    retrieved = client.get(f"/api/v1/scan/{body['scan_id']}")

    assert created.status_code == 200 and body["verdict"] == "SUSPICIOUS"
    assert body["investigator_confidence"] == 0.81
    assert retrieved.status_code == 200
    assert [entry["name"] for entry in retrieved.json()["agent_trace"]["tools_called"]] == [
        "check_company_registry", "check_prior_reports"
    ]


def test_static_scan_path_omits_agent_trace(client, monkeypatch):
    _patch_suspicious_pipeline(monkeypatch)
    limiter.reset()
    monkeypatch.setattr(scan_router, "is_openai_agent_available", lambda: False)

    async def static_explanation(*args):
        return "Static explanation."

    monkeypatch.setattr(scan_router, "generate_explanation", static_explanation)
    created = client.post("/api/v1/scan", json={
        "description": "A detailed engineering position with responsibilities and qualifications.",
    })
    retrieved = client.get(f"/api/v1/scan/{created.json()['scan_id']}")

    assert created.status_code == 200
    assert "agent_trace" not in retrieved.json()
