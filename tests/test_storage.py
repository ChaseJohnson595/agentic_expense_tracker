import json
import sqlite3
from pathlib import Path

import pytest

from expense_tracker.models import Expense
from expense_tracker.storage import (
    StorageError,
    add_expense,
    delete_expense,
    import_json_expenses,
    list_expenses,
    load_expenses,
    save_expenses,
)


def make_expense(
    amount_cents: int,
    category: str,
    expense_date: str,
    expense_id: str,
    note: str | None = None,
) -> Expense:
    return Expense(
        amount_cents=amount_cents,
        category=category,
        date=expense_date,
        id=expense_id,
        note=note,
    )


def test_missing_database_file_loads_as_empty(tmp_path: Path) -> None:
    assert load_expenses(tmp_path / "expenses.sqlite3") == []


def test_save_and_load_round_trip_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "expenses.sqlite3"
    expenses = [make_expense(1250, "food", "2025-01-02", "food1234", "Lunch")]

    save_expenses(expenses, path)

    assert path.exists()
    assert load_expenses(path) == expenses

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT id, amount_cents, category, date, note FROM expenses"
        ).fetchall()
    assert rows == [("food1234", 1250, "food", "2025-01-02", "Lunch")]


def test_import_json_expenses_imports_records_and_preserves_source(
    tmp_path: Path,
) -> None:
    source = tmp_path / "expenses.json"
    source_contents = json.dumps(
        [
            {
                "id": "food1234",
                "amount_cents": 1250,
                "category": " food ",
                "date": "2025-01-02",
                "note": "Lunch",
            },
            {
                "id": "transit1",
                "amount_cents": 400,
                "category": "transit",
                "date": "2025-01-03",
                "note": None,
            },
        ],
        indent=2,
    )
    source.write_text(source_contents, encoding="utf-8")
    database = tmp_path / "expenses.sqlite3"

    assert import_json_expenses(source, database) == 2
    assert load_expenses(database) == [
        make_expense(400, "transit", "2025-01-03", "transit1"),
        make_expense(1250, "food", "2025-01-02", "food1234", "Lunch"),
    ]
    assert source.read_text(encoding="utf-8") == source_contents


@pytest.mark.parametrize(
    ("source_contents", "message"),
    [
        ("{not json", "Invalid JSON"),
        ('{"not": "an array"}', "must contain a JSON array"),
        (
            (
                '[{"id": "bad", "amount_cents": 0, "category": "food", '
                '"date": "2025-01-01"}]'
            ),
            "Invalid expense record",
        ),
    ],
)
def test_import_json_expenses_rejects_invalid_source_without_database_changes(
    tmp_path: Path, source_contents: str, message: str
) -> None:
    source = tmp_path / "expenses.json"
    source.write_text(source_contents, encoding="utf-8")
    database = tmp_path / "expenses.sqlite3"
    existing = make_expense(500, "food", "2025-01-01", "existing")
    save_expenses([existing], database)

    with pytest.raises(StorageError, match=message):
        import_json_expenses(source, database)

    assert load_expenses(database) == [existing]
    assert source.read_text(encoding="utf-8") == source_contents


def test_import_json_expenses_rolls_back_on_existing_id_conflict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "expenses.json"
    source_contents = json.dumps(
        [
            {
                "id": "new",
                "amount_cents": 100,
                "category": "food",
                "date": "2025-01-01",
            },
            {
                "id": "existing",
                "amount_cents": 200,
                "category": "transit",
                "date": "2025-01-02",
            },
        ]
    )
    source.write_text(source_contents, encoding="utf-8")
    database = tmp_path / "expenses.sqlite3"
    existing = make_expense(500, "food", "2025-01-03", "existing")
    save_expenses([existing], database)

    with pytest.raises(StorageError, match="expense ID already exists"):
        import_json_expenses(source, database)

    assert load_expenses(database) == [existing]
    assert source.read_text(encoding="utf-8") == source_contents


def test_import_json_expenses_reports_missing_source(tmp_path: Path) -> None:
    with pytest.raises(StorageError, match="does not exist"):
        import_json_expenses(
            tmp_path / "missing.json", tmp_path / "expenses.sqlite3"
        )


def test_database_schema_initializes_and_persists_across_connections(
    tmp_path: Path,
) -> None:
    path = tmp_path / "expenses.sqlite3"
    save_expenses([], path)

    with sqlite3.connect(path) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'expenses'"
        ).fetchall()
    assert tables == [("expenses",)]

    expense = make_expense(875, "food", "2025-02-03", "expense1")
    add_expense(expense, path)

    with sqlite3.connect(path) as connection:
        rows = connection.execute(
            "SELECT id, amount_cents, category, date, note FROM expenses"
        ).fetchall()
    assert rows == [("expense1", 875, "food", "2025-02-03", None)]


def test_save_expenses_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "expenses.sqlite3"
    expenses = [
        make_expense(100, "food", "2025-01-01", "duplicate"),
        make_expense(200, "travel", "2025-01-02", "duplicate"),
    ]

    with pytest.raises(ValueError, match="unique"):
        save_expenses(expenses, path)

    assert load_expenses(path) == []


def test_add_expense_persists_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "expenses.sqlite3"
    expense = make_expense(875, "food", "2025-02-03", "expense1")

    assert add_expense(expense, path) == expense
    assert load_expenses(path) == [expense]
    with pytest.raises(ValueError, match="already exists"):
        add_expense(expense, path)


def test_list_expenses_filters_and_sorts_newest_first(tmp_path: Path) -> None:
    path = tmp_path / "expenses.sqlite3"
    expenses = [
        make_expense(100, "food", "2025-03-01", "older"),
        make_expense(200, "Transit", "2025-03-02", "transit"),
        make_expense(300, "food", "2025-03-03", "newer"),
        make_expense(400, "food", "2025-04-01", "outside"),
    ]
    save_expenses(expenses, path)

    matches = list_expenses(
        path, start_date="2025-03-01", end_date="2025-03-31", category=" food "
    )

    assert [expense.id for expense in matches] == ["newer", "older"]


def test_list_expenses_rejects_reversed_date_range(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="on or before"):
        list_expenses(
            tmp_path / "expenses.sqlite3",
            start_date="2025-03-02",
            end_date="2025-03-01",
        )


def test_delete_expense_removes_match_and_reports_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "expenses.sqlite3"
    keep = make_expense(100, "food", "2025-01-01", "keep")
    remove = make_expense(200, "travel", "2025-01-02", "remove")
    save_expenses([keep, remove], path)

    assert delete_expense("remove", path) is True
    assert load_expenses(path) == [keep]
    assert delete_expense("missing", path) is False


def test_load_reports_storage_error_for_directory_path(tmp_path: Path) -> None:
    path = tmp_path / "directory"
    path.mkdir()

    with pytest.raises(StorageError, match="Could not open expense database"):
        load_expenses(path)
