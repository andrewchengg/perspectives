from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    source: str
    text: str
    relevance: str


class StandardFinding(BaseModel):
    element: str  # e.g. "CTS.02.02.01 EP2"
    description: str
    status: Literal["pass", "fail", "partial", "not_applicable"]
    finding: str
    citations: list[Citation]
    remediation: str | None = None


class StandardResult(BaseModel):
    standard_id: str  # "CTS.01", "CTS.02", etc.
    standard_name: str
    overall_status: Literal["compliant", "non_compliant", "partial"]
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
    standards: list[StandardResult]  # CTS.01 through CTS.05
    overall_compliance_percentage: float
    critical_gaps: list[CriticalGap]
    recommendations: list[str]
    audit_summary: str
