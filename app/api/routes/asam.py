from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_llm_client
from app.api.routes.extraction import get_patient_data
from app.db.database import get_db
from app.db.models import ASAMEvaluation as ASAMEvaluationModel
from app.schemas.asam import ASAMEvaluation
from app.services.asam_engine import ASAMEngine
from app.services.llm_client import LLMClient

router = APIRouter()


@router.post("/patients/{patient_id}/asam-evaluation", response_model=ASAMEvaluation)
async def evaluate_asam(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Evaluate a patient across all 6 ASAM dimensions (4th Edition)
    and recommend a level of care."""

    extraction = await get_patient_data(patient_id, db)

    engine = ASAMEngine(llm)
    evaluation = await engine.evaluate(extraction)

    db_eval = ASAMEvaluationModel(
        patient_id=patient_id,
        dimension_scores_json=[d.model_dump() for d in evaluation.dimensions],
        recommended_level=evaluation.recommended_level,
        level_rationale=evaluation.level_rationale,
        raw_llm_response=llm.last_raw_response,
    )
    db.add(db_eval)
    await db.commit()

    return evaluation
