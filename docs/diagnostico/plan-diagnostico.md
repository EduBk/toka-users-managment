# E4.2 - Plan de diagnóstico con logs centralizados

Plan sistemático para ir del síntoma a la causa en **7 pasos** (N = 7), sin cambiar nada
en producción hasta tener evidencia. Las hipótesis y su prioridad están en
[`incidente.md`](incidente.md); aquí está el cómo.

## Qué hay realmente para diagnosticar

| Pieza | Estado en el proyecto |
|---|---|
| Logs | JSON a `stdout` en todos los servicios (`services/common/app_common/logging.py`) con `timestamp`, `level`, `service`, `trace_id`, `logger`, `message` y campos extra por evento |
| Correlación | Nginx genera `X-Request-ID` (`$request_id`) y cada servicio lo acepta como `trace_id` (charset y longitud validados); se devuelve en la respuesta |
| Acceso HTTP | Log `request completed` (`method`, `path`, `status_code`, `duration_ms`) y `request failed` (`error`, `duration_ms`) |
| Errores 500 | Log `unhandled error` con stacktrace y `{"code":"internal_error"}` en la respuesta |
| Eventos | `event scheduled for retry`, `event sent to dead-letter queue`, `event already processed` con `event_id`, `event_type`, `attempt`, `reason` |
| Caché | `cache_hit`, `cache_miss`, `cache_error` con `key` y `operation` |
| Healthchecks | `/health` (liveness) por servicio; compose lo consulta cada 10 s con 5 reintentos |
| Logs centralizados | **No hay Loki/ELK**. La fuente es `docker compose logs`; si el incidente supera la retención del buffer, se captura a fichero antes de reiniciar contenedores |

## Herramientas

| Herramienta | Para qué | Nota |
|---|---|---|
| `docker compose logs` (JSON) | Fuente principal de evidencia | `--no-log-prefix`, `--since`, `--no-color` |
| `jq` / `Select-String` | Filtrar y agregar logs JSON | Sin `jq`, PowerShell filtra por texto |
| `docker compose ps -a` / `docker stats` | Estado y recursos de contenedores | Detecta reinicios y OOM |
| `psql` | Conexiones, locks, disco, outbox | Dentro del contenedor `postgres` |
| `redis-cli` | Aciertos/fallos de caché, memoria | Autenticación con `REDISCLI_AUTH` |
| `rabbitmqctl list_queues` | Profundidad de colas y consumidores | `messages_ready`, `messages_unacknowledged` |
| `mongosh` | Volumen de auditoría e índices | Base `audit_db`, colección `audit_entries` |
| `curl` | `/health`, JWKS, API de Qdrant (`:6333`) | Verifica dependencias sin UI |
| `py-spy dump --pid <pid>` | Stack del proceso cuando la latencia es interna | Opcional; requiere instalar en la imagen o usar `--pid host` |
| `git log` / `alembic current` | Cambios recientes y esquema aplicado | Correlaciona el inicio con un deploy |

## Paso 1 - Acotar la ventana y el alcance (5 min)

```powershell
docker compose ps                      # quién está healthy, quién reinicia
docker compose ps -a | Select-String "Exit|Restart|OOM"
docker compose logs --no-log-prefix --since 60m --no-color auth-service user-service role-service audit-service |
  jq -r 'select(.status_code >= 500) | [.timestamp,.service,.path,.status_code,.trace_id] | @tsv' |
  Select-Object -First 20
```

Sin `jq` en Windows:

```powershell
docker compose logs --no-log-prefix --since 60m auth-service user-service role-service audit-service |
  Select-String '"status_code":5' |
  Select-Object -First 20
```

Salida esperada: primer 5xx con hora, servicio y ruta. Con eso se fija la ventana del
incidente y se descarta el ruido previo. **No reiniciar nada todavía**: `docker compose
logs` pierde el histórico del contenedor al recrearlo.

## Paso 2 - Seguir una petición concreta por `trace_id`

El `trace_id` de una petición fallida se obtiene de la cabecera `X-Request-ID` de la
respuesta (DevTools → Network) o del log de acceso del servicio que la atendió.

```powershell
docker compose logs --no-log-prefix --no-color `
  auth-service user-service role-service audit-service |
  Select-String '"trace_id":"7f3a91c2d4e84b0fa1c3"'
