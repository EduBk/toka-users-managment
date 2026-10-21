# E4.1 - Hipótesis del incidente

Incidente simulado: **los usuarios no pueden guardar registros, varios microservicios
responden 500 y hay reportes de alta latencia en los agentes de IA**. Este documento fija
las hipótesis, su prioridad y el criterio para decidir contención, rollback o escalado.
El plan operativo (comandos, filtros, evidencias) está en
[`plan-diagnostico.md`](plan-diagnostico.md) y el detalle de IA en
[`agentes-ia.md`](agentes-ia.md).

## Escenario

| Síntoma reportado | Traducción técnica | Endpoints candidatos |
|---|---|---|
| No se pueden guardar registros | Escrituras con 5xx o rechazadas | `POST /users`, `PATCH /users/{id}`, `POST /roles`, `PUT /roles/{id}/permissions` |
| Varios servicios con 500 | `internal_error` en el sobre de error del servicio | Cualquiera con acceso a PostgreSQL/MongoDB/RabbitMQ |
| Usuarios "sin permisos" al guardar | 403 por pérdida de roles/scopes | Escrituras que exigen `users:write`, rol `admin` |
| Latencia alta en agentes de IA | p95 alto o `429` de OpenAI | `POST /ai/ask` (E5) |

El sobre de error es homogéneo (`services/common/app_common/errors.py`):

```json
{ "code": "internal_error", "message": "Unexpected error", "details": null }
```

Un 500 real deja además un log `unhandled error` con `trace_id` y stacktrace; un 403 con
`{"code":"forbidden"}` **no** es un fallo de persistencia y descarta las hipótesis de base
de datos.

## Radio de alcance

Antes de priorizar hay que responder tres preguntas:

1. **¿Solo escritura o también lectura?** Si `GET /users` responde bien y las escrituras
   fallan, el problema está en transacciones/outbox, no en conectividad ni en JWT.
2. **¿Todos los usuarios o un subconjunto?** Si afecta a pocas cuentas, mirar primero
   roles/scopes (`role_service_unavailable`) y datos concretos, no el pool global.
3. **¿Desde cuándo?** Primer `status_code >= 500` en los logs y correlación con el último
   `docker compose up -d --build` o migración. Sin esta ventana, el resto del análisis se
   hace sobre ruido.

Tabla mínima de alcance a dejar escrita en el canal del incidente:

| Dimensión | Valor |
|---|---|
| Desde (UTC) | primer 5xx sostenido |
| Servicios afectados | los que emiten 5xx, no los que solo se quejan |
| Endpoints afectados | método + ruta + `status_code` |
| Usuarios afectados | todos / por rol / por identificador |
| Último cambio | commit, migración Alembic o variable de `.env` |

## Hipótesis priorizadas

Probabilidad (P) e impacto (I) en escala 1-5; el orden de trabajo es el score `P × I`.
Las señales concretas y los comandos para confirmarlas o descartarlas están en la tabla
siguiente y se ejecutan en el orden del plan de diagnóstico.

| # | Hipótesis | Dominio | P | I | Score |
|---|---|---|---|---|---|
| H1 | Pool de conexiones de PostgreSQL agotado en escrituras | Base de datos | 5 | 5 | 25 |
| H2 | Consulta o transacción bloqueada (lock, `idle in transaction`) | Base de datos | 4 | 5 | 20 |
| H3 | Migración o despliegue reciente incompatible (columna `NOT NULL`, índice único) | Despliegue | 4 | 5 | 20 |
| H4 | `outbox` atascado o tabla de outbox creciendo sin publicar | Mensajería | 3 | 4 | 12 |
| H12 | Agente de IA: latencia de OpenAI, prompts grandes, `429` o reintentos caros | IA | 4 | 3 | 12 |
| H7 | Disco lleno en `postgres`/`mongodb` (WAL, volumen, logs) | Infraestructura | 2 | 5 | 10 |
| H5 | RabbitMQ caído o consumidor (`audit-service`) caído con cola creciendo | Mensajería | 3 | 3 | 9 |
| H6 | `role-service` no responde y `auth-service` emite tokens sin roles/scopes | Comunicación | 3 | 3 | 9 |
| H8 | Redis caído o lento: el caché degrada a PostgreSQL y lo satura | Infraestructura | 3 | 3 | 9 |
| H9 | Contenedor reiniciando por OOM o CPU agotada en el host | Recursos | 2 | 4 | 8 |
| H10 | Red interna/DNS de Docker intermitente entre servicios | Red | 2 | 4 | 8 |
| H13 | JWKS no disponible y clave no cacheada (401 masivo, no 500) | Auth | 2 | 4 | 8 |
| H11 | Proxy Nginx devolviendo 413/502 por tamaño de payload o upstream caído | Red | 2 | 3 | 6 |
| H14 | Rate limit de login (10 req/60 s) confundido con caída (429, no 500) | Auth | 2 | 2 | 4 |

### Justificación del orden

- **H1 y H2 primero** porque explican simultáneamente "no se puede guardar" y 500 en
  varios servicios: todas las escrituras pasan por PostgreSQL y el motor se crea con
  `pool_pre_ping=True` y el pool por defecto de SQLAlchemy (5 conexiones + 10 de
  overflow por proceso). Con 4-5 servicios y arranques en paralelo se agota antes de lo
  que parece, y el síntoma típico es `TimeoutError` al pedir conexión.
