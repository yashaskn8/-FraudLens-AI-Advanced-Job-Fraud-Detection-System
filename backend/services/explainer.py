"""
LLM Explanation Generator
Uses a local Mistral-7B (via Ollama) or cloud LLM to generate plain-English
explanations of why a job posting was flagged.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.services.agent_tools import OPENAI_TOOL_DEFINITIONS, execute_agent_tool
from backend.services.trust_scorer import TrustScoreResult

logger = logging.getLogger("trusthire.explainer")

MAX_TOOL_ITERATIONS = 5


class ToolIterationLimitExceeded(RuntimeError):
    """Raised only after the independent tool-round safety cap is reached."""

    def __init__(
        self,
        tools_called: list[dict[str, Any]],
        reasoning_steps: list[dict[str, Any]],
    ) -> None:
        super().__init__("OpenAI tool loop did not converge")
        self.tools_called = tools_called
        self.reasoning_steps = reasoning_steps

EXPLANATION_PROMPT = """You are TrustHire, an AI fraud detection system for job postings.
A job posting has been analysed and produced the following fraud signals.

Trust Score: {trust_score}/100 ({verdict})
Flags detected:
{flags_text}

Job Title: {job_title}
Company: {company_name}

Write a clear, professional, 3–4 paragraph explanation for a job seeker explaining:
1. What the overall assessment means for them
2. The 2–3 most important red flags and why they matter
3. What specific actions they should take next

Be direct but not alarmist. Use simple language. Do not use bullet points — write in flowing paragraphs.
Do not repeat the technical flag text verbatim — explain the implications in human terms."""


AGENT_SYSTEM_PROMPT = """You are TrustHire's evidence-aware explanation agent. Explain a
completed job-fraud assessment in plain language. The deterministic score and verdict are
authoritative: do not modify or second-guess them. You may choose from the listed tools if
they will clarify an ambiguous fact. Do not state that a fact was verified unless it appears
in a tool result or in the supplied assessment. Do not claim that an employer is fraudulent
solely because no registry or community-report result is available."""

CRITIC_SYSTEM_PROMPT = """You are an evidence critic for a job-fraud explanation. Compare
the proposed explanation with the supplied score, flags, and tool results. Reject claims
that are unsupported by those inputs, including claims that an external check was run when
there is no matching tool result. Respond only as JSON:
{"approved": true|false, "unsupported_claims": ["brief reason"]}."""


@dataclass
class AgentExplanationResult:
    explanation: str
    tools_called: list[dict[str, Any]] = field(default_factory=list)
    reasoning_steps: list[dict[str, Any]] = field(default_factory=list)
    critic_passed: bool | None = None
    used_agent: bool = False


def is_openai_agent_available() -> bool:
    """The agentic path is opt-in and never replaces local Ollama."""
    return settings.LLM_PROVIDER.lower() == "openai" and bool(settings.OPENAI_API_KEY.strip())


async def _openai_chat(payload: dict[str, Any]) -> dict[str, Any]:
    """Make one OpenAI Chat Completions request for the function-call loop."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
            json={"model": "gpt-4o-mini", **payload},
        )
        return response.json()


def _choice_message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise ValueError("OpenAI returned no completion choices")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenAI completion did not contain a message")
    return message


async def run_tool_enabled_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    db: Session | None,
    retry_instruction: str = "",
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """Run an OpenAI tool loop and record actions, not model chain-of-thought."""
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    if retry_instruction:
        messages.append({"role": "user", "content": retry_instruction})

    request = {
        "messages": messages,
        "tools": OPENAI_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "temperature": 0.2,
        "max_tokens": 700,
    }
    response = await _openai_chat(request)
    tools_called: list[dict[str, Any]] = []
    reasoning_steps: list[dict[str, Any]] = []

    tool_iterations = 0
    while True:
        message = _choice_message(response)
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            content = message.get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("OpenAI returned an empty final explanation")
            return content.strip(), tools_called, reasoning_steps

        if tool_iterations >= MAX_TOOL_ITERATIONS:
            logger.warning(
                "Tool loop reached MAX_TOOL_ITERATIONS=%s without a final answer",
                MAX_TOOL_ITERATIONS,
            )
            raise ToolIterationLimitExceeded(tools_called, reasoning_steps)
        tool_iterations += 1

        messages.append({
            "role": "assistant",
            "content": message.get("content") or "",
            "tool_calls": tool_calls,
        })
        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            name = function.get("name", "")
            try:
                arguments = json.loads(function.get("arguments") or "{}")
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                arguments = {}
                result = {"available": False, "reason": f"Invalid tool arguments: {exc}"}
            else:
                result = await execute_agent_tool(name, arguments, db)

            tools_called.append({"name": name, "arguments": arguments, "result": result})
            reasoning_steps.append({"action": "tool_called", "tool": name})
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": json.dumps(result),
            })

        response = await _openai_chat(request)



async def _critic_explanation(
    *,
    explanation: str,
    trust_result: TrustScoreResult,
    tools_called: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """Reject unsupported prose before it reaches a user."""
    evidence = {
        "trust_score": trust_result.trust_score,
        "verdict": trust_result.verdict,
        "flags": trust_result.all_flags,
        "tool_results": tools_called,
        "proposed_explanation": explanation,
    }
    response = await _openai_chat({
        "messages": [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(evidence)},
        ],
        "temperature": 0,
        "max_tokens": 250,
        "response_format": {"type": "json_object"},
    })
    payload = json.loads(_choice_message(response).get("content") or "{}")
    claims = payload.get("unsupported_claims") or []
    if not isinstance(claims, list):
        claims = ["Critic response used an invalid unsupported_claims value."]
    return payload.get("approved") is True, [str(claim) for claim in claims]


