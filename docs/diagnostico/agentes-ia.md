# E4.3 - Problemas específicos de agentes de IA

Diagnóstico de los tres síntomas propios de un agente: **alta latencia, coste de tokens y
`429` (rate limiting)**. Se apoya en el flujo 4 de
`docs/arquitectura/flujos-de-datos.md`: `POST /ai/ask` → embedding (OpenAI) → búsqueda
top-k en Qdrant → chat completion (OpenAI).

> **Estado**: `ai-service` corresponde a E5 y todavía no está desplegado en
> `docker-compose.yml`. Por eso este documento define el diagnóstico esperado y el
> **contrato de observabilidad que E5.1/E5.5 deben implementar**; las métricas marcadas
> como propuestas no existen aún y no deben darse por implementadas.

## Por qué la latencia de un agente no se diagnostica como la de un CRUD

Una petición de usuario hace, como mínimo, dos llamadas a un proveedor externo y una a la
vector DB dentro del mismo request. La latencia total es la suma de etapas con colas y
reintentos en medio, y el coste crece con los tokens, no con el número de peticiones. Eso
obliga a medir **por etapa** antes de decidir nada.

## Causas típicas de alta latencia

| Etapa | Causa | Señal | Cómo se confirma |
|---|---|---|---|
| Embedding | Segunda llamada al proveedor por consulta; se puede reutilizar caché | `latency_embedding_ms` alta con `tokens_input` pequeño | Comparar con el percentil de una consulta idéntica ya cacheada |
| Retrieval | Índice sin filtros, `top_k` grande, payloads pesados, cold start de Qdrant | `latency_retrieval_ms` alta; Qdrant responde lento sin carga de LLM | `GET /collections` en `:6333` y repetir la búsqueda con `top_k` menor |
| Generación | Modelo grande, `max_tokens` alto, respuesta larga, streaming desactivado | `latency_llm_ms` domina el total; `tokens_output` alto | Probar el mismo prompt con `max_tokens` menor y comparar |
| Prompt | Contexto inflado, few-shot excesivo, documentos duplicados | `tokens_input` muy por encima del presupuesto por petición | Revisar el `system prompt` versionado y el `top_k` efectivo |
| Cola interna | Concurrencia limitada y backlog de peticiones (un worker, muchas consultas) | `queue_wait_ms` alto con etapas individuales normales | `docker stats` del `ai-service` y nº de peticiones en vuelo |
| Reintentos | Backoff ante `429`/timeout que se suma a la latencia percibida | `attempts > 1` y `latency_total_ms` ≈ suma de intentos | Log `attempt` por petición |
| Red/TLS | Salida a internet lenta o inestable | Latencia alta en ambas llamadas a OpenAI, no en Qdrant | Probar Qdrant (interno) contra OpenAI (externo) |

## Métricas a revisar

Contrato propuesto para el log `ai_request_completed` (una línea JSON por petición):

```json
{
  "timestamp": "2026-10-21T14:32:11.482Z",
  "level": "INFO",
  "service": "ai-service",
  "trace_id": "7f3a91c2d4e84b0fa1c3",
  "logger": "ai.request",
  "message": "ai_request_completed",
  "user_id": "uuid",
  "model": "gpt-4o-mini",
  "latency_embedding_ms": 210,
  "latency_retrieval_ms": 45,
  "latency_llm_ms": 1830,
  "latency_total_ms": 2085,
  "tokens_input": 1420,
  "tokens_output": 310,
  "cost_usd": 0.0004,
  "retrieval_hits": 5,
  "attempts": 1,
  "cache_hit": false,
  "status": "ok"
}
```

| Métrica | Uso | Umbral propuesto |
|---|---|---|
| `latency_total_ms` p95 / p99 | Salud percibida | p95 ≤ 6 s, p99 ≤ 10 s |
| `latency_embedding_ms`, `latency_retrieval_ms`, `latency_llm_ms` | Atribuir la latencia a una etapa | cada etapa < 60 % del total de forma sostenida |
| `tokens_input` / `tokens_output` por petición | Detectar prompts inflados | input ≤ 2 000, output ≤ 800 |
| `cost_usd` por petición y por día | Coste | ≤ presupuesto diario configurado |
| `cache_hit` (embeddings y respuestas) | Eficiencia | ≥ 30 % en consultas repetidas |
| `http_429_rate` | Rate limiting del proveedor | < 1 % en 5 min |
| `attempts` | Reintentos y bucles | media ≤ 1,2 |
| `timeouts` | Red/proveedor | < 1 % en 5 min |

Ninguna de estas métricas debe hardcodear precios: la tarifa del modelo va en
configuración (`AI_PRICE_INPUT_PER_1M`, `AI_PRICE_OUTPUT_PER_1M`) y el cálculo del coste
se hace en el servicio.

## Analizar el coste de tokens

```
cost_usd = tokens_input / 1e6 * precio_input + tokens_output / 1e6 * precio_output
```

Firmas de coste anómalo:

