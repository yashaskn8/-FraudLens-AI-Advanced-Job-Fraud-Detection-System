"""
Analytics Router — provides dashboard data.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.database import get_db
from backend.models.job_scan import JobScan

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard(db: Session = Depends(get_db)):
    """Get analytics data for the dashboard."""
    try:
        total_scans = db.query(func.count(JobScan.id)).scalar() or 0
        fraud_count = db.query(func.count(JobScan.id)).filter(
            JobScan.verdict.in_(["FRAUD", "LIKELY_FRAUD"])
        ).scalar() or 0
        safe_count = db.query(func.count(JobScan.id)).filter(
            JobScan.verdict == "SAFE"
        ).scalar() or 0
        suspicious_count = db.query(func.count(JobScan.id)).filter(
            JobScan.verdict == "SUSPICIOUS"
        ).scalar() or 0
        avg_score = db.query(func.avg(JobScan.trust_score)).scalar() or 50

        # Recent scans
        recent = db.query(JobScan).order_by(
            JobScan.created_at.desc()
        ).limit(10).all()

        # Verdict distribution
        verdict_distribution = {
            "SAFE": safe_count,
            "SUSPICIOUS": suspicious_count,
            "LIKELY_FRAUD": fraud_count,
            "FRAUD": db.query(func.count(JobScan.id)).filter(
                JobScan.verdict == "FRAUD"
            ).scalar() or 0,
        }

    except Exception:
        total_scans = 0
        fraud_count = 0
        safe_count = 0
        suspicious_count = 0
        avg_score = 50
        recent = []
        verdict_distribution = {"SAFE": 0, "SUSPICIOUS": 0, "LIKELY_FRAUD": 0, "FRAUD": 0}

    return {
        "total_scans": total_scans,
        "fraud_detected": fraud_count,
        "safe_count": safe_count,
        "suspicious_count": suspicious_count,
        "average_trust_score": round(avg_score, 1),
        "detection_rate": round(fraud_count / max(total_scans, 1) * 100, 1),
        "verdict_distribution": verdict_distribution,
        "recent_scans": [
            {
                "scan_id": s.id,
                "job_title": s.job_title,
                "company_name": s.company_name,
                "trust_score": s.trust_score,
                "verdict": s.verdict,
                "scanned_at": s.created_at.isoformat() if s.created_at else "",
            }
            for s in recent
        ],
    }
