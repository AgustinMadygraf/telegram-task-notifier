# Datamaq Communications API

MVP local con FastAPI + Telegram webhook expuesto por ngrok, todo iniciado desde `run.py`.

Incluye endpoints de contacto/email (`POST /contact`, `POST /mail`) con respuesta `202`, `request_id`, anti-spam (`rate-limit` + `honeypot`) y CORS estricto por entorno.

## Requisitos

- Python 3.10+ (recomendado 3.11+)
- `uvicorn`, `fastapi`, `httpx`, `pyngrok`
- ngrok autenticado (opcionalmente por `NGROK_AUTHTOKEN` en `.env`)
- Instalacion sugerida:
  - `pip install uvicorn fastapi httpx pyngrok`

## Quickstart (Windows)

1. Configura variables de entorno (podes copiar `.env.example` a `.env`):
  - `APP_ENV` (obligatorio; `development|staging|production|test`)
  - `CORS_ALLOWED_ORIGINS` (obligatorio; lista separada por comas)
  - `SMTP_HOST` (obligatorio)
  - `SMTP_PORT` (obligatorio; entero > 0)
  - `SMTP_USER` (opcional)
  - `SMTP_PASS` (opcional)
  - `SMTP_TLS` (opcional; default `true`)
  - `SMTP_FROM` (obligatorio)
  - `SMTP_TO_DEFAULT` (obligatorio)
  - `RATE_LIMIT_WINDOW` (obligatorio; entero > 0)
  - `RATE_LIMIT_MAX` (obligatorio; entero > 0)
  - `HONEYPOT_FIELD` (obligatorio; default `website`)
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
     - `Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/tasks/start -ContentType 'application/json' -Body '{"duration_seconds":2,"force_fail":false,"modified_files_count":2}'`
   - CMD:
      - `curl -X POST http://127.0.0.1:8000/tasks/start -H "Content-Type: application/json" -d "{\"duration_seconds\":2,\"force_fail\":false,\"modified_files_count\":2}"`

5. Prueba endpoint de contacto (respuesta esperada: `202`):
   - PowerShell:
     - `Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/contact -ContentType 'application/json' -Body '{"name":"Juan Pérez","email":"juan@empresa.com","message":"Necesito una demo","meta":{"source":"landing"},"attribution":{"website":""}}'`

6. Prueba endpoint de mail (respuesta esperada: `202`):
   - PowerShell:
     - `Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/mail -ContentType 'application/json' -Body '{"name":"María Gómez","email":"maria@cliente.com","message":"Quiero recibir información","meta":{"source":"footer-form"},"attribution":{"website":""}}'`

7. (Opcional) Notificar automaticamente luego de usar Codex CLI:
   - `python scripts/run_codex_and_notify.py -- codex`
   - Este wrapper ejecuta Codex y envia `curl` a `/tasks/start` por iteracion (sin esperar al fin de sesion) solo si hubo cambios reales de contenido en archivos del working tree (hash antes/despues), con:
     - `modified_files_count`
     - `repository_name`
     - `execution_time_seconds`
   - No notifica por fin de sesion; notifica cuando detecta cambios y estabilidad de iteracion.
   - Si falla lectura de git status, se puede elegir comportamiento:
     - `python scripts/run_codex_and_notify.py --on-git-error notify -- codex` (default)
     - `python scripts/run_codex_and_notify.py --on-git-error skip -- codex`
   - `--dry-run-notify` solo imprime el curl y no envia notificacion real a Telegram.
   - Prueba real minima:
     - `python scripts/run_codex_and_notify.py --always-notify -- python -c "print('codex simulado')"`
   - Canal soportado por este flujo: Telegram (no WhatsApp).

## Endpoints

- `POST /contact`
  - Recibe payload compatible con frontend Vue (`name`, `email`, `message`, `meta`, `attribution`).
  - Responde `202 Accepted` con `{ request_id, status, message }`.
  - Aplica anti-spam con honeypot (`HONEYPOT_FIELD`) y rate-limit (`RATE_LIMIT_WINDOW`, `RATE_LIMIT_MAX`).
  - Error uniforme: `{ request_id, error: { code, message } }` con `400/422/429/500`.
  - CORS expone métodos `POST` y `OPTIONS`.

- `POST /mail`
  - Mismo contrato de request/response que `POST /contact`.
  - Flujo de envío por SMTP (`SMTP_*`) en background.
  - SMTP soporta modo con auth (`SMTP_USER` y `SMTP_PASS`) o sin auth (ambos vacíos).

- `POST /telegram/webhook`
  - Recibe updates de Telegram y guarda `last_chat_id`.
  - Si `TELEGRAM_WEBHOOK_SECRET` esta configurado, valida `X-Telegram-Bot-Api-Secret-Token`.

- `GET /telegram/last_chat`
  - Debug de `last_chat_id`.
  - Se persiste en `.last_chat_id` para no perderse al reiniciar el server.

- `POST /tasks/start`
  - Lanza tarea en background y notifica resultado al ultimo chat capturado.
  - Si no hay `last_chat_id`, usa `TELEGRAM_CHAT_ID` como fallback si esta configurado.
  - Notificacion incluye: estado, repositorio, tiempo de ejecucion y cantidad de archivos modificados.

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

Nota de escalabilidad anti-spam:

- El rate-limit actual es `in-memory`; en despliegues con múltiples workers/instancias migrar a backend compartido (ej. Redis).

## Ejecucion

- `run.py` levanta el servidor FastAPI en un hilo.
- Si `NGROK_ENABLED=true`, abre el tunel con `pyngrok`.
- Si `AUTO_SET_WEBHOOK=true`, configura webhook de Telegram automaticamente.
- Al cerrar (Ctrl+C), intenta bajar server y ngrok ordenadamente.

## Scripts Python

- `python scripts/run_codex_and_notify.py -- codex`
  - Ejecuta Codex CLI y notifica automaticamente a `/tasks/start` por iteracion estable si detecta cambios de archivos en el working tree.
  - `--dry-run-notify` simula la notificacion (no envio real).
  - `--on-git-error notify|skip` define que hacer si falla `git status`.

- `python scripts/notify_task.py --modified-files-count 2 --execution-time-seconds 42.5`
  - Envia notificacion manual via `curl` a `/tasks/start`.

## Deploy VPS (Docker + Nginx)

Objetivo de produccion:

- API: `https://api.datamaq.com.ar`
- Webhook Telegram: `https://api.datamaq.com.ar/telegram/webhook`
- Contacto: `https://api.datamaq.com.ar/contact`
- Mail: `https://api.datamaq.com.ar/mail`

Archivos incluidos para despliegue:

- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env.production.example`
- `deploy/nginx/api.datamaq.com.ar.conf`

Pasos rapidos en VPS:

1. Copiar variables de produccion:
   - `cp .env.production.example .env`
  - Completar `TELEGRAM_TOKEN`, `TELEGRAM_WEBHOOK_SECRET` y variables `SMTP_*`.
2. Levantar contenedor:
   - `docker compose up -d --build`
3. Validar API local:
   - `curl http://127.0.0.1:8000/telegram/last_chat`
4. Instalar bloque Nginx y recargar:
   - `nginx -t`
   - `systemctl reload nginx`
5. Emitir SSL:
   - `certbot --nginx -d api.datamaq.com.ar`
6. Configurar webhook en Telegram (`setWebhook`) con `secret_token`.

Documentacion operativa relacionada:

- `docs/deploy-fastapi-telegram-vps.md`
- `docs/github-actions-fastapi-vps.md`
