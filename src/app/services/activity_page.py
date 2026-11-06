"""Server-rendered instruction log. Works without JavaScript."""

import json
from html import escape
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

from src.app.core.config import get_settings
from src.app.services import llm as llm_module
from src.app.services.activity_log import list_activity
from src.app.services.flow import process_transcription
from src.app.services.task_store import list_tasks

_EXAMPLE = "add buy groceries to my list"


def interpret_and_redirect(transcription: str) -> RedirectResponse:
    return _run_and_redirect(transcription, execute=False, notice="interpreted")


def execute_and_redirect(transcription: str) -> RedirectResponse:
    return _run_and_redirect(transcription, execute=True, notice="executed")


def render_activity_page(
    *,
    notice: str | None = None,
    error: str | None = None,
    draft: str | None = None,
    flow: str | None = None,
) -> str:
    tasks = list_tasks()
    entries = list(reversed(list_activity()))
    mode = _mode_copy()
    notice_html = _notice_html(notice)
    error_html = _error_html(error)
    interpret_draft = escape(draft) if flow == "interpret" and draft else ""
    execute_draft = escape(draft) if flow == "execute" and draft else ""
    return f"""<!doctype html>
<html lang="es" data-motion="full">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <link rel="icon" href="data:,">
  <meta name="description" content="Registro de cómo una transcripción se convierte en una llamada HTTP a la lista de tareas.">
  <title>Registro de instrucciones · Voice Command API</title>
  <link rel="stylesheet" href="/static/signal/tokens/tokens.css">
  <link rel="stylesheet" href="/static/signal/tokens/motion.css">
  <link rel="stylesheet" href="/static/activity.css">
</head>
<body>
  <a class="skip" href="#contenido">Saltar al contenido</a>
  <header class="site-header">
    <div class="wrap">
      <p class="kicker">Voice Command API</p>
      <h1>Registro de instrucciones</h1>
      <p class="lead">Cada transcripción se convierte en una llamada HTTP. Interpretar solo muestra esa llamada. Ejecutar la aplica a la lista en memoria.</p>
      <p class="banner" role="status">{escape(mode)}</p>
    </div>
  </header>
  <main id="contenido" tabindex="-1">
    <div class="wrap">
      <p id="loading" class="loading" hidden role="status">Enviando la transcripción…</p>
      {notice_html}
      {error_html}
      <section class="panel" aria-labelledby="acciones-titulo">
        <h2 id="acciones-titulo">Acciones</h2>
        <div class="actions">
          <form method="post" action="/activity/interpret" data-flow="interpret">
            <h3>Interpretar sin ejecutar</h3>
            <p class="help">No crea, cambia ni borra tareas. Sirve para leer endpoint, método y parámetros.</p>
            <label for="interpret-text">Transcripción</label>
            <textarea id="interpret-text" name="transcription" required minlength="1" rows="4">{interpret_draft}</textarea>
            <button class="primary" type="submit">Interpretar transcripción</button>
          </form>
          <form method="post" action="/activity/execute" data-flow="execute">
            <h3>Ejecutar en la lista</h3>
            <p class="help">Usa la misma decisión y llama al endpoint de tareas. La interfaz de voz del puerto 5173 hace este paso sola.</p>
            <label for="execute-text">Transcripción</label>
            <textarea id="execute-text" name="transcription" required minlength="1" rows="4">{execute_draft}</textarea>
            <button class="primary" type="submit">Ejecutar transcripción</button>
          </form>
        </div>
        <p class="help">{escape(_fixture_help())}</p>
      </section>
      <section aria-labelledby="tareas-titulo">
        <h2 id="tareas-titulo">Tareas en memoria</h2>
        <p class="meta">{len(tasks)} en esta ejecución del proceso. Reiniciar el servidor vacía la lista.</p>
        {_tasks_table(tasks)}
      </section>
      <section aria-labelledby="registro-titulo">
        <h2 id="registro-titulo">Interpretaciones</h2>
        <p class="meta">{len(entries)} registradas en memoria, de la más reciente a la más antigua.</p>
        {_activity_table(entries)}
        <p class="meta"><a href="/activity">Ver este registro en JSON</a> · <a href="/docs">Contrato OpenAPI</a></p>
      </section>
    </div>
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <p class="caption">Crédito visual del encargo académico. No implica aval oficial de las marcas.</p>
      <img class="lockup lockup-horizontal" src="/static/signal/brand/lockups/signal-horizontal.svg" width="400" height="64" alt="4Geeks por Divinivid">
      <img class="lockup lockup-stacked" src="/static/signal/brand/lockups/signal-stacked.svg" width="280" height="140" alt="4Geeks por Divinivid">
    </div>
  </footer>
  <script src="/static/activity.js"></script>
</body>
</html>
"""


