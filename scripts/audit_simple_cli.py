#!/usr/bin/env python3
"""Simple CLI for MOD-011 Audit Trail System"""

import argparse
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from audit_logger import (
    AUDIT,
    get_audit_statistics,
    search_audit_entries,
    verify_audit_chain,
)


def cmd_stats():
    """Show audit statistics"""
    stats = get_audit_statistics()
    print("Audit Log Statistics:")
    print(f"  File: {AUDIT}")
    print(f"  Total entries: {stats['total_entries']}")
    print(f"  File size: {stats['file_size_mb']:.3f} MB")
    print(f"  Unique tasks: {stats['unique_tasks']}")
    print(f"  Unique phases: {stats['unique_phases']}")
    print(f"  Unique actions: {stats['unique_actions']}")


def cmd_verify():
    """Verify audit chain"""
    result = verify_audit_chain()
    print("Chain Verification Results:")
    print(f"  Status: {result['status']}")
    print(f"  Verified: {result['verified']}")
    print(f"  Entries checked: {result['entries_checked']}")

    if result["chain_breaks"]:
        print(f"  Chain breaks: {len(result['chain_breaks'])}")
    if result["hash_mismatches"]:
        print(f"  Hash mismatches: {len(result['hash_mismatches'])}")


def cmd_search(task_id=None, limit=10):
    """Search audit entries"""
    entries = list(search_audit_entries(task_id=task_id, limit=limit))
    print(f"Found {len(entries)} entries:")

    for entry in entries:
        entry_id = entry.get("entry_id", entry.get("sha", "unknown"))[:8]
        task = entry.get("task_id", "unknown")
        action = entry.get("action", "unknown")
        print(f"  {entry_id} | {task} | {action}")


def main():
    parser = argparse.ArgumentParser(description="Simple Audit CLI")
    parser.add_argument(
        "command", choices=["stats", "verify", "search"], help="Command to run"
    )
    parser.add_argument("--task-id", help="Task ID to search for")
    parser.add_argument("--limit", type=int, default=10, help="Limit results")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats()
    elif args.command == "verify":
        cmd_verify()
    elif args.command == "search":
        cmd_search(task_id=args.task_id, limit=args.limit)


if __name__ == "__main__":
    main()
