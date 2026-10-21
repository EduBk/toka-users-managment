# Ejemplo de uso del agente integrado (E5.5)

Ejemplo completo contra el stack local: el agente responde con la documentación
del repositorio y, opcionalmente, con datos agregados de `user-service` y
`role-service`.

> En la UI está disponible en **Asistente** (`/assistant`) para usuarios con
> scope `ai:use`: chat con fuentes, latencia, tokens y coste, historial corto y
> opción de incluir datos del sistema. Ver el paso 8.

## 1. Arrancar el stack

```powershell
# .env con OPENAI_API_KEY (OpenCode Go / OpenAI), OPENAI_BASE_URL y OPENAI_MODEL
docker compose up -d --build
docker compose ps            # ai-service debe aparecer healthy
```

## 2. Login (auth-service a través del proxy del frontend)

```powershell
# Credenciales de desarrollo: ver docs/ejecucion.md (no se versionan)
$email = $env:BOOTSTRAP_ADMIN_EMAIL
$password = $env:BOOTSTRAP_ADMIN_PASSWORD

$login = Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/auth/login `
  -ContentType 'application/json' `
  -Body (@{ email = $email; password = $password } | ConvertTo-Json)

$env:TOKEN = $login.access_token
```

## 3. Indexar la documentación (una vez, y tras cambios en `docs/`)

Desde la UI: **Asistente → Reindexar documentación** (solo `admin`). Equivalente
por API:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/ai/reindex `
  -Headers @{ Authorization = "Bearer $env:TOKEN" }
```

```json
{
  "documents_seen": 13,
  "documents_indexed": 13,
  "documents_skipped": 0,
  "documents_deleted": 0,
  "chunks_indexed": 208,
  "embedding_tokens": 91240
}
```

Es idempotente: repetirlo sin cambios devuelve `documents_skipped = documents_seen`
y no duplica vectores.

## 4. Preguntar al agente (RAG)

```powershell
$body = @{ question = '¿Cómo se validan los tokens JWT entre microservicios?' } |
  ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/ai/ask `
  -Headers @{ Authorization = "Bearer $env:TOKEN" } `
  -ContentType 'application/json' -Body $body
```

```json
{
  "answer": "Cada servicio valida el JWT localmente con la clave pública publicada en el JWKS de auth-service, sin llamar al emisor en cada petición [1]. Fuentes: [1] arquitectura/flujos-de-datos.md — Validación de tokens.",
  "sources": [
    {
      "document": "arquitectura/flujos-de-datos.md",
      "section": "Validación de tokens",
      "score": 0.83
    }
  ],
  "usage": {
    "input_tokens": 1840,
    "output_tokens": 96,
    "total_tokens": 1936,
    "cost_usd": 0.000334
  },
  "latency": {
    "total_ms": 1740.5,
    "embedding_ms": 210.2,
    "retrieval_ms": 32.1,
    "llm_ms": 1498.2
  },
  "model": "gpt-4o-mini",
  "prompt_version": "v1",
  "quality": {"passed": true, "issues": []}
}
```

Pregunta fuera del corpus (no consume tokens de generación):

```json
{
  "answer": "No tengo información suficiente en la documentación disponible para responder esa consulta...",
  "sources": [],
  "quality": {"passed": true, "issues": []}
}
```

## 5. Pregunta sobre datos del sistema (integración con user/role services)

```powershell
$body = @{
  question = '¿Cuántos usuarios hay por estado y qué roles existen?'
  include_system_data = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://localhost:3000/api/ai/ask `
  -Headers @{ Authorization = "Bearer $env:TOKEN" } `
  -ContentType 'application/json' -Body $body
```

El agente reenvía el token del usuario a `user-service` y `role-service`; si no
tiene permisos de lectura, responde solo con RAG. A la respuesta se añade una
fuente `user-service` y el LLM recibe únicamente agregados (totales, estados y
nombres de roles), nunca emails ni nombres.

## 6. Consultar latencia y coste

```powershell
Invoke-RestMethod -Uri http://localhost:3000/api/ai/metrics `
  -Headers @{ Authorization = "Bearer $env:TOKEN" }
```

Devuelve invocaciones, latencia media y p95, tokens y coste acumulado de la
ventana en memoria, más el desglose por resultado (`answered`, `no_context`,
`error`).

## 7. Cómo se integra con el sistema existente

```text
frontend (Nginx /api/ai/*)
        |
        v
ai-service (FastAPI) --validación JWT local con JWKS de auth-service
        |                               |
        |-- OpenAI (embeddings + chat)  |
        |-- Qdrant (docs indexados)     |
        |-- user-service / role-service (opcional, token del usuario)
        |-- Redis (rate limit por sub)
```

- Mismos contratos que el resto de servicios: errores `{code, message, details}`,
  `X-Request-ID` para correlación y logs JSON.
- El token se valida en el propio servicio con el JWKS de `auth-service`; no hay
  llamada por petición al emisor.
- `ai:use` ya está sembrado en los roles `admin` y `user` de `role-service`.
- El reindexado y las métricas exigen rol `admin`; las preguntas exigen scope
  `ai:use`.

Ejemplo equivalente con `curl.exe`:

```powershell
curl.exe -s -X POST http://localhost:3000/api/ai/ask `
  -H "Authorization: Bearer $env:TOKEN" -H "Content-Type: application/json" `
  -d '{\"question\":\"¿Cómo se publican los eventos de dominio?\"}'
```

## 8. Uso desde la UI

1. Inicia sesión en <http://localhost:3000> con una cuenta que tenga `ai:use`
   (los roles `admin` y `user` lo incluyen).
2. Abre **Asistente** en la barra lateral (`/assistant`).
3. Si es el primer uso (o cambió `docs/`), un `admin` pulsa **Reindexar
   documentación** y confirma. El resumen indica documentos y fragmentos
   procesados; la primera vez descarga el modelo local de embeddings.
4. Escribe la pregunta y pulsa `Intro` (o el botón **Preguntar**). Cada respuesta
   muestra:
   - el texto con citas `[n]` y la lista de **Fuentes** (`documento — sección`);
   - latencia total en ms, tokens totales, coste estimado, modelo y versión de
     prompt;
   - un aviso si la validación de calidad detectó algún problema.
5. Si la cuenta tiene `users:read`, activa **Incluir datos del sistema** para
   preguntas sobre usuarios y roles (solo se envían agregados al LLM).
6. Usa **Nueva conversación** para limpiar el historial. El historial enviado al
   agente se limita a los últimos 6 mensajes.

Si el asistente responde "No tengo información suficiente" nada más desplegar,
un admin debe ejecutar antes `POST /ai/reindex` (paso 3): el corpus se indexa bajo
demanda.
