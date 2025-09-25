#!/usr/bin/env python3
"""
CLI Orchestrator Audit Trail Utility (MOD-011)

Command-line interface for interacting with the enhanced audit trail system.
Provides verification, search, statistics, and analysis capabilities.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Add lib to path for audit_logger import
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from audit_logger import (
    AUDIT,
    get_audit_statistics,
    search_audit_entries,
    verify_audit_chain,
)


def format_timestamp(ts: float) -> str:
    """Format timestamp for human readable display."""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def cmd_verify(args):
    """Verify audit chain integrity."""
    print(f"Verifying audit chain: {AUDIT}")

    result = verify_audit_chain(
        start_entry=args.start_entry, max_entries=args.max_entries
    )

    print("📊 Verification Results:")
    print(f"  Status: {result['status'].upper()}")
    print(f"  Verified: {'✅ Yes' if result['verified'] else '❌ No'}")
    print(f"  Entries Checked: {result['entries_checked']}")

    if result["chain_breaks"]:
        print(f"\n🔗 Chain Breaks ({len(result['chain_breaks'])}):")
        for break_info in result["chain_breaks"][:5]:  # Show first 5
            print(f"  - Line {break_info['line_number']}: {break_info['entry_id']}")

    if result["hash_mismatches"]:
        print(f"\n🔐 Hash Mismatches ({len(result['hash_mismatches'])}):")
        for mismatch in result["hash_mismatches"][:5]:  # Show first 5
            print(
                f"  - Line {mismatch['line_number']}: {mismatch['field']} hash mismatch"
            )

    if result["invalid_entries"]:
        print(f"\n❌ Invalid Entries ({len(result['invalid_entries'])}):")
        for invalid in result["invalid_entries"][:5]:  # Show first 5
            print(f"  - Line {invalid['line_number']}: {invalid['error']}")

    if result.get("error"):
        print(f"\n⚠️  Error: {result['error']}")

    return 0 if result["verified"] else 1


def cmd_search(args):
    """Search audit entries with filters."""
    print("🔍 Searching audit entries...")

    # Parse time filters
    start_time = None
    end_time = None

    if args.since:
        if args.since.endswith("h"):
            hours = int(args.since[:-1])
            start_time = time.time() - (hours * 3600)
        elif args.since.endswith("d"):
            days = int(args.since[:-1])
            start_time = time.time() - (days * 86400)
        else:
            start_time = float(args.since)

    if args.until:
        end_time = float(args.until)

    # Search entries
    entries = list(
        search_audit_entries(
            task_id=args.task_id,
            phase=args.phase,
            action=args.action,
            user_id=args.user_id,
            tool=args.tool,
            start_time=start_time,
            end_time=end_time,
            limit=args.limit,
        )
    )

    print(f"📋 Found {len(entries)} matching entries:")

    for entry in entries:
        ts_str = format_timestamp(entry.get("ts", 0))
        entry_id = entry.get("entry_id", entry.get("sha", "unknown"))[:8]
        task_id = entry.get("task_id", "unknown")
        action = entry.get("action", "unknown")
        tool = entry.get("tool", "-")
        user = entry.get("user_id", "-")

        print(f"  [{ts_str}] {entry_id} | {task_id} | {action} | {tool} | {user}")

        if args.verbose:
            details = entry.get("details", {})
            if details:
                details_str = json.dumps(details, separators=(",", ":"))
                if len(details_str) > 100:
                    details_str = details_str[:97] + "..."
                print(f"    Details: {details_str}")

    return 0


def cmd_stats(args):
    """Show audit log statistics."""
    print("📈 Audit Log Statistics")

    stats = get_audit_statistics()

    if stats.get("error"):
        print(f"❌ Error: {stats['error']}")
        return 1

    print("\n📂 File Information:")
    print(f"  Location: {AUDIT}")
    print(
        f"  Size: {stats['file_size_mb']:.2f} MB ({stats['file_size_bytes']:,} bytes)"
    )
    print(f"  Total Entries: {stats['total_entries']:,}")

    if stats["earliest_entry"] and stats["latest_entry"]:
        earliest = format_timestamp(stats["earliest_entry"])
        latest = format_timestamp(stats["latest_entry"])
        duration = stats["latest_entry"] - stats["earliest_entry"]
        duration_hours = duration / 3600

        print("\n⏱️  Time Range:")
        print(f"  Earliest: {earliest}")
        print(f"  Latest: {latest}")
        print(f"  Duration: {duration_hours:.1f} hours")

    print("\n🏷️  Unique Values:")
    print(f"  Tasks: {stats['unique_tasks']}")
    print(f"  Phases: {stats['unique_phases']}")
    print(f"  Actions: {stats['unique_actions']}")
    print(f"  Tools: {stats['unique_tools']}")
    print(f"  Users: {stats['unique_users']}")

    if args.verbose:
        print("\n📊 Additional Metrics:")
        avg_entry_size = stats["file_size_bytes"] / max(stats["total_entries"], 1)
        print(f"  Average Entry Size: {avg_entry_size:.0f} bytes")

        if duration_hours > 0:
            entries_per_hour = stats["total_entries"] / duration_hours
            print(f"  Entries per Hour: {entries_per_hour:.1f}")

    return 0


def cmd_export(args):
    """Export audit entries to a file."""
    print(f"📤 Exporting audit entries to: {args.output}")

    # Parse time filters
    start_time = None
    end_time = None

    if args.since:
        if args.since.endswith("h"):
            hours = int(args.since[:-1])
            start_time = time.time() - (hours * 3600)
        elif args.since.endswith("d"):
            days = int(args.since[:-1])
            start_time = time.time() - (days * 86400)
        else:
            start_time = float(args.since)

    if args.until:
        end_time = float(args.until)

    # Export entries
    exported = 0
    try:
        with open(args.output, "w", encoding="utf-8") as outfile:
            for entry in search_audit_entries(
                task_id=args.task_id,
                phase=args.phase,
                action=args.action,
                user_id=args.user_id,
                tool=args.tool,
                start_time=start_time,
                end_time=end_time,
                limit=args.limit or 999999,
            ):
                if args.format == "json":
                    json.dump(entry, outfile, separators=(",", ":"))
                    outfile.write("\n")
                elif args.format == "csv":
                    # CSV header on first entry
                    if exported == 0:
                        outfile.write(
                            "timestamp,entry_id,task_id,phase,action,tool,user_id,success\n"
                        )

                    # CSV row
                    ts = entry.get("ts", 0)
                    entry_id = entry.get("entry_id", entry.get("sha", ""))
                    task_id = entry.get("task_id", "")
                    phase = entry.get("phase", "")
                    action = entry.get("action", "")
                    tool = entry.get("tool", "")
                    user_id = entry.get("user_id", "")
                    success = entry.get("details", {}).get("success", True)

                    outfile.write(
                        f"{ts},{entry_id},{task_id},{phase},{action},{tool},{user_id},{success}\n"
                    )

                exported += 1

        print(f"✅ Exported {exported} entries to {args.output}")
        return 0

    except Exception as e:
        print(f"❌ Export failed: {e}")
        return 1


def cmd_tail(args):
    """Show recent audit entries (like tail -f)."""
    print(f"👀 Showing last {args.lines} audit entries:")

    entries = list(search_audit_entries(limit=args.lines))

    # Reverse to show most recent last
    for entry in reversed(entries):
        ts_str = format_timestamp(entry.get("ts", 0))
        entry_id = entry.get("entry_id", entry.get("sha", "unknown"))[:8]
        task_id = entry.get("task_id", "unknown")
        action = entry.get("action", "unknown")

        print(f"[{ts_str}] {entry_id} | {task_id} | {action}")

        if args.verbose:
            details = entry.get("details", {})
            if details:
                details_str = json.dumps(details, separators=(",", ":"))
                if len(details_str) > 100:
                    details_str = details_str[:97] + "..."
                print(f"  {details_str}")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="CLI Orchestrator Audit Trail Utility (MOD-011)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify entire audit chain
  python audit_cli.py verify

  # Search for specific task entries
  python audit_cli.py search --task-id "my_task" --limit 10

  # Show entries from last 24 hours
  python audit_cli.py search --since 24h --verbose

  # Get audit statistics
  python audit_cli.py stats --verbose

  # Export recent entries to CSV
  python audit_cli.py export --since 1d --format csv --output recent.csv

  # Show last 20 entries
  python audit_cli.py tail --lines 20 --verbose
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify audit chain integrity")
    verify_parser.add_argument(
        "--start-entry",
        type=int,
        default=0,
        help="Entry number to start verification from",
    )
    verify_parser.add_argument(
        "--max-entries", type=int, help="Maximum number of entries to verify"
    )

    # Search command
    search_parser = subparsers.add_parser("search", help="Search audit entries")
    search_parser.add_argument("--task-id", help="Filter by task ID")
    search_parser.add_argument("--phase", help="Filter by phase")
    search_parser.add_argument("--action", help="Filter by action")
    search_parser.add_argument("--user-id", help="Filter by user ID")
    search_parser.add_argument("--tool", help="Filter by tool")
    search_parser.add_argument(
        "--since", help="Show entries since (e.g., 24h, 7d, or timestamp)"
    )
    search_parser.add_argument("--until", help="Show entries until timestamp")
    search_parser.add_argument(
        "--limit", type=int, default=50, help="Maximum entries to return"
    )
    search_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show entry details"
    )

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show audit log statistics")
    stats_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show additional metrics"
    )

    # Export command
    export_parser = subparsers.add_parser("export", help="Export audit entries")
    export_parser.add_argument("--output", "-o", required=True, help="Output file path")
    export_parser.add_argument(
        "--format", choices=["json", "csv"], default="json", help="Export format"
    )
    export_parser.add_argument("--task-id", help="Filter by task ID")
    export_parser.add_argument("--phase", help="Filter by phase")
    export_parser.add_argument("--action", help="Filter by action")
    export_parser.add_argument("--user-id", help="Filter by user ID")
    export_parser.add_argument("--tool", help="Filter by tool")
    export_parser.add_argument(
        "--since", help="Show entries since (e.g., 24h, 7d, or timestamp)"
    )
    export_parser.add_argument("--until", help="Show entries until timestamp")
    export_parser.add_argument("--limit", type=int, help="Maximum entries to export")

    # Tail command
    tail_parser = subparsers.add_parser("tail", help="Show recent audit entries")
    tail_parser.add_argument(
        "--lines", "-n", type=int, default=10, help="Number of recent entries to show"
    )
    tail_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show entry details"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Check if audit file exists
    if not AUDIT.exists() and args.command != "verify":
        print(f"❌ Audit file not found: {AUDIT}")
        print("No audit entries have been logged yet.")
        return 1

    # Execute command
    if args.command == "verify":
        return cmd_verify(args)
    elif args.command == "search":
        return cmd_search(args)
    elif args.command == "stats":
        return cmd_stats(args)
    elif args.command == "export":
        return cmd_export(args)
    elif args.command == "tail":
        return cmd_tail(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
