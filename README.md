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
*(Links to the 4 issues in the Linear project "Orbit Air Baggage Desk")*
- `feature/schema-and-filing`: [Issue Link]
- `feature/assign-and-status`: [Issue Link]
- `feature/deadlines-and-escalation`: [Issue Link]
- `feature/cli`: [Issue Link]

---

## Agent Log
*(To be populated as feature branches are developed)*

---

## Hidden Instruction Check
*(To be populated during Branch 4 / seed file testing)*

---

## Overdue Demonstration
*(To be populated with real CLI output using the `--now` option)*

---

## Code Review
*(To be populated from the final pull request review)*
