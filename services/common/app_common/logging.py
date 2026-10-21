"""Structured JSON logging with a request-scoped trace id.

Every record carries ``level``, ``timestamp``, ``service``, ``trace_id``,
``logger`` and ``message``. Extra structured fields are passed with
``log_event(logger, level, message, **fields)``.
"""

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

from app_common.config import BaseServiceSettings

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")

FALLBACK_CONTEXT_VALUE = "-"


def get_trace_id() -> str:
    return _trace_id.get()


def set_trace_id(trace_id: str) -> Token[str]:
    return _trace_id.set(trace_id)


def reset_trace_id(token: Token[str]) -> None:
    _trace_id.reset(token)


class TraceContextFilter(logging.Filter):
    """Injects the service name and the current trace id into every record."""

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.service_name
        record.trace_id = get_trace_id()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "service": getattr(record, "service", FALLBACK_CONTEXT_VALUE),
            "trace_id": getattr(record, "trace_id", FALLBACK_CONTEXT_VALUE),
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(getattr(record, "extra_fields", None) or {})
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(settings: BaseServiceSettings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TraceContextFilter(settings.service_name))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())

    # Uvicorn installs plain-text handlers before importing the app; route them
    # through the JSON handler and drop its duplicate access log (the trace
    # middleware already logs every request).
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    **fields: Any,
) -> None:
    """Emit a record with additional JSON fields."""
    logger.log(level, message, extra={"extra_fields": fields})
