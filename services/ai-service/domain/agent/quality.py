"""Basic answer quality validation and PII handling (E5.5)."""

from __future__ import annotations

import re

from domain.agent.models import QualityReport

MAX_ANSWER_CHARS = 4000

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
_NO_CONTEXT = (
    "no tengo información suficiente",
    "sin información suficiente",
    "no dispongo de información",
)


def redact_pii(text: str) -> str:
    """Remove emails and phone numbers before logging free text."""

    return _PHONE.sub("[phone]", _EMAIL.sub("[email]", text))


def contains_pii(text: str) -> bool:
    return bool(_EMAIL.search(text) or _PHONE.search(text))


def admits_missing_context(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in _NO_CONTEXT)


def validate_answer(
    answer: str, *, has_sources: bool, max_chars: int = MAX_ANSWER_CHARS
) -> QualityReport:
    """Check structure, grounding and absence of leaked personal data."""

    issues: list[str] = []
    text = answer.strip()
    if not text:
        issues.append("empty_answer")
    if len(text) > max_chars:
        issues.append("answer_too_long")
    if not has_sources and not admits_missing_context(text):
        issues.append("missing_sources")
    if contains_pii(text):
        issues.append("pii_in_answer")
    return QualityReport(passed=not issues, issues=tuple(issues))
