"""Parse model JSON and apply it to the task list.

Intent selection happens in the language model. This module only checks that
the returned object is an allowed task call, then runs that call.
"""

import json
import re
from typing import Any

from fastapi import HTTPException, status

from src.app.schemas.voice import InstructionPayload
from src.app.services import llm as llm_module
from src.app.services.prompts import SYSTEM_PROMPT
from src.app.services.task_store import (
    create_task,
    delete_task,
    list_tasks,
    replace_task,
    update_task,
)

_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_TASKS = re.compile(r"^/tasks$")
_TASK_ID = re.compile(r"^/tasks/(\d+)$")
_RETRY_MARKER = "\n\nThe previous reply was invalid:"


class InstructionParseError(Exception):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_user_message(transcription: str) -> str:
    snapshot = json.dumps(list_tasks(), ensure_ascii=False)
    return (
        "Current tasks (JSON array, may be empty):\n"
        f"{snapshot}\n\n"
        "User transcription:\n"
        f"{transcription.strip()}"
    )


def resolve_instruction(
    transcription: str,
    model: Any | None = None,
) -> InstructionPayload:
    language_model = model if model is not None else llm_module.get_language_model()
    user_message = build_user_message(transcription)
    raw = language_model.complete(system_prompt=SYSTEM_PROMPT, user_text=user_message)
    try:
        return parse_instruction(raw)
    except InstructionParseError as first_error:
        retry_message = (
            user_message
            + _RETRY_MARKER
            + " "
            + first_error.message
            + "\nReply again with only the JSON object."
        )
        raw_retry = language_model.complete(
            system_prompt=SYSTEM_PROMPT,
            user_text=retry_message,
        )
        try:
            return parse_instruction(raw_retry)
        except InstructionParseError as second_error:
            raise HTTPException(
                status_code=second_error.status_code,
                detail=second_error.message,
            ) from second_error


def parse_instruction(raw: str) -> InstructionPayload:
    text = _strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InstructionParseError(
            "The model did not return valid routing JSON.",
            status_code=status.HTTP_502_BAD_GATEWAY,
        ) from exc
    if not isinstance(data, dict):
        raise InstructionParseError(
            "The model did not return a JSON object.",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    unsupported = _is_explicit_unsupported(data)
    if unsupported:
        raise InstructionParseError(
            "The model did not map this transcription to a task call.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    endpoint, method, params = _canonical_call(data)
    return InstructionPayload(endpoint=endpoint, method=method, params=params)


def execute_instruction(payload: InstructionPayload) -> Any:
    """Run a call that parse_instruction already allowed."""
    method = payload.method
    params = dict(payload.params)
    task_id = _id_from_endpoint(payload.endpoint)

    if method == "GET":
        return list_tasks()
    if method == "POST":
        return create_task(str(params["title"]), bool(params.get("done", False)))
    if task_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This call needs a task id in the endpoint path.",
        )
    if method == "PUT":
        return replace_task(task_id, str(params["title"]), bool(params["done"]))
    if method == "PATCH":
        return update_task(
            task_id,
            title=params.get("title"),
            done=params.get("done"),
        )
    if method == "DELETE":
        return delete_task(task_id)
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Method is not allowed.",
    )


