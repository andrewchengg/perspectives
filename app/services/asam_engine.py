import json
import logging
from datetime import datetime, timezone

from app.prompts.asam_prompt import ASAM_STRUCTURED_PROMPT, ASAM_SYSTEM_PROMPT, ASAM_THINKING_PROMPT
from app.schemas.asam import ASAMEvaluation
from app.schemas.patient import PatientExtraction
from app.services.asam_flowchart import SubdimensionResult, determine_loc
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

VALID_LEVELS = {
    "1.5", "1.5_COE", "1.7", "1.7_COE",
    "2.1", "2.5", "2.5_COE", "2.7", "2.7_COE",
    "3.1", "3.5", "3.5_COE", "3.7", "3.7_BIO", "3.7_COE",
    "4", "4_PSYCH",
}

LEVEL_NAMES = {
    "1.5": "Outpatient Services",
    "1.5_COE": "Outpatient Services, Co-occurring Enhanced",
    "1.7": "Medically Monitored Outpatient",
    "1.7_COE": "Medically Monitored Outpatient, Co-occurring Enhanced",
    "2.1": "Intensive Outpatient Services",
    "2.5": "Partial Hospitalization Services",
    "2.5_COE": "Partial Hospitalization, Co-occurring Enhanced",
    "2.7": "Medically Monitored Intensive Outpatient",
    "2.7_COE": "Medically Monitored Intensive Outpatient, Co-occurring Enhanced",
    "3.1": "Clinically Managed Low-Intensity Residential",
    "3.5": "Clinically Managed High-Intensity Residential",
    "3.5_COE": "Clinically Managed High-Intensity Residential, Co-occurring Enhanced",
    "3.7": "Medically Monitored Intensive Inpatient",
    "3.7_BIO": "Medically Monitored Intensive Inpatient, Biomedical Enhanced",
    "3.7_COE": "Medically Monitored Intensive Inpatient, Co-occurring Enhanced",
    "4": "Medically Managed Intensive Inpatient",
    "4_PSYCH": "Medically Managed Inpatient Psychiatric",
}


