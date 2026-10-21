# E1.4 - Diseño del docker-compose.yml

Estructura previa del `docker-compose.yml` que orquesta servicios, redes, volúmenes y
variables de entorno. Este documento es el contrato que implementa E2.2 (infraestructura)
y completa E3.8 (front-end). No contiene secretos reales.

## Vista de despliegue

```mermaid
flowchart LR
    subgraph fnet["frontend-net"]
        fe["frontend<br/>nginx :80"]
        auth["auth-service :8000"]
        user["user-service :8000"]
        role["role-service :8000"]
        audit["audit-service :8000"]
        ai["ai-service :8000"]
    end

    subgraph bnet["backend-net"]
        pg[("postgres :5432")]
        mongo[("mongodb :27017")]
        redis[("redis :6379")]
        rabbit[["rabbitmq :5672 / :15672"]]
        qdrant[("qdrant :6333 / :6334")]
    end

    openai["OpenAI API<br/>(externo)"]

    fe -->|"/api/auth"| auth
    fe -->|"/api/users"| user
    fe -->|"/api/roles"| role
    fe -->|"/api/audit"| audit
    fe -->|"/api/ai"| ai
    ai -->|HTTPS| openai
    auth --- pg
    user --- pg
    role --- pg
    audit --- mongo
    user --- redis
    auth --- redis
    audit --- rabbit
    user --- rabbit
    role --- rabbit
    ai --- qdrant
```

## Servicios de aplicación

| Servicio | Build | Red(es) | Puerto interno | depends_on (salud) |
|---|---|---|---|---|
| `auth-service` | `./services/auth-service` | `frontend-net`, `backend-net` | 8000 | `postgres`, `rabbitmq`, `redis` (opcional) |
| `user-service` | `./services/user-service` | `frontend-net`, `backend-net` | 8000 | `postgres`, `redis`, `rabbitmq` |
| `role-service` | `./services/role-service` | `frontend-net`, `backend-net` | 8000 | `postgres`, `rabbitmq` |
| `audit-service` | `./services/audit-service` | `frontend-net`, `backend-net` | 8000 | `mongodb`, `rabbitmq` |
| `ai-service` | `./services/ai-service` | `frontend-net`, `backend-net` | 8000 | `qdrant` |
| `frontend` | `./frontend` (multi-stage Node → Nginx) | `frontend-net` | 80 | los cinco servicios API |

Los servicios API no se publican al host: el front los consume por red interna y Nginx
hace de proxy (`/api/*`), lo que además elimina CORS en local (E3.8). El puerto interno
8000 es uniforme y lo fija la plantilla de E2.1.

## Servicios de infraestructura

| Servicio | Imagen (propuesta) | Red | Volumen | Puerto host |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | `backend-net` | `pg_data` | 5432 |
| `mongodb` | `mongo:7` | `backend-net` | `mongo_data` | 27017 |
| `redis` | `redis:7-alpine` | `backend-net` | `redis_data` | — |
| `rabbitmq` | `rabbitmq:3-management-alpine` | `backend-net` | `rabbitmq_data` | 15672 |
| `qdrant` | `qdrant/qdrant:latest` | `backend-net` | `qdrant_data` | 6333 |

Solo RabbitMQ (UI de management) y Qdrant (UI/REST) se publican para inspección en
desarrollo. PostgreSQL y MongoDB se publican para conectar clientes SQL/NoSQL locales;
el detalle está en la tabla de puertos.

## Redes

| Red | Miembros | Motivo |
|---|---|---|
| `frontend-net` | `frontend` + los cinco servicios API | Aísla el tráfico este-oeste que necesita Nginx; la infraestructura no es visible desde el front |
| `backend-net` | Los cinco servicios API + `postgres`, `mongodb`, `redis`, `rabbitmq`, `qdrant` | Aísla los almacenes; sin `internal: true` porque `ai-service` y `auth-service` necesitan salida a internet (OpenAI) |

## Volúmenes

| Volumen | Contenido | Nota |
|---|---|---|
| `pg_data` | Las tres bases lógicas `auth_db`, `users_db`, `roles_db` | Un único servidor PostgreSQL con tres bases creadas por init scripts; un solo volumen las respalda (E2.2) |
| `mongo_data` | Base de auditoría y colección `audit_entries` | |
| `redis_data` | Caché y revocación de `jti` | Persistencia opcional; Redis puede recrearse sin pérdida de datos de negocio |
| `rabbitmq_data` | Definiciones del exchange `domain.events`, colas y DLQ | |
| `qdrant_data` | Colecciones vectoriales | |

