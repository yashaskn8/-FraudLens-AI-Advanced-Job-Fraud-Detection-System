"""Behavioural tests for service fallbacks and deterministic decision rules."""
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from backend.services import company_verifier, consistency_checker, explainer, job_relevance_detector, url_cache


@pytest.fixture(autouse=True)
def offline_tld_extractor(monkeypatch):
    def extract(url):
        host = (urlparse(url if "://" in url else f"//{url}").hostname or "").lower()
        labels = host.split(".")
        return SimpleNamespace(
            subdomain=".".join(labels[:-2]),
            domain=labels[-2] if len(labels) >= 2 else host,
            suffix=labels[-1] if len(labels) >= 2 else "",
        )

    monkeypatch.setattr(company_verifier.tldextract, "extract", extract)
    monkeypatch.setattr(job_relevance_detector.tldextract, "extract", extract)


@pytest.mark.parametrize(
    "description,title,consistent",
    [
        ("Junior intern role. Salary INR 150,000 per month.", "Intern", False),
        ("Leadership role. Salary INR 600,000 each month.", "Director", False),
        ("Salary INR 50,000 monthly with benefits.", "Engineer", True),
    ],
)
def test_salary_consistency_detects_implausible_claims(description, title, consistent):
    actual, flags = consistency_checker.check_salary_consistency(description, title)
    assert actual is consistent
    assert bool(flags) is (not consistent)


def test_contact_and_combined_consistency_checks_report_each_conflict():
    contact_ok, contact_flags = consistency_checker.check_contact_consistency("Message us on WhatsApp only")
    telegram_ok, telegram_flags = consistency_checker.check_contact_consistency("Contact us on Telegram")

    assert contact_ok is False and "WhatsApp" in contact_flags[0]
    assert telegram_ok is False and "Telegram" in telegram_flags[0]


@pytest.mark.asyncio
async def test_combined_consistency_score_reflects_all_failed_checks():
    result = await consistency_checker.check_consistency(
        "Remote office job. Contact on Telegram. No experience required. Salary INR 150,000.",
        title="Senior Intern",
    )
    assert result.consistency_score == 0.0
    assert len(result.flags) == 4


@pytest.mark.parametrize(
    "url,description,expected",
    [
        ("", "This position is based in India.", "IN"),
        ("https://example.com/us-en/jobs", "", "US"),
        ("https://example.co.uk/jobs", "", "GB"),
        ("", "United Kingdom office", "GB"),
    ],
)
def test_country_detection_uses_explicit_text_and_url_hints(url, description, expected):
    assert company_verifier._detect_country(url, description) == expected


@pytest.mark.asyncio
async def test_company_verifier_fast_pass_impersonation_and_graceful_missing_name():
    known = await company_verifier.verify_company_global(company_domain="google.com")
    impersonated = await company_verifier.verify_company_global(
        company_domain="google-career-verification.org", company_name="Google Jobs"
    )
    missing = await company_verifier.verify_company_global()

    assert (known.is_registered, known.company_trust_score, known.registry_used) == (True, 0.94, "Verified global employer whitelist")
    assert (impersonated.is_registered, impersonated.company_trust_score, impersonated.has_active_fraud_evidence) == (False, 0.06, True)
    assert missing.signals_checked == 0 and missing.company_trust_score == 0.5


@pytest.mark.asyncio
async def test_company_verifier_recognises_career_portal_and_registry_results(monkeypatch):
    career = await company_verifier.verify_company_global(
        company_name="Example", url="https://careers.example.com/opening"
    )
    not_found = await company_verifier.verify_company_global(company_name="Tiny")
    monkeypatch.setattr(company_verifier, "_verify_opencorporates", lambda name, country: (True, "dissolved"))
    inactive = await company_verifier.verify_company_global(company_name="Any Company")

    assert career.registry_used == "Career subdomain detection" and career.company_trust_score == 0.78
    assert not_found.company_trust_score == 0.3 and not_found.has_active_fraud_evidence
    assert inactive.company_trust_score == 0.4 and inactive.has_active_fraud_evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "description,company,expected_registry",
    [
        ("United Kingdom role", "Example Ltd", "Companies House (UK)"),
        ("Australia role", "Example Pty", "ABN Lookup (Australia)"),
        ("United States role", "Example Inc", "SEC EDGAR (US) / State Registries"),
        ("India role", "Example Private Limited", "Ministry of Corporate Affairs (India)"),
    ],
)
async def test_company_verifier_routes_country_to_its_registry(monkeypatch, description, company, expected_registry):
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "test")
    monkeypatch.setenv("ABN_LOOKUP_GUID", "test")
    result = await company_verifier.verify_company_global(company_name=company, description=description)
    assert result.registry_used == expected_registry
    assert result.is_registered is True and result.company_trust_score == 0.95


