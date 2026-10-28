# Expense Tracker Implementation Plan

## Goal

Build a small command-line tool for recording, listing, summarizing, and deleting
personal expenses. Keep the implementation readable, use the Python standard
library where practical, and keep business logic out of the CLI.

## Status key

- `[x]` Complete
- `[ ]` Not complete

## Existing foundation

- [x] Define the expense model, including validation and integer-cent amounts.
- [x] Implement the `add`, `list`, `summary`, and `delete` CLI commands.
- [x] Cover the existing model, JSON storage, and CLI behavior with tests.
- [x] Document the current JSON storage and command usage in the README.

The items above describe the current implementation. The SQLite migration work
below is still to be completed.

## Expense data

Represent each expense with:

- A short, unique ID for lookup and deletion.
- An amount stored as integer cents, never as a floating-point number.
- A required category, trimmed of surrounding whitespace.
- A date stored as an ISO 8601 string (`YYYY-MM-DD`), defaulting to today.
- An optional note.

Validate required values, amounts, and dates before changing persisted data.
Report invalid input with clear, specific errors.

## Commands

Keep the existing command behavior and user-facing output consistent:

- `add`: Accept an amount and category, plus optional date and note. Validate
  inputs, save the expense, and display a confirmation with its ID. Amounts
  must have no more than two decimal places.
- `list`: Display expenses newest date first. Support optional date-range and
  category filters, and explain when no records match.
- `summary`: Default to the current month, with an option to select a month.
  Display the total and totals grouped by category using integer cents.
- `delete`: By default, display a numbered menu of expenses from the current
  month. Allow `--month YYYY-MM` to choose another month, remove the selected
  entry, and allow cancellation without deleting anything.
- `import-json <path>`: Import expenses from an existing JSON file into the
  SQLite database. Report success only after the complete import commits.

Keep output human-readable and the existing filters limited to those described
above. JSON is an import format only; it is not used for ongoing storage, and
the import command must leave the source file unchanged.

## Architecture

- `src/expense_tracker/cli.py`: Define the `argparse` commands, call model and
  storage operations, and format user-facing output. Keep business logic out of
  this file.
- `src/expense_tracker/models.py`: Define the expense representation, field
  validation, and expense summarization calculations. Keep date inputs
  overridable for deterministic tests.
- `src/expense_tracker/storage.py`: Own all SQLite access and operations for
  creating the schema, loading, adding, listing/filtering, deleting, and
  importing expenses. Return expense records to the model layer rather than
  calculating summaries in storage.

Use Python's standard-library `sqlite3` module; do not add a dependency. Keep
persistence behind the storage boundary so database details do not leak into
the CLI or model validation.

## Persistence and data safety

- SQLite is the primary and only ongoing storage backend.
- Store the database at `~/.expense_tracker/expenses.sqlite3` by default
  (for example, `%USERPROFILE%\.expense_tracker\expenses.sqlite3` on Windows).
  Keep the database path injectable so tests use a temporary database.
- Create the parent directory and database schema when needed. Use a table with
  columns for the expense ID, integer-cent amount, category, ISO date, and
  optional note. Enforce unique IDs and appropriate field constraints.
- Use parameterized SQL for values and transactions for data changes. Import
  all records in one transaction so a malformed record or duplicate ID cannot
  leave a partial import; report the error clearly and preserve existing
  database contents.
- Missing databases should initialize as an empty tracker. SQLite and file
  errors must be reported clearly, not treated as an empty tracker or success.
- JSON importing must validate the existing array-and-record format and reuse
  the expense model's validation. It must not delete, rewrite, or otherwise
  modify the source JSON file.
- Add the SQLite database and its journal/sidecar files to `.gitignore` if any
  of these files could be created inside the repository.

## Tests

Keep tests isolated from the real per-user database and current date. Use
temporary database and JSON paths, and inject a fixed date where relevant.
Cover:

- Model validation, including amount and date edge cases.
- SQLite schema initialization, persistence across connections, and storage
  error handling.
- Adding, listing, filtering, and deleting expenses, including duplicate IDs.
- JSON import success, malformed or invalid JSON records, duplicate-ID
  conflicts, transaction rollback, and preservation of the source file.
- CLI argument handling, the `import-json` command, and user-visible success
  and error cases for both import and existing commands.

## Implementation sequence

1. [x] Replace JSON as the primary storage with SQLite in `storage.py`; define
   schema initialization, the default database path, injectable test paths,
   CRUD operations, and clear transactional/error behavior.
2. [x] Implement the JSON-to-SQLite import operation. Validate the complete
   source before committing, roll back the whole import on failure, and leave
   the source file unchanged.
3. [ ] Update the CLI to use SQLite for all existing commands and add
   `import-json <path>`, preserving existing command behavior and reporting
   import failures without success-shaped output.
4. [ ] Update storage and CLI tests for the SQLite backend and JSON import,
   while retaining coverage for existing behavior.
5. [ ] Update the README with SQLite as primary storage, the default database
   location, the JSON import command, and the fact that JSON is not used for
   ongoing storage.
6. [ ] Update `.gitignore` if needed to exclude repository-local SQLite
   databases and sidecar files.
7. [ ] Run the test suite and Ruff checks; fix any issues introduced by the
   migration.

## Completion criteria

- SQLite is the primary storage backend for every existing expense command.
- The database initializes safely and persists validated expenses using integer
  cents and ISO dates.
- JSON expenses can be imported explicitly; invalid data or ID conflicts do not
  cause partial imports, and the source JSON remains unchanged.
- CLI output and behavior remain consistent for existing commands, with clear
  errors for storage and import failures.
- Tests cover SQLite persistence, CRUD, import, important failure cases, and
  CLI behavior using isolated temporary paths.
- README usage and storage-location documentation match the implementation.
- The test suite and Ruff checks pass.
