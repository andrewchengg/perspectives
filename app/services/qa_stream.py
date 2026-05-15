"""
Streaming QA Agent — SSE event stream showing the agent working live.

Now with real-time LLM token streaming — you see the model's chain-of-thought
as it reasons through each ASAM dimension, like watching Claude Code think.
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from app.schemas.patient import PatientExtraction
from app.services.llm_client import LLMClient
from app.services.qa_agent import compile_clinical_doc
from app.services.qa_loop import (
    Claim,
    CLAIM_FIX_PROMPT,
    _build_linked_evidence,
    apply_fixes,
    decompose_asam,
    decompose_tjc,
    verify_claim,
    MAX_FIX_ITERATIONS,
)

logger = logging.getLogger(__name__)

TOKEN_BATCH_SIZE = 6  # batch tokens before emitting SSE (reduces overhead)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _stream_llm(llm: LLMClient, system: str, user: str, label: str, pass_num: int = 0, max_tokens: int = 8192):
    """Stream an LLM call, yielding SSE events for each token batch.

    Yields: (sse_event_string, None) for token events
            (None, full_text) as the final yield with the complete response
    """
    yield _sse("llm_stream_start", {"pass": pass_num, "label": label}), None

    full_text = ""
    buffer = ""
    async for chunk in llm.stream(system=system, user=user, max_tokens=max_tokens):
        full_text += chunk
        buffer += chunk
        if len(buffer) >= TOKEN_BATCH_SIZE:
            yield _sse("llm_token", {"text": buffer, "pass": pass_num, "label": label}), None
            buffer = ""
            await asyncio.sleep(0)  # force flush to browser

    # Flush remaining buffer
    if buffer:
        yield _sse("llm_token", {"text": buffer, "pass": pass_num, "label": label}), None

    yield _sse("llm_stream_end", {"pass": pass_num, "label": label}), None

    # Final yield: the complete text
    yield None, full_text


async def _stream_fix_claims(
    llm: LLMClient,
    source_doc: str,
    failed_claims: list[Claim],
) -> AsyncGenerator[tuple[str | None, dict | None], None]:
    """Stream the fix_claims LLM call, yielding token events + final result."""
    if not failed_claims:
        yield None, {}
        return

    claims_text = "\n\n".join(
        f"CLAIM [{c.id}] ({c.issue_type}):\n"
        f"  The report says: \"{c.claim_text[:200]}\"\n"
        f"  Cited evidence: \"{(c.cited_text or 'NONE')[:200]}\"\n"
        f"  Issue: {c.issue}\n"
        f"  Best match found: \"{(c.best_match or 'NONE')[:150]}\""
        for c in failed_claims
    )

    prompt = CLAIM_FIX_PROMPT.format(
        source_doc=source_doc,
        claims_text=claims_text,
    )

    system = (
        "You are a meticulous clinical document QA agent. "
        "Your citations must be EXACT verbatim text from the source. "
        "Respond with valid JSON only."
    )

    full_text = ""
    buffer = ""

    yield _sse("llm_stream_start", {"pass": 0, "label": "fix_claims"}), None

    try:
        async for chunk in llm.stream(system=system, user=prompt, max_tokens=4000):
            full_text += chunk
            buffer += chunk
            if len(buffer) >= TOKEN_BATCH_SIZE:
                yield _sse("llm_token", {"text": buffer, "pass": 0, "label": "fix_claims"}), None
                buffer = ""

        if buffer:
            yield _sse("llm_token", {"text": buffer, "pass": 0, "label": "fix_claims"}), None

        yield _sse("llm_stream_end", {"pass": 0, "label": "fix_claims"}), None

        # Parse
        text = full_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]

        fixes = json.loads(text.strip())
        yield None, {f["claim_id"]: f for f in fixes if isinstance(f, dict)}
    except Exception as e:
        logger.error("Streaming fix_claims failed: %s", e)
        yield _sse("llm_stream_end", {"pass": 0, "label": "fix_claims"}), None
        yield None, {}


async def _stream_reconstruct(llm, system_prompt, prompt, label="reconstruct"):
    """Stream a reconstruct LLM call, yielding SSE events + final raw JSON."""
    raw = ""
    async for sse_event, text in _stream_llm(llm, system_prompt, prompt, label):
        if sse_event:
            yield sse_event, None
            await asyncio.sleep(0)
        if text is not None:
            raw = text
    yield None, raw


# ============================================================================
# ASAM Streaming
# ============================================================================

async def stream_qa_agent_asam(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> AsyncGenerator[str, None]:
    """Stream the QA agent's ASAM work with real-time LLM token output."""
    from app.services.asam_engine import ASAMEngine
    from app.prompts.asam_prompt import ASAM_SYSTEM_PROMPT, ASAM_THINKING_PROMPT, ASAM_STRUCTURED_PROMPT

    source_doc = compile_clinical_doc(extraction)
    engine = ASAMEngine(llm)
    clinical_document = engine._compile_clinical_document(extraction)

    yield _sse("agent_start", {
        "message": "QA Agent initialized",
        "detail": "Loaded patient chart, ASAM 4th Edition criteria, and verification tools",
    })
    await asyncio.sleep(0)

    # --- Pass 1: Stream clinical reasoning ---
    yield _sse("thinking", {"message": "Analyzing clinical documentation across all 6 ASAM dimensions..."})
    yield _sse("tool_call", {
        "tool": "llm_call",
        "description": "Pass 1/2 — Deep clinical reasoning across ASAM dimensions",
        "detail": "Reading BPS assessment, progress notes, and applying ASAM 4th Edition criteria",
    })
    await asyncio.sleep(0)

    thinking_prompt = ASAM_THINKING_PROMPT.format(clinical_document=clinical_document)
    reasoning = ""
    async for sse_event, text in _stream_llm(llm, ASAM_SYSTEM_PROMPT, thinking_prompt, "clinical_reasoning", pass_num=1):
        if sse_event:
            yield sse_event
            await asyncio.sleep(0)
        if text is not None:
            reasoning = text

    yield _sse("tool_result", {
        "tool": "llm_call",
        "result": f"Clinical reasoning complete ({len(reasoning)} chars)",
    })

    # --- Pass 2: Stream structured JSON ---
    yield _sse("tool_call", {
        "tool": "llm_call",
        "description": "Pass 2/2 — Formatting as structured JSON",
        "detail": "Converting clinical reasoning into structured ASAM evaluation",
    })
    await asyncio.sleep(0)

    structured_prompt = f"Here is your clinical analysis:\n\n{reasoning}\n\n{ASAM_STRUCTURED_PROMPT}"
    raw_json = ""
    async for sse_event, text in _stream_llm(llm, ASAM_SYSTEM_PROMPT, structured_prompt, "json_output", pass_num=2):
        if sse_event:
            yield sse_event
            await asyncio.sleep(0)
        if text is not None:
            raw_json = text

    # Parse the evaluation
    try:
        evaluation = engine._parse_response(raw_json, extraction.patient.id)
        engine._validate_citations(evaluation)
    except Exception as e:
        logger.error("Failed to parse streamed ASAM response: %s", e)
        yield _sse("tool_result", {"tool": "llm_call", "result": f"Parse error: {e}"})
        return

    yield _sse("tool_result", {
        "tool": "llm_call",
        "result": f"Evaluation complete — Level {evaluation.recommended_level} ({evaluation.recommended_level_name})",
        "detail": f"{len(evaluation.dimensions)} dimensions, {sum(len(d.subdimensions) for d in evaluation.dimensions)} subdimensions",
    })

    yield _sse("initial_result", {"evaluation": evaluation.model_dump()})
    await asyncio.sleep(0)

    # --- QA Agent verification loop ---
    yield _sse("thinking", {"message": "Now verifying every claim against the source chart..."})
    await asyncio.sleep(0)

    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        yield _sse("iteration", {"number": iteration, "phase": "start", "message": f"Verification pass {iteration + 1}"})

        claims = decompose_asam(evaluation)
        citation_claims = [c for c in claims if c.claim_type == "citation"]

        yield _sse("tool_call", {
            "tool": "decompose",
            "description": f"Decomposed into {len(claims)} claims ({len(citation_claims)} citations)",
        })
        await asyncio.sleep(0)

        yield _sse("tool_call", {
            "tool": "verify_citations",
            "description": f"Checking {len(citation_claims)} citations against source",
        })
        await asyncio.sleep(0)

        for claim in claims:
            verify_claim(claim, source_doc)
            if claim.claim_type == "citation" and claim.cited_text:
                snippet = (claim.cited_text or "")[:80]
                if claim.verdict == "verified":
                    yield _sse("claim_verified", {
                        "id": claim.id, "location": claim.location,
                        "snippet": snippet, "score": round(claim.match_score, 2),
                        "source_match": (claim.best_match or "")[:120],
                    })
                else:
                    yield _sse("claim_failed", {
                        "id": claim.id, "location": claim.location,
                        "snippet": snippet, "issue_type": claim.issue_type,
                        "issue": claim.issue, "score": round(claim.match_score, 2),
                    })
                await asyncio.sleep(0)

        verified = [c for c in claims if c.verdict == "verified"]
        pending = [c for c in claims if c.verdict == "pending"]
        unsupported = [c for c in claims if c.verdict == "unsupported"]

        yield _sse("verify_summary", {
            "verified": len(verified), "failed": len(pending),
            "unsupported": len(unsupported), "total": len(claims),
            "accuracy": round(len(verified) / len(claims), 3) if claims else 0,
        })

        if not pending:
            yield _sse("thinking", {"message": "All claims verified. No hallucinations detected."})
            yield _sse("iteration", {"number": iteration, "phase": "complete", "message": "All claims verified"})
            break

        # Describe issues
        hallucinations = [c for c in pending if c.issue_type == "hallucination"]
        weak = [c for c in pending if c.issue_type == "weak_match"]
        parts = []
        if hallucinations: parts.append(f"{len(hallucinations)} hallucinated")
        if weak: parts.append(f"{len(weak)} imprecise")
        yield _sse("thinking", {"message": f"Found {len(pending)} issues ({', '.join(parts)}). Fixing..."})
        await asyncio.sleep(0)

        # --- Fix with streaming ---
        yield _sse("tool_call", {
            "tool": "fix_claims",
            "description": f"Finding correct evidence for {len(pending)} broken claims",
        })

        for c in pending:
            yield _sse("search", {
                "claim_id": c.id, "location": c.location,
                "query": (c.cited_text or "")[:80],
                "description": f"[{c.issue_type}] {c.location}",
            })
            await asyncio.sleep(0)

        fixes = {}
        async for sse_event, result in _stream_fix_claims(llm, source_doc, pending):
            if sse_event:
                yield sse_event
                await asyncio.sleep(0)
            if result is not None:
                fixes = result

        claims = apply_fixes(claims, fixes, source_doc)

        newly_fixed = [c for c in claims if c.verdict == "fixed"]
        still_broken = [c for c in claims if c.verdict == "pending"]
        newly_unsupported = [c for c in claims if c.verdict == "unsupported" and c not in unsupported]

        yield _sse("tool_result", {
            "tool": "fix_claims",
            "result": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, still broken {len(still_broken)}",
        })

        for c in newly_fixed:
            yield _sse("claim_fixed", {
                "id": c.id, "location": c.location,
                "old_text": (c.cited_text or "")[:100],
                "new_text": (c.fixed_text or "")[:100],
                "explanation": c.issue or "",
            })
            await asyncio.sleep(0)

        for c in newly_unsupported:
            yield _sse("claim_unsupported", {
                "id": c.id, "location": c.location,
                "text": (c.cited_text or "")[:100],
                "reason": c.issue or "No supporting evidence",
            })
            await asyncio.sleep(0)

        yield _sse("iteration", {
            "number": iteration, "phase": "complete",
            "message": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, still broken {len(still_broken)}",
        })

        if not newly_fixed and not newly_unsupported:
            yield _sse("thinking", {"message": "No further progress. Finalizing..."})
            break

        if newly_fixed or newly_unsupported:
            yield _sse("tool_call", {"tool": "reconstruct", "description": "Rebuilding evaluation with corrections"})

            # Build corrections list (same as reconstruct_asam)
            corrections = []
            for c in claims:
                if c.verdict == "fixed" and c.fixed_text:
                    corrections.append(f'- [{c.location}]: Replace citation "{(c.cited_text or "")[:80]}..." with "{c.fixed_text[:120]}"')
                elif c.verdict == "unsupported":
                    corrections.append(f"- [{c.location}]: {c.issue}. Adjust the rating/finding to reflect only what IS documented.")

            if corrections:
                original_json = json.dumps(evaluation.model_dump(), indent=2, default=str)
                recon_prompt = (
                    f"Apply these corrections to the ASAM evaluation. Change ONLY what is listed below.\n"
                    f"Keep everything else exactly the same.\n\n"
                    f"<corrections>\n{chr(10).join(corrections)}\n</corrections>\n\n"
                    f"<source_document>\n{source_doc}\n</source_document>\n\n"
                    f"<original_evaluation>\n{original_json}\n</original_evaluation>\n\n"
                    f"Output the corrected evaluation as valid JSON (same schema).\n"
                    f"All citations must be EXACT verbatim quotes from the source document."
                )
                raw_recon = ""
                async for sse_event, text in _stream_reconstruct(llm, ASAM_SYSTEM_PROMPT, recon_prompt):
                    if sse_event:
                        yield sse_event
                        await asyncio.sleep(0)
                    if text is not None:
                        raw_recon = text
                try:
                    evaluation = engine._parse_response(raw_recon, evaluation.patient_id)
                except Exception as e:
                    logger.error("Streamed ASAM reconstruct parse failed: %s", e)

            yield _sse("tool_result", {"tool": "reconstruct", "result": "Evaluation rebuilt"})
            yield _sse("thinking", {"message": "Re-verifying all claims..."})

    # --- Final ---
    yield _sse("tool_call", {"tool": "final_verify", "description": "Final verification pass"})

    final_claims = decompose_asam(evaluation)
    for claim in final_claims:
        verify_claim(claim, source_doc)

    linked = _build_linked_evidence(final_claims, source_doc)

    v = sum(1 for c in final_claims if c.verdict == "verified")
    f = sum(1 for c in claims if c.verdict == "fixed")
    u = sum(1 for c in final_claims if c.verdict == "unsupported")
    fl = sum(1 for c in final_claims if c.verdict == "pending")
    total = len(final_claims)
    accuracy = v / total if total > 0 else 0

    yield _sse("tool_result", {"tool": "final_verify", "result": f"{v}/{total} verified ({accuracy:.0%})"})
    yield _sse("thinking", {"message": f"Done. {v} verified, {f} fixed, {u} unsupported."})

    yield _sse("complete", {
        "evaluation": evaluation.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "claims": {"total": total, "verified": v, "fixed": f, "unsupported": u, "failed": fl},
    })