@pytest.mark.asyncio
async def test_company_verifier_marks_transient_registry_failure_as_no_fraud_evidence(monkeypatch):
    monkeypatch.setattr(company_verifier, "_verify_opencorporates", lambda *args: (_ for _ in ()).throw(RuntimeError("down")))
    result = await company_verifier.verify_company_global(company_name="Example Company")
    assert result.company_trust_score == 0.5
    assert result.has_active_fraud_evidence is False
    assert "temporarily unavailable" in result.flags[0]


@pytest.mark.asyncio
async def test_job_relevance_rejects_no_input_and_non_jobs_and_accepts_job_text(monkeypatch):
    no_input = await job_relevance_detector.detect_job_relevance()
    product = await job_relevance_detector.detect_job_relevance(url="https://chat.openai.com/")
    job_text = await job_relevance_detector.detect_job_relevance(
        description="We are hiring a full-time engineer. Key responsibilities include building services. "
                    "Qualifications and experience required include Python and SQL. Apply now online."
    )
    assert no_input.detected_type == "no_input"
    assert product.is_job_content is False and product.detected_entity == "ChatGPT AI chatbot"
    assert job_text.is_job_content is True and job_text.confidence == 0.88


@pytest.mark.asyncio
async def test_url_relevance_paths_and_content_fallbacks(monkeypatch):
    linkedin_job = await job_relevance_detector._check_url_relevance("https://linkedin.com/jobs/view/1")
    linkedin_profile = await job_relevance_detector._check_url_relevance("https://linkedin.com/in/person")
    career = await job_relevance_detector._check_url_relevance("https://careers.example.com/opening")
    path_match = await job_relevance_detector._check_url_relevance("https://example.com/jobs/123")

    async def fetched(url):
        return "Engineer", "Responsibilities. Qualifications. Apply now.", 200
    monkeypatch.setattr(job_relevance_detector, "_fetch_page_sample", fetched)
    content_match = await job_relevance_detector._check_url_relevance("https://example.com/about")

    assert linkedin_job.detected_type == "job_board"
    assert linkedin_profile.is_job_content is False
    assert career.detected_type == "employer_career"
    assert path_match.confidence == 0.80
    assert content_match.is_job_content and content_match.confidence == 0.85


@pytest.mark.asyncio
async def test_url_relevance_content_errors_unknown_pages_and_description_precedence(monkeypatch):
    async def error_page(url): return "", "", 404
    monkeypatch.setattr(job_relevance_detector, "_fetch_page_sample", error_page)
    failed = await job_relevance_detector._check_url_relevance("https://example.com/about")

    async def no_content(url): return "", "", None
    monkeypatch.setattr(job_relevance_detector, "_fetch_page_sample", no_content)
    unknown = await job_relevance_detector._check_url_relevance("https://example.com/about")
    monkeypatch.setattr(job_relevance_detector, "_check_url_relevance", lambda url: _async_result(
        job_relevance_detector.JobRelevanceResult(True, .80, "unknown", None, None)
    ))
    from_description = await job_relevance_detector.detect_job_relevance(
        url="https://example.com", description="We are hiring. Responsibilities and qualifications are listed."
    )

    assert failed.is_job_content is False and "HTTP 404" in failed.rejection_reason
    assert unknown.is_job_content and unknown.confidence == 0.40
    assert from_description.detected_type == "job_description"


@pytest.mark.asyncio
async def test_relevance_page_sample_strips_markup_and_falls_back_on_transport_error(monkeypatch):
    class Response:
        status_code = 200
        text = "<html><title>Role</title><script>ignore()</script><body><nav>nav</nav>Responsibilities here</body></html>"
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url): return Response()
    monkeypatch.setattr(job_relevance_detector.httpx, "AsyncClient", lambda **kwargs: Client())
    title, body, status = await job_relevance_detector._fetch_page_sample("https://example.com")
    assert (title, status) == ("Role", 200)
    assert "ignore" not in body and "Responsibilities" in body

    class FailingClient(Client):
        async def get(self, url): raise RuntimeError("offline")
    monkeypatch.setattr(job_relevance_detector.httpx, "AsyncClient", lambda **kwargs: FailingClient())
    assert await job_relevance_detector._fetch_page_sample("https://example.com") == (None, None, None)


def test_description_relevance_rejects_short_and_non_job_text_but_allows_marginal_text():
    short = job_relevance_detector._check_description_relevance("too short")
    non_job = job_relevance_detector._check_description_relevance("Latest news headlines and weather forecast for tomorrow." * 2)
    marginal = job_relevance_detector._check_description_relevance(
        "This engineering opportunity discusses collaboration, mentoring, product quality, and long-term learning."
    )
    assert short.is_job_content is False
    assert non_job.is_job_content is False
    assert marginal.is_job_content is True and marginal.confidence == 0.52


