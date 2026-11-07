from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from starlette.datastructures import UploadFile

from src.app.schemas.voice import InstructionRequest, TranscribeFlowResponse
from src.app.services.flow import process_transcription
from src.app.services.llm import get_language_model
from src.app.core.config import get_settings
from src.app.utils.language import normalize_transcription_language

router = APIRouter(tags=["transcribe"])


@router.get("/")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/transcribe", response_model=TranscribeFlowResponse)
async def transcribe_and_run_flow(request: Request) -> TranscribeFlowResponse:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        transcription = await _transcription_from_json(request)
    else:
        transcription = await _transcription_from_audio(request)
    outcome = process_transcription(transcription, execute=True)
    return TranscribeFlowResponse(
        transcription=outcome["transcription"],
        instruction=outcome["instruction"],
        result=outcome["result"],
    )


async def _transcription_from_json(request: Request) -> str:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON body must include a transcription string.",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON body must be an object with transcription.",
        )
    raw_transcription = payload.get("transcription", "")
    if not isinstance(raw_transcription, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON body must include a non-empty transcription.",
        )
    try:
        parsed = InstructionRequest(transcription=raw_transcription)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="JSON body must include a non-empty transcription.",
        ) from exc
    return parsed.transcription


async def _transcription_from_audio(request: Request) -> str:
    form = await request.form()
    language = normalize_transcription_language(form.get("language"))
    upload = form.get("file")
    if not isinstance(upload, UploadFile):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Send multipart field 'file', or JSON {\"transcription\": \"...\"}.",
        )
    content = await upload.read()
    settings = get_settings()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audio file is empty.",
        )
    if len(content) > settings.max_audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio file is too large.",
        )
    filename = Path(upload.filename or "command.webm").name
    if filename in {"", ".", ".."}:
        filename = "command.webm"
    model = get_language_model()
    return model.transcribe(
        filename=filename[:120],
        content=content,
        content_type=upload.content_type or "application/octet-stream",
        language=language,
    )
