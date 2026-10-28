import json
from datetime import date
from pathlib import Path

import pytest

from expense_tracker import cli
from expense_tracker.models import Expense
from expense_tracker.storage import load_expenses, save_expenses


def test_add_command_creates_expense_and_defaults_to_injected_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"

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
    path = tmp_path / "expenses.sqlite3"

    result = cli.main(["add", "1.234", "--category", "food"], data_path=path)

    assert result == 2
    assert "at most two decimal places" in capsys.readouterr().err
    assert not path.exists()


def test_add_command_uses_explicit_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"

    result = cli.main(
        ["add", "12.50", "--category", "food", "--date", "2025-03-01"],
        data_path=path,
        today=date(2025, 3, 10),
    )

    assert result == 0
    assert "$12.50 for food on 2025-03-01." in capsys.readouterr().out
    assert load_expenses(path)[0].date == "2025-03-01"


def test_list_command_applies_category_and_date_filters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"
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
    result = cli.main(["list"], data_path=tmp_path / "expenses.sqlite3")

    assert result == 0
    assert capsys.readouterr().out.strip() == "No expenses found."


def test_summary_command_uses_injected_current_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"
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


def test_summary_command_accepts_selected_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"
    save_expenses(
        [
            Expense(125, "food", "2025-03-01", id="march"),
            Expense(275, "food", "2025-04-01", id="april"),
        ],
        path,
    )

    result = cli.main(["summary", "--month", "2025-04"], data_path=path)

    output = capsys.readouterr().out
    assert result == 0
    assert "Total for 2025-04: $2.75" in output
    assert "food: $2.75" in output
    assert "march" not in output


def test_summary_command_rejects_invalid_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.main(
        ["summary", "--month", "2025-13"], data_path=tmp_path / "expenses.sqlite3"
    )

    assert result == 2
    assert "month must be in YYYY-MM format" in capsys.readouterr().err


def test_delete_command_lists_expenses_and_deletes_selected_entry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "expenses.sqlite3"
    keep = Expense(500, "travel", "2025-03-02", id="travel1")
    remove = Expense(125, "food", "2025-03-01", id="food1", note="Lunch")
    save_expenses([remove, keep], path)

    monkeypatch.setattr("builtins.input", lambda _prompt: "2")
    result = cli.main(["delete"], data_path=path, today=date(2025, 3, 10))

    output = capsys.readouterr().out
    assert result == 0
    assert "1. 2025-03-02  travel  $5.00" in output
    assert "2. 2025-03-01  food  $1.25 - Lunch" in output
    assert "q. Cancel" in output
    assert "Deleted expense: 2025-03-01  food  $1.25." in output
    assert load_expenses(path) == [keep]


def test_delete_command_can_be_cancelled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expenses.sqlite3"
    expense = Expense(125, "food", "2025-03-01", id="food1")
    save_expenses([expense], path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "q")

    result = cli.main(["delete"], data_path=path, today=date(2025, 3, 10))

    assert result == 0
    assert "Deletion cancelled." in capsys.readouterr().out
    assert load_expenses(path) == [expense]


def test_delete_command_handles_empty_expense_list(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"

    result = cli.main(["delete"], data_path=path, today=date(2025, 3, 10))

    assert result == 0
    assert capsys.readouterr().out.strip() == "No expenses to delete for 2025-03."
    assert not path.exists()


@pytest.mark.parametrize("selection", ["invalid", "0", "2"])
def test_delete_command_rejects_invalid_selection(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    selection: str,
) -> None:
    path = tmp_path / "expenses.sqlite3"
    expense = Expense(125, "food", "2025-03-01", id="food1")
    save_expenses([expense], path)
    monkeypatch.setattr("builtins.input", lambda _prompt: selection)

    result = cli.main(["delete"], data_path=path, today=date(2025, 3, 10))

    assert result == 1
    assert "Invalid selection. Nothing was deleted." in capsys.readouterr().err
    assert load_expenses(path) == [expense]


def test_delete_command_defaults_to_injected_current_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expenses.sqlite3"
    current = Expense(125, "food", "2025-03-01", id="current")
    previous = Expense(500, "travel", "2025-02-28", id="previous")
    save_expenses([previous, current], path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")

    result = cli.main(["delete"], data_path=path, today=date(2025, 3, 10))

    output = capsys.readouterr().out
    assert result == 0
    assert "current" not in output
    assert "2025-03-01  food  $1.25" in output
    assert "2025-02-28" not in output
    assert load_expenses(path) == [previous]


def test_delete_command_accepts_a_month_filter(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "expenses.sqlite3"
    current = Expense(125, "food", "2025-03-01", id="current")
    selected = Expense(500, "travel", "2025-02-28", id="selected")
    save_expenses([selected, current], path)
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")

    result = cli.main(
        ["delete", "--month", "2025-02"], data_path=path, today=date(2025, 3, 10)
    )

    output = capsys.readouterr().out
    assert result == 0
    assert "2025-02-28  travel  $5.00" in output
    assert "2025-03-01" not in output
    assert load_expenses(path) == [current]


def test_delete_command_rejects_invalid_month(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = cli.main(
        ["delete", "--month", "2025-13"], data_path=tmp_path / "expenses.sqlite3"
    )

    assert result == 2
    assert "month must be in YYYY-MM format" in capsys.readouterr().err


def test_cli_help_lists_all_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])

    output = capsys.readouterr().out
    assert result.value.code == 0
    assert all(
        command in output
        for command in ("add", "list", "summary", "delete", "import-json")
    )


def test_list_command_reports_storage_error_without_success_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "expenses.sqlite3"
    path.mkdir()

    result = cli.main(["list"], data_path=path)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Could not open expense database" in captured.err


def test_import_json_command_imports_expenses_without_modifying_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "expenses.json"
    source_contents = json.dumps(
        [
            {
                "id": "food1234",
                "amount_cents": 1250,
                "category": "food",
                "date": "2025-03-01",
                "note": "Lunch",
            }
        ],
        indent=2,
    )
    source.write_text(source_contents, encoding="utf-8")
    database = tmp_path / "expenses.sqlite3"

    result = cli.main(["import-json", str(source)], data_path=database)

    output = capsys.readouterr().out
    assert result == 0
    assert "Imported 1 expenses" in output
    assert str(source) in output
    assert load_expenses(database) == [
        Expense(1250, "food", "2025-03-01", id="food1234", note="Lunch")
    ]
    assert source.read_text(encoding="utf-8") == source_contents


def test_import_json_command_reports_failure_without_success_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "invalid.json"
    source.write_text("{invalid json", encoding="utf-8")

    result = cli.main(
        ["import-json", str(source)], data_path=tmp_path / "expenses.sqlite3"
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "Invalid JSON" in captured.err


def test_import_json_command_reports_duplicate_id_conflict_without_success_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "expenses.json"
    source.write_text(
        json.dumps(
            [
                {
                    "id": "existing",
                    "amount_cents": 1250,
                    "category": "food",
                    "date": "2025-03-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    database = tmp_path / "expenses.sqlite3"
    existing = Expense(500, "travel", "2025-03-02", id="existing")
    save_expenses([existing], database)

    result = cli.main(["import-json", str(source)], data_path=database)

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "expense ID already exists" in captured.err
    assert load_expenses(database) == [existing]
