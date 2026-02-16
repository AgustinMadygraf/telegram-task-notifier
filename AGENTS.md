# AGENTS

## Ejecucion base
- Inicia la app con `python run.py` (o `scripts\run_server.bat`).
- `run.py` levanta FastAPI, ngrok y configura webhook automaticamente si esta habilitado.

## Notificacion tras Codex CLI
- Flujo recomendado (wrapper):
  - `python scripts/run_codex_and_notify.py --commit-proposal "feat: mensaje de commit" -- codex`
- Ese script:
  - Ejecuta Codex CLI.
  - Mide tiempo real de ejecucion.
  - Detecta nombre del repo.
  - Hace `curl` a `POST /tasks/start` con `commit_proposal`, `repository_name` y `execution_time_seconds`.

## Notificacion manual
- Si Codex ya corrio, podes notificar manualmente:
  - `python scripts/notify_task.py --commit-proposal "feat: mensaje de commit" --execution-time-seconds 42.5`

## Config relevante
- `TASKS_START_URL` (default: `http://127.0.0.1:8000/tasks/start`)
- `REPOSITORY_NAME`
- `TELEGRAM_CHAT_ID` (fallback de chat)
- `TELEGRAM_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
