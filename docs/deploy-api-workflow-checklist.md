# Deploy Workflow Checklist (`deploy-api.yml`)

Fecha: 2026-02-19

Objetivo: validar de forma repetible el flujo de GitHub Actions por etapas:

1. `build_tests`
2. `build_image`
3. `build_gate`
4. `deploy_prepare`
5. `deploy_apply`
6. `verify_local`
7. `verify_public`
8. `deploy_gate`

## 1) Validacion local rapida (sin tocar VPS)

### 1.1 Contrato del workflow

```bash
PYTHONPATH=. pytest -q tests/test_deploy_artifacts.py
```

Debe pasar 100%. Este test valida DAG, triggers, `concurrency`, secretos SSH y checks de health/CORS/smoke.

### 1.2 Lint de GitHub Actions

```bash
docker run --rm -v "${PWD}:/repo" -w /repo rhysd/actionlint:latest
```

Debe terminar sin errores.

### 1.3 Suite completa

```bash
PYTHONPATH=. pytest -q
```

## 2) Simulacion local de jobs build con `act`

Prerequisito: tener Docker y `act` instalado.

### 2.1 `build_tests`

```bash
act pull_request -j build_tests
```

### 2.2 `build_image`

```bash
act pull_request -j build_image
```

`build_gate` no requiere prueba separada: depende de los dos jobs anteriores.

## 3) Simulacion local de `deploy_prepare` con `act`

Este job requiere contexto de `main` + secrets SMTP.

```bash
printf '{"ref":"refs/heads/main"}' > .github/act-main.json
act push -e .github/act-main.json -j deploy_prepare \
  -s SMTP_HOST=localhost \
  -s SMTP_FROM=no-reply@example.com \
  -s SMTP_TO_DEFAULT=ops@example.com
```

Esperado:

1. pasa preflight de secretos SMTP,
2. genera `datamaq-communications-api.tar.gz`,
3. publica artifact `deploy-workspace`.

Nota: `act` no cubre de forma confiable `deploy_apply`/`verify_*` porque dependen de SSH/VPS real y dominio publico.

## 4) Prueba real en GitHub Actions (recomendada para deploy)

### 4.1 Ejecutar workflow en rama feature

Accion esperada:

1. corren `build_tests` y `build_image` (en paralelo),
2. corre `build_gate`,
3. no debe correr deploy (porque no es `main`).

### 4.2 Ejecutar workflow en `main`

Accion esperada:

1. `build_tests` + `build_image` en paralelo,
2. `build_gate`,
3. `deploy_prepare`,
4. `deploy_apply`,
5. `verify_local` y `verify_public` en paralelo,
6. `deploy_gate`.

## 5) Checklist de salida por job

### `build_tests`

1. tests verdes
2. sin errores de import/sintaxis

### `build_image`

1. `docker build` exitoso
2. imagen `datamaq-communications-api:ci` creada

### `deploy_prepare`

1. preflight SMTP ok
2. artifact `deploy-workspace` disponible

### `deploy_apply`

1. upload por `scp` ok (con reintentos)
2. extract remoto ok
3. `.env` con `SMTP_HOST`, `SMTP_FROM`, `SMTP_TO_DEFAULT`
4. `docker compose up -d --build` ok

### `verify_local`

1. `http://127.0.0.1:8000/health` -> 200
2. OPTIONS local `/contact` -> 200/204
3. POST local `/contact` -> 202

### `verify_public`

1. `https://api.datamaq.com.ar/health` -> 200
2. OPTIONS publico `/contact` -> 200/204
3. POST publico `/contact` -> 202

### `deploy_gate`

1. confirma que `verify_local` y `verify_public` pasaron

## 6) Causas de falla frecuentes

1. `deploy_prepare` falla por secretos SMTP faltantes.
2. `deploy_apply` falla por host key/SSH key (`VPS_KNOWN_HOSTS`, `VPS_SSH_KEY`).
3. `verify_local` falla por contenedor `api` caido (`docker compose logs --tail=200 api`).
4. `verify_public` falla por DNS/TLS/Nginx/ruta de proxy.

## 7) Comandos de diagnostico rapido en VPS

```bash
cd "$VPS_APP_DIR"
docker compose ps
docker compose logs --tail=200 api
curl -i http://127.0.0.1:8000/health
curl -i -X OPTIONS http://127.0.0.1:8000/contact -H "Origin: https://datamaq.com.ar" -H "Access-Control-Request-Method: POST"
```