def render_not_found(path: str) -> str:
    safe_path = escape(path[:200])
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <link rel="icon" href="data:,">
  <title>Ruta no encontrada · Voice Command API</title>
  <link rel="stylesheet" href="/static/signal/tokens/tokens.css">
  <link rel="stylesheet" href="/static/signal/tokens/motion.css">
  <link rel="stylesheet" href="/static/activity.css">
</head>
<body>
  <a class="skip" href="#contenido">Saltar al contenido</a>
  <main id="contenido" class="wrap" tabindex="-1">
    <p class="kicker">404</p>
    <h1>Esta ruta no existe</h1>
    <p class="lead">No hay ningún recurso en <span class="mono">{safe_path}</span>.</p>
    <p><a class="button-link" href="/activity/view">Volver al registro de instrucciones</a></p>
  </main>
  <footer class="site-footer">
    <div class="wrap">
      <p class="caption">Crédito visual del encargo académico. No implica aval oficial de las marcas.</p>
      <img class="lockup lockup-horizontal" src="/static/signal/brand/lockups/signal-horizontal.svg" width="400" height="64" alt="4Geeks por Divinivid">
      <img class="lockup lockup-stacked" src="/static/signal/brand/lockups/signal-stacked.svg" width="280" height="140" alt="4Geeks por Divinivid">
    </div>
  </footer>
