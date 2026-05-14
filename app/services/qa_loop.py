"""
Agentic QA — Claim-by-claim verification and self-healing loop.

This is not a batch checker. It's an AGENT that:

1. DECOMPOSES the generated report into individual claims (every citation, finding, rating)
2. VERIFIES each claim against the source document — does the evidence actually exist?
3. DIAGNOSES failures — hallucination? negation flip? fabricated entity? missing evidence?
4. FIXES each broken claim — goes back to the source, finds real evidence, rewrites
5. LOOPS until every claim is grounded or explicitly marked as unsupported

Think of it like a human QA reviewer with the original patient chart open:
  "The report says the patient has a history of seizures... let me check the chart...
   no, the chart says 'denies history of seizures' — this is a negation flip. Fixing it."

Each claim gets a verdict: VERIFIED, FIXED, or UNSUPPORTED.
The agent keeps working until there are no more fixable issues.
"""

import json
import logging
import re
from dataclasses import dataclass, field

from app.schemas.asam import ASAMEvaluation
from app.schemas.patient import PatientExtraction
from app.schemas.tjc import TJCAuditResult
from app.services.llm_client import LLMClient
from app.services.qa_agent import (
    CITATION_PARTIAL,
    NEGATION_TERMS,
    AFFIRMATION_TERMS,
    check_citation,
    compile_clinical_doc,
)

logger = logging.getLogger(__name__)

MAX_FIX_ITERATIONS = 3


# ============================================================================
# Step 1: Decompose — Extract every claim from the report
# ============================================================================

@dataclass
class Claim:
    """A single verifiable claim extracted from an LLM-generated report."""
    id: str                          # e.g. "D1/Intoxication/citation_0"
    claim_text: str                  # the assertion the LLM made
    cited_text: str | None           # the quote the LLM provided as evidence
    cited_source: str | None         # where the LLM says the quote came from
    location: str                    # where in the report this claim lives
    claim_type: str                  # "citation", "rating", "finding", "status"

    # Filled by verification
    verdict: str = "pending"         # "verified", "fixed", "unsupported", "pending"
    issue: str | None = None         # what's wrong (if anything)
    issue_type: str | None = None    # "hallucination", "negation_flip", "fabrication", "weak_match"
    match_score: float = 0.0
    best_match: str | None = None    # closest text found in source
    fixed_text: str | None = None    # corrected citation after fix


def decompose_asam(evaluation: ASAMEvaluation) -> list[Claim]:
    """Extract every verifiable claim from an ASAM evaluation."""
    claims = []

    for dim in evaluation.dimensions:
        for sub in dim.subdimensions:
            loc = f"D{dim.dimension_number}/{sub.name}"

            # Each citation is a claim
            for i, cit in enumerate(sub.citations):
                claims.append(Claim(
                    id=f"{loc}/citation_{i}",
                    claim_text=cit.relevance,
                    cited_text=cit.text,
                    cited_source=cit.source,
                    location=loc,
                    claim_type="citation",
                ))

            # The rating itself is a claim
            claims.append(Claim(
                id=f"{loc}/rating",
                claim_text=f"Risk rating: {sub.risk_rating_code}, Minimum level: {sub.minimum_level}",
                cited_text=None,
                cited_source=None,
                location=loc,
                claim_type="rating",
            ))

    # LOC recommendation is a claim
    claims.append(Claim(
        id="loc/recommendation",
        claim_text=f"Recommended Level {evaluation.recommended_level}: {evaluation.level_rationale}",
        cited_text=None,
        cited_source=None,
        location="LOC Recommendation",
        claim_type="rating",
    ))

    return claims


def decompose_tjc(audit: TJCAuditResult) -> list[Claim]:
    """Extract every verifiable claim from a TJC audit."""
    claims = []

    for standard in audit.standards:
        for finding in standard.findings:
            loc = f"{standard.standard_id}/{finding.element}"

            # Each citation is a claim
            for i, cit in enumerate(finding.citations):
                claims.append(Claim(
                    id=f"{loc}/citation_{i}",
                    claim_text=finding.finding,
                    cited_text=cit.text,
                    cited_source=cit.source,
                    location=loc,
                    claim_type="citation",
                ))

            # The pass/fail status is a claim
            claims.append(Claim(
                id=f"{loc}/status",
                claim_text=f"Status: {finding.status} — {finding.finding}",
                cited_text=None,
                cited_source=None,
                location=loc,
                claim_type="status",
            ))

            # A "pass" with zero citations is suspicious
            if finding.status == "pass" and not finding.citations:
                claims.append(Claim(
                    id=f"{loc}/missing_evidence",
                    claim_text=f"Marked PASS but no citations provided for: {finding.description}",
                    cited_text=None,
                    cited_source=None,
                    location=loc,
                    claim_type="finding",
                    verdict="unsupported",
                    issue="Pass verdict has no supporting evidence",
                    issue_type="missing_citation",
                ))

    return claims


