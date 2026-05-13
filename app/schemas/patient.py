from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class Diagnosis(BaseModel):
    code: str
    description: str


class ClinicianInfo(BaseModel):
    name: str
    credentials: str


class PatientDemographics(BaseModel):
    id: str
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    race_ethnicity: str | None = None
    primary_language: str
    admission_date: date
    referral_source: str | None = None
    diagnoses: list[Diagnosis]


class AssessmentData(BaseModel):
    assessment_type: str
    assessment_date: date
    clinician: ClinicianInfo
    presenting_problem: str
    history_of_present_illness: str
    substance_use_history: str
    medical_history: str
    psychiatric_history: str
    family_history: str
    social_history: str
    spiritual_cultural: str | None = None
    strengths: str | None = None
    risk_assessment: str
    mental_status_exam: str
    diagnoses: list[Diagnosis]
    raw_text: str


class ProgressNoteData(BaseModel):
    note_date: date
    note_format: Literal["SOAP", "DAP", "DSAP"]
    clinician: ClinicianInfo
    sections: dict[str, str]
    raw_text: str
    session_duration_minutes: int | None = None
    cpt_code: str | None = None


class ExtractionMetadata(BaseModel):
    source: str
    extracted_at: datetime


class PatientExtraction(BaseModel):
    patient: PatientDemographics
    assessment: AssessmentData
    progress_notes: list[ProgressNoteData]
    extraction_metadata: ExtractionMetadata
