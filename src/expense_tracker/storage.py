import sqlite3
from pathlib import Path

from expense_tracker.models import Expense, validate_category, validate_date

DEFAULT_DATA_PATH = Path.home() / ".expense_tracker" / "expenses.sqlite3"


class StorageError(Exception):
    """Raised when expense data cannot be read or written safely."""


def load_expenses(data_path: Path | str = DEFAULT_DATA_PATH) -> list[Expense]:
    """Load all expenses from SQLite, creating the database if needed."""
    path = Path(data_path)
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
    """Replace all stored expenses with the supplied list in one transaction."""
    _ensure_expenses_are_valid(expenses)
    path = Path(data_path)
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
    if not isinstance(expense, Expense):
        raise TypeError("expenses must contain only Expense instances")
    path = Path(data_path)
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
    """Delete the matching expense and return whether it was found."""
    path = Path(data_path)
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
        raise StorageError(f"Could not open expense database at {database_path}: {error}") from error
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
        raise StorageError(f"Could not initialize expense database schema: {error}") from error


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
    return (expense.id, expense.amount_cents, expense.category, expense.date, expense.note)
