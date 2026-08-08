"""
Scan Router — handles job scanning API endpoints.
"""
import uuid
import re
import json
import asyncio
import time
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import tldextract
from backend.database import get_db
from backend.schemas.scan import ScanRequest, ScanResponse
from backend.services.url_analyser import analyse_url
from backend.services.nlp_classifier import classify_description
from backend.services.company_verifier import verify_company_global
from backend.services.trust_scorer import compute_trust_score
from backend.services.explainer import (
    generate_agentic_explanation,
    generate_explanation,
    is_openai_agent_available,
)
from backend.services.investigator_agent import investigate_suspicious
from backend.services.url_cache import get_cached_result, cache_result, get_cache_stats
from backend.services.job_relevance_detector import detect_job_relevance
from backend.models.job_scan import AgentTrace, JobScan
from backend.config import settings
from backend.rate_limiter import limiter
from backend.routers.auth import get_current_user, get_optional_current_user

router = APIRouter(prefix="/api/v1", tags=["scan"])

# ── Well-known domain → company name mapping ─────────────────────────────────
DOMAIN_TO_NAME = {
    "accenture": "Accenture", "infosys": "Infosys",
    "wipro": "Wipro", "tcs": "Tata Consultancy Services",
    "cognizant": "Cognizant", "hcltech": "HCL Technologies",
    "capgemini": "Capgemini", "ibm": "IBM", "oracle": "Oracle",
    "google": "Google", "microsoft": "Microsoft",
    "amazon": "Amazon", "apple": "Apple", "meta": "Meta",
    "bbc": "BBC", "hsbc": "HSBC", "barclays": "Barclays",
    "commbank": "Commonwealth Bank", "westpac": "Westpac",
    "shopify": "Shopify", "sap": "SAP", "siemens": "Siemens",
    "grab": "Grab", "dbs": "DBS Bank", "emirates": "Emirates",
    "naukri": "Naukri", "linkedin": "LinkedIn",
    "indeed": "Indeed", "glassdoor": "Glassdoor",
    "netflix": "Netflix", "adobe": "Adobe", "salesforce": "Salesforce",
    "deloitte": "Deloitte", "kpmg": "KPMG", "pwc": "PwC", "ey": "EY",
    "flipkart": "Flipkart", "paytm": "Paytm", "zomato": "Zomato",
    "swiggy": "Swiggy", "zoho": "Zoho", "freshworks": "Freshworks",
}


def extract_all_entities_from_request(request: ScanRequest) -> dict:
    """
    Extracts company domain, company name hint, recruiter email, and job title
    from the submitted request. Prioritises explicit user-provided values,
    then falls back to URL-derived values, then spaCy NER on description.

    This function guarantees that company_domain is never empty when a URL
    is provided — which is the prerequisite for the verified domain fast-pass
    in the company verifier.
    """
    result = {
        "company_domain": "",
        "company_name": "",
        "recruiter_email": "",
        "job_title": "",
    }

    # ── Step 1: Derive company domain from URL (always available) ─────────
    if request.url:
        try:
            ext = tldextract.extract(request.url)
            if ext.domain and ext.suffix:
                result["company_domain"] = f"{ext.domain}.{ext.suffix}".lower()

                # CRITICAL: Only set company name from domain if the root domain
                # is actually the brand's own domain. Never set it from a compound
                # impersonation domain like "google-career-verification.org".
                from backend.services.company_verifier import (
                    BRAND_LEGITIMATE_DOMAINS as _LEGIT_DOMAINS,
                )
                domain_lower = ext.domain.lower()
                root_domain = f"{ext.domain}.{ext.suffix}".lower()

                if domain_lower in DOMAIN_TO_NAME:
                    # Verify this is actually the brand's registered domain
                    legit_list = _LEGIT_DOMAINS.get(domain_lower, [domain_lower + ".com"])
                    if root_domain in legit_list or any(
                        root_domain.endswith("." + ld) for ld in legit_list
                    ):
                        result["company_name"] = DOMAIN_TO_NAME[domain_lower]
                    # If root_domain is NOT in legit list, do NOT set company_name
                    # e.g. "google-career-verification.org" → company_name stays ""
                else:
                    # Not a well-known brand — use domain capitalized as hint
                    result["company_name"] = ext.domain.capitalize()
        except Exception:
            pass

    # ── Step 2: Override with user-provided values if present ─────────────
    if request.company_name and request.company_name.strip():
        result["company_name"] = request.company_name.strip()
    if request.recruiter_email and request.recruiter_email.strip():
        result["recruiter_email"] = request.recruiter_email.strip()
    if request.job_title and request.job_title.strip():
        result["job_title"] = request.job_title.strip()

    # ── Step 3: Extract from description using spaCy NER ─────────────────
    if request.description and len(request.description.strip()) > 20:
        try:
            import spacy
            nlp_spacy = spacy.load("en_core_web_lg")
            doc = nlp_spacy(request.description[:1500])

            # Company name from NER (only if not already set via URL or user)
            if not request.company_name and not result["company_name"]:
                for ent in doc.ents:
                    if ent.label_ == "ORG" and len(ent.text) > 2:
                        result["company_name"] = ent.text
                        break
        except Exception:
            pass

        # Email extraction
        if not result["recruiter_email"]:
            email_match = re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+",
                                     request.description)
            if email_match:
                result["recruiter_email"] = email_match.group()

    # ── Step 4: Derive company_domain from recruiter email if still empty ─
    if not result["company_domain"] and result["recruiter_email"]:
        if "@" in result["recruiter_email"]:
            result["company_domain"] = result["recruiter_email"].split("@")[1]

    return result


