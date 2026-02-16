# Telegram Task Notifier MVP

MVP local con FastAPI + Telegram webhook expuesto por ngrok, todo iniciado desde `run.py`.

## Requisitos

- Python 3.10+ (recomendado 3.11+)
- `uvicorn`, `fastapi`, `httpx`, `pyngrok`
- ngrok autenticado (opcionalmente por `NGROK_AUTHTOKEN` en `.env`)
- Instalacion sugerida:
  - `pip install uvicorn fastapi httpx pyngrok`

## Quickstart (Windows)

1. Configura variables de entorno (podes copiar `.env.example` a `.env`):
   - `TELEGRAM_TOKEN` (obligatorio)
   - `TELEGRAM_WEBHOOK_SECRET` (opcional, recomendado)
   - `TELEGRAM_CHAT_ID` (opcional; fallback para ejecutar `/tasks/start` sin depender del primer webhook)
   - `DROP_PENDING_UPDATES` (opcional, default `true`)
   - `REPOSITORY_NAME` (opcional; default nombre de carpeta del repo)
   - `SERVER_HOST` (opcional; default `0.0.0.0`)
   - `SERVER_PORT` (opcional; default `8000`)
   - `NGROK_ENABLED` (opcional; default `true`)
   - `NGROK_AUTHTOKEN` (opcional)
   - `NGROK_DOMAIN` (opcional; para dominio reservado)
   - `AUTO_SET_WEBHOOK` (opcional; default `true`)
   - `TELEGRAM_WEBHOOK_PATH` (opcional; default `/telegram/webhook`)
   - `TASKS_START_URL` (opcional; default `http://127.0.0.1:8000/tasks/start`)

2. Inicia todo desde un solo comando:
   - `scripts\run_server.bat`
   - o `python run.py`

3. Verifica el estado de chat:
   - `curl http://127.0.0.1:8000/telegram/last_chat`

4. Dispara una tarea de ejemplo:
   - PowerShell:
     - `Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/tasks/start -ContentType 'application/json' -Body '{"duration_seconds":2,"force_fail":false,"commit_proposal":"feat: notificar tiempo y resumen por telegram"}'`
   - CMD:
      - `curl -X POST http://127.0.0.1:8000/tasks/start -H "Content-Type: application/json" -d "{\"duration_seconds\":2,\"force_fail\":false,\"commit_proposal\":\"feat: notificar tiempo y resumen por telegram\"}"`

5. (Opcional) Notificar automaticamente luego de usar Codex CLI:
   - `python scripts/run_codex_and_notify.py --commit-proposal "feat: resumen de cambios" -- codex`
   - Este wrapper ejecuta Codex, mide el tiempo real y envia `curl` a `/tasks/start` solo si hubo cambios de archivos en la iteracion (detectado con `git status --porcelain`), con:
     - `commit_proposal`
     - `repository_name`
     - `execution_time_seconds`
   - Para forzar envio aunque no haya cambios:
     - `python scripts/run_codex_and_notify.py --always-notify --commit-proposal "feat: resumen de cambios" -- codex`

## Endpoints

- `POST /telegram/webhook`
  - Recibe updates de Telegram y guarda `last_chat_id`.
  - Si `TELEGRAM_WEBHOOK_SECRET` esta configurado, valida `X-Telegram-Bot-Api-Secret-Token`.

- `GET /telegram/last_chat`
  - Debug de `last_chat_id`.
  - Se persiste en `.last_chat_id` para no perderse al reiniciar el server.

- `POST /tasks/start`
  - Lanza tarea en background y notifica resultado al ultimo chat capturado.
  - Si no hay `last_chat_id`, usa `TELEGRAM_CHAT_ID` como fallback si esta configurado.
  - Notificacion incluye: estado, repositorio, tiempo de ejecucion y propuesta de commit.

## Arquitectura

Estructura de arquitectura limpia:

- `src/entities/`
- `src/use_cases/`
- `src/interface_adapters/presenters/`
- `src/interface_adapters/gateways/`
- `src/interface_adapters/controllers/`
- `src/shared/logger.py`
- `src/shared/config.py`
- `src/infrastructure/httpx/`
- `src/infrastructure/fastapi/`
- `src/infrastructure/pyngrok/`

## Ejecucion

- `run.py` levanta el servidor FastAPI en un hilo.
- Si `NGROK_ENABLED=true`, abre el tunel con `pyngrok`.
- Si `AUTO_SET_WEBHOOK=true`, configura webhook de Telegram automaticamente.
- Al cerrar (Ctrl+C), intenta bajar server y ngrok ordenadamente.

## Scripts Python

- `python scripts/run_codex_and_notify.py --commit-proposal "feat: resumen de cambios" -- codex`
  - Ejecuta Codex CLI y al finalizar notifica automaticamente a `/tasks/start` si detecta cambios de archivos.

- `python scripts/notify_task.py --commit-proposal "feat: resumen de cambios" --execution-time-seconds 42.5`
  - Envia notificacion manual via `curl` a `/tasks/start`.