## Variables de entorno

Todas se resuelven desde `.env` (no versionado). `.env.example` documenta los nombres con
valores de relleno (`change-me`), nunca credenciales reales.

### Infraestructura (`.env.example`)

```dotenv
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
AUTH_DB_NAME=auth_db
USERS_DB_NAME=users_db
ROLES_DB_NAME=roles_db

MONGO_INITDB_ROOT_USERNAME=root
MONGO_INITDB_ROOT_PASSWORD=change-me
MONGO_INITDB_DATABASE=audit_db
MONGO_URI=mongodb://root:change-me@mongodb:27017/audit_db?authSource=admin
AUDIT_RETENTION_DAYS=90

REDIS_PASSWORD=change-me
REDIS_URL=redis://:change-me@redis:6379/0

RABBITMQ_DEFAULT_USER=app
RABBITMQ_DEFAULT_PASS=change-me
RABBITMQ_URL=amqp://app:change-me@rabbitmq:5672/

QDRANT_URL=http://qdrant:6333

JWT_ISSUER=auth-service
JWT_AUDIENCE=user-management
ACCESS_TOKEN_TTL_SECONDS=900
REFRESH_TOKEN_TTL_DAYS=7
VITE_API_URL=/api
OPENAI_API_KEY=
```

### Por servicio

| Servicio | Variables |
|---|---|
| `auth-service` | `SERVICE_NAME`, `LOG_LEVEL`, `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, `JWT_PRIVATE_KEY_PATH`, `JWT_PUBLIC_KEY_PATH`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_TTL_SECONDS`, `REFRESH_TOKEN_TTL_DAYS` |
| `user-service` | `SERVICE_NAME`, `LOG_LEVEL`, `DATABASE_URL`, `REDIS_URL`, `CACHE_TTL_SECONDS`, `RABBITMQ_URL`, `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` |
| `role-service` | `SERVICE_NAME`, `LOG_LEVEL`, `DATABASE_URL`, `RABBITMQ_URL`, `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` |
| `audit-service` | `SERVICE_NAME`, `LOG_LEVEL`, `MONGO_URI`, `MONGO_DATABASE`, `AUDIT_RETENTION_DAYS`, `RABBITMQ_URL`, `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` |
| `ai-service` | `SERVICE_NAME`, `LOG_LEVEL`, `QDRANT_URL`, `QDRANT_COLLECTION`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `FASTEMBED_MODEL`, `FASTEMBED_CACHE_DIR`, `JWKS_URL`, `JWT_ISSUER`, `JWT_AUDIENCE` |
| `frontend` | `VITE_API_URL` (build arg; E3.8) |

`JWKS_URL` apunta a `http://auth-service:8000/.well-known/jwks.json` (E2.4). Las claves
RS256 se montan como archivos de solo lectura desde `infra/keys/` (generadas en local y
excluidas de git), nunca se escriben en el compose.

Generación local del par de claves (obligatorio antes de `docker compose up`):

```powershell
py scripts/generate_jwt_keys.py
```

El script escribe `infra/keys/jwt_private.pem` y `infra/keys/jwt_public.pem` (2048 bits,
sin passphrase) y se niega a sobrescribirlas salvo con `--force`. La clave privada solo
la lee `auth-service`; el resto de servicios valida con la pública: bien por JWKS desde
`JWKS_URL`, bien con `JWT_PUBLIC_KEY_PATH` cuando la tengan montada. `app_common.jwt_auth`
expone `JwtValidator`, la dependencia `CurrentClaims` y los factories `require_scopes` /
`require_roles`; el chequeo de `jti` revocado en Redis es opcional (lo usan los servicios
con `REDIS_URL`, como `auth-service` y `user-service`).

## Healthchecks y arranque ordenado

