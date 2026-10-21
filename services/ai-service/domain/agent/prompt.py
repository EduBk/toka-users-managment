"""Prompt composition, question sanitisation and injection detection (E5.4).

Prompts themselves live in ``prompts/*.md`` (versioned artifacts); this module
only renders them with context and history, so the wording can change without
touching the application layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.agent.exceptions import InvalidQuestion
from domain.agent.models import Message, RetrievedChunk

MAX_QUESTION_CHARS = 2000
MAX_HISTORY_CHARS = 2000

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLANKS = re.compile(r"\n{3,}")

# Cheap, documented heuristics: they flag prompts that try to override the
# system instructions. The question is still answered, wrapped as data.
_INJECTION = (
    re.compile(r"ignore (all )?(previous|above) instructions", re.I),
    re.compile(r"ignora (todas )?(las )?instrucciones", re.I),
    re.compile(r"(olvida|forget) (tu|your) (rol|role|reglas|rules)", re.I),
    re.compile(r"^\s*(system|assistant|developer)\s*:", re.I | re.M),
    re.compile(r"</?\s*(system|instructions?)\s*>", re.I),
    re.compile(r"reveal (the )?(system prompt|instructions)", re.I),
    re.compile(r"muestra (tu|el) (prompt|sistema)", re.I),
)


@dataclass(frozen=True, slots=True)
class SanitizedQuestion:
    text: str
    injection_suspected: bool


@dataclass(frozen=True, slots=True)
class FewShot:
    question: str
    answer: str


@dataclass(frozen=True, slots=True)
class PromptBundle:
    version: str
    system: str
    user_template: str
    few_shots: tuple[FewShot, ...] = ()

    def render_system(self) -> str:
        if not self.few_shots:
            return self.system
        examples = "\n\n".join(
            f"Pregunta: {shot.question}\nRespuesta: {shot.answer}"
            for shot in self.few_shots
        )
        return f"{self.system}\n\n## Ejemplos\n\n{examples}"


def sanitize_question(
    raw: str, *, max_chars: int = MAX_QUESTION_CHARS
) -> SanitizedQuestion:
    """Normalise the question and flag likely prompt-injection attempts."""

    text = _CONTROL_CHARS.sub("", raw or "")
    text = _BLANKS.sub("\n\n", text).strip()
    if not text:
        raise InvalidQuestion("the question is empty")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
    return SanitizedQuestion(
        text=text,
        injection_suspected=any(pattern.search(text) for pattern in _INJECTION),
    )


def render_context(chunks: tuple[RetrievedChunk, ...]) -> str:
    """Number the retrieved fragments so the answer can cite them."""

    return "\n\n".join(
        f"[{index}] {chunk.document} — {chunk.section}\n{chunk.text}"
        for index, chunk in enumerate(chunks, start=1)
    )


def render_history(history: tuple[Message, ...], *, max_chars: int) -> str:
    """Serialise the short conversation history, newest turns last."""

    if not history:
        return "(sin historial)"
    lines = [f"{message.role}: {message.content}" for message in history]
    rendered = "\n".join(lines)
    return rendered[-max_chars:] if len(rendered) > max_chars else rendered


def build_user_prompt(
    bundle: PromptBundle,
    *,
    context: str,
    question: str,
    history: str,
) -> str:
    return (
        bundle.user_template.replace("{{context}}", context or "(sin contexto)")
        .replace("{{question}}", question)
        .replace("{{history}}", history)
    )
