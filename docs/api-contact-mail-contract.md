# Contrato API: `POST /contact` y `POST /mail`

Fecha: 2026-02-18  
Estado: Propuesto para implementación

## Objetivo

Definir el contrato final para migrar frontend Vue hacia endpoints de contacto/email, preservando compatibilidad del backend Telegram/tasks existente.

## Endpoints

- `POST /contact`
- `POST /mail`

Ambos endpoints aceptan el mismo request para compatibilidad con frontend actual.

## Request (compat Vue)

### JSON schema (conceptual)

- `name` (string, requerido, 1..120)
- `email` (string, requerido, formato email, 5..254)
- `message` (string, requerido, 1..5000)
- `meta` (object, opcional)
  - `source` (string, opcional)
  - `campaign` (string, opcional)
  - `locale` (string, opcional)
  - `ip` (string, opcional; preferible inferir del servidor)
- `attribution` (object, opcional)
  - `path` (string, opcional)
  - `referrer` (string, opcional)
  - `user_agent` (string, opcional)
  - `{HONEYPOT_FIELD}` (string, opcional, debe venir vacío)

> Nota: `{HONEYPOT_FIELD}` se reemplaza por el valor de entorno `HONEYPOT_FIELD` (ejemplo: `website`).

### Ejemplo request `POST /contact`

```json
{
  "name": "Juan Pérez",
  "email": "juan@empresa.com",
  "message": "Necesito una demo del producto.",
  "meta": {
    "source": "landing",
    "campaign": "q1-2026",
    "locale": "es-AR"
  },
  "attribution": {
    "path": "/contacto",
    "referrer": "https://google.com",
    "user_agent": "Mozilla/5.0",
    "website": ""
  }
}
```

### Ejemplo request `POST /mail`

```json
{
  "name": "María Gómez",
  "email": "maria@cliente.com",
  "message": "Quiero recibir información comercial.",
  "meta": {
    "source": "footer-form",
    "campaign": "always-on",
    "locale": "es-AR"
  },
  "attribution": {
    "path": "/",
    "referrer": "https://datamaq.com.ar",
    "user_agent": "Mozilla/5.0",
    "website": ""
  }
}
```

## Response estándar

### Éxito (`202 Accepted`)

- `request_id` (UUID string)
- `status` (`accepted`)
- `message` (string)

#### Ejemplo éxito (`POST /contact`)

```json
{
  "request_id": "0f2df63f-4131-4ed0-8ef5-0a443f6ef6cf",
  "status": "accepted",
  "message": "Contact request accepted for processing"
}
```

#### Ejemplo éxito (`POST /mail`)

```json
{
  "request_id": "f8bc6f3e-8f8d-45ff-8b3f-0cdb0d37f9bb",
  "status": "accepted",
  "message": "Mail request accepted for processing"
}
```

## Tabla de errores

| HTTP | code                    | Cuándo aplica                                                                 |
|------|-------------------------|-------------------------------------------------------------------------------|
| 400  | `BAD_REQUEST`           | Payload semánticamente inválido (ej. honeypot no vacío, reglas de negocio). |
| 422  | `VALIDATION_ERROR`      | Estructura/tipos inválidos o campos requeridos ausentes.                     |
| 429  | `RATE_LIMIT_EXCEEDED`   | Excede límite por ventana (`RATE_LIMIT_WINDOW` / `RATE_LIMIT_MAX`).          |
| 500  | `INTERNAL_ERROR`        | Error inesperado del sistema.                                                 |

### Formato estándar de error

```json
{
  "request_id": "bca6b67e-e277-4f80-93a0-a8a8145d150d",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests"
  }
}
```

## Decisión técnica comparada y recomendación

### `200` síncrono vs `202 Accepted`

- `200` síncrono:
  - Ventaja: modelo más simple.
  - Desventaja: acopla request HTTP a SMTP, más latencia y riesgo de timeout.
- `202 Accepted` (elegida):
  - Ventaja: respuesta rápida, desacople de envío, mejor resiliencia y escalado.
  - Trade-off: requiere trazabilidad (`request_id`) y pipeline de procesamiento.

### Anti-spam

- Solo `rate-limit`: limita volumen pero no bots de baja frecuencia.
- Solo `honeypot`: frena bots básicos, insuficiente ante bots avanzados.
- **Recomendación final:** ambos (`rate-limit` + `honeypot`).

### CORS estricto

- Producción: lista explícita de orígenes permitidos (sin wildcard).
- Desarrollo: permitir `http://localhost:5173` y `http://127.0.0.1:5173` (u origen de dev acordado).

## Diseño por capas (Arquitectura Limpia + SOLID)

### Domain

- Entidades/VOs:
  - `ContactMessage`
  - `EmailAddress`
  - `AttributionData`

Responsabilidad: invariantes y reglas puras del dominio.

### Application

- Casos de uso:
  - `SubmitContactUseCase`
  - `SendMailUseCase`
- Puertos:
  - `MailGateway`
  - `RateLimiterGateway`
  - `RequestIdProvider`

Responsabilidad: orquestación de casos de uso sin dependencia de frameworks.

### Infrastructure

- Adapters:
  - `SmtpMailGateway` (SMTP)
  - Implementación de rate-limit (in-memory/redis según entorno)

Responsabilidad: integración con servicios externos.

### Interface

- Routers FastAPI:
  - `POST /contact`
  - `POST /mail`
- DTOs/schemas para request/response.

Responsabilidad: traducción HTTP <-> application.

### Compatibilidad Telegram

- Mantener sin cambios:
  - `POST /telegram/webhook`
  - `GET /telegram/last_chat`
  - `POST /tasks/start`

## Variables de entorno propuestas

- SMTP:
  - `SMTP_HOST`
  - `SMTP_PORT`
  - `SMTP_USER`
  - `SMTP_PASS`
  - `SMTP_TLS`
  - `SMTP_FROM`
  - `SMTP_TO_DEFAULT`
- Seguridad/HTTP:
  - `CORS_ALLOWED_ORIGINS`
  - `APP_ENV`
- Anti-spam:
  - `RATE_LIMIT_WINDOW`
  - `RATE_LIMIT_MAX`
  - `HONEYPOT_FIELD`

## Plan de implementación en 4 etapas (sin código)

### Etapa 1 — Contrato y decisiones

- Congelar contrato request/response para `/contact` y `/mail`.
- Aprobar ADR y semántica `202`.
- Alinear naming con frontend Vue para evitar breaking changes.

### Etapa 2 — Núcleo application/domain

- Introducir entidades/VOs de contacto en domain.
- Crear casos de uso y puertos en application.
- Definir errores de negocio y mapeo estándar de errores.

### Etapa 3 — Infraestructura e interface

- Implementar adapter SMTP.
- Implementar anti-spam (`rate-limit` + honeypot).
- Exponer routers FastAPI nuevos con CORS estricto por entorno.

### Etapa 4 — Hardening y rollout

- Agregar tests de contrato e integración.
- Instrumentar logs/correlación por `request_id`.
- Desplegar gradual y validar migración del frontend Vue.