async def generate_agentic_explanation(
    trust_result: TrustScoreResult,
    job_title: str = "",
    company_name: str = "",
    company_domain: str = "",
    db: Session | None = None,
    additional_evidence: list[dict[str, Any]] | None = None,
) -> AgentExplanationResult:
    """Use tool calls only for configured OpenAI; retain static behavior otherwise."""
    if not is_openai_agent_available():
        return AgentExplanationResult(
            explanation=await generate_explanation(trust_result, job_title, company_name)
        )

    context = {
        "trust_score": trust_result.trust_score,
        "verdict": trust_result.verdict,
        "confidence": trust_result.confidence,
        "flags": trust_result.all_flags,
        "explanation_context": trust_result.explanation_context,
        "job_title": job_title,
        "company_name": company_name,
        "company_domain": company_domain,
        "additional_evidence": additional_evidence or [],
    }
    all_tools: list[dict[str, Any]] = []
    all_steps: list[dict[str, Any]] = []
    rejection_reasons: list[str] = []

    for attempt in range(2):
        retry_instruction = ""
        if attempt:
            retry_instruction = (
                "Regenerate using only supplied evidence. Avoid these critic-identified unsupported "
                f"claims: {json.dumps(rejection_reasons)}"
            )
        try:
            explanation, tools_called, reasoning_steps = await run_tool_enabled_completion(
                system_prompt=AGENT_SYSTEM_PROMPT,
                user_prompt=json.dumps(context),
                db=db,
                retry_instruction=retry_instruction,
            )
            all_tools.extend(tools_called)
            all_steps.extend(reasoning_steps)
            approved, claims = await _critic_explanation(
                explanation=explanation,
                trust_result=trust_result,
                tools_called=all_tools,
            )
            all_steps.append({"action": "critic_review", "approved": approved})
            if approved:
                return AgentExplanationResult(
                    explanation, all_tools, all_steps, critic_passed=True, used_agent=True
                )
            rejection_reasons = claims or ["The critic could not verify the explanation."]
        except Exception as exc:
            if isinstance(exc, ToolIterationLimitExceeded):
                logger.warning("Returning rule-based explanation after tool-loop safety cap")
                all_tools.extend(exc.tools_called)
                all_steps.extend(exc.reasoning_steps)
                return AgentExplanationResult(
                    _fallback_explanation(trust_result), all_tools, all_steps,
                    critic_passed=False, used_agent=True,
                )
            rejection_reasons = [f"Agent or critic failure: {exc}"]
            all_steps.append({"action": "critic_review", "approved": False})
        logger.warning("Explanation critic rejected attempt %s: %s", attempt + 1, rejection_reasons)

    return AgentExplanationResult(
        _fallback_explanation(trust_result), all_tools, all_steps,
        critic_passed=False, used_agent=True,
    )


async def generate_explanation(
    trust_result: TrustScoreResult,
    job_title: str = "",
    company_name: str = "",
) -> str:
    """
    Generate a plain-English explanation of the fraud analysis.
    Uses Ollama (local, free) by default. Falls back to OpenAI if configured.
    """
    flags_text = "\n".join(f"- {flag}" for flag in trust_result.all_flags[:10])

    prompt = EXPLANATION_PROMPT.format(
        trust_score=trust_result.trust_score,
        verdict=trust_result.verdict,
        flags_text=flags_text or "No specific flags detected.",
        job_title=job_title or "Unknown position",
        company_name=company_name or "Unknown company",
    )

    if settings.LLM_PROVIDER == "ollama":
        return await _call_ollama(prompt)
    elif settings.LLM_PROVIDER == "openai":
        return await _call_openai(prompt)
    else:
        return _fallback_explanation(trust_result)


async def _call_ollama(prompt: str) -> str:
    """Call local Ollama instance (free, runs on your machine)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            return response.json().get("response", _fallback_explanation(None))
        except Exception:
            return _fallback_explanation(None)


async def _call_openai(prompt: str) -> str:
    """Call OpenAI API (paid, higher quality)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 600,
                },
            )
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            return _fallback_explanation(None)


def _fallback_explanation(trust_result) -> str:
    """Rule-based fallback when LLM is unavailable."""
    if trust_result is None:
        return (
            "Our analysis is complete. Based on the signals detected, please review the "
            "individual flag descriptions above for a detailed understanding of potential "
            "risks. As a general precaution, always verify a company's legitimacy through "
            "official channels before sharing personal information or financial details. "
            "Never pay upfront fees for job applications, and be wary of postings that "
            "promise unrealistic earnings or require minimal qualifications."
        )

    score = trust_result.trust_score if trust_result else 50
    if score >= 75:
        return (
            "This job posting has passed our automated fraud checks. The URL appears "
            "legitimate, the company description is coherent, and no known scam patterns "
            "were detected. As always, verify the company through independent channels "
            "before submitting your application or sharing personal documents."
        )
    elif score >= 50:
        return (
            "This posting has raised some concerns. While it may be legitimate, one or "
            "more signals were unusual. We recommend verifying the company's registration "
            "independently, checking their official website for the same job posting, and "
            "avoiding any requests for upfront payment. Proceed with caution and do your "
            "own research before applying."
        )
    else:
        return (
            "This posting shows multiple characteristics commonly associated with "
            "fraudulent job listings. We strongly advise against responding to this "
            "posting. Do not pay any fees, share bank details, or submit identity "
            "documents like Aadhaar or PAN. If you have already shared such information, "
            "consider reporting to cybercrime.gov.in and monitoring your accounts."
        )
