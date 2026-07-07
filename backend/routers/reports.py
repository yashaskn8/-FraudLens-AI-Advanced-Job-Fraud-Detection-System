"""
Reports Router — handles community fraud report submissions.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.job_scan import FraudReport, JobScan
from backend.schemas.scan import ReportRequest, ReportResponse

router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.post("/report", response_model=ReportResponse)
async def submit_fraud_report(
    request: ReportRequest,
    req: Request,
    db: Session = Depends(get_db),
):
    """Submit a fraud report for a scanned job posting."""
    report_id = str(uuid.uuid4())

    # Save report
    try:
        report = FraudReport(
            id=report_id,
            scan_id=request.scan_id,
            reporter_ip=req.client.host if req.client else None,
            reason=request.reason,
            created_at=datetime.utcnow(),
        )
        db.add(report)

        # Increment report count on the scan
        scan = db.query(JobScan).filter(JobScan.id == request.scan_id).first()
        if scan:
            scan.report_count = (scan.report_count or 0) + 1
            if scan.report_count >= 5:
                scan.is_confirmed_fraud = 1

        db.commit()
    except Exception as e:
        print(f"Report save failed: {e}")
        db.rollback()

    return ReportResponse(
        report_id=report_id,
        message="Thank you for your report. It helps protect other job seekers.",
    )


@router.get("/reports")
async def get_reports(limit: int = 50, db: Session = Depends(get_db)):
    """Get recent fraud reports."""
    reports = db.query(FraudReport).order_by(
        FraudReport.created_at.desc()
    ).limit(limit).all()
    return {
        "reports": [
            {
                "report_id": r.id,
                "scan_id": r.scan_id,
                "reason": r.reason,
                "confirmed": r.confirmed,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in reports
        ],
        "total": len(reports),
    }
