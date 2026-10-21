# Ejercicio 4 - Diagnóstico de un incidente en microservicios

Respuesta al **punto 4 de `prueba.pdf`**. Escenario simulado en producción:

> Los usuarios no pueden guardar registros, algunos microservicios responden con errores
> 500 y hay reportes de alta latencia en las respuestas de los agentes de IA.

## Entregables

| Documento | Spec | Qué responde |
|---|---|---|
| [`incidente.md`](incidente.md) | E4.1 | Escenario, radio de alcance, 14 hipótesis priorizadas por probabilidad × impacto, señales de confirmación/descarte y criterio de rollback/escalado |
| [`plan-diagnostico.md`](plan-diagnostico.md) | E4.2 | Plan en 7 pasos con consultas sobre los logs JSON, filtros por `trace_id`/servicio/ventana, cruce con métricas, aislamiento origen vs. cascada y captura de evidencias |
| [`agentes-ia.md`](agentes-ia.md) | E4.3 | Latencia por etapa, coste de tokens, rate limiting del proveedor, cómo distinguir retrieval de LLM e infraestructura y mitigaciones |
| [`comunicacion.md`](comunicacion.md) | E4.4 | Updates por audiencia, cadencia, plantillas inicial/intermedia/resolución, cierre y criterios de escalado |

## Los primeros 15 minutos

1. **Acotar** (`plan-diagnostico.md` paso 1): `docker compose ps -a` y primer 5xx en los
   logs. Sin ventana temporal, el resto del análisis es ruido.
2. **Clasificar** (paso 3): ¿es 500 real, 403 por roles perdidos, 429 o 413 del proxy? Solo
   el 500 apunta a persistencia.
3. **Seguir una petición** (paso 2) por `X-Request-ID`/`trace_id` para ver en qué servicio y
   en qué capa muere.
4. **Descartar lo barato**: disco de PostgreSQL, conexiones y locks (paso 4), outbox y colas
   (paso 5).
5. **Decidir** con el criterio de `incidente.md`: a los 20 min sin causa raíz, rollback; a
   los 30 min sin mitigación, escalado.

## Trazabilidad con el enunciado

| Requisito del punto 4 | Dónde se cubre |
|---|---|
| Formular hipótesis (BD, comunicación, red, IA…) | `incidente.md` → tabla de H1-H14 y justificación del orden |
| Plan de diagnóstico sistemático con logs estructurados y herramientas de debugging | `plan-diagnostico.md` → 7 pasos, tabla de herramientas, comandos por capa |
| Uso de logs centralizados para identificar el problema | `plan-diagnostico.md` → pasos 2 y 3 (correlación por `trace_id`, filtros por nivel/servicio/ventana), más la brecha de no tener Loki/ELK documentada |
| Problemas propios de agentes IA (latencia, coste, rate limiting) | `agentes-ia.md` → métricas por etapa, fórmula de coste, diagnóstico de `429`, umbrales |
| Comunicación del avance a stakeholders | `comunicacion.md` → estructura, audiencias, cadencia, plantillas y escalado |

## Supuestos y límites

- **No hay stack de observabilidad centralizado**: los logs JSON van a `stdout` y se
  consultan con `docker compose logs`. El plan usa esas herramientas reales y propone
  Loki/Grafana como mejora, sin asumirlo instalado.
- **`ai-service` es E5 y aún no está desplegado**: el diagnóstico de IA se apoya en el
  diseño del flujo 4 (`docs/arquitectura/flujos-de-datos.md`) y define el contrato de
  observabilidad que E5 debe implementar. Se distingue explícitamente lo que existe de lo
  propuesto.
- **La llamada `auth-service → role-service` no propaga `X-Request-ID`**: el cruce de ese
  salto se hace por marca de tiempo y `user_id`. Es una mejora identificada, no una
  capacidad actual.
- Los umbrales de latencia/coste de IA son una propuesta inicial a validar con datos
  reales en E5.5.

## Referencias

- Arquitectura y flujos: `docs/arquitectura/diagrama.md`,
  `docs/arquitectura/flujos-de-datos.md`.
- Ejecución del stack: `docs/ejecucion.md`.
- Controles de seguridad: `docs/seguridad/owasp-api-top10.md`.
