import argparse
import datetime
import sys

from claims import (
    assign_claim,
    close_claim,
    escalate_overdue_claims,
    file_claim,
    get_claim,
    get_claim_history,
    get_tier_report,
    list_claims,
    resolve_claim,
    seed_claims_from_csv,
)
from db import get_connection


def parse_args(args=None):
    """Parse top-level arguments and subcommands."""
    parser = argparse.ArgumentParser(
        description="Orbit Air Baggage Desk CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Global options (must be specified before command name)
    parser.add_argument(
        "--now",
        type=str,
        default=None,
        help="Simulated current time in ISO format (e.g. 2026-11-04T14:00:00)",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="claims.db",
        help="Path to SQLite database file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. file
    p_file = subparsers.add_parser("file", help="File a new baggage claim")
    p_file.add_argument("--passenger", required=True, help="Passenger full name")
    p_file.add_argument("--flight", required=True, help="Flight number")
    p_file.add_argument(
        "--type",
        required=True,
        choices=["delayed", "lost", "damaged"],
        help="Claim type",
    )
    p_file.add_argument(
        "--tier",
        required=True,
        choices=["standard", "silver", "gold"],
        help="Passenger tier",
    )
    p_file.add_argument("--note", default="", help="Optional claim notes")

    # 2. list
    p_list = subparsers.add_parser("list", help="List claims with optional filters")
    p_list.add_argument("--status", default=None, help="Filter by status")
    p_list.add_argument("--tier", default=None, help="Filter by tier")

    # 3. assign
    p_assign = subparsers.add_parser("assign", help="Assign a claim to an agent")
    p_assign.add_argument("claim_id", type=int, help="Claim ID")
    p_assign.add_argument("--agent", required=True, help="Agent name")

    # 4. resolve
    p_resolve = subparsers.add_parser("resolve", help="Resolve an assigned or escalated claim")
    p_resolve.add_argument("claim_id", type=int, help="Claim ID")

    # 5. close
    p_close = subparsers.add_parser("close", help="Close a resolved claim")
    p_close.add_argument("claim_id", type=int, help="Claim ID")

    # 6. escalate
    subparsers.add_parser("escalate", help="Escalate overdue open and assigned claims")

    # 7. history
    p_history = subparsers.add_parser("history", help="Show audit history for a claim")
    p_history.add_argument("claim_id", type=int, help="Claim ID")

    # 8. seed
    p_seed = subparsers.add_parser("seed", help="Load claims from a CSV file")
    p_seed.add_argument("csv_path", type=str, help="Path to CSV file")

    # STRETCH GOAL 2: report
    subparsers.add_parser(
        "report", help="Report counts of open and overdue claims by tier"
    )

    return parser.parse_args(args)


def main(argv=None):
    """Main CLI entrypoint."""
    parsed = parse_args(argv)

    # Determine current timestamp: inject --now if provided, otherwise real clock
    if parsed.now:
        now_dt = datetime.datetime.fromisoformat(parsed.now)
    else:
        now_dt = datetime.datetime.now()

    conn = get_connection(parsed.db)

    try:
        cmd = parsed.command

        if cmd == "file":
            claim_id = file_claim(
                conn=conn,
                passenger=parsed.passenger,
                flight=parsed.flight,
                claim_type=parsed.type,
                tier=parsed.tier,
                note=parsed.note,
                now=now_dt,
            )
            claim = get_claim(conn, claim_id)
            print(
                f"Filed claim #{claim_id} for {claim['passenger']} (Flight: {claim['flight']}, "
                f"Tier: {claim['tier']}, Status: {claim['status']}, Deadline: {claim['deadline']})"
            )

        elif cmd == "list":
            claims = list_claims(conn, status=parsed.status, tier=parsed.tier)
            if not claims:
                print("No claims found.")
            else:
                print(f"{'ID':<4} {'Passenger':<18} {'Flight':<8} {'Type':<8} {'Tier':<9} {'Status':<10} {'Deadline'}")
                print("-" * 75)
                for c in claims:
                    print(
                        f"{c['id']:<4} {c['passenger']:<18} {c['flight']:<8} "
                        f"{c['type']:<8} {c['tier']:<9} {c['status']:<10} {c['deadline']}"
                    )

        elif cmd == "assign":
            assign_claim(conn, parsed.claim_id, agent=parsed.agent, now=now_dt)
            print(f"Assigned claim #{parsed.claim_id} to {parsed.agent}")

        elif cmd == "resolve":
            resolve_claim(conn, parsed.claim_id, now=now_dt)
            print(f"Resolved claim #{parsed.claim_id}")

        elif cmd == "close":
            close_claim(conn, parsed.claim_id, now=now_dt)
            print(f"Closed claim #{parsed.claim_id}")

        elif cmd == "escalate":
            escalated = escalate_overdue_claims(conn, now=now_dt)
            if escalated:
                print(f"Escalated {len(escalated)} claim(s): {escalated}")
            else:
                print("No overdue claims to escalate.")

        elif cmd == "history":
            claim = get_claim(conn, parsed.claim_id)
            if not claim:
                print(f"Claim #{parsed.claim_id} not found.")
                sys.exit(1)
            history = get_claim_history(conn, parsed.claim_id)
            print(f"Audit History for Claim #{parsed.claim_id}:")
            for h in history:
                old_s = h["old_status"] or "None"
                print(
                    f"  [{h['changed_at']}] {old_s} -> {h['new_status']} (By: {h['changed_by']})"
                )

        elif cmd == "seed":
            count = seed_claims_from_csv(conn, parsed.csv_path, now=now_dt)
            print(f"Seeded {count} claims from {parsed.csv_path}")

        elif cmd == "report":
            # STRETCH GOAL 2
            rep = get_tier_report(conn, now=now_dt)
            print(f"{'Tier':<10} {'Total':<8} {'Open/Assigned':<15} {'Overdue'}")
            print("-" * 45)
            for tier, counts in rep.items():
                print(
                    f"{tier:<10} {counts['total']:<8} {counts['open']:<15} {counts['overdue']}"
                )

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