# ============================================================================
# TJC Streaming
# ============================================================================

async def _run_tjc_section(llm: LLMClient, section: dict, clinical_document: str) -> tuple[str, str]:
    """Run a single TJC section audit. Returns (section_id, raw_json)."""
    from app.prompts.tjc_sections import TJC_SECTION_SYSTEM, build_section_prompt
    prompt = build_section_prompt(section, clinical_document)
    raw = await llm.complete(system=TJC_SECTION_SYSTEM, user=prompt, max_tokens=8192)
    return section["id"], raw


def _parse_section_json(raw: str) -> list[dict]:
    """Parse a section's raw JSON into a list of standard dicts."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()
    data = json.loads(text)
    return data.get("standards", [])


def _get_all_expected_standard_ids() -> set[str]:
    """Return the set of all 39 standard IDs we expect."""
    from app.prompts.tjc_sections import SECTIONS
    import re
    ids = set()
    for section in SECTIONS:
        for match in re.finditer(r'^([A-Z]+\.\d[\d.]+)', section["standards"], re.MULTILINE):
            ids.add(match.group(1))
    return ids


async def stream_qa_agent_tjc(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> AsyncGenerator[str, None]:
    """Stream the QA agent's TJC work — multi-section parallel audit."""
    from app.services.tjc_engine import TJCEngine
    from app.prompts.tjc_prompt import TJC_SYSTEM_PROMPT
    from app.prompts.tjc_sections import SECTIONS, TJC_SECTION_SYSTEM, build_section_prompt

    source_doc = compile_clinical_doc(extraction)
    engine = TJCEngine(llm)
    clinical_document = engine._compile_clinical_document(extraction)

    expected_ids = _get_all_expected_standard_ids()

    yield _sse("agent_start", {
        "message": "TJC Orchestrator initialized",
        "detail": f"Auditing {len(expected_ids)} standards across {len(SECTIONS)} sections",
    })
    await asyncio.sleep(0)

    # --- Phase 1: Parallel section audits ---
    yield _sse("thinking", {"message": f"Dispatching {len(SECTIONS)} parallel audit agents..."})
    await asyncio.sleep(0)

    all_standards = []
    completed_ids = set()

    # Fire all sections in parallel
    tasks = []
    for section in SECTIONS:
        yield _sse("tool_call", {
            "tool": "audit_section",
            "description": f"Agent → {section['name']}",
        })
        await asyncio.sleep(0)
        tasks.append(asyncio.create_task(_run_tjc_section(llm, section, clinical_document)))

    # Collect results as they complete
    for coro in asyncio.as_completed(tasks):
        section_id, raw = await coro
        section_name = next((s["name"] for s in SECTIONS if s["id"] == section_id), section_id)
        try:
            stds = _parse_section_json(raw)
            # Normalize statuses
            for std in stds:
                s = std.get("overall_status", "").lower().strip()
                if s in ("compliant", "pass", "met"):
                    std["overall_status"] = "compliant"
                elif "non" in s or "fail" in s or "not" in s:
                    std["overall_status"] = "non_compliant"
                elif "partial" in s:
                    std["overall_status"] = "partial"

                for finding in std.get("findings", []):
                    fs = finding.get("status", "").lower().strip()
                    if fs in ("pass", "met", "compliant", "yes"):
                        finding["status"] = "pass"
                    elif fs in ("fail", "failed", "unmet", "no") or "non" in fs or "not" in fs:
                        finding["status"] = "fail"
                    elif "partial" in fs:
                        finding["status"] = "partial"

            all_standards.extend(stds)
            for std in stds:
                completed_ids.add(std.get("standard_id", ""))
            n_findings = sum(len(std.get("findings", [])) for std in stds)
            yield _sse("tool_result", {
                "tool": "audit_section",
                "result": f"{section_name}: {len(stds)} standards, {n_findings} findings",
            })
        except Exception as e:
            logger.error("Failed to parse section %s: %s", section_id, e)
            yield _sse("tool_result", {
                "tool": "audit_section",
                "result": f"{section_name}: PARSE ERROR — {e}",
            })
        await asyncio.sleep(0)

    # --- Phase 2: Check coverage and retry missing ---
    missing_ids = expected_ids - completed_ids
    retry_round = 0
    MAX_RETRIES = 2

    while missing_ids and retry_round < MAX_RETRIES:
        retry_round += 1
        yield _sse("thinking", {
            "message": f"Missing {len(missing_ids)} standards: {', '.join(sorted(missing_ids)[:8])}{'...' if len(missing_ids) > 8 else ''}. Spawning retry agent...",
        })
        await asyncio.sleep(0)

        # Build a targeted prompt for just the missing standards
        missing_eps = []
        for section in SECTIONS:
            for line in section["standards"].split("\n"):
                line_stripped = line.strip()
                for mid in missing_ids:
                    if line_stripped.startswith(mid):
                        # Grab this standard and its EPs
                        missing_eps.append(line_stripped)
                        break
                else:
                    # Include EP lines that belong to a missing standard
                    if line_stripped.startswith("EP ") and missing_eps:
                        missing_eps.append("  " + line_stripped)

        if not missing_eps:
            break

        retry_standards_text = "\n".join(missing_eps)
        retry_prompt = f"""\
Audit the following clinical documentation against ONLY these standards.
You MUST produce a finding for EVERY EP listed — do NOT skip any.

STANDARDS TO AUDIT:
{retry_standards_text}

CLINICAL DOCUMENTATION:
{clinical_document}

OUTPUT FORMAT — respond with ONLY valid JSON:
{{"standards": [
  {{"standard_id": "...", "standard_name": "...", "overall_status": "compliant"|"non_compliant"|"partial",
    "findings": [{{"element": "... EP N", "description": "...", "status": "pass"|"fail"|"partial",
      "finding": "...", "citations": [{{"source": "...", "text": "exact quote", "relevance": "..."}}],
      "remediation": "..." or null}}],
    "compliance_percentage": 75.0}}
]}}"""

        yield _sse("tool_call", {"tool": "retry_missing", "description": f"Retry agent for {len(missing_ids)} missing standards"})
        await asyncio.sleep(0)

        try:
            raw_retry = await llm.complete(system=TJC_SECTION_SYSTEM, user=retry_prompt, max_tokens=6000)
            retry_stds = _parse_section_json(raw_retry)

            for std in retry_stds:
                s = std.get("overall_status", "").lower().strip()
                if s in ("compliant", "pass", "met"):
                    std["overall_status"] = "compliant"
                elif "non" in s or "fail" in s or "not" in s:
                    std["overall_status"] = "non_compliant"
                elif "partial" in s:
                    std["overall_status"] = "partial"
                for finding in std.get("findings", []):
                    fs = finding.get("status", "").lower().strip()
                    if fs in ("pass", "met", "compliant", "yes"):
                        finding["status"] = "pass"
                    elif fs in ("fail", "failed", "unmet", "no") or "non" in fs or "not" in fs:
                        finding["status"] = "fail"
                    elif "partial" in fs:
                        finding["status"] = "partial"

            all_standards.extend(retry_stds)
            for std in retry_stds:
                completed_ids.add(std.get("standard_id", ""))
            n_found = len(retry_stds)
            yield _sse("tool_result", {
                "tool": "retry_missing",
                "result": f"Recovered {n_found} standards",
            })
        except Exception as e:
            logger.error("Retry failed: %s", e)
            yield _sse("tool_result", {"tool": "retry_missing", "result": f"Retry failed: {e}"})

        missing_ids = expected_ids - completed_ids
        await asyncio.sleep(0)

    # --- Phase 3: Assemble final audit ---
    yield _sse("thinking", {
        "message": f"Assembling audit: {len(all_standards)} standards from {len(completed_ids)} unique IDs ({len(completed_ids)}/{len(expected_ids)} coverage)",
    })
    await asyncio.sleep(0)

    # Deduplicate by standard_id (keep first occurrence)
    seen = set()
    deduped = []
    for std in all_standards:
        sid = std.get("standard_id", "")
        if sid not in seen:
            seen.add(sid)
            deduped.append(std)

    # Calculate overall compliance
    total_findings = sum(len(s.get("findings", [])) for s in deduped)
    pass_findings = sum(
        sum(1 for f in s.get("findings", []) if f.get("status") == "pass")
        for s in deduped
    )
    overall_pct = (pass_findings / total_findings * 100) if total_findings > 0 else 0

    # Build critical gaps
    critical_gaps = []
    recommendations = []
    for std in deduped:
        for f in std.get("findings", []):
            if f.get("status") == "fail" and f.get("remediation"):
                critical_gaps.append({
                    "standard": std.get("standard_id", ""),
                    "element": f.get("element", ""),
                    "severity": "major",
                    "description": f.get("finding", "")[:200],
                    "impact": "Accreditation risk",
                })
                if f["remediation"] not in recommendations:
                    recommendations.append(f["remediation"])

    audit_data = {
        "patient_id": extraction.patient.id,
        "audited_at": json.dumps(None),
        "standards": deduped,
        "overall_compliance_percentage": round(overall_pct, 1),
        "critical_gaps": critical_gaps[:20],
        "recommendations": recommendations[:15],
        "audit_summary": f"Audit of {len(deduped)} standards ({total_findings} EPs). "
                         f"Overall compliance: {overall_pct:.1f}%. "
                         f"Coverage: {len(completed_ids)}/{len(expected_ids)} standards.",
    }

    try:
        audit = engine._parse_response(json.dumps(audit_data), extraction.patient.id)
    except Exception as e:
        logger.error("Failed to assemble TJC audit: %s", e)
        yield _sse("tool_result", {"tool": "assemble", "result": f"Assembly error: {e}"})
        return

    pct = audit.overall_compliance_percentage
    yield _sse("tool_result", {
        "tool": "assemble",
        "result": f"Audit complete — {pct:.1f}% compliance, {len(deduped)} standards, {total_findings} findings",
    })

    yield _sse("initial_result", {"audit": audit.model_dump()})
    await asyncio.sleep(0)

    # --- Phase 4: QA verification loop (same as before) ---
    yield _sse("thinking", {"message": "Verifying every citation against the source chart..."})
    await asyncio.sleep(0)

    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        yield _sse("iteration", {"number": iteration, "phase": "start", "message": f"Verification pass {iteration + 1}"})

        claims = decompose_tjc(audit)
        citation_claims = [c for c in claims if c.claim_type == "citation"]

        yield _sse("tool_call", {"tool": "decompose", "description": f"Decomposed into {len(claims)} claims ({len(citation_claims)} citations)"})
        yield _sse("tool_call", {"tool": "verify_citations", "description": f"Checking {len(citation_claims)} citations"})
        await asyncio.sleep(0)

        for claim in claims:
            if claim.verdict != "unsupported":
                verify_claim(claim, source_doc)
            if claim.claim_type == "citation" and claim.cited_text:
                snippet = (claim.cited_text or "")[:80]
                if claim.verdict == "verified":
                    yield _sse("claim_verified", {
                        "id": claim.id, "location": claim.location,
                        "snippet": snippet, "score": round(claim.match_score, 2),
                    })
                elif claim.verdict == "pending":
                    yield _sse("claim_failed", {
                        "id": claim.id, "location": claim.location,
                        "snippet": snippet, "issue_type": claim.issue_type,
                        "issue": claim.issue, "score": round(claim.match_score, 2),
                    })
                await asyncio.sleep(0)

        verified = [c for c in claims if c.verdict == "verified"]
        pending = [c for c in claims if c.verdict == "pending"]
        unsupported = [c for c in claims if c.verdict == "unsupported"]

        yield _sse("verify_summary", {
            "verified": len(verified), "failed": len(pending),
            "unsupported": len(unsupported), "total": len(claims),
            "accuracy": round(len(verified) / len(claims), 3) if claims else 0,
        })

        if not pending:
            yield _sse("thinking", {"message": "All claims verified."})
            yield _sse("iteration", {"number": iteration, "phase": "complete", "message": "All claims verified"})
            break

        yield _sse("thinking", {"message": f"Found {len(pending)} issues. Fixing..."})

        yield _sse("tool_call", {"tool": "fix_claims", "description": f"Finding evidence for {len(pending)} broken claims"})
        for c in pending:
            yield _sse("search", {
                "claim_id": c.id, "location": c.location,
                "query": (c.cited_text or "")[:80],
                "description": f"[{c.issue_type}] {c.location}",
            })
            await asyncio.sleep(0)

        fixes = {}
        async for sse_event, result in _stream_fix_claims(llm, source_doc, pending):
            if sse_event:
                yield sse_event
                await asyncio.sleep(0)
            if result is not None:
                fixes = result

        claims = apply_fixes(claims, fixes, source_doc)

        newly_fixed = [c for c in claims if c.verdict == "fixed"]
        still_broken = [c for c in claims if c.verdict == "pending"]
        newly_unsupported = [c for c in claims if c.verdict == "unsupported" and c not in unsupported]

        yield _sse("tool_result", {
            "tool": "fix_claims",
            "result": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, broken {len(still_broken)}",
        })

        for c in newly_fixed:
            yield _sse("claim_fixed", {
                "id": c.id, "location": c.location,
                "old_text": (c.cited_text or "")[:100],
                "new_text": (c.fixed_text or "")[:100],
            })
            await asyncio.sleep(0)

        yield _sse("iteration", {
            "number": iteration, "phase": "complete",
            "message": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, broken {len(still_broken)}",
        })

        if not newly_fixed and not newly_unsupported:
            break

        if newly_fixed or newly_unsupported:
            yield _sse("tool_call", {"tool": "reconstruct", "description": "Rebuilding audit with corrections"})

            corrections = []
            for c in claims:
                if c.verdict == "fixed" and c.fixed_text:
                    corrections.append(f'- [{c.location}]: Replace citation "{(c.cited_text or "")[:80]}..." with "{c.fixed_text[:120]}"')
                elif c.verdict == "unsupported":
                    corrections.append(f"- [{c.location}]: {c.issue}. If status was 'pass', change to 'fail' since evidence is missing.")

            if corrections:
                original_json = json.dumps(audit.model_dump(), indent=2, default=str)
                recon_prompt = (
                    f"Apply these corrections to the TJC audit. Change ONLY what is listed below.\n"
                    f"Keep everything else exactly the same.\n\n"
                    f"<corrections>\n{chr(10).join(corrections)}\n</corrections>\n\n"
                    f"<source_document>\n{source_doc}\n</source_document>\n\n"
                    f"<original_audit>\n{original_json}\n</original_audit>\n\n"
                    f"Output the corrected audit as valid JSON (same schema).\n"
                    f"All citations must be EXACT verbatim quotes from the source document.\n"
                    f"Recalculate compliance percentages after corrections."
                )
                raw_recon = ""
                async for sse_event, text in _stream_reconstruct(llm, TJC_SYSTEM_PROMPT, recon_prompt):
                    if sse_event:
                        yield sse_event
                        await asyncio.sleep(0)
                    if text is not None:
                        raw_recon = text
                try:
                    audit = engine._parse_response(raw_recon, audit.patient_id)
                except Exception as e:
                    logger.error("Streamed TJC reconstruct parse failed: %s", e)

            yield _sse("tool_result", {"tool": "reconstruct", "result": "Audit rebuilt"})

    # --- Final ---
    yield _sse("tool_call", {"tool": "final_verify", "description": "Final verification pass"})

    final_claims = decompose_tjc(audit)
    for claim in final_claims:
        if claim.verdict != "unsupported":
            verify_claim(claim, source_doc)

    linked = _build_linked_evidence(final_claims, source_doc)

    v = sum(1 for c in final_claims if c.verdict == "verified")
    f = sum(1 for c in claims if c.verdict == "fixed")
    u = sum(1 for c in final_claims if c.verdict == "unsupported")
    fl = sum(1 for c in final_claims if c.verdict == "pending")
    total = len(final_claims)
    accuracy = v / total if total > 0 else 0

    yield _sse("tool_result", {"tool": "final_verify", "result": f"{v}/{total} verified ({accuracy:.0%})"})
    yield _sse("thinking", {"message": f"Done. {v} verified, {f} fixed, {u} unsupported."})

    yield _sse("complete", {
        "audit": audit.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "claims": {"total": total, "verified": v, "fixed": f, "unsupported": u, "failed": fl},
    })