# ============================================================================
# Step 2: Verify — Check each claim against the source
# ============================================================================

def verify_claim(claim: Claim, source_doc: str) -> Claim:
    """Verify a single claim against the source document.

    For citations: does the quoted text actually exist in the source?
    For ratings/findings: are there negation flips or fabricated entities?
    """
    # Citation claims — check if the quoted text exists in source
    if claim.cited_text and claim.claim_type == "citation":
        result = check_citation(claim.cited_text, source_doc)
        claim.match_score = result["score"]
        claim.best_match = result["best_match"]

        if result["verdict"] == "verified":
            claim.verdict = "verified"
        elif result["verdict"] == "partial":
            claim.verdict = "pending"  # fixable — close match exists
            claim.issue = (
                f"Citation is imprecise (score: {result['score']:.0%}). "
                f"Closest source text: \"{result['best_match'][:100]}...\""
            )
            claim.issue_type = "weak_match"
        else:
            # Check if it's a negation flip vs pure hallucination
            if _is_negation_flip(claim.cited_text, source_doc):
                claim.verdict = "pending"
                claim.issue = "NEGATION FLIP — source says the opposite"
                claim.issue_type = "negation_flip"
            else:
                claim.verdict = "pending"
                claim.issue = f"Citation not found in source (best score: {result['score']:.0%})"
                claim.issue_type = "hallucination"

    # Status/finding claims — check for internal issues
    elif claim.claim_type in ("status", "finding", "rating"):
        if claim.claim_text and _is_negation_flip(claim.claim_text, source_doc):
            claim.verdict = "pending"
            claim.issue = "Possible negation flip in finding text"
            claim.issue_type = "negation_flip"
        elif claim.verdict != "unsupported":  # don't overwrite pre-set verdicts
            claim.verdict = "verified"  # we'll let the LLM do deeper rating checks

    return claim


def _is_negation_flip(text: str, source_doc: str) -> bool:
    """Quick check: does the text assert something the source negates (or vice versa)?"""
    text_lower = text.lower()
    source_lower = source_doc.lower()

    # Extract key clinical phrases (strip negation/affirmation triggers)
    for neg_term in NEGATION_TERMS:
        if neg_term in text_lower:
            # The generated text negates something — does the source affirm it?
            stripped = text_lower.replace(neg_term, "").strip()
            key_words = [w for w in stripped.split() if len(w) > 3][:4]
            if len(key_words) < 2:
                continue
            # Check if source has these key words in an affirmative context
            for aff_term in AFFIRMATION_TERMS:
                # Look for affirmation_term near the same key words
                pattern = re.compile(
                    rf'{re.escape(aff_term)}\s+.{{0,40}}' + r'\s+'.join(re.escape(w) for w in key_words),
                    re.IGNORECASE,
                )
                if pattern.search(source_lower):
                    return True

    for aff_term in AFFIRMATION_TERMS:
        if aff_term in text_lower:
            stripped = text_lower.replace(aff_term, "").strip()
            key_words = [w for w in stripped.split() if len(w) > 3][:4]
            if len(key_words) < 2:
                continue
            for neg_term in NEGATION_TERMS:
                pattern = re.compile(
                    rf'{re.escape(neg_term)}\s+.{{0,40}}' + r'\s+'.join(re.escape(w) for w in key_words),
                    re.IGNORECASE,
                )
                if pattern.search(source_lower):
                    return True

    return False


# ============================================================================
# Step 3: Fix — Ask the LLM to correct broken claims
# ============================================================================

