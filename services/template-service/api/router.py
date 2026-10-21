"""Service routes.

Routes validate input, delegate to use cases and map domain errors. Business
rules never live here. ``/health`` is provided by ``app_common``.
"""

from fastapi import APIRouter

router = APIRouter()