@pytest.mark.parametrize("score,established,ttl", [(0.9, True, 86400), (0.9, False, 3600), (0.6, False, 1800), (0.4, False, 600), (0.1, False, 300)])
def test_url_cache_ttl_tracks_risk(score, established, ttl):
    assert url_cache._compute_ttl(score, established) == ttl


def test_memory_cache_normalises_keys_stores_reads_and_invalidates(monkeypatch):
    url_cache._memory_cache.clear()
    monkeypatch.setattr(url_cache, "_get_redis", lambda: None)
    url_cache.cache_result(" HTTPS://Example.com/jobs/ ", {"score": 0.8}, 0.8, False)
    assert url_cache.get_cached_result("https://example.com/jobs") == {"score": 0.8}
    url_cache.invalidate_cache("https://example.com/jobs")
    assert url_cache.get_cached_result("https://example.com/jobs") is None


def test_redis_cache_is_used_when_available(monkeypatch):
    class FakeRedis:
        def __init__(self): self.data, self.ttl = {}, None
        def setex(self, key, ttl, data): self.data[key], self.ttl = data, ttl
        def get(self, key): return self.data.get(key)
        def delete(self, key): self.data.pop(key, None)
        def info(self, section): return {"db0": {"keys": len(self.data)}}

    fake = FakeRedis()
    monkeypatch.setattr(url_cache, "_get_redis", lambda: fake)
    url_cache.cache_result("https://example.com", {"nested": [1]}, 0.2, False)
    assert fake.ttl == 300
    assert url_cache.get_cached_result("https://example.com") == {"nested": [1]}
    assert url_cache.get_cache_stats()["redis_keys"] == 1


def test_cache_degrades_when_redis_operations_or_serialisation_fail(monkeypatch):
    class FailingRedis:
        def get(self, key): raise RuntimeError("read down")
        def setex(self, *args): raise RuntimeError("write down")
        def delete(self, key): raise RuntimeError("delete down")
        def info(self, section): raise RuntimeError("info down")

    url_cache._memory_cache.clear()
    monkeypatch.setattr(url_cache, "_get_redis", lambda: FailingRedis())
    url_cache.cache_result("https://failure.example", {"ok": True}, .8, False)
    assert url_cache.get_cached_result("https://failure.example") == {"ok": True}
    assert url_cache.get_cache_stats()["redis_keys"] == "unknown"
    url_cache.invalidate_cache("https://failure.example")
    assert url_cache.get_cached_result("https://failure.example") is None


@pytest.mark.parametrize("score,phrase", [(80, "passed our automated fraud checks"), (60, "raised some concerns"), (20, "multiple characteristics")])
def test_fallback_explanation_matches_trust_band(score, phrase):
    result = SimpleNamespace(trust_score=score)
    assert phrase in explainer._fallback_explanation(result)


@pytest.mark.asyncio
async def test_explanation_provider_dispatch_and_unknown_provider_fallback(monkeypatch):
    result = SimpleNamespace(trust_score=60, verdict="SUSPICIOUS", all_flags=["registration fee"])
    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(explainer, "_call_ollama", lambda prompt: _async("local explanation"))
    assert await explainer.generate_explanation(result, "Engineer", "Example") == "local explanation"

    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "unsupported")
    assert "raised some concerns" in await explainer.generate_explanation(result)

    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(explainer, "_call_openai", lambda prompt: _async("cloud explanation"))
    assert await explainer.generate_explanation(result) == "cloud explanation"


@pytest.mark.asyncio
async def test_llm_helpers_parse_provider_responses_and_fall_back_on_errors(monkeypatch):
    class Response:
        def __init__(self, data): self.data = data
        def json(self): return self.data
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            if "/api/generate" in url:
                return Response({"response": "local answer"})
            return Response({"choices": [{"message": {"content": "cloud answer"}}]})
    monkeypatch.setattr(explainer.httpx, "AsyncClient", lambda **kwargs: Client())
    assert await explainer._call_ollama("prompt") == "local answer"
    assert await explainer._call_openai("prompt") == "cloud answer"

    class BrokenClient(Client):
        async def post(self, *args, **kwargs): raise RuntimeError("offline")
    monkeypatch.setattr(explainer.httpx, "AsyncClient", lambda **kwargs: BrokenClient())
    assert "Our analysis is complete" in await explainer._call_ollama("prompt")
    assert "Our analysis is complete" in await explainer._call_openai("prompt")


async def _async(value):
    return value


async def _async_result(value):
    return value
