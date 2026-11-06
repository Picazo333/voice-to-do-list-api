import hashlib
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]

SIGNAL_HASHES = {
    "src/app/static/signal/tokens/tokens.css": "9b1f68b4a44d79f0990778953c208af96c08e5bd8bd4f70b16697fbb24f51e52",
    "src/app/static/signal/tokens/motion.css": "36b2f4d56439871d1ae46d4e2ad3e3d0d0b5da7a2700c503d4382247784b2f5c",
    "src/app/static/signal/tokens/tokens.json": "aee1644faad9743f1fd6278453f7dc5fc7ddd31572a790ad068ec23afad202fa",
    "src/app/static/signal/tokens/motion.json": "c13a8241b6a7c8d638fee1d5a4457b37da5141d2b563e58541297637a63aa5c5",
    "src/app/static/signal/brand/lockups/signal-horizontal.svg": "85459232bf51e7bf7c94225fd4f2cd6b71a681b6d701cb4ffd6d2a142cf57a81",
    "src/app/static/signal/brand/lockups/signal-stacked.svg": "11314b300284db342bc15a7c7695c23199f65f68178af45586b62d01e9ea133a",
}


def test_activity_page_shows_interpretation_without_changing_tasks(client: TestClient) -> None:
    empty = client.get("/activity/view")
    assert empty.status_code == 200
    assert "Registro de instrucciones" in empty.text
    assert "Todavía no hay instrucciones" in empty.text
    assert "signal-horizontal.svg" in empty.text
    assert "signal-stacked.svg" in empty.text
    assert 'alt="4Geeks por Divinivid"' in empty.text

    interpreted = client.post(
        "/activity/interpret",
        data={"transcription": "add buy groceries to my list"},
        follow_redirects=True,
    )
    assert interpreted.status_code == 200
    assert "POST /tasks" in interpreted.text
    assert "Buy groceries" in interpreted.text
    assert "la lista de tareas no cambió" in interpreted.text
    assert client.get("/tasks").json() == []

    executed = client.post(
        "/activity/execute",
        data={"transcription": "add buy groceries to my list"},
        follow_redirects=True,
    )
    assert "se ejecutó" in executed.text
    assert client.get("/tasks").json()[0]["title"] == "Buy groceries"


def test_activity_error_keeps_the_draft(client: TestClient) -> None:
    response = client.post(
        "/activity/execute",
        data={"transcription": "frase que no está en las fixtures"},
        follow_redirects=True,
    )
    assert "Error." in response.text
    assert "frase que no está en las fixtures" in response.text
    assert client.get("/tasks").json() == []


def test_html_404_and_json_404(client: TestClient) -> None:
    html = client.get("/no-esta", headers={"Accept": "text/html"})
    assert html.status_code == 404
    assert "Esta ruta no existe" in html.text
    as_json = client.get("/no-esta")
    assert as_json.status_code == 404
    assert as_json.json()["detail"] == "Not Found"


def test_cors_allows_the_frontend_origin_only(client: TestClient) -> None:
    allowed = client.get("/tasks", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    preflight = client.options(
        "/tasks",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    blocked = client.get("/tasks", headers={"Origin": "http://evil.example"})
    assert blocked.headers.get("access-control-allow-origin") is None


def test_frontend_bytes_match_the_template_lock() -> None:
    lock = (ROOT / "source" / "frontend-sha256.txt").read_text().splitlines()
    assert lock
    for line in lock:
        digest, relative = line.split("  ", 1)
        payload = (ROOT / "frontend" / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest


def test_signal_asset_bytes() -> None:
    for relative, digest in SIGNAL_HASHES.items():
        payload = (ROOT / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == digest


def test_store_is_memory_only_and_routes_are_not_keyword_matchers() -> None:
    banned_snippets = (
        'if "add"',
        "if 'add'",
        'if "añade"',
        "if 'añade'",
        '"add" in ',
        "'add' in ",
        '"añade" in ',
        "'añade' in ",
    )
    scanned = [
        ROOT / "src/app/api/routes/instruction.py",
        ROOT / "src/app/api/routes/transcribe.py",
        ROOT / "src/app/api/routes/tasks.py",
        ROOT / "src/app/services/routing.py",
        ROOT / "src/app/services/flow.py",
        ROOT / "src/app/services/task_store.py",
        ROOT / "src/app/services/llm.py",
    ]
    for path in scanned:
        text = path.read_text(encoding="utf-8")
        for snippet in banned_snippets:
            assert snippet not in text, f"{path} contains {snippet}"
    for path in (ROOT / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert "sqlite" not in text
        assert "sqlalchemy" not in text
    assert "tasks: list[dict[str, Any]] = []" in (
        ROOT / "src/app/services/task_store.py"
    ).read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines()
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "gsk_" not in example
    for path in (ROOT / "src").rglob("*.py"):
        assert "gsk_" not in path.read_text(encoding="utf-8")