</body>
</html>
"""


def _run_and_redirect(transcription: str, *, execute: bool, notice: str) -> RedirectResponse:
    cleaned = transcription.strip()
    flow = "execute" if execute else "interpret"
    if not cleaned:
        return _redirect(error="Escribe una transcripción antes de enviarla.", draft="", flow=flow)
    try:
        process_transcription(cleaned, execute=execute)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else "La solicitud falló."
        return _redirect(error=detail, draft=cleaned, flow=flow)
    return _redirect(notice=notice)


def _redirect(
    *,
    notice: str | None = None,
    error: str | None = None,
    draft: str | None = None,
    flow: str | None = None,
) -> RedirectResponse:
    params: list[str] = []
    if notice:
        params.append("notice=" + quote(notice))
    if error:
        params.append("error=" + quote(error[:500]))
    if draft:
        params.append("draft=" + quote(draft[:2000]))
    if flow:
        params.append("flow=" + quote(flow))
    query = ("?" + "&".join(params)) if params else ""
    return RedirectResponse(url="/activity/view" + query, status_code=303)


def _mode_copy() -> str:
    settings = get_settings()
    if settings.voice_command_mock:
        return (
            "Modo mock explícito. Groq no se llama. "
            "La transcripción tiene que coincidir con una frase de prueba, carácter por carácter."
        )
    if llm_module.configured_groq_api_key(settings) is None:
        return (
            "No hay GROQ_API_KEY y el modo mock está apagado. "
            "Interpretar devolverá un error hasta configurar el servidor."
        )
    return (
        "Groq está configurado en el servidor. La clave no se envía al navegador. "
        "Esta página no puede demostrar por sí sola que la llamada de red ocurrió."
    )


def _fixture_help() -> str:
    settings = get_settings()
    if settings.voice_command_mock:
        return (
            "Ejemplo exacto en modo mock: "
            + _EXAMPLE
            + ". Otras frases documentadas están en docs/IMPLEMENTATION.md."
        )
    return (
        "Ejemplo de comando: "
        + _EXAMPLE
        + ". Con Groq activo la frase no tiene que coincidir con una lista fija."
    )


def _notice_html(notice: str | None) -> str:
    if notice == "interpreted":
        text = "Listo. La interpretación quedó registrada y la lista de tareas no cambió."
    elif notice == "executed":
        text = "Listo. La instrucción se ejecutó sobre la lista en memoria."
    else:
        return ""
    return f'<p class="notice" role="status">Listo. {escape(text.removeprefix("Listo. "))}</p>'


def _error_html(error: str | None) -> str:
    if not error:
        return ""
    return (
        '<div class="alert" role="alert">'
        f"<p><strong>Error.</strong> {escape(error)}</p>"
        '<p><a class="button-link" href="/activity/view">Reintentar</a></p>'
        "</div>"
    )


def _tasks_table(tasks: list[dict[str, Any]]) -> str:
    if not tasks:
        return (
            '<div class="table-scroll" tabindex="0" aria-label="Tareas en memoria">'
            "<table><caption class=\"sr-only\">Tareas en memoria</caption><thead><tr>"
            "<th>Id</th><th>Título</th><th>Hecha</th></tr></thead><tbody><tr>"
            "<td colspan=\"3\">No hay tareas. Ejecuta una transcripción de alta, "
            f"por ejemplo {escape(_EXAMPLE)}.</td></tr></tbody></table></div>"
        )
    rows = []
    for task in tasks:
        done = "Sí" if task["done"] else "No"
        rows.append(
            "<tr>"
            f"<td>{task['id']}</td>"
            f"<td>{escape(str(task['title']))}</td>"
            f"<td>{done}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return (
        '<div class="table-scroll" tabindex="0" aria-label="Tareas en memoria, desplazamiento horizontal si no cabe">'
        "<table><caption class=\"sr-only\">Tareas en memoria</caption><thead><tr>"
        "<th>Id</th><th>Título</th><th>Hecha</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
    )


def _activity_table(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return (
            '<div class="table-scroll" tabindex="0" aria-label="Interpretaciones">'
            "<table><caption class=\"sr-only\">Interpretaciones</caption><thead><tr>"
            "<th>Hora</th><th>Transcripción</th><th>Llamada</th><th>Modo</th><th>Resultado</th>"
            "</tr></thead><tbody><tr><td colspan=\"5\">Todavía no hay instrucciones. "
            "Escribe una transcripción y pulsa Interpretar transcripción.</td></tr></tbody></table></div>"
        )
    rows = []
    for index, entry in enumerate(entries):
        fresh = " is-new" if index == 0 else ""
        motion = " data-motion-node" if index == 0 else ""
        call = _call_text(entry)
        mode = "Ejecutar" if entry["executed"] else "Interpretar"
        result = _result_text(entry)
        rows.append(
            f"<tr class=\"{fresh.strip()}\"{motion}>"
            f"<td>{escape(str(entry['at']))}</td>"
            f"<td>{escape(str(entry['transcription']))}</td>"
            f"<td class=\"mono\">{escape(call)}</td>"
            f"<td>{mode}</td>"
            f"<td class=\"mono\">{escape(result)}</td>"
            "</tr>"
        )
    body = "".join(rows)
    return (
        '<div class="table-scroll" tabindex="0" aria-label="Interpretaciones, desplazamiento horizontal si no cabe">'
        "<table><caption class=\"sr-only\">Interpretaciones</caption><thead><tr>"
        "<th>Hora</th><th>Transcripción</th><th>Llamada</th><th>Modo</th><th>Resultado</th>"
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _call_text(entry: dict[str, Any]) -> str:
    instruction = entry.get("instruction")
    if not isinstance(instruction, dict):
        return "Sin llamada"
    method = instruction.get("method", "")
    endpoint = instruction.get("endpoint", "")
    params = json.dumps(instruction.get("params", {}), ensure_ascii=False)
    return f"{method} {endpoint} {params}"


def _result_text(entry: dict[str, Any]) -> str:
    if entry.get("error"):
        return "Error: " + str(entry["error"])
    if entry.get("result") is None:
        return "Sin resultado"
    return json.dumps(entry["result"], ensure_ascii=False)