@router.post("/scan", response_model=ScanResponse)
@limiter.limit(settings.RATE_LIMIT_FREE)
async def scan_job(
    request: Request,
    scan_request: ScanRequest,
    db: Session = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
):
    """
    Main scan endpoint. Accepts a job URL and/or description.
    Runs the Job Relevance Gate first, then all analysis signals,
    and returns a Trust Score.
    """

    # ── STEP 0: Job Relevance Gate — must pass before any analysis runs ──
    relevance = await detect_job_relevance(
        url=scan_request.url,
        description=scan_request.description
    )

    if not relevance.is_job_content:
        # Return a structured rejection — not an error, not a fraud score.
        return ScanResponse(
            scan_id="not_applicable",
            trust_score=None,
            verdict="NOT_JOB_CONTENT",
            verdict_color="gray",
            confidence=relevance.confidence,
            effective_signals=0,
            recommendation=relevance.rejection_reason,
            flags=[],
            signal_scores={},
            signal_weights={},
            configured_weights={},
            explanation=relevance.rejection_reason,
            explanation_context={
                "detected_type": relevance.detected_type,
                "detected_entity": relevance.detected_entity,
                "suggestions": relevance.suggestions,
            },
            model_trained=False,
            is_job_content=False,
            rejection_reason=relevance.rejection_reason,
            suggestions=relevance.suggestions,
            scanned_at=datetime.utcnow().isoformat()
        )

    # ── STEP 1: Extract all entities from the request ─────────────────────
    # Critical fix: entities are always extracted before any analysis service
    scan_id = str(uuid.uuid4())
    entities = extract_all_entities_from_request(scan_request)

    company_domain  = entities["company_domain"]
    company_name    = entities["company_name"]
    recruiter_email = entities["recruiter_email"]
    job_title       = entities["job_title"]

    # Check URL cache first
    url_result = None
    cached_url = None
    if scan_request.url:
        cached_url = get_cached_result(scan_request.url)

    # Run all analyses concurrently
    url_task = None
    if scan_request.url and not cached_url:
        url_task = analyse_url(scan_request.url)
    nlp_task = classify_description(scan_request.description or "")
    company_task = verify_company_global(
        company_name=company_name,
        company_domain=company_domain,
        url=scan_request.url or "",
        description=scan_request.description or "",
    )

    tasks = [t for t in [url_task, nlp_task, company_task] if t is not None]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Map results back, handling possible None and exceptions
    idx = 0
    if scan_request.url and not cached_url:
        url_result = results[idx] if not isinstance(results[idx], Exception) else None
        idx += 1
        # Cache the fresh result
        if url_result is not None:
            cache_result(
                scan_request.url, url_result.__dict__,
                url_result.url_trust_score,
                getattr(url_result, 'is_established_domain', False)
            )
    elif cached_url:
        # Reconstruct from cache
        from backend.services.url_analyser import URLAnalysisResult
        try:
            url_result = URLAnalysisResult(**{k: v for k, v in cached_url.items()
                                              if k in URLAnalysisResult.__dataclass_fields__})
        except Exception:
            url_result = None
    nlp_result = results[idx] if not isinstance(results[idx], Exception) else None
    idx += 1
    company_result = results[idx] if not isinstance(results[idx], Exception) else None

    # Compute final trust score with dynamic weight redistribution
    trust_result = compute_trust_score(url_result, nlp_result, company_result)

    # The deterministic score above remains authoritative. Agent evidence is additive only.
    investigator_result = None
    agent_explanation = None
    if is_openai_agent_available():
        investigator_result = await investigate_suspicious(
            trust_result,
            company_name=company_name,
            company_domain=company_domain,
            db=db,
        )
        agent_explanation = await generate_agentic_explanation(
            trust_result,
            scan_request.job_title or "",
            company_name,
            company_domain,
            db,
            investigator_result.additional_evidence if investigator_result else None,
        )
        explanation = agent_explanation.explanation
    else:
        # Preserve the established Ollama/missing-key static path unchanged.
        explanation = await generate_explanation(
            trust_result, scan_request.job_title or "", company_name
        )

    # Save to database
    try:
        scan = JobScan(
            id=scan_id,
            user_id=current_user["user_id"] if current_user else None,
            url=scan_request.url or "",
            job_title=scan_request.job_title or "",
            company_name=company_name,
            description=(scan_request.description or "")[:5000],
            trust_score=trust_result.trust_score,
            verdict=trust_result.verdict,
            flags=trust_result.all_flags,
            signal_scores=trust_result.signal_scores,
            explanation=explanation,
            created_at=datetime.utcnow(),
        )
        db.add(scan)
        if agent_explanation and agent_explanation.used_agent:
            investigator_tools = investigator_result.tools_called if investigator_result else []
            investigator_steps = investigator_result.reasoning_steps if investigator_result else []
            tools_called = investigator_tools + agent_explanation.tools_called
            db.add(AgentTrace(
                id=str(uuid.uuid4()),
                scan_id=scan_id,
                tools_called=tools_called,
                tool_results=[call.get("result", {}) for call in tools_called],
                reasoning_steps=investigator_steps + agent_explanation.reasoning_steps,
                critic_passed=agent_explanation.critic_passed,
                created_at=datetime.utcnow(),
            ))
        db.commit()
    except Exception as e:
        print(f"Database save failed: {e}")
        db.rollback()

    return ScanResponse(
        scan_id=scan_id,
        trust_score=trust_result.trust_score,
        verdict=trust_result.verdict,
        verdict_color=trust_result.verdict_color,
        confidence=trust_result.confidence,
        effective_signals=trust_result.effective_signals,
        recommendation=trust_result.recommendation,
        flags=trust_result.all_flags,
        signal_scores=trust_result.signal_scores,
        signal_weights=trust_result.signal_weights,
        configured_weights=trust_result.configured_weights,
        explanation_context=trust_result.explanation_context,
        explanation=explanation,
        model_trained=trust_result.model_trained,
        url_details=url_result.__dict__ if url_result else None,
        nlp_details={
            "bert_fraud_probability": nlp_result.bert_fraud_probability,
            "bert_confidence": nlp_result.bert_confidence,
            "used_trained_model": nlp_result.used_trained_model,
            "model_source": getattr(nlp_result, 'model_source', 'heuristic'),
            "optimal_threshold": nlp_result.optimal_threshold,
            "duplicate_found": nlp_result.duplicate_found,
            "duplicate_similarity": nlp_result.duplicate_similarity,
            "scam_phrases_found": nlp_result.scam_phrases_found,
            "structural_score": nlp_result.structural_score,
            "combined_nlp_score": nlp_result.combined_nlp_score,
        } if nlp_result else None,
        company_details=company_result.__dict__ if company_result else None,
        additional_evidence=(
            investigator_result.additional_evidence if investigator_result else None
        ),
        investigator_confidence=(
            investigator_result.investigator_confidence if investigator_result else None
        ),
        scanned_at=datetime.utcnow().isoformat(),
    )


