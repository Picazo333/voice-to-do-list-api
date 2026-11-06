import pytest
from fastapi.testclient import TestClient

from src.app.core.config import get_settings
from src.app.main import app
from src.app.services.activity_log import reset_activity
from src.app.services.task_store import reset_tasks


@pytest.fixture(autouse=True)
def _isolate_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VOICE_COMMAND_MOCK", "1")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.delenv("VOICE_COMMAND_MOCK_TRANSCRIPT", raising=False)
    get_settings.cache_clear()
    reset_tasks()
    reset_activity()
    yield
    get_settings.cache_clear()
    reset_tasks()
    reset_activity()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
