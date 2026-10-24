from datetime import date

import pytest

from expense_tracker.models import (
    Expense,
    create_expense,
    parse_amount,
    validate_category,
    validate_date,
)


@pytest.mark.parametrize(
    ("amount", "expected_cents"),
    [("12", 1200), ("12.3", 1230), ("12.34", 1234), (".05", 5), (" 1.00 ", 100)],
)
def test_parse_amount_converts_decimal_strings_to_cents(
    amount: str, expected_cents: int
) -> None:
    assert parse_amount(amount) == expected_cents


@pytest.mark.parametrize(
    "amount",
    ["", "abc", "1.234", "1.", "-1.00", "0", ".00", "1e2", "$1.00"],
)
def test_parse_amount_rejects_invalid_amounts(amount: str) -> None:
    with pytest.raises(ValueError):
        parse_amount(amount)


def test_parse_amount_rejects_non_string_values() -> None:
    with pytest.raises(TypeError, match="decimal string"):
        parse_amount(1.25)  # type: ignore[arg-type]


def test_validate_category_trims_surrounding_whitespace() -> None:
    assert validate_category("  groceries \t") == "groceries"


@pytest.mark.parametrize("category", ["", " \t\n"])
def test_validate_category_rejects_blank_values(category: str) -> None:
    with pytest.raises(ValueError, match="required"):
        validate_category(category)


@pytest.mark.parametrize("value", ["2024-02-29", "2000-01-01"])
def test_validate_date_accepts_valid_iso_dates(value: str) -> None:
    assert validate_date(value) == value


@pytest.mark.parametrize(
    "value",
    ["2023-02-29", "2024-13-01", "2024-04-31", "20240101", "01-01-2024"],
)
def test_validate_date_rejects_invalid_or_non_iso_dates(value: str) -> None:
    with pytest.raises(ValueError, match="date"):
        validate_date(value)


def test_expense_validates_fields_and_generates_short_id() -> None:
    expense = Expense(amount_cents=1250, category=" food ", date="2025-02-03")

    assert expense.amount_cents == 1250
    assert expense.category == "food"
    assert expense.date == "2025-02-03"
    assert len(expense.id) == 8
    assert expense.id.isalnum()


@pytest.mark.parametrize("amount_cents", [0, -1, 1.5, True])
def test_expense_rejects_invalid_amount_cents(amount_cents: int) -> None:
    expected_error = TypeError if isinstance(amount_cents, (float, bool)) else ValueError
    with pytest.raises(expected_error):
        Expense(amount_cents=amount_cents, category="food", date="2025-02-03")


def test_expense_rejects_invalid_note_and_id() -> None:
    with pytest.raises(TypeError, match="note"):
        Expense(100, "food", "2025-02-03", note=3)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="id"):
        Expense(100, "food", "2025-02-03", id=" ")


def test_create_expense_uses_injected_today_when_date_is_missing() -> None:
    expense = create_expense("5.25", "  transit ", today=date(2025, 3, 4))

    assert expense.amount_cents == 525
    assert expense.category == "transit"
    assert expense.date == "2025-03-04"
