from fastapi import APIRouter

from src.app.schemas.voice import InstructionPayload, InstructionRequest
from src.app.services.flow import process_transcription

router = APIRouter(tags=["instruction"])


@router.post("/instruction", response_model=InstructionPayload)
def route_instruction(payload: InstructionRequest) -> InstructionPayload:
    """Return routing JSON only. This route does not change the task list."""
    outcome = process_transcription(payload.transcription, execute=False)
    return InstructionPayload(**outcome["instruction"])