CLAIM_FIX_PROMPT = """\
You are a clinical document QA agent. You have the original source chart and a \
list of claims from a generated report that FAILED verification.

Your job: for each failed claim, search the source document and either:
  A) Find the CORRECT evidence and provide the EXACT verbatim quote, or
  B) State that no supporting evidence exists in the source.

<source_document>
{source_doc}
</source_document>

<failed_claims>
{claims_text}
</failed_claims>

For EACH failed claim, respond with a JSON object in this array:
[
  {{
    "claim_id": "the claim ID",
    "action": "fix" or "unsupported",
    "corrected_citation": "EXACT verbatim text from the source document (copy-paste, do not paraphrase)" or null,
    "corrected_source": "which section of the source the text comes from" or null,
    "explanation": "what was wrong and what you found"
  }}
]

RULES:
- For "fix": the corrected_citation MUST be an EXACT substring of the source document.
  Do not paraphrase, summarize, or rephrase. Copy the text character-for-character.
- For negation flips: find the original text and preserve its polarity.
- For "unsupported": the information genuinely does not exist in the source. Be honest.
- Search the ENTIRE source document, not just the beginning.

Respond with the JSON array only."""


async def fix_claims(
    llm: LLMClient,
    source_doc: str,
    failed_claims: list[Claim],
) -> dict[str, dict]:
    """Ask the LLM to fix a batch of failed claims.

    Returns a dict mapping claim_id → fix result.
    """
    if not failed_claims:
        return {}

    claims_text = "\n\n".join(
        f"CLAIM [{c.id}] ({c.issue_type}):\n"
        f"  The report says: \"{c.claim_text[:200]}\"\n"
        f"  Cited evidence: \"{c.cited_text[:200] if c.cited_text else 'NONE'}\"\n"
        f"  Issue: {c.issue}\n"
        f"  Best match found: \"{c.best_match[:150] if c.best_match else 'NONE'}\""
        for c in failed_claims
    )

    prompt = CLAIM_FIX_PROMPT.format(
        source_doc=source_doc,
        claims_text=claims_text,
    )

    try:
        raw = await llm.complete(
            system=(
                "You are a meticulous clinical document QA agent. "
                "Your citations must be EXACT verbatim text from the source. "
                "Respond with valid JSON only."
            ),
            user=prompt,
            max_tokens=4000,
        )
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        fixes = json.loads(text.strip())
        return {f["claim_id"]: f for f in fixes if isinstance(f, dict)}
    except Exception as e:
        logger.error("Claim fix request failed: %s", e)
        return {}


def apply_fixes(claims: list[Claim], fixes: dict[str, dict], source_doc: str) -> list[Claim]:
    """Apply LLM fixes to failed claims and re-verify."""
    for claim in claims:
        if claim.id not in fixes:
            continue

        fix = fixes[claim.id]

        if fix.get("action") == "unsupported":
            claim.verdict = "unsupported"
            claim.issue = fix.get("explanation", "No supporting evidence in source")
            claim.fixed_text = None
            continue

        corrected = fix.get("corrected_citation")
        if not corrected:
            continue

        # Verify the fix is actually in the source (don't trust the LLM blindly)
        result = check_citation(corrected, source_doc)

        if result["verdict"] == "verified":
            claim.verdict = "fixed"
            claim.fixed_text = corrected
            claim.match_score = 1.0
            claim.issue = f"Fixed: {fix.get('explanation', '')}"
        elif result["score"] >= CITATION_PARTIAL:
            claim.verdict = "fixed"
            claim.fixed_text = corrected
            claim.match_score = result["score"]
            claim.issue = f"Partially fixed (score: {result['score']:.0%}): {fix.get('explanation', '')}"
        else:
            # The "fix" itself is hallucinated — mark unsupported
            claim.verdict = "unsupported"
            claim.issue = f"Fix attempt also failed verification (score: {result['score']:.0%})"

    return claims


# ============================================================================
# Step 4: Reconstruct — Build corrected output from verified claims
# ============================================================================

async def reconstruct_asam(
    llm: LLMClient,
    source_doc: str,
    original: ASAMEvaluation,
    claims: list[Claim],
) -> ASAMEvaluation:
    """Reconstruct an ASAM evaluation incorporating claim fixes.

    Sends the original evaluation + a list of corrections to the LLM,
    asks it to produce an updated version that incorporates the fixes.
    """
    corrections = []
    for c in claims:
        if c.verdict == "fixed" and c.fixed_text:
            corrections.append(
                f"- [{c.location}]: Replace citation \"{(c.cited_text or '')[:80]}...\" "
                f"with \"{c.fixed_text[:120]}\""
            )
        elif c.verdict == "unsupported":
            corrections.append(
                f"- [{c.location}]: {c.issue}. "
                f"Adjust the rating/finding to reflect only what IS documented."
            )

    if not corrections:
        return original  # nothing to change

    original_json = json.dumps(original.model_dump(), indent=2, default=str)

    prompt = f"""\
Apply these corrections to the ASAM evaluation. Change ONLY what is listed below.
Keep everything else exactly the same.

<corrections>
{chr(10).join(corrections)}
</corrections>

<source_document>
{source_doc}
</source_document>

<original_evaluation>
{original_json}
</original_evaluation>

Output the corrected evaluation as valid JSON (same schema).
All citations must be EXACT verbatim quotes from the source document."""

    try:
        from app.prompts.asam_prompt import ASAM_SYSTEM_PROMPT
        from app.services.asam_engine import ASAMEngine

        raw = await llm.complete(system=ASAM_SYSTEM_PROMPT, user=prompt)
        # Reuse the engine's parser for normalization
        engine = ASAMEngine(llm)
        return engine._parse_response(raw, original.patient_id)
    except Exception as e:
        logger.error("ASAM reconstruction failed: %s — returning original", e)
        return original


