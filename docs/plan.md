# Expense Tracker Implementation Plan

## Goal

Build a small command-line tool for recording, listing, summarizing, and deleting
personal expenses. Keep the implementation readable, use the Python standard
library where practical, and keep business logic vout of the CLI.

## Expense data

Represent each expense with:

- A human readable/typeable, short, unique ID for lookup and deletion.
- An amount stored as integer cents, never a floating-point number. 
- A required category, trimmed of surrounding whitespace.
- A date stored as an ISO 8601 string (`YYYY-MM-DD`), defaulting to today.
- An optional note.

Validate required values, amounts, and dates before changing persisted data.
Report invalid input with clear, specific errors.

## Commands

- `add`: Accept an amount and category, plus optional date and note. Validate
  inputs, save the expense, and display a confirmation with its ID. Amounts entered must be parsed with either string handling or decimal data types. No more than two decimal places are allowed.
- `list`: Display expenses newest date first. Support optional date-range and
  category filters, and explain when no records match.
- `summary`: Default to the current month, with an option to select a month.
  Display the total and totals grouped by category. Perform calculations using
  integer cents.
- `delete`: Remove the expense matching a required ID. Confirm success and
  clearly report when the ID does not exist.

Keep output human-readable and the initial filter options limited to those
described above.

## Architecture

- `src/expense_tracker/cli.py`: Define the `argparse` commands, call the
  appropriate model and storage operations, and format user-facing output.
  Keep business logic out of this file.
- `src/expense_tracker/models.py`: Define the expense representation and
  validation for its fields. Data-file path and today's date must be overridable for tests.
- `src/expense_tracker/storage.py`: Own all data-file access and operations for
  loading, saving, adding, listing/filtering, and deleting
  expenses.

Keep persistence behind the storage boundary so JSON can later be replaced by
SQLite without moving CLI behavior or model validation into the database layer.

## Persistence and data safety

Use JSON for the initial storage format. Select and document a predictable
per-user data-file location so expense data is not stored in the repository by
default. If a repository-local file is chosen instead, add it to `.gitignore`.
Malformed or unreadable data must produce a clear error; do not silently treat
it as an empty tracker. A solution must be implemented to prevent corruption or
loss of data in case of error. Writing to a temporary file and then replacing the 
original on successful save is an option.

## Tests

Replace the placeholder-only test coverage with focused tests for:

- Model validation, including amount and date edge cases.
- JSON loading and saving, including malformed or unreadable data.
- Adding, listing, filtering, summarizing, and deleting expenses.
- Command argument handling and user-visible success and error cases.

Tests must use a temp data path and a fixed date, never the real data file or the real current date.

## Implementation sequence

1. Define the expense model and field validation.
2. Implement JSON storage operations and test persistence and failure cases.
3. Implement the four CLI commands using the model and storage interfaces.
4. Add or complete command-level tests and verify documented usage.
5. Run the test suite and Ruff checks; update the README with the working
   commands and data-file location.

## Completion criteria

- The four commands work with JSON-backed persistence.
- Amounts are stored and summarized as integer cents; dates use
  `YYYY-MM-DD`.
- Invalid input and storage failures are reported clearly without corrupting
  data or returning success-shaped output.
- Tests cover the core behaviors and important failure cases.
- README usage and storage-location documentation match the implementation.
