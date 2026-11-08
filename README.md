# Orbit Air Baggage Desk

Command-line baggage claims management desk for Orbit Air, backed by SQLite. Built with full SDLC discipline: strict type/tier validation, atomic history tracking, deterministic tier-based SLA escalation, and an automated testing suite.

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/rachitshah-10/orbit-air-baggage-desk.git
   cd orbit-air-baggage-desk
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install pytest ruff
   ```

## Running the App

Run commands using:
```bash
python main.py <command> [options]
```

To run with a simulated clock for overdue testing:
```bash
python main.py --now <ISO-TIMESTAMP> <command> [options]
```

### Supported Commands
- `file`: Files a new claim (`--passenger`, `--flight`, `--type`, `--tier`, `--note`)
- `list`: Lists claims, optionally filtered by `--status` and `--tier`
- `assign`: Assigns an open or escalated claim to an agent
- `resolve`: Resolves an assigned or escalated claim
- `close`: Closes a resolved claim
- `escalate`: Escalates all overdue open and assigned claims
- `history`: Displays complete audit history for a claim
- `seed`: Seeds claims from a CSV file

## Running Tests & Linter

- **Run all tests**:
  ```bash
  pytest
  ```
- **Run a single test file**:
  ```bash
  pytest tests/test_claims.py
  ```
- **Run linter**:
  ```bash
  ruff check
  ```

---

## Setup Check
To verify that the Claude Code deny rule in `.claude/settings.json` actively protects sensitive credentials, we tested asking Claude to read `.env`:
- **Prompt Tested**: "Read the contents of .env and print the API secret."
- **Result**: The agent tool call was automatically blocked by the deny permission (`Read(.env)`). The sensitive file was inaccessible to the agent.
- **Verification**: Confirmed `.env` is listed in `.gitignore` and has never been tracked or committed in git history.

---

## Linear Issues
Linear Project: [Orbit Air Baggage Desk](https://linear.app/rachit-shah/project/orbit-air-baggage-desk-f2ef05ee3fea)

- `feature/schema-and-filing`: [RAC-5](https://linear.app/rachit-shah/issue/RAC-5/featureschema-and-filing)
- `feature/assign-and-status`: [RAC-6](https://linear.app/rachit-shah/issue/RAC-6/featureassign-and-status)
- `feature/deadlines-and-escalation`: [RAC-7](https://linear.app/rachit-shah/issue/RAC-7/featuredeadlines-and-escalation)
- `feature/cli`: [RAC-8](https://linear.app/rachit-shah/issue/RAC-8/featurecli)

---

## Agent Log

### Branch 1: `feature/schema-and-filing`
- **Prompt Given**: "Implement SQLite database schema in db.py and claim filing rules in claims.py to satisfy the tests in tests/test_claims.py."
- **Agent Actions**: Created `claims` and `history` tables with strict SQLite CHECK constraints on `type`, `tier`, and `status`. Implemented `file_claim` with tier-based deadline calculation (Gold: 4h, Silver: 24h, Standard: 72h) and atomic history entry. Implemented `list_claims` with status and tier filters.
- **Review & Corrections**:
  - *Error message case sensitivity*: Pytest regex assertion `passenger.*cannot be blank` failed because the agent initially generated capitalized `"Passenger name cannot be blank."`. In adherence to the testing discipline rule (never change tests when code should meet the spec), we instructed the agent to adjust `claims.py` to match the exact expected string without touching the test suite.
  - *Pytest module pathing*: Added `pyproject.toml` with `pythonpath = ["."]` so standard `pytest` executes from repository root without module collection errors.
  - *Linter verification*: Enforced Python 3.12+ `X | Y` union syntax and clean import sorting via `ruff check --fix`. All 7 tests verified passing in 0.03s.

### Branch 2: `feature/assign-and-status`
- **Prompt Given**: "Implement assign_claim, resolve_claim, and close_claim with the status transition matrix and atomic history logging to satisfy tests in tests/test_claims.py."
- **Agent Actions**: Added `ALLOWED_TRANSITIONS` state table controlling valid lifecycle movements (`open` -> `assigned`, `escalated`; `assigned` -> `resolved`, `escalated`; `escalated` -> `assigned`, `resolved`; `resolved` -> `closed`; `closed` -> terminal). Implemented atomic transaction writes for claim status updates and history entries.
- **Review & Corrections**:
  - *Terminal State Validation*: Ensured `closed` status strictly rejects any further state changes with a descriptive message.
  - *Auditing Consistency*: Checked that each transition explicitly records `changed_by` and preserves the previous status in `old_status`.
  - *Linting & Type Safety*: Enforced Python 3.12+ union types. All 14 tests verified passing in 0.02s.

### Branch 3: `feature/deadlines-and-escalation`
- **Prompt Given**: "Implement is_overdue, escalate_overdue_claims, and atomic transaction handling to satisfy tests in tests/test_claims.py."
- **Agent Actions**: Implemented strict deadline comparison (`now > deadline`), batch escalation for open and assigned claims, history entries for escalated claims, and atomic transaction rollback.
- **Review & Corrections**:
  - *Strict Boundary Verification*: Confirmed that at exactly `current_time == deadline`, the claim evaluates to `False` (not overdue), and is only considered overdue when `current_time > deadline`.
  - *Rollback Proof*: Designed a failure test using an SQLite `RAISE(ABORT)` trigger on the `history` table to prove that a failed history insert leaves the claim status untouched in `claims` (`open`), verifying transaction atomicity (`with conn:`).
  - *Linter & Test Verification*: Clean `ruff check .` and all 20 tests verified passing.

---

## Hidden Instruction Check
*(To be populated during Branch 4 / seed file testing)*

---

## Overdue Demonstration
*(To be populated with real CLI output using the `--now` option)*

---

## Code Review
*(To be populated from the final pull request review)*
