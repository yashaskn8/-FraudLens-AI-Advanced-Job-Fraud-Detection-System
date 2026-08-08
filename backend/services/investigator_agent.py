"""Evidence-gathering agent for suspicious (and only suspicious) scan results."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from backend.services.explainer import is_openai_agent_available, run_tool_enabled_completion
from backend.services.trust_scorer import TrustScoreResult

logger = logging.getLogger("trusthire.investigator")

INVESTIGATOR_PROMPT = """You are TrustHire's investigator. The deterministic trust score
has already classified this posting as SUSPICIOUS. You must not change its score or verdict.
Use the available tools only when they would resolve an uncertainty. Return JSON only with:
{
  "investigator_confidence": number from 0 to 1,
  "summary": "short evidence-based summary"
}
Do not claim a check was run unless its tool result is present."""


@dataclass
class InvestigatorResult:
    additional_evidence: list[dict[str, Any]] = field(default_factory=list)
    investigator_confidence: float | None = None
    tools_called: list[dict[str, Any]] = field(default_factory=list)
    reasoning_steps: list[dict[str, Any]] = field(default_factory=list)


async def investigate_suspicious(
    trust_result: TrustScoreResult,
    *,
    company_name: str,
    company_domain: str,
    db: Session | None,
) -> InvestigatorResult | None:
    """Gather optional supporting evidence without affecting deterministic scoring."""
    # Boundary: this agent may add evidence only; scorer output is never altered here.
    if trust_result.verdict != "SUSPICIOUS" or not is_openai_agent_available():
        return None

    context = {
        "trust_score": trust_result.trust_score,
        "verdict": trust_result.verdict,
        "confidence": trust_result.confidence,
        "flags": trust_result.all_flags,
        "company_name": company_name,
        "company_domain": company_domain,
    }
    try:
        content, tools_called, reasoning_steps = await run_tool_enabled_completion(
            system_prompt=INVESTIGATOR_PROMPT,
            user_prompt=json.dumps(context),
            db=db,
        )
        payload = json.loads(content or "{}")
        confidence = payload.get("investigator_confidence")
        if not isinstance(confidence, (int, float)):
            confidence = None
        else:
            confidence = max(0.0, min(1.0, float(confidence)))
        evidence = [{"summary": payload["summary"]}] if isinstance(payload.get("summary"), str) else []
        evidence.extend(call["result"] for call in tools_called)
        return InvestigatorResult(evidence, confidence, tools_called, reasoning_steps)
    except Exception:
        logger.exception("Suspicious-scan investigator failed; continuing without agent evidence")
        return None
