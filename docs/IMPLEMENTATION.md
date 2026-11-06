# Implementación

Documento técnico de esta copia. No sustituye el enunciado del template en `README.md` ni el enunciado del syllabus en `source/`.

## Procedencia

| Pieza | Identidad |
|---|---|
| Template | https://github.com/4GeeksAcademy/voice-command-api @ `bab45fe91823d3dc5a285269f7c3b66898ab0224` |
| Syllabus | https://github.com/4GeeksAcademy/ai-engineering-syllabus @ `fd2da034894ba93ba738559280ccde074ab1d953` |
| Frontend | Copia byte a byte. Lista en `source/frontend-sha256.txt`. |
| Licencia | El snapshot del template no incluye archivo `LICENSE`. El encabezado de autoría de `README.md` y `README.es.md` queda el del template. |

El syllabus habla de Web Speech API en el navegador y de un frontend que, con el JSON de `POST /instruction`, llama él mismo a los endpoints de tareas. El frontend de este template no hace eso: graba audio o acepta texto manual y lo envía a `POST /transcribe`. Esa diferencia se resuelve conservando el frontend y cubriendo los dos contratos en el backend.

## Cómo correrlo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

En `.env`, o bien pegas una `GROQ_API_KEY` real, o dejas el placeholder y activas el modo de prueba:

```bash
VOICE_COMMAND_MOCK=1
```

Backend:

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (no está modificado; hace falta su `.env`):

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

`frontend/.env` debe contener `VITE_API_BASE_URL=http://127.0.0.1:8000`.

Pruebas:

```bash
pytest
```

## Datos

La única lista de tareas es `tasks` en `src/app/services/task_store.py`. Cada elemento tiene `id` (entero, no se reutiliza), `title` (texto) y `done` (booleano, alta por defecto `false`). No hay base de datos ni fichero de tareas. El proceso, al reiniciar, empieza vacío.

Hay un registro aparte, `activity`, también en memoria, para la página extra. No es el almacén de tareas.

## Endpoints

| Método y ruta | Efecto | Código habitual |
|---|---|---|
| `GET /tasks` | Lista | 200 |
| `POST /tasks` | Alta. Cuerpo: `title`, `done` opcional | 201 |
| `PUT /tasks/{id}` | Reemplazo. Exige `title` y `done` | 200 o 404 |
| `PATCH /tasks/{id}` | Cambia `title` y/o `done` | 200, 404 o 422 si el cuerpo va vacío |
| `DELETE /tasks/{id}` | Borra. Cuerpo: `{"message": "Task <id> deleted"}` | 200 o 404 |
| `POST /instruction` | JSON `{ "transcription": "..." }`. Devuelve `{endpoint, method, params}` y no toca la lista | 200, 422, 502 o 503 |
| `POST /transcribe` | JSON con `transcription`, o multipart con `file` y `language` opcional. Transcribe si hace falta, reutiliza `/instruction` y ejecuta | 200 o error |
| `GET /` | `{"status": "ok"}` | 200 |
| `GET /activity` | Registro JSON | 200 |
| `GET /activity/view` | Misma información en HTML | 200 |

CORS permite `http://localhost:5173` y `http://127.0.0.1:5173`. Se cambia con `ALLOWED_ORIGINS`.

## Groq y modo mock

Con `VOICE_COMMAND_MOCK=0` y una clave distinta del placeholder, `/instruction` llama a `Groq.chat.completions.create` (modelo por defecto `llama-3.1-8b-instant`, JSON, temperatura 0). El audio llama a `Groq.audio.transcriptions.create` con `whisper-large-v3-turbo`. La clave se lee en el servidor y no se envía al navegador ni se imprime en los errores.

El enunciado cita `llama3-8b-8192` o uno similar. El template fija `llama-3.1-8b-instant`. Ese es el valor por defecto. `GROQ_MODEL` lo cambia.

Si no hay clave, la API responde 503. No inventa una decisión.

`VOICE_COMMAND_MOCK=1` no abre red. Compara la transcripción completa con la tabla de abajo. Si no está, responde 422. No hay un `if "add" in text`.

El audio en mock no se transcribe. Hace falta `VOICE_COMMAND_MOCK_TRANSCRIPT` con una frase de la tabla, o enviar JSON. Eso no es una transcripción de Whisper.

Un criterio que exija una llamada real a Groq, o voz grabada de verdad, no queda cubierto por este modo.

### Frases exactas del mock

| Transcripción | Llamada |
|---|---|
| `add buy groceries to my list` | `POST /tasks` `{"title":"Buy groceries"}` |
| `añade comprar leche a mi lista` | `POST /tasks` `{"title":"Comprar leche"}` |
| `show my tasks` | `GET /tasks` |
| `lista mis tareas` | `GET /tasks` |
| `mark task 1 as done` | `PATCH /tasks/1` `{"done":true}` |
| `marca la tarea 1 como hecha` | `PATCH /tasks/1` `{"done":true}` |
| `rename task 1 to Call mom` | `PATCH /tasks/1` `{"title":"Call mom"}` |
| `renombra la tarea 1 a Llamar a mamá` | `PATCH /tasks/1` `{"title":"Llamar a mamá"}` |
| `replace task 1 with Pay rent done` | `PUT /tasks/1` `{"title":"Pay rent","done":true}` |
| `delete task 1` | `DELETE /tasks/1` |
| `elimina la tarea 1` | `DELETE /tasks/1` |

Sentinelas de prueba, no son comandos de usuario: `__mock_invalid_json__`, `__mock_disallowed__`, `__mock_unsupported__`.

## Qué decide el modelo

`src/app/services/prompts.py` exige un único objeto JSON con `endpoint`, `method` y `params`. El mensaje de usuario incluye la lista actual para que el modelo pueda resolver un título a un id. El servidor solo valida que la llamada sea `GET/POST /tasks` o `PUT/PATCH/DELETE /tasks/<id>`, normaliza el id y ejecuta esa llamada. Si el JSON no es válido, hay un segundo intento. Si sigue mal, 502 o 422. No se reescribe la frase con reglas de verbos.

La página `GET /activity/view` enseña esa llamada. «Interpretar transcripción» no modifica la lista. «Ejecutar transcripción» sí. El frontend de `/frontend` sigue usando solo `POST /transcribe`.

## Qué no está demostrado aquí

- No hay `GROQ_API_KEY` de trabajo en el entorno de verificación, así que no hay evidencia de una respuesta real del modelo.
- El micrófono de la VM no se usa como prueba de voz. El fallo de captura o el campo manual del frontend no equivalen a un comando hablado.
