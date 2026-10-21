# Sistema de gestión de usuarios (Toka)

Monorepo de microservicios para gestionar usuarios, roles y auditoría, con un
frontend React y un asistente de IA (RAG) que responde sobre la documentación
del propio sistema.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | React 19 + TypeScript + Vite, servido con Nginx |
| APIs | FastAPI (Python 3.12) con DDD + Clean Architecture |
| Datos | PostgreSQL (auth, users, roles), MongoDB (auditoría), Redis (caché/revocación), Qdrant (RAG), RabbitMQ (eventos) |
| Auth | JWT RS256 con JWKS, refresh rotado y revocación por `jti` |

Servicios: `auth-service`, `user-service`, `role-service`, `audit-service`,
`ai-service` (y `common` como librería técnica compartida).

## Arranque rápido

Requisitos: Docker + Docker Compose v2. Python 3.12 y Node 22+ solo para
scripts y tests fuera de Docker.

```powershell
Copy-Item .env.example .env          # reemplazar todos los `change-me`
py scripts/generate_jwt_keys.py      # claves JWT en infra/keys/
docker compose up -d --build
docker compose ps                    # esperar `healthy`
```

Abrir <http://localhost:3000> e iniciar sesión con `admin@example.com` /
`Password2026!` (credenciales de desarrollo local definidas en `.env`).
`OPENAI_API_KEY` es opcional: sin ella el sistema funciona salvo `/ai/ask`.

`.env` e `infra/keys/` no se versionan.

## Tests

```powershell
py scripts/run_tests.py              # backend (equivale a `make test`)
cd frontend; npm ci; npm test        # frontend
```

## Documentación

Toda la documentación está en **[`docs/`](docs/)** y es también el corpus del
asistente: tras modificarla hay que ejecutar `/ai/reindex` para reindexarla.

| Documento | Qué encontrarás |
|---|---|
| [`docs/ejecucion.md`](docs/ejecucion.md) | Prerrequisitos, arranque, admin semilla, endpoints, smoke tests, tests y cobertura |
| [`docs/arquitectura/diagrama.md`](docs/arquitectura/diagrama.md) | Diagrama de servicios e infraestructura |
| [`docs/arquitectura/justificacion-tecnica.md`](docs/arquitectura/justificacion-tecnica.md) | Decisiones de stack y trade-offs |
| [`docs/arquitectura/flujos-de-datos.md`](docs/arquitectura/flujos-de-datos.md) | Flujos REST y eventos RabbitMQ |
| [`docs/arquitectura/diseno-docker-compose.md`](docs/arquitectura/diseno-docker-compose.md) | Redes, volúmenes y despliegue |
| [`docs/arquitectura/ddd-clean-architecture.md`](docs/arquitectura/ddd-clean-architecture.md) | Diseño de capas y bounded contexts |
| [`docs/arquitectura/ddd-implementacion.md`](docs/arquitectura/ddd-implementacion.md) | Cómo quedó implementado |
| [`docs/seguridad/owasp-api-top10.md`](docs/seguridad/owasp-api-top10.md) | Controles frente a OWASP API Top 10 |
| [`docs/ia/rag.md`](docs/ia/rag.md), [`prompt-engineering.md`](docs/ia/prompt-engineering.md), [`evaluacion.md`](docs/ia/evaluacion.md), [`ejemplo-uso.md`](docs/ia/ejemplo-uso.md) | Pipeline RAG, prompts, métricas y ejemplo de uso |
| [`docs/diagnostico/README.md`](docs/diagnostico/README.md) | Ejercicio de diagnóstico de incidentes |
| [`services/README.md`](services/README.md) | Estructura de un servicio y cómo añadir uno nuevo |

## Estructura del repositorio

```text
docs/          documentación (y corpus del RAG)
frontend/      SPA React + Nginx
services/      microservicios FastAPI + common
infra/         configuración de Postgres, RabbitMQ y claves JWT
scripts/       bootstrap de admin, claves JWT, tests y escaneo de secretos
```

## Seguridad

- No versionar `.env` ni `infra/keys/`.
- `py scripts/scan_secrets.py` revisa posibles secretos antes de un commit.
