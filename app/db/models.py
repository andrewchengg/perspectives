import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sp_client_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(50))
    race_ethnicity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_language: Mapped[str] = mapped_column(String(50), default="English")
    insurance_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    admission_date: Mapped[date] = mapped_column(Date)
    referral_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_diagnosis: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assessments: Mapped[list["Assessment"]] = relationship(back_populates="patient")
    progress_notes: Mapped[list["ProgressNote"]] = relationship(back_populates="patient")
    asam_evaluations: Mapped[list["ASAMEvaluation"]] = relationship(back_populates="patient")
    tjc_audits: Mapped[list["TJCAudit"]] = relationship(back_populates="patient")


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    assessment_type: Mapped[str] = mapped_column(String(50))
    assessment_date: Mapped[date] = mapped_column(Date)
    clinician_name: Mapped[str] = mapped_column(String(100))
    clinician_credentials: Mapped[str] = mapped_column(String(50))
    presenting_problem: Mapped[str] = mapped_column(Text)
    history_of_present_illness: Mapped[str] = mapped_column(Text)
    substance_use_history: Mapped[str] = mapped_column(Text)
    medical_history: Mapped[str] = mapped_column(Text)
    psychiatric_history: Mapped[str] = mapped_column(Text)
    family_history: Mapped[str] = mapped_column(Text)
    social_history: Mapped[str] = mapped_column(Text)
    spiritual_cultural: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_assessment: Mapped[str] = mapped_column(Text)
    mental_status_exam: Mapped[str] = mapped_column(Text)
    diagnoses_json: Mapped[dict] = mapped_column(JSON, default=list)
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="assessments")


class ProgressNote(Base):
    __tablename__ = "progress_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    note_date: Mapped[date] = mapped_column(Date)
    note_format: Mapped[str] = mapped_column(String(10))
    clinician_name: Mapped[str] = mapped_column(String(100))
    clinician_credentials: Mapped[str] = mapped_column(String(50))
    sections_json: Mapped[dict] = mapped_column(JSON)
    raw_text: Mapped[str] = mapped_column(Text)
    session_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cpt_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient: Mapped["Patient"] = relationship(back_populates="progress_notes")


class ASAMEvaluation(Base):
    __tablename__ = "asam_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    dimension_scores_json: Mapped[dict] = mapped_column(JSON)
    recommended_level: Mapped[str] = mapped_column(String(10))
    level_rationale: Mapped[str] = mapped_column(Text)
    full_evaluation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    linked_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qa_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    qa_claims_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qa_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[str] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="asam_evaluations")


class TJCAudit(Base):
    __tablename__ = "tjc_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"))
    audited_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    standards_json: Mapped[dict] = mapped_column(JSON)
    overall_compliance_pct: Mapped[float] = mapped_column(Float)
    critical_gaps: Mapped[dict] = mapped_column(JSON)
    full_audit_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    linked_evidence_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qa_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    qa_claims_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    qa_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_document: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_response: Mapped[str] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(back_populates="tjc_audits")
