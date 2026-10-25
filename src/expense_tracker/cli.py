import argparse
import sys
from calendar import monthrange
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from expense_tracker.models import (
    Expense,
    create_expense,
    summarize_expenses,
    validate_month,
)
from expense_tracker.storage import (
    DEFAULT_DATA_PATH,
    StorageError,
    add_expense,
    delete_expense,
    list_expenses,
    load_expenses,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Log and summarize expenses.")
    commands = parser.add_subparsers(dest="command", required=True)

    add_parser = commands.add_parser("add", help="Add an expense.")
    add_parser.add_argument("amount", help="Expense amount, with up to two decimals.")
    add_parser.add_argument("--category", required=True, help="Expense category.")
    add_parser.add_argument("--date", dest="expense_date", help="Date in YYYY-MM-DD.")
    add_parser.add_argument("--note", help="Optional note.")

    list_parser = commands.add_parser("list", help="List expenses.")
    list_parser.add_argument("--start-date", help="Include expenses on or after date.")
    list_parser.add_argument("--end-date", help="Include expenses on or before date.")
    list_parser.add_argument("--category", help="Filter by category.")

    summary_parser = commands.add_parser("summary", help="Summarize monthly expenses.")
    summary_parser.add_argument("--month", help="Month to summarize in YYYY-MM format.")

    delete_parser = commands.add_parser("delete", help="Choose an expense to delete.")
    delete_parser.add_argument(
        "--month", help="Month of expenses to choose from, in YYYY-MM format."
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    data_path: Path | str | None = None,
    today: date | None = None,
) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    path = data_path if data_path is not None else DEFAULT_DATA_PATH
    try:
        return _dispatch(arguments, path, today)
    except (StorageError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


def _dispatch(
    arguments: argparse.Namespace, path: Path | str, today: date | None
) -> int:
    if arguments.command == "add":
        return _add(arguments, path, today)
    if arguments.command == "list":
        return _list(arguments, path)
    if arguments.command == "summary":
        return _summary(arguments, path, today)
    return _delete(arguments, path, today)


def _add(arguments: argparse.Namespace, path: Path | str, today: date | None) -> int:
    expense = create_expense(
        arguments.amount,
        arguments.category,
        arguments.expense_date,
        arguments.note,
        today=today,
    )
    add_expense(expense, path)
    print(
        f"Added expense {expense.id}: {_format_money(expense.amount_cents)} "
        f"for {expense.category} on {expense.date}."
    )
    return 0


def _list(arguments: argparse.Namespace, path: Path | str) -> int:
    expenses = list_expenses(
        path,
        start_date=arguments.start_date,
        end_date=arguments.end_date,
        category=arguments.category,
    )
    if not expenses:
        print("No expenses found.")
        return 0
    for expense in expenses:
        note = f" - {expense.note}" if expense.note else ""
        print(
            f"{expense.date}  {expense.category}  "
            f"{_format_money(expense.amount_cents)}  [{expense.id}]{note}"
        )
    return 0


def _summary(
    arguments: argparse.Namespace, path: Path | str, today: date | None
) -> int:
    selected_month = arguments.month or (today or date.today()).strftime("%Y-%m")
    total, category_totals = summarize_expenses(
        load_expenses(path), month=selected_month
    )
    print(f"Total for {selected_month}: {_format_money(total)}")
    if not category_totals:
        print("No expenses found for this month.")
    else:
        for category, amount in category_totals.items():
            print(f"{category}: {_format_money(amount)}")
    return 0


def _delete(
    arguments: argparse.Namespace, path: Path | str, today: date | None
) -> int:
    selected_month, expenses = _delete_candidates(arguments, path, today)
    if not expenses:
        print(f"No expenses to delete for {selected_month}.")
        return 0

    try:
        selected_index = _choose_expense(expenses)
    except ValueError as error:
        print(f"{error} Nothing was deleted.", file=sys.stderr)
        return 1
    if selected_index is None:
        print("Deletion cancelled.")
        return 0

    expense = expenses[selected_index - 1]
    if not delete_expense(expense.id, path):
        print("The selected expense was not found; nothing was deleted.")
        return 1
    print(
        f"Deleted expense: {expense.date}  {expense.category}  "
        f"{_format_money(expense.amount_cents)}."
    )
    return 0


def _delete_candidates(
    arguments: argparse.Namespace, path: Path | str, today: date | None
) -> tuple[str, list[Expense]]:
    selected_month = validate_month(
        arguments.month or (today or date.today()).strftime("%Y-%m")
    )
    year, month = (int(part) for part in selected_month.split("-"))
    expenses = list_expenses(
        path,
        start_date=f"{selected_month}-01",
        end_date=f"{selected_month}-{monthrange(year, month)[1]:02d}",
    )
    return selected_month, expenses


def _choose_expense(expenses: list[Expense]) -> int | None:
    print("Select an expense to delete:")
    for index, expense in enumerate(expenses, start=1):
        note = f" - {expense.note}" if expense.note else ""
        print(
            f"{index}. {expense.date}  {expense.category}  "
            f"{_format_money(expense.amount_cents)}{note}"
        )
    print("q. Cancel")

    try:
        selection = input("Choose an expense number or q: ").strip()
    except EOFError as error:
        raise ValueError("No selection received.") from error
    if selection.casefold() == "q":
        return None
    try:
        selected_index = int(selection)
    except ValueError as error:
        raise ValueError("Invalid selection.") from error
    if not 1 <= selected_index <= len(expenses):
        raise ValueError("Invalid selection.")
    return selected_index


def _format_money(amount_cents: int) -> str:
    dollars, cents = divmod(amount_cents, 100)
    return f"${dollars}.{cents:02d}"
