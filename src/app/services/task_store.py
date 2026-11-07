"""In-memory task list.

`tasks` is the only task store. Nothing in this module reads or writes the
filesystem or a database. The list is empty again after the process restarts.
"""

from threading import Lock
from typing import Any

from fastapi import HTTPException, status

tasks: list[dict[str, Any]] = []
_next_id = 1
_lock = Lock()


def reset_tasks() -> None:
    global _next_id
    with _lock:
        tasks.clear()
        _next_id = 1


def list_tasks() -> list[dict[str, Any]]:
    with _lock:
        return [_copy(item) for item in tasks]


def create_task(title: str, done: bool = False) -> dict[str, Any]:
    global _next_id
    cleaned = _require_title(title)
    with _lock:
        task = {"id": _next_id, "title": cleaned, "done": bool(done)}
        _next_id += 1
        tasks.append(task)
        return _copy(task)


def replace_task(task_id: int, title: str, done: bool) -> dict[str, Any]:
    cleaned = _require_title(title)
    with _lock:
        index = _index_of(task_id)
        task = {"id": task_id, "title": cleaned, "done": bool(done)}
        tasks[index] = task
        return _copy(task)


def update_task(
    task_id: int,
    *,
    title: str | None = None,
    done: bool | None = None,
) -> dict[str, Any]:
    if title is None and done is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide title and/or done.",
        )
    cleaned = _require_title(title) if title is not None else None
    with _lock:
        index = _index_of(task_id)
        current = tasks[index]
        if cleaned is not None:
            current["title"] = cleaned
        if done is not None:
            current["done"] = bool(done)
        return _copy(current)


def delete_task(task_id: int) -> dict[str, str]:
    with _lock:
        index = _index_of(task_id)
        tasks.pop(index)
    return {"message": f"Task {task_id} deleted"}


def _require_title(title: str) -> str:
    if not isinstance(title, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title must be a string.",
        )
    cleaned = title.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title must not be blank.",
        )
    if len(cleaned) > 200:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Title must be at most 200 characters.",
        )
    return cleaned


def _index_of(task_id: int) -> int:
    for index, task in enumerate(tasks):
        if task["id"] == task_id:
            return index
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Task {task_id} not found.",
    )


def _copy(task: dict[str, Any]) -> dict[str, Any]:
    return {"id": task["id"], "title": task["title"], "done": task["done"]}
