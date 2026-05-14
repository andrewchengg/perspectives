"""
QA Agent — Comprehensive validation suite for LLM-generated clinical outputs.

Runs 7 independent checks against source documents:

1. CITATION VERIFICATION (RapidFuzz 3-tier: exact → fuzzy → token overlap)
2. NEGATION FLIP DETECTION (catches "denies X" → "reports X" — 30% of clinical hallucinations)
3. COMPLETENESS CHECK (all required ASAM dimensions / TJC standards present?)
4. CONSISTENCY CHECK (do ratings support LOC? do percentages add up?)
5. ADVERSARIAL LLM VERIFICATION (skeptical second-opinion, no access to generator reasoning)
6. FABRICATION SCAN (entities/medications/codes in output but not in source)
7. TEMPORAL COHERENCE (dates referenced correctly, no anachronisms)

Each check is independent and can be run in isolation.
"""

import json
import logging
import re
from datetime import datetime, timezone
from rapidfuzz import fuzz

from app.schemas.asam import ASAMEvaluation
from app.schemas.patient import PatientExtraction
from app.schemas.tjc import TJCAuditResult
from app.services.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Thresholds (tuned per research — see docs/research/llm-qa-hallucination-research.md)
# ---------------------------------------------------------------------------
CITATION_VERIFIED = 0.85       # >= this: citation exists in source
CITATION_PARTIAL = 0.60        # >= this but < VERIFIED: likely paraphrase

NEGATION_TERMS = [
    "denies", "denied", "no history", "no evidence", "negative for",
    "without", "absent", "none", "no current", "no prior", "no known",
    "ruled out", "no reported", "not present", "no significant",
    "no active", "does not", "has not", "never", "no complaints",
]
AFFIRMATION_TERMS = [
    "reports", "reported", "history of", "evidence of", "positive for",
    "presents with", "present", "active", "current", "prior", "known",
    "diagnosed", "endorses", "endorsed", "admits to", "admitted to",
    "confirmed", "significant", "complaints of", "has been", "has had",
    "acknowledges", "states", "indicates", "experiences", "suffering from",
]


# ============================================================================
# CHECK 1: Citation Verification (RapidFuzz 3-tier)
# ============================================================================

def check_citation(cited_text: str, source_doc: str) -> dict:
    """Verify a single citation against source document using 3-tier matching.

    Returns:
        {
            "cited_text": str,
            "verdict": "verified" | "partial" | "not_found",
            "score": float,
            "best_match": str | None,
            "method": "exact" | "fuzzy" | "token_overlap"
        }
    """
    cited_clean = cited_text.strip().strip('"\'')
    if len(cited_clean) < 10:
        return {
            "cited_text": cited_text,
            "verdict": "verified",
            "score": 1.0,
            "best_match": cited_clean,
            "method": "too_short_to_check",
        }

    doc_lower = source_doc.lower()
    cited_lower = cited_clean.lower()

    # Tier 1: Exact substring match
    idx = doc_lower.find(cited_lower)
    if idx != -1:
        # Pull the original-cased text from source at the found position
        exact_source = source_doc[idx:idx + len(cited_clean)]
        return {
            "cited_text": cited_text,
            "verdict": "verified",
            "score": 1.0,
            "best_match": exact_source,
            "method": "exact",
            "source_start": idx,
            "source_end": idx + len(cited_clean),
        }

    # Tier 2: Fuzzy match — try multiple strategies, track position in source
    best_score = 0.0
    best_match = None
    best_start = -1
    best_end = -1

    # Split into sentences but track their positions in the original doc
    for m in re.finditer(r'[^.!?\n]+[.!?\n]?', source_doc):
        sentence = m.group().strip()
        if len(sentence) < 10:
            continue
        s_lower = sentence.lower()
        score = max(
            fuzz.partial_ratio(cited_lower, s_lower),
            fuzz.token_set_ratio(cited_lower, s_lower),
        ) / 100.0
        if score > best_score:
            best_score = score
            best_match = sentence[:200]
            best_start = m.start()
            best_end = m.end()

    if best_score >= CITATION_VERIFIED:
        return {
            "cited_text": cited_text,
            "verdict": "verified",
            "score": best_score,
            "best_match": best_match,
            "method": "fuzzy",
            "source_start": best_start,
            "source_end": best_end,
        }

    # Tier 3: Token-level overlap — handles reordered/paraphrased citations
    cited_tokens = set(cited_lower.split())
    stopwords = {"the", "a", "an", "is", "was", "are", "were", "of", "in", "to", "and", "or", "for", "with", "on", "at", "by", "from", "that", "this", "it", "as"}
    cited_tokens -= stopwords
    if cited_tokens:
        doc_tokens = set(doc_lower.split())
        overlap = len(cited_tokens & doc_tokens) / len(cited_tokens)
        if overlap > best_score:
            best_score = overlap

    verdict = "partial" if best_score >= CITATION_PARTIAL else "not_found"
    return {
        "cited_text": cited_text,
        "verdict": verdict,
        "score": best_score,
        "best_match": best_match,
        "method": "token_overlap" if best_score >= CITATION_PARTIAL else "fuzzy",
        "source_start": best_start if best_start >= 0 else None,
        "source_end": best_end if best_end >= 0 else None,
    }


