from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class Citation(BaseModel):
    source: str  # e.g. "BPS Intake", "SOAP Note 2025-04-18"
    text: str  # exact quoted text from the document
    relevance: str  # why this text matters for the rating


class DimensionRating(BaseModel):
    dimension_number: int  # 1-6
    dimension_name: str
    risk_rating: int  # 0-4
    risk_label: Literal["None", "Low", "Moderate", "High", "Very High"]
    rationale: str
    citations: list[Citation]
    key_factors: list[str]


class AlternativeLevel(BaseModel):
    level: str
    name: str
    reason_not_recommended: str


class ASAMEvaluation(BaseModel):
    patient_id: str
    evaluated_at: datetime
    dimensions: list[DimensionRating]  # exactly 6
    recommended_level: str  # e.g. "2.1"
    recommended_level_name: str  # e.g. "Intensive Outpatient Services"
    level_rationale: str
    alternative_levels: list[AlternativeLevel]
    clinical_summary: str
    fourth_edition_notes: str  # how 4th ed changes apply to this case