def _canonical_call(data: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if "endpoint" not in data or "method" not in data:
        raise InstructionParseError(
            "Routing JSON must include endpoint and method.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if not isinstance(data["endpoint"], str) or not isinstance(data["method"], str):
        raise InstructionParseError(
            "endpoint and method must be strings.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    method = data["method"].strip().upper()
    if method not in _ALLOWED_METHODS:
        raise InstructionParseError(
            "Method is not allowed. Use GET, POST, PUT, PATCH, or DELETE.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    endpoint = _clean_endpoint(data["endpoint"])
    raw_params = data.get("params", {})
    if raw_params is None:
        raw_params = {}
    if not isinstance(raw_params, dict) or isinstance(raw_params, list):
        raise InstructionParseError(
            "params must be a JSON object.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    params = dict(raw_params)
    path_id = _id_from_endpoint(endpoint)
    param_id = _pop_param_id(params)
    if path_id is not None and param_id is not None and path_id != param_id:
        raise InstructionParseError(
            "The task id in the endpoint and in params do not match.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    task_id = path_id if path_id is not None else param_id
    if task_id is None:
        if method in {"PUT", "PATCH", "DELETE"}:
            raise InstructionParseError(
                "PUT, PATCH, and DELETE need a positive task id.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        endpoint = "/tasks"
    else:
        if method in {"GET", "POST"}:
            raise InstructionParseError(
                "GET and POST are only allowed on /tasks.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        endpoint = f"/tasks/{task_id}"

    normalized = _normalize_params(method, params)
    return endpoint, method, normalized


def _normalize_params(method: str, params: dict[str, Any]) -> dict[str, Any]:
    if method == "GET":
        _reject_unknown(params, set())
        return {}
    if method == "DELETE":
        _reject_unknown(params, set())
        return {}
    if method == "POST":
        _reject_unknown(params, {"title", "done"})
        title = _require_title(params.get("title"))
        body: dict[str, Any] = {"title": title}
        if "done" in params:
            body["done"] = _require_bool(params.get("done"))
        return body
    if method == "PUT":
        _reject_unknown(params, {"title", "done"})
        if "title" not in params or "done" not in params:
            raise InstructionParseError(
                "PUT requires title and done.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return {
            "title": _require_title(params.get("title")),
            "done": _require_bool(params.get("done")),
        }
    if method == "PATCH":
        _reject_unknown(params, {"title", "done"})
        body = {}
        if "title" in params:
            body["title"] = _require_title(params.get("title"))
        if "done" in params:
            body["done"] = _require_bool(params.get("done"))
        if not body:
            raise InstructionParseError(
                "PATCH requires title and/or done.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return body
    raise InstructionParseError(
        "Method is not allowed.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def _clean_endpoint(endpoint: str) -> str:
    value = endpoint.strip()
    if "://" in value or "?" in value or "#" in value or " " in value:
        raise InstructionParseError(
            "Endpoint must be a path, without a host or query string.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if not value.startswith("/"):
        value = "/" + value
    if len(value) > 1:
        value = value.rstrip("/")
    if _TASKS.fullmatch(value):
        return "/tasks"
    match = _TASK_ID.fullmatch(value)
    if not match:
        raise InstructionParseError(
            "Endpoint is not allowed. Use /tasks or /tasks/<id>.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    task_id = int(match.group(1))
    if task_id < 1:
        raise InstructionParseError(
            "Task id must be a positive integer.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return f"/tasks/{task_id}"


def _id_from_endpoint(endpoint: str) -> int | None:
    match = _TASK_ID.fullmatch(endpoint)
    if not match:
        return None
    return int(match.group(1))


def _pop_param_id(params: dict[str, Any]) -> int | None:
    raw = None
    if "id" in params:
        raw = params.pop("id")
    elif "task_id" in params:
        raw = params.pop("task_id")
    if raw is None:
        return None
    return _require_id(raw)


def _require_id(value: object) -> int:
    if isinstance(value, bool):
        raise InstructionParseError(
            "Task id must be a positive integer.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str) and value.strip().isdigit() and int(value.strip()) >= 1:
        return int(value.strip())
    raise InstructionParseError(
        "Task id must be a positive integer.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def _require_title(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InstructionParseError(
            "title must be a non-empty string.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    title = value.strip()
    if len(title) > 200:
        raise InstructionParseError(
            "title must be at most 200 characters.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return title


def _require_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise InstructionParseError(
        "done must be a boolean.",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def _reject_unknown(params: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise InstructionParseError(
            "params contains a field that is not allowed.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _is_explicit_unsupported(data: dict[str, Any]) -> bool:
    params = data.get("params")
    return isinstance(params, dict) and params.get("unsupported") is True


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()
