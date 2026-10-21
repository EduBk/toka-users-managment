"""Token pricing used to estimate the cost of an invocation (E5.5)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPrice:
    """USD price per one million tokens."""

    input_per_million: float = 0.0
    output_per_million: float = 0.0

    def __post_init__(self) -> None:
        if self.input_per_million < 0 or self.output_per_million < 0:
            raise ValueError("prices must be >= 0")

    def cost(self, *, input_tokens: int, output_tokens: int) -> float:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("tokens must be >= 0")
        cost = (
            input_tokens * self.input_per_million
            + output_tokens * self.output_per_million
        ) / 1_000_000
        return round(cost, 8)
