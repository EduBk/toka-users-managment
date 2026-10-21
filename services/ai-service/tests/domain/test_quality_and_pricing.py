import pytest

from domain.agent.pricing import TokenPrice
from domain.agent.quality import (
    admits_missing_context,
    contains_pii,
    redact_pii,
    validate_answer,
)


def test_price_calculates_the_cost_per_million_tokens() -> None:
    price = TokenPrice(input_per_million=0.15, output_per_million=0.60)

    assert price.cost(input_tokens=1000, output_tokens=500) == 0.00045


@pytest.mark.parametrize(
    ("input_tokens", "output_tokens"),
    [(-1, 0), (0, -1)],
)
def test_price_rejects_negative_tokens(input_tokens: int, output_tokens: int) -> None:
    with pytest.raises(ValueError):
        TokenPrice().cost(input_tokens=input_tokens, output_tokens=output_tokens)


def test_price_rejects_negative_rates() -> None:
    with pytest.raises(ValueError):
        TokenPrice(input_per_million=-1)


def test_validate_answer_passes_with_sources() -> None:
    report = validate_answer("Los roles viven en role-service [1].", has_sources=True)

    assert report.passed is True
    assert report.issues == ()


def test_validate_answer_flags_an_answer_without_sources() -> None:
    report = validate_answer("Los roles son tres.", has_sources=False)

    assert report.passed is False
    assert report.issues == ("missing_sources",)


def test_validate_answer_accepts_an_explicit_no_context_answer() -> None:
    report = validate_answer(
        "No tengo información suficiente para responder.", has_sources=False
    )

    assert report.passed is True
    assert admits_missing_context("Sin información suficiente en el corpus.")


def test_validate_answer_flags_empty_and_long_answers() -> None:
    empty = validate_answer("   ", has_sources=True)
    long = validate_answer("x" * 20, has_sources=True, max_chars=10)

    assert empty.issues == ("empty_answer",)
    assert long.issues == ("answer_too_long",)


def test_validate_answer_flags_leaked_pii() -> None:
    report = validate_answer("Escribe a ana@example.com [1]", has_sources=True)

    assert report.issues == ("pii_in_answer",)
    assert contains_pii("+34 600 123 456")


def test_redact_pii_masks_emails_and_phones() -> None:
    redacted = redact_pii("ana@example.com y +34 600 123 456")

    assert redacted == "[email] y [phone]"
