# E1.2 - Justificación técnica

Decisiones tecnológicas del sistema, con el problema que resuelve cada una y su
trade-off. Los nombres de servicios y almacenes coinciden con `diagrama.md` (E1.1).

## Stack por tecnología

| Tecnología | Por qué | Trade-off asumido |
|---|---|---|
| **FastAPI** (Python 3.12, SQLAlchemy 2.x, Alembic) | Tipado con Pydantic, validación de entrada y documentación OpenAPI automática (contratos verificables por el front). Async nativo para I/O concurrente (BD, HTTP, mensajería). Mismo lenguaje que el ecosistema de IA (SDK de OpenAI, Qdrant), evitando dos runtimes. | Menos "baterías incluidas" que frameworks monolíticos: seguridad, sesiones y transacciones se componen a mano. El ecosistema async exige disciplina (drivers async, no bloquear el event loop). |
| **PostgreSQL** (una base lógica por servicio: `auth_db`, `users_db`, `roles_db`) | Datos transaccionales con ACID, integridad referencial e índices maduros. Una base por bounded context evita acoplamiento por joins entre servicios y permite migraciones independientes con Alembic. | Más trabajo operativo (varias bases/migraciones) y sin consultas cruzadas directas: los cruces requieren API o evento. |
| **MongoDB** | La auditoría es un log append-only con esquemas heterogéneos por tipo de evento. Documentos evitan migraciones por cada nuevo payload y permiten indexar por `timestamp`, `actor` y `type`. | Sin transacciones relacionales entre colecciones: la consistencia se resuelve con eventos idempotentes, no con joins. Crecimiento del volumen requiere TTL/índices y política de retención. |
| **Redis** | Caché de lecturas de `user-service` con TTL e invalidación por evento: reduce latencia y carga sobre PostgreSQL en endpoints de listado/detalle. | Un dato puede estar obsoleto hasta el TTL o la invalidación; añade un estado más que sincronizar (cache stampede, invalidación fallida). |
| **RabbitMQ** (exchange topic `domain.events`, cola DLQ `domain.events.dlq`) | Desacopla la auditoría del camino crítico: `audit-service` consume sin que `user-service`/`role-service` dependan de él. Routing por topic (`user.*`, `role.*`) y acknowledgment con reintentos/DLQ dan entrega al-menos-una-vez controlada. | Consistencia eventual: el evento se publica tras el commit y puede perderse si el publicador cae (requiere outbox o publicación fiable). Operación adicional (broker, DLQ, monitorización). |
| **Qdrant** | Base vectorial para RAG: búsqueda por similitud con filtros por metadatos, contenedor local sin coste de servicio gestionado y API estable. | Un almacén más que mantener y cuyo contenido depende del pipeline de embeddings; resultados sensibles a la calidad de chunking y del modelo de embeddings. |
| **OpenAI** | API de LLM con calidad y latencia suficientes para el asistente, sin operar GPU propia ni modelos. | Dependencia de terceros: coste por token, latencia variable, rate limits y envío de datos a un proveedor externo (requiere no enviar PII innecesaria). |
| **React 19 + TypeScript + Vite + Zustand** (Jest + RTL) | SPA tipada con arranque y HMR rápidos; Zustand aporta estado global mínimo (sesión, usuario, roles) sin el boilerplate de Redux. TS comparte contratos con el OpenAPI del backend. | SPA implica más lógica de cliente (guards de ruta, refresco de token) y requiere que la autorización real viva en el servidor. Estado global sin capa de normalización puede duplicarse si crece el dominio. |

## Patrón de comunicación: REST + eventos

- **REST/HTTP para consultas y commands**: son operaciones con respuesta inmediata y
  contrato claro (`POST /users`, `GET /users/{id}`). El cliente necesita el resultado
  para continuar, y el error debe poder devolverse en la misma petición.
- **Eventos para auditoría y desacoplamiento**: la auditoría es un efecto secundario que
  no debe bloquear ni poder tumbar el alta de un usuario. Publicar `user.created` o
  `role.assigned` en `domain.events` permite que `audit-service` evolucione (nuevos
  consumidores, reprocesos) sin tocar a los productores.
- **Trade-off**: dos modelos mentales y dos modos de fallo (HTTP con timeout/retry vs
  eventos con entrega al-menos-una-vez). Por eso los consumidores deben ser idempotentes
  y la publicación no puede ser "fire and forget" sin control.