def check_all_citations_asam(source_doc: str, evaluation: ASAMEvaluation) -> list[dict]:
    """Check every citation in an ASAM evaluation."""
    results = []
    for dim in evaluation.dimensions:
        for sub in dim.subdimensions:
            for citation in sub.citations:
                result = check_citation(citation.text, source_doc)
                result["location"] = f"D{dim.dimension_number} / {sub.name}"
                result["source_label"] = citation.source
                results.append(result)
    return results


def check_all_citations_tjc(source_doc: str, audit: TJCAuditResult) -> list[dict]:
    """Check every citation in a TJC audit."""
    results = []
    for standard in audit.standards:
        for finding in standard.findings:
            for citation in finding.citations:
                result = check_citation(citation.text, source_doc)
                result["location"] = f"{standard.standard_id} / {finding.element}"
                result["source_label"] = citation.source
                results.append(result)
    return results


# ============================================================================
# CHECK 2: Negation Flip Detection
# ============================================================================

def _extract_clinical_assertions(text: str) -> list[dict]:
    """Extract negated and affirmed clinical assertions from text."""
    assertions = []
    sentences = re.split(r'[.;!\n]+', text)
    for sentence in sentences:
        s_lower = sentence.lower().strip()
        if not s_lower:
            continue
        for term in NEGATION_TERMS:
            if term in s_lower:
                assertions.append({
                    "sentence": sentence.strip(),
                    "polarity": "negative",
                    "trigger": term,
                })
                break
        else:
            for term in AFFIRMATION_TERMS:
                if term in s_lower:
                    assertions.append({
                        "sentence": sentence.strip(),
                        "polarity": "positive",
                        "trigger": term,
                    })
                    break
    return assertions


def check_negation_flips(source_doc: str, generated_text: str) -> list[dict]:
    """Detect cases where the LLM flipped a negation from the source.

    This catches the #1 clinical hallucination pattern (30% of errors):
    "denies chest pain" in source → "reports chest pain" in output.
    """
    source_assertions = _extract_clinical_assertions(source_doc)
    generated_assertions = _extract_clinical_assertions(generated_text)

    flips = []
    for gen_a in generated_assertions:
        gen_words = set(gen_a["sentence"].lower().split()) - {"the", "a", "an", "is", "was", "patient", "client", "reports", "denies", "no", "not"}
        if len(gen_words) < 2:
            continue

        for src_a in source_assertions:
            if gen_a["polarity"] == src_a["polarity"]:
                continue  # same polarity, no flip

            src_words = set(src_a["sentence"].lower().split()) - {"the", "a", "an", "is", "was", "patient", "client", "reports", "denies", "no", "not"}
            if len(src_words) < 2:
                continue

            # Check if the clinical content overlaps (same topic, different polarity)
            overlap = len(gen_words & src_words)
            union = len(gen_words | src_words)
            if union > 0 and overlap / union >= 0.4:
                flips.append({
                    "source_text": src_a["sentence"],
                    "source_polarity": src_a["polarity"],
                    "generated_text": gen_a["sentence"],
                    "generated_polarity": gen_a["polarity"],
                    "overlap_ratio": round(overlap / union, 2),
                    "severity": "critical",
                    "explanation": (
                        f"Source says '{src_a['trigger']}' (negative) but output says "
                        f"'{gen_a['trigger']}' (positive)"
                        if src_a["polarity"] == "negative"
                        else f"Source says '{src_a['trigger']}' (positive) but output says "
                        f"'{gen_a['trigger']}' (negative)"
                    ),
                })

    return flips


# ============================================================================
# CHECK 3: Completeness
# ============================================================================

REQUIRED_ASAM_DIMENSIONS = {1, 2, 3, 4, 5}  # D6 is separate (dimension_6_notes)
REQUIRED_TJC_STANDARDS = {"CTS.01", "CTS.02", "CTS.03", "CTS.04", "CTS.05"}


