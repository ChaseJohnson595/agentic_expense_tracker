from datetime import date
from pathlib import Path

import pytest

from expense_tracker import cli
from expense_tracker.models import Expense
from expense_tracker.storage import load_expenses, save_expenses


def test_add_command_creates_expense_and_defaults_to_injected_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.json"

    result = cli.main(
        ["add", "12.50", "--category", " food ", "--note", "Lunch"],
        data_path=path,
        today=date(2025, 3, 10),
    )

    output = capsys.readouterr().out
    expenses = load_expenses(path)
    assert result == 0
    assert "Added expense " in output
    assert "$12.50 for food on 2025-03-10." in output
    assert len(expenses) == 1
    assert expenses[0].amount_cents == 1250
    assert expenses[0].note == "Lunch"


def test_add_command_reports_invalid_amount_without_saving(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.json"

    result = cli.main(["add", "1.234", "--category", "food"], data_path=path)

    assert result == 2
    assert "at most two decimal places" in capsys.readouterr().err
    assert not path.exists()


def test_list_command_applies_category_and_date_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.json"
    save_expenses(
        [
            Expense(1250, "food", "2025-03-01", id="food1"),
            Expense(500, "travel", "2025-03-02", id="travel1"),
            Expense(800, "Food", "2025-04-01", id="food2"),
        ],
        path,
    )

    result = cli.main(
        [
            "list",
            "--start-date",
            "2025-03-01",
            "--end-date",
            "2025-03-31",
            "--category",
            "food",
        ],
        data_path=path,
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "2025-03-01  food  $12.50  [food1]" in output
    assert "travel1" not in output
    assert "food2" not in output


def test_list_command_explains_when_no_expenses_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.main(["list"], data_path=tmp_path / "expenses.json")

    assert result == 0
    assert capsys.readouterr().out.strip() == "No expenses found."


def test_summary_command_uses_injected_current_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.json"
    save_expenses(
        [
            Expense(125, "food", "2025-03-01", id="food1"),
            Expense(275, "food", "2025-03-02", id="food2"),
            Expense(300, "travel", "2025-03-03", id="travel1"),
            Expense(900, "food", "2025-04-01", id="later"),
        ],
        path,
    )

    result = cli.main(["summary"], data_path=path, today=date(2025, 3, 10))

    output = capsys.readouterr().out
    assert result == 0
    assert "Total for 2025-03: $7.00" in output
    assert "food: $4.00" in output
    assert "travel: $3.00" in output
    assert "later" not in output


def test_summary_command_rejects_invalid_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.main(
        ["summary", "--month", "2025-13"], data_path=tmp_path / "expenses.json"
    )

    assert result == 2
    assert "month must be in YYYY-MM format" in capsys.readouterr().err


def test_delete_command_confirms_success_and_missing_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.json"
    save_expenses([Expense(125, "food", "2025-03-01", id="food1")], path)

    deleted = cli.main(["delete", "food1"], data_path=path)
    deleted_output = capsys.readouterr().out
    missing = cli.main(["delete", "missing"], data_path=path)
    missing_output = capsys.readouterr().out

    assert deleted == 0
    assert deleted_output.strip() == "Deleted expense food1."
    assert load_expenses(path) == []
    assert missing == 1
    assert "was not found" in missing_output
