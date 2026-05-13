from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_llm_client
from app.api.routes.extraction import get_patient_data
from app.db.database import get_db
from app.db.models import TJCAudit as TJCAuditModel
from app.schemas.tjc import TJCAuditResult
from app.services.llm_client import LLMClient
from app.services.tjc_engine import TJCEngine

router = APIRouter()


@router.post("/patients/{patient_id}/tjc-audit", response_model=TJCAuditResult)
async def audit_tjc(
    patient_id: str,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Audit a patient's documentation against Joint Commission CTS standards
    for behavioral health treatment."""

    extraction = await get_patient_data(patient_id, db)

    engine = TJCEngine(llm)
    result = await engine.audit(extraction)

    db_audit = TJCAuditModel(
        patient_id=patient_id,
        standards_json=[s.model_dump() for s in result.standards],
        overall_compliance_pct=result.overall_compliance_percentage,
        critical_gaps=[g.model_dump() for g in result.critical_gaps],
        raw_llm_response=llm.last_raw_response,
    )
    db.add(db_audit)
    await db.commit()

    return result
