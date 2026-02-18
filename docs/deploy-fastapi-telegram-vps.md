# Deploy FastAPI Telegram en VPS (`api.datamaq.com.ar`)

Fecha: 2026-02-17

## Objetivo

- API publica: `https://api.datamaq.com.ar`
- Webhook Telegram: `https://api.datamaq.com.ar/telegram/webhook`

## Supuestos

1. El codigo vive en el VPS (ejemplo: `/opt/datamaq-communications-api`).
2. Nginx del host ya esta operativo.
3. El dominio `datamaq.com.ar` resuelve al VPS.

## 1) DNS

Crear registro `A`:

- Host: `api`
- Valor: `168.181.184.103`
- Recomendado durante puesta en marcha: `DNS only`.

Validacion:

```bash
nslookup api.datamaq.com.ar
```

## 2) Variables de entorno de produccion

Crear `.env` en el directorio del proyecto:

- `TELEGRAM_TOKEN` (obligatorio)
- `TELEGRAM_WEBHOOK_SECRET` (obligatorio recomendado)
- `TELEGRAM_CHAT_ID` (opcional fallback)
- `DROP_PENDING_UPDATES=true`
- `NGROK_ENABLED=false`
- `AUTO_SET_WEBHOOK=false`
- `SERVER_HOST=0.0.0.0`
- `SERVER_PORT=8000`

No versionar secretos. Gestionarlos en Bitwarden.

## 3) Docker

Artefactos requeridos en el repo:

- `Dockerfile`
- `docker-compose.yml`
- `requirements.txt`
- `.env.production.example`

Levantar:

```bash
docker compose up -d --build
```

Validar API local:

```bash
curl http://127.0.0.1:8000/telegram/last_chat
```

## 4) Nginx reverse proxy

Ejemplo: `deploy/nginx/api.datamaq.com.ar.conf`

Validar y recargar:

```bash
nginx -t
systemctl reload nginx
```

## 5) SSL con Certbot

```bash
certbot --nginx -d api.datamaq.com.ar
certbot certificates
curl -I https://api.datamaq.com.ar
```

## 6) Configurar webhook Telegram

```bash
curl -X POST "https://api.telegram.org/bot<TELEGRAM_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://api.datamaq.com.ar/telegram/webhook","secret_token":"<TELEGRAM_WEBHOOK_SECRET>","drop_pending_updates":true}'
```

Validacion:

```bash
curl "https://api.telegram.org/bot<TELEGRAM_TOKEN>/getWebhookInfo"
```

## 7) Smoke test

1. `curl -I https://api.datamaq.com.ar` sin error TLS.
2. `GET /telegram/last_chat` devuelve JSON.
3. `POST /tasks/start` genera notificacion Telegram.
4. `nginx -t` sin errores.

## 8) Operacion y rollback

Deploy:

```bash
cd /opt/datamaq-communications-api
git pull --ff-only
docker compose up -d --build
```

Logs:

```bash
docker compose logs -f api
journalctl -u nginx -f
```

Rollback:

1. Volver al commit/tag anterior.
2. `docker compose up -d --build`.
