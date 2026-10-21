"""Prompt provider port: versioned prompt artifacts live in the repository."""

from __future__ import annotations

from typing import Protocol

from domain.agent.prompt import PromptBundle


class PromptProvider(Protocol):
    def current(self) -> PromptBundle: ...
