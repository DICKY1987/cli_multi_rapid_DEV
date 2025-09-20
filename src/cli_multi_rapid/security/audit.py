"""
Audit logging for CLI Orchestrator.

Provides comprehensive audit trail for security events,
workflow executions, and system operations.
"""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class AuditEvent:
    """Structured audit event."""

    timestamp: float
    user_id: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    success: bool = True
    details: Dict[str, Any] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class AuditLogger:
    """Audit logger for CLI Orchestrator security events."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(exist_ok=True)
        self._lock = asyncio.Lock()

    async def log_event(
        self,
        user_id: str,
        action: str,
        resource: str,
        resource_id: Optional[str] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log an audit event."""
        event = AuditEvent(
            timestamp=time.time(),
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            success=success,
            details=details or {},
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._write_event(event)

    async def log_workflow_event(
        self,
        user_id: str,
        action: str,
        workflow_id: str,
        workflow_name: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log workflow-specific audit event."""
        workflow_details = {"workflow_name": workflow_name, **(details or {})}

        await self.log_event(
            user_id=user_id,
            action=action,
            resource="workflow",
            resource_id=workflow_id,
            success=success,
            details=workflow_details,
        )

    async def log_adapter_event(
        self,
        user_id: str,
        action: str,
        adapter_name: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log adapter usage audit event."""
        adapter_details = {"adapter_name": adapter_name, **(details or {})}

        await self.log_event(
            user_id=user_id,
            action=action,
            resource="adapter",
            resource_id=adapter_name,
            success=success,
            details=adapter_details,
        )

    async def log_security_event(
        self,
        user_id: str,
        action: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log security-specific audit event."""
        await self.log_event(
            user_id=user_id,
            action=action,
            resource="security",
            success=success,
            details=details,
            ip_address=ip_address,
        )

    async def log_api_request(
        self,
        user_id: str,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log API request audit event."""
        await self.log_event(
            user_id=user_id,
            action="api_request",
            resource="api",
            resource_id=f"{method} {endpoint}",
            success=status_code < 400,
            details={
                "method": method,
                "endpoint": endpoint,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def _write_event(self, event: AuditEvent) -> None:
        """Write audit event to log file."""
        async with self._lock:
            try:
                event_json = json.dumps(asdict(event), separators=(",", ":"))

                with open(self.log_file, "a") as f:
                    f.write(event_json + "\n")

            except Exception as e:
                # Fallback logging to avoid losing audit events
                import logging

                logging.error(f"Failed to write audit event: {e}")
                logging.info(f"Lost audit event: {event}")

    async def search_events(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Search audit events with filters."""
        if not self.log_file.exists():
            return []

        events = []
        count = 0

        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    if count >= limit:
                        break

                    try:
                        event_data = json.loads(line.strip())
                        event = AuditEvent(**event_data)

                        # Apply filters
                        if user_id and event.user_id != user_id:
                            continue
                        if action and event.action != action:
                            continue
                        if resource and event.resource != resource:
                            continue
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue
                        if success is not None and event.success != success:
                            continue

                        events.append(event)
                        count += 1

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            import logging

            logging.error(f"Failed to search audit events: {e}")

        return list(reversed(events))  # Most recent first

    async def get_user_activity_summary(
        self, user_id: str, hours: int = 24
    ) -> Dict[str, Any]:
        """Get activity summary for a user."""
        start_time = time.time() - (hours * 3600)
        events = await self.search_events(
            user_id=user_id, start_time=start_time, limit=1000
        )

        summary = {
            "user_id": user_id,
            "time_range_hours": hours,
            "total_events": len(events),
            "successful_events": len([e for e in events if e.success]),
            "failed_events": len([e for e in events if not e.success]),
            "actions": {},
            "resources": {},
            "recent_activities": [],
        }

        # Count by action
        for event in events:
            summary["actions"][event.action] = (
                summary["actions"].get(event.action, 0) + 1
            )

        # Count by resource
        for event in events:
            summary["resources"][event.resource] = (
                summary["resources"].get(event.resource, 0) + 1
            )

        # Recent activities (last 10)
        summary["recent_activities"] = [
            {
                "timestamp": event.timestamp,
                "action": event.action,
                "resource": event.resource,
                "resource_id": event.resource_id,
                "success": event.success,
            }
            for event in events[:10]
        ]

        return summary

    async def get_security_incidents(
        self, hours: int = 24, include_failed_only: bool = True
    ) -> list[AuditEvent]:
        """Get potential security incidents."""
        start_time = time.time() - (hours * 3600)

        # Security-relevant actions
        security_actions = [
            "login_failed",
            "permission_denied",
            "rate_limit_exceeded",
            "api_key_misuse",
            "workflow_pattern_blocked",
            "adapter_blocked",
            "account_locked",
            "token_invalid",
            "unauthorized_access",
        ]

        incidents = []
        for action in security_actions:
            events = await self.search_events(
                action=action,
                start_time=start_time,
                success=False if include_failed_only else None,
                limit=50,
            )
            incidents.extend(events)

        # Sort by timestamp (most recent first)
        incidents.sort(key=lambda x: x.timestamp, reverse=True)

        return incidents[:100]  # Return top 100

    async def export_audit_log(
        self,
        output_file: Path,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        format: str = "jsonl",
    ) -> int:
        """Export audit log to file."""
        if not self.log_file.exists():
            return 0

        exported_count = 0

        try:
            with open(self.log_file, "r") as infile, open(output_file, "w") as outfile:
                for line in infile:
                    try:
                        event_data = json.loads(line.strip())
                        event = AuditEvent(**event_data)

                        # Apply time filters
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue

                        if format == "jsonl":
                            outfile.write(line)
                        elif format == "csv":
                            # Convert to CSV format
                            csv_line = f"{event.timestamp},{event.user_id},{event.action},{event.resource},{event.resource_id or ''},{event.success}\n"
                            outfile.write(csv_line)

                        exported_count += 1

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            import logging

            logging.error(f"Failed to export audit log: {e}")

        return exported_count

    def get_log_stats(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        if not self.log_file.exists():
            return {"total_events": 0, "file_size": 0}

        try:
            file_size = self.log_file.stat().st_size
            line_count = 0

            with open(self.log_file, "r") as f:
                line_count = sum(1 for _ in f)

            return {
                "total_events": line_count,
                "file_size_bytes": file_size,
                "file_size_mb": file_size / (1024 * 1024),
                "log_file": str(self.log_file),
            }

        except Exception as e:
            import logging

            logging.error(f"Failed to get log stats: {e}")
            return {"error": str(e)}