## Estrategia multi-DB (una base por bounded context)

- Cada servicio es dueño de su esquema: `auth-service` → `auth_db`, `user-service` →
  `users_db`, `role-service` → `roles_db`. Ningún servicio lee tablas de otro.
- Ventajas: migraciones independientes, límites de dominio explícitos, fallos aislados
  y posibilidad de escalar/migrar un contexto sin arrastrar el resto.
- **Trade-off**: no hay FK ni transacción entre contextos; la coherencia se logra por
  contrato de API o por evento. Las referencias entre agregados se guardan como IDs
  (p. ej. `role_id` en un usuario) sin garantía de integridad referencial de BD.
- En local se usa **un único contenedor PostgreSQL con tres bases lógicas** para no
  multiplicar recursos; el aislamiento es lógico, no físico. En un despliegue real cada
  base puede moverse a su propia instancia sin cambiar el código.

## Autenticación con JWT de clave asimétrica (RS256 + JWKS)

- `auth-service` firma con clave privada y publica las claves públicas en un endpoint
  JWKS. Cada servicio valida firma y claims **localmente**, sin llamar a `auth-service`
  por request.
- Ventajas: elimina un punto único de fallo y un salto de red en cada petición; permite
  escalar servicios (y `auth-service`) de forma independiente; el token es verificable
  por cualquier servicio nuevo sin coordinación.
- **Trade-off**: la revocación no es inmediata (un token válido sigue siéndolo hasta su
  `exp`); se mitiga con access tokens de vida corta + refresh tokens. La rotación de
  claves exige cachear y refrescar el JWKS ante `kid` desconocido.

## Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| **SQL Server** | Licencia y peso de contenedor para un entorno local; la prueba no requiere features específicas (T-SQL, integración Microsoft). PostgreSQL cubre ACID, JSONB e índices sin coste. |
| **Kafka** | Sobredimensionado para el volumen del sistema: requiere ZooKeeper/KRaft, particiones y operación más compleja. RabbitMQ da routing por topic, DLQ y management UI con menos infraestructura. |
| **NestJS** | Unificaría el stack en TypeScript, pero duplicaría el lenguaje del ecosistema de IA (Python) y obligaría a dos runtimes o a reescribir el servicio de IA. FastAPI ya ofrece tipado y OpenAPI. |
| **Azure OpenAI** | Añade dependencia de Azure (cuenta, región, red) sin beneficio para la prueba; el SDK y los modelos de OpenAI son equivalentes y funcionan con una API key. Queda como opción si se exige residencia de datos en Azure. |

## Criterios no funcionales

| Criterio | Cómo se cubre | Coste / límite |
|---|---|---|
| **Escalabilidad horizontal** | Servicios sin estado (JWT validado localmente), escalado por réplicas detrás de un balanceador; `audit-service` consume en paralelo con prefetch acotado. | El estado vive en PostgreSQL/Redis/MongoDB, que se convierten en el cuello de botella y requieren su propia estrategia (réplicas, índices). |
| **Resiliencia** | Timeouts y reintentos acotados en clientes HTTP, DLQ para eventos fallidos, idempotencia por `event_id`, healthchecks y `depends_on` con condición de salud en compose. | Los reintentos pueden duplicar efectos si no hay idempotencia; la consistencia entre servicio y evento no es transaccional sin outbox. |
| **Observabilidad** | Logs JSON estructurados con `correlation_id` propagado desde el front, estado de colas y DLQ en la UI de RabbitMQ, healthchecks por servicio. | Sin stack de trazas (OTel/Jaeger) no hay trazas distribuidas completas: se sigue el `correlation_id` en logs. Es una mejora futura, no parte del alcance. |
| **Coste local** | Todo contenedorizado en Docker Compose; el único coste variable es OpenAI (por token) y Qdrant/Redis/RabbitMQ/BD corren en local. | Consumo de RAM de cinco almacenes + seis servicios en una sola máquina; el rendimiento local no representa producción. |

## Notas

- El `docker-compose.yml` final (E2.2) incluye `postgres`, `mongodb`, `redis`,
  `rabbitmq` y `qdrant`; cada uno queda justificado arriba.
- Los nombres de eventos citados (`user.created`, `role.assigned`) se confirman en
  `specs/e2-08-eventos-rabbitmq.md`.