@router.get("/cache/stats")
async def cache_stats():
    """Return URL cache statistics."""
    return get_cache_stats()


@router.get("/training/status")
async def get_training_status():
    """
    Returns current model training status.
    Used by the UI to show training progress and update NLP badge automatically.
    """
    bert_info_path = Path(settings.BERT_MODEL_PATH) / "model_info.json"
    log_path = Path("logs/training.log")

    bert_trained = False
    bert_info = {}
    try:
        with open(bert_info_path) as f:
            bert_info = json.load(f)
        bert_trained = bert_info.get("trained", False)
    except Exception:
        pass

    training_active = False
    last_log_line = ""
    if log_path.exists():
        try:
            with open(log_path, "rb") as f:
                f.seek(max(0, f.seek(0, 2) - 500))
                last_log_line = f.read().decode("utf-8", errors="ignore").strip().split("\n")[-1]
            training_active = (time.time() - log_path.stat().st_mtime) < 60
        except Exception:
            pass

    return {
        "bert_trained": bert_trained,
        "training_active": training_active,
        "last_log_line": last_log_line,
        "bert_metrics": {
            "test_f1": bert_info.get("test_f1_at_threshold"),
            "test_roc_auc": bert_info.get("test_roc_auc"),
            "optimal_threshold": bert_info.get("optimal_threshold"),
            "trained_at": bert_info.get("trained_at"),
        } if bert_trained else None,
        "baseline_available": (
            Path(settings.BASELINE_MODEL_PATH) / "classifier.pkl"
        ).exists(),
        "faiss_available": Path(settings.FAISS_INDEX_PATH).exists(),
    }


