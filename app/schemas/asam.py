from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    source: str  # e.g. "BPS Intake", "SOAP Note 2026-05-07"
    text: str  # exact quoted text from the document
    relevance: str  # why this text matters for the rating


class SubdimensionRating(BaseModel):
    name: str  # e.g. "Intoxication and Associated Risks"
    risk_rating_code: str  # e.g. "ANY", "0", "2", "3A", "3B", "4", "A", "B", "C", "D", "E"
    minimum_level: str  # e.g. "Any Level of Care", "Minimum Level 2.7", "No Specific Needs"
    rationale: str
    citations: list[Citation]


class DimensionRating(BaseModel):
    dimension_number: int  # 1-6
    dimension_name: str
    subdimensions: list[SubdimensionRating]
    key_factors: list[str]


class LOCDeterminationStep(BaseModel):
    step: int  # 1-6
    description: str  # e.g. "Inpatient Care (Level 4 / 4 Psychiatric)"
    result: str  # e.g. "Not indicated", "Level 2.1 indicated"
    rationale: str


class AlternativeLevel(BaseModel):
    level: str
    name: str
    reason_not_recommended: str


class ASAMEvaluation(BaseModel):
    patient_id: str
    evaluated_at: datetime
    dimensions: list[DimensionRating]  # 5 clinical dimensions (D6 is separate)
    loc_determination_steps: list[LOCDeterminationStep]  # steps 1-6 top-down
    recommended_level: str  # e.g. "2.1"
    recommended_level_name: str  # e.g. "Intensive Outpatient Services"
    coe_indicated: bool  # Co-occurring Enhanced needed?
    recovery_residence_indicated: bool  # Recovery residence needed?
    level_rationale: str
    dimension_6_notes: str  # patient willingness/ability
    clinical_summary: str
    alternative_levels: list[AlternativeLevel]
