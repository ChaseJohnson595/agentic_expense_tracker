import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from expense_tracker.models import Expense, validate_category, validate_date

DEFAULT_DATA_PATH = Path.home() / ".expense_tracker" / "expenses.sqlite3"


class StorageError(Exception):
    """Raised when expense data cannot be read or written safely."""


def load_expenses(data_path: Path | str = DEFAULT_DATA_PATH) -> list[Expense]:
    """Load expenses from JSON if the path is JSON-backed, otherwise use SQLite."""
    path = Path(data_path)
    if path.suffix.lower() == ".json":
        return _load_json_expenses(path)
    if not path.exists():
        return []

    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_database(path)
        _initialize_database(connection)
        rows = connection.execute(
            """
            SELECT id, amount_cents, category, date, note
            FROM expenses
            ORDER BY date DESC, id DESC
            """
        ).fetchall()
    except sqlite3.Error as error:
        raise StorageError(f"Could not read expenses from {path}: {error}") from error
    finally:
        if connection is not None:
            connection.close()
    return [_row_to_expense(row) for row in rows]


def save_expenses(
    expenses: list[Expense], data_path: Path | str = DEFAULT_DATA_PATH
) -> None:
    """Replace stored expenses in the active storage backend."""
    path = Path(data_path)
    if path.suffix.lower() == ".json":
        _save_json_expenses(expenses, path)
        return

    _ensure_expenses_are_valid(expenses)
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_database(path)
        _initialize_database(connection)
        with connection:
            connection.execute("DELETE FROM expenses")
            if expenses:
                connection.executemany(
                    """
                    INSERT INTO expenses (id, amount_cents, category, date, note)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [_expense_row(expense) for expense in expenses],
                )
    except sqlite3.Error as error:
        raise StorageError(f"Could not save expenses to {path}: {error}") from error
    finally:
        if connection is not None:
            connection.close()


def add_expense(expense: Expense, data_path: Path | str = DEFAULT_DATA_PATH) -> Expense:
    """Insert a single expense and reject duplicate IDs."""
    path = Path(data_path)
    if path.suffix.lower() == ".json":
        return _add_json_expense(expense, path)

    if not isinstance(expense, Expense):
        raise TypeError("expenses must contain only Expense instances")
    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_database(path)
        _initialize_database(connection)
        with connection:
            try:
                connection.execute(
                    """
                    INSERT INTO expenses (id, amount_cents, category, date, note)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    _expense_row(expense),
                )
            except sqlite3.IntegrityError as error:
                if "UNIQUE constraint failed: expenses.id" in str(error):
                    raise ValueError(
                        f"An expense with ID {expense.id!r} already exists"
                    ) from error
                raise StorageError(
                    f"Could not add expense to {path}: {error}"
                ) from error
    except sqlite3.Error as error:
        raise StorageError(f"Could not add expense to {path}: {error}") from error
    finally:
        if connection is not None:
            connection.close()
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

    path = Path(data_path)
    if path.suffix.lower() == ".json":
        expenses = _load_json_expenses(path)
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
    if not path.exists():
        return []

    where_clauses: list[str] = []
    parameters: list[str] = []
    if start is not None:
        where_clauses.append("date >= ?")
        parameters.append(start)
    if end is not None:
        where_clauses.append("date <= ?")
        parameters.append(end)
    if normalized_category is not None:
        where_clauses.append("LOWER(category) = LOWER(?)")
        parameters.append(normalized_category)

    query = "SELECT id, amount_cents, category, date, note FROM expenses"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
    query += " ORDER BY date DESC, id DESC"

    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_database(path)
        _initialize_database(connection)
        rows = connection.execute(query, parameters).fetchall()
    except sqlite3.Error as error:
        raise StorageError(f"Could not read expenses from {path}: {error}") from error
    finally:
        if connection is not None:
            connection.close()
    return [_row_to_expense(row) for row in rows]


def delete_expense(expense_id: str, data_path: Path | str = DEFAULT_DATA_PATH) -> bool:
    """Delete the matching expense and return whether an expense was found."""
    path = Path(data_path)
    if path.suffix.lower() == ".json":
        expenses = _load_json_expenses(path)
        remaining = [expense for expense in expenses if expense.id != expense_id]
        if len(remaining) == len(expenses):
            return False
        _save_json_expenses(remaining, path)
        return True
    if not path.exists():
        return False

    connection: sqlite3.Connection | None = None
    try:
        connection = _connect_database(path)
        _initialize_database(connection)
        with connection:
            cursor = connection.execute(
                "DELETE FROM expenses WHERE id = ?",
                (expense_id,),
            )
            return cursor.rowcount > 0
    except sqlite3.Error as error:
        raise StorageError(
            f"Could not delete expense {expense_id!r} from {path}: {error}"
        ) from error
    finally:
        if connection is not None:
            connection.close()


def _connect_database(path: Path | str) -> sqlite3.Connection:
    database_path = Path(path)
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StorageError(
            f"Could not create the database directory for {database_path}: {error}"
        ) from error

    try:
        connection = sqlite3.connect(database_path)
    except sqlite3.Error as error:
        raise StorageError(
            f"Could not open expense database at {database_path}: {error}"
        ) from error
    connection.row_factory = sqlite3.Row
    return connection


def _initialize_database(connection: sqlite3.Connection) -> None:
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                note TEXT
            )
            """
        )
    except sqlite3.Error as error:
        raise StorageError(
            f"Could not initialize expense database schema: {error}"
        ) from error


def _ensure_expenses_are_valid(expenses: list[Expense]) -> None:
    for expense in expenses:
        if not isinstance(expense, Expense):
            raise TypeError("expenses must contain only Expense instances")
    ids = [expense.id for expense in expenses]
    if len(ids) != len(set(ids)):
        raise ValueError("expense IDs must be unique")


def _row_to_expense(row: sqlite3.Row) -> Expense:
    return Expense(
        id=row["id"],
        amount_cents=row["amount_cents"],
        category=row["category"],
        date=row["date"],
        note=row["note"],
    )


def _expense_row(expense: Expense) -> tuple[str, int, str, str, str | None]:
    return (
        expense.id,
        expense.amount_cents,
        expense.category,
        expense.date,
        expense.note,
    )


def _load_json_expenses(path: Path) -> list[Expense]:
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8")
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


def _save_json_expenses(expenses: list[Expense], path: Path) -> None:
    _ensure_expenses_are_valid(expenses)
    records = [_expense_record(expense) for expense in expenses]
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


def _add_json_expense(expense: Expense, path: Path) -> Expense:
    expenses = _load_json_expenses(path)
    if any(existing.id == expense.id for existing in expenses):
        raise ValueError(f"An expense with ID {expense.id!r} already exists")
    _save_json_expenses([*expenses, expense], path)
    return expense


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
