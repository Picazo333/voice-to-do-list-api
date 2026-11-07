# 008 — Evidencia de micrófono E2E: revisión parcial

**Fecha de prueba:** 2026-11-07 (CDMX). **Criterio:** R25, comandos por voz real.
**Origen:** video de 140.22 s enviado por el alumno, `Voice Command Frontend - Google Chrome 2026-11-07 00-20-56.mp4`; resolución 1920×1020, contiene pista de audio. Se inspeccionó la grabación y se preparó un extracto de 52.33 s con sus operaciones acreditadas, sin las pestañas ajenas de ChatGPT. Las marcas de tiempo siguientes son del archivo original.

## Evidencia que aparece realmente en el video

| Operación | Evidencia visual | Estado |
| --- | --- | --- |
| Crear | ~00:22: la transcripción visible es «Add boy groceries to my list.»; la respuesta devuelve `id: 1`, `title: "Boy groceries"`, `done: false`. Hubo otra alta con título «Bui groceries» e id 2 | PASS de **creación**; precisión ASR imperfecta |
| Listar | ~00:58: «show my task», y la respuesta muestra dos tareas, ids 1 y 2 | PASS de **listado** |
| Completar | ~02:08: «Mark task one as done.»; API devuelve `id:1`, `title:"Boy groceries"`, `done:true` | PASS de **actualización de estado** |
| Eliminar | No aparece una respuesta de borrado dentro del archivo. Al final de la grabación se muestra ChatGPT indicando el siguiente paso «Delete task one» | **SIN EVIDENCIA** |

## Incidencias observadas

- El ASR identificó `buy` como `boy` y `bui` en altas de prueba, por lo que no se acredita la conservación exacta del título esperado «Buy groceries».
- En torno a 01:40 se ve respuesta `422`: `The model did not map this transcription to a task call.` La actualización de estado se consiguió posteriormente, en un nuevo intento.
- Antes de esta prueba, el alumno diagnosticó y resolvió un `404` de Groq en la ruta `POST /instruction` cambiando localmente el modelo a `openai/gpt-oss-20b`; este ajuste **no** se ha publicado como cambio de configuración en el repositorio.
- En los fotogramas inspeccionados no se observó un archivo `.env` ni la API key, pero el video original contiene pestañas y contenidos personales ajenos al ejercicio, por lo que se debe publicar **solo un extracto depurado**.

**Nota del alumno sobre la captura pendiente:** Se realizó y guardó la grabación de video de la prueba. Posteriormente se cerró la pantalla de la aplicación, por lo que no fue posible tomar una captura adicional del resultado final. El video disponible no muestra la respuesta de eliminación; en consecuencia, esta nota explica la ausencia de la captura, pero no se considera evidencia independiente de DELETE.

## Adjudicación

**R25: parcialmente comprobado, NO cerrado.** Las rutas de crear, listar y marcar completada funcionan mediante audio capturado en navegador y respuesta de la API. Para acreditar las cuatro operaciones se necesita únicamente una captura o clip que muestre la respuesta de eliminación real (no repetir las tres anteriores).

**Evidencia pendiente de publicación:** `4Geeks_008_voz_evidencia_parcial_extractos.mp4` (extracto de 52.33 s), más la evidencia de DELETE. Este documento no afirma que el video esté ya alojado en GitHub. No adjuntar el original completo por posible divulgación incidental de pestañas personales.

**No se realizó** merge, despliegue ni modificación de la lógica del backend.
