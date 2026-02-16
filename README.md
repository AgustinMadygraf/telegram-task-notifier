# Telegram Task Notifier MVP

MVP local con FastAPI + Telegram webhook expuesto por ngrok.

## Requisitos

- Python 3.10+ (recomendado 3.11+)
- `uvicorn`, `fastapi`, `httpx`
- `ngrok` instalado y autenticado (`ngrok config add-authtoken ...`)

## Quickstart MVP (Windows)

1. Configura variables de entorno (podes copiar `.env.example` a `.env`):
   - `TELEGRAM_TOKEN` (obligatorio)
   - `TELEGRAM_WEBHOOK_SECRET` (opcional, recomendado)
   - `DROP_PENDING_UPDATES` (opcional, default `true`)
   - Nota: `main.py` y los scripts cargan `.env` automaticamente si existe.

2. Levanta el servidor:
   - `scripts\run_server.bat`

3. En otra terminal, levanta ngrok:
   - `scripts\run_ngrok.bat`

4. En otra terminal, configura el webhook:
   - `scripts\setup_webhook.bat`
   - Esto detecta la URL HTTPS de ngrok y configura Telegram en:
     - `https://<ngrok>/telegram/webhook`

5. Mandale `hola` al bot en Telegram.

6. Verifica que el backend capturo `chat_id`:
   - `curl http://127.0.0.1:8000/telegram/last_chat`
   - Esperado: `last_chat_id` distinto de `null`.

7. Dispara una tarea de ejemplo:
   - PowerShell:
     - `Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/tasks/start -ContentType 'application/json' -Body '{"duration_seconds":2,"force_fail":false}'`
   - CMD:
     - `curl -X POST http://127.0.0.1:8000/tasks/start -H "Content-Type: application/json" -d "{\"duration_seconds\":2,\"force_fail\":false}"`
   - Esperado: el bot envia `Termin\u00e9`.
   - Para simular error: `force_fail=true` y espera `Fall\u00f3`.

## Endpoints

- `POST /telegram/webhook`
  - Recibe updates de Telegram y guarda `last_chat_id`.
  - Si `TELEGRAM_WEBHOOK_SECRET` esta configurado, valida `X-Telegram-Bot-Api-Secret-Token`.

- `GET /telegram/last_chat`
  - Debug de `last_chat_id`.
  - Se persiste en `.last_chat_id` para no perderse al reiniciar el server.

- `POST /tasks/start`
  - Lanza tarea en background y notifica resultado al ultimo chat capturado.
  - Body ejemplo:
    - `{"duration_seconds": 2, "force_fail": false}`

## Scripts

- `python scripts/get_ngrok_url.py`
  - Obtiene la URL publica HTTPS desde `http://127.0.0.1:4040/api/tunnels`.

- `python scripts/set_telegram_webhook.py`
  - Configura webhook usando `WEBHOOK_URL` o ngrok local.
  - Imprime `getWebhookInfo`.

- `python scripts/dev_setup_webhook.py`
  - Orquesta setup de desarrollo y deja pasos de prueba.
