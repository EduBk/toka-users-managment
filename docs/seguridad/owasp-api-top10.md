# Revisión OWASP API Security Top 10 (2023) - E2.11

Revisión de los servicios implementados (`auth`, `user`, `role`, `audit`, `ai`) frente a
[OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/).

## Resumen por riesgo

| Riesgo | Estado | Controles aplicados / riesgo residual |
|---|---|---|
| API1 Broken Object Level Authorization | Mitigado | Ningún endpoint devuelve recursos "del usuario actual" por id del cliente sin authz: `GET/PATCH/DELETE /users/{id}` exige scope `users:read`/`users:write`; `POST /users/{id}/roles` y `DELETE /users/{id}/roles/{role_id}` exigen rol `admin`; `GET /audit` exige `auditor`/`admin`. Los ids son UUID v4 (no enumerables). |
| API2 Broken Authentication | Mitigado | JWT RS256 con `iss`, `aud`, `exp`, `jti` y `token_type` obligatorios; access token de 15 min; refresh rotado y revocado en Redis; logout revoca ambos `jti`. bcrypt para contraseñas (límite 72 bytes). **Rate limiting** por IP en `/auth/login`, `/auth/register` y `/auth/refresh` (E2.11). Errores de login genéricos (`invalid_credentials`) sin distinguir email inexistente de contraseña incorrecta. |
| API3 Broken Object Property Level Authorization | Mitigado | Schemas Pydantic de respuesta explícitos: `AccountResponse` nunca expone `password_hash`; `UserUpdateRequest` no acepta `status` ni `id` (mass assignment imposible: solo `email`, `name`, `profile`). |
| API4 Unrestricted Resource Consumption | Mitigado parcialmente | `page_size` ≤ 100 en `/users` y `/audit`; longitudes máximas en todos los strings de entrada (`email` 254, `name` 120, `role.name` 60, filtros de auditoría 254/120). Rate limiting en auth y en IA (`ai:ask` por `sub`, 20/min; `top_k` ≤ 20, `question` ≤ 2000, historial ≤ 6 mensajes, `max_tokens` 800). Residual: `profile` es JSON libre sin límite de tamaño propio (lo acota el límite de cuerpo del proxy Nginx de E3.8). |
| API5 Broken Function Level Authorization | Mitigado | Authz server-side con `require_scopes` / `require_roles` de `app_common.jwt_auth`; escrituras de roles solo `admin`; `GET /auth/accounts` (E2.13) solo `admin`; `POST /ai/reindex` y `GET /ai/metrics` solo `admin`; `POST /ai/ask` exige `ai:use`. La UI (E3.x) solo oculta, nunca autoriza. |
| API6 Unrestricted Access to Sensitive Business Flows | Mitigado parcialmente | Registro y login limitados por IP. Residual: no hay CAPTCHA ni bloqueo por cuenta (fuera del alcance de la prueba). |
| API7 Server Side Request Forgery | No aplica | Ningún endpoint acepta URLs del cliente. Las URLs salientes (`JWKS_URL`, `ROLE_SERVICE_URL`) vienen de variables de entorno. |
| API8 Security Misconfiguration | Mitigado | Errores con esquema uniforme `{code, message, details}`; 500 genérico sin stack trace ni mensaje interno; los 422 **no reflejan el valor enviado** (`input` eliminado: podía contener contraseñas). `/docs`, `/redoc` y `/openapi.json` desactivados con `ENVIRONMENT=production`. APIs sin puerto publicado al host; Redis y AMQP solo en `backend-net`. Contenedores no-root con código de solo lectura (ver abajo). |
| API9 Improper Inventory Management | Mitigado | Inventario de endpoints en `docs/ejecucion.md` y OpenAPI por servicio en entornos no productivos. No quedan endpoints de negocio sin JWT: desde E2.14, `GET /users/{id}/roles` y `/permissions` de `role-service` exigen scope `roles:read`; `auth-service` usa un token de servicio de 60 s. |
| API10 Unsafe Consumption of APIs | Mitigado | `auth-service` consume `role-service` con timeout (`ROLE_SERVICE_TIMEOUT_SECONDS`) y falla cerrado en privilegios (claims vacíos). Los eventos consumidos se validan como `EventEnvelope` y los inválidos van a DLQ. `ai-service` llama a OpenAI con timeout, reintentos acotados y backoff (429/5xx), y a `user-service`/`role-service` con timeout y token del usuario. |

## Validación y sanitización de entradas

- Toda entrada HTTP pasa por Pydantic (tipos, longitudes, `ge`/`le`) y después por
  los value objects del dominio (`Email`, `UserName`, `RoleName`, `PermissionName`,
  `EventType`...), que normalizan y rechazan valores inválidos con 400.
