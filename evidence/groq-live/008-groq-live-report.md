# 008 Groq live evidence
captured_at: 2026-11-06 08:38:44 CST

## R14: PASS
- command: POST /instruction with VOICE_COMMAND_MOCK=0 and real GROQ_API_KEY
- timestamp_cst: 2026-11-06 08:38:44 CST
- model: qwen/qwen3.8-27b
- note: Llamada real al SDK Groq chat.completions (temperature=0, response_format=json_object). Sin mock.
- call1: {'transcription': 'add buy groceries to my list', 'http_status': 200, 'latency_ms': 462.1}
- call2: {'transcription': 'show my tasks', 'http_status': 200, 'latency_ms': 290.0}

## R16: PASS
- command: POST /instruction x9 frases EN/ES distintas (modelo real)
- timestamp_cst: 2026-11-06 08:38:44 CST
- ok_json_shapes: 9
- total: 9
- semantic_checks: {'create_en': True, 'create_es': True, 'list_en': True, 'list_es': True, 'patch_en': True, 'patch_es': True, 'delete_en': True, 'delete_es': True}
- note: System prompt exige JSON único; consistencia medida contra Groq real.
- call1: {'transcription': 'add buy groceries to my list', 'http_status': 200, 'latency_ms': 30764.6}
- call2: {'transcription': 'añade comprar leche a mi lista', 'http_status': 200, 'latency_ms': 287.4}
- call3: {'transcription': 'Please add buy groceries to my list', 'http_status': 200, 'latency_ms': 350.7}
- call4: {'transcription': 'could you show my tasks', 'http_status': 200, 'latency_ms': 254.1}
- call5: {'transcription': 'lista mis tareas', 'http_status': 200, 'latency_ms': 309.8}
- call6: {'transcription': 'mark task 1 as done', 'http_status': 200, 'latency_ms': 391.2}
- call7: {'transcription': 'marca la tarea 1 como hecha', 'http_status': 200, 'latency_ms': 324.2}
- call8: {'transcription': 'delete task 1', 'http_status': 200, 'latency_ms': 254.5}
- call9: {'transcription': 'elimina la tarea 1', 'http_status': 200, 'latency_ms': 384.5}

## R24: PASS
- command: POST /transcribe multipart with gTTS→ffmpeg wav; Whisper whisper-large-v3-turbo
- timestamp_cst: 2026-11-06 08:38:44 CST
- tts: gTTS 2.5.4 → mp3 → ffmpeg 16kHz mono wav
- transcription_model: whisper-large-v3-turbo
- note: Audio TTS sintético generado en la caja. No es micrófono (R25 sigue HITL_MIGUEL).
- call1: {'file': 'add_buy_groceries.wav', 'language': 'en', 'http_status': 200, 'latency_ms': 3604.9, 'expect_substr': 'groceries', 'transcription': 'Add buy groceries to my list.', 'contains_expect': True}
- call2: {'file': 'show_my_tasks.wav', 'language': 'en', 'http_status': 200, 'latency_ms': 7280.6, 'expect_substr': 'task', 'transcription': 'Show my tasks', 'contains_expect': True}
- call3: {'file': 'delete_task_1.wav', 'language': 'en', 'http_status': 200, 'latency_ms': 6631.5, 'expect_substr': 'delete', 'transcription': 'Delete Task 1.', 'contains_expect': True}

## R25: HITL_MIGUEL
- note: Micrófono real / flujo hablado punta a punta. La VM no tiene dispositivo; queda para Miguel.