- **H3 tercero** porque un cambio reciente explica un fallo súbito y global sin necesidad
  de degradación: si el primer 5xx coincide con el deploy, se investiga el deploy, no la
  infraestructura.
- **H4 y H12 (12)** empatan por motivos distintos: el patrón outbox está en la ruta de
  escritura (los casos de uso registran el evento en la misma transacción), mientras que
  el síntoma de IA es independiente del resto y se diagnostica en paralelo con
  [`agentes-ia.md`](agentes-ia.md).
- **H7 (10)** es menos probable pero catastrófica: se descarta en un comando (`df -h`).
- **H5, H6 y H8 (9)** cubren dependencias compartidas: cola, roles y caché. **H6** no
  produce 500, pero sí el "no puedo guardar" percibido: sin `role-service`,
  `HttpUserAccessProvider` devuelve roles y scopes vacíos (mínimo privilegio) y la
  escritura responde 403. Debe descartarse pronto para no perseguir un falso 500.
- **H9, H10 y H13 (8)** se confirman con una mirada a `docker stats`, logs de resolución
  DNS y el estado de JWKS.
- **H11 y H14 (6 y 4)** se descartan leyendo el `status_code`: 413/502 vienen del proxy y
  429 del límite de login, ninguno es un 500 de persistencia.

## Señales que confirman o descartan cada hipótesis

| # | Confirma | Descarta |
|---|---|---|
| H1 | `pg_stat_activity` con conexiones al límite; logs `unhandled error` con `TimeoutError`/`QueuePool`; latencia creciente solo en escrituras | Conexiones libres y `duration_ms` bajo en `request completed` de escrituras correctas |
| H2 | `pg_locks` con esperas; `state = 'idle in transaction'` con `xact_start` antiguo | Sin locks en espera y transacciones cortas |
| H3 | Primer 5xx alineado con deploy/migración; error de constraint o columna inexistente en el stacktrace | 5xx anteriores al deploy o sin migraciones pendientes |
| H4 | Filas de `outbox_events` sin `published_at` creciendo y con `last_error`; reintentos en logs del `outbox-worker` | Outbox vacía o publicando con normalidad |
| H5 | `messages_ready`/`messages_unacknowledged` creciendo; `audit-service` reiniciando; mensajes en la DLQ | Colas vacías y consumidor con `consumers = 1` |
| H6 | Log `role_service_unavailable`; 403 en escrituras; `/users/{id}/permissions` lento o con error | Roles y scopes presentes en el token emitido |
| H7 | `df -h` del contenedor de PostgreSQL/MongoDB al 100 %; errores de escritura a disco | Espacio libre suficiente |
| H8 | Logs `cache_error`/`cache_miss` masivos y escrituras de PostgreSQL disparadas | `cache_hit` normal y Redis con `PONG` |
| H9 | `docker stats` con CPU al 100 %; `OOMKilled` en `docker compose ps -a` | Recursos holgados y sin reinicios |
| H10 | Errores de resolución (`getaddrinfo`, `Name or service not known`) o timeouts entre servicios | Llamadas internas con latencia estable |
| H11 | 413/502 en el proxy; `client_max_body_size 64k` superado | Respuestas vienen del servicio, no de Nginx |
| H12 | Logs de IA con `429`, timeouts o `duration_ms` alto por etapa; coste por petición fuera de presupuesto | Etapas dentro de umbral (ver umbrales en `agentes-ia.md`) |
| H13 | 401 en cadena y `jwks` inaccesible | 200/403 en endpoints protegidos |
| H14 | 429 con `Retry-After` solo en `/auth/login` | 500 o 403 en escrituras autenticadas |

## Decisión y contención

Criterio explícito, acordado antes de tocar nada:

| Momento | Acción |
|---|---|
| T+0 a T+20 min | Diagnosticar en paralelo con contención de bajo riesgo: reiniciar el consumidor caído **después** de capturar sus logs, subir el pool con reinicio controlado si H1 está confirmada, purgar la DLQ solo si se conoce el impacto |
| T+20 min sin causa raíz identificada | **Rollback** al último deploy/migración conocido bueno (X = 20 min) |
| T+30 min sin mitigación | Escalar a líder técnico + responsable de infraestructura; declarar incidente P1 |
| Cualquier indicio de pérdida de datos, PII expuesta o corrupción | Escalar de inmediato a seguridad; no esperar a los 20 min |
| H12 confirmada | Degradar el agente (respuesta sin generación o cuota reducida) antes que tumbar el resto del sistema |

Reglas de contención:

- Un rollback se decide con evidencia, no por impaciencia: si el primer 5xx es anterior al
  deploy, revertir no arregla nada y añade riesgo.
- Reiniciar un contenedor antes de capturar logs y `docker compose ps -a` destruye la
  evidencia del post-mortem.
- No se cambia más de una variable a la vez: cada cambio se anota con hora en la línea de
  tiempo del incidente.

## Supuestos

- `ai-service` corresponde a E5 y **no está desplegado** en el compose actual; el síntoma
  de IA se diagnostica sobre el diseño del flujo 4 de `docs/arquitectura/flujos-de-datos.md`.
- El sistema no tiene stack de métricas centralizado (no hay Prometheus/Grafana/Loki en
  `docker-compose.yml`): las señales se obtienen de logs JSON a stdout, `docker stats` y
  las herramientas nativas de cada contenedor.
- El acceso a logs y a contenedores es de operación local (Docker Compose), no de un
  clúster con `kubectl`.
