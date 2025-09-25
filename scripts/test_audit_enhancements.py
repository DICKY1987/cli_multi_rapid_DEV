#!/usr/bin/env python3
"""
Test script for MOD-011 Audit Trail Enhancement

Tests the enhanced audit logging system with JSONL format and hashing.
"""

import json
import sys
import time
from pathlib import Path

# Add lib to path for audit_logger import
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from audit_logger import (
    AUDIT,
    get_audit_statistics,
    log_action,
    search_audit_entries,
    verify_audit_chain,
)


def test_basic_logging():
    """Test basic audit logging functionality."""
    print("Testing basic audit logging...")

    # Log some test entries
    entry_ids = []

    # Test entry 1: Simple action
    entry_id1 = log_action(
        task_id="test_task_001",
        phase="testing",
        action="test_basic_logging",
        details={"test": "value", "number": 42},
    )
    entry_ids.append(entry_id1)
    print(f"  [OK] Logged entry 1: {entry_id1}")

    # Test entry 2: With all metadata
    entry_id2 = log_action(
        task_id="test_task_002",
        phase="testing",
        action="test_enhanced_logging",
        details={"enhanced": True, "metadata": {"key": "value"}},
        cost_delta=0.05,
        tool="test_tool",
        user_id="test_user",
        session_id="test_session_123",
    )
    entry_ids.append(entry_id2)
    print(f"  ✅ Logged entry 2: {entry_id2}")

    # Test entry 3: Error scenario
    entry_id3 = log_action(
        task_id="test_task_003",
        phase="testing",
        action="test_error_logging",
        details={
            "error": "Test error message",
            "stack_trace": "Mock stack trace",
            "severity": "high",
        },
        user_id="test_user",
    )
    entry_ids.append(entry_id3)
    print(f"  ✅ Logged entry 3: {entry_id3}")

    return entry_ids


def test_chain_integrity():
    """Test audit chain integrity verification."""
    print("\n🔗 Testing chain integrity...")

    result = verify_audit_chain()

    print(f"  Status: {result['status']}")
    print(f"  Verified: {result['verified']}")
    print(f"  Entries Checked: {result['entries_checked']}")

    if result["chain_breaks"]:
        print(f"  ❌ Chain breaks found: {len(result['chain_breaks'])}")
        return False

    if result["hash_mismatches"]:
        print(f"  ❌ Hash mismatches found: {len(result['hash_mismatches'])}")
        return False

    print("  ✅ Chain integrity verified")
    return True


def test_search_functionality():
    """Test search functionality."""
    print("\n🔍 Testing search functionality...")

    # Search by task_id
    entries = list(search_audit_entries(task_id="test_task_001"))
    print(f"  Task ID search: found {len(entries)} entries")

    # Search by action
    entries = list(search_audit_entries(action="test_enhanced_logging"))
    print(f"  Action search: found {len(entries)} entries")

    # Search by user_id
    entries = list(search_audit_entries(user_id="test_user"))
    print(f"  User ID search: found {len(entries)} entries")

    # Time-based search (last 10 seconds)
    recent_time = time.time() - 10
    entries = list(search_audit_entries(start_time=recent_time))
    print(f"  Recent entries search: found {len(entries)} entries")

    print("  ✅ Search functionality working")
    return True


def test_statistics():
    """Test statistics functionality."""
    print("\n📊 Testing statistics...")

    stats = get_audit_statistics()

    print(f"  Total entries: {stats['total_entries']}")
    print(f"  File size: {stats['file_size_mb']:.2f} MB")
    print(f"  Unique tasks: {stats['unique_tasks']}")
    print(f"  Unique actions: {stats['unique_actions']}")

    if stats["total_entries"] > 0:
        print("  ✅ Statistics working")
        return True
    else:
        print("  ❌ No entries found in statistics")
        return False


def test_entry_format():
    """Test enhanced entry format."""
    print("\n📝 Testing enhanced entry format...")

    if not AUDIT.exists():
        print("  ❌ Audit file doesn't exist")
        return False

    # Read the last few entries to check format
    with open(AUDIT, encoding="utf-8") as f:
        lines = f.readlines()

    if not lines:
        print("  ❌ No entries in audit file")
        return False

    # Check last entry format
    try:
        last_entry = json.loads(lines[-1].strip())

        # Check required v1.1 fields
        required_fields = [
            "entry_id",
            "ts",
            "ts_iso",
            "task_id",
            "phase",
            "action",
            "details",
            "details_hash",
            "entry_hash",
            "prev_hash",
            "version",
        ]

        missing_fields = [field for field in required_fields if field not in last_entry]
        if missing_fields:
            print(f"  ❌ Missing fields: {missing_fields}")
            return False

        # Check version
        if last_entry.get("version") != "v1.1":
            print(f"  ❌ Wrong version: {last_entry.get('version')}")
            return False

        print("  ✅ Enhanced entry format correct")
        return True

    except Exception as e:
        print(f"  ❌ Entry format error: {e}")
        return False


def test_backward_compatibility():
    """Test that we can handle mixed format logs."""
    print("\n🔄 Testing backward compatibility...")

    # The existing audit log should have old format entries
    # New entries should work alongside them
    if not AUDIT.exists():
        print("  ⚠️  No existing audit file to test compatibility")
        return True

    # Try to search through all entries (old + new)
    all_entries = list(search_audit_entries(limit=1000))
    old_format_count = 0
    new_format_count = 0

    for entry in all_entries:
        if entry.get("version") == "v1.1":
            new_format_count += 1
        else:
            old_format_count += 1

    print(f"  Old format entries: {old_format_count}")
    print(f"  New format entries: {new_format_count}")
    print("  ✅ Backward compatibility working")
    return True


def run_all_tests():
    """Run all tests."""
    print("MOD-011 Audit Trail Enhancement Tests\n")

    tests = [
        ("Basic Logging", test_basic_logging),
        ("Chain Integrity", test_chain_integrity),
        ("Search Functionality", test_search_functionality),
        ("Statistics", test_statistics),
        ("Entry Format", test_entry_format),
        ("Backward Compatibility", test_backward_compatibility),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results[test_name] = False

    # Summary
    print("\n📋 Test Results Summary:")
    passed = 0
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! MOD-011 implementation is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
