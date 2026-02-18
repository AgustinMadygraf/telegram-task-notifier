# Runbook CODEX CLI (acceso a VPS + GitHub)

Fecha: 2026-02-18  
Proyecto: **datamaq-communications-api**

## Objetivo

Guía operativa para que CODEX CLI ejecute cambios y validaciones end-to-end sobre:

- Repositorio GitHub (renombrado)
- VPS productivo
- Deploy Docker Compose + Nginx
- Validaciones de API (`/telegram/*`, `/tasks/start`, `/contact`, `/mail`)

## Alcance y restricciones

1. No romper endpoints existentes:
   - `POST /telegram/webhook`
   - `GET /telegram/last_chat`
   - `POST /tasks/start`
2. Preservar seguridad:
   - No imprimir secretos completos en logs.
   - Enmascarar valores sensibles.
3. Usar cambios mínimos y reversibles.
4. Si falla deploy, recolectar evidencia y proponer rollback inmediato.

## Pre-requisitos

### Secrets en GitHub Actions

Verificar que existan y estén completos:

- `VPS_HOST`
- `VPS_PORT`
- `VPS_USER`
- `VPS_APP_DIR`
- `VPS_SSH_KEY`
- `VPS_KNOWN_HOSTS` (opcional)
- `GITHUB_DEPLOY_KEY` (opcional, recomendado si el VPS no tiene key propia para `git@github.com`)
- `SMTP_HOST`
- `SMTP_FROM`
- `SMTP_TO_DEFAULT`

### Variables críticas en runtime (startup checks)

- `SMTP_HOST`
- `SMTP_PORT` (> 0)
- `SMTP_FROM`
- `SMTP_TO_DEFAULT`
- `CORS_ALLOWED_ORIGINS`
- `RATE_LIMIT_WINDOW` (> 0)
- `RATE_LIMIT_MAX` (> 0)
- `HONEYPOT_FIELD`
- `APP_ENV` en `development|staging|production|test`

## Prompt recomendado para CODEX CLI

Copiar/pegar en CODEX CLI:

```text
Actúa como Staff DevOps + Backend Engineer.

Contexto:
- Repo: datamaq-communications-api
- Deploy: GitHub Actions -> VPS -> Docker Compose -> Nginx
- Dominio: https://api.datamaq.com.ar
- Endpoints legacy críticos: /telegram/webhook, /telegram/last_chat, /tasks/start
- Endpoints nuevos: POST /contact, POST /mail

Objetivo:
Dejar entorno productivo sano, validar rutas nuevas/legacy y entregar evidencia.

Instrucciones:
1) Validar repositorio remoto y ruta en VPS
   - detectar ruta real (VPS_APP_DIR)
   - git remote -v (apuntar a repo nuevo)
   - git fetch --all --prune
   - git checkout main
   - git pull --ff-only

2) Validar .env en VPS
   - asegurar SMTP_HOST/SMTP_FROM/SMTP_TO_DEFAULT no vacíos
   - no imprimir secretos completos

3) Deploy
   - docker compose up -d --build
   - docker compose ps
   - si falla: docker compose logs --tail=300 api

4) Smoke tests (prod)
   - GET https://api.datamaq.com.ar/telegram/last_chat -> 200
   - OPTIONS https://api.datamaq.com.ar/contact con Origin=https://datamaq.com.ar y ACRM=POST -> 200
   - POST https://api.datamaq.com.ar/contact payload válido -> 202
   - POST https://api.datamaq.com.ar/mail payload válido -> 202

5) Anti-spam
   - honeypot lleno -> 400
   - rate-limit (2 requests seguidos, según ventana/config) -> 429

6) Si /contact o /mail devuelven 404
   - diagnosticar Nginx upstream / despliegue de contenedor
   - validar nginx -t y recargar si aplica
   - reintentar smoke tests

7) Reporte final
   - ruta final en VPS
   - commit desplegado
   - estado contenedores
   - resultados HTTP (status + body breve)
   - riesgos y próximos pasos
```

## Comandos de referencia (VPS)

