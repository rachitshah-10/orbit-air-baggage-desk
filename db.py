import sqlite3


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Return SQLite rows as standard Python dictionaries."""
    fields = [column[0] for column in cursor.description]
    return dict(zip(fields, row))


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize SQLite database tables with strict schema and CHECK constraints."""
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = dict_factory

    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger TEXT NOT NULL,
                flight TEXT NOT NULL,
                type TEXT NOT NULL CHECK (type IN ('delayed', 'lost', 'damaged')),
                tier TEXT NOT NULL CHECK (tier IN ('standard', 'silver', 'gold')),
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
                assigned_agent TEXT,
                note TEXT,
                filed_at TEXT NOT NULL,
                deadline TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim_id INTEGER NOT NULL REFERENCES claims(id),
                old_status TEXT,
                new_status TEXT NOT NULL CHECK (new_status IN ('open', 'assigned', 'escalated', 'resolved', 'closed')),
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL
            );
            """
        )


def get_connection(db_path: str = "claims.db") -> sqlite3.Connection:
    """Open and return a database connection configured with the schema."""
    conn = sqlite3.connect(db_path)
    init_db(conn)
    return conn
