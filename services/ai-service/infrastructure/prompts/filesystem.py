"""Versioned prompt artifacts loaded from disk (E5.4)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from domain.agent.prompt import FewShot, PromptBundle

_VERSION = re.compile(r"^v\d+$")


class FilePromptProvider:
    """Reads ``system.<version>.md``, ``rag.<version>.md`` and few-shots.

    Keeping the files in the repository makes every prompt change reviewable and
    traceable; the version is returned with each answer.
    """

    def __init__(self, directory: Path, *, version: str = "v1") -> None:
        if not _VERSION.match(version):
            raise ValueError("prompt version must look like 'v1'")
        self._directory = directory
        self._version = version
        self._bundle: PromptBundle | None = None

    def current(self) -> PromptBundle:
        if self._bundle is None:
            self._bundle = self._load()
        return self._bundle

    def _load(self) -> PromptBundle:
        system = self._read(f"system.{self._version}.md")
        template = self._read(f"rag.{self._version}.md")
        shots = json.loads(self._read(f"few-shots.{self._version}.json"))
        return PromptBundle(
            version=self._version,
            system=system,
            user_template=template,
            few_shots=tuple(
                FewShot(question=shot["question"], answer=shot["answer"])
                for shot in shots
            ),
        )

    def _read(self, name: str) -> str:
        path = self._directory / name
        if not path.is_file():
            raise FileNotFoundError(f"prompt artifact not found: {path}")
        return path.read_text(encoding="utf-8").strip()
