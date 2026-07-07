"""
LLM Explanation Generator
Uses a local Mistral-7B (via Ollama) or cloud LLM to generate plain-English
explanations of why a job posting was flagged.
"""
import httpx
from backend.config import settings
from backend.services.trust_scorer import TrustScoreResult

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
