import pytest
from fastapi.testclient import TestClient

from src.app.core.config import get_settings
from src.app.services.llm import GroqLanguageModel, MOCK_FIXTURES
from src.app.services.prompts import SYSTEM_PROMPT
from src.app.services.routing import parse_instruction, resolve_instruction


def test_instruction_returns_routing_json_without_executing(client: TestClient) -> None:
    response = client.post(
        "/instruction",
        json={"transcription": "add buy groceries to my list"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "endpoint": "/tasks",
        "method": "POST",
        "params": {"title": "Buy groceries"},
    }
    assert client.get("/tasks").json() == []


def test_routing_json_can_drive_the_task_endpoints(client: TestClient) -> None:
    created_route = client.post(
        "/instruction",
        json={"transcription": "add buy groceries to my list"},
    ).json()
    created = client.request(
        created_route["method"],
        created_route["endpoint"],
        json=created_route["params"],
    )
    assert created.status_code == 201

    listed_route = client.post(
        "/instruction",
        json={"transcription": "show my tasks"},
    ).json()
    listed = client.request(listed_route["method"], listed_route["endpoint"])
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "Buy groceries"

    patched_route = client.post(
        "/instruction",
        json={"transcription": "mark task 1 as done"},
    ).json()
    patched = client.request(
        patched_route["method"],
        patched_route["endpoint"],
        json=patched_route["params"],
    )
    assert patched.json()["done"] is True

    renamed_route = client.post(
        "/instruction",
        json={"transcription": "rename task 1 to Call mom"},
    ).json()
    renamed = client.request(
        renamed_route["method"],
        renamed_route["endpoint"],
        json=renamed_route["params"],
    )
    assert renamed.json()["title"] == "Call mom"
    assert renamed.json()["done"] is True

    replaced_route = client.post(
        "/instruction",
        json={"transcription": "replace task 1 with Pay rent done"},
    ).json()
    replaced = client.request(
        replaced_route["method"],
        replaced_route["endpoint"],
        json=replaced_route["params"],
    )
    assert replaced.json() == {"id": 1, "title": "Pay rent", "done": True}

    deleted_route = client.post(
        "/instruction",
        json={"transcription": "delete task 1"},
    ).json()
    deleted = client.request(deleted_route["method"], deleted_route["endpoint"])
    assert deleted.status_code == 200
    assert deleted.json()["message"] == "Task 1 deleted"
    assert client.get("/tasks").json() == []


def test_transcribe_json_executes_create_list_update_and_delete(client: TestClient) -> None:
    created = client.post(
        "/transcribe",
        json={"transcription": "añade comprar leche a mi lista"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["transcription"] == "añade comprar leche a mi lista"
    assert body["instruction"]["endpoint"] == "/tasks"
    assert body["instruction"]["method"] == "POST"
    assert body["result"]["title"] == "Comprar leche"
    assert body["result"]["done"] is False

    listed = client.post("/transcribe", json={"transcription": "lista mis tareas"})
    assert listed.json()["result"][0]["title"] == "Comprar leche"

    updated = client.post(
        "/transcribe",
        json={"transcription": "marca la tarea 1 como hecha"},
    )
    assert updated.json()["result"]["done"] is True

    deleted = client.post("/transcribe", json={"transcription": "elimina la tarea 1"})
    assert deleted.json()["result"]["message"] == "Task 1 deleted"
    assert client.get("/tasks").json() == []


def test_unknown_mock_phrase_does_not_guess(client: TestClient) -> None:
    response = client.post("/instruction", json={"transcription": "haz algo con la lista"})
    assert response.status_code == 422
    assert "exact fixture" in response.json()["detail"]
    assert client.get("/tasks").json() == []


def test_mock_rejects_invalid_and_disallowed_model_output(client: TestClient) -> None:
    invalid = client.post("/instruction", json={"transcription": "__mock_invalid_json__"})
    assert invalid.status_code == 502
    disallowed = client.post("/instruction", json={"transcription": "__mock_disallowed__"})
    assert disallowed.status_code == 422
    unsupported = client.post("/instruction", json={"transcription": "__mock_unsupported__"})
    assert unsupported.status_code == 422
    assert client.get("/tasks").json() == []


def test_missing_key_is_503_and_does_not_fake_a_call(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VOICE_COMMAND_MOCK", "0")
    monkeypatch.setenv("GROQ_API_KEY", "your_groq_api_key_here")
    get_settings.cache_clear()
    response = client.post(
        "/instruction",
        json={"transcription": "add buy groceries to my list"},
    )
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
    assert client.get("/tasks").json() == []


def test_audio_mock_does_not_invent_speech(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refused = client.post(
        "/transcribe",
        files={"file": ("command.webm", b"not-audio", "audio/webm")},
    )
    assert refused.status_code == 422
    assert "does not transcribe audio" in refused.json()["detail"]

    monkeypatch.setenv("VOICE_COMMAND_MOCK_TRANSCRIPT", "add buy groceries to my list")
    get_settings.cache_clear()
    scripted = client.post(
        "/transcribe",
        files={"file": ("command.webm", b"not-audio", "audio/webm")},
    )
    assert scripted.status_code == 200
    assert scripted.json()["transcription"] == "add buy groceries to my list"
    assert scripted.json()["result"]["title"] == "Buy groceries"


def test_audio_validation(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = client.post(
        "/transcribe",
        files={"file": ("command.webm", b"", "audio/webm")},
    )
    assert empty.status_code == 422
    bad_language = client.post(
        "/transcribe",
        data={"language": "spanish"},
        files={"file": ("command.webm", b"abc", "audio/webm")},
    )
    assert bad_language.status_code == 400
    monkeypatch.setenv("MAX_AUDIO_BYTES", "4")
    get_settings.cache_clear()
    too_big = client.post(
        "/transcribe",
        files={"file": ("command.webm", b"12345", "audio/webm")},
    )
    assert too_big.status_code == 413


def test_parser_normalizes_id_and_fenced_json() -> None:
    payload = parse_instruction(
        '```json\n{"endpoint":"/tasks","method":"delete","params":{"task_id":"3"}}\n```'
    )
    assert payload.endpoint == "/tasks/3"
    assert payload.method == "DELETE"
    assert payload.params == {}


def test_retry_uses_a_second_model_reply() -> None:
    class Flaky:
        def __init__(self) -> None:
            self.calls = 0

        def complete(self, *, system_prompt: str, user_text: str) -> str:
            assert "endpoint" in system_prompt
            self.calls += 1
            if self.calls == 1:
                return "I would add a task"
            return MOCK_FIXTURES["show my tasks"]

    model = Flaky()
    payload = resolve_instruction("show my tasks", model=model)
    assert model.calls == 2
    assert payload.method == "GET"


def test_groq_client_sends_the_sdk_payload_shape() -> None:
    class Completions:
        def __init__(self) -> None:
            self.kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs

            class Message:
                content = MOCK_FIXTURES["show my tasks"]

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class Chat:
        def __init__(self) -> None:
            self.completions = Completions()

    class Client:
        def __init__(self) -> None:
            self.chat = Chat()

    client = Client()
    settings = get_settings()
    model = GroqLanguageModel(settings, client=client)  # type: ignore[arg-type]
    text = model.complete(system_prompt=SYSTEM_PROMPT, user_text="User transcription:\nshow my tasks")
    kwargs = client.chat.completions.kwargs
    assert kwargs["model"] == settings.groq_model
    assert kwargs["temperature"] == 0
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1]["content"].endswith("show my tasks")
    assert "Buy groceries" in text or "GET" in text


def test_prompt_requires_json_only() -> None:
    assert '"endpoint"' in SYSTEM_PROMPT
    assert '"method"' in SYSTEM_PROMPT
    assert '"params"' in SYSTEM_PROMPT
    assert "one JSON object" in SYSTEM_PROMPT
    assert "No markdown" in SYSTEM_PROMPT
