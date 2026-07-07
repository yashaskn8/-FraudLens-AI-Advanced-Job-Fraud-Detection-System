"""
Celery async task for background job scanning.
"""
from backend.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def async_scan_job(self, scan_id: str, url: str, description: str, **kwargs):
    """
    Run a full job scan asynchronously via Celery.
    Used for high-traffic scenarios where synchronous scanning is too slow.
    """
    import asyncio
    from backend.services.url_analyser import analyse_url
    from backend.services.nlp_classifier import classify_description
    from backend.services.company_verifier import verify_company_global
    from backend.services.trust_scorer import compute_trust_score
    from backend.services.explainer import generate_explanation
    from backend.database import SessionLocal
    from backend.models.job_scan import JobScan
    from datetime import datetime

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Run analyses
        url_result = loop.run_until_complete(analyse_url(url)) if url else None
        nlp_result = loop.run_until_complete(classify_description(description))
        # Extract domain from URL for company verifier fast-pass
        import tldextract
        company_domain = ""
        if url:
            try:
                ext = tldextract.extract(url)
                if ext.domain and ext.suffix:
                    company_domain = f"{ext.domain}.{ext.suffix}".lower()
            except Exception:
                pass

        company_result = loop.run_until_complete(
            verify_company_global(
                company_name=kwargs.get("company_name", ""),
                company_domain=company_domain,
                url=url,
                description=description,
            )
        )

        trust_result = compute_trust_score(url_result, nlp_result, company_result)
        explanation = loop.run_until_complete(
            generate_explanation(trust_result, kwargs.get("job_title", ""), kwargs.get("company_name", ""))
        )

        # Save to database
        db = SessionLocal()
        scan = JobScan(
            id=scan_id,
            url=url or "",
            job_title=kwargs.get("job_title", ""),
            company_name=kwargs.get("company_name", ""),
            description=(description or "")[:5000],
            trust_score=trust_result.trust_score,
            verdict=trust_result.verdict,
            flags=trust_result.all_flags,
            signal_scores=trust_result.signal_scores,
            explanation=explanation,
            created_at=datetime.utcnow(),
        )
        db.add(scan)
        db.commit()
        db.close()

        loop.close()
        return {"scan_id": scan_id, "status": "completed", "trust_score": trust_result.trust_score}

    except Exception as exc:
        self.retry(exc=exc)
