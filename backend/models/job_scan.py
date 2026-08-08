from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class JobScan(Base):
    __tablename__ = "job_scans"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True, index=True)
    url = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    company_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    trust_score = Column(Integer, nullable=False)
    verdict = Column(String, nullable=False)
    flags = Column(JSON, default=list)
    signal_scores = Column(JSON, default=dict)
    explanation = Column(Text, nullable=True)
    is_confirmed_fraud = Column(Integer, default=0)
    report_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class FraudReport(Base):
    __tablename__ = "fraud_reports"

    id = Column(String, primary_key=True)
    scan_id = Column(String, nullable=False)
    reporter_ip = Column(String, nullable=True)
    reason = Column(Text, nullable=True)
    confirmed = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
