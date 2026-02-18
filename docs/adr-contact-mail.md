# ADR-0001: Incorporar `POST /contact` y `POST /mail` con Arquitectura Limpia + SOLID

- Fecha: 2026-02-18
- Estado: Aprobada (propuesta)
- Decisores: Backend Team

## Contexto

La auditoría del backend confirmó que:

1. No existen endpoints `POST /contact` ni `POST /mail`.
2. No hay implementación SMTP.
3. El backend actual está orientado a Telegram/tasks y no debe romperse.

Se requiere habilitar formularios de contacto/email compatibles con frontend Vue actual, manteniendo estabilidad del flujo existente (`/telegram/*`, `/tasks/start`).

## Opciones evaluadas

### Opción A: Respuesta `200 OK` síncrona

- El endpoint valida y envía SMTP dentro del request.
- Devuelve éxito solo si SMTP completa en línea.

Pros:
- Implementación inicial simple.
- Semántica directa para clientes.

Contras:
- Acopla UX a latencia/fallas SMTP.
- Mayor riesgo de timeout.
- Dificulta escalado y retries controlados.

### Opción B: Respuesta `202 Accepted` asincrónica

- El endpoint valida, registra `request_id` y delega el envío.
- Devuelve aceptación inmediata.

Pros:
- Desacopla disponibilidad de SMTP del request HTTP.
- Mejor resiliencia ante picos y degradación parcial.
- Facilita retries y observabilidad por `request_id`.

Contras:
- Requiere diseño claro de estados y trazabilidad.

## Decisiones técnicas

1. **Semántica de respuesta:** elegir `202 Accepted` para `POST /contact` y `POST /mail`.
2. **Anti-spam:** aplicar enfoque combinado (`rate-limit` + `honeypot`).
3. **CORS:** política estricta por entorno:
   - Producción: dominios explícitos.
   - Desarrollo: `localhost`/`127.0.0.1` en puertos definidos.
4. **Compatibilidad:** no modificar comportamiento de endpoints Telegram/tasks existentes.

## Recomendación final

Adoptar Opción B (`202`) con anti-spam combinado y CORS estricto. Esta combinación minimiza impacto operativo y preserva la evolución del backend hacia un modelo más escalable sin romper compatibilidad.

## Consecuencias

- Se incorporan nuevas entidades/VOs en domain para contacto.
- Se agregan casos de uso y puertos de aplicación para envío de correo.
- Se implementa un adapter SMTP en infraestructura.
- Se añaden routers FastAPI nuevos (`/contact`, `/mail`) aislados del flujo Telegram.
- Se introduce trazabilidad estandarizada por `request_id`.

## Variables de entorno requeridas

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASS`
- `SMTP_TLS`
- `SMTP_FROM`
- `SMTP_TO_DEFAULT`
- `CORS_ALLOWED_ORIGINS`
- `RATE_LIMIT_WINDOW`
- `RATE_LIMIT_MAX`
- `HONEYPOT_FIELD`
- `APP_ENV`

## Alternativas descartadas

- Mantener solo Telegram como canal: no cumple requerimiento de migración frontend Vue.
- Implementar solo honeypot o solo rate-limit: cobertura anti-spam insuficiente frente a bots heterogéneos.
- CORS permisivo (`*`) en producción: riesgo de abuso y superficie innecesaria.
