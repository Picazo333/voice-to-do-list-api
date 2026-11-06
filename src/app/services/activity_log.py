"""In-memory log of interpretations. Not a task store and not written to disk."""

from datetime import datetime, timezone
from threading import Lock
from typing import Any

activity: list[dict[str, Any]] = []
_next_id = 1
_lock = Lock()
_MAX_ENTRIES = 100


def reset_activity() -> None:
    global _next_id
    with _lock:
        activity.clear()
        _next_id = 1


def list_activity() -> list[dict[str, Any]]:
    with _lock:
        return [dict(item) for item in activity]


def record_activity(
    *,
    transcription: str,
    instruction: dict[str, Any] | None,
    executed: bool,
    result: Any,
    error: str | None,
) -> dict[str, Any]:
    global _next_id
    entry = {
        "id": _next_id,
        "at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "transcription": transcription,
        "instruction": instruction,
        "executed": executed,
        "result": result,
        "error": error,
    }
    with _lock:
        entry["id"] = _next_id
        _next_id += 1
        activity.append(entry)
        if len(activity) > _MAX_ENTRIES:
            del activity[: len(activity) - _MAX_ENTRIES]
        return dict(entry)
