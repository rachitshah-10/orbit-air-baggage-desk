import datetime
import sqlite3
import pytest

from db import init_db
from claims import file_claim, list_claims, get_claim, get_claim_history


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
