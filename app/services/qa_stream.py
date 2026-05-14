"""
Streaming QA Agent — SSE event stream showing the agent working live.

Like Claude Code: you see each tool call, each search through the source
document, each verification, each fix as it happens in real-time.
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
    _build_linked_evidence,
    apply_fixes,
    decompose_asam,
    decompose_tjc,
    fix_claims,
    reconstruct_asam,
    reconstruct_tjc,
    verify_claim,
    MAX_FIX_ITERATIONS,
)

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def stream_qa_agent_asam(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> AsyncGenerator[str, None]:
    """Stream the QA agent's ASAM work as SSE events."""
    from app.services.asam_engine import ASAMEngine

    source_doc = compile_clinical_doc(extraction)
    engine = ASAMEngine(llm)

    yield _sse("agent_start", {
        "message": "QA Agent initialized",
        "detail": "Loaded patient chart, ASAM 4th Edition criteria, and verification tools",
    })
    await asyncio.sleep(0)

    # --- Generate: Pass 1 (thinking) ---
    yield _sse("thinking", {"message": "Analyzing clinical documentation across all 6 ASAM dimensions..."})
    yield _sse("tool_call", {
        "tool": "llm_call",
        "description": "Pass 1/2 — Deep clinical reasoning across ASAM dimensions",
        "detail": "Reading BPS assessment, progress notes, and applying ASAM 4th Edition criteria",
    })
    await asyncio.sleep(0)

    evaluation = await engine.evaluate(extraction)

    yield _sse("tool_result", {
        "tool": "llm_call",
        "result": f"Evaluation complete — recommending Level {evaluation.recommended_level} ({evaluation.recommended_level_name})",
        "detail": f"Evaluated {len(evaluation.dimensions)} dimensions, {sum(len(d.subdimensions) for d in evaluation.dimensions)} subdimensions",
    })

    yield _sse("initial_result", {"evaluation": evaluation.model_dump()})
    await asyncio.sleep(0)

    # --- QA Agent begins ---
    yield _sse("thinking", {"message": "Now I need to verify every claim in this evaluation is grounded in the source chart..."})
    await asyncio.sleep(0)

    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        yield _sse("iteration", {
            "number": iteration,
            "phase": "start",
            "message": f"Verification pass {iteration + 1}",
        })

        # --- Decompose ---
        claims = decompose_asam(evaluation)
        citation_claims = [c for c in claims if c.claim_type == "citation"]
        rating_claims = [c for c in claims if c.claim_type == "rating"]

        yield _sse("tool_call", {
            "tool": "decompose",
            "description": f"Decomposed evaluation into {len(claims)} atomic claims",
            "detail": f"{len(citation_claims)} citations to verify, {len(rating_claims)} ratings to check",
        })
        await asyncio.sleep(0)

        # --- Verify each claim with granular streaming ---
        yield _sse("tool_call", {
            "tool": "verify_citations",
            "description": f"Checking {len(citation_claims)} citations against source document",
            "detail": "Using RapidFuzz 3-tier matching: exact substring → fuzzy → token overlap",
        })
        await asyncio.sleep(0)

        verified_count = 0
        failed_count = 0

        for claim in claims:
            verify_claim(claim, source_doc)

            if claim.claim_type == "citation" and claim.cited_text:
                snippet = (claim.cited_text or "")[:80]

                if claim.verdict == "verified":
                    verified_count += 1
                    yield _sse("claim_verified", {
                        "id": claim.id,
                        "location": claim.location,
                        "snippet": snippet,
                        "score": round(claim.match_score, 2),
                        "source_match": (claim.best_match or "")[:120],
                        "method": "exact" if claim.match_score == 1.0 else "fuzzy",
                        "progress": f"{verified_count + failed_count}/{len(citation_claims)}",
                    })
                else:
                    failed_count += 1
                    yield _sse("claim_failed", {
                        "id": claim.id,
                        "location": claim.location,
                        "snippet": snippet,
                        "issue_type": claim.issue_type,
                        "issue": claim.issue,
                        "score": round(claim.match_score, 2),
                        "progress": f"{verified_count + failed_count}/{len(citation_claims)}",
                    })
                await asyncio.sleep(0)

        verified = [c for c in claims if c.verdict == "verified"]
        pending = [c for c in claims if c.verdict == "pending"]
        unsupported = [c for c in claims if c.verdict == "unsupported"]

        yield _sse("verify_summary", {
            "verified": len(verified),
            "failed": len(pending),
            "unsupported": len(unsupported),
            "total": len(claims),
            "accuracy": round(len(verified) / len(claims), 3) if claims else 0,
        })

        # --- All good? ---
        if not pending:
            yield _sse("thinking", {"message": "All claims verified against source document. No hallucinations detected."})
            yield _sse("iteration", {"number": iteration, "phase": "complete", "message": "All claims verified — no fixes needed"})
            break

        # --- Agent thinks about what to fix ---
        hallucinations = [c for c in pending if c.issue_type == "hallucination"]
        negation_flips = [c for c in pending if c.issue_type == "negation_flip"]
        weak_matches = [c for c in pending if c.issue_type == "weak_match"]

        issues_summary = []
        if hallucinations:
            issues_summary.append(f"{len(hallucinations)} hallucinated citations")
        if negation_flips:
            issues_summary.append(f"{len(negation_flips)} negation flips")
        if weak_matches:
            issues_summary.append(f"{len(weak_matches)} imprecise quotes")

        yield _sse("thinking", {
            "message": f"Found {len(pending)} issues: {', '.join(issues_summary)}. Searching source document for correct evidence...",
        })
        await asyncio.sleep(0)

        # --- Fix: show each search ---
        yield _sse("tool_call", {
            "tool": "fix_claims",
            "description": f"Asking LLM to find correct evidence for {len(pending)} broken claims",
            "detail": "The fixer searches the source document and returns exact verbatim quotes",
        })

        for c in pending:
            search_desc = f"[{c.issue_type}] {c.location}"
            if c.issue_type == "hallucination":
                search_desc += f" — LLM cited \"{(c.cited_text or '')[:50]}\" but this doesn't exist in the chart"
            elif c.issue_type == "negation_flip":
                search_desc += f" — source says the opposite of what was cited"
            elif c.issue_type == "weak_match":
                search_desc += f" — citation is close ({c.match_score:.0%}) but not verbatim"

            yield _sse("search", {
                "claim_id": c.id,
                "location": c.location,
                "query": (c.cited_text or "")[:80],
                "description": search_desc,
            })
            await asyncio.sleep(0)

        fixes = await fix_claims(llm, source_doc, pending)
        claims = apply_fixes(claims, fixes, source_doc)

        newly_fixed = [c for c in claims if c.verdict == "fixed"]
        still_broken = [c for c in claims if c.verdict == "pending"]
        newly_unsupported = [c for c in claims if c.verdict == "unsupported" and c not in unsupported]

        yield _sse("tool_result", {
            "tool": "fix_claims",
            "result": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, still broken {len(still_broken)}",
        })

        # Show each fix with before/after
        for c in newly_fixed:
            yield _sse("claim_fixed", {
                "id": c.id,
                "location": c.location,
                "old_text": (c.cited_text or "")[:100],
                "new_text": (c.fixed_text or "")[:100],
                "explanation": (c.issue or ""),
            })
            await asyncio.sleep(0)

        for c in newly_unsupported:
            yield _sse("claim_unsupported", {
                "id": c.id,
                "location": c.location,
                "text": (c.cited_text or "")[:100],
                "reason": c.issue or "No supporting evidence in source document",
            })
            await asyncio.sleep(0)

        yield _sse("iteration", {
            "number": iteration,
            "phase": "complete",
            "message": f"Fixed {len(newly_fixed)}, unsupported {len(newly_unsupported)}, still broken {len(still_broken)}",
        })

        if not newly_fixed and not newly_unsupported:
            yield _sse("thinking", {"message": "No further progress possible. Finalizing..."})
            break

        if newly_fixed or newly_unsupported:
            yield _sse("tool_call", {
                "tool": "reconstruct",
                "description": f"Rebuilding evaluation with {len(newly_fixed) + len(newly_unsupported)} corrections",
                "detail": "LLM applies targeted fixes while preserving all verified claims",
            })
            evaluation = await reconstruct_asam(llm, source_doc, evaluation, claims)
            yield _sse("tool_result", {"tool": "reconstruct", "result": "Evaluation rebuilt with corrections"})
            yield _sse("thinking", {"message": "Re-verifying all claims after reconstruction..."})
            await asyncio.sleep(0)

    # --- Final verification ---
    yield _sse("tool_call", {
        "tool": "final_verify",
        "description": "Final verification pass — checking every claim one last time",
    })

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

    yield _sse("tool_result", {
        "tool": "final_verify",
        "result": f"{v}/{total} claims verified ({accuracy:.0%} accuracy)",
    })

    yield _sse("thinking", {
        "message": f"Done. {v} claims verified, {f} fixed, {u} unsupported, {fl} unresolved. Accuracy: {accuracy:.1%}",
    })

    yield _sse("complete", {
        "evaluation": evaluation.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "claims": {"total": total, "verified": v, "fixed": f, "unsupported": u, "failed": fl},
    })


