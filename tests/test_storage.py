import json
from datetime import date
from pathlib import Path

import pytest

from expense_tracker.models import Expense
from expense_tracker.storage import (
    StorageError,
    add_expense,
    delete_expense,
    list_expenses,
    load_expenses,
    save_expenses,
    summarize_expenses,
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


def test_missing_data_file_loads_as_empty(tmp_path: Path) -> None:
    assert load_expenses(tmp_path / "expenses.json") == []


def test_save_and_load_round_trip_creates_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "expenses.json"
    expenses = [make_expense(1250, "food", "2025-01-02", "food1234", "Lunch")]

    save_expenses(expenses, path)

    assert load_expenses(path) == expenses
    assert json.loads(path.read_text(encoding="utf-8"))[0]["amount_cents"] == 1250


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("{not json", "Invalid JSON"),
        ("{}", "JSON array"),
        ('[{"amount_cents": 0}]', "Invalid expense record"),
    ],
)
def test_load_rejects_malformed_data(
    tmp_path: Path, content: str, message: str
) -> None:
    path = tmp_path / "expenses.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(StorageError, match=message):
        load_expenses(path)


def test_load_reports_unreadable_data_path(tmp_path: Path) -> None:
    path = tmp_path / "directory"
    path.mkdir()

    with pytest.raises(StorageError, match="Could not read expenses"):
        load_expenses(path)


def test_load_reports_invalid_utf8(tmp_path: Path) -> None:
    path = tmp_path / "expenses.json"
    path.write_bytes(b"\xff")

    with pytest.raises(StorageError, match="not valid UTF-8"):
        load_expenses(path)


def test_save_failure_preserves_existing_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expenses.json"
    original = [make_expense(100, "food", "2025-01-01", "original")]
    save_expenses(original, path)
    original_content = path.read_text(encoding="utf-8")

    def fail_replace(source: Path, target: Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("expense_tracker.storage.os.replace", fail_replace)

    with pytest.raises(StorageError, match="replace failed"):
        save_expenses([make_expense(200, "travel", "2025-01-02", "next")], path)

    assert path.read_text(encoding="utf-8") == original_content
    assert load_expenses(path) == original
    assert list(tmp_path.glob("*.tmp")) == []


def test_add_expense_persists_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "expenses.json"
    expense = make_expense(875, "food", "2025-02-03", "expense1")

    assert add_expense(expense, path) == expense
    assert load_expenses(path) == [expense]
    with pytest.raises(ValueError, match="already exists"):
        add_expense(expense, path)


def test_list_expenses_filters_and_sorts_newest_first(tmp_path: Path) -> None:
    path = tmp_path / "expenses.json"
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
            tmp_path / "expenses.json",
            start_date="2025-03-02",
            end_date="2025-03-01",
        )


def test_summarize_expenses_uses_integer_cents_and_selected_month(
    tmp_path: Path,
) -> None:
    path = tmp_path / "expenses.json"
    save_expenses(
        [
            make_expense(125, "food", "2025-03-01", "food1"),
            make_expense(275, "food", "2025-03-02", "food2"),
            make_expense(300, "travel", "2025-03-03", "travel1"),
            make_expense(900, "food", "2025-04-01", "future"),
        ],
        path,
    )

    assert summarize_expenses(path, month="2025-03") == (
        700,
        {"food": 400, "travel": 300},
    )


def test_summarize_expenses_defaults_to_injected_current_month(
    tmp_path: Path,
) -> None:
    path = tmp_path / "expenses.json"
    save_expenses(
        [
            make_expense(125, "food", "2025-03-01", "current"),
            make_expense(275, "food", "2025-04-01", "other"),
        ],
        path,
    )

    assert summarize_expenses(path, today=date(2025, 3, 10)) == (
        125,
        {"food": 125},
    )


@pytest.mark.parametrize("month", ["", "0000-01", "2025-13", "2025-1"])
def test_summarize_expenses_rejects_invalid_month(
    tmp_path: Path, month: str
) -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        summarize_expenses(tmp_path / "expenses.json", month=month)


def test_delete_expense_removes_match_and_reports_missing_id(tmp_path: Path) -> None:
    path = tmp_path / "expenses.json"
    keep = make_expense(100, "food", "2025-01-01", "keep")
    remove = make_expense(200, "travel", "2025-01-02", "remove")
    save_expenses([keep, remove], path)

    assert delete_expense("remove", path) is True
    assert load_expenses(path) == [keep]
    assert delete_expense("missing", path) is False
