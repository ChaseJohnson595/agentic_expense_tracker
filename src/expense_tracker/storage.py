import json
import os
import tempfile
from pathlib import Path
from typing import Any

from expense_tracker.models import Expense, validate_category, validate_date

DEFAULT_DATA_PATH = Path.home() / ".expense_tracker" / "expenses.json"


class StorageError(Exception):
    """Raised when expense data cannot be read or written safely."""


def load_expenses(data_path: Path | str = DEFAULT_DATA_PATH) -> list[Expense]:
    """Load expenses from JSON; a missing file represents an empty tracker."""
    path = Path(data_path)
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as error:
        raise StorageError(f"Could not read expenses from {path}: {error}") from error
    except UnicodeError as error:
        raise StorageError(
            f"Expense file {path} is not valid UTF-8: {error}"
        ) from error

    try:
        records = json.loads(content)
    except json.JSONDecodeError as error:
        raise StorageError(f"Invalid JSON in expense file {path}: {error}") from error
    return _decode_expenses(records, path)


def save_expenses(
    expenses: list[Expense], data_path: Path | str = DEFAULT_DATA_PATH
) -> None:
    """Save expenses using a temporary file and atomic replacement."""
    path = Path(data_path)
    records = [_expense_record(expense) for expense in expenses]
    _ensure_unique_ids(expenses)
    temporary_path: Path | None = None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            json.dump(records, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
        os.replace(temporary_path, path)
    except (OSError, UnicodeError) as error:
        cleanup_error = _remove_temporary_file(temporary_path)
        message = f"Could not save expenses to {path}: {error}"
        if cleanup_error is not None:
            message += f"; could not remove temporary file: {cleanup_error}"
        raise StorageError(message) from error


def add_expense(expense: Expense, data_path: Path | str = DEFAULT_DATA_PATH) -> Expense:
    """Append one expense, rejecting an ID that is already in use."""
    expenses = load_expenses(data_path)
    if any(existing.id == expense.id for existing in expenses):
        raise ValueError(f"An expense with ID {expense.id!r} already exists")
    save_expenses([*expenses, expense], data_path)
    return expense


def list_expenses(
    data_path: Path | str = DEFAULT_DATA_PATH,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
) -> list[Expense]:
    """Return matching expenses, newest date first."""
    start = validate_date(start_date) if start_date is not None else None
    end = validate_date(end_date) if end_date is not None else None
    normalized_category = validate_category(category) if category is not None else None
    if start is not None and end is not None and start > end:
        raise ValueError("start_date must be on or before end_date")

    expenses = load_expenses(data_path)
    return sorted(
        (
            expense
            for expense in expenses
            if (start is None or expense.date >= start)
            and (end is None or expense.date <= end)
            and (
                normalized_category is None
                or expense.category.casefold() == normalized_category.casefold()
            )
        ),
        key=lambda expense: (expense.date, expense.id),
        reverse=True,
    )


def delete_expense(expense_id: str, data_path: Path | str = DEFAULT_DATA_PATH) -> bool:
    """Delete the matching expense and return whether an expense was found."""
    expenses = load_expenses(data_path)
    remaining = [expense for expense in expenses if expense.id != expense_id]
    if len(remaining) == len(expenses):
        return False
    save_expenses(remaining, data_path)
    return True


def _decode_expenses(records: Any, path: Path) -> list[Expense]:
    if not isinstance(records, list):
        raise StorageError(f"Expense file {path} must contain a JSON array")

    expenses: list[Expense] = []
    try:
        for index, record in enumerate(records):
            expenses.append(_decode_expense(record))
    except (TypeError, ValueError) as error:
        message = f"Invalid expense record at index {index} in {path}: {error}"
        raise StorageError(message) from error

    try:
        _ensure_unique_ids(expenses)
    except ValueError as error:
        raise StorageError(f"Invalid expense data in {path}: {error}") from error
    return expenses


def _decode_expense(record: Any) -> Expense:
    if not isinstance(record, dict):
        raise TypeError("record must be a JSON object")
    required_keys = {"amount_cents", "category", "date", "id"}
    allowed_keys = required_keys | {"note"}
    if not required_keys.issubset(record) or not set(record).issubset(allowed_keys):
        raise ValueError("record has missing or unexpected fields")
    return Expense(
        amount_cents=record["amount_cents"],
        category=record["category"],
        date=record["date"],
        note=record.get("note"),
        id=record["id"],
    )


def _expense_record(expense: Expense) -> dict[str, Any]:
    if not isinstance(expense, Expense):
        raise TypeError("expenses must contain only Expense instances")
    return {
        "amount_cents": expense.amount_cents,
        "category": expense.category,
        "date": expense.date,
        "note": expense.note,
        "id": expense.id,
    }


def _ensure_unique_ids(expenses: list[Expense]) -> None:
    ids = [expense.id for expense in expenses]
    if len(ids) != len(set(ids)):
        raise ValueError("expense IDs must be unique")


def _remove_temporary_file(path: Path | None) -> OSError | None:
    if path is None:
        return None
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        return error
    return None
