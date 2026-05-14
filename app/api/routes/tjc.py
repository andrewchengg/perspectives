import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_llm_client
from app.api.routes.extraction import get_patient_data
from app.db.database import get_db
from app.db.models import TJCAudit as TJCAuditModel
from app.schemas.tjc import TJCAuditResult
from app.services.llm_client import LLMClient
from app.services.qa_loop import run_qa_agent_tjc
from app.services.qa_stream import stream_qa_agent_tjc

logger = logging.getLogger(__name__)

router = APIRouter()


async def _save_tjc(db: AsyncSession, patient_id: str, result: dict, raw_response: str):
    """Persist TJC audit + QA results to database."""
    audit = TJCAuditResult.model_validate(result["audit"])
    db_audit = TJCAuditModel(
        patient_id=patient_id,
        standards_json=[s.model_dump() for s in audit.standards],
        overall_compliance_pct=audit.overall_compliance_percentage,
        critical_gaps=[g.model_dump() for g in audit.critical_gaps],
        full_audit_json=result["audit"],
        linked_evidence_json=result["linked_evidence"],
        qa_accuracy=result["accuracy"],
        qa_claims_json=result["claims"],
        qa_iterations=result["iterations"],
        source_document=result["source_document"],
        raw_llm_response=raw_response,
    )
    db.add(db_audit)
    await db.commit()
    logger.info("Saved TJC audit for patient %s (accuracy=%.1f%%)", patient_id, result["accuracy"] * 100)


@router.post("/patients/{patient_id}/tjc-audit")
async def audit_tjc(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Audit patient docs against TJC CTS standards with agentic QA loop."""
    extraction = await get_patient_data(patient_id, db)
    result = await run_qa_agent_tjc(llm, extraction)

    await _save_tjc(db, patient_id, result, llm.last_raw_response)

    return {
        **result["audit"],
        "source_document": result["source_document"],
        "linked_evidence": result["linked_evidence"],
        "qa_agent": {
            "accuracy": result["accuracy"],
            "iterations": result["iterations"],
            "claims": result["claims"],
            "trace": result["trace"],
            "unresolved_claims": result["final_claims"],
        },
    }


@router.post("/patients/{patient_id}/tjc-audit/stream")
async def audit_tjc_stream(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Stream TJC audit with live QA agent events (SSE).
    Saves to database when complete."""
    extraction = await get_patient_data(patient_id, db)

    async def stream_and_save():
        final_data = None
        async for event in stream_qa_agent_tjc(llm, extraction):
            yield event
            if event.startswith("event: complete\n"):
                data_line = event.split("data: ", 1)[1].split("\n")[0]
                final_data = json.loads(data_line)

        if final_data:
            await _save_tjc(db, patient_id, {
                "audit": final_data["audit"],
                "source_document": final_data["source_document"],
                "linked_evidence": final_data["linked_evidence"],
                "accuracy": final_data["accuracy"],
                "claims": final_data["claims"],
                "iterations": 0,
                "trace": [],
                "final_claims": [],
            }, llm.last_raw_response)

    return StreamingResponse(
        stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
