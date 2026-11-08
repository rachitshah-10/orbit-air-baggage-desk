import datetime
import sqlite3

VALID_TYPES = {"delayed", "lost", "damaged"}
VALID_TIERS = {"standard", "silver", "gold"}
VALID_STATUSES = {"open", "assigned", "escalated", "resolved", "closed"}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"assigned", "escalated"},
    "assigned": {"resolved", "escalated"},
    "escalated": {"assigned", "resolved"},
    "resolved": {"closed"},
    "closed": set(),
}

TIER_HOURS = {
    "gold": 4,
    "silver": 24,
    "standard": 72,
}


def _parse_time(now: datetime.datetime | str) -> datetime.datetime:
    """Normalize input timestamp into a datetime object without calling system clock."""
    if isinstance(now, datetime.datetime):
        return now
    if isinstance(now, str):
        return datetime.datetime.fromisoformat(now)
    raise ValueError("Current time must be provided as a datetime object or an ISO string.")


def file_claim(
    conn: sqlite3.Connection,
    passenger: str,
    flight: str,
    claim_type: str,
    tier: str,
    note: str = "",
    now: datetime.datetime | str = ...,
    changed_by: str = "system",
) -> int:
    """File a new baggage claim with strict validation, deadline calculation, and history logging."""
    if now is ... or now is None:
        raise ValueError("A timestamp ('now') must be explicitly provided.")

    current_dt = _parse_time(now)
    current_iso = current_dt.isoformat()

    # Passenger name validation
    if not passenger or not passenger.strip():
        raise ValueError("passenger name cannot be blank.")
    passenger = passenger.strip()

    # Flight number validation
    if not flight or not flight.strip():
        raise ValueError("flight number cannot be blank.")
    flight = flight.strip()

    # Claim type validation
    if claim_type not in VALID_TYPES:
        raise ValueError(
            f"Invalid claim type '{claim_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}."
        )

    # Tier validation
    if tier not in VALID_TIERS:
        raise ValueError(
            f"Invalid tier '{tier}'. Must be one of: {', '.join(sorted(VALID_TIERS))}."
        )

    # Compute deadline
    deadline_dt = current_dt + datetime.timedelta(hours=TIER_HOURS[tier])
    deadline_iso = deadline_dt.isoformat()

    # Atomic write to claims and history tables
    with conn:
        cursor = conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, note, filed_at, deadline)
            VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
            """,
            (passenger, flight, claim_type, tier, note, current_iso, deadline_iso),
        )
        claim_id = cursor.lastrowid

        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, NULL, 'open', ?, ?)
            """,
            (claim_id, changed_by, current_iso),
        )

    return claim_id


def assign_claim(
    conn: sqlite3.Connection,
    claim_id: int,
    agent: str,
    now: datetime.datetime | str = ...,
    changed_by: str | None = None,
) -> None:
    """Assign an open or escalated claim to an agent."""
    if now is ... or now is None:
        raise ValueError("A timestamp ('now') must be explicitly provided.")

    if not agent or not agent.strip():
        raise ValueError("agent name cannot be blank.")
    agent = agent.strip()

    claim = get_claim(conn, claim_id)
    if not claim:
        raise ValueError(f"Claim with ID {claim_id} not found.")

    old_status = claim["status"]
    if "assigned" not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise ValueError(
            f"Cannot transition claim from '{old_status}' to 'assigned'."
        )

    current_iso = _parse_time(now).isoformat()
    changer = changed_by or agent

    with conn:
        conn.execute(
            "UPDATE claims SET status = 'assigned', assigned_agent = ? WHERE id = ?",
            (agent, claim_id),
        )
        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, ?, 'assigned', ?, ?)
            """,
            (claim_id, old_status, changer, current_iso),
        )


def resolve_claim(
    conn: sqlite3.Connection,
    claim_id: int,
    now: datetime.datetime | str = ...,
    changed_by: str | None = None,
) -> None:
    """Resolve an assigned or escalated claim."""
    if now is ... or now is None:
        raise ValueError("A timestamp ('now') must be explicitly provided.")

    claim = get_claim(conn, claim_id)
    if not claim:
        raise ValueError(f"Claim with ID {claim_id} not found.")

    old_status = claim["status"]
    if "resolved" not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise ValueError(
            f"Cannot transition claim from '{old_status}' to 'resolved'."
        )

    current_iso = _parse_time(now).isoformat()
    changer = changed_by or claim.get("assigned_agent") or "system"

    with conn:
        conn.execute(
            "UPDATE claims SET status = 'resolved' WHERE id = ?",
            (claim_id,),
        )
        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, ?, 'resolved', ?, ?)
            """,
            (claim_id, old_status, changer, current_iso),
        )


def close_claim(
    conn: sqlite3.Connection,
    claim_id: int,
    now: datetime.datetime | str = ...,
    changed_by: str | None = None,
) -> None:
    """Close a resolved claim."""
    if now is ... or now is None:
        raise ValueError("A timestamp ('now') must be explicitly provided.")

    claim = get_claim(conn, claim_id)
    if not claim:
        raise ValueError(f"Claim with ID {claim_id} not found.")

    old_status = claim["status"]
    if "closed" not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise ValueError(
            f"Cannot transition claim from '{old_status}' to 'closed'."
        )

    current_iso = _parse_time(now).isoformat()
    changer = changed_by or "system"

    with conn:
        conn.execute(
            "UPDATE claims SET status = 'closed' WHERE id = ?",
            (claim_id,),
        )
        conn.execute(
            """
            INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at)
            VALUES (?, ?, 'closed', ?, ?)
            """,
            (claim_id, old_status, changer, current_iso),
        )


def get_claim(conn: sqlite3.Connection, claim_id: int) -> dict | None:
    """Retrieve a single claim by its ID."""
    cursor = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_claim_history(conn: sqlite3.Connection, claim_id: int) -> list[dict]:
    """Retrieve full audit history for a single claim ordered by ID."""
    cursor = conn.execute(
        "SELECT * FROM history WHERE claim_id = ? ORDER BY id ASC", (claim_id,)
    )
    return [dict(row) for row in cursor.fetchall()]


def list_claims(
    conn: sqlite3.Connection,
    status: str | None = None,
    tier: str | None = None,
) -> list[dict]:
    """List claims with optional filtering by status and/or tier."""
    query = "SELECT * FROM claims WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)

    if tier:
        query += " AND tier = ?"
        params.append(tier)

    query += " ORDER BY id ASC"
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]
