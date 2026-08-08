"""Tests for the additive, fully mocked OpenAI evidence-agent layer."""
from types import SimpleNamespace

import pytest

from backend.services import agent_tools, explainer, investigator_agent
from backend.models.job_scan import FraudReport, JobScan
from backend.services.trust_scorer import TrustScoreResult


def _trust_result(verdict="SUSPICIOUS"):
    return TrustScoreResult(
        trust_score=58,
        verdict=verdict,
        verdict_color="yellow",
        confidence=0.8,
        effective_signals=3,
        recommendation="Verify independently.",
        all_flags=["Domain is recently registered"],
        signal_scores={"URL Analysis": 55},
        signal_weights={"URL Analysis": 1.0},
        configured_weights={"URL Analysis": 0.35},
        explanation_context={},
        model_trained=False,
    )


@pytest.mark.asyncio
async def test_agent_tools_wrap_existing_domain_and_company_services(monkeypatch):
    async def analyse(url):
        assert url == "https://example.com"
        return SimpleNamespace(
            domain="example.com", domain_age_days=12, ssl_valid=True,
            is_established_domain=False, url_trust_score=0.42, flags=["Recent domain"],
        )

    async def company(**kwargs):
        assert kwargs["company_name"] == "Example"
        assert kwargs["company_domain"] == "example.com"
        return SimpleNamespace(
            company_name="Example", registry_used="Registry", is_registered=False,
            company_status=None, company_trust_score=0.3, flags=["Not found"],
        )

    monkeypatch.setattr(agent_tools, "analyse_url", analyse)
    monkeypatch.setattr(agent_tools, "verify_company_global", company)

    domain = await agent_tools.check_domain_evidence("https://www.example.com/jobs")
    registry = await agent_tools.check_company_registry("Example", "www.example.com")

    assert domain["domain_age_days"] == 12 and domain["flags"] == ["Recent domain"]
    assert registry["registry_used"] == "Registry" and registry["is_registered"] is False


@pytest.mark.asyncio
async def test_prior_report_tool_and_dispatcher_return_structured_evidence(db_session):
    db_session.add(JobScan(
        id="scan-example", url="https://jobs.example.com/role", job_title="Engineer",
        company_name="Example Co", description="role", trust_score=40, verdict="SUSPICIOUS",
    ))
    db_session.add(FraudReport(
        id="report-example", scan_id="scan-example", reason="Asked for a fee", confirmed=1,
    ))
    db_session.commit()

    reports = agent_tools.check_prior_reports("example", db_session)
    missing_term = agent_tools.check_prior_reports("", db_session)
    missing_store = agent_tools.check_prior_reports("example", None)
    unsupported = await agent_tools.execute_agent_tool("not_a_tool", {}, db_session)

    assert reports["report_count"] == 1 and reports["confirmed_count"] == 1
    assert reports["recent_reasons"] == ["Asked for a fee"]
    assert missing_term["available"] is False and missing_store["available"] is False
    assert unsupported["available"] is False and "Unsupported" in unsupported["reason"]


