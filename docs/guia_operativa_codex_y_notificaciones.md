# Guia operativa: Codex + notificaciones Telegram

Esta guia resume el flujo recomendado para trabajar con Codex CLI y asegurar notificaciones de tareas al canal de Telegram.

## 1. Levantar la app local

Inicia el servicio con:

```powershell
python run.py
```

Alternativa:

```powershell
scripts\run_server.bat
```

`run.py` levanta FastAPI, ngrok y webhook (si esta habilitado).

## 2. Ejecutar Codex con wrapper de notificaciones

Usa siempre:

```powershell
python scripts/run_codex_and_notify.py -- codex
```

Importante:

- La notificacion se emite por iteracion estable, no al final de toda la sesion.
- Solo notifica si detecta cambios reales de contenido en archivos.
- Cambios hechos fuera de ese proceso envuelto no disparan Telegram automaticamente.

## 3. Flags utiles

- `--idle-seconds`: tiempo sin cambios para cerrar iteracion.
- `--poll-interval-seconds`: frecuencia de deteccion.
- `--exclude-patterns`: patrones extra a excluir.
- `--on-git-error notify|skip`: comportamiento si falla `git status` (default `notify`).
- `--dry-run-notify`: imprime `curl` sin enviar POST real.
- `--debug-change-detection`: log detallado de deteccion.
- `--always-notify`: fuerza notificacion (ideal para pruebas).

## 4. Prueba minima de envio

```powershell
python scripts/run_codex_and_notify.py --always-notify -- python -c "print('codex simulado')"
```

Con diagnostico:

```powershell
python scripts/run_codex_and_notify.py --debug-change-detection --always-notify -- python -c "print('codex simulado')"
```

## 5. Checklist rapido si no llega Telegram

- App levantada (`python run.py`).
- `TELEGRAM_TOKEN` valido en `.env`.
- Chat capturado en `GET /telegram/last_chat` (`last_chat_id` no nulo) o `TELEGRAM_CHAT_ID` valido.
- No estar usando `--dry-run-notify` en prueba real.

## 6. Notificacion manual

Si Codex ya corrio:

```powershell
python scripts/notify_task.py --modified-files-count 2 --execution-time-seconds 42.5
```

Evita enviar valores negativos en tiempos o conteos.

## 7. Variables relevantes

- `TASKS_START_URL` (default `http://127.0.0.1:8000/tasks/start`)
- `REPOSITORY_NAME`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
