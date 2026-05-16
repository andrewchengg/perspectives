from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    source: str
    text: str
    relevance: str


class SAFERRating(BaseModel):
    """SAFER Matrix risk classification for non-compliant EPs.
    Used by TJC since Jan 2017 to prioritize findings."""
    likelihood: Literal["high", "moderate", "low"]
    scope: Literal["widespread", "pattern", "limited"]


class StandardFinding(BaseModel):
    element: str  # e.g. "CTS.02.02.01 EP 2"
    description: str
    score: int = 2  # 0=insufficient, 1=partial, 2=satisfactory
    status: Literal["satisfactory", "partial", "insufficient", "pass", "fail", "not_applicable"] = "satisfactory"
    finding: str
    citations: list[Citation] = []
    safer: SAFERRating | None = None  # Required for score 0 or 1
    remediation: str | None = None


class StandardResult(BaseModel):
    standard_id: str
    standard_name: str
    overall_status: Literal["compliant", "non_compliant", "partial"] = "compliant"
    findings: list[StandardFinding]
    compliance_percentage: float


class CriticalGap(BaseModel):
    standard: str
    element: str
    severity: Literal["critical", "major", "minor"]
    description: str
    impact: str


class TJCAuditResult(BaseModel):
    patient_id: str
    audited_at: datetime
    standards: list[StandardResult]
    overall_compliance_percentage: float
    critical_gaps: list[CriticalGap]
    recommendations: list[str]
    audit_summary: str