@pytest.mark.asyncio
async def test_tool_calling_explainer_retries_once_after_critic_rejects_claim(monkeypatch):
    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(explainer.settings, "OPENAI_API_KEY", "test-key")
    calls = []
    responses = iter([
        {"choices": [{"message": {"tool_calls": [{
            "id": "call-domain", "function": {
                "name": "check_domain_evidence", "arguments": '{"domain":"example.com"}'
            }
        }]}}]},
        {"choices": [{"message": {"content": "The company is definitely fraudulent."}}]},
        {"choices": [{"message": {"content": '{"approved": false, "unsupported_claims": ["No evidence proves fraud."]}'}}]},
        {"choices": [{"message": {"content": "The signals warrant caution and independent verification."}}]},
        {"choices": [{"message": {"content": '{"approved": true, "unsupported_claims": []}'}}]},
    ])

    async def openai(payload):
        calls.append(payload)
        return next(responses)

    async def tool(name, arguments, db):
        assert (name, arguments) == ("check_domain_evidence", {"domain": "example.com"})
        return {"available": True, "domain_age_days": 12, "flags": ["Recent domain"]}

    monkeypatch.setattr(explainer, "_openai_chat", openai)
    monkeypatch.setattr(explainer, "execute_agent_tool", tool)

    result = await explainer.generate_agentic_explanation(
        _trust_result(), company_name="Example", company_domain="example.com"
    )

    assert result.critic_passed is True
    assert result.explanation.startswith("The signals warrant caution")
    assert result.tools_called[0]["name"] == "check_domain_evidence"
    assert [step["approved"] for step in result.reasoning_steps if step["action"] == "critic_review"] == [False, True]
    assert "No evidence proves fraud" in calls[3]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_tool_loop_accepts_a_final_answer_after_three_tool_rounds(monkeypatch):
    tool_response = {
        "choices": [{"message": {"tool_calls": [{
            "id": "call-domain", "function": {
                "name": "check_domain_evidence", "arguments": '{"domain":"example.com"}'
            }
        }]}}]
    }
    responses = iter([tool_response, tool_response, tool_response, {
        "choices": [{"message": {"content": "Evidence supports proceeding cautiously."}}]
    }])

    async def openai(payload):
        return next(responses)

    monkeypatch.setattr(explainer, "_openai_chat", openai)
    monkeypatch.setattr(
        explainer, "execute_agent_tool", lambda *args: _async({"available": True})
    )

    explanation, tools_called, _ = await explainer.run_tool_enabled_completion(
        system_prompt="system", user_prompt="assessment", db=None
    )

    assert explanation == "Evidence supports proceeding cautiously."
    assert len(tools_called) == 3


@pytest.mark.asyncio
async def test_non_converging_tool_loop_hits_hard_cap_and_uses_fallback(monkeypatch):
    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(explainer.settings, "OPENAI_API_KEY", "test-key")
    tool_response = {
        "choices": [{"message": {"tool_calls": [{
            "id": "call-domain", "function": {
                "name": "check_domain_evidence", "arguments": '{"domain":"example.com"}'
            }
        }]}}]
    }
    calls = 0

    async def openai(payload):
        nonlocal calls
        calls += 1
        return tool_response

    monkeypatch.setattr(explainer, "_openai_chat", openai)
    monkeypatch.setattr(
        explainer, "execute_agent_tool", lambda *args: _async({"available": True})
    )
    fallback = "Rule-based fallback."
    monkeypatch.setattr(explainer, "_fallback_explanation", lambda result: fallback)

    result = await explainer.generate_agentic_explanation(_trust_result())

    assert result.explanation == fallback
    assert result.critic_passed is False and result.used_agent is True
    assert len(result.tools_called) == explainer.MAX_TOOL_ITERATIONS
    # A sixth tool request proves the agent did not produce a final answer after the cap rounds.
    assert calls == explainer.MAX_TOOL_ITERATIONS + 1


@pytest.mark.asyncio
async def test_ollama_and_missing_key_use_static_explainer_without_agent_trace(monkeypatch):
    monkeypatch.setattr(explainer.settings, "LLM_PROVIDER", "ollama")
    monkeypatch.setattr(explainer.settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(explainer, "generate_explanation", lambda *args: _async("static explanation"))
    monkeypatch.setattr(explainer, "_openai_chat", _fail_openai)

    result = await explainer.generate_agentic_explanation(_trust_result())

    assert result.explanation == "static explanation"
    assert result.used_agent is False and result.tools_called == []


@pytest.mark.asyncio
async def test_investigator_only_runs_for_suspicious_verdict(monkeypatch):
    monkeypatch.setattr(investigator_agent, "is_openai_agent_available", lambda: True)
    monkeypatch.setattr(
        investigator_agent,
        "run_tool_enabled_completion",
        lambda **kwargs: _async((
            '{"investigator_confidence": 0.82, "summary": "Registry result needs review."}',
            [{"name": "check_company_registry", "arguments": {}, "result": {"available": True}}],
            [{"action": "tool_called", "tool": "check_company_registry"}],
        )),
    )

    suspicious = await investigator_agent.investigate_suspicious(
        _trust_result(), company_name="Example", company_domain="example.com", db=None
    )
    safe = await investigator_agent.investigate_suspicious(
        _trust_result("SAFE"), company_name="Example", company_domain="example.com", db=None
    )

    assert suspicious.investigator_confidence == 0.82
    assert suspicious.additional_evidence[0]["summary"].startswith("Registry")
    assert safe is None


async def _async(value):
    return value


async def _fail_openai(*args, **kwargs):
    raise AssertionError("OpenAI should not be called on the static path")