| Servicio | Healthcheck | `depends_on` con condición |
|---|---|---|
| `postgres` | `pg_isready -U $POSTGRES_USER -d postgres` | — |
| `mongodb` | `mongosh --quiet --eval "db.adminCommand('ping')"` | — |
| `redis` | `redis-cli -a $REDIS_PASSWORD ping` | — |
| `rabbitmq` | `rabbitmq-diagnostics -q ping` | — |
| `qdrant` | HTTP `GET /healthz` (propuesto; confirmar binario disponible en la imagen) | — |
| `auth-service` | `GET /health` (E2.1) | `postgres` y `rabbitmq` sanos; `redis` sano pero `required: false` |
| `user-service` | `GET /health` | `postgres`, `redis`, `rabbitmq` sanos |
| `role-service` | `GET /health` | `postgres`, `rabbitmq` sanos |
| `audit-service` | `GET /health` | `mongodb`, `rabbitmq` sanos |
| `ai-service` | `GET /health` | `qdrant` sano |
| `frontend` | `wget -q --spider http://localhost/` | los cinco servicios API sanos |

`redis` es opcional para `auth-service` porque el login funciona sin él (E1.3); Compose
permite `condition: service_healthy` junto a `required: false`.

No se declaran dependencias entre servicios API: todos validan JWT con JWKS cacheado y no
necesitan `auth-service` para arrancar, lo que evita un arranque en cascada.

## Puertos expuestos

| Servicio | Contenedor | Host | Necesidad |
|---|---|---|---|
| `frontend` | 80 | 3000 | Único punto de entrada de la UI |
| `postgres` | 5432 | 5432 | Cliente SQL local y migraciones Alembic |
| `mongodb` | 27017 | 27017 | Inspección de auditoría con `mongosh` |
| `rabbitmq` | 15672 | 15672 | Management UI (colas y DLQ) |
| `qdrant` | 6333 | 6333 | UI/REST de Qdrant |
| `redis` | 6379 | — | Solo acceso interno de los servicios |
| `rabbitmq` | 5672 | — | AMQP solo por `backend-net` |
| `qdrant` | 6334 | — | gRPC solo por `backend-net` |
| servicios API | 8000 | — | Consumidos vía proxy de Nginx |

`3000:80` para el front es un valor propuesto; se confirma en E3.8.

## Esqueleto del compose

```yaml
name: user-management

networks:
  frontend-net:
    driver: bridge
  backend-net:
    driver: bridge

volumes:
  pg_data:
  mongo_data:
  redis_data:
  rabbitmq_data:
  qdrant_data:

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./infra/postgres/init:/docker-entrypoint-initdb.d:ro
    ports:
      - "5432:5432"
    networks: [backend-net]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  mongodb:
    image: mongo:7
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_INITDB_ROOT_USERNAME}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_INITDB_ROOT_PASSWORD}
      MONGO_INITDB_DATABASE: ${MONGO_INITDB_DATABASE}
    volumes:
      - mongo_data:/data/db
    ports:
      - "27017:27017"
    networks: [backend-net]
    healthcheck:
      test: ["CMD-SHELL", "mongosh --quiet --eval \"db.adminCommand('ping')\""]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    volumes:
      - redis_data:/data
    networks: [backend-net]
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a $${REDIS_PASSWORD} ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  rabbitmq:
    image: rabbitmq:3-management-alpine
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_DEFAULT_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_DEFAULT_PASS}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
      - ./infra/rabbitmq/definitions.json:/etc/rabbitmq/definitions.json:ro
    ports:
      - "15672:15672"
    networks: [backend-net]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 15s
      timeout: 10s
      retries: 5
      start_period: 20s

  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    networks: [backend-net]

  auth-service:
    build: ./services/auth-service
    environment:
      SERVICE_NAME: auth-service
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${AUTH_DB_NAME}
      REDIS_URL: ${REDIS_URL}
      RABBITMQ_URL: ${RABBITMQ_URL}
      JWT_PRIVATE_KEY_PATH: /run/secrets/jwt_private.pem
      JWT_PUBLIC_KEY_PATH: /run/secrets/jwt_public.pem
      JWT_ISSUER: ${JWT_ISSUER}
      JWT_AUDIENCE: ${JWT_AUDIENCE}
      ACCESS_TOKEN_TTL_SECONDS: ${ACCESS_TOKEN_TTL_SECONDS:-900}
      REFRESH_TOKEN_TTL_DAYS: ${REFRESH_TOKEN_TTL_DAYS:-7}
    volumes:
      - ./infra/keys:/run/secrets:ro
    networks: [frontend-net, backend-net]
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
      redis:
        condition: service_healthy
        required: false

  user-service:
    build: ./services/user-service
    environment:
      SERVICE_NAME: user-service
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${USERS_DB_NAME}
      REDIS_URL: ${REDIS_URL}
      RABBITMQ_URL: ${RABBITMQ_URL}
      JWKS_URL: http://auth-service:8000/.well-known/jwks.json
      JWT_ISSUER: ${JWT_ISSUER}
      JWT_AUDIENCE: ${JWT_AUDIENCE}
    networks: [frontend-net, backend-net]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  role-service:
    build: ./services/role-service
    environment:
      SERVICE_NAME: role-service
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${ROLES_DB_NAME}
      RABBITMQ_URL: ${RABBITMQ_URL}
      JWKS_URL: http://auth-service:8000/.well-known/jwks.json
      JWT_ISSUER: ${JWT_ISSUER}
      JWT_AUDIENCE: ${JWT_AUDIENCE}
    networks: [frontend-net, backend-net]
    depends_on:
      postgres:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  audit-service:
    build: ./services/audit-service
    environment:
      SERVICE_NAME: audit-service
      MONGO_URI: ${MONGO_URI}
      MONGO_DATABASE: ${MONGO_INITDB_DATABASE}
      RABBITMQ_URL: ${RABBITMQ_URL}
      JWKS_URL: http://auth-service:8000/.well-known/jwks.json
      JWT_ISSUER: ${JWT_ISSUER}
      JWT_AUDIENCE: ${JWT_AUDIENCE}
    networks: [frontend-net, backend-net]
    depends_on:
      mongodb:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy

  ai-service:
    build: ./services/ai-service
    environment:
      SERVICE_NAME: ai-service
      QDRANT_URL: ${QDRANT_URL}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      JWKS_URL: http://auth-service:8000/.well-known/jwks.json
      JWT_ISSUER: ${JWT_ISSUER}
      JWT_AUDIENCE: ${JWT_AUDIENCE}
    networks: [frontend-net, backend-net]
    depends_on:
      qdrant:
        condition: service_started

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_URL: ${VITE_API_URL}
    networks: [frontend-net]
    ports:
      - "3000:80"
    depends_on:
      auth-service:
        condition: service_healthy
      user-service:
        condition: service_healthy
      role-service:
        condition: service_healthy
      audit-service:
        condition: service_healthy
      ai-service:
        condition: service_healthy
```

