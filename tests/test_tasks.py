from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.app.services.task_store import create_task


def test_crud_status_codes_and_json(client: TestClient) -> None:
    empty = client.get("/tasks")
    assert empty.status_code == 200
    assert empty.json() == []
    assert empty.headers["content-type"].startswith("application/json")

    created = client.post("/tasks", json={"title": "Buy groceries"})
    assert created.status_code == 201
    assert created.json() == {"id": 1, "title": "Buy groceries", "done": False}

    replaced = client.put("/tasks/1", json={"title": "Pay rent", "done": True})
    assert replaced.status_code == 200
    assert replaced.json() == {"id": 1, "title": "Pay rent", "done": True}

    renamed = client.patch("/tasks/1", json={"title": "Pay rent today"})
    assert renamed.status_code == 200
    assert renamed.json()["done"] is True
    assert renamed.json()["title"] == "Pay rent today"

    marked = client.patch("/tasks/1", json={"done": False})
    assert marked.json() == {"id": 1, "title": "Pay rent today", "done": False}

    deleted = client.delete("/tasks/1")
    assert deleted.status_code == 200
    assert deleted.json() == {"message": "Task 1 deleted"}
    assert client.get("/tasks").json() == []


def test_ids_stay_unique_after_delete(client: TestClient) -> None:
    first = client.post("/tasks", json={"title": "a"}).json()
    second = client.post("/tasks", json={"title": "b"}).json()
    assert client.delete(f"/tasks/{first['id']}").status_code == 200
    third = client.post("/tasks", json={"title": "c"}).json()
    assert third["id"] not in {first["id"], second["id"]}
    assert {item["id"] for item in client.get("/tasks").json()} == {second["id"], third["id"]}


def test_parallel_creates_do_not_reuse_ids() -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(lambda _: create_task("x")["id"], range(40)))
    assert sorted(ids) == list(range(1, 41))


def test_missing_and_invalid_task_requests(client: TestClient) -> None:
    assert client.put("/tasks/9", json={"title": "x", "done": False}).status_code == 404
    assert client.patch("/tasks/9", json={"done": True}).status_code == 404
    assert client.delete("/tasks/9").status_code == 404
    assert client.post("/tasks", json={"done": False}).status_code == 422
    assert client.post("/tasks", json={"title": "   "}).status_code == 422
    assert client.put("/tasks/1", json={"title": "only title"}).status_code == 422
    assert client.patch("/tasks/1", json={}).status_code == 422
    created = client.post("/tasks", json={"title": "keep"}).json()
    assert client.patch(f"/tasks/{created['id']}", json={}).status_code == 422
    assert client.get("/tasks").json() == [created]


def test_health(client: TestClient) -> None:
    assert client.get("/").json() == {"status": "ok"}