def check_completeness_asam(evaluation: ASAMEvaluation) -> list[dict]:
    """Verify all required ASAM dimensions are present with substance."""
    gaps = []

    found_dims = {d.dimension_number for d in evaluation.dimensions}
    for d in REQUIRED_ASAM_DIMENSIONS:
        if d not in found_dims:
            gaps.append({
                "expected": f"Dimension {d}",
                "description": f"ASAM Dimension {d} is completely missing from evaluation",
                "severity": "critical",
            })

    for dim in evaluation.dimensions:
        if not dim.subdimensions:
            gaps.append({
                "expected": f"D{dim.dimension_number} subdimensions",
                "description": f"Dimension {dim.dimension_number} ({dim.dimension_name}) has no subdimensions",
                "severity": "critical",
            })
        for sub in dim.subdimensions:
            if not sub.citations:
                gaps.append({
                    "expected": f"D{dim.dimension_number}/{sub.name} citations",
                    "description": f"Subdimension '{sub.name}' has no supporting citations",
                    "severity": "major",
                })
            if not sub.rationale or len(sub.rationale.strip()) < 20:
                gaps.append({
                    "expected": f"D{dim.dimension_number}/{sub.name} rationale",
                    "description": f"Subdimension '{sub.name}' has insufficient rationale",
                    "severity": "major",
                })

    if not evaluation.loc_determination_steps:
        gaps.append({
            "expected": "LOC determination steps",
            "description": "No LOC determination steps (top-down algorithm) documented",
            "severity": "critical",
        })

    if not evaluation.recommended_level:
        gaps.append({
            "expected": "Recommended level",
            "description": "No recommended level of care specified",
            "severity": "critical",
        })

    if not evaluation.clinical_summary or len(evaluation.clinical_summary.strip()) < 50:
        gaps.append({
            "expected": "Clinical summary",
            "description": "Clinical summary is missing or too brief",
            "severity": "major",
        })

    return gaps


def check_completeness_tjc(audit: TJCAuditResult) -> list[dict]:
    """Verify all required TJC standards are present with substance."""
    gaps = []

    found_standards = {s.standard_id for s in audit.standards}
    for std_id in REQUIRED_TJC_STANDARDS:
        if std_id not in found_standards:
            gaps.append({
                "expected": std_id,
                "description": f"TJC standard {std_id} is completely missing from audit",
                "severity": "critical",
            })

    for standard in audit.standards:
        if not standard.findings:
            gaps.append({
                "expected": f"{standard.standard_id} findings",
                "description": f"Standard {standard.standard_id} ({standard.standard_name}) has no findings",
                "severity": "critical",
            })
        for finding in standard.findings:
            if finding.status == "fail" and not finding.remediation:
                gaps.append({
                    "expected": f"{finding.element} remediation",
                    "description": f"Failed finding '{finding.element}' has no remediation recommendation",
                    "severity": "major",
                })
            if not finding.citations and finding.status == "pass":
                gaps.append({
                    "expected": f"{finding.element} citations",
                    "description": f"Passing finding '{finding.element}' has no supporting citations",
                    "severity": "major",
                })

    if not audit.audit_summary or len(audit.audit_summary.strip()) < 50:
        gaps.append({
            "expected": "Audit summary",
            "description": "Audit summary is missing or too brief",
            "severity": "major",
        })

    return gaps


# ============================================================================
# CHECK 4: Consistency
# ============================================================================

def check_consistency_asam(evaluation: ASAMEvaluation) -> list[dict]:
    """Check internal consistency of ASAM evaluation."""
    issues = []

    # 4a: LOC vs algorithmic flowchart
    from app.services.asam_flowchart import SubdimensionResult, determine_loc

    subdim_results = []
    for dim in evaluation.dimensions:
        for sub in dim.subdimensions:
            subdim_results.append(
                SubdimensionResult(
                    dimension=dim.dimension_number,
                    subdimension=sub.name,
                    risk_code=sub.risk_rating_code,
                    minimum_level=sub.minimum_level,
                )
            )

    if subdim_results:
        algorithmic = determine_loc(subdim_results)
        if algorithmic.level != evaluation.recommended_level:
            issues.append({
                "issue_type": "loc_mismatch",
                "description": (
                    f"LLM recommended Level {evaluation.recommended_level} but "
                    f"rule-based flowchart suggests Level {algorithmic.level}"
                ),
                "expected": algorithmic.level,
                "actual": evaluation.recommended_level,
                "severity": "critical",
                "algorithm_rationale": algorithmic.rationale,
            })

    # 4b: COE indicated but no mental health subdimension flagged
    if evaluation.coe_indicated:
        has_mh_risk = False
        for dim in evaluation.dimensions:
            if dim.dimension_number == 3:
                for sub in dim.subdimensions:
                    if sub.risk_rating_code not in ("0", "ANY", "A"):
                        has_mh_risk = True
        if not has_mh_risk:
            issues.append({
                "issue_type": "coe_without_mh_risk",
                "description": "COE indicated but no elevated risk in Dimension 3 (Emotional/Behavioral/Cognitive)",
                "expected": "Elevated D3 risk for COE",
                "actual": "All D3 subdimensions at baseline risk",
                "severity": "major",
            })

    # 4c: LOC determination steps should reference the recommended level
    if evaluation.loc_determination_steps:
        step_texts = " ".join(s.result + " " + s.rationale for s in evaluation.loc_determination_steps)
        if evaluation.recommended_level not in step_texts:
            issues.append({
                "issue_type": "loc_steps_disconnect",
                "description": f"LOC determination steps don't reference the recommended level '{evaluation.recommended_level}'",
                "expected": f"Level {evaluation.recommended_level} mentioned in steps",
                "actual": "Not found in step results/rationale",
                "severity": "major",
            })

    return issues