class ASAMEngine:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def evaluate(self, extraction: PatientExtraction) -> ASAMEvaluation:
        clinical_document = self._compile_clinical_document(extraction)

        # Pass 1: LLM assigns risk codes per subdimension (clinical reasoning)
        thinking_prompt = ASAM_THINKING_PROMPT.format(clinical_document=clinical_document)
        reasoning = await self._llm.complete(
            system=ASAM_SYSTEM_PROMPT,
            user=thinking_prompt,
        )

        # Pass 2: LLM outputs structured JSON with risk codes + citations
        structured_prompt = (
            f"Here is your clinical analysis:\n\n{reasoning}\n\n"
            f"{ASAM_STRUCTURED_PROMPT}"
        )
        raw_json = await self._llm.complete(
            system=ASAM_SYSTEM_PROMPT,
            user=structured_prompt,
        )

        evaluation = self._parse_response(raw_json, extraction.patient.id)

        # Pass 3: ALGORITHM determines LOC from the LLM's risk codes
        # This is the key change — the algorithm DRIVES the recommendation,
        # not the LLM. The LLM's job is subdimensional assessment only.
        algorithmic_loc = self._apply_algorithmic_loc(evaluation)

        # Log if LLM and algorithm disagree (for transparency)
        llm_level = evaluation.recommended_level
        if algorithmic_loc.level != llm_level:
            logger.info(
                "Algorithm overriding LLM recommendation: LLM said %s, algorithm says %s. "
                "Using algorithm result. Rationale: %s",
                llm_level, algorithmic_loc.level, algorithmic_loc.rationale,
            )

        # Override LLM's recommendation with algorithmic result
        evaluation.recommended_level = algorithmic_loc.level
        evaluation.recommended_level_name = LEVEL_NAMES.get(
            algorithmic_loc.level, f"Level {algorithmic_loc.level}"
        )

        # Add recovery residence flag if indicated
        if algorithmic_loc.recovery_residence:
            evaluation.recommended_level_name += " + Recovery Residence"

        # Store the determination steps from the algorithm
        evaluation.loc_determination_steps = [
            {"step": s["step"], "description": s.get("rationale", ""), "result": s["result"]}
            for s in algorithmic_loc.steps
        ]

        # Update the level rationale to reflect algorithmic determination
        evaluation.level_rationale = (
            f"Algorithmically determined: {algorithmic_loc.rationale}"
            + (f" (LLM had suggested {llm_level})" if llm_level != algorithmic_loc.level else "")
        )

        # Validate citations exist
        self._validate_citations(evaluation)

        return evaluation

    @staticmethod
    def _normalize_minimum_level(dim: int, subdim_name: str, risk_code: str, min_level_str: str) -> str:
        """Normalize LLM's minimum_level string to a flowchart-compatible level code."""
        from app.services.asam_flowchart import resolve_minimum_level
        s = min_level_str.strip()

        # Try to extract level from strings like "Minimum Level 2.5" or "Min. Level 3.7 COE"
        import re
        m = re.search(r'(?:Level\s+)?(\d\.\d(?:\s*(?:COE|BIO))?)', s, re.IGNORECASE)
        if m:
            return m.group(1).upper().replace(" ", "_")

        # Common LLM outputs
        lower = s.lower()
        if "no specific" in lower or lower == "0":
            return "0"
        if "any level" in lower or lower == "any":
            return "ANY"
        if "moud" in lower:
            return "MOUD-C"
        if "recovery residence" in lower:
            return "RR"
        if "evaluation" in lower or "eval" in lower:
            return "EVAL"

        # Fall back to dimension-aware resolution from risk code
        return resolve_minimum_level(dim, subdim_name, risk_code)

    def _apply_algorithmic_loc(self, evaluation: ASAMEvaluation):
        """Extract subdimension results and run the rule-based LOC flowchart."""
        subdim_results = []
        for dim in evaluation.dimensions:
            for subdim in dim.subdimensions:
                normalized = self._normalize_minimum_level(
                    dim.dimension_number, subdim.name,
                    subdim.risk_rating_code, subdim.minimum_level,
                )
                subdim_results.append(
                    SubdimensionResult(
                        dimension=dim.dimension_number,
                        subdimension=subdim.name,
                        risk_code=subdim.risk_rating_code,
                        minimum_level=normalized,
                    )
                )

        if not subdim_results:
            logger.warning("No subdimension results found — cannot determine LOC algorithmically")
            from app.services.asam_flowchart import LOCRecommendation
            return LOCRecommendation(
                level=evaluation.recommended_level,
                name=evaluation.recommended_level_name,
                coe=False, recovery_residence=False,
                rationale="Fallback: no subdimension data for algorithmic determination.",
            )

        return determine_loc(subdim_results)

    def _apply_algorithmic_loc_to_evaluation(self, evaluation: ASAMEvaluation) -> ASAMEvaluation:
        """Re-run algorithmic LOC on an evaluation and update it in place.
        Used by QA loop after corrections change subdimension ratings."""
        algorithmic_loc = self._apply_algorithmic_loc(evaluation)
        old_level = evaluation.recommended_level

        evaluation.recommended_level = algorithmic_loc.level
        evaluation.recommended_level_name = LEVEL_NAMES.get(
            algorithmic_loc.level, f"Level {algorithmic_loc.level}"
        )
        if algorithmic_loc.recovery_residence:
            evaluation.recommended_level_name += " + Recovery Residence"

        evaluation.loc_determination_steps = [
            {"step": s["step"], "description": s.get("rationale", ""), "result": s["result"]}
            for s in algorithmic_loc.steps
        ]
        evaluation.level_rationale = (
            f"Algorithmically determined after QA corrections: {algorithmic_loc.rationale}"
            + (f" (changed from {old_level})" if old_level != algorithmic_loc.level else "")
        )

        if old_level != algorithmic_loc.level:
            logger.info(
                "QA corrections changed LOC: %s → %s. Rationale: %s",
                old_level, algorithmic_loc.level, algorithmic_loc.rationale,
            )

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

    def _validate_citations(self, evaluation: ASAMEvaluation) -> None:
        """Warn if any subdimension is missing citations."""
        for dim in evaluation.dimensions:
            for subdim in dim.subdimensions:
                if not subdim.citations:
                    logger.warning(
                        "Dimension %d (%s) subdimension '%s' has no citations",
                        dim.dimension_number,
                        dim.dimension_name,
                        subdim.name,
                    )
