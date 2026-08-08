"""Narrow, auditable adapters around TrustHire's existing evidence services."""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.models.job_scan import FraudReport, JobScan
from backend.services.company_verifier import verify_company_global
from backend.services.url_analyser import analyse_url


OPENAI_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_domain_evidence",
            "description": "Check existing URL-analysis evidence, including domain age and SSL status.",
            "parameters": {
                "type": "object",
                "properties": {"domain": {"type": "string"}},
                "required": ["domain"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_company_registry",
            "description": "Run the existing company-verification and registry checks for an employer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "domain": {"type": "string"},
                },
                "required": ["name", "domain"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_prior_reports",
            "description": "Look for existing community fraud reports linked to the employer name or domain.",
            "parameters": {
                "type": "object",
                "properties": {"company_name_or_domain": {"type": "string"}},
                "required": ["company_name_or_domain"],
                "additionalProperties": False,
            },
        },
    },
]


def _normalise_domain(domain: str) -> str:
    """Accept a domain or URL, returning only a safe hostname for existing services."""
    value = (domain or "").strip().lower()
    if not value:
        return ""
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").removeprefix("www.")


async def check_domain_evidence(domain: str) -> dict[str, Any]:
    """Expose selected output from the existing URL analyser (including WHOIS logic)."""
    hostname = _normalise_domain(domain)
    if not hostname:
        return {"available": False, "reason": "No domain was supplied."}

    try:
        result = await analyse_url(f"https://{hostname}")
    except Exception as exc:
        return {"available": False, "domain": hostname, "reason": f"Domain check unavailable: {exc}"}

    return {
        "available": True,
        "domain": result.domain,
        "domain_age_days": result.domain_age_days,
        "ssl_valid": result.ssl_valid,
        "is_established_domain": result.is_established_domain,
        "url_trust_score": result.url_trust_score,
        "flags": result.flags,
    }


async def check_company_registry(name: str, domain: str) -> dict[str, Any]:
    """Expose selected output from the existing company verification service."""
    hostname = _normalise_domain(domain)
    if not (name or hostname):
        return {"available": False, "reason": "No company name or domain was supplied."}

    try:
        result = await verify_company_global(
            company_name=(name or "").strip(),
            company_domain=hostname,
            url=f"https://{hostname}" if hostname else "",
        )
    except Exception as exc:
        return {"available": False, "reason": f"Company registry check unavailable: {exc}"}

    return {
        "available": True,
        "company_name": result.company_name,
        "registry_used": result.registry_used,
        "is_registered": result.is_registered,
        "company_status": result.company_status,
        "company_trust_score": result.company_trust_score,
        "flags": result.flags,
    }


def check_prior_reports(company_name_or_domain: str, db: Session | None) -> dict[str, Any]:
    """Query the existing community reports associated with matching saved scans."""
    needle = (company_name_or_domain or "").strip()
    if not needle:
        return {"available": False, "reason": "No company name or domain was supplied."}
    if db is None:
        return {"available": False, "reason": "Community report store is unavailable."}

    pattern = f"%{needle.lower()}%"
    reports = (
        db.query(FraudReport)
        .join(JobScan, FraudReport.scan_id == JobScan.id)
        .filter(
            or_(
                func.lower(JobScan.company_name).like(pattern),
                func.lower(JobScan.url).like(pattern),
            )
        )
        .order_by(FraudReport.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "available": True,
        "match_term": needle,
        "report_count": len(reports),
        "confirmed_count": sum(1 for report in reports if report.confirmed),
        "recent_reasons": [report.reason for report in reports if report.reason][:5],
    }


async def execute_agent_tool(name: str, arguments: dict[str, Any], db: Session | None) -> dict[str, Any]:
    """Dispatch only the three declared tools and return JSON-serialisable output."""
    if name == "check_domain_evidence":
        return await check_domain_evidence(str(arguments.get("domain", "")))
    if name == "check_company_registry":
        return await check_company_registry(
            str(arguments.get("name", "")), str(arguments.get("domain", ""))
        )
    if name == "check_prior_reports":
        return check_prior_reports(str(arguments.get("company_name_or_domain", "")), db)
    return {"available": False, "reason": f"Unsupported tool requested: {name}"}
