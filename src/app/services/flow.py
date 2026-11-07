"""Shared path for /instruction and /transcribe."""

from typing import Any

from fastapi import HTTPException, status

from src.app.schemas.voice import InstructionPayload
from src.app.services.activity_log import record_activity
from src.app.services.routing import execute_instruction, resolve_instruction


def process_transcription(
    transcription: str,
    *,
    execute: bool,
    model: Any | None = None,
) -> dict[str, Any]:
    cleaned = transcription.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transcription must not be blank.",
        )
    instruction: dict[str, Any] | None = None
    result: Any = None
    try:
        payload: InstructionPayload = resolve_instruction(cleaned, model=model)
        instruction = payload.model_dump()
        if execute:
            result = execute_instruction(payload)
    except HTTPException as exc:
        record_activity(
            transcription=cleaned,
            instruction=instruction,
            executed=execute,
            result=None,
            error=_detail_text(exc.detail),
        )
        raise
    record_activity(
        transcription=cleaned,
        instruction=instruction,
        executed=execute,
        result=result,
        error=None,
    )
    return {
        "transcription": cleaned,
        "instruction": instruction,
        "result": result,
    }


def _detail_text(detail: object) -> str:
    if isinstance(detail, str):
        return detail
    return "Request failed."
