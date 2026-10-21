# Servicios backend

Monorepo de microservicios FastAPI. Cada servicio es una carpeta independiente con la
misma estructura de capas descrita en `docs/arquitectura/ddd-clean-architecture.md`:

```text
services/<servicio>/
├── domain/            # agregados, value objects, eventos, contratos de repositorio
├── application/       # casos de uso y puertos de salida
├── infrastructure/    # adaptadores: SQLAlchemy, Redis, RabbitMQ, MongoDB, HTTP
├── api/               # rutas, schemas Pydantic, composición de dependencias
├── pyproject.toml
└── main.py
```

`services/common` (`app_common`) concentra solo infraestructura técnica compartida:
configuración por entorno, logging JSON con `trace_id`, esquema de errores y `/health`.
No contiene reglas de negocio.

## Puesta en marcha local

```powershell
py -m pip install -e services/common
cd services/template-service
$env:SERVICE_NAME = "template-service"
py -m uvicorn main:app --host 127.0.0.1 --port 8000
```

`GET http://127.0.0.1:8000/health` responde JSON y cada log de stdout es una línea JSON
con `level`, `timestamp`, `service`, `trace_id`, `logger` y `message`.

## Variables de entorno comunes

| Variable | Obligatoria | Por defecto | Uso |
|---|---|---|---|
| `SERVICE_NAME` | Sí | por servicio | Identifica el servicio en los logs |
| `LOG_LEVEL` | No | `INFO` | Nivel mínimo de logging |
| `ENVIRONMENT` | No | `local` | Entorno (`local`, `docker`, `test`, ...) |
| `SERVICE_VERSION` | No | `0.1.0` | Versión expuesta en `/health` |

El resto de variables (bases de datos, broker, claves JWT) se añaden por servicio y se
documentan en `.env.example`. Los valores reales viven en `.env`, que no se versiona.

## Añadir un servicio

1. Copia `services/template-service` con el nombre del nuevo servicio y ajusta `name` en
   su `pyproject.toml` y `service_name` en `main.py`.
2. Añade las dependencias propias del servicio a su `pyproject.toml`.
3. Declara las rutas en `api/router.py` y la lógica en `domain/` + `application/`.
4. Registra los adaptadores en `api/` (composition root) e implementa los puertos en
   `infrastructure/`.
