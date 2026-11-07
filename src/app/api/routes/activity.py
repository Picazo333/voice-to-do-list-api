from typing import Any

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse

from src.app.services.activity_log import list_activity
from src.app.services.activity_page import (
    execute_and_redirect,
    interpret_and_redirect,
    render_activity_page,
)

router = APIRouter(tags=["activity"])


@router.get("/activity")
def get_activity() -> list[dict[str, Any]]:
    return list_activity()


@router.get("/activity/view", response_class=HTMLResponse)
def view_activity(
    notice: str | None = Query(default=None),
    error: str | None = Query(default=None),
    draft: str | None = Query(default=None),
    flow: str | None = Query(default=None),
) -> HTMLResponse:
    page = render_activity_page(
        notice=notice,
        error=_clip(error),
        draft=_clip(draft, 2000),
        flow=flow if flow in {"interpret", "execute"} else None,
    )
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


@router.post("/activity/interpret")
def post_interpret(transcription: str = Form(default="")):
    return interpret_and_redirect(transcription)


@router.post("/activity/execute")
def post_execute(transcription: str = Form(default="")):
    return execute_and_redirect(transcription)


def _clip(value: str | None, limit: int = 500) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    return cleaned[:limit]
