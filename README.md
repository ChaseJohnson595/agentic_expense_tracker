# Expense Tracker

A small command-line tool for logging and summarizing personal expenses.

This is a learning project for practicing agent-assisted development and standard engineering habits: version control, testing, linting, and CI.

> **Status:** In development. The usage examples below describe the planned interface and may change as commands are built.

## Features (planned)

- Add an expense with an amount, category, date, and optional note
- List expenses, with optional filtering
- Summarize spending by month and category
- Delete an expense
- Local storage (JSON first, SQLite later)

## Requirements

- Python 3.12+

## Setup

```bash
git clone <your-repo-url>
cd expense-tracker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install pytest ruff
pip install -e .                 # once pyproject.toml is configured
```

## Usage (planned)

```bash
python -m expense_tracker add 12.50 --category food --note "Lunch"
python -m expense_tracker list
python -m expense_tracker summary --month 2026-10
python -m expense_tracker delete <id>
```

Run `python -m expense_tracker --help` for the current list of commands.

## Development

```bash
python -m pytest -q      # run tests
ruff check .             # lint
ruff format .            # format
```

CI runs the tests and lint on every push once the GitHub Actions workflow is added.

## Project structure

```
src/expense_tracker/
    cli.py        argument parsing and output
    models.py     data classes and validation
    storage.py    reading and writing data
tests/            one test file per module
docs/plan.md      design decisions and task checklist
```

## Design notes

- Amounts are stored as integer cents to avoid floating-point errors.
- Dates are stored as ISO 8601 strings (`YYYY-MM-DD`).
- Business logic lives outside `cli.py` so it can be tested directly.

See `docs/plan.md` for the full plan and progress.

## Contributing

This is a personal learning project. Work happens on short-lived branches and is merged through pull requests once tests and lint pass.
