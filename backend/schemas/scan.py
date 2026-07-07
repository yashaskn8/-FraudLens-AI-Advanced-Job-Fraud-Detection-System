from pydantic import BaseModel
from typing import Optional, Dict, List, Any


class ScanRequest(BaseModel):
    url: Optional[str] = None
    description: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    recruiter_email: Optional[str] = None


class ScanResponse(BaseModel):
    scan_id: str
    trust_score: Optional[int] = None        # None when not a job posting
    verdict: str
    verdict_color: str
    confidence: float
    effective_signals: int = 0               # How many signals contributed
    recommendation: Optional[str] = None
    flags: List[str] = []
    signal_scores: Dict[str, Optional[int]] = {}   # None = signal excluded
    signal_weights: Dict[str, float] = {}
    configured_weights: Dict[str, float] = {}      # Original configured weights
    explanation_context: Dict[str, Any] = {}        # Exclusion reasons, bert status
    explanation: Optional[str] = None
    model_trained: bool = False                     # Whether BERT is fine-tuned
    is_job_content: bool = True                     # False when gate rejects
    rejection_reason: Optional[str] = None          # Human-readable reason
    suggestions: List[str] = []                     # Actionable next steps
    url_details: Optional[Dict[str, Any]] = None
    nlp_details: Optional[Dict[str, Any]] = None
    company_details: Optional[Dict[str, Any]] = None
    scanned_at: str

    model_config = {"from_attributes": True}


class ScanStatusResponse(BaseModel):
    scan_id: str
    status: str
    progress: int
    message: str


class ScanHistoryItem(BaseModel):
    scan_id: str
    url: Optional[str]
    job_title: Optional[str]
    company_name: Optional[str]
    trust_score: int
    verdict: str
    scanned_at: str

    model_config = {"from_attributes": True}


class ReportRequest(BaseModel):
    scan_id: str
    reason: Optional[str] = None


class ReportResponse(BaseModel):
    report_id: str
    message: str
