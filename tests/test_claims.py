import datetime
import sqlite3

import pytest

from claims import (
    assign_claim,
    close_claim,
    file_claim,
    get_claim,
    get_claim_history,
    list_claims,
    resolve_claim,
)
from db import init_db


@pytest.fixture
def conn():
    """Provides an in-memory SQLite database initialized with the schema."""
    connection = sqlite3.connect(":memory:")
    init_db(connection)
    yield connection
    connection.close()


def test_schema_check_constraints(conn):
    """Verify CHECK constraints on type, tier, and status at the database layer."""
    now_str = "2026-11-04T12:00:00"

    # Invalid type should violate CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("John Doe", "OA101", "destroyed", "gold", "open", now_str, now_str),
        )

    # Invalid tier should violate CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("John Doe", "OA101", "lost", "diamond", "open", now_str, now_str),
        )

    # Invalid status should violate CHECK constraint
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            INSERT INTO claims (passenger, flight, type, tier, status, filed_at, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("John Doe", "OA101", "lost", "gold", "unknown_status", now_str, now_str),
        )


def test_file_claim_success_and_deadline_by_tier(conn):
    """Verify filing claims computes correct deadlines for gold (4h), silver (24h), and standard (72h)."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)

    # Gold: 4 hours
    gold_id = file_claim(conn, "Alice Gold", "OA100", "delayed", "gold", note="VIP", now=now)
    gold_claim = get_claim(conn, gold_id)
    assert gold_claim["status"] == "open"
    assert gold_claim["deadline"] == "2026-11-04T14:00:00"

    # Silver: 24 hours
    silver_id = file_claim(conn, "Bob Silver", "OA200", "lost", "silver", now=now)
    silver_claim = get_claim(conn, silver_id)
    assert silver_claim["deadline"] == "2026-11-05T10:00:00"

    # Standard: 72 hours
    std_id = file_claim(conn, "Charlie Std", "OA300", "damaged", "standard", now=now)
    std_claim = get_claim(conn, std_id)
    assert std_claim["deadline"] == "2026-11-07T10:00:00"

    # Verify initial history entry for filing
    history = get_claim_history(conn, gold_id)
    assert len(history) == 1
    assert history[0]["old_status"] is None
    assert history[0]["new_status"] == "open"
    assert history[0]["changed_at"] == "2026-11-04T10:00:00"


def test_file_claim_rejects_blank_passenger(conn):
    """Verify blank passenger name is rejected with a clear error."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    with pytest.raises(ValueError, match="passenger.*cannot be blank"):
        file_claim(conn, "", "OA100", "lost", "gold", now=now)
    with pytest.raises(ValueError, match="passenger.*cannot be blank"):
        file_claim(conn, "   ", "OA100", "lost", "gold", now=now)


def test_file_claim_rejects_blank_flight(conn):
    """Verify blank flight number is rejected with a clear error."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    with pytest.raises(ValueError, match="flight.*cannot be blank"):
        file_claim(conn, "John Doe", "", "lost", "gold", now=now)
    with pytest.raises(ValueError, match="flight.*cannot be blank"):
        file_claim(conn, "John Doe", "   ", "lost", "gold", now=now)


def test_file_claim_rejects_unknown_type(conn):
    """Verify unknown claim type is rejected with a clear error."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    with pytest.raises(ValueError, match="Invalid claim type"):
        file_claim(conn, "John Doe", "OA100", "stolen", "gold", now=now)


def test_file_claim_rejects_unknown_tier(conn):
    """Verify unknown tier is rejected with a clear error."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    with pytest.raises(ValueError, match="Invalid tier"):
        file_claim(conn, "John Doe", "OA100", "lost", "vip", now=now)


def test_list_claims_filtering(conn):
    """Verify listing claims with status and tier filters."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    file_claim(conn, "Passenger 1", "OA1", "lost", "gold", now=now)
    file_claim(conn, "Passenger 2", "OA2", "delayed", "silver", now=now)
    file_claim(conn, "Passenger 3", "OA3", "damaged", "gold", now=now)

    # All claims
    all_claims = list_claims(conn)
    assert len(all_claims) == 3

    # Filter by tier
    gold_claims = list_claims(conn, tier="gold")
    assert len(gold_claims) == 2
    assert all(c["tier"] == "gold" for c in gold_claims)

    silver_claims = list_claims(conn, tier="silver")
    assert len(silver_claims) == 1

    # Filter by status
    open_claims = list_claims(conn, status="open")
    assert len(open_claims) == 3

    resolved_claims = list_claims(conn, status="resolved")
    assert len(resolved_claims) == 0