- **Prompt inflado**: `tokens_input` alto con `retrieval_hits` bajo → se está enviando
  contexto irrelevante o el `system prompt` se duplica por petición.
- **Respuesta excesiva**: `tokens_output` alto con preguntas cortas → `max_tokens` sin
  acotar o prompt que invita a extenderse.
- **Bucle de reintentos caros**: `attempts > 1` **y** `tokens_input > 0` en cada intento →
  se paga el prompt completo varias veces por el mismo error (timeout o `429`).
- **Duplicación por cliente**: mismo `user_id` y misma pregunta en pocos segundos → falta
  caché de respuestas o debounce en la UI.

Consulta de coste agregado (una vez exista el contrato de log):

```powershell
docker compose logs --no-log-prefix --since 24h ai-service |
  jq -s '[.[] | select(.message == "ai_request_completed") | .cost_usd] | add'
```

## Diagnosticar rate limiting del proveedor

| Señal | Interpretación | Acción |
|---|---|---|
| `429` con `Retry-After` | Cuota RPM/TPM alcanzada | Respetar `Retry-After`, backoff exponencial con jitter |
| `429` sin `Retry-After` y `attempts` alto | Reintentos agresivos propios | Backoff + circuit breaker; no reintentar en bucle cerrado |
| `429` solo de un `user_id` | Abuso o integración defectuosa | Límite por cliente en `ai-service` (Redis, igual que E2.11) |
| `429` global a una hora concreta | Pico de uso legítimo | Cola con concurrencia limitada y cuota por usuario |

Hoy **no existe** límite de tasa en la ruta de IA (solo el rate limit de `/auth/login`,
10 req/60 s por cliente). Es un requisito de E5.1: cuota por usuario/día + concurrencia
máxima hacia el proveedor, con *fail-closed* en IA (a diferencia del caché, que es
*fail-open*).

## Cómo distinguir retrieval, LLM e infraestructura

| Comportamiento | Conclusión |
|---|---|
| Embedding y retrieval rápidos, generación lenta | LLM: modelo, `max_tokens` o proveedor |
| Embedding lento, retrieval rápido | Proveedor de embeddings o red de salida |
| Retrieval lento, proveedor rápido | Qdrant: índice, `top_k`, cold start o recursos |
| Todas las etapas lentas por igual, sin carga | Host/contenedor: CPU, memoria o red del nodo |
| Etapas rápidas y total alto | Cola interna o espera de concurrencia |
| Total alto solo en peticiones con `attempts > 1` | Reintentos: rate limit o timeouts |

## Mitigaciones

| Medida | Latencia | Coste | Nota |
|---|---|---|---|
| Streaming de la respuesta | Percibida ↓↓ (real =) | = | Requiere soporte SSE en el proxy |
| Caché de embeddings por hash del texto | ↓ | ↓↓ | TTL corto; el texto normalizado como clave |
| Caché de respuestas para preguntas repetidas | ↓↓ | ↓↓ | Incluir versión del prompt en la clave |
| Reducir `top_k` y recortar contexto | ↓ | ↓↓ | Validar que no baja la calidad (E5.5) |
| `max_tokens` acotado por caso de uso | ↓ | ↓ | Evita respuestas eternas |
| Timeout + circuit breaker hacia el proveedor | ↓ (falla rápido) | ↓ | Degradar a "sin generación" en vez de 500 |
| Cola con concurrencia limitada | ↑ en picos | = | Protege la cuota del proveedor |
| Cuota por usuario/día | = | ↓↓ | Corta el abuso antes de llegar al proveedor |
| Modelo pequeño para clasificar/enrutar | ↓ | ↓ | Solo si la calidad se mantiene |

Las mitigaciones deben atacar **coste y latencia**; el streaming solo mejora la
percepción, no el gasto.

## Umbrales y reporte

| Alerta | Condición | Destino |
|---|---|---|
| Latencia | p95 > 6 s durante 10 min | Canal de guardia + dashboard |
| Coste | gasto diario > 80 % del presupuesto | Aviso a negocio y al owner del servicio |
| Rate limit | `429` > 1 % de peticiones en 5 min | Guardia técnico |
| Errores | 5xx de `ai-service` > 2 % en 5 min | Guardia técnico |
| Calidad | respuestas "sin información suficiente" > 30 % | Revisión de retrieval/prompt (E5.5) |

Reporte mínimo: panel con p95 por etapa, coste acumulado del día, ratio de `429`, tasa de
acierto de caché y número de peticiones por usuario. Un resumen diario del coste evita
descubrir el gasto a fin de mes.

## Supuestos

- El proveedor es OpenAI (decisión de `specs/README.md`); si se cambia a Azure OpenAI, las
  métricas y el contrato de log se mantienen y solo cambia la configuración.
- Los umbrales son una propuesta inicial a validar con datos reales en E5.5.
- Las cuotas del proveedor (RPM/TPM) dependen del plan contratado: se leen de configuración,
  no se asumen.
