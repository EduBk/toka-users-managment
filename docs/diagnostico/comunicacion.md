# E4.4 - Comunicación a stakeholders

Cómo se informa del incidente mientras se diagnostica y cómo se cierra. El objetivo es
que negocio entienda **qué deja de funcionar y cuándo vuelve**, y que el equipo técnico
tenga el detalle sin ruido.

## Principios

- **Impacto antes que causa.** Nadie fuera del equipo necesita saber que el pool estaba
  agotado; sí necesita saber que no se pueden crear usuarios.
- **Un solo owner de la comunicación.** Una persona emite los updates oficiales; el resto
  del equipo aporta detalle en el hilo técnico, no en el canal de negocio.
- **No especular.** Se comunica lo confirmado; las hipótesis se etiquetan como tales.
- **Sin ETA inventada.** Si no hay base para un tiempo, se da el siguiente hito ("próximo
  update en 30 min"), no una promesa.
- **Nunca PII, tokens ni credenciales.** Ni en capturas ni en mensajes.

## Estructura de cada update

| Campo | Contenido | Ejemplo |
|---|---|---|
| Estado | Investigando / Mitigado / Resuelto / En vigilancia | "Mitigado" |
| Impacto | Qué no puede hacer el usuario, en lenguaje de negocio | "No se pueden crear ni editar usuarios" |
| Alcance | A quién afecta y desde cuándo | "Todos los usuarios, desde las 14:30 UTC" |
| Acciones en curso | Qué se está haciendo ahora | "Revisando la base de datos de usuarios" |
| ETA / próximo hito | Tiempo estimado o cuándo se vuelve a informar | "Próximo update 15:10 UTC" |
| Owner | Quién coordina | "@ana (guardia)" |

## Audiencias, canal y cadencia

| Audiencia | Qué le importa | Canal | Cadencia |
|---|---|---|---|
| Negocio / dirección | Impacto, clientes afectados, cuándo vuelve | Canal de incidentes (o hilo dedicado) | Cada 30 min y en cada cambio de estado |
| Equipo técnico | Hipótesis, evidencia, acciones | Hilo técnico del incidente | Continua, sin formato |
| Soporte / atención a clientes | Qué responder a quien pregunte | Canal de soporte con texto listo para copiar | Cada 30 min, alineado con negocio |
| Clientes finales | Qué pasa y qué hacer mientras tanto | Aviso en la app / estado público | Solo si el impacto es visible, cada 60 min |
| Seguridad / cumplimiento | ¿Hay datos afectados? | Escalado directo | Inmediato, sin esperar cadencia |

## Plantillas

### Update inicial (T+0 a T+10)

> **Estado**: Investigando
> **Impacto**: los usuarios no pueden guardar cambios (crear/editar usuarios). La consulta
> de información funciona con normalidad. *(ajustar según lo confirmado)*
> **Alcance**: todos los usuarios, desde las `HH:MM UTC`.
> **Acciones**: estamos revisando los servicios de usuarios y la base de datos; ya tenemos
> identificadas las peticiones que fallan y su traza.
> **Próximo update**: `HH:MM UTC` (30 min) o antes si cambia el estado.
> **Owner**: `@nombre`

### Update intermedio (T+30)

> **Estado**: Investigando / Mitigado
> **Impacto**: sin cambios respecto al update anterior. *(o: "los guardados vuelven a
> funcionar; vigilancias hasta las HH:MM")*
> **Qué hemos descartado**: no es un problema de autenticación; los usuarios que ya tienen
> sesión no se ven afectados.
> **Acciones en curso**: `acción concreta` (responsable).
> **Riesgo de la acción**: `p. ej., reinicio del servicio de usuarios, ~1 min de 502`.
> **Próximo update**: `HH:MM UTC`.

### Update de resolución (T+fin)

> **Estado**: Resuelto (en vigilancia hasta `HH:MM UTC`)
> **Impacto**: resuelto. Los guardados funcionan desde las `HH:MM UTC`.
> **Causa raíz**: `descripción en una frase, sin jerga`.
> **Qué hicimos**: `medida aplicada`.
> **Prevención**: `medida permanente, con dueño y fecha`.
> **Datos afectados**: `ninguno / N registros, ya recuperados / en revisión`.

## Cierre del incidente

Al resolver se comunica, en este orden:

1. **Causa raíz** confirmada (no la hipótesis inicial).
2. **Medidas correctivas** aplicadas y su efecto verificado.
3. **Prevención de recurrencia**: acción con dueño y fecha, no "vamos a revisarlo".
4. **Datos afectados**: si hubo pérdida, duplicación o exposición, con el alcance exacto.
5. **Enlace al post-mortem** (interno) y a la evidencia capturada.

El post-mortem se escribe sin culpables y con la línea de tiempo de
[`plan-diagnostico.md`](plan-diagnostico.md); si hubo pérdida o exposición de datos, se
escala a seguridad antes de publicar nada.

## Criterios de escalado

| Situación | A quién | Cuándo | Canal |
|---|---|---|---|
| Impacto confirmado en escrituras | Responsable de negocio | De inmediato | Canal de incidentes |
| T+20 min sin causa raíz | Líder técnico + infraestructura | A los 20 min | Llamada + canal |
| T+30 min sin mitigación | Dirección técnica | A los 30 min | Llamada |
| Sospecha de pérdida o exposición de datos | Seguridad / cumplimiento | Inmediato | Directo, sin cadencia |
| Cambio que requiere rollback | Owner del servicio | Antes de ejecutarlo | Canal + aprobación |
| `429`/coste descontrolado en IA | Owner de IA + negocio | Al superar presupuesto | Canal de incidentes |

## Errores que evitar

- "Ya casi está" sin evidencia: genera desconfianza y no aporta información.
- Dar una ETA que no se puede sostener; mejor comprometer el siguiente update.
- Mezclar hipótesis con hechos en el mensaje de negocio.
- Comunicar "resuelto" antes de la ventana de vigilancia.
- Publicar capturas con correos, tokens o `trace_id` completos de clientes.
- Abrir un canal nuevo por cada update: se pierde el hilo y la cronología.