# ==============================================================================
# Tests for Branch 2: feature/assign-and-status
# ==============================================================================


def test_assign_claim_success(conn):
    """Verify assigning an open claim changes status to assigned and sets agent."""
    t0 = datetime.datetime(2026, 11, 4, 10, 0, 0)
    t1 = datetime.datetime(2026, 11, 4, 11, 0, 0)

    claim_id = file_claim(conn, "Jane Doe", "OA500", "lost", "gold", now=t0)
    assign_claim(conn, claim_id, agent="Agent Smith", now=t1, changed_by="Agent Smith")

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "assigned"
    assert claim["assigned_agent"] == "Agent Smith"

    history = get_claim_history(conn, claim_id)
    assert len(history) == 2
    assert history[1]["old_status"] == "open"
    assert history[1]["new_status"] == "assigned"
    assert history[1]["changed_by"] == "Agent Smith"
    assert history[1]["changed_at"] == "2026-11-04T11:00:00"


def test_resolve_claim_success(conn):
    """Verify resolving an assigned claim transitions status to resolved."""
    t0 = datetime.datetime(2026, 11, 4, 10, 0, 0)
    t1 = datetime.datetime(2026, 11, 4, 11, 0, 0)
    t2 = datetime.datetime(2026, 11, 4, 12, 0, 0)

    claim_id = file_claim(conn, "Jane Doe", "OA500", "delayed", "silver", now=t0)
    assign_claim(conn, claim_id, agent="Agent Smith", now=t1)
    resolve_claim(conn, claim_id, now=t2, changed_by="Agent Smith")

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "resolved"

    history = get_claim_history(conn, claim_id)
    assert len(history) == 3
    assert history[2]["old_status"] == "assigned"
    assert history[2]["new_status"] == "resolved"
    assert history[2]["changed_by"] == "Agent Smith"
    assert history[2]["changed_at"] == "2026-11-04T12:00:00"


def test_close_claim_success(conn):
    """Verify closing a resolved claim transitions status to closed."""
    t0 = datetime.datetime(2026, 11, 4, 10, 0, 0)
    t1 = datetime.datetime(2026, 11, 4, 11, 0, 0)
    t2 = datetime.datetime(2026, 11, 4, 12, 0, 0)
    t3 = datetime.datetime(2026, 11, 4, 13, 0, 0)

    claim_id = file_claim(conn, "Jane Doe", "OA500", "damaged", "standard", now=t0)
    assign_claim(conn, claim_id, agent="Agent Smith", now=t1)
    resolve_claim(conn, claim_id, now=t2)
    close_claim(conn, claim_id, now=t3, changed_by="Supervisor")

    claim = get_claim(conn, claim_id)
    assert claim["status"] == "closed"

    history = get_claim_history(conn, claim_id)
    assert len(history) == 4
    assert history[3]["old_status"] == "resolved"
    assert history[3]["new_status"] == "closed"
    assert history[3]["changed_by"] == "Supervisor"
    assert history[3]["changed_at"] == "2026-11-04T13:00:00"


