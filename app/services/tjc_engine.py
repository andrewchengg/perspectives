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

        # Normalize LLM output — fuzzy match status values
        def normalize_status(s: str) -> str:
            s = s.lower().strip()
            if s in ("compliant", "pass", "met"):
                return "compliant"
            if "non" in s or "fail" in s or "not" in s or "unmet" in s:
                return "non_compliant"
            if "partial" in s:
                return "partial"
            if "n/a" in s or "applicable" in s:
                return "not_applicable"
            return s

        def normalize_finding_status(s: str) -> str:
            s = s.lower().strip()
            if s in ("pass", "met", "compliant", "yes"):
                return "pass"
            if s in ("fail", "failed", "unmet", "no") or "non" in s or "not" in s:
                return "fail"
            if "partial" in s:
                return "partial"
            if "n/a" in s or "applicable" in s:
                return "not_applicable"
            return s

        for std in data.get("standards", []):
            std["overall_status"] = normalize_status(std.get("overall_status", ""))
            for finding in std.get("findings", []):
                finding["status"] = normalize_finding_status(finding.get("status", ""))

        return TJCAuditResult.model_validate(data)

    def _validate_audit(self, result: TJCAuditResult) -> None:
        expected_standards = {"CTS.02", "CTS.03", "CTS.04", "CTS.06"}
        found_standards = {s.standard_id for s in result.standards}

        missing = expected_standards - found_standards
        if missing:
            logger.warning("Audit missing standards: %s", missing)

        for standard in result.standards:
            if not standard.findings:
                logger.warning(
                    "Standard %s has no findings — audit may be incomplete",
                    standard.standard_id,
                )

            fail_count = sum(1 for f in standard.findings if f.status == "fail")
            total = len(standard.findings)
            if total > 0:
                calculated_pct = ((total - fail_count) / total) * 100
                if abs(calculated_pct - standard.compliance_percentage) > 10:
                    logger.warning(
                        "Standard %s: reported compliance %.1f%% but calculated %.1f%%",
                        standard.standard_id,
                        standard.compliance_percentage,
                        calculated_pct,
                    )