def check_consistency_tjc(audit: TJCAuditResult) -> list[dict]:
    """Check internal consistency of TJC audit."""
    issues = []

    # 4a: Overall percentage vs calculated
    total_findings = 0
    total_pass = 0
    for standard in audit.standards:
        for finding in standard.findings:
            total_findings += 1
            if finding.status in ("pass", "not_applicable"):
                total_pass += 1

    if total_findings > 0:
        calculated_pct = (total_pass / total_findings) * 100
        if abs(calculated_pct - audit.overall_compliance_percentage) > 5:
            issues.append({
                "issue_type": "overall_percentage_mismatch",
                "description": (
                    f"Reported overall compliance {audit.overall_compliance_percentage:.1f}% "
                    f"but calculated {calculated_pct:.1f}% from individual findings"
                ),
                "expected": f"{calculated_pct:.1f}%",
                "actual": f"{audit.overall_compliance_percentage:.1f}%",
                "severity": "major",
            })

    # 4b: Per-standard percentage vs calculated
    for standard in audit.standards:
        if not standard.findings:
            continue
        std_total = len(standard.findings)
        std_pass = sum(1 for f in standard.findings if f.status in ("pass", "not_applicable"))
        calc_pct = (std_pass / std_total) * 100
        if abs(calc_pct - standard.compliance_percentage) > 10:
            issues.append({
                "issue_type": "standard_percentage_mismatch",
                "description": (
                    f"{standard.standard_id}: reported {standard.compliance_percentage:.1f}% "
                    f"but calculated {calc_pct:.1f}%"
                ),
                "expected": f"{calc_pct:.1f}%",
                "actual": f"{standard.compliance_percentage:.1f}%",
                "severity": "major",
            })

    # 4c: Critical gaps should reference actual failed findings
    failed_elements = set()
    for standard in audit.standards:
        for finding in standard.findings:
            if finding.status == "fail":
                failed_elements.add(finding.element)

    for gap in audit.critical_gaps:
        if gap.element not in failed_elements:
            issues.append({
                "issue_type": "phantom_critical_gap",
                "description": f"Critical gap references '{gap.element}' but it's not marked as failed in findings",
                "expected": f"'{gap.element}' in failed findings",
                "actual": "Not found among failed findings",
                "severity": "major",
            })

    # 4d: Standard marked compliant but has failed findings
    for standard in audit.standards:
        has_fail = any(f.status == "fail" for f in standard.findings)
        if has_fail and standard.overall_status == "compliant":
            issues.append({
                "issue_type": "status_contradiction",
                "description": f"{standard.standard_id} marked 'compliant' but has failed findings",
                "expected": "non_compliant or partial",
                "actual": "compliant",
                "severity": "critical",
            })

    return issues


# ============================================================================
# CHECK 5: Adversarial LLM Verification
# ============================================================================

ADVERSARIAL_ASAM_PROMPT = """\
You are an independent clinical QA auditor. You have NEVER seen this evaluation before.
Your job is to FIND ERRORS — not confirm correctness. Approach every claim with skepticism.

<source_document>
{clinical_doc}
</source_document>

<evaluation_to_check>
{eval_json}
</evaluation_to_check>

For EACH claim in the evaluation:
1. Search the source document for the cited evidence. Is the quoted text actually there?
   Could the quote be a paraphrase, fabrication, or taken out of context?
2. Does the cited evidence actually support the conclusion drawn?
3. Is there CONTRADICTING evidence in the source that was ignored?
4. Are there negation flips? (e.g., source says "denies X" but evaluation says "reports X")
5. Are risk ratings proportional to the evidence? Flag any over-rated or under-rated.

Do NOT assume the evaluation is correct. Your value comes from catching what the first pass missed.

Respond with JSON only:
{{
  "hallucinations": ["list of claims not supported by source — quote the specific claim"],
  "missed_evidence": ["important source content the evaluation ignored"],
  "negation_errors": ["any polarity flips between source and evaluation"],
  "rating_concerns": ["ratings that seem too high or too low given evidence"],
  "overall_quality": "good|acceptable|poor",
  "summary": "2-3 sentence summary of findings"
}}"""

ADVERSARIAL_TJC_PROMPT = """\
You are an independent clinical QA auditor. You have NEVER seen this audit before.
Your job is to FIND ERRORS — not confirm correctness. Approach every finding with skepticism.

<source_document>
{clinical_doc}
</source_document>

<audit_to_check>
{audit_json}
</audit_to_check>

For EACH finding in the audit:
1. If marked PASS: Search the source document thoroughly — is the required element ACTUALLY documented?
   Could this be a false pass where the auditor assumed documentation exists but it doesn't?
2. If marked FAIL: Search the source document thoroughly — is there text that actually DOES satisfy
   this requirement that the auditor missed? Could this be a false fail?
3. Check every citation — does the quoted text actually appear in the source?
4. Are there negation flips? (source says "no history of X", audit interprets as "history of X")
5. Are there compliance gaps the audit completely missed?

Do NOT trust the audit. Your job is adversarial verification.

Respond with JSON only:
{{
  "false_passes": ["findings marked pass that should be fail — explain why"],
  "false_failures": ["findings marked fail that should be pass — quote the supporting evidence"],
  "hallucinated_citations": ["citations that don't exist in the source"],
  "negation_errors": ["any polarity flips between source and audit"],
  "missed_gaps": ["compliance issues the audit didn't catch"],
  "overall_quality": "good|acceptable|poor",
  "summary": "2-3 sentence summary of findings"
}}"""