def test_disallowed_status_transitions_rejected(conn):
    """Verify disallowed status transitions raise clear errors."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)

    # 1. open -> resolved is disallowed
    c1 = file_claim(conn, "Passenger A", "OA1", "lost", "gold", now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'open' to 'resolved'"):
        resolve_claim(conn, c1, now=now)

    # 2. open -> closed is disallowed
    with pytest.raises(ValueError, match="Cannot transition claim from 'open' to 'closed'"):
        close_claim(conn, c1, now=now)

    # 3. assigned -> closed is disallowed
    assign_claim(conn, c1, agent="Agent 1", now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'assigned' to 'closed'"):
        close_claim(conn, c1, now=now)

    # 4. resolved -> assigned is disallowed
    resolve_claim(conn, c1, now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'resolved' to 'assigned'"):
        assign_claim(conn, c1, agent="Agent 2", now=now)

    # 5. closed -> anything is disallowed
    close_claim(conn, c1, now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'closed'"):
        assign_claim(conn, c1, agent="Agent 3", now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'closed'"):
        resolve_claim(conn, c1, now=now)
    with pytest.raises(ValueError, match="Cannot transition claim from 'closed'"):
        close_claim(conn, c1, now=now)


def test_assign_claim_rejects_blank_agent(conn):
    """Verify assigning a claim with a blank agent name is rejected with clear error."""
    now = datetime.datetime(2026, 11, 4, 10, 0, 0)
    claim_id = file_claim(conn, "Passenger B", "OA2", "delayed", "silver", now=now)

    with pytest.raises(ValueError, match="agent.*cannot be blank"):
        assign_claim(conn, claim_id, agent="", now=now)
    with pytest.raises(ValueError, match="agent.*cannot be blank"):
        assign_claim(conn, claim_id, agent="   ", now=now)


def test_escalated_claim_transitions(conn):
    """Verify escalated claims can be assigned or resolved."""
    t0 = datetime.datetime(2026, 11, 4, 10, 0, 0)
    t1 = datetime.datetime(2026, 11, 4, 15, 0, 0)

    # Simulate an escalated claim in database
    claim_id = file_claim(conn, "Passenger C", "OA3", "lost", "gold", now=t0)
    with conn:
        conn.execute("UPDATE claims SET status = 'escalated' WHERE id = ?", (claim_id,))
        conn.execute(
            "INSERT INTO history (claim_id, old_status, new_status, changed_by, changed_at) VALUES (?, 'open', 'escalated', 'system', ?)",
            (claim_id, t1.isoformat()),
        )

    # escalated -> assigned should succeed
    assign_claim(conn, claim_id, agent="Specialist Agent", now=t1)
    claim = get_claim(conn, claim_id)
    assert claim["status"] == "assigned"
    assert claim["assigned_agent"] == "Specialist Agent"

    # Reset to escalated
    with conn:
        conn.execute("UPDATE claims SET status = 'escalated' WHERE id = ?", (claim_id,))

    # escalated -> resolved should succeed
    resolve_claim(conn, claim_id, now=t1)
    claim = get_claim(conn, claim_id)
    assert claim["status"] == "resolved"


def test_complete_history_audit_trail(conn):
    """Verify atomic and full audit history across multiple status transitions."""
    t0 = datetime.datetime(2026, 11, 4, 10, 0, 0)
    t1 = datetime.datetime(2026, 11, 4, 11, 0, 0)
    t2 = datetime.datetime(2026, 11, 4, 12, 0, 0)
    t3 = datetime.datetime(2026, 11, 4, 13, 0, 0)

    claim_id = file_claim(conn, "Full Audit", "OA999", "lost", "gold", now=t0, changed_by="Filer")
    assign_claim(conn, claim_id, agent="Agent 1", now=t1, changed_by="Supervisor")
    resolve_claim(conn, claim_id, now=t2, changed_by="Agent 1")
    close_claim(conn, claim_id, now=t3, changed_by="Manager")

    history = get_claim_history(conn, claim_id)
    assert len(history) == 4

    # Entry 1: filing
    assert history[0]["old_status"] is None
    assert history[0]["new_status"] == "open"
    assert history[0]["changed_by"] == "Filer"
    assert history[0]["changed_at"] == t0.isoformat()

    # Entry 2: assignment
    assert history[1]["old_status"] == "open"
    assert history[1]["new_status"] == "assigned"
    assert history[1]["changed_by"] == "Supervisor"
    assert history[1]["changed_at"] == t1.isoformat()

    # Entry 3: resolution
    assert history[2]["old_status"] == "assigned"
    assert history[2]["new_status"] == "resolved"
    assert history[2]["changed_by"] == "Agent 1"
    assert history[2]["changed_at"] == t2.isoformat()

    # Entry 4: closure
    assert history[3]["old_status"] == "resolved"
    assert history[3]["new_status"] == "closed"
    assert history[3]["changed_by"] == "Manager"
    assert history[3]["changed_at"] == t3.isoformat()
