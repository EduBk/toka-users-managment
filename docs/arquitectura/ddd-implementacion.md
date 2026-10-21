# DDD y Clean Architecture en la implementación real (E2.11)

Complementa a [`ddd-clean-architecture.md`](ddd-clean-architecture.md) (E1.5, diseño)
describiendo cómo quedó el código de E2.x y dónde se desvió del diseño y por qué.

## Capas y regla de dependencias

Cada servicio (`auth`, `user`, `role`, `audit`, `ai`) mantiene las cuatro capas de E1.5:

| Capa | Contenido real | Verificación |
|---|---|---|
| `domain/<contexto>/` | Agregados (`entity.py`), value objects, eventos, `repository.py` (`Protocol`) y excepciones | Ningún archivo importa FastAPI, SQLAlchemy, Pydantic, Redis, aio-pika, Motor, httpx ni `app_common` |
| `application/` | `use_cases/` (un caso de uso por clase con `execute`), `ports/` (`Protocol`) y `dto.py` (dataclasses) | Solo importa `domain/` y sus puertos |
| `infrastructure/` | Adaptadores SQLAlchemy, Redis, MongoDB, RabbitMQ (outbox worker) y HTTP (`role_service/client.py`) | Implementa los puertos; no importa `api/` |
| `api/` | `router.py`, `schemas.py` (Pydantic), `errors.py` (excepción → HTTP) y `deps.py` (composition root) | Solo `deps.py` toca `infrastructure/` |

La comprobación se hizo con una búsqueda de imports sobre `domain/` y `application/`
de todos los servicios (0 coincidencias fuera de `tests/`).

`main.py` arma la app con `app_common.create_service_app` (logging JSON, `trace_id`,
errores uniformes, `/health`) y en el `lifespan` crea los adaptadores reales y los deja
en `app.state`, de donde `api/deps.py` los inyecta en los casos de uso.

## Modelo por contexto: diseño vs. implementación

| Contexto | Diseño E1.5 | Implementado | Motivo |
|---|---|---|---|
| Auth | Agregado `Credential`, entidad `RefreshToken`, servicio de dominio `TokenIssuer` | Agregado `Account` (`id`, `email`, `password_hash`, `is_active`, `created_at`), VO `Email`, `TokenClaims`/`IssuedToken`; puerto `TokenService` implementado por `Rs256TokenService` en infraestructura | E2.3 manda `Account`. La firma RS256 depende de PyJWT/cryptography, así que vive en infraestructura detrás de un puerto; el refresh token se modela por `jti` revocado en Redis, sin entidad persistida |
| Usuarios | `User` + VOs, eventos, repositorio | Igual: `User`, `Email`, `UserName`, `UserStatus`, `Profile`; `UserCreated/Updated/Deactivated` | - |
| Roles | `Role` + `Permission` interno, agregado `UserRoleAssignment` | Igual, con `RoleName`, `RoleDescription`, `PermissionName`, `AssignmentKey` | Se confirmó la propuesta de E1.5 |
| Auditoría | `AuditEntry` inmutable, `add_if_absent` | Igual; `MongoProcessedEventStore` reutiliza el índice único `event_id` como marcador de idempotencia | Evita una segunda colección |
| Agente IA | `AgentRequest`/`AgentResponse`, `VectorStore`, `LlmClient` | `AgentQuestion`/`AgentAnswer`/`Source`/`Usage`, puertos `LlmClient`, `EmbeddingClient`, `VectorStore`, `PromptProvider`, `MetricsStore`, `SystemDataProvider`; adaptadores OpenAI/Qdrant/ficheros/HTTP | Sin persistencia transaccional ni outbox: los documentos viven en Qdrant y las métricas en memoria + logs JSON. El agente reutiliza el token del usuario en las consultas a otros servicios |

## Patrones aplicados

- **Unit of Work** (`user`, `role`): `SqlAlchemyUnitOfWork` abre una sesión por caso
  de uso y expone repositorios + outbox sobre la misma transacción.
- **Outbox transaccional**: `outbox_events` por base; el agregado acumula eventos
  (`pull_events`) y el caso de uso los añade al outbox antes del `commit`. En
  `auth-service` los eventos de login no acompañan un cambio de agregado, así que el
  outbox abre su propia sesión.
- **Envelope y publicador compartidos**: `app_common.event_envelope` y
  `app_common.event_publisher` (en lugar de un `serializer.py` por servicio) porque
  son infraestructura técnica idéntica en los tres productores.
- **Worker**: un worker por proceso lee pendientes ordenados por `occurred_at`; no usa
  `FOR UPDATE SKIP LOCKED` porque hay un único worker por servicio. Entrega
  *at-least-once*; el consumidor es idempotente por `event_id`.
- **CQRS ligero**: comandos por el agregado; `GetUser`/`ListUsers` leen con caché
  Redis cache-aside (E2.6). Sin read models separados.
- **Puertos para resiliencia**: `UserCache`, `TokenRevocationStore`,
  `UserAccessProvider` tienen implementación nula (`Null*`) para arrancar sin la
  dependencia y degradar de forma explícita.
- **Puertos del agente IA**: `LlmClient`, `EmbeddingClient`, `VectorStore`,
  `PromptProvider` y `SystemDataProvider` permiten sustituir OpenAI/Qdrant por
  dobles en tests y en la suite de evaluación; el caso de uso `AskAgent` no conoce
  ningún SDK.

## Desviaciones respecto a E1.5

| Punto de E1.5 | Implementación | Comentario |
|---|---|---|
| `api/routes/<recurso>.py` | `api/router.py` | Un router por servicio basta para el tamaño actual |
| `application/ports/outbox.py`, `cache.py` | `event_outbox.py`, `user_cache.py` | Solo nombres |
| Fallo de base de datos → `503` | `500 internal_error` genérico | El handler común no distingue errores de infraestructura; no se filtra SQL ni stack trace |
| Lecturas de roles solo con JWT | `GET /users/{id}/roles` y `/permissions` con scope `roles:read` | `auth-service` las consulta en el login con un token de servicio propio de 60 s (E2.14) |
| Verificación automática con `import-linter` | Revisión por búsqueda de imports | Sigue como mejora opcional |

## Ejemplo trazable

`POST /users` recorre `api/router.py` → `api/deps.py` (`CreateUser` con
`SqlAlchemyUnitOfWork` + `RedisUserCache`) → `application/use_cases/create_user.py`
→ `domain/user/entity.py` (`User.create` valida y genera `UserCreated`) →
`infrastructure/persistence/` (fila + outbox en el mismo `commit`) → invalidación de
caché → `201`. El worker publica `user.created` y `audit-service` lo guarda en
`audit_entries`.
