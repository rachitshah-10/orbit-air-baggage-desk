import subprocess
import sys
from pathlib import Path


def run_cli(*args, db_path: str = None):
    """Helper to run main.py via subprocess."""
    repo_root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, str(repo_root / "main.py")]
    if db_path:
        cmd.extend(["--db", db_path])
    cmd.extend(args)
    res = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)
    return res


def test_cli_file_and_list(tmp_path):
    """Verify filing and listing claims via CLI."""
    db_file = str(tmp_path / "test_claims.db")
    now_str = "2026-11-04T10:00:00"

    # File a claim
    res_file = run_cli(
        "--now",
        now_str,
        "file",
        "--passenger",
        "John CLI",
        "--flight",
        "OA101",
        "--type",
        "lost",
        "--tier",
        "gold",
        "--note",
        "Lost at gate",
        db_path=db_file,
    )
    assert res_file.returncode == 0
    assert "Filed claim #1" in res_file.stdout

    # List claims
    res_list = run_cli("list", db_path=db_file)
    assert res_list.returncode == 0
    assert "John CLI" in res_list.stdout
    assert "OA101" in res_list.stdout
    assert "gold" in res_list.stdout


def test_cli_now_option_and_escalate(tmp_path):
    """Verify --now option properly drives overdue checking and escalation."""
    db_file = str(tmp_path / "test_claims.db")
    t0 = "2026-11-04T10:00:00"

    # File gold claim (deadline 14:00:00)
    run_cli(
        "--now",
        t0,
        "file",
        "--passenger",
        "Escalate Passenger",
        "--flight",
        "OA202",
        "--type",
        "delayed",
        "--tier",
        "gold",
        db_path=db_file,
    )

    # Escalate before deadline (at 13:00:00) -> should not escalate
    res_esc_early = run_cli(
        "--now", "2026-11-04T13:00:00", "escalate", db_path=db_file
    )
    assert res_esc_early.returncode == 0
    assert "No overdue claims to escalate" in res_esc_early.stdout

    # Escalate after deadline (at 14:30:00) -> should escalate claim 1
    res_esc_late = run_cli(
        "--now", "2026-11-04T14:30:00", "escalate", db_path=db_file
    )
    assert res_esc_late.returncode == 0
    assert "Escalated 1 claim(s): [1]" in res_esc_late.stdout

    # Verify history
    res_hist = run_cli("history", "1", db_path=db_file)
    assert res_hist.returncode == 0
    assert "escalated" in res_hist.stdout


def test_cli_assign_resolve_close_lifecycle(tmp_path):
    """Verify assign, resolve, and close commands via CLI."""
    db_file = str(tmp_path / "test_claims.db")
    now_str = "2026-11-04T10:00:00"

    # File claim
    run_cli(
        "--now",
        now_str,
        "file",
        "--passenger",
        "Lifecycle User",
        "--flight",
        "OA303",
        "--type",
        "damaged",
        "--tier",
        "silver",
        db_path=db_file,
    )

    # Assign
    res_assign = run_cli("assign", "1", "--agent", "Agent Cooper", db_path=db_file)
    assert res_assign.returncode == 0
    assert "Assigned claim #1 to Agent Cooper" in res_assign.stdout

    # Resolve
    res_resolve = run_cli("resolve", "1", db_path=db_file)
    assert res_resolve.returncode == 0
    assert "Resolved claim #1" in res_resolve.stdout

    # Close
    res_close = run_cli("close", "1", db_path=db_file)
    assert res_close.returncode == 0
    assert "Closed claim #1" in res_close.stdout


def test_cli_seed_command(tmp_path):
    """Verify seed command imports valid CSV claims without error."""
    db_file = str(tmp_path / "test_claims.db")
    repo_root = Path(__file__).resolve().parent.parent
    seed_csv = repo_root / "seed_claims.csv"

    # Run seed
    res_seed = run_cli("seed", str(seed_csv), db_path=db_file)
    assert res_seed.returncode == 0
    assert "Seeded" in res_seed.stdout

    # Check that at least 10 claims were loaded
    res_list = run_cli("list", db_path=db_file)
    assert res_list.returncode == 0
    assert res_list.stdout.count("\n") >= 10
