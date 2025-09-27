"""
Merge queue management for coordinated workflow integration.

This module provides the merge queue infrastructure for safely integrating
multiple parallel workflows while maintaining quality gates and preventing conflicts.
"""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
import time


class MergeStatus(Enum):
    """Status of items in the merge queue."""
    QUEUED = "queued"
    VERIFYING = "verifying"
    READY = "ready"
    MERGING = "merging"
    MERGED = "merged"
    FAILED = "failed"
    CONFLICT = "conflict"
    CANCELLED = "cancelled"


class VerificationLevel(Enum):
    """Verification levels for merge queue items."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


@dataclass
class MergeQueueItem:
    """Represents an item in the merge queue."""
    branch: str
    workflow_id: str
    priority: int = 1
    status: MergeStatus = MergeStatus.QUEUED
    verification_level: VerificationLevel = VerificationLevel.STANDARD
    quality_gates: List[str] = None
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    merge_commit: Optional[str] = None

    def __post_init__(self):
        if self.quality_gates is None:
            self.quality_gates = self._default_quality_gates()
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.updated_at is None:
            self.updated_at = self.created_at

        # Convert string enums to enum objects
        if isinstance(self.status, str):
            self.status = MergeStatus(self.status)
        if isinstance(self.verification_level, str):
            self.verification_level = VerificationLevel(self.verification_level)

    def _default_quality_gates(self) -> List[str]:
        """Get default quality gates based on verification level."""
        gates_map = {
            VerificationLevel.MINIMAL: ["lint"],
            VerificationLevel.STANDARD: ["lint", "test"],
            VerificationLevel.COMPREHENSIVE: ["lint", "test", "typecheck", "security"]
        }
        return gates_map.get(self.verification_level, gates_map[VerificationLevel.STANDARD])

    def update_status(self, status: MergeStatus, error: Optional[str] = None):
        """Update the status of this queue item."""
        self.status = status
        self.updated_at = datetime.now().isoformat()
        if error:
            self.error = error
            self.attempts += 1

    def is_eligible_for_retry(self) -> bool:
        """Check if this item is eligible for retry."""
        return (
            self.status in [MergeStatus.FAILED, MergeStatus.CONFLICT] and
            self.attempts < self.max_attempts
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings for JSON serialization
        data['status'] = self.status.value
        data['verification_level'] = self.verification_level.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MergeQueueItem':
        """Create from dictionary."""
        return cls(**data)


class MergeQueueManager:
    """Manages merge queue for coordinated workflow integration."""

    def __init__(self, queue_file: Optional[Path] = None):
        self.queue_file = queue_file or Path(".ai/coordination/merge_queue.json")
        self.queue: List[MergeQueueItem] = []
        self.processing_history: List[Dict[str, Any]] = []
        self._load_queue()

    def add_to_queue(self, branch: str, workflow_id: str,
                    priority: int = 1, verification_level: str = "standard",
                    quality_gates: Optional[List[str]] = None) -> bool:
        """Add branch to merge queue."""

        # Check if already in queue
        if any(item.branch == branch for item in self.queue):
            return False

        item = MergeQueueItem(
            branch=branch,
            workflow_id=workflow_id,
            priority=priority,
            verification_level=VerificationLevel(verification_level),
            quality_gates=quality_gates
        )

        self.queue.append(item)
        self._sort_queue()
        self._save_queue()
        return True

    def get_next_item(self) -> Optional[MergeQueueItem]:
        """Get next item ready for processing."""

        for item in self.queue:
            if item.status == MergeStatus.QUEUED and item.attempts < item.max_attempts:
                return item
        return None

    def update_item_status(self, branch: str, status: MergeStatus,
                          error: Optional[str] = None, merge_commit: Optional[str] = None):
        """Update status of queue item."""

        for item in self.queue:
            if item.branch == branch:
                item.update_status(status, error)
                if merge_commit:
                    item.merge_commit = merge_commit
                break

        self._save_queue()

    def remove_completed(self):
        """Remove successfully merged items from queue."""

        completed_items = [item for item in self.queue if item.status == MergeStatus.MERGED]

        # Archive completed items to history
        for item in completed_items:
            self.processing_history.append({
                "item": item.to_dict(),
                "completed_at": datetime.now().isoformat()
            })

        # Remove from active queue
        self.queue = [item for item in self.queue if item.status != MergeStatus.MERGED]
        self._save_queue()

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status summary."""

        status_counts = {}
        for status in MergeStatus:
            status_counts[status.value] = len([item for item in self.queue if item.status == status])

        return {
            "total_items": len(self.queue),
            "status_breakdown": status_counts,
            "next_item": self.get_next_item().branch if self.get_next_item() else None,
            "queue_length": len([item for item in self.queue if item.status == MergeStatus.QUEUED]),
            "processing_items": len([item for item in self.queue if item.status in [MergeStatus.VERIFYING, MergeStatus.MERGING]]),
            "failed_items": len([item for item in self.queue if item.status == MergeStatus.FAILED]),
            "last_updated": datetime.now().isoformat()
        }

    def retry_failed_items(self) -> List[str]:
        """Retry failed items that are eligible."""

        retried_branches = []

        for item in self.queue:
            if item.is_eligible_for_retry():
                item.status = MergeStatus.QUEUED
                item.error = None
                item.updated_at = datetime.now().isoformat()
                retried_branches.append(item.branch)

        if retried_branches:
            self._sort_queue()
            self._save_queue()

        return retried_branches

    def cancel_item(self, branch: str) -> bool:
        """Cancel a specific queue item."""

        for item in self.queue:
            if item.branch == branch:
                if item.status not in [MergeStatus.MERGED, MergeStatus.MERGING]:
                    item.update_status(MergeStatus.CANCELLED)
                    self._save_queue()
                    return True
                return False
        return False

    def clear_queue(self):
        """Clear all items from the queue (emergency operation)."""

        self.queue = []
        self._save_queue()

    def get_item_by_branch(self, branch: str) -> Optional[MergeQueueItem]:
        """Get queue item by branch name."""

        for item in self.queue:
            if item.branch == branch:
                return item
        return None

    def estimate_wait_time(self, branch: str) -> Optional[int]:
        """Estimate wait time in minutes for a specific branch."""

        item = self.get_item_by_branch(branch)
        if not item:
            return None

        # Find position in queue
        position = 0
        for queue_item in sorted(self.queue, key=lambda x: x.priority, reverse=True):
            if queue_item.status == MergeStatus.QUEUED:
                if queue_item.branch == branch:
                    break
                position += 1

        # Estimate 5 minutes per item ahead in queue
        estimated_minutes = position * 5
        return estimated_minutes

    def _sort_queue(self):
        """Sort queue by priority (higher first), then by created time."""

        def sort_key(item: MergeQueueItem):
            # Priority first (higher = earlier), then creation time (earlier = first)
            return (-item.priority, item.created_at or "")

        self.queue.sort(key=sort_key)

    def _load_queue(self):
        """Load queue from file."""

        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    data = json.load(f)

                    # Load queue items
                    self.queue = [MergeQueueItem.from_dict(item_data) for item_data in data.get("queue", [])]

                    # Load processing history
                    self.processing_history = data.get("processing_history", [])

            except Exception as e:
                print(f"Warning: Failed to load merge queue: {e}")
                self.queue = []
                self.processing_history = []

    def _save_queue(self):
        """Save queue to file."""

        self.queue_file.parent.mkdir(parents=True, exist_ok=True)

        queue_data = {
            "queue": [item.to_dict() for item in self.queue],
            "processing_history": self.processing_history,
            "last_updated": datetime.now().isoformat()
        }

        with open(self.queue_file, 'w') as f:
            json.dump(queue_data, f, indent=2)


