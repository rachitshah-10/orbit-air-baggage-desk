# Implementation Plan: Orbit Air Baggage Desk

## 1. Problem Statement in Own Words
Orbit Air's current baggage handling operations rely on manual tracking across disparate spreadsheets and email chains. This lack of centralized tracking causes lost, delayed, and damaged baggage claims to routinely miss customer service deadlines. 

To resolve this operational breakdown, we are developing a robust command-line baggage claim desk backed by an SQLite relational database. The application enables airline staff to file claims, assign them to agents, manage strict status transitions, record an immutable audit history atomically, and automatically escalate overdue claims based on passenger loyalty tier SLAs.

## 2. Deadline Rules and Allowed Status Changes in Own Words

### Deadline and Overdue Rules
When a claim is filed, its resolution deadline is computed directly from the filing timestamp based on passenger tier:
- **Gold**: 4 hours from filing
- **Silver**: 24 hours from filing
- **Standard**: 72 hours from filing

A claim is considered overdue strictly when `current_time > deadline`. If the current time is exactly equal to the deadline (`current_time == deadline`), the claim is **not** overdue.

To ensure deterministic testing and support operational time shifts, all business logic functions must accept `now` as an injected argument rather than querying system time.

### Allowed Status Changes
All claims start in the `open` state. Only the following transitions are permitted:
- `open` -> `assigned`, `escalated` (escalation allowed only if claim is overdue)
- `assigned` -> `resolved`, `escalated` (escalation allowed only if claim is overdue)
- `escalated` -> `assigned`, `resolved`
- `resolved` -> `closed`
- `closed` -> (terminal state; no further transitions allowed)

Any transition outside this state machine is rejected with a clear error message. Resolved and closed claims can never be escalated under any circumstances.

## 3. Database Schema: Tables and Columns

### `claims` Table
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `passenger`: TEXT NOT NULL (non-blank check)
- `flight`: TEXT NOT NULL (non-blank check)
- `type`: TEXT NOT NULL CHECK (type IN ('delayed', 'lost', 'damaged'))
- `tier`: TEXT NOT NULL CHECK (tier IN ('standard', 'silver', 'gold'))
- `status`: TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')) DEFAULT 'open'
- `assigned_agent`: TEXT
- `note`: TEXT
- `filed_at`: TEXT NOT NULL (ISO-8601 string)
- `deadline`: TEXT NOT NULL (ISO-8601 string)

### `history` Table
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `claim_id`: INTEGER NOT NULL REFERENCES claims(id)
- `old_status`: TEXT
- `new_status`: TEXT NOT NULL CHECK (new_status IN ('open', 'assigned', 'escalated', 'resolved', 'closed'))
- `changed_by`: TEXT NOT NULL
- `changed_at`: TEXT NOT NULL (ISO-8601 string)

## 4. Branches and Planned Tests

### Branch 1: `feature/schema-and-filing` (Minimum 5 tests)
1. Verify tables creation and SQLite CHECK constraints on type and tier.
2. Verify valid filing calculates correct deadlines for Gold (4h), Silver (24h), and Standard (72h).
3. Verify rejection of blank passenger name or blank flight number.
4. Verify rejection of unknown claim types.
5. Verify rejection of unknown passenger tiers.
6. Verify listing claims with status and tier filter options.

### Branch 2: `feature/assign-and-status` (Minimum 6 tests)
1. Verify assigning an open claim changes status to `assigned` and sets agent.
2. Verify resolving an assigned claim changes status to `resolved`.
3. Verify closing a resolved claim changes status to `closed`.
4. Verify disallowed status changes (e.g., `open` -> `closed`, `resolved` -> `open`) raise clear errors.
5. Verify filing automatically records initial history entry (`old_status=None`, `new_status='open'`).
6. Verify status transitions atomically record full history (`old_status`, `new_status`, `changed_by`, `changed_at`).

### Branch 3: `feature/deadlines-and-escalation` (Minimum 6 tests)
1. Verify strict deadline edge: 1 minute before deadline is NOT overdue.
2. Verify strict deadline edge: exactly at deadline is NOT overdue.
3. Verify strict deadline edge: 1 minute after deadline IS overdue.
4. Verify batch escalation transitions all overdue open/assigned claims to `escalated` and logs history.
5. Verify non-overdue, resolved, or closed claims are not escalated.
6. Verify atomic rollback: simulate a history write failure and verify claim status does not change.

### Branch 4: `feature/cli` (Minimum 3 tests)
1. Verify CLI argument parsing and execution for all commands (`file`, `list`, `assign`, `resolve`, `close`, `escalate`, `history`).
2. Verify `--now` global option properly overrides current time across CLI commands without reading system clock.
3. Verify `seed` command successfully imports claims from a valid CSV file.

## 5. Risks and Mitigations

### Risk 1: System clock drift causing non-deterministic / flaky deadline tests
- **Mitigation**: Pure dependency injection for time. Every function in `claims.py` that evaluates deadlines requires a `now` datetime parameter. No internal calls to `datetime.now()` will exist in business logic, guaranteeing reproducible test results.

### Risk 2: Inconsistent state / partial writes if history logging fails
- **Mitigation**: Wrap all claim updates and history inserts in atomic SQLite transactions using connection context managers (`with conn:`). A dedicated test will intentionally force a history write failure to verify that claim status changes roll back completely.

### Risk 3: Credential leakage and prompt injection via external input files
- **Mitigation**: Strict `.gitignore` blocking `.env`, complemented by Claude Code deny permissions in `.claude/settings.json`. CSV notes are treated strictly as passive text data and never executed or evaluated.