```

Se recorre la misma petición en todos los servicios y se ordena por `timestamp`:

```powershell
docker compose logs --no-log-prefix --no-color --since 15m `
  auth-service user-service role-service audit-service |
  jq -r 'select(.trace_id == "7f3a91c2d4e84b0fa1c3") |
         [.timestamp, .service, .level, .logger, .message, (.status_code // ""), (.duration_ms // "")] | @tsv' |
  Sort-Object
```

**Limitación conocida**: la llamada `auth-service` → `role-service` usa `httpx` sin
propagar `X-Request-ID`, así que ese salto se correlaciona por `timestamp` + `user_id`
(log `role_service_unavailable`) y no por `trace_id`. Cerrar esa brecha es una acción de
mejora, no un requisito del diagnóstico inmediato.

## Paso 3 - Clasificar el error antes de mirar infraestructura

| Respuesta | Log clave | Qué significa | Ir a |
|---|---|---|---|
| 500 `internal_error` | `unhandled error` + stacktrace | Excepción no controlada en el servicio | Pasos 4-6 según el stacktrace |
| 403 `forbidden` | `role_service_unavailable` | Token sin roles/scopes: no es fallo de guardado | Paso 6 (dependencias) |
| 429 `rate_limited` | `rate_limited` (login: 10 req/60 s) | Límite por cliente, no caída | Contención, no diagnóstico |
| 401 `unauthorized` | `unauthorized` | Token expirado/revocado o JWKS no disponible | Paso 6 |
| 413/502 | log de Nginx, no del servicio | Payload > 64k o upstream caído | Logs del proxy, no los del servicio |

El stacktrace del `unhandled error` es la evidencia más valiosa: distingue un
`TimeoutError` de pool de un error de constraint sin necesidad de más comandos.

## Paso 4 - Capa de datos (PostgreSQL, 10 min)

```powershell
# Conexiones por estado en la base afectada
docker compose exec -T postgres psql -U postgres -d users_db -c `
  "select state, count(*) from pg_stat_activity where datname = current_database() group by state;"

# Límite del servidor y consultas/transacciones más antiguas
docker compose exec -T postgres psql -U postgres -d users_db -c "show max_connections;"
docker compose exec -T postgres psql -U postgres -d users_db -c `
  "select pid, state, wait_event_type, now() - xact_start as age, left(query, 80) as query
     from pg_stat_activity where datname is not null order by age desc nulls last limit 10;"

# Locks en espera y espacio en disco
docker compose exec -T postgres psql -U postgres -d users_db -c "select count(*) from pg_locks where not granted;"
docker compose exec -T postgres df -h /var/lib/postgresql/data
```

Repetir en `auth_db` y `roles_db`. Lectura: `active` alto con `wait_event_type = 'Client'`
suele ser pool agotado; `idle in transaction` con `age` de minutos, un lock retenido.

## Paso 5 - Mensajería y ruta de escritura asíncrona

El evento de dominio se escribe en `outbox_events` **en la misma transacción** que el
agregado, así que una tabla de outbox bloqueada o llena también rompe el `POST`.

```powershell
# Outbox pendiente por base (users_db, roles_db, auth_db)
docker compose exec -T postgres psql -U postgres -d users_db -c `
  "select count(*) as pendientes,
          count(*) filter (where attempts >= 5) as agotados,
          max(now() - created_at) as antiguedad
     from outbox_events where published_at is null;"

# Colas y consumidores
docker compose exec -T rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
docker compose logs --no-log-prefix --since 30m audit-service |
  Select-String 'dead-letter|scheduled for retry|already processed'

# Auditoría persistida en la última hora (compone la traza con los eventos)
docker compose exec -T mongodb mongosh --quiet `
  -u $env:MONGO_INITDB_ROOT_USERNAME -p $env:MONGO_INITDB_ROOT_PASSWORD `
  --authenticationDatabase admin audit_db `
  --eval 'db.audit_entries.countDocuments({occurred_at: {$gte: new Date(Date.now() - 3600e3)}})'
```

Firma de outbox atascado: pendientes crecientes + `antiguedad` de minutos + `last_error`
repetido. Firma de consumidor caído: `messages_ready` creciendo con `consumers = 0`.

## Paso 6 - Dependencias, recursos y cambios recientes