async def adversarial_verify_asam(
    llm: LLMClient, clinical_doc: str, evaluation: ASAMEvaluation
) -> dict:
    """Run adversarial LLM verification on an ASAM evaluation.

    Uses a separate prompt with skeptical framing — the verifier never sees
    the generator's chain-of-thought reasoning (only structured output).
    This prevents confirmation bias (per CoVe research, ACL Findings 2024).
    """
    eval_json = json.dumps(evaluation.model_dump(), indent=2, default=str)
    prompt = ADVERSARIAL_ASAM_PROMPT.format(
        clinical_doc=clinical_doc,
        eval_json=eval_json,
    )

    try:
        raw = await llm.complete(
            system=(
                "You are a skeptical clinical QA reviewer. Your job is to find errors, "
                "not confirm correctness. Be thorough and adversarial. Respond with valid JSON only."
            ),
            user=prompt,
            max_tokens=3000,
        )
        return _parse_json_response(raw)
    except Exception as e:
        logger.error("Adversarial ASAM verification failed: %s", e)
        return {"error": str(e), "overall_quality": "unknown", "summary": f"Verification failed: {e}"}


async def adversarial_verify_tjc(
    llm: LLMClient, clinical_doc: str, audit: TJCAuditResult
) -> dict:
    """Run adversarial LLM verification on a TJC audit."""
    audit_json = json.dumps(audit.model_dump(), indent=2, default=str)
    prompt = ADVERSARIAL_TJC_PROMPT.format(
        clinical_doc=clinical_doc,
        audit_json=audit_json,
    )

    try:
        raw = await llm.complete(
            system=(
                "You are a skeptical clinical QA reviewer. Your job is to find errors, "
                "not confirm correctness. Be thorough and adversarial. Respond with valid JSON only."
            ),
            user=prompt,
            max_tokens=3000,
        )
        return _parse_json_response(raw)
    except Exception as e:
        logger.error("Adversarial TJC verification failed: %s", e)
        return {"error": str(e), "overall_quality": "unknown", "summary": f"Verification failed: {e}"}


# ============================================================================
# CHECK 6: Fabrication Scan
# ============================================================================

def scan_fabrications(source_doc: str, generated_text: str) -> list[dict]:
    """Detect likely fabricated entities — medications, diagnoses, codes, or
    proper nouns that appear in the generated text but not in the source.

    This catches the most common fabrication pattern: the LLM invents a
    medication name, lab value, or diagnosis code that was never documented.
    """
    fabrications = []

    # Extract medication-like patterns:
    # Strategy 1: Words with common drug suffixes
    # Strategy 2: Any word directly followed by a dosage (e.g., "disulfiram 250mg")
    med_pattern = re.compile(
        r'\b([A-Z][a-z]+(?:ine|ole|ide|ate|pam|lol|pin|fen|lin|cin|xin|tin|van|mab|nib|ram|lam|tam|zam|pril|tan|one|yde|ase)\b'
        r'(?:\s+\d+\s*(?:mg|mcg|ml|units?))?)',
        re.IGNORECASE,
    )
    # Also catch "word + dosage" pattern for drugs with unusual suffixes
    dosage_pattern = re.compile(r'\b([A-Za-z]{4,})\s+\d+\s*(?:mg|mcg|ml|units?)\b', re.IGNORECASE)
    gen_meds = set(m.lower() for m in med_pattern.findall(generated_text))
    gen_meds |= set(m.lower() for m in dosage_pattern.findall(generated_text))
    src_meds = set(m.lower() for m in med_pattern.findall(source_doc))
    src_meds |= set(m.lower() for m in dosage_pattern.findall(source_doc))
    for med in gen_meds - src_meds:
        if len(med) > 4:  # skip very short matches
            fabrications.append({
                "type": "medication",
                "value": med,
                "severity": "critical",
                "explanation": f"Medication '{med}' appears in output but not in source documents",
            })

    # Extract ICD/DSM codes
    code_pattern = re.compile(r'\b([A-Z]\d{2}(?:\.\d{1,2})?)\b')
    gen_codes = set(code_pattern.findall(generated_text))
    src_codes = set(code_pattern.findall(source_doc))
    for code in gen_codes - src_codes:
        fabrications.append({
            "type": "diagnostic_code",
            "value": code,
            "severity": "major",
            "explanation": f"Diagnostic code '{code}' appears in output but not in source documents",
        })

    # Extract lab values (number + unit patterns)
    lab_pattern = re.compile(r'(\d+(?:\.\d+)?)\s*(mg/dL|mmol/L|mEq/L|ng/mL|pg/mL|µg/dL|IU/L|U/L|g/dL|%|mmHg|bpm)', re.IGNORECASE)
    gen_labs = set((v, u.lower()) for v, u in lab_pattern.findall(generated_text))
    src_labs = set((v, u.lower()) for v, u in lab_pattern.findall(source_doc))
    for val, unit in gen_labs - src_labs:
        fabrications.append({
            "type": "lab_value",
            "value": f"{val} {unit}",
            "severity": "critical",
            "explanation": f"Lab value '{val} {unit}' appears in output but not in source documents",
        })

    return fabrications


