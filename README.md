# Expense Tracker

A small command-line tool for recording, listing, summarizing, and deleting
personal expenses.

This is a learning project for practicing agent-assisted development and standard engineering habits: version control, testing, linting, and CI.

## Requirements and setup

- Python 3.12 or later

Create and activate a virtual environment, then install the project:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On macOS or Linux, activate the environment with
`source .venv/bin/activate`.

## Usage

Run commands with `python -m expense_tracker`:

```text
python -m expense_tracker add 12.50 --category food --note "Lunch"
python -m expense_tracker list
python -m expense_tracker list --start-date 2026-10-01 --end-date 2026-10-31 --category food
python -m expense_tracker summary
python -m expense_tracker summary --month 2026-10
python -m expense_tracker delete <id>
```

* `add` accepts an amount with at most two decimal places, a required category,
an optional `--date` in `YYYY-MM-DD` format, and an optional `--note`. If no
date is provided, today's date is used. 
* `list` sorts newest dates first and
accepts inclusive `--start-date` and `--end-date` filters and a `--category`
filter. 
* `summary` defaults to the current month and reports integer-cent
totals overall and by category. 
* `delete` takes the expense ID shown by `add`
or `list`.

Run `python -m expense_tracker --help` or
`python -m expense_tracker <command> --help` for command help.

## Data storage

Expenses are currently stored as JSON at `~/.expense_tracker/expenses.json` (for
example, `%USERPROFILE%\.expense_tracker\expenses.json` on Windows) with future plans to migrate to SQLite. A
data file is created only when the first expense is added. Writes use a temporary
file and replace the data file only after a successful save.

## Project structure

```
src/expense_tracker/
    cli.py        argument parsing and output
    models.py     data classes and validation
    storage.py    reading and writing data
tests/            one test file per module
docs/plan.md      design decisions and task checklist
```

## Development

Install the development tools in the active environment if needed:

```text
python -m pip install pytest ruff
```

Run tests and lint:

```text
python -m pytest -q
ruff check .
```

Amounts are stored as integer cents and dates as ISO 8601 strings
(`YYYY-MM-DD`). Business logic lives outside the CLI. See [docs/plan.md](docs/plan.md)
for the design and implementation plan.