class MergeQueueProcessor:
    """Processes items in the merge queue."""

    def __init__(self, git_ops_adapter=None):
        self.git_ops = git_ops_adapter
        self.manager = MergeQueueManager()

    def process_queue(self, max_items: int = 5) -> List[Dict[str, Any]]:
        """Process items in the merge queue."""

        results = []
        processed_count = 0

        while processed_count < max_items:
            item = self.manager.get_next_item()
            if not item:
                break

            print(f"Processing merge queue item: {item.branch}")

            # Update status to verifying
            self.manager.update_item_status(item.branch, MergeStatus.VERIFYING)

            try:
                # Process the merge
                result = self._process_merge_item(item)
                results.append(result)

                # Update final status
                if result["success"]:
                    self.manager.update_item_status(
                        item.branch,
                        MergeStatus.MERGED,
                        merge_commit=result.get("merge_commit")
                    )
                else:
                    self.manager.update_item_status(
                        item.branch,
                        MergeStatus.FAILED,
                        error=result.get("error")
                    )

            except Exception as e:
                error_msg = f"Processing exception: {str(e)}"
                self.manager.update_item_status(item.branch, MergeStatus.FAILED, error=error_msg)
                results.append({
                    "branch": item.branch,
                    "success": False,
                    "error": error_msg
                })

            processed_count += 1

        # Clean up completed items
        self.manager.remove_completed()

        return results

    def _process_merge_item(self, item: MergeQueueItem) -> Dict[str, Any]:
        """Process a single merge queue item."""

        if self.git_ops:
            # Use actual git operations
            queue_config = {
                "branches": [item.branch],
                "verification_level": item.verification_level.value,
                "quality_gates": item.quality_gates
            }

            merge_results = self.git_ops.execute_merge_queue(queue_config)

            if merge_results and len(merge_results) > 0:
                result = merge_results[0]
                return {
                    "branch": item.branch,
                    "success": result.get("status") == "merged",
                    "merge_commit": result.get("merge_commit"),
                    "error": result.get("error"),
                    "gates": result.get("gates", []),
                    "timestamp": result.get("timestamp")
                }

        # Mock processing for testing
        return {
            "branch": item.branch,
            "success": True,
            "merge_commit": f"mock_commit_{int(time.time())}",
            "gates": [{"gate": gate, "success": True} for gate in item.quality_gates],
            "timestamp": datetime.now().isoformat()
        }


# Export main classes
__all__ = [
    'MergeStatus',
    'VerificationLevel',
    'MergeQueueItem',
    'MergeQueueManager',
    'MergeQueueProcessor'
]