```powershell
docker stats --no-stream                                                  # CPU/RAM por contenedor
curl.exe -s -o NUL -w "%{http_code}`n" http://localhost:6333/collections   # Qdrant (RAG)
docker compose exec -T redis sh -lc 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli INFO stats' | Select-String 'keyspace'
docker compose exec -T auth-service python -c "import urllib.request as u; print(u.urlopen('http://auth-service:8000/.well-known/jwks.json', timeout=3).status)"
docker compose logs --no-log-prefix --since 60m auth-service user-service role-service audit-service |
  Select-String 'role_service_unavailable|cache_error|jwks'
git log --oneline -5                      # si el repo está disponible en el host
docker compose exec -T user-service alembic current   # versión de esquema aplicada
```

Comportamientos de degradación que hay que tener presentes para no diagnosticar mal:

| Dependencia caída | Efecto real | Log |
|---|---|---|
| Redis | El caché degrada a PostgreSQL y el rate limit queda *fail-open* | `cache_error`, `rate_limit_unavailable` |
| RabbitMQ | La escritura commitea; el outbox reintenta con backoff (5 intentos, 1 s → 30 s) | `event scheduled for retry` |
| `role-service` | Login/refresh emiten token sin roles/scopes → 403 en escrituras | `role_service_unavailable` |
| JWKS de `auth-service` | 401 si la clave no está cacheada en el proceso | `unauthorized` |

## Paso 7 - Aislar el origen frente al fallo en cascada

Regla: el primer servicio que degrada es el que **falla sin que su dependencia esté
lenta**. Se decide con tres comprobaciones:

1. Orden temporal: primer `request failed`/`duration_ms` anómalo por `timestamp`.
2. Dirección de la dependencia: si A llama a B y B responde en 50 ms pero A tarda 2 s, el
   problema es A (espera, retry o lock interno).
3. Simetría: si varios servicios independientes fallan a la vez, el origen es compartido
   (PostgreSQL, RabbitMQ, host), no uno de ellos.

| Patrón observado | Interpretación |
|---|---|
| Latencia alta en todas las llamadas a PostgreSQL y sana la del resto | Origen: base de datos |
| `audit-service` acumula cola pero las escrituras funcionan | Origen: consumidor; no es la causa del 500 |
| 403 en escrituras con servicios sanos | Origen: `role-service` o su timeout de 2 s |
| Errores solo en `ai-service` con el resto sano | Origen: proveedor de IA (ver `agentes-ia.md`) |
| 5xx inmediatos en varios servicios tras deploy | Origen: despliegue/migración (rollback) |

## Evidencia que se captura para el post-mortem

Antes de aplicar el rollback o reiniciar:

```powershell
New-Item -ItemType Directory -Force capturas\incidente | Out-Null
docker compose ps -a                       > capturas\incidente\ps.txt
docker compose logs --no-log-prefix --since 2h `
  auth-service user-service role-service audit-service > capturas\incidente\logs.jsonl
docker stats --no-stream                   > capturas\incidente\stats.txt
docker compose exec -T rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers > capturas\incidente\colas.txt
```

El paquete debe incluir además:

- Línea de tiempo con hora UTC de: primer síntoma, primera hipótesis, cada acción
  aplicada y quién la aplicó.
- `trace_id` de 3-5 peticiones fallidas representativas.
- Consultas y salidas de `pg_stat_activity`, `pg_locks` y `outbox_events`.
- Diff de configuración (`git diff` de `.env`/compose) y versión de esquema por servicio.
- Qué se descartó y con qué evidencia (tan importante como lo que se confirmó).

## Brechas de observabilidad detectadas (acciones de mejora)

| Brecha | Impacto en el diagnóstico | Acción propuesta |
|---|---|---|
| Sin stack de logs/métricas centralizado | Solo hay histórico mientras el contenedor existe | Añadir Loki + Grafana (o Promtail) al compose, o `json-file` con rotación y volumen |
| `X-Request-ID` no se propaga en llamadas servicio→servicio | El salto `auth-service → role-service` no se correlaciona | Propagar la cabecera en `HttpUserAccessProvider` |
| `/health` es solo liveness | Un contenedor sano puede tener la BD caída | Añadir `/ready` con comprobación de dependencias |
| Sin circuit breaker en `auth-service → role-service` | El timeout de 2 s se paga en cada login durante una caída | Circuit breaker + caché breve de roles |
| Sin métricas de negocio (5xx, p95, profundidad de cola) | El análisis depende de leer logs a mano | Exportar contadores Prometheus por servicio |
