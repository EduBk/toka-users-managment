"""Request-scoped trace id propagation and access logging."""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app_common.logging import reset_trace_id, set_trace_id

logger = logging.getLogger("app_common.access")

# Client-provided ids are untrusted: accept a conservative charset and length.
_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{8,64}$")


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        trace_id = (
            incoming if _TRACE_ID_PATTERN.fullmatch(incoming) else uuid.uuid4().hex
        )
        token = set_trace_id(trace_id)
        request.state.trace_id = trace_id
        started = time.perf_counter()
        fields = {"method": request.method, "path": request.url.path}

        try:
            response = await call_next(request)
        except Exception as exc:
            # The traceback is logged once by the unexpected-error handler.
            logger.error(
                "request failed",
                extra={
                    "extra_fields": {
                        **fields,
                        "error": type(exc).__name__,
                        "duration_ms": round(
                            (time.perf_counter() - started) * 1000, 2
                        ),
                    }
                },
            )
            raise
        else:
            response.headers["X-Request-ID"] = trace_id
            logger.info(
                "request completed",
                extra={
                    "extra_fields": {
                        **fields,
                        "status_code": response.status_code,
                        "duration_ms": round(
                            (time.perf_counter() - started) * 1000, 2
                        ),
                    }
                },
            )
            return response
        finally:
            reset_trace_id(token)
