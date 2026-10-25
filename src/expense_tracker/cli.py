import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from expense_tracker.models import create_expense
from expense_tracker.storage import (
    DEFAULT_DATA_PATH,
    StorageError,
    add_expense,
    delete_expense,
    list_expenses,
    summarize_expenses,
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

    delete_parser = commands.add_parser("delete", help="Delete an expense by ID.")
    delete_parser.add_argument("expense_id", help="ID of the expense to delete.")
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
    return _delete(arguments, path)


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
    total, category_totals = summarize_expenses(path, month=selected_month, today=today)
    print(f"Total for {selected_month}: {_format_money(total)}")
    if not category_totals:
        print("No expenses found for this month.")
    else:
        for category, amount in category_totals.items():
            print(f"{category}: {_format_money(amount)}")
    return 0


def _delete(arguments: argparse.Namespace, path: Path | str) -> int:
    if not delete_expense(arguments.expense_id, path):
        print(f"Expense with ID {arguments.expense_id!r} was not found.")
        return 1
    print(f"Deleted expense {arguments.expense_id}.")
    return 0


def _format_money(amount_cents: int) -> str:
    dollars, cents = divmod(amount_cents, 100)
    return f"${dollars}.{cents:02d}"