# ============================================================================
# CHECK 7: Temporal Coherence
# ============================================================================

def check_temporal_coherence(source_doc: str, generated_text: str) -> list[dict]:
    """Check that dates referenced in generated text actually exist in source
    and that temporal claims (e.g., 'for the past 3 years') are consistent.
    """
    issues = []

    # Extract all dates from both
    date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|\w+ \d{1,2},? \d{4})\b')
    gen_dates = set(date_pattern.findall(generated_text))
    src_dates = set(date_pattern.findall(source_doc))

    for d in gen_dates - src_dates:
        # Skip if it's a date that could be generated (like audited_at)
        issues.append({
            "type": "date_not_in_source",
            "value": d,
            "severity": "major",
            "explanation": f"Date '{d}' appears in output but not in source documents — possible fabrication",
        })

    # Check duration claims (e.g., "for 5 years", "since 2019")
    duration_pattern = re.compile(r'(?:for|past|last|over)\s+(\d+)\s+(years?|months?|weeks?|days?)', re.IGNORECASE)
    gen_durations = duration_pattern.findall(generated_text)
    src_durations = duration_pattern.findall(source_doc)
    src_duration_set = set((n, u.lower().rstrip('s')) for n, u in src_durations)

    for num, unit in gen_durations:
        normalized = (num, unit.lower().rstrip('s'))
        if normalized not in src_duration_set:
            # Check if source has any similar duration
            issues.append({
                "type": "duration_mismatch",
                "value": f"{num} {unit}",
                "severity": "major",
                "explanation": f"Duration '{num} {unit}' in output not found in source — verify accuracy",
            })

    return issues


# ============================================================================
# Compile Clinical Document (shared utility)
# ============================================================================

def compile_clinical_doc(extraction: PatientExtraction) -> str:
    """Compile patient extraction into a single text document for QA checks."""
    parts = []
    p = extraction.patient
    parts.append(f"Name: {p.first_name} {p.last_name}")
    parts.append(f"DOB: {p.date_of_birth}, Gender: {p.gender}")
    parts.append(f"Admission: {p.admission_date}")
    parts.append("")
    parts.append(f"=== ASSESSMENT ({extraction.assessment.assessment_date}) ===")
    parts.append(extraction.assessment.raw_text)
    parts.append("")
    for note in sorted(extraction.progress_notes, key=lambda n: n.note_date):
        parts.append(f"=== {note.note_format} NOTE ({note.note_date}) ===")
        parts.append(note.raw_text)
        parts.append("")
    return "\n".join(parts)


def _flatten_generated_text_asam(evaluation: ASAMEvaluation) -> str:
    """Extract all generated prose from an ASAM evaluation for text-level checks."""
    parts = []
    for dim in evaluation.dimensions:
        parts.append(dim.dimension_name)
        parts.extend(dim.key_factors)
        for sub in dim.subdimensions:
            parts.append(sub.rationale)
            for c in sub.citations:
                parts.append(c.relevance)
    for step in evaluation.loc_determination_steps:
        parts.append(step.result)
        parts.append(step.rationale)
    parts.append(evaluation.level_rationale)
    parts.append(evaluation.clinical_summary)
    parts.append(evaluation.dimension_6_notes)
    return "\n".join(parts)


def _flatten_generated_text_tjc(audit: TJCAuditResult) -> str:
    """Extract all generated prose from a TJC audit for text-level checks."""
    parts = []
    for standard in audit.standards:
        for finding in standard.findings:
            parts.append(finding.finding)
            if finding.remediation:
                parts.append(finding.remediation)
            for c in finding.citations:
                parts.append(c.relevance)
    for gap in audit.critical_gaps:
        parts.append(gap.description)
        parts.append(gap.impact)
    parts.extend(audit.recommendations)
    parts.append(audit.audit_summary)
    return "\n".join(parts)


# ============================================================================
# JSON parsing utility
# ============================================================================

