"""Document ingestion port (implemented over a local directory)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class DocumentSource:
    document: str
    text: str
    updated_at: str


class DocumentLoader(Protocol):
    async def load(self) -> tuple[DocumentSource, ...]: ...
