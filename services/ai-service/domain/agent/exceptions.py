"""Agent domain errors."""


class InvalidQuestion(Exception):
    """The question is empty or cannot be safely sent to the LLM."""