async def reconstruct_tjc(
    llm: LLMClient,
    source_doc: str,
    original: TJCAuditResult,
    claims: list[Claim],
) -> TJCAuditResult:
    """Reconstruct a TJC audit incorporating claim fixes."""
    corrections = []
    for c in claims:
        if c.verdict == "fixed" and c.fixed_text:
            corrections.append(
                f"- [{c.location}]: Replace citation \"{(c.cited_text or '')[:80]}...\" "
                f"with \"{c.fixed_text[:120]}\""
            )
        elif c.verdict == "unsupported":
            corrections.append(
                f"- [{c.location}]: {c.issue}. "
                f"If status was 'pass', change to 'fail' since evidence is missing."
            )

    if not corrections:
        return original

    original_json = json.dumps(original.model_dump(), indent=2, default=str)

    prompt = f"""\
Apply these corrections to the TJC audit. Change ONLY what is listed below.
Keep everything else exactly the same.

<corrections>
{chr(10).join(corrections)}
</corrections>

<source_document>
{source_doc}
</source_document>

<original_audit>
{original_json}
</original_audit>

Output the corrected audit as valid JSON (same schema).
All citations must be EXACT verbatim quotes from the source document.
Recalculate compliance percentages after corrections."""

    try:
        from app.prompts.tjc_prompt import TJC_SYSTEM_PROMPT
        from app.services.tjc_engine import TJCEngine

        raw = await llm.complete(system=TJC_SYSTEM_PROMPT, user=prompt)
        engine = TJCEngine(llm)
        return engine._parse_response(raw, original.patient_id)
    except Exception as e:
        logger.error("TJC reconstruction failed: %s — returning original", e)
        return original


# ============================================================================
# Step 5: The Agent Loop — orchestrates everything
# ============================================================================

def _build_linked_evidence(claims: list[Claim], source_doc: str) -> list[dict]:
    """Build linked evidence map — for each citation claim, find the exact
    character offsets in the source document so the UI can highlight them.

    Like Abridge's "Linked Evidence": click any finding → see the exact
    source text that supports it.
    """
    evidence = []
    for claim in claims:
        if claim.claim_type != "citation" or not claim.cited_text:
            continue

        result = check_citation(claim.cited_text, source_doc)
        entry = {
            "claim_id": claim.id,
            "location": claim.location,
            "cited_text": claim.cited_text,
            "verdict": claim.verdict if claim.verdict != "pending" else result["verdict"],
            "score": result["score"],
            "source_start": result.get("source_start"),
            "source_end": result.get("source_end"),
            "source_text": result.get("best_match"),
        }

        # If we have a fixed citation, link to that instead
        if claim.fixed_text:
            fix_result = check_citation(claim.fixed_text, source_doc)
            entry["fixed_text"] = claim.fixed_text
            entry["source_start"] = fix_result.get("source_start") or entry["source_start"]
            entry["source_end"] = fix_result.get("source_end") or entry["source_end"]
            entry["source_text"] = fix_result.get("best_match") or entry["source_text"]

        evidence.append(entry)

    return evidence


@dataclass
class AgentTrace:
    """Full trace of the agent's work — every claim, every fix, every iteration."""
    iterations: list[dict] = field(default_factory=list)
    total_claims: int = 0
    verified_count: int = 0
    fixed_count: int = 0
    unsupported_count: int = 0
    failed_count: int = 0


