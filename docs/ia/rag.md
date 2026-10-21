# RAG y pipeline de embeddings (E5.2 / E5.3)

El `ai-service` responde preguntas sobre el propio sistema combinando dos fuentes
de contexto:

1. **Documentación** del repositorio, indexada en Qdrant (RAG).
2. **Datos agregados** de `user-service` y `role-service`, consultados en vivo con
   el token del usuario que pregunta (opcional, `include_system_data`).

## Corpus y chunking

- Fuente: `docs/**/*.md`, montado de solo lectura en `/app/docs`
  (`DOCS_PATH`). Se descartan archivos vacíos y cualquier extensión distinta de
  `.md` (los SVG de `docs/arquitectura/svg/` no se indexan).
- El documento se parte por encabezados Markdown; cada fragmento guarda la
  sección a la que pertenece.
- Tamaño y solapamiento configurables: `CHUNK_MAX_CHARS` (800) y
  `CHUNK_OVERLAP` (100). Los párrafos más largos que el límite se cortan en
  ventanas del mismo tamaño, de modo que ningún fragmento supera el límite.
- Metadatos por vector: `document`, `section`, `text`, `doc_hash`, `chunk_index`
  y `updated_at` (fecha del archivo). `document` es un índice de payload
  filtrable en Qdrant.

## Embeddings e idempotencia

- **Proveedor local por defecto**: `EMBEDDING_PROVIDER=fastembed` con
  `FASTEMBED_MODEL` (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`,
  384 dimensiones, multilingüe). Corre en CPU dentro del contenedor: sin clave y
  sin coste por token. El modelo se descarga en la primera indexación y queda en
  el volumen `fastembed_cache` (`/models`).
- Alternativa: `EMBEDDING_PROVIDER=openai` con `EMBEDDING_MODEL`
  (`text-embedding-3-small`) y una clave real de OpenAI; entonces sí se factura
  (`EMBEDDING_INPUT_PRICE_PER_MILLION`).
- Los fragmentos se envían en lotes de `EMBEDDING_BATCH_SIZE` (64) para reducir
  llamadas.
- Colección versionada por modelo: `QDRANT_COLLECTION`
  (`system_docs_fastembed_v1`). Si se cambia el proveedor o el modelo hay que
  cambiar la colección y reindexar (las dimensiones no son compatibles).
- **Re-ingesta idempotente**:
  - Se calcula `sha256` del texto del documento.
  - Si el hash coincide con el ya indexado, el documento se omite.
  - Cada punto usa un `uuid5(doc_hash, document, chunk_index)`, así que repetir
    la carga nunca duplica vectores.
  - Si el documento cambió, se borran sus puntos anteriores antes de insertar los
    nuevos; los documentos que ya no existen en el corpus también se eliminan.

## Pipeline

```text
docs/**/*.md
  -> MarkdownDocumentLoader (lectura recursiva, fecha de modificación)
  -> chunk_document (secciones + ventanas configurables)
  -> FastEmbedEmbeddings u OpenAIEmbeddings (lotes de 64)
  -> QdrantVectorStore.upsert (uuid5 determinista, payload con doc_hash)
```

Se ejecuta con el botón **Reindexar documentación** de `/assistant` (solo
`admin`) o con `POST /ai/reindex`. Es incremental: solo gasta tiempo/tokens en
documentos nuevos o modificados. La primera vez descarga el modelo local.

## Retrieval y generación

```text
pregunta -> sanitize_question -> embedding de la consulta
        -> Qdrant search (top_k, min_score, filtro opcional por document)
        -> contexto numerado [1]..[n] + historial corto
        -> system prompt + plantilla rag -> OpenAI chat
        -> respuesta + fuentes + uso de tokens + latencia por etapa
```

- `top_k` por defecto `TOP_K` (4), ajustable por petición (1..20).
- `RETRIEVAL_MIN_SCORE` (0.2) descarta fragmentos poco relevantes. Si no queda
  ninguno **no se llama al LLM**: se devuelve la respuesta de "sin información
  suficiente" (menos coste y menos alucinación).
- Filtro opcional `document` para preguntar sobre un archivo concreto.
- Historial: máximo 6 mensajes (`user` / `assistant`), recortado a 2000 caracteres.
- El chat usa cualquier endpoint compatible con OpenAI vía `OPENAI_BASE_URL`. Por
  defecto OpenCode Go (`https://opencode.ai/inference/go/openai/v1`) con
  `glm-5.3-flash`; el servicio envía `x-opencode-session` (id de usuario) y un
  `User-Agent` propio, como recomienda Go. También sirve OpenAI directamente
  (`https://api.openai.com/v1`) cambiando base y modelo.

## Integración con los microservicios

`include_system_data=true` añade un resumen de `user-service` (`GET /users`) y
`role-service` (`GET /roles`):

- Se reenvía el `Authorization` del usuario; si no tiene `users:read` o
  `roles:read`, el servicio responde 403 y el resumen se omite sin fallar.
- Solo se envían al LLM **agregados** (total de usuarios, conteo por estado y
  nombres de roles). Nunca emails, nombres ni otros datos personales.
- La fuente `user-service` se añade a `sources` para que la respuesta sea
  trazable.

## Errores

| Situación | Respuesta |
|---|---|
| Sin token / token inválido | `401` `missing_token` / `invalid_token` |
| Sin scope `ai:use` | `403` `insufficient_scope` |
| Rate limit propio (Redis, por `sub`) | `429` `rate_limited` + `Retry-After` |
| OpenAI devuelve 401 (clave inválida) | `503` `ai_not_configured` |
| Modelo deshabilitado o inexistente (403/404/400) | `503` `ai_model_unavailable` |
| OpenAI devuelve 429 | `429` `ai_rate_limited` + `Retry-After` |
| OpenAI caído, timeout o 5xx tras reintentos | `503` `ai_unavailable` |
| Qdrant caído | `503` `ai_unavailable` |
| Pregunta vacía | `400` `invalid_question` / `422` de validación |
