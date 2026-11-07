from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.app.api.routes.activity import router as activity_router
from src.app.api.routes.instruction import router as instruction_router
from src.app.api.routes.tasks import router as tasks_router
from src.app.api.routes.transcribe import router as transcribe_router
from src.app.core.config import get_settings
from src.app.services.activity_page import render_not_found

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Voice Command Transcription API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    app.include_router(tasks_router)
    app.include_router(instruction_router)
    app.include_router(transcribe_router)
    app.include_router(activity_router)
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ):
        if exc.status_code == 404 and _prefers_html(request):
            return HTMLResponse(render_not_found(request.url.path), status_code=404)
        detail = exc.detail if exc.detail is not None else "Request failed."
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    return app


def _prefers_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    html_at = accept.find("text/html")
    if html_at < 0:
        return False
    json_at = accept.find("application/json")
    if json_at < 0:
        return True
    return html_at < json_at


app = create_app()