- Los ids de ruta se tipan como `UUID` (422 si no lo son).
- Persistencia solo con consultas parametrizadas (SQLAlchemy Core/ORM, filtros MongoDB
  construidos como diccionarios con valores, nunca concatenando strings).
- El `X-Request-ID` entrante se acepta solo si cumple `^[A-Za-z0-9._-]{8,64}$`.
- No hay renderizado HTML en el backend (sin superficie XSS server-side).

## Manejo de errores

- `AppError` y las excepciones de dominio se traducen a HTTP en el borde
  (`app_common.errors` y `api/errors.py` de cada servicio).
- Excepciones no controladas → `500 {"code": "internal_error", "message": "Unexpected error"}`;
  el traceback solo va al log JSON del servicio, correlacionado por `trace_id`.
- `429 rate_limited` incluye `Retry-After` y `details.retry_after_seconds`.
- Los logs no incluyen contraseñas, tokens ni IPs (`rate_limit_exceeded` solo registra
  el scope).

## Rate limiting

| Endpoint | Clave | Límite por defecto | Variables |
|---|---|---|---|
| `POST /auth/login` | `auth:login:<ip>` | 10 / 60 s | `AUTH_RATE_LIMIT_REQUESTS`, `AUTH_RATE_LIMIT_WINDOW_SECONDS` |
| `POST /auth/register` | `auth:register:<ip>` | 10 / 60 s | idem |
| `POST /auth/refresh` | `auth:refresh:<ip>` | 10 / 60 s | idem |
| `POST /ai/ask` | por usuario (`sub`) | E5.1/E5.5 | se define en E5.x |

- Implementación: `app_common.rate_limit` (ventana fija, `INCR` + `EXPIRE NX` en
  Redis, compartido entre réplicas). Sin `REDIS_URL` usa un contador en memoria por
  proceso. Si Redis falla, deja pasar la petición y registra `rate_limit_unavailable`
  (mismo criterio fail-open que la caché de E2.6).
- Detrás del proxy Nginx (E3.8) la IP real llega en `X-Forwarded-For`, que Nginx
  sobrescribe (no concatena) con `$remote_addr`, así que el cliente no puede falsearla.
  `auth-service` tiene `FORWARDED_ALLOW_IPS=*` (las APIs no se publican al host).
  Verificado: la clave en Redis lleva la IP del cliente, no la del contenedor Nginx.
- `client_max_body_size 64k` en Nginx acota el tamaño de cualquier body (413).

## Secretos

- Todos los secretos llegan por variables de entorno (`BaseServiceSettings`) o por
  ficheros montados de solo lectura (`/run/secrets/*.pem`).
- `.env.example` solo contiene `change-me` o valores vacíos (`OPENAI_API_KEY=`).
- `.env`, `*.pem` e `infra/keys/` están en `.gitignore` y en `services/.dockerignore`.
- `py scripts/scan_secrets.py` busca claves privadas, claves OpenAI/AWS, credenciales
  en URLs y asignaciones de contraseñas/secretos (excluye `tests/` y los placeholders
  `change-me`); sale con 1 si encuentra algo. Última ejecución: 0 hallazgos.

## Imágenes Docker

- Multi-stage: la etapa `builder` genera wheels (`pip wheel`); la final instala solo
  esos wheels con `--no-index` y los borra. Sin compiladores, `setuptools` ni
  dependencias de test en runtime.
- Base `python:3.12-slim`; usuario `appuser` (UID 10001); el código en `/app` es
  propiedad de `root` y no es escribible por el proceso.
- `services/.dockerignore` excluye `tests/`, cachés, `*.egg-info`, `.env` y `*.pem`.

## Riesgos residuales (para revisión)

- Sin bloqueo por cuenta ante fuerza bruta distribuida (solo límite por IP).
- La revocación de `jti` solo se comprueba en `auth-service` y `user-service`; el resto
  depende de la vida corta del access token (trade-off de E1.2).
- Cabeceras HTTP en el Nginx del frontend (E3.8): CSP `default-src 'self'`,
  `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: no-referrer`. Sin TLS ni HSTS:
  el stack local sirve HTTP; en un despliegue real TLS termina delante de este Nginx.
- `FORWARDED_ALLOW_IPS=*`: un contenedor comprometido dentro de la red Docker podría
  falsear su IP ante el rate limit. Alternativa: IP fija para `frontend` y confiar solo
  en ella.
- La vista de auditoría muestra el payload completo (incluye email y nombre) a los
  roles `auditor`/`admin`; es el dato que guarda `audit-service` (E2.9).