async def stream_qa_agent_tjc(
    llm: LLMClient,
    extraction: PatientExtraction,
) -> AsyncGenerator[str, None]:
    """Stream the QA agent's TJC work as SSE events."""
    from app.services.tjc_engine import TJCEngine

    source_doc = compile_clinical_doc(extraction)
    engine = TJCEngine(llm)

    yield _sse("agent_start", {
        "message": "QA Agent initialized",
        "detail": "Loaded patient chart, TJC CTS standards (CTS.01–CTS.05), and verification tools",
    })
    await asyncio.sleep(0)

    yield _sse("thinking", {"message": "Auditing clinical documentation against Joint Commission CTS standards..."})
    yield _sse("tool_call", {
        "tool": "llm_call",
        "description": "Pass 1/2 — Analyzing compliance across CTS.01–CTS.05 standards",
        "detail": "Checking screening, assessment, treatment planning, provision, and coordination",
    })
    await asyncio.sleep(0)

    audit = await engine.audit(extraction)
    pct = audit.overall_compliance_percentage
    fail_count = sum(1 for s in audit.standards for f in s.findings if f.status == "fail")

    yield _sse("tool_result", {
        "tool": "llm_call",
        "result": f"Audit complete — {pct:.1f}% compliance, {fail_count} failed elements, {len(audit.critical_gaps)} critical gaps",
    })

    yield _sse("initial_result", {"audit": audit.model_dump()})
    await asyncio.sleep(0)

    yield _sse("thinking", {"message": "Now verifying every citation and finding against the source chart..."})
    await asyncio.sleep(0)

    claims: list[Claim] = []

    for iteration in range(MAX_FIX_ITERATIONS):
        yield _sse("iteration", {"number": iteration, "phase": "start", "message": f"Verification pass {iteration + 1}"})

        claims = decompose_tjc(audit)
        citation_claims = [c for c in claims if c.claim_type == "citation"]
        status_claims = [c for c in claims if c.claim_type == "status"]

        yield _sse("tool_call", {
            "tool": "decompose",
            "description": f"Decomposed audit into {len(claims)} atomic claims",
            "detail": f"{len(citation_claims)} citations, {len(status_claims)} status verdicts",
        })
        await asyncio.sleep(0)

        yield _sse("tool_call", {
            "tool": "verify_citations",
            "description": f"Checking {len(citation_claims)} citations against source document",
            "detail": "RapidFuzz 3-tier: exact → fuzzy → token overlap",
        })
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
                        "source_match": (claim.best_match or "")[:120],
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
            yield _sse("thinking", {"message": "All claims verified. Every finding is grounded in the source chart."})
            yield _sse("iteration", {"number": iteration, "phase": "complete", "message": "All claims verified"})
            break

        hallucinations = [c for c in pending if c.issue_type == "hallucination"]
        weak_matches = [c for c in pending if c.issue_type == "weak_match"]
        issues_parts = []
        if hallucinations: issues_parts.append(f"{len(hallucinations)} hallucinated")
        if weak_matches: issues_parts.append(f"{len(weak_matches)} imprecise")
        yield _sse("thinking", {"message": f"Found {len(pending)} issues ({', '.join(issues_parts)}). Searching for correct evidence..."})
        await asyncio.sleep(0)

        yield _sse("tool_call", {
            "tool": "fix_claims",
            "description": f"Finding correct evidence for {len(pending)} broken claims",
        })

        for c in pending:
            yield _sse("search", {
                "claim_id": c.id, "location": c.location,
                "query": (c.cited_text or "")[:80],
                "description": f"[{c.issue_type}] {c.location} — searching source for correct text",
            })
            await asyncio.sleep(0)

        fixes = await fix_claims(llm, source_doc, pending)
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
            yield _sse("tool_call", {
                "tool": "reconstruct",
                "description": f"Rebuilding audit with {len(newly_fixed) + len(newly_unsupported)} corrections",
            })
            audit = await reconstruct_tjc(llm, source_doc, audit, claims)
            yield _sse("tool_result", {"tool": "reconstruct", "result": "Audit rebuilt with corrections"})
            yield _sse("thinking", {"message": "Re-verifying all claims..."})

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
    yield _sse("thinking", {"message": f"Done. {v} verified, {f} fixed, {u} unsupported, {fl} unresolved."})

    yield _sse("complete", {
        "audit": audit.model_dump(),
        "source_document": source_doc,
        "linked_evidence": linked,
        "accuracy": round(accuracy, 3),
        "claims": {"total": total, "verified": v, "fixed": f, "unsupported": u, "failed": fl},
    })
