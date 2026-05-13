import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.database import get_db
from app.db.models import Patient
from app.schemas.patient import (
    AssessmentData,
    ClinicianInfo,
    Diagnosis,
    ExtractionMetadata,
    PatientDemographics,
    PatientExtraction,
    ProgressNoteData,
)
from app.services.simplepractice import LocalExportParser, SimplePracticeExtractor

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Task 2: Programmatic extraction from SimplePractice ---


class SPExtractionRequest(BaseModel):
    """Request body for programmatic SimplePractice extraction."""

    client_name: str  # Client name as it appears in SimplePractice (e.g. "Jack Smith")
    email: str | None = None  # Falls back to SP_EMAIL env var
    password: str | None = None  # Falls back to SP_PASSWORD env var
    totp_secret: str | None = None  # Optional TOTP secret for 2FA


@router.post("/extract", response_model=PatientExtraction)
async def extract_from_simplepractice(
    request: SPExtractionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Programmatically extract patient data from SimplePractice.

    This endpoint:
    1. Logs into SimplePractice using admin credentials (via headless browser)
    2. Navigates to Settings > Practice > Data Export
    3. Triggers a single-client "Sessions" export
    4. Downloads the ZIP file
    5. Parses CSVs (demographics) and PDFs (clinical notes) with pdfplumber
    6. Returns structured JSON and persists to local database

    In production, this runs inside a Docker container / cloud VM.
    """
    email = request.email or settings.sp_email
    password = request.password or settings.sp_password

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="SimplePractice credentials required. "
            "Provide in request body or set SP_EMAIL/SP_PASSWORD env vars.",
        )

    extractor = SimplePracticeExtractor()
    try:
        extraction = await extractor.extract(
            email=email,
            password=password,
            client_name=request.client_name,
            totp_secret=request.totp_secret,
        )

        await _persist_extraction(db, extraction)
        return extraction

    except Exception as e:
        logger.error("SimplePractice extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")


# --- Development helper: parse a local export directory ---


class LocalParseRequest(BaseModel):
    """Request body for parsing an already-downloaded export."""

    export_path: str  # Path to the unzipped export directory on disk
    client_name: str  # Client name to look for in the export


@router.post("/parse-export", response_model=PatientExtraction)
async def parse_local_export(
    request: LocalParseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Parse an already-downloaded SimplePractice export directory.

    Development helper — use when you've manually downloaded the export ZIP
    and want to test the parsing without re-running the full browser automation.
    """
    parser = LocalExportParser()
    try:
        extraction = parser.parse_directory(request.export_path, request.client_name)
        await _persist_extraction(db, extraction)
        return extraction
    except Exception as e:
        logger.error("Export parsing failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Parsing failed: {e}")


# --- Read extracted data from database ---


@router.get("/patients/{patient_id}/extract", response_model=PatientExtraction)
async def get_patient_data(
    patient_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve previously extracted patient data from the database."""
    result = await db.execute(
        select(Patient)
        .where(Patient.id == patient_id)
        .options(
            selectinload(Patient.assessments),
            selectinload(Patient.progress_notes),
        )
    )
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if not patient.assessments:
        raise HTTPException(
            status_code=404, detail="No assessment found for patient"
        )

    assessment = patient.assessments[0]
    notes = sorted(patient.progress_notes, key=lambda n: n.note_date)

    diagnoses = [
        Diagnosis(code=d["code"], description=d["description"])
        for d in (
            assessment.diagnoses_json
            if isinstance(assessment.diagnoses_json, list)
            else []
        )
    ]

    return PatientExtraction(
        patient=PatientDemographics(
            id=str(patient.id),
            first_name=patient.first_name,
            last_name=patient.last_name,
            date_of_birth=patient.date_of_birth,
            gender=patient.gender,
            race_ethnicity=patient.race_ethnicity,
            primary_language=patient.primary_language,
            admission_date=patient.admission_date,
            referral_source=patient.referral_source,
            diagnoses=diagnoses,
        ),
        assessment=AssessmentData(
            assessment_type=assessment.assessment_type,
            assessment_date=assessment.assessment_date,
            clinician=ClinicianInfo(
                name=assessment.clinician_name,
                credentials=assessment.clinician_credentials,
            ),
            presenting_problem=assessment.presenting_problem,
            history_of_present_illness=assessment.history_of_present_illness,
            substance_use_history=assessment.substance_use_history,
            medical_history=assessment.medical_history,
            psychiatric_history=assessment.psychiatric_history,
            family_history=assessment.family_history,
            social_history=assessment.social_history,
            spiritual_cultural=assessment.spiritual_cultural,
            strengths=assessment.strengths,
            risk_assessment=assessment.risk_assessment,
            mental_status_exam=assessment.mental_status_exam,
            diagnoses=diagnoses,
            raw_text=assessment.raw_text,
        ),
        progress_notes=[
            ProgressNoteData(
                note_date=n.note_date,
                note_format=n.note_format,
                clinician=ClinicianInfo(
                    name=n.clinician_name,
                    credentials=n.clinician_credentials,
                ),
                sections=n.sections_json,
                raw_text=n.raw_text,
                session_duration_minutes=n.session_duration_minutes,
                cpt_code=n.cpt_code,
            )
            for n in notes
        ],
        extraction_metadata=ExtractionMetadata(
            source="database",
            extracted_at=datetime.now(timezone.utc),
        ),
    )


# --- Persist extraction to database ---


async def _persist_extraction(
    db: AsyncSession, extraction: PatientExtraction
) -> None:
    """Save extracted data to the local database."""
    from app.db.models import Assessment as AssessmentModel
    from app.db.models import Patient as PatientModel
    from app.db.models import ProgressNote as ProgressNoteModel

    # Check if patient already exists
    result = await db.execute(
        select(PatientModel).where(
            PatientModel.first_name == extraction.patient.first_name,
            PatientModel.last_name == extraction.patient.last_name,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info(
            "Patient %s %s already exists, skipping persist.",
            extraction.patient.first_name,
            extraction.patient.last_name,
        )
        return

    patient = PatientModel(
        sp_client_id=extraction.patient.id,
        first_name=extraction.patient.first_name,
        last_name=extraction.patient.last_name,
        date_of_birth=extraction.patient.date_of_birth,
        gender=extraction.patient.gender,
        race_ethnicity=extraction.patient.race_ethnicity,
        primary_language=extraction.patient.primary_language,
        admission_date=extraction.patient.admission_date,
        referral_source=extraction.patient.referral_source,
    )
    db.add(patient)
    await db.flush()

    a = extraction.assessment
    assessment = AssessmentModel(
        patient_id=patient.id,
        assessment_type=a.assessment_type,
        assessment_date=a.assessment_date,
        clinician_name=a.clinician.name,
        clinician_credentials=a.clinician.credentials,
        presenting_problem=a.presenting_problem,
        history_of_present_illness=a.history_of_present_illness,
        substance_use_history=a.substance_use_history,
        medical_history=a.medical_history,
        psychiatric_history=a.psychiatric_history,
        family_history=a.family_history,
        social_history=a.social_history,
        spiritual_cultural=a.spiritual_cultural,
        strengths=a.strengths,
        risk_assessment=a.risk_assessment,
        mental_status_exam=a.mental_status_exam,
        diagnoses_json=[d.model_dump() for d in a.diagnoses],
        raw_text=a.raw_text,
    )
    db.add(assessment)

    for n in extraction.progress_notes:
        note = ProgressNoteModel(
            patient_id=patient.id,
            note_date=n.note_date,
            note_format=n.note_format,
            clinician_name=n.clinician.name,
            clinician_credentials=n.clinician.credentials,
            sections_json=n.sections,
            raw_text=n.raw_text,
            session_duration_minutes=n.session_duration_minutes,
            cpt_code=n.cpt_code,
        )
        db.add(note)

    await db.commit()
    logger.info(
        "Persisted patient %s %s to database.",
        extraction.patient.first_name,
        extraction.patient.last_name,
    )
