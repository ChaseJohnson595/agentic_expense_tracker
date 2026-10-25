import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date as Date
from decimal import Decimal
from uuid import uuid4


def parse_amount(amount: str) -> int:
    """Convert a positive amount with at most two decimal places to cents."""
    if not isinstance(amount, str):
        raise TypeError("amount must be entered as a decimal string")

    normalized = amount.strip()
    if not re.fullmatch(r"(?:\d+(?:\.\d{1,2})?|\.\d{1,2})", normalized):
        raise ValueError("amount must be a number with at most two decimal places")

    cents = int(Decimal(normalized) * 100)
    if cents <= 0:
        raise ValueError("amount must be greater than zero")
    return cents


def validate_category(category: str) -> str:
    """Trim a category and ensure it contains a non-whitespace character."""
    if not isinstance(category, str):
        raise TypeError("category must be text")

    normalized = category.strip()
    if not normalized:
        raise ValueError("category is required")
    return normalized


def validate_date(value: str) -> str:
    """Validate and return a date in YYYY-MM-DD format."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("date must be in YYYY-MM-DD format")

    try:
        Date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("date must be a valid date in YYYY-MM-DD format") from error
    return value


def validate_month(value: str) -> str:
    """Validate and return a month in YYYY-MM format."""
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", value)
        or value[:4] == "0000"
    ):
        raise ValueError("month must be in YYYY-MM format")
    return value


@dataclass(frozen=True)
class Expense:
    amount_cents: int
    category: str
    date: str = field(default_factory=lambda: Date.today().isoformat())
    note: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex[:8])

    def __post_init__(self) -> None:
        if isinstance(self.amount_cents, bool) or not isinstance(self.amount_cents, int):
            raise TypeError("amount_cents must be an integer")
        if self.amount_cents <= 0:
            raise ValueError("amount must be greater than zero")

        object.__setattr__(self, "category", validate_category(self.category))
        object.__setattr__(self, "date", validate_date(self.date))

        if self.note is not None and not isinstance(self.note, str):
            raise TypeError("note must be text or None")
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("id is required")


def create_expense(
    amount: str,
    category: str,
    expense_date: str | None = None,
    note: str | None = None,
    *,
    today: Date | None = None,
) -> Expense:
    """Build an expense, with an injectable date for deterministic callers."""
    default_date = (today or Date.today()).isoformat()
    return Expense(
        amount_cents=parse_amount(amount),
        category=category,
        date=validate_date(expense_date if expense_date is not None else default_date),
        note=note,
    )


def summarize_expenses(
    expenses: Iterable[Expense],
    *,
    month: str | None = None,
    today: Date | None = None,
) -> tuple[int, dict[str, int]]:
    """Calculate the integer-cent total and category totals for one month."""
    selected_month = validate_month(
        month if month is not None else (today or Date.today()).strftime("%Y-%m")
    )
    category_totals: dict[str, int] = {}
    total = 0
    for expense in expenses:
        if expense.date.startswith(selected_month):
            total += expense.amount_cents
            category_totals[expense.category] = (
                category_totals.get(expense.category, 0) + expense.amount_cents
            )
    return total, dict(sorted(category_totals.items()))
