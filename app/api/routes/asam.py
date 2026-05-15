import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_llm_client
from app.api.routes.extraction import get_patient_data
from app.db.database import get_db
from app.db.models import ASAMEvaluation as ASAMEvaluationModel
from app.schemas.asam import ASAMEvaluation
from app.services.llm_client import LLMClient
from app.services.qa_loop import run_qa_agent_asam
from app.services.qa_stream import stream_qa_agent_asam

logger = logging.getLogger(__name__)

router = APIRouter()


async def _save_asam(db: AsyncSession, patient_id: str, result: dict, raw_response: str):
    """Persist ASAM evaluation + QA results to database."""
    evaluation = ASAMEvaluation.model_validate(result["evaluation"])
    db_eval = ASAMEvaluationModel(
        patient_id=patient_id,
        dimension_scores_json=[d.model_dump() for d in evaluation.dimensions],
        recommended_level=evaluation.recommended_level,
        level_rationale=evaluation.level_rationale,
        full_evaluation_json=result["evaluation"],
        linked_evidence_json=result["linked_evidence"],
        qa_accuracy=result["accuracy"],
        qa_claims_json=result["claims"],
        qa_iterations=result["iterations"],
        source_document=result["source_document"],
        raw_llm_response=raw_response,
    )
    db.add(db_eval)
    await db.commit()
    logger.info("Saved ASAM evaluation for patient %s (accuracy=%.1f%%)", patient_id, result["accuracy"] * 100)


@router.post("/patients/{patient_id}/asam-evaluation")
async def evaluate_asam(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Evaluate patient across ASAM dimensions with agentic QA loop."""
    extraction = await get_patient_data(patient_id, db)
    result = await run_qa_agent_asam(llm, extraction)

    await _save_asam(db, patient_id, result, llm.last_raw_response)

    return {
        **result["evaluation"],
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


@router.post("/patients/{patient_id}/asam-evaluation/stream")
async def evaluate_asam_stream(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Stream ASAM evaluation with live QA agent events (SSE).
    Saves to database when complete."""
    extraction = await get_patient_data(patient_id, db)

    async def stream_and_save():
        final_data = None
        async for event in stream_qa_agent_asam(llm, extraction):
            yield event
            # Capture the complete event data for persistence
            if event.startswith("event: complete\n"):
                data_line = event.split("data: ", 1)[1].split("\n")[0]
                final_data = json.loads(data_line)

        # Save after stream finishes
        if final_data:
            await _save_asam(db, patient_id, {
                "evaluation": final_data["evaluation"],
                "source_document": final_data["source_document"],
                "linked_evidence": final_data["linked_evidence"],
                "accuracy": final_data["accuracy"],
                "claims": final_data["claims"],
                "iterations": 0,  # not tracked in stream
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


@router.post("/patients/{patient_id}/asam-report")
async def generate_asam_report_endpoint(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF report from the most recent saved ASAM evaluation."""
    from app.services.report_generator import generate_asam_report

    # Load most recent evaluation from DB
    result = await db.execute(
        select(ASAMEvaluationModel)
        .where(ASAMEvaluationModel.patient_id == patient_id)
        .order_by(ASAMEvaluationModel.evaluated_at.desc())
        .limit(1)
    )
    saved = result.scalar_one_or_none()
    if not saved or not saved.full_evaluation_json:
        raise HTTPException(status_code=404, detail="No ASAM evaluation found. Run an evaluation first.")

    extraction = await get_patient_data(patient_id, db)
    patient_dict = json.loads(extraction.model_dump_json())
    asam_dict = saved.full_evaluation_json
    asam_dict["qa_validation"] = {
        "accuracy": saved.qa_accuracy or 0,
        "citation_issues": [],
        "loc_consistency_issues": [],
        "llm_validation": {
            "overall_quality": "good" if (saved.qa_accuracy or 0) >= 0.8 else "acceptable",
            "issues_summary": "",
        },
    }

    pdf_bytes = generate_asam_report(patient_dict, asam_dict)

    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="asam_report_{patient_id}.pdf"',
        },
    )


@router.get("/patients/{patient_id}/asam-history")
async def list_asam_history(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
):
    """List all past ASAM evaluations for a patient."""
    result = await db.execute(
        select(ASAMEvaluationModel)
        .where(ASAMEvaluationModel.patient_id == patient_id)
        .order_by(ASAMEvaluationModel.evaluated_at.desc())
    )
    evals = result.scalars().all()
    return [
        {
            "id": e.id,
            "evaluated_at": str(e.evaluated_at),
            "recommended_level": e.recommended_level,
            "qa_accuracy": e.qa_accuracy,
            "qa_iterations": e.qa_iterations,
        }
        for e in evals
    ]


@router.get("/patients/{patient_id}/asam-history/{eval_id}")
async def get_asam_evaluation(
    patient_id: str,
    eval_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Load a specific past ASAM evaluation."""
    result = await db.execute(
        select(ASAMEvaluationModel)
        .where(ASAMEvaluationModel.id == eval_id)
        .where(ASAMEvaluationModel.patient_id == patient_id)
    )
    e = result.scalar_one_or_none()
    if not e:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    return {
        **(e.full_evaluation_json or {}),
        "source_document": e.source_document,
        "linked_evidence": e.linked_evidence_json,
        "qa_agent": {
            "accuracy": e.qa_accuracy,
            "claims": e.qa_claims_json,
            "iterations": e.qa_iterations,
            "trace": [],
            "unresolved_claims": [],
        },
    }
