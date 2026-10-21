# Ejecución del sistema

## Prerrequisitos

| Herramienta | Uso |
|---|---|
| Docker + Docker Compose v2 | Levantar todo el stack |
| Python 3.12 (`py` en Windows) | Scripts de `scripts/` y tests locales |
| `cryptography` (`py -m pip install cryptography`) | `scripts/generate_jwt_keys.py` |
| Node 22+ y npm 11 (opcional) | Desarrollo y tests del frontend fuera de Docker |

## Levantar el stack

```powershell
Copy-Item .env.example .env          # y reemplazar todos los `change-me`
py scripts/generate_jwt_keys.py      # crea infra/keys/jwt_private.pem y jwt_public.pem
docker compose up -d --build
docker compose ps                    # esperar a que todo esté `healthy`
```

El admin semilla se crea solo en el arranque (perfil `local`, ver abajo). Abrir
<http://localhost:3000> e iniciar sesión con `admin@example.com` / `Password2026!`.

- `.env` y `infra/keys/` no se versionan. `OPENAI_API_KEY` es necesaria para
  preguntar al agente (`/ai/ask`); el reindexado y el resto del sistema funcionan
  sin ella.
- Las migraciones Alembic se aplican al arrancar cada servicio con base relacional
  (`docker-entrypoint.sh`).

### Orden de arranque

Compose lo resuelve con `depends_on` + `healthcheck`:

1. Infraestructura: `postgres` (crea `auth_db`, `users_db`, `roles_db`), `mongodb`,
   `redis`, `rabbitmq`, `qdrant`.
2. `role-service` (catálogo de roles semilla: `admin`, `auditor`, `user`).
3. `auth-service` (consulta `role-service` al emitir tokens; si no responde, emite
   tokens sin roles).
4. `user-service`, `audit-service` y `ai-service` (validan JWT con el JWKS de
   `auth-service`; `ai-service` espera además a Qdrant y a Redis).
5. `frontend` (Nginx), cuando las cuatro APIs están `healthy`.

Puertos publicados al host: la UI en `3000` y, solo para desarrollo, PostgreSQL 5432,
MongoDB 27017, RabbitMQ management 15672 y Qdrant 6333. Las APIs no se publican; se
accede a ellas desde la red Docker o a través del proxy del frontend.

### Frontend en Docker

`frontend/Dockerfile` es multi-stage: compila con `node:20-alpine` (`npm ci` +
`npm run build`) y sirve `dist/` con `nginx:1.27-alpine`. La imagen final solo contiene
Nginx y los estáticos (~74 MB, sin Node ni `node_modules`).

La identidad de Toka vive en `frontend/public/` (`favicon.svg`, `logo-toka.svg`,
`site.webmanifest`) y en `src/components/Brand.tsx` (isotipo inline). Las tipografías
(Sora 600 e IBM Plex Sans variable) se sirven desde `/fonts/` en el mismo origen para no
abrir la CSP (`default-src 'self'`); Nginx las cachea 30 días.

- `VITE_API_URL` (por defecto `/api`, en `.env`) se inyecta como build arg: se fija al
  construir la imagen. Si cambia, `docker compose build frontend`.
- Proxy (`frontend/nginx/default.conf`), sin CORS porque UI y API comparten origen:

| Ruta pública | Servicio |
|---|---|
| `/api/auth/*` | `auth-service` |
| `/api/users/{id}/roles[/{role_id}]`, `/api/users/{id}/permissions` | `role-service` |
| `/api/users[/*]` (resto) | `user-service` |
| `/api/roles[/*]` | `role-service` |
| `/api/audit` | `audit-service` |
| `/api/ai/*` | `ai-service` |
| `/api/*` (otro) | 404 JSON |
| resto | SPA (`index.html`) |

- Se quita el prefijo `/api` antes de reenviar; se propaga `X-Request-ID`
  (`$request_id` de Nginx) para correlacionar logs.
- `X-Forwarded-For` se sobrescribe con la IP real del cliente y `auth-service` confía en
  él (`FORWARDED_ALLOW_IPS`, por defecto `*`: las APIs solo son alcanzables desde la red
  Docker). Así el rate limit cuenta por cliente y no por proxy.
