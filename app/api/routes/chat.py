"""
Interactive QA Chat — Ask questions about the patient's documents,
challenge findings, request changes to the evaluation/audit.
"""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_llm_client
from app.api.routes.extraction import get_patient_data
from app.db.database import get_db
from app.services.llm_client import LLMClient
from app.services.qa_agent import compile_clinical_doc

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    context_type: str = "general"  # "general", "asam", "tjc"
    evaluation_json: dict | None = None
    history: list[dict] = []  # [{"role": "user"|"assistant", "content": "..."}]


CHAT_SYSTEM = """\
You are a clinical intelligence assistant for Perspectives Health. You have access to \
a patient's full clinical documentation and the AI-generated evaluation/audit.

Your capabilities:
1. ANSWER QUESTIONS about the patient's clinical documents (cite specific text)
2. EXPLAIN why a particular finding, rating, or compliance status was assigned
3. CHALLENGE findings — if the user disagrees, re-examine the evidence
4. SUGGEST EDITS — propose specific changes with justification:

   SUGGESTED EDIT:
     Location: [where]
     Current: [what it says now]
     Proposed: [what it should say]
     Rationale: [why, citing source text]

5. FIND EVIDENCE — search the source documents for specific clinical information

Always quote EXACT text from the source document when citing evidence. Be concise."""


@router.post("/patients/{patient_id}/chat")
async def chat(
    patient_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    """Stream an interactive chat response about the patient's documents."""
    extraction = await get_patient_data(patient_id, db)
    source_doc = compile_clinical_doc(extraction)

    # Build messages array
    messages = []

    # First message always has the full context
    context = f"<source_document>\n{source_doc}\n</source_document>"
    if request.evaluation_json:
        context += (
            f"\n\n<current_{request.context_type}>\n"
            f"{json.dumps(request.evaluation_json, indent=2, default=str)[:8000]}\n"
            f"</current_{request.context_type}>"
        )

    # If there's history, inject context as first exchange
    if request.history:
        messages.append({"role": "user", "content": context})
        messages.append({"role": "assistant", "content": "I have the patient's clinical documentation loaded. What would you like to know?"})
        for msg in request.history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": request.message})
    else:
        messages.append({"role": "user", "content": f"{context}\n\n{request.message}"})

    async def generate():
        async with llm._client.messages.stream(
            model=llm._model,
            max_tokens=2000,
            system=CHAT_SYSTEM,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
