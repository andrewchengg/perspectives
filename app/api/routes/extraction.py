import logging
from datetime import datetime, timezone
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

    client_name: str | None = None  # If None, extracts ALL clients
    email: str | None = None  # Falls back to SP_EMAIL env var
    password: str | None = None  # Falls back to SP_PASSWORD env var
    totp_secret: str | None = None  # Optional TOTP secret for 2FA


@router.post("/extract")
async def extract_from_simplepractice(
    request: SPExtractionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Programmatically extract patient data from SimplePractice.

    If client_name is provided, extracts just that client.
    If omitted, discovers and extracts ALL clients in the practice.
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
        extractions = await extractor.extract(
            email=email,
            password=password,
            client_name=request.client_name,
            totp_secret=request.totp_secret,
        )

        for extraction in extractions:
            await _persist_extraction(db, extraction)

        if not extractions:
            raise HTTPException(status_code=404, detail="No patients found in export")

        # Return all patients — UI will add each to the sidebar
        if len(extractions) == 1:
            return extractions[0]
        else:
            # Return list of all extracted patients
            return [e.model_dump() for e in extractions]

    except HTTPException:
        raise
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


# --- Structure raw assessment text via LLM ---


class StructureRequest(BaseModel):
    raw_text: str


@router.post("/structure-assessment")
async def structure_assessment(request: StructureRequest):
    """Use Haiku to parse raw assessment text into clean labeled sections."""
    from app.services.llm_client import LLMClient

    llm = LLMClient()
    prompt = f"""\
Split the following clinical assessment document into clearly labeled sections.
Return a JSON array where each element has:
- "title": the section name (e.g. "Presenting Problem", "Substance Use History", "Intake Questionnaire")
- "body": the full text content of that section

Rules:
- Preserve ALL text content exactly as written — do not summarize or omit anything
- Merge numbered headers with their content (e.g. "1. Presenting Problem" becomes title "Presenting Problem")
- If there is an intake questionnaire section, make it its own section titled "Intake Questionnaire"
- Keep sub-headers within the body text (e.g. "Strengths:", "Weaknesses:", "Stressors:")
- Remove page footers like "Created on ... Page X of Y" or "Completed on ..."
- Remove duplicate content if the same section appears twice

DOCUMENT:
{request.raw_text}

Respond with ONLY the JSON array, no markdown fences."""

    try:
        raw = await llm.complete(
            system="You are a clinical document parser. Return valid JSON only.",
            user=prompt,
            max_tokens=8000,
            model="claude-haiku-4-5-20251001",
        )
        import json
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        sections = json.loads(text.strip())
        return {"sections": sections}
    except Exception as e:
        logger.error("Assessment structuring failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Structuring failed: {e}")


# --- Read extracted data from database ---


@router.get("/patients")
async def list_patients(db: AsyncSession = Depends(get_db)):
    """List all patients in the database (id, name, dob, note count)."""
    result = await db.execute(
        select(Patient).options(
            selectinload(Patient.progress_notes),
        )
    )
    patients = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "first_name": p.first_name,
            "last_name": p.last_name,
            "date_of_birth": str(p.date_of_birth),
            "note_count": len(p.progress_notes),
        }
        for p in patients
    ]


@router.get("/patients/{patient_id}/extract", response_model=PatientExtraction)
async def get_patient_data(
    patient_id: str,
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
            "Patient %s %s already exists, updating ID.",
            extraction.patient.first_name,
            extraction.patient.last_name,
        )
        extraction.patient.id = str(existing.id)
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

    # Update extraction with the DB-generated UUID so the UI gets the right ID
    extraction.patient.id = str(patient.id)

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
