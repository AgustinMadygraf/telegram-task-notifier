# GitHub Actions para FastAPI + Telegram en VPS

Fecha: 2026-02-17

## Objetivo

1. Validar cambios en cada `push`/`pull_request`.
2. Desplegar a produccion por SSH al VPS desde `main`.

## Alcance

1. `CI`: install, tests y build Docker.
2. `CD`: deploy por SSH solo en `main`.
3. Secretos de aplicacion quedan en el VPS (`.env`), no en Actions.

## Secrets de GitHub Actions

Configurar en `Settings > Secrets and variables > Actions`:

- `VPS_HOST`
- `VPS_PORT`
- `VPS_USER`
- `VPS_SSH_KEY`
- `VPS_APP_DIR`
- Opcional: `VPS_KNOWN_HOSTS`

## Workflow

Archivo: `.github/workflows/deploy-api.yml`

Comportamiento:

1. Job `ci`:
   - checkout
   - Python 3.11
   - install deps (si existe `requirements.txt`)
   - tests (si existe `tests/`)
   - `docker build`
2. Job `deploy`:
   - corre solo en `main`
   - usa `environment: production`
   - conecta por SSH al VPS
   - ejecuta:
     - `git pull --ff-only`
     - `docker compose up -d --build`
     - `docker compose ps`
     - health check local a `127.0.0.1:8000`

## Seguridad recomendada

1. No publicar `.env` en Actions.
2. Guardar secretos en Bitwarden y VPS.
3. Requerir aprobacion manual en `environment: production`.
4. Preferir usuario de deploy dedicado sobre `root`.

## Rollback

```bash
cd /opt/telegram-task-notifier
git log --oneline -n 5
git checkout <commit_anterior>
docker compose up -d --build
```

Validar:

```bash
curl -I https://api.datamaq.com.ar
curl -fsS http://127.0.0.1:8000/telegram/last_chat
```

## Checklist post-deploy

1. `https://api.datamaq.com.ar` responde sin error TLS.
2. `docker compose ps` muestra `api` en `Up`.
3. `nginx -t` sin errores (si hubo cambios de proxy).
4. `getWebhookInfo` sin `last_error_message`.