@router.get("/scan/{scan_id}")
async def get_scan_result(scan_id: str, db: Session = Depends(get_db)):
    """Retrieve a previously completed scan by ID."""
    scan = db.query(JobScan).filter(JobScan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = {
        "scan_id": scan.id,
        "trust_score": scan.trust_score,
        "verdict": scan.verdict,
        "verdict_color": (
            "green" if scan.trust_score >= 70 else
            "yellow" if scan.trust_score >= 45 else
            "orange" if scan.trust_score >= 25 else "red"
        ),
        "confidence": 0.8,
        "effective_signals": 0,
        "recommendation": "",
        "flags": scan.flags or [],
        "signal_scores": scan.signal_scores or {},
        "signal_weights": {},
        "configured_weights": {},
        "explanation_context": {},
        "explanation": scan.explanation or "",
        "model_trained": False,
        "url_details": None,
        "nlp_details": None,
        "company_details": None,
        "scanned_at": scan.created_at.isoformat() if scan.created_at else "",
    }
    trace = db.query(AgentTrace).filter(AgentTrace.scan_id == scan_id).first()
    if trace:
        result["agent_trace"] = {
            "tools_called": trace.tools_called or [],
            "tool_results": trace.tool_results or [],
            "reasoning_steps": trace.reasoning_steps or [],
            "critic_passed": trace.critic_passed,
            "created_at": trace.created_at.isoformat() if trace.created_at else "",
        }
    return result


@router.get("/history")
async def get_scan_history(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get the authenticated user's recent scan history."""
    scans = (
        db.query(JobScan)
        .filter(JobScan.user_id == current_user["user_id"])
        .order_by(JobScan.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "scans": [
            {
                "scan_id": s.id,
                "url": s.url,
                "job_title": s.job_title,
                "company_name": s.company_name,
                "trust_score": s.trust_score,
                "verdict": s.verdict,
                "scanned_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in scans
        ],
        "total": len(scans),
    }


@router.post("/debug/scan")
async def debug_scan(request: ScanRequest):
    """
    Debug endpoint — returns raw signal outputs before fusion.
    Use this to verify each module is working correctly.
    """
    results = {}
    if request.url:
        try:
            url_result = await analyse_url(request.url)
            results["url"] = {
                "score": url_result.url_trust_score,
                "domain": url_result.domain,
                "domain_age_days": url_result.domain_age_days,
                "ssl_valid": url_result.ssl_valid,
                "is_free_hosting": url_result.is_free_hosting,
                "is_established_domain": url_result.is_established_domain,
                "flags": url_result.flags,
            }
        except Exception as e:
            results["url"] = {"error": str(e)}
    if request.description:
        try:
            nlp_result = await classify_description(request.description)
            results["nlp"] = {
                "bert_fraud_probability": nlp_result.bert_fraud_probability,
                "used_trained_model": nlp_result.used_trained_model,
                "optimal_threshold": nlp_result.optimal_threshold,
                "duplicate_found": nlp_result.duplicate_found,
                "scam_phrases_found": nlp_result.scam_phrases_found,
                "structural_score": nlp_result.structural_score,
                "combined_score": nlp_result.combined_nlp_score,
                "flags": nlp_result.flags,
            }
        except Exception as e:
            results["nlp"] = {"error": str(e)}
    if request.company_name or request.recruiter_email or request.url:
        try:
            # Extract domain from URL for the fast-pass
            debug_domain = ""
            if request.url:
                try:
                    ext = tldextract.extract(request.url)
                    if ext.domain and ext.suffix:
                        debug_domain = f"{ext.domain}.{ext.suffix}".lower()
                except Exception:
                    pass
            company_result = await verify_company_global(
                company_name=request.company_name or "",
                company_domain=debug_domain,
                url=request.url or "",
                description=request.description or "",
            )
            results["company"] = {
                "trust_score": company_result.company_trust_score,
                "signals_checked": company_result.signals_checked,
                "country_detected": company_result.country_detected,
                "registry_used": company_result.registry_used,
                "is_registered": company_result.is_registered,
                "has_active_fraud_evidence": company_result.has_active_fraud_evidence,
                "flags": company_result.flags,
            }
        except Exception as e:
            results["company"] = {"error": str(e)}
    return results


@router.post("/debug/consistency-check")
async def check_score_flag_consistency(request: ScanRequest):
    """
    Runs the URL analyser and returns a consistency report:
    - What the ML model scored the URL
    - What flags were detected
    - What the final score is after penalty application
    - Whether the score is consistent with the flags

    A score above 60 with any high/critical flag is flagged as INCONSISTENT.
    """
    url_result = await analyse_url(request.url) if request.url else None

    if not url_result:
        return {"error": "URL required for consistency check"}

    # Assess consistency
    high_critical_flags = [
        f for f in url_result.flags
        if any(kw in f.lower() for kw in [
            "phishing", "malware", "expired", "invalid", "ip address",
            "free hosting", "free website", "impersonation", "days ago",
            "random", "shortened", "unencrypted", "concealed"
        ])
    ]

    is_consistent = True
    consistency_issues = []

    if url_result.url_trust_score > 0.60 and len(high_critical_flags) >= 1:
        is_consistent = False
        consistency_issues.append(
            f"Score is {url_result.url_trust_score:.2f} but {len(high_critical_flags)} "
            f"high/critical flags are present — score should be below 0.50"
        )

    if url_result.url_trust_score > 0.75 and len(url_result.flags) >= 2:
        is_consistent = False
        consistency_issues.append(
            f"Score is {url_result.url_trust_score:.2f} but {len(url_result.flags)} "
            f"total flags are present — score should not be above 0.75 with 2+ flags"
        )

    return {
        "url": request.url,
        "ml_fraud_probability": url_result.ml_classifier_score,
        "final_url_trust_score": url_result.url_trust_score,
        "final_url_score_100": round(url_result.url_trust_score * 100),
        "total_flags": len(url_result.flags),
        "high_critical_flags": high_critical_flags,
        "all_flags": url_result.flags,
        "is_consistent": is_consistent,
        "consistency_issues": consistency_issues,
    }
