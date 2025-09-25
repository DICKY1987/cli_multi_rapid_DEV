#!/usr/bin/env python3
"""Simple test for MOD-011 Audit Trail Enhancement"""

import sys
from pathlib import Path

# Add lib to path for audit_logger import
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from audit_logger import get_audit_statistics, log_action, verify_audit_chain


def main():
    print("Testing MOD-011 Enhanced Audit System...")

    # Test 1: Log some entries
    print("\n1. Testing basic logging...")
    entry_id1 = log_action(
        task_id="test_001",
        phase="testing",
        action="mod_011_test",
        details={"test": "value", "enhanced": True},
        user_id="test_user",
    )
    print(f"   Logged entry: {entry_id1}")

    entry_id2 = log_action(
        task_id="test_002",
        phase="testing",
        action="chain_test",
        details={"chain": "integrity", "test": 2},
        user_id="test_user",
    )
    print(f"   Logged entry: {entry_id2}")

    # Test 2: Verify chain integrity
    print("\n2. Testing chain integrity...")
    result = verify_audit_chain()
    print(f"   Status: {result['status']}")
    print(f"   Verified: {result['verified']}")
    print(f"   Entries checked: {result['entries_checked']}")

    # Test 3: Get statistics
    print("\n3. Testing statistics...")
    stats = get_audit_statistics()
    print(f"   Total entries: {stats['total_entries']}")
    print(f"   File size: {stats['file_size_mb']:.3f} MB")
    print(f"   Unique tasks: {stats['unique_tasks']}")

    print("\nMOD-011 Enhancement Test Complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
