# Expense Tracker

Command-line tool for logging and summarizing personal expenses. Learning project: prefer simple, readable code over clever code.

## Stack
- Python 3.14, standard library first. Ask before adding any dependency.
- CLI: `argparse`. Storage: JSON file (current), SQLite (planned).
- Tests: `pytest`. Lint/format: `ruff`.

## Commands
The virtual environment already exists at `.venv`. Never create, delete, or reinstall it, and never run `pip install` without asking. Run every tool through the venv path below, never bare `python`, `pytest`, or `ruff`.
- Run tests: `.venv\Scripts\python.exe -m pytest -q`
- Lint: `.venv\Scripts\ruff.exe check .`
- Format: `.venv\Scripts\ruff.exe format .`
- Run app: `.venv\Scripts\expense-tracker.exe <command>`
If a command fails, report the error and ask before trying anything else.

## Layout
- `src/expense_tracker/cli.py`: argument parsing and output only
- `src/expense_tracker/models.py`: data classes and validation
- `src/expense_tracker/storage.py`: all reading/writing of data
- `tests/`: one `test_<module>.py` per module

## Conventions
- Add type hints to all function signatures.
- Keep functions under 30 lines; one job per function.
- Store money as integer cents, never floats.
- Store dates as ISO 8601 strings (`YYYY-MM-DD`).
- Put no business logic in `cli.py`; call `models` or `storage` instead.
- Raise specific exceptions with clear messages; do not use bare `except`.

## Workflow
- For changes touching more than one file, propose a short plan and wait for approval before editing.
- Make one small change per request. Do not refactor unrelated code.
- Add or update a test for every behavior change, then run the tests and report the result.
- Fix lint errors before finishing.
- If requirements are unclear, ask one question instead of guessing.

## Do not
- Edit `.github/` unless the task is about CI, or touch files outside this repo.
- Delete or rewrite existing tests to make them pass.
