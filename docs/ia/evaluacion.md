# Evaluación del agente (E5.5)

## Métricas por invocación

Cada respuesta registra en `domain.agent.models.AgentAnswer` y en el log
`ai_answer`:

| Métrica | Campo | Uso |
|---|---|---|
| Latencia total | `latency.total_ms` | SLA percibido |
| Latencia por etapa | `latency.embedding_ms`, `retrieval_ms`, `llm_ms` | Localizar el cuello de botella |
| Tokens | `usage.input_tokens`, `output_tokens`, `total_tokens` | Coste y tamaño de contexto |
| Coste | `usage.cost_usd` | Presupuesto por consulta |
| Fuentes | `len(sources)` | Grounding de la respuesta |
| Calidad | `quality.passed`, `quality.issues` | Validación automática |

El coste se estima con precios por millón de tokens configurables
(`CHAT_INPUT_PRICE_PER_MILLION`, `CHAT_OUTPUT_PRICE_PER_MILLION`,
`EMBEDDING_INPUT_PRICE_PER_MILLION`). Cambiar de modelo o de tarifa no requiere
tocar código.

Con la configuración por defecto (OpenCode Go + `glm-5.3-flash`) el chat cuesta
`0.15` / `0.50` USD por 1M de tokens y los embeddings son locales (FastEmbed), por
lo que su coste es `0`. Si se usa `EMBEDDING_PROVIDER=openai`, hay que fijar el
precio real de `text-embedding-3-small` (~0.02 USD/1M).

Los errores del proveedor también se cuentan (`outcome="error"`), además de
`answered` y `no_context`.

## Consulta de métricas

```powershell
curl.exe -s -H "Authorization: Bearer $TOKEN" http://localhost:3000/api/ai/metrics
```

`GET /ai/metrics` (rol `admin`) devuelve, sobre una ventana deslizante en memoria
(`METRICS_WINDOW_SIZE`, 200 invocaciones por réplica):

```json
{
  "invocations": 12,
  "window_size": 200,
  "avg_latency_ms": 1834.2,
  "p95_latency_ms": 2910.5,
  "input_tokens": 18240,
  "output_tokens": 3110,
  "cost_usd": 0.005421,
  "by_outcome": {"answered": 11, "no_context": 1}
}
```

Los logs JSON (`ai_answer`) son la fuente para un dashboard centralizado cuando
hay varias réplicas; la métrica en memoria es por proceso.

## Validación básica de calidad

`domain/agent/quality.py` marca:

| Check | Issue | Regla |
|---|---|---|
| Respuesta vacía | `empty_answer` | — |
| Demasiado larga | `answer_too_long` | `> 4000` caracteres |
| Sin grounding | `missing_sources` | Sin fuentes y sin admitir "sin información" |
| PII | `pii_in_answer` | Email o teléfono en la respuesta; se redacta antes de devolverla |

La respuesta de "sin información suficiente" se considera válida cuando no hay
contexto: admitir el hueco es el comportamiento esperado.

## Suite de evaluación reproducible

```powershell
cd services/ai-service
py -m eval.run_eval          # tabla de resultados; sale 1 si falla una expectativa
py -m eval.run_eval --json   # reporte JSON completo
```

- Ejecuta el pipeline real: chunking, embeddings, Qdrant en memoria, retrieval,
  prompt versionado, validación de calidad y métricas.
- Proveedor **stub determinista** (bolsa de palabras sobre el vocabulario del
  corpus + LLM que cita el fragmento): sin API key, sin red y con resultados
  reproducibles.
- Dataset: `services/ai-service/eval/dataset.json`. Cada caso declara
  expectativas: `sources_min`, `no_context`, `quality`, `no_pii`,
  `max_latency_ms`, `must_include`.
- Cubre los criterios del enunciado: respuesta con fuentes, admisión de "sin
  información", ausencia de PII y latencia.

Formato de un caso:

```json
{
  "id": "validacion-jwt",
  "question": "¿Cómo se validan los tokens JWT entre microservicios?",
  "expect": {"sources_min": 1, "quality": true, "max_latency_ms": 2000}
}
```

Para evaluar con el proveedor real, se puede apuntar `AskAgent` al
`OpenAICompleter` (es el mismo caso de uso que usa la API) y reutilizar el
dataset; el harness no depende del proveedor.

## Rate limiting y resiliencia

- **Por usuario**: `RateLimitPolicy` sobre Redis, clave `ai:ask:<sub>`,
  `AI_RATE_LIMIT_REQUESTS` (20) por `AI_RATE_LIMIT_WINDOW_SECONDS` (60). Si Redis
  no responde, se permite la petición (fail-open, igual que la caché) y se
  registra `rate_limit_unavailable`.
- **Proveedor**: reintentos con backoff exponencial (`AI_MAX_RETRIES`,
  `AI_RETRY_BACKOFF_SECONDS`) ante 429, timeout, error de conexión y 5xx. Un 429
  respeta `Retry-After` si viene en la respuesta. Agotados los intentos: `429` o
  `503` con el esquema de error común.
- **Sin contexto**: no se llama al LLM, por lo que una pregunta fuera del corpus
  no consume tokens de generación.

## Optimización de costes

| Medida | Efecto en coste |
|---|---|
| Modelo barato por defecto (`glm-5.3-flash` en OpenCode Go) | Input/output ~6× más barato que `kimi-k2.7-code` |
| Embeddings locales con FastEmbed | Coste de embeddings = 0 y sin clave adicional |
| `RETRIEVAL_MIN_SCORE` + respuesta sin LLM si no hay contexto | Evita generaciones inútiles |
| `TOP_K` (4) y `CHUNK_MAX_CHARS` (800) | Acota el contexto enviado |
| `MAX_ANSWER_TOKENS` (1200) | Acota la salida (incluye tokens de razonamiento) |
| Embeddings en lotes de 64 | Menos llamadas, mismo tokens |
| Reindexado por hash | No re-embebe documentos sin cambios |
| `MAX_QUESTION_CHARS` (2000) | Evita prompts gigantes |
| `GET /ai/metrics` + logs por etapa | Permite detectar consultas y etapas caras |

Los precios se revisan contra la tarifa vigente del proveedor; están en `.env`,
no en el código.

### Caché de respuestas

No se implementó caché de respuestas completa: dos preguntas idénticas pueden
tener contexto distinto (documentos reindexados, permisos del usuario, datos
vivos de usuarios/roles) y una respuesta obsoleta es peor que una llamada extra.
Lo que sí se evita es gasto innecesario: reindexado por hash, embeddings en lote,
umbral de relevancia y no invocar al LLM cuando no hay contexto.

Si se necesita, la evolución natural es una clave
`sha256(pregunta normalizada + document + top_k + prompt_version)` en Redis con
TTL corto (por ejemplo 10 minutos), invalidada al ejecutar `POST /ai/reindex` y
excluyendo las consultas con `include_system_data=true` (datos vivos). El punto
de extensión es un puerto `AnswerCache` junto a `MetricsStore`; el caso de uso no
cambiaría.