> Ejecutar con usuario deploy correspondiente.

```bash
cd "$VPS_APP_DIR"
git remote -v
git fetch --all --prune
git checkout main
git pull --ff-only

[ -f .env ] || cp .env.production.example .env

docker compose up -d --build
docker compose ps
docker compose logs --tail=200 api
```

## Comandos de validación HTTP (producción)

### Legacy

```bash
curl -i https://api.datamaq.com.ar/telegram/last_chat
```

### CORS preflight

```bash
curl -i -X OPTIONS https://api.datamaq.com.ar/contact \
  -H "Origin: https://datamaq.com.ar" \
  -H "Access-Control-Request-Method: POST"
```

### Contact 202

```bash
curl -i -X POST https://api.datamaq.com.ar/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Juan Perez",
    "email":"juan@empresa.com",
    "message":"Necesito una demo",
    "meta":{"source":"landing"},
    "attribution":{"website":""}
  }'
```

### Mail 202

```bash
curl -i -X POST https://api.datamaq.com.ar/mail \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Maria Gomez",
    "email":"maria@cliente.com",
    "message":"Quiero recibir información",
    "meta":{"source":"footer-form"},
    "attribution":{"website":""}
  }'
```

### Honeypot 400

```bash
curl -i -X POST https://api.datamaq.com.ar/contact \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Bot",
    "email":"bot@spam.com",
    "message":"spam",
    "meta":{},
    "attribution":{"website":"filled-by-bot"}
  }'
```

### Rate-limit 429 (si RATE_LIMIT_MAX=1 o bajo)

```bash
curl -i -X POST https://api.datamaq.com.ar/contact -H "Content-Type: application/json" -d '{"name":"A","email":"a@a.com","message":"ok","meta":{},"attribution":{"website":""}}'
curl -i -X POST https://api.datamaq.com.ar/contact -H "Content-Type: application/json" -d '{"name":"A","email":"a@a.com","message":"ok","meta":{},"attribution":{"website":""}}'
```

## Diagnóstico rápido de fallas comunes

### 1) `RuntimeError: Missing or invalid critical settings: SMTP_*`

- Causa: faltan secretos SMTP en GitHub o `.env` incompleto en VPS.
- Acción:
  - cargar `SMTP_HOST`, `SMTP_FROM`, `SMTP_TO_DEFAULT` en GitHub Secrets.
  - rerun de workflow.

### 1.b) `Permission denied (publickey)` en `git pull` remoto

- Causa: el VPS no tiene identidad SSH válida para leer el repo en GitHub.
- Acción:
  - cargar `GITHUB_DEPLOY_KEY` en GitHub Secrets (private key con deploy key de lectura en el repo), o
  - configurar llave SSH del usuario de VPS con acceso al repo.
  - validar en VPS: `git ls-remote --heads origin`.

### 2) `404 /contact` o `404 /mail` en dominio real

- Causa probable: versión vieja corriendo o deploy no aplicado.
- Acción:
  - verificar commit en VPS
  - `docker compose up -d --build`
  - revisar logs de `api`

### 3) CORS preflight no responde 200

- Causa probable: config CORS no aplicada en contenedor en ejecución.
- Acción:
  - confirmar versión desplegada
  - revisar `CORS_ALLOWED_ORIGINS` en `.env`
  - redeploy

## Criterio de éxito

Checklist final esperado:

- [ ] Workflow CI verde
- [ ] Deploy verde
- [ ] `GET /telegram/last_chat` -> `200`
- [ ] `OPTIONS /contact` origin `https://datamaq.com.ar` -> `200`
- [ ] `POST /contact` -> `202`
- [ ] `POST /mail` -> `202`
- [ ] Honeypot -> `400`
- [ ] Rate-limit -> `429` (según configuración)

## Rollback mínimo

Si el deploy queda inestable:

1. Volver al commit/tag anterior en VPS.
2. `docker compose up -d --build`.
3. Confirmar healthcheck legacy (`/telegram/last_chat`).
4. Documentar incidente y diferencia de configuración.
