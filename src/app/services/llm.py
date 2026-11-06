"""Language-model gateway.

Production calls the Groq SDK with GROQ_API_KEY.
VOICE_COMMAND_MOCK=1 selects exact-string fixtures and never calls the network.
There is no keyword intent matcher on either path.
"""

import json
from typing import Protocol

from fastapi import HTTPException, status
from groq import APIError, Groq

from src.app.core.config import Settings, get_settings

_UNSET_KEYS = {"", "your_groq_api_key_here"}
_TRANSCRIPTION_MARKER = "User transcription:\n"
_RETRY_MARKER = "\n\nThe previous reply was invalid:"

# Exact transcription -> model text. Test double only.
MOCK_FIXTURES: dict[str, str] = {
    "add buy groceries to my list": json.dumps(
        {"endpoint": "/tasks", "method": "POST", "params": {"title": "Buy groceries"}}
    ),
    "añade comprar leche a mi lista": json.dumps(
        {"endpoint": "/tasks", "method": "POST", "params": {"title": "Comprar leche"}}
    ),
    "show my tasks": json.dumps(
        {"endpoint": "/tasks", "method": "GET", "params": {}}
    ),
    "lista mis tareas": json.dumps(
        {"endpoint": "/tasks", "method": "GET", "params": {}}
    ),
    "mark task 1 as done": json.dumps(
        {"endpoint": "/tasks/1", "method": "PATCH", "params": {"done": True}}
    ),
    "marca la tarea 1 como hecha": json.dumps(
        {"endpoint": "/tasks/1", "method": "PATCH", "params": {"done": True}}
    ),
    "rename task 1 to Call mom": json.dumps(
        {
            "endpoint": "/tasks/1",
            "method": "PATCH",
            "params": {"title": "Call mom"},
        }
    ),
    "renombra la tarea 1 a Llamar a mamá": json.dumps(
        {
            "endpoint": "/tasks/1",
            "method": "PATCH",
            "params": {"title": "Llamar a mamá"},
        }
    ),
    "replace task 1 with Pay rent done": json.dumps(
        {
            "endpoint": "/tasks/1",
            "method": "PUT",
            "params": {"title": "Pay rent", "done": True},
        }
    ),
    "delete task 1": json.dumps(
        {"endpoint": "/tasks/1", "method": "DELETE", "params": {}}
    ),
    "elimina la tarea 1": json.dumps(
        {"endpoint": "/tasks/1", "method": "DELETE", "params": {}}
    ),
    "__mock_invalid_json__": "not json",
    "__mock_disallowed__": json.dumps(
        {"endpoint": "/admin", "method": "POST", "params": {}}
    ),
    "__mock_unsupported__": json.dumps(
        {"endpoint": "/tasks", "method": "GET", "params": {"unsupported": True}}
    ),
}


class LanguageModel(Protocol):
    def complete(self, *, system_prompt: str, user_text: str) -> str: ...

    def transcribe(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        language: str | None,
    ) -> str: ...


class GroqLanguageModel:
    """Real Groq SDK client. Constructed only when a key is configured."""

    def __init__(self, settings: Settings, client: Groq | None = None) -> None:
        key = configured_groq_api_key(settings)
        if client is None and key is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=_missing_key_detail(),
            )
        self._client = client or Groq(
            api_key=key,
            timeout=settings.request_timeout_seconds,
            max_retries=1,
        )
        self._model = settings.groq_model
        self._transcription_model = settings.groq_transcription_model

    def complete(self, *, system_prompt: str, user_text: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            )
        except APIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_groq_failure_detail(exc),
            ) from exc
        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Groq returned an empty completion.",
            )
        return content

    def transcribe(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        language: str | None,
    ) -> str:
        file_payload = (filename, content, content_type or "application/octet-stream")
        kwargs: dict[str, object] = {
            "file": file_payload,
            "model": self._transcription_model,
            "response_format": "json",
            "temperature": 0,
        }
        if language:
            kwargs["language"] = language
        try:
            result = self._client.audio.transcriptions.create(**kwargs)
        except APIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=_groq_failure_detail(exc),
            ) from exc
        text = getattr(result, "text", None)
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Groq transcription was empty.",
            )
        return text.strip()


class MockLanguageModel:
    """Exact-string fixtures. Refuses unknown text instead of guessing an intent."""

    def complete(self, *, system_prompt: str, user_text: str) -> str:
        _ = system_prompt
        transcription = _transcription_from_user_message(user_text)
        try:
            return MOCK_FIXTURES[transcription]
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Mock mode has no exact fixture for this transcription. "
                    "It will not guess an intent. Use a documented fixture, "
                    "or set VOICE_COMMAND_MOCK=0 and provide GROQ_API_KEY."
                ),
            ) from exc

    def transcribe(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        language: str | None,
    ) -> str:
        _ = (filename, content, content_type, language)
        settings = get_settings()
        scripted = settings.voice_command_mock_transcript.strip()
        if not scripted:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Mock mode does not transcribe audio and will not invent speech. "
                    "Send JSON {\"transcription\": \"...\"}, set "
                    "VOICE_COMMAND_MOCK_TRANSCRIPT to an exact fixture phrase, "
                    "or call Groq Whisper with GROQ_API_KEY and VOICE_COMMAND_MOCK=0."
                ),
            )
        return scripted


def get_language_model() -> LanguageModel:
    settings = get_settings()
    if settings.voice_command_mock:
        return MockLanguageModel()
    if configured_groq_api_key(settings) is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_missing_key_detail(),
        )
    return GroqLanguageModel(settings)


def configured_groq_api_key(settings: Settings) -> str | None:
    value = settings.groq_api_key.strip()
    if value in _UNSET_KEYS:
        return None
    return value


def _transcription_from_user_message(user_text: str) -> str:
    if _TRANSCRIPTION_MARKER not in user_text:
        return user_text.strip()
    rest = user_text.split(_TRANSCRIPTION_MARKER, 1)[1]
    if _RETRY_MARKER in rest:
        rest = rest.split(_RETRY_MARKER, 1)[0]
    return rest.strip()


def _missing_key_detail() -> str:
    return (
        "GROQ_API_KEY is not set. Refusing to invent a routing decision. "
        "Set the key in the server environment, or set VOICE_COMMAND_MOCK=1 "
        "to use exact-string fixtures."
    )


def _groq_failure_detail(exc: APIError) -> str:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return f"Groq request failed with status {status_code}."
    return "Groq request failed."