- `client_max_body_size 64k` (413 si se supera), cabeceras `Content-Security-Policy`,
  `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
  `index.html` sin caché; `/assets/*` (con hash) con caché de 1 año.
- Healthcheck: `wget -q --spider http://127.0.0.1/`.

Comprobación rápida desde el host:

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:3000/            # 200
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:3000/api/users   # 401 (sin token)
```

## Usuario administrador semilla

`role-service` siembra los roles, pero no hay usuarios. El primer admin se crea así:

### Credenciales de desarrollo local

| Campo | Valor |
|---|---|
| Email | `admin@example.com` |
| Contraseña | `Password2026!` |
| Rol | `admin` |

Salen de `.env` (`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD`), que no se
versiona. Son credenciales de **desarrollo local**: no reutilizarlas fuera de este
entorno.

**Automático (por defecto en local).** Con `COMPOSE_PROFILES=local` en `.env` y
`BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` definidas, `docker compose up -d`
ejecuta dos contenedores efímeros del perfil `local`:

1. `bootstrap-account` crea (o localiza) la cuenta en `auth-service` y deja su `id` en el
   volumen `bootstrap_state`.
2. `bootstrap-admin` le asigna el rol `admin` en `role-service`.

Comprobación: `docker compose ps -a` debe mostrarlos en `Exited (0)`.

**Manual (hosts con Python 3.12).** Alternativa equivalente, sin perfil:

```powershell
py scripts/bootstrap_admin.py --email admin@example.com
```

- Pide la contraseña de forma oculta (o la lee de `BOOTSTRAP_ADMIN_PASSWORD`) y la pasa
  por stdin al contenedor, nunca por argumentos.
- Crea la cuenta en `auth-service` (o reutiliza la existente) y le asigna el rol `admin`
  en `role-service`. Es idempotente.
- Si la cuenta ya existe, **no cambia su contraseña**: solo devuelve su `id`. Para
  cambiarla hay que borrar la cuenta y su asignación de rol y volver a ejecutar el
  bootstrap:

  ```powershell
  $id = (docker compose exec -T postgres psql -U postgres -d auth_db -tAc "delete from accounts where email = 'admin@example.com' returning id;" | Select-Object -First 1).Trim()
  docker compose exec -T postgres psql -U postgres -d roles_db -c "delete from user_roles where user_id = '$id';"
  docker compose up -d
  ```

- Ese admin hace login en `POST /auth/login` y gestiona usuarios y roles; el resto de
  cuentas se registran con `POST /auth/register` y reciben roles desde la API.

## Smoke tests

```powershell
docker compose ps
docker compose exec -T auth-service python -c "import urllib.request as u; [print(s, u.urlopen(f'http://{s}:8000/health').status) for s in ('auth-service','user-service','role-service','audit-service','ai-service')]"
docker compose exec -T auth-service python -c "import urllib.request as u; print(u.urlopen('http://auth-service:8000/.well-known/jwks.json').read().decode())"
docker compose exec -T auth-service python -c "import urllib.request as u, urllib.error as e;`ntry: u.urlopen('http://user-service:8000/users')`nexcept e.HTTPError as x: print(x.code)"
```

Esperado: cinco `200`, un JWKS con una clave `RS256` y `401` en `/users` sin token.

## Endpoints

| Servicio | Endpoints | Authz |
|---|---|---|
| `auth-service` | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`; `GET /auth/accounts?email=`; `GET /.well-known/jwks.json` | Públicos salvo `logout` (token) y `accounts` (rol `admin`) |
| `user-service` | `POST/GET /users`, `GET/PATCH/DELETE /users/{id}` | Scopes `users:read` / `users:write` |
| `role-service` | `GET/POST /roles`, `PUT /roles/{id}/permissions`, `POST /users/{id}/roles`, `DELETE /users/{id}/roles/{role_id}`; `GET /users/{id}/roles` y `/permissions` | `GET /roles` con token; escrituras rol `admin`; lecturas de usuario con scope `roles:read` |
| `audit-service` | `GET /audit?user=&type=&from=&to=&page=&page_size=` | Rol `auditor` o `admin` |
| `ai-service` | `POST /ai/ask`, `POST /ai/reindex`, `GET /ai/metrics`, `GET /ai/health` | Scope `ai:use`; reindex y métricas rol `admin` |

Todos exponen `GET /health` y, fuera de `ENVIRONMENT=production`, `/docs`.

## Servicio de IA

Documentación detallada: [`ia/rag.md`](ia/rag.md),
[`ia/prompt-engineering.md`](ia/prompt-engineering.md),
[`ia/evaluacion.md`](ia/evaluacion.md) y [`ia/ejemplo-uso.md`](ia/ejemplo-uso.md).

1. Indexar la documentación en Qdrant (rol `admin`, idempotente). Desde la UI con
   el botón **Reindexar documentación** en `/assistant`, o por API:

   ```powershell
   curl.exe -s -X POST http://localhost:3000/api/ai/reindex `
     -H "Authorization: Bearer $TOKEN"
   ```

2. Preguntar al agente:

   ```powershell
   curl.exe -s -X POST http://localhost:3000/api/ai/ask `
     -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" `
     -d '{\"question\":\"¿Cómo se validan los tokens JWT?\"}'
   ```

3. Latencia y coste acumulados (rol `admin`):

   ```powershell
   curl.exe -s http://localhost:3000/api/ai/metrics -H "Authorization: Bearer $TOKEN"
   ```

El corpus es `docs/` (montado en `/app/docs`). Tras cambiar documentación hay que
volver a ejecutar `/ai/reindex`: solo re-embebe los archivos cuyo hash cambió.

**Proveedores**: el chat usa un endpoint compatible con OpenAI (`OPENAI_BASE_URL`)
y `OPENAI_MODEL`; por defecto OpenCode Go con `glm-5.3-flash`. Los embeddings se
generan en local con **FastEmbed** (`EMBEDDING_PROVIDER=fastembed`), así que no
consumen tokens ni necesitan clave; la primera indexación descarga el modelo
(~1–2 min) en el volumen `fastembed_cache`. Sin `OPENAI_API_KEY` el reindex
funciona, pero `/ai/ask` responde `503 ai_not_configured`.

### Vista del asistente

La UI incluye **Asistente** (`/assistant`) para usuarios con scope `ai:use` (los
roles `admin` y `user` ya lo tienen sembrado). Permite:

- Preguntar en lenguaje natural y ver la respuesta con **fuentes citadas**
  (documento y sección), latencia, tokens, coste, modelo y versión de prompt.
- Enviar con `Intro`, salto de línea con `Mayús+Intro` y un límite de 2000
  caracteres; historial corto de 6 mensajes para preguntas de seguimiento.
- Activar **Incluir datos del sistema** (usuarios/roles) si la cuenta tiene
  `users:read`; el backend reenvía el token del usuario.
- Reintentar tras un error y empezar una conversación nueva.
- **Reindexar la documentación** (solo `admin`) con confirmación y resumen de
  documentos/fragmentos procesados.

El primer uso requiere que un `admin` ejecute `/ai/reindex` para cargar el corpus.

## Revisión de secretos

```powershell
py scripts/scan_secrets.py   # sale con 1 si encuentra posibles secretos
```

Detalle de controles de seguridad: [`seguridad/owasp-api-top10.md`](seguridad/owasp-api-top10.md).
Aplicación real de DDD/Clean: [`arquitectura/ddd-implementacion.md`](arquitectura/ddd-implementacion.md).

## Tests del backend

Cada servicio Python tiene su suite en `services/<servicio>/tests/` y no necesita
infraestructura levantada: PostgreSQL, Redis, RabbitMQ, MongoDB y Qdrant se
sustituyen por fakes en memoria y los tokens se firman con una clave RS256
generada en el propio test (`app_common.testing`). El `ai-service` sustituye
OpenAI por dobles de prueba y añade una suite de evaluación reproducible
(`py -m eval.run_eval`).

| Capa | Qué se prueba |
|---|---|
| `domain/` | Entidades, value objects y reglas de negocio |
| `application/` | Casos de uso contra puertos en memoria (`tests/application/fakes.py`) |
| `infrastructure/` | Adaptadores con sesiones/clientes falsos (SQLAlchemy, Redis, MongoDB) y outbox workers |
| `api/` | `TestClient` de FastAPI: códigos de estado, validación (422), errores de dominio y authz (401/403) |

### Instalación (una vez)

```powershell
py -m pip install -e "services/common[test]"
py -m pip install -e "services/auth-service[test]"
py -m pip install -e "services/user-service[test]"
py -m pip install -e "services/role-service[test]"
py -m pip install -e "services/audit-service[test]"
py -m pip install -e "services/ai-service[test]"
```

### Ejecutar todos los suites

```powershell
py scripts/run_tests.py            # equivalente a `make test`
py scripts/run_tests.py --html     # además genera services/<servicio>/htmlcov/
py scripts/run_tests.py user-service role-service   # solo algunos servicios
```

Con `make` disponible (Linux/macOS/WSL): `make test` o `make test-html`
(`PYTHON=py make test` si el intérprete no se llama `python`).

El script ejecuta `pytest` en cada servicio y termina con un resumen:

```text
=== Summary ===
service         result  coverage
common          PASS    82.05%
auth-service    PASS    93.83%
...
```

El código de salida es distinto de 0 si algún suite falla o no llega al umbral.

### Ejecutar un solo servicio

```powershell
cd services/user-service
py -m pytest            # tests + coverage (umbral 70 %)
py -m pytest tests/api  # solo la capa API
```

### Leer el reporte de cobertura

- La configuración vive en el `pyproject.toml` de cada servicio
  (`[tool.pytest.ini_options] addopts` y `[tool.coverage.run] source`).
- Se mide `api`, `application`, `domain` e `infrastructure` (en `common`, el paquete
  `app_common`). `main.py` (composición con infraestructura real) y `migrations/`
  quedan fuera.
- `--cov-fail-under=70` hace fallar el suite si la cobertura total baja del 70 %.
- En terminal se listan solo los archivos con líneas sin cubrir (columna `Missing`).
- `coverage.xml` (formato Cobertura, apto para CI) se escribe en el directorio de
  cada servicio; con `--html` se genera además `htmlcov/index.html`.
- Ambos artefactos están en `.gitignore`.

## Tests del frontend

Requiere Node 22+ (`@testing-library/jest-dom` 7) y npm 11. Jest 30 (`jsdom` + `@swc/jest`) con React Testing Library; no
necesita servicios levantados: los tests de vistas mockean los adaptadores de
`src/services/*Api.ts` y el cliente HTTP se prueba con un `fetch` falso. Los tiempos
(toasts) usan fake timers, así que el suite es determinista.

```powershell
cd frontend
npm ci                      # una vez (no usar `npm install`, ver nota)
npm test                    # todos los tests
npm test -- --coverage      # + reporte de cobertura
npm test -- src/features/audit   # solo una carpeta
npm run lint                # ESLint + Prettier
npm run build               # tsc + build de Vite
```

| Suite | Qué se prueba |
|---|---|
| `services/apiClient.test.ts`, `jwt.test.ts`, `endpoints.test.ts` | JWT, errores `{code,message,details}`, refresh ante 401, rutas y métodos de cada servicio |
| `stores/stores.test.ts` | Transiciones `idle → loading → success/error` y errores de mutación |
| `components/feedback.test.tsx` | Spinner, Skeleton, ErrorState, EmptyState, ConfirmDialog y toasts |
| `features/auth/auth.test.tsx`, `app/routes.test.tsx` | Login, rate limit, guards, logout, refresh único y sesión caducada |
| `features/users`, `features/roles`, `features/audit` | Vistas con datos simulados, formularios, confirmaciones y acceso denegado |
| `features/ai` | Chat del asistente: envío, historial, fuentes, error con reintento, calidad y permisos |

Cobertura: se mide `src/` salvo `main.tsx` y `src/test/`. En terminal sale el resumen
y la tabla por archivo; `frontend/coverage/lcov-report/index.html` tiene el detalle
(`coverage/` está en `.gitignore`).

Nota sobre `package-lock.json`: en Windows, `npm install` poda del lock dependencias
opcionales de otras plataformas (`@emnapi/*`) y el `npm ci` de la imagen Linux falla.
Si hay que cambiar dependencias, regenerar el lock en Linux:

```powershell
cd frontend
docker run --rm -v "${PWD}:/src" node:20-alpine sh -c "npm i -g npm@11.6.2 >/dev/null && mkdir /tmp/w && cp /src/package.json /tmp/w/ && cd /tmp/w && npm install --package-lock-only && cp package-lock.json /src/"
npm ci
```