def _parse_json_response(raw: str) -> dict:
    """Parse LLM JSON response, handling markdown code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return json.loads(text.strip())


# ============================================================================
# Scoring & Aggregation
# ============================================================================

def compute_confidence_score(
    citation_results: list[dict],
    negation_flips: list[dict],
    completeness_gaps: list[dict],
    consistency_issues: list[dict],
    fabrications: list[dict],
    temporal_issues: list[dict],
    llm_verification: dict | None = None,
) -> float:
    """Compute an aggregated confidence score (0.0-1.0) from all check results.

    Weights:
    - Citation verification: 25% (most direct measure of grounding)
    - Negation detection: 20% (most dangerous clinical error type)
    - Completeness: 15%
    - Consistency: 15%
    - Fabrication scan: 15%
    - Temporal coherence: 5%
    - LLM verification: 5% (subjective, used as tiebreaker)
    """
    scores = {}

    # Citation score: fraction verified
    if citation_results:
        verified = sum(1 for r in citation_results if r["verdict"] == "verified")
        scores["citations"] = verified / len(citation_results)
    else:
        scores["citations"] = 1.0  # no citations to check

    # Negation: binary (any flip is very bad)
    scores["negation"] = 0.0 if negation_flips else 1.0

    # Completeness: penalize by severity
    critical_gaps = sum(1 for g in completeness_gaps if g["severity"] == "critical")
    major_gaps = sum(1 for g in completeness_gaps if g["severity"] == "major")
    if critical_gaps > 0:
        scores["completeness"] = 0.0
    elif major_gaps > 0:
        scores["completeness"] = max(0.0, 1.0 - (major_gaps * 0.2))
    else:
        scores["completeness"] = 1.0

    # Consistency: penalize by severity
    critical_issues = sum(1 for i in consistency_issues if i.get("severity") == "critical")
    major_issues = sum(1 for i in consistency_issues if i.get("severity") == "major")
    if critical_issues > 0:
        scores["consistency"] = 0.0
    elif major_issues > 0:
        scores["consistency"] = max(0.0, 1.0 - (major_issues * 0.25))
    else:
        scores["consistency"] = 1.0

    # Fabrication: binary per critical, scaled per major
    critical_fabs = sum(1 for f in fabrications if f["severity"] == "critical")
    if critical_fabs > 0:
        scores["fabrication"] = 0.0
    elif fabrications:
        scores["fabrication"] = max(0.0, 1.0 - (len(fabrications) * 0.15))
    else:
        scores["fabrication"] = 1.0

    # Temporal
    if temporal_issues:
        scores["temporal"] = max(0.0, 1.0 - (len(temporal_issues) * 0.2))
    else:
        scores["temporal"] = 1.0

    # LLM verification
    if llm_verification and "overall_quality" in llm_verification:
        quality_map = {"good": 1.0, "acceptable": 0.7, "poor": 0.3}
        scores["llm_verify"] = quality_map.get(llm_verification["overall_quality"], 0.5)
    else:
        scores["llm_verify"] = 0.5

    weights = {
        "citations": 0.25,
        "negation": 0.20,
        "completeness": 0.15,
        "consistency": 0.15,
        "fabrication": 0.15,
        "temporal": 0.05,
        "llm_verify": 0.05,
    }

    return round(sum(scores[k] * weights[k] for k in weights), 3)


# ============================================================================
# Main Orchestrator — runs all checks
# ============================================================================

class QAAgent:
    """Comprehensive QA suite for LLM-generated clinical intelligence outputs.

    Runs 7 independent checks:
    1. Citation verification (RapidFuzz 3-tier)
    2. Negation flip detection
    3. Completeness check
    4. Consistency check
    5. Adversarial LLM verification
    6. Fabrication scan
    7. Temporal coherence

    Each check can also be called independently via the module-level functions.
    """

    def __init__(self, llm_client: LLMClient):
        self._llm = llm_client

    async def validate_asam(
        self, extraction: PatientExtraction, evaluation: ASAMEvaluation
    ) -> dict:
        """Run full QA suite on an ASAM evaluation."""
        source_doc = compile_clinical_doc(extraction)
        generated_text = _flatten_generated_text_asam(evaluation)

        # Checks 1-4, 6-7 are deterministic (no LLM needed)
        citation_results = check_all_citations_asam(source_doc, evaluation)
        negation_flips = check_negation_flips(source_doc, generated_text)
        completeness_gaps = check_completeness_asam(evaluation)
        consistency_issues = check_consistency_asam(evaluation)
        fabrications = scan_fabrications(source_doc, generated_text)
        temporal_issues = check_temporal_coherence(source_doc, generated_text)

        # Check 5: Adversarial LLM verification (separate API call)
        llm_verification = await adversarial_verify_asam(self._llm, source_doc, evaluation)

        # Aggregate
        confidence = compute_confidence_score(
            citation_results, negation_flips, completeness_gaps,
            consistency_issues, fabrications, temporal_issues, llm_verification,
        )

        citation_fails = [r for r in citation_results if r["verdict"] == "not_found"]
        citation_partials = [r for r in citation_results if r["verdict"] == "partial"]

        checks_summary = [
            {
                "check": "citation_verification",
                "passed": len(citation_fails) == 0,
                "verified": sum(1 for r in citation_results if r["verdict"] == "verified"),
                "partial": len(citation_partials),
                "not_found": len(citation_fails),
                "total": len(citation_results),
            },
            {
                "check": "negation_detection",
                "passed": len(negation_flips) == 0,
                "flips_found": len(negation_flips),
            },
            {
                "check": "completeness",
                "passed": not any(g["severity"] == "critical" for g in completeness_gaps),
                "critical_gaps": sum(1 for g in completeness_gaps if g["severity"] == "critical"),
                "major_gaps": sum(1 for g in completeness_gaps if g["severity"] == "major"),
                "minor_gaps": sum(1 for g in completeness_gaps if g["severity"] == "minor"),
            },
            {
                "check": "consistency",
                "passed": not any(i.get("severity") == "critical" for i in consistency_issues),
                "issues": len(consistency_issues),
            },
            {
                "check": "adversarial_llm_verification",
                "passed": llm_verification.get("overall_quality") in ("good", "acceptable"),
                "quality": llm_verification.get("overall_quality", "unknown"),
            },
            {
                "check": "fabrication_scan",
                "passed": not any(f["severity"] == "critical" for f in fabrications),
                "fabrications_found": len(fabrications),
            },
            {
                "check": "temporal_coherence",
                "passed": len(temporal_issues) == 0,
                "issues": len(temporal_issues),
            },
        ]

        all_deterministic_pass = all(c["passed"] for c in checks_summary if c["check"] != "adversarial_llm_verification")

        return {
            "target": "asam",
            "overall_pass": all_deterministic_pass and confidence >= 0.7,
            "confidence_score": confidence,
            "checks": checks_summary,
            "citation_details": citation_results,
            "negation_flips": negation_flips,
            "completeness_gaps": completeness_gaps,
            "consistency_issues": consistency_issues,
            "fabrications": fabrications,
            "temporal_issues": temporal_issues,
            "llm_verification": llm_verification,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def validate_tjc(
        self, extraction: PatientExtraction, audit: TJCAuditResult
    ) -> dict:
        """Run full QA suite on a TJC audit."""
        source_doc = compile_clinical_doc(extraction)
        generated_text = _flatten_generated_text_tjc(audit)

        citation_results = check_all_citations_tjc(source_doc, audit)
        negation_flips = check_negation_flips(source_doc, generated_text)
        completeness_gaps = check_completeness_tjc(audit)
        consistency_issues = check_consistency_tjc(audit)
        fabrications = scan_fabrications(source_doc, generated_text)
        temporal_issues = check_temporal_coherence(source_doc, generated_text)

        llm_verification = await adversarial_verify_tjc(self._llm, source_doc, audit)

        confidence = compute_confidence_score(
            citation_results, negation_flips, completeness_gaps,
            consistency_issues, fabrications, temporal_issues, llm_verification,
        )

        citation_fails = [r for r in citation_results if r["verdict"] == "not_found"]
        citation_partials = [r for r in citation_results if r["verdict"] == "partial"]

        checks_summary = [
            {
                "check": "citation_verification",
                "passed": len(citation_fails) == 0,
                "verified": sum(1 for r in citation_results if r["verdict"] == "verified"),
                "partial": len(citation_partials),
                "not_found": len(citation_fails),
                "total": len(citation_results),
            },
            {
                "check": "negation_detection",
                "passed": len(negation_flips) == 0,
                "flips_found": len(negation_flips),
            },
            {
                "check": "completeness",
                "passed": not any(g["severity"] == "critical" for g in completeness_gaps),
                "critical_gaps": sum(1 for g in completeness_gaps if g["severity"] == "critical"),
                "major_gaps": sum(1 for g in completeness_gaps if g["severity"] == "major"),
                "minor_gaps": sum(1 for g in completeness_gaps if g["severity"] == "minor"),
            },
            {
                "check": "consistency",
                "passed": not any(i.get("severity") == "critical" for i in consistency_issues),
                "issues": len(consistency_issues),
            },
            {
                "check": "adversarial_llm_verification",
                "passed": llm_verification.get("overall_quality") in ("good", "acceptable"),
                "quality": llm_verification.get("overall_quality", "unknown"),
            },
            {
                "check": "fabrication_scan",
                "passed": not any(f["severity"] == "critical" for f in fabrications),
                "fabrications_found": len(fabrications),
            },
            {
                "check": "temporal_coherence",
                "passed": len(temporal_issues) == 0,
                "issues": len(temporal_issues),
            },
        ]

        all_deterministic_pass = all(c["passed"] for c in checks_summary if c["check"] != "adversarial_llm_verification")

        return {
            "target": "tjc",
            "overall_pass": all_deterministic_pass and confidence >= 0.7,
            "confidence_score": confidence,
            "checks": checks_summary,
            "citation_details": citation_results,
            "negation_flips": negation_flips,
            "completeness_gaps": completeness_gaps,
            "consistency_issues": consistency_issues,
            "fabrications": fabrications,
            "temporal_issues": temporal_issues,
            "llm_verification": llm_verification,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }
