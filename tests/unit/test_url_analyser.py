import pytest
from types import SimpleNamespace
from urllib.parse import urlparse
import asyncio
import json
import pickle

from backend.services import url_analyser


class _Scaler:
    def transform(self, values):
        return values


class _Classifier:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, values):
        return __import__("numpy").array([[1 - self.probability, self.probability]])


@pytest.fixture(autouse=True)
def offline_public_suffix_lookup(monkeypatch):
    """Keep URL feature tests deterministic; the production helper imports this module lazily."""
    def extract(url):
        host = (urlparse(url if "://" in url else f"//{url}").hostname or "").lower()
        labels = host.split(".")
        return SimpleNamespace(
            subdomain=".".join(labels[:-2]),
            domain=labels[-2] if len(labels) >= 2 else host,
            suffix=labels[-1] if len(labels) >= 2 else "",
        )

    import tldextract
    monkeypatch.setattr(tldextract, "extract", extract)


def test_entropy_distinguishes_repeated_from_adversarial_random_text():
    assert url_analyser.calculate_url_entropy("aaaaaa") == 0.0
    assert url_analyser.calculate_url_entropy("a9$Kp2!Qx7") > 3.0
    assert url_analyser._shannon_entropy("aaaaaa") == 0.0


def test_typosquatting_detects_one_edit_brand_impersonation_but_not_the_brand():
    assert url_analyser.is_typosquatting("gooogle.example")
    assert not url_analyser.is_typosquatting("google.com")


def test_feature_extraction_marks_suspicious_tld_and_not_trusted_tld():
    suspicious = url_analyser._extract_url_features("https://career.example.xyz/apply")
    trusted = url_analyser._extract_url_features("https://careers.example.com/apply")

    assert suspicious["is_suspicious_tld"] == 1
    assert suspicious["is_trusted_tld"] == 0
    assert trusted["is_suspicious_tld"] == 0


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://192.168.1.50/jobs", 1),
        ("https://example.com/jobs", 0),
        ("https://999.999.999.999/jobs", 1),
    ],
)
def test_ip_address_regex_feature(url, expected):
    assert url_analyser._extract_url_features(url)["is_ip_address"] == expected


@pytest.mark.asyncio
async def test_page_content_analysis_extracts_scam_and_form_signals(monkeypatch):
    html = """
    <html><title>Earn Money Fast</title><meta name='description' content='registration fee required'>
    <body>earn money registration fee urgent apply now pay deposit <form><input type='password'></form>
    <a href='https://evil.example/x'>outside</a></body></html>
    """
    class Response:
        status_code, text = 200, html
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr(url_analyser.httpx, "AsyncClient", lambda **kwargs: Client())
    result = await url_analyser._fetch_page_content("https://example.com/jobs")

    assert result.fetched and result.title == "Earn Money Fast"
    assert result.has_form and result.has_login_form and result.external_link_count == 1
    assert result.scam_keyword_count >= 1 and result.content_risk_score > 0


def test_url_trust_score_compounds_real_red_flags_and_explains_each_one():
    score, flags = url_analyser.compute_url_trust_score(
        is_https=False, ssl_valid=False, ssl_expiry_days=None, domain_age_days=10,
        is_free_hosting=True, is_url_shortener=True, has_ip_address=True,
        is_likely_typosquatting=True, has_random_subdomain=True,
        redirect_chain_length=5, google_safe_browsing_clean=False,
        virustotal_malicious_count=4, page_fraud_signal_count=3, http_status=404,
        ml_fraud_probability=0.10, url="http://192.168.1.5/pay",
    )
    assert score == pytest.approx(0.04)
    assert len(flags) >= 10
    assert any("raw IP" in flag for flag in flags)
    assert any("Google Safe Browsing" in flag for flag in flags)


@pytest.mark.asyncio
async def test_analyse_url_assembles_result_from_all_injected_live_checks(monkeypatch):
    async def redirects(url): return url, [url, url]
    async def safe(url): return True
    async def vt(url): return 0
    async def content(url): return url_analyser.PageContentSignals(fetched=True, scam_keyword_count=1, payment_keyword_count=1)
    features = {"is_free_hosting": 0, "is_url_shortener": 0, "is_ip_address": 0, "is_likely_typosquatting": 0}
    monkeypatch.setattr(url_analyser, "follow_redirects", redirects)
    monkeypatch.setattr(url_analyser, "check_google_safe_browsing", safe)
    monkeypatch.setattr(url_analyser, "check_virustotal", vt)
    monkeypatch.setattr(url_analyser, "_fetch_page_content", content)
    monkeypatch.setattr(url_analyser, "_extract_url_features", lambda url: features)
    monkeypatch.setattr(url_analyser, "_detect_random_subdomain", lambda url: False)
    monkeypatch.setattr(url_analyser, "_ml_classify_url", lambda url: 0.10)

    result = await url_analyser.analyse_url("http://google.com/jobs")
    assert result.ml_classifier_available is True
    assert result.is_established_domain is True
    assert result.page_content_signals["payment_keyword_count"] == 1
    assert result.url_trust_score < 0.9


@pytest.mark.asyncio
async def test_threat_intel_and_redirect_helpers_handle_keys_and_transport_failures(monkeypatch):
    monkeypatch.setattr(url_analyser.settings, "GOOGLE_SAFE_BROWSING_API_KEY", "key")
    monkeypatch.setattr(url_analyser.settings, "VIRUSTOTAL_API_KEY", "key")
    class Response:
        def __init__(self, data, url="https://final.example"):
            self._data, self.url, self.history = data, url, [SimpleNamespace(url="https://middle.example")]
        def json(self): return self._data
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return Response({"matches": [{}]})
        async def get(self, *args, **kwargs): return Response({"data": {"attributes": {"last_analysis_stats": {"malicious": 3}}}})
    monkeypatch.setattr(url_analyser.httpx, "AsyncClient", lambda **kwargs: Client())
    assert await url_analyser.check_google_safe_browsing("https://example.com") is False
    assert await url_analyser.check_virustotal("https://example.com") == 3
    final, chain = await url_analyser.follow_redirects("https://start.example")
    assert final == "https://final.example" and len(chain) == 3


@pytest.mark.parametrize("url,expected", [
    ("https://jobs.example.com", False),
    ("https://ab1234cd.example.com", True),
    ("https://very-long-random-looking-sub-domain.example.com", True),
])
def test_random_subdomain_detection_uses_structure_not_known_career_names(url, expected):
    assert url_analyser._detect_random_subdomain(url) is expected


def test_url_classifier_loader_and_ensemble_prediction(monkeypatch, tmp_path):
    model_dir = tmp_path / "url-model"
    model_dir.mkdir()
    (model_dir / "model_info.json").write_text(json.dumps({"trained": True, "ensemble_weights": {"xgb": .6, "lgb": .4}}))
    for filename, obj in [("xgb_model.pkl", _Classifier(.2)), ("lgb_model.pkl", _Classifier(.5)), ("scaler.pkl", _Scaler())]:
        with open(model_dir / filename, "wb") as handle:
            pickle.dump(obj, handle)
    (model_dir / "feature_names.json").write_text(json.dumps(["is_https", "url_length"]))
    monkeypatch.setattr(url_analyser.settings, "URL_CLASSIFIER_PATH", str(model_dir))
    url_analyser._ml_model_cache.clear()
    loaded = url_analyser._load_url_classifier()
    assert loaded["loaded"] is True
    assert url_analyser._ml_classify_url("https://example.com") == pytest.approx(.32)


def test_url_classifier_missing_or_bad_model_degrades_to_none(monkeypatch, tmp_path):
    monkeypatch.setattr(url_analyser.settings, "URL_CLASSIFIER_PATH", str(tmp_path / "missing"))
    url_analyser._ml_model_cache.clear()
    assert url_analyser._load_url_classifier()["loaded"] is False
    assert url_analyser._ml_classify_url("https://example.com") is None


def test_url_trust_score_handles_ssl_age_and_single_page_signal_bands():
    score, flags = url_analyser.compute_url_trust_score(
        is_https=True, ssl_valid=False, ssl_expiry_days=None, domain_age_days=60,
        is_free_hosting=False, is_url_shortener=False, has_ip_address=False,
        is_likely_typosquatting=False, has_random_subdomain=False,
        redirect_chain_length=1, google_safe_browsing_clean=None,
        virustotal_malicious_count=None, page_fraud_signal_count=1, http_status=None,
        ml_fraud_probability=.10,
    )
    assert score < .9
    assert any("SSL certificate" in flag for flag in flags)
    assert any("known fraud language pattern" in flag for flag in flags)
