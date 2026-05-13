import json
import logging
from datetime import datetime, timezone

from app.prompts.asam_prompt import ASAM_STRUCTURED_PROMPT, ASAM_SYSTEM_PROMPT, ASAM_THINKING_PROMPT
from app.schemas.asam import ASAMEvaluation
from app.schemas.patient import PatientExtraction
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_LEVELS = {"1.0", "1.7", "2.1", "2.5", "2.7", "3.1", "3.5", "3.7", "4.0"}


class ASAMEngine:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def evaluate(self, extraction: PatientExtraction) -> ASAMEvaluation:
        clinical_document = self._compile_clinical_document(extraction)

        # Pass 1: Clinical reasoning (think through each dimension)
        thinking_prompt = ASAM_THINKING_PROMPT.format(clinical_document=clinical_document)
        reasoning = await self._llm.complete(
            system=ASAM_SYSTEM_PROMPT,
            user=thinking_prompt,
        )

        # Pass 2: Structured output (format the analysis as JSON)
        structured_prompt = (
            f"Here is your clinical analysis:\n\n{reasoning}\n\n"
            f"{ASAM_STRUCTURED_PROMPT}"
        )
        raw_json = await self._llm.complete(
            system=ASAM_SYSTEM_PROMPT,
            user=structured_prompt,
        )

        evaluation = self._parse_response(raw_json, extraction.patient.id)
        self._validate_consistency(evaluation)
        return evaluation

    def _compile_clinical_document(self, extraction: PatientExtraction) -> str:
        parts = []

        p = extraction.patient
        parts.append("=== PATIENT DEMOGRAPHICS ===")
        parts.append(f"Name: {p.first_name} {p.last_name}")
        parts.append(f"DOB: {p.date_of_birth}, Gender: {p.gender}")
        parts.append(f"Race/Ethnicity: {p.race_ethnicity or 'Not documented'}")
        parts.append(f"Language: {p.primary_language}")
        parts.append(f"Admission Date: {p.admission_date}")
        parts.append(f"Referral Source: {p.referral_source or 'Not documented'}")
        if p.diagnoses:
            dx_str = "; ".join(f"{d.code} — {d.description}" for d in p.diagnoses)
            parts.append(f"Diagnoses: {dx_str}")
        parts.append("")

        a = extraction.assessment
        parts.append(f"=== BIOPSYCHOSOCIAL ASSESSMENT ({a.assessment_date}) ===")
        parts.append(f"Clinician: {a.clinician.name}, {a.clinician.credentials}")
        parts.append(f"Type: {a.assessment_type}")
        parts.append(f"\nPresenting Problem:\n{a.presenting_problem}")
        parts.append(f"\nHistory of Present Illness:\n{a.history_of_present_illness}")
        parts.append(f"\nSubstance Use History:\n{a.substance_use_history}")
        parts.append(f"\nMedical History:\n{a.medical_history}")
        parts.append(f"\nPsychiatric History:\n{a.psychiatric_history}")
        parts.append(f"\nFamily History:\n{a.family_history}")
        parts.append(f"\nSocial History:\n{a.social_history}")
        parts.append(f"\nSpiritual/Cultural:\n{a.spiritual_cultural or 'Not documented'}")
        parts.append(f"\nStrengths:\n{a.strengths or 'Not documented'}")
        parts.append(f"\nRisk Assessment:\n{a.risk_assessment}")
        parts.append(f"\nMental Status Exam:\n{a.mental_status_exam}")
        parts.append("")

        for note in extraction.progress_notes:
            parts.append(f"=== PROGRESS NOTE — {note.note_format} ({note.note_date}) ===")
            parts.append(f"Clinician: {note.clinician.name}, {note.clinician.credentials}")
            for section_name, section_text in note.sections.items():
                parts.append(f"\n{section_name.upper()}:\n{section_text}")
            parts.append("")

        return "\n".join(parts)

    def _parse_response(self, raw: str, patient_id: str) -> ASAMEvaluation:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        data = json.loads(text)
        data["patient_id"] = patient_id
        data["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        return ASAMEvaluation.model_validate(data)

    def _validate_consistency(self, evaluation: ASAMEvaluation) -> None:
        if evaluation.recommended_level not in VALID_LEVELS:
            logger.warning(
                "ASAM level %s is not a valid 4th edition level. Valid: %s",
                evaluation.recommended_level,
                VALID_LEVELS,
            )

        if len(evaluation.dimensions) != 6:
            logger.warning(
                "Expected 6 ASAM dimensions, got %d", len(evaluation.dimensions)
            )
            return

        # Run the rule-based flowchart as a consistency check
        from app.services.asam_flowchart import DimensionRatings, determine_loc

        dims_by_num = {d.dimension_number: d for d in evaluation.dimensions}
        ratings = DimensionRatings(
            d1_withdrawal=dims_by_num[1].risk_rating,
            d2_biomedical=dims_by_num[2].risk_rating,
            d3_emotional=dims_by_num[3].risk_rating,
            d4_readiness=dims_by_num[4].risk_rating,
            d5_relapse=dims_by_num[5].risk_rating,
            d6_environment=dims_by_num[6].risk_rating,
        )
        algorithmic = determine_loc(ratings)

        if algorithmic.level != evaluation.recommended_level:
            logger.warning(
                "LLM recommended Level %s but flowchart algorithm suggests Level %s. "
                "Algorithm pathway: %s. Algorithm rationale: %s",
                evaluation.recommended_level,
                algorithmic.level,
                algorithmic.pathway,
                algorithmic.rationale,
            )

        # Check citations exist for every dimension
        for dim in evaluation.dimensions:
            if not dim.citations:
                logger.warning(
                    "Dimension %d (%s) has no citations",
                    dim.dimension_number,
                    dim.dimension_name,
                )
