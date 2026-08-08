"""Tests for security controls added around user-supplied URLs and settings."""
import os
import subprocess
import sys

import pytest

from backend.security import ssrf_guard
from backend.services import job_relevance_detector, url_analyser


def test_ssrf_guard_allows_a_publicly_resolved_hostname(monkeypatch):
    monkeypatch.setattr(
        ssrf_guard,
        "resolve_hostname",
        lambda hostname: {"93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"},
    )

    assert ssrf_guard.validate_public_url("https://jobs.example.test/apply") == "https://jobs.example.test/apply"


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:8000/health",
        "http://10.0.0.5/internal",
        "http://172.16.0.1/internal",
        "http://192.168.1.5/internal",
        "http://[::1]/internal",
    ],
)
def test_ssrf_guard_rejects_private_and_reserved_addresses(url):
    with pytest.raises(ssrf_guard.UnsafeURL):
        ssrf_guard.validate_public_url(url)


@pytest.mark.asyncio
async def test_ssrf_guard_rejects_a_private_redirect_before_requesting_it(monkeypatch):
    monkeypatch.setattr(ssrf_guard, "resolve_hostname", lambda hostname: {"93.184.216.34"})

    class RedirectResponse:
        status_code = 302
        headers = {"location": "http://169.254.169.254/latest/meta-data/"}
        url = "https://public.example.test/continue"
        history = []

    class Client:
        calls = []

        async def get(self, url, **kwargs):
            self.calls.append(url)
            return RedirectResponse()

    client = Client()
    with pytest.raises(ssrf_guard.UnsafeURL):
        await ssrf_guard.get_with_validated_redirects(client, "https://public.example.test/continue")

    assert client.calls == ["https://public.example.test/continue"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fetcher, expected",
    [
        (url_analyser._fetch_page_content, False),
        (job_relevance_detector._fetch_page_sample, (None, None, None)),
    ],
)
async def test_user_url_fetchers_block_private_addresses_before_http(fetcher, expected, monkeypatch):
    calls = []

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            calls.append(url)
            raise AssertionError("A blocked URL must never be requested")

    monkeypatch.setattr(url_analyser.httpx, "AsyncClient", lambda **kwargs: Client())
    monkeypatch.setattr(job_relevance_detector.httpx, "AsyncClient", lambda **kwargs: Client())

    result = await fetcher("http://127.0.0.1:8000/admin")

    assert calls == []
    if expected is False:
        assert result.fetched is False
    else:
        assert result == expected


@pytest.mark.parametrize(
    "secret_key",
    [
        "your-secret-key-change-in-production",
        "change-this-to-a-secure-random-string-in-production",
    ],
)
def test_production_startup_rejects_insecure_secret_keys(secret_key):
    environment = os.environ.copy()
    environment["SECRET_KEY"] = secret_key
    environment["DEBUG"] = "false"
    result = subprocess.run(
        [sys.executable, "-c", "from backend.config import settings"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "SECRET_KEY must be set to a non-default value" in result.stderr


def test_cors_middleware_reads_allowed_origins_from_settings():
    from backend.config import settings
    from backend.main import app
    from fastapi.middleware.cors import CORSMiddleware

    cors = next(
        middleware for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    assert cors.kwargs["allow_origins"] is settings.ALLOWED_ORIGINS