async def run_qa_agent_asam(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> dict:
    """The full agentic QA loop for ASAM evaluations.

    1. Generate initial evaluation
    2. Decompose into claims
    3. Verify each claim against source
    4. Fix failed claims (ask LLM to find real evidence)
    5. Verify the fixes (don't trust the fixer blindly)
    6. Reconstruct the evaluation with corrections
    7. Loop until clean or max iterations
    """
    from app.services.asam_engine import ASAMEngine

    source_doc = compile_clinical_doc(extraction)
    engine = ASAMEngine(llm)
    trace = AgentTrace()

    # --- Generate ---
    logger.info("QA Agent [ASAM] — Generating initial evaluation")
    evaluation = await engine.evaluate(extraction)
    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        logger.info("QA Agent [ASAM] — Iteration %d: decomposing and verifying", iteration)

        # --- Decompose ---
        claims = decompose_asam(evaluation)
        trace.total_claims = len(claims)

        # --- Verify each claim ---
        for claim in claims:
            verify_claim(claim, source_doc)

        verified = [c for c in claims if c.verdict == "verified"]
        pending = [c for c in claims if c.verdict == "pending"]
        unsupported = [c for c in claims if c.verdict == "unsupported"]

        iter_log = {
            "iteration": iteration,
            "total_claims": len(claims),
            "verified": len(verified),
            "pending": len(pending),
            "unsupported": len(unsupported),
            "issues": [
                {"id": c.id, "type": c.issue_type, "issue": c.issue}
                for c in pending
            ],
        }

        logger.info(
            "QA Agent [ASAM] — Iter %d: %d verified, %d pending, %d unsupported (of %d total)",
            iteration, len(verified), len(pending), len(unsupported), len(claims),
        )

        # --- All good? ---
        if not pending:
            iter_log["action"] = "all_verified"
            trace.iterations.append(iter_log)
            logger.info("QA Agent [ASAM] — All claims verified! Done.")
            break

        # --- Fix failed claims ---
        logger.info("QA Agent [ASAM] — Iter %d: fixing %d claims", iteration, len(pending))
        fixes = await fix_claims(llm, source_doc, pending)
        claims = apply_fixes(claims, fixes, source_doc)

        newly_fixed = [c for c in claims if c.verdict == "fixed"]
        still_broken = [c for c in claims if c.verdict == "pending"]
        newly_unsupported = [c for c in claims if c.verdict == "unsupported" and c not in unsupported]

        iter_log["fixes_applied"] = len(newly_fixed)
        iter_log["still_broken"] = len(still_broken)
        iter_log["marked_unsupported"] = len(newly_unsupported)
        iter_log["action"] = "fixes_applied"
        trace.iterations.append(iter_log)

        logger.info(
            "QA Agent [ASAM] — Iter %d: %d fixed, %d still broken, %d unsupported",
            iteration, len(newly_fixed), len(still_broken), len(newly_unsupported),
        )

        # --- Nothing got fixed? Stop. ---
        if not newly_fixed and not newly_unsupported:
            logger.warning("QA Agent [ASAM] — No progress made, stopping")
            break

        # --- Reconstruct with fixes ---
        if newly_fixed or newly_unsupported:
            logger.info("QA Agent [ASAM] — Reconstructing evaluation with %d corrections", len(newly_fixed) + len(newly_unsupported))
            evaluation = await reconstruct_asam(llm, source_doc, evaluation, claims)

    # --- Final tally + linked evidence ---
    final_claims = decompose_asam(evaluation)
    for claim in final_claims:
        verify_claim(claim, source_doc)

    linked = _build_linked_evidence(final_claims, source_doc)

    trace.verified_count = sum(1 for c in final_claims if c.verdict == "verified")
    trace.fixed_count = sum(1 for c in claims if c.verdict == "fixed")
    trace.unsupported_count = sum(1 for c in final_claims if c.verdict == "unsupported")
    trace.failed_count = sum(1 for c in final_claims if c.verdict == "pending")
    trace.total_claims = len(final_claims)

    accuracy = trace.verified_count / trace.total_claims if trace.total_claims > 0 else 0

    return {
        "evaluation": evaluation.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "iterations": len(trace.iterations),
        "claims": {
            "total": trace.total_claims,
            "verified": trace.verified_count,
            "fixed": trace.fixed_count,
            "unsupported": trace.unsupported_count,
            "failed": trace.failed_count,
        },
        "trace": [
            {k: v for k, v in it.items()}
            for it in trace.iterations
        ],
        "final_claims": [
            {
                "id": c.id,
                "location": c.location,
                "verdict": c.verdict,
                "score": c.match_score,
                "issue": c.issue,
            }
            for c in final_claims
            if c.verdict != "verified"
        ],
    }


async def run_qa_agent_tjc(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> dict:
    """The full agentic QA loop for TJC audits. Same pattern as ASAM."""
    from app.services.tjc_engine import TJCEngine

    source_doc = compile_clinical_doc(extraction)
    engine = TJCEngine(llm)
    trace = AgentTrace()

    # --- Generate ---
    logger.info("QA Agent [TJC] — Generating initial audit")
    audit = await engine.audit(extraction)
    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        logger.info("QA Agent [TJC] — Iteration %d: decomposing and verifying", iteration)

        # --- Decompose ---
        claims = decompose_tjc(audit)
        trace.total_claims = len(claims)

        # --- Verify each claim ---
        for claim in claims:
            if claim.verdict != "unsupported":  # don't re-verify pre-set verdicts
                verify_claim(claim, source_doc)

        verified = [c for c in claims if c.verdict == "verified"]
        pending = [c for c in claims if c.verdict == "pending"]
        unsupported = [c for c in claims if c.verdict == "unsupported"]

        iter_log = {
            "iteration": iteration,
            "total_claims": len(claims),
            "verified": len(verified),
            "pending": len(pending),
            "unsupported": len(unsupported),
            "issues": [
                {"id": c.id, "type": c.issue_type, "issue": c.issue}
                for c in pending
            ],
        }

        logger.info(
            "QA Agent [TJC] — Iter %d: %d verified, %d pending, %d unsupported (of %d total)",
            iteration, len(verified), len(pending), len(unsupported), len(claims),
        )

        if not pending:
            iter_log["action"] = "all_verified"
            trace.iterations.append(iter_log)
            logger.info("QA Agent [TJC] — All claims verified! Done.")
            break

        # --- Fix ---
        logger.info("QA Agent [TJC] — Iter %d: fixing %d claims", iteration, len(pending))
        fixes = await fix_claims(llm, source_doc, pending)
        claims = apply_fixes(claims, fixes, source_doc)

        newly_fixed = [c for c in claims if c.verdict == "fixed"]
        still_broken = [c for c in claims if c.verdict == "pending"]
        newly_unsupported = [c for c in claims if c.verdict == "unsupported" and c not in unsupported]

        iter_log["fixes_applied"] = len(newly_fixed)
        iter_log["still_broken"] = len(still_broken)
        iter_log["marked_unsupported"] = len(newly_unsupported)
        iter_log["action"] = "fixes_applied"
        trace.iterations.append(iter_log)

        logger.info(
            "QA Agent [TJC] — Iter %d: %d fixed, %d still broken, %d unsupported",
            iteration, len(newly_fixed), len(still_broken), len(newly_unsupported),
        )

        if not newly_fixed and not newly_unsupported:
            logger.warning("QA Agent [TJC] — No progress made, stopping")
            break

        if newly_fixed or newly_unsupported:
            logger.info("QA Agent [TJC] — Reconstructing audit with %d corrections", len(newly_fixed) + len(newly_unsupported))
            audit = await reconstruct_tjc(llm, source_doc, audit, claims)

    # --- Final tally + linked evidence ---
    final_claims = decompose_tjc(audit)
    for claim in final_claims:
        if claim.verdict != "unsupported":
            verify_claim(claim, source_doc)

    linked = _build_linked_evidence(final_claims, source_doc)

    trace.verified_count = sum(1 for c in final_claims if c.verdict == "verified")
    trace.fixed_count = sum(1 for c in claims if c.verdict == "fixed")
    trace.unsupported_count = sum(1 for c in final_claims if c.verdict == "unsupported")
    trace.failed_count = sum(1 for c in final_claims if c.verdict == "pending")
    trace.total_claims = len(final_claims)

    accuracy = trace.verified_count / trace.total_claims if trace.total_claims > 0 else 0

    return {
        "audit": audit.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "iterations": len(trace.iterations),
        "claims": {
            "total": trace.total_claims,
            "verified": trace.verified_count,
            "fixed": trace.fixed_count,
            "unsupported": trace.unsupported_count,
            "failed": trace.failed_count,
        },
        "trace": [
            {k: v for k, v in it.items()}
            for it in trace.iterations
        ],
        "final_claims": [
            {
                "id": c.id,
                "location": c.location,
                "verdict": c.verdict,
                "score": c.match_score,
                "issue": c.issue,
            }
            for c in final_claims
            if c.verdict != "verified"
        ],
    }