Los healthchecks de los servicios API (`GET /health`) y del front se declaran en E2.2 y
E3.8 respectivamente; aquí solo se fija la condición de arranque.

## Cobertura del diagrama de E1.1

| Elemento E1.1 | En el compose | Estado |
|---|---|---|
| `frontend` | servicio `frontend` | Cubierto |
| `auth-service` | servicio `auth-service` | Cubierto |
| `user-service` | servicio `user-service` | Cubierto |
| `role-service` | servicio `role-service` | Cubierto |
| `audit-service` | servicio `audit-service` | Cubierto |
| `ai-service` | servicio `ai-service` | Cubierto |
| PostgreSQL (`auth_db`, `users_db`, `roles_db`) | `postgres` + init scripts | Cubierto |
| MongoDB (`audit_entries`) | `mongodb` | Cubierto |
| Redis | `redis` | Cubierto |
| RabbitMQ (`domain.events`, `domain.events.dlq`) | `rabbitmq` + `definitions.json` | Cubierto |
| Qdrant | `qdrant` | Cubierto |
| OpenAI API | Variable `OPENAI_API_KEY` + salida a internet | Externo, no es contenedor |

## Notas y supuestos

- **Sin secretos reales**: solo nombres de variables y valores `change-me`/vacíos. Las
  claves JWT y la API key viven en `.env` o en `infra/keys/`, ambos ignorados por git.
- **PostgreSQL único**: un servidor con tres bases lógicas vía init scripts (E2.2); el
  volumen `pg_data` respalda las tres. Si se decide una instancia por base, se multiplican
  servicios y volúmenes.
- **Puertos**: `3000:80` del front y `8000` interno de las APIs son propuestas a confirmar
  en E3.8 y E2.1. Los puertos de infraestructura son los estándar de cada imagen.
- **Qdrant**: sin healthcheck documentado en E2.2; se usa `service_started` hasta
  confirmar que la imagen permite un chequeo HTTP en E2.2.
- **RabbitMQ**: las colas, el exchange y la DLQ se predeclaran con `definitions.json`;
  el detalle de routing keys se implementa en E2.2/E2.8.
- **Sin límites de recursos ni réplicas**: no forman parte del alcance de la prueba local;
  se documentan en `justificacion-tecnica.md` como criterio de escalabilidad.
