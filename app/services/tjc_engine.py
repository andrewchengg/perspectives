import json
import logging
from datetime import datetime, timezone

from app.prompts.tjc_prompt import TJC_STRUCTURED_PROMPT, TJC_SYSTEM_PROMPT, TJC_THINKING_PROMPT
from app.schemas.patient import PatientExtraction
from app.schemas.tjc import TJCAuditResult
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


class TJCEngine:
    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def audit(self, extraction: PatientExtraction) -> TJCAuditResult:
        clinical_document = self._compile_clinical_document(extraction)

        # Pass 1: Compliance analysis (think through each standard)
        thinking_prompt = TJC_THINKING_PROMPT.format(clinical_document=clinical_document)
        reasoning = await self._llm.complete(
            system=TJC_SYSTEM_PROMPT,
            user=thinking_prompt,
        )

        # Pass 2: Structured output (format the audit as JSON)
        structured_prompt = (
            f"Here is your compliance analysis:\n\n{reasoning}\n\n"
            f"{TJC_STRUCTURED_PROMPT}"
        )
        raw_json = await self._llm.complete(
            system=TJC_SYSTEM_PROMPT,
            user=structured_prompt,
        )

        result = self._parse_response(raw_json, extraction.patient.id)
        self._validate_audit(result)
        return result

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
        parts.append(f"\nSpiritual/Cultural:\n{a.spiritual_cultural or 'NOT DOCUMENTED'}")
        parts.append(f"\nStrengths:\n{a.strengths or 'NOT DOCUMENTED'}")
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

    def _parse_response(self, raw: str, patient_id: str) -> TJCAuditResult:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        data = json.loads(text)
        data["patient_id"] = patient_id
        data["audited_at"] = datetime.now(timezone.utc).isoformat()

        # Normalize EP scores and statuses from LLM output
        def normalize_score(finding: dict) -> int:
            """Normalize to official 0/1/2 scale."""
            # If LLM provided a score field, use it
            score = finding.get("score")
            if score is not None:
                try:
                    s = int(score)
                    if s in (0, 1, 2):
                        return s
                except (ValueError, TypeError):
                    pass

            # Fall back to status field
            status = str(finding.get("status", "")).lower().strip()
            if status in ("pass", "satisfactory", "met", "compliant", "2"):
                return 2
            if status in ("partial", "1"):
                return 1
            if status in ("fail", "insufficient", "failed", "unmet", "0") or "non" in status or "not" in status:
                return 0
            return 0  # default to insufficient if unclear

        def score_to_status(score: int) -> str:
            return {2: "satisfactory", 1: "partial", 0: "insufficient"}.get(score, "insufficient")

        for std in data.get("standards", []):
            for finding in std.get("findings", []):
                score = normalize_score(finding)
                finding["score"] = score
                finding["status"] = score_to_status(score)

                # Ensure SAFER rating exists for non-compliant EPs
                if score < 2 and not finding.get("safer"):
                    finding["safer"] = {
                        "likelihood": "moderate",
                        "scope": "limited",
                    }
                elif score == 2:
                    finding["safer"] = None

                # Clear citations for score 0 (absence is the finding)
                if score == 0:
                    finding["citations"] = []

            # Apply official TJC standard-level compliance rules
            self._apply_standard_compliance(std)

        return TJCAuditResult.model_validate(data)

    def _apply_standard_compliance(self, std: dict) -> None:
        """Apply official TJC standard-level compliance determination.

        Rules (from TJC accreditation manual):
        1. Any single EP scored (0) → entire standard is non_compliant
        2. If 35% or more of EPs scored (1) → standard is non_compliant
        3. Otherwise → standard is compliant
        """
        findings = std.get("findings", [])
        if not findings:
            std["overall_status"] = "non_compliant"
            std["compliance_percentage"] = 0.0
            return

        total = len(findings)
        score_2_count = sum(1 for f in findings if f.get("score") == 2)
        score_1_count = sum(1 for f in findings if f.get("score") == 1)
        score_0_count = sum(1 for f in findings if f.get("score") == 0)

        # Compliance percentage = fully compliant EPs / total
        std["compliance_percentage"] = round((score_2_count / total) * 100, 1)

        # Rule 1: Any EP at 0 → non-compliant
        if score_0_count > 0:
            std["overall_status"] = "non_compliant"
            return

        # Rule 2: 35%+ of EPs at 1 → non-compliant
        if total > 0 and (score_1_count / total) >= 0.35:
            std["overall_status"] = "non_compliant"
            return

        std["overall_status"] = "compliant"

    def _validate_audit(self, result: TJCAuditResult) -> None:
        """Post-processing: recalculate overall compliance and validate."""
        total_findings = 0
        total_score_2 = 0

        for standard in result.standards:
            if not standard.findings:
                logger.warning(
                    "Standard %s has no findings — audit may be incomplete",
                    standard.standard_id,
                )

            for f in standard.findings:
                total_findings += 1
                if f.score == 2:
                    total_score_2 += 1

        # Recalculate overall compliance
        if total_findings > 0:
            result.overall_compliance_percentage = round(
                (total_score_2 / total_findings) * 100, 1
            )
