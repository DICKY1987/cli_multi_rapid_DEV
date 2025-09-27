"""
Security framework for multi-agent coordination.

This module provides security isolation and validation for coordinated
workflow execution, ensuring safe parallel execution with proper access controls.
"""

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
from enum import Enum
from datetime import datetime
import tempfile
import os


class SecurityLevel(Enum):
    """Security isolation levels for workflow execution."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccessMode(Enum):
    """File access modes for security validation."""
    READ_ONLY = "read-only"
    WRITE_ONLY = "write-only"
    READ_WRITE = "read-write"
    EXECUTE = "execute"
    NONE = "none"


@dataclass
class SecurityContext:
    """Security context for workflow execution."""
    workflow_id: str
    security_level: SecurityLevel = SecurityLevel.MEDIUM
    allowed_paths: List[str] = None
    forbidden_paths: List[str] = None
    allowed_commands: List[str] = None
    forbidden_commands: List[str] = None
    file_access_modes: Dict[str, AccessMode] = None
    network_access: bool = False
    temp_directory: Optional[str] = None
    max_file_size: int = 10_000_000  # 10MB default
    max_execution_time: int = 1800    # 30 minutes default

    def __post_init__(self):
        if self.allowed_paths is None:
            self.allowed_paths = []
        if self.forbidden_paths is None:
            self.forbidden_paths = []
        if self.allowed_commands is None:
            self.allowed_commands = []
        if self.forbidden_commands is None:
            self.forbidden_commands = []
        if self.file_access_modes is None:
            self.file_access_modes = {}

        # Convert string enums to enum objects
        if isinstance(self.security_level, str):
            self.security_level = SecurityLevel(self.security_level)


@dataclass
class SecurityViolation:
    """Represents a security violation."""
    violation_type: str
    description: str
    workflow_id: str
    severity: str = "medium"
    timestamp: Optional[str] = None
    context: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.context is None:
            self.context = {}


@dataclass
class IsolationEnvironment:
    """Isolated execution environment for workflows."""
    environment_id: str
    workflow_id: str
    temp_directory: Path
    allowed_files: Set[str] = None
    sandbox_root: Optional[Path] = None
    environment_variables: Dict[str, str] = None
    resource_limits: Dict[str, Any] = None

    def __post_init__(self):
        if self.allowed_files is None:
            self.allowed_files = set()
        if self.environment_variables is None:
            self.environment_variables = {}
        if self.resource_limits is None:
            self.resource_limits = {
                'max_memory': 1024 * 1024 * 1024,  # 1GB
                'max_cpu_time': 1800,               # 30 minutes
                'max_open_files': 100
            }


class SecurityManager:
    """Manages security contexts and isolation for coordinated workflows."""

    def __init__(self, base_security_dir: Optional[Path] = None):
        self.base_security_dir = base_security_dir or Path(".ai/security")
        self.base_security_dir.mkdir(parents=True, exist_ok=True)
        self.active_contexts: Dict[str, SecurityContext] = {}
        self.active_environments: Dict[str, IsolationEnvironment] = {}
        self.violation_log = self.base_security_dir / "violations.jsonl"

    def create_security_context(self, workflow_id: str, coordination_metadata: Dict[str, Any]) -> SecurityContext:
        """Create security context based on workflow coordination metadata."""

        coordination = coordination_metadata.get('coordination', {})
        risk_level = coordination.get('risk_level', 'medium')

        # Map risk level to security level
        security_level_map = {
            'low': SecurityLevel.LOW,
            'medium': SecurityLevel.MEDIUM,
            'high': SecurityLevel.HIGH,
            'critical': SecurityLevel.CRITICAL
        }
        security_level = security_level_map.get(risk_level, SecurityLevel.MEDIUM)

        # Extract file scope for allowed paths
        file_scope = coordination.get('file_scope', [])
        allowed_paths = file_scope.copy()

        # Add safe default paths
        allowed_paths.extend([
            "artifacts/**",
            "logs/**",
            ".ai/coordination/**",
            "temp/**"
        ])

        # Define forbidden paths based on security level
        forbidden_paths = self._get_forbidden_paths(security_level)

        # Define allowed commands based on security level
        allowed_commands = self._get_allowed_commands(security_level)

        context = SecurityContext(
            workflow_id=workflow_id,
            security_level=security_level,
            allowed_paths=allowed_paths,
            forbidden_paths=forbidden_paths,
            allowed_commands=allowed_commands,
            network_access=security_level in [SecurityLevel.LOW, SecurityLevel.MEDIUM],
            max_execution_time=coordination.get('timeout_minutes', 30) * 60
        )

        self.active_contexts[workflow_id] = context
        return context

    def create_isolation_environment(self, workflow_id: str,
                                   security_context: SecurityContext) -> IsolationEnvironment:
        """Create isolated execution environment for workflow."""

        environment_id = f"env_{workflow_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Create temporary directory for isolation
        temp_dir = Path(tempfile.mkdtemp(prefix=f"workflow_{workflow_id}_"))

        # Create sandbox root if high security
        sandbox_root = None
        if security_context.security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            sandbox_root = temp_dir / "sandbox"
            sandbox_root.mkdir(parents=True, exist_ok=True)

        # Set up environment variables
        env_vars = {
            'WORKFLOW_ID': workflow_id,
            'SECURITY_LEVEL': security_context.security_level.value,
            'TEMP_DIR': str(temp_dir),
            'COORDINATION_MODE': 'true'
        }

        # Create allowed files set from security context
        allowed_files = set()
        for pattern in security_context.allowed_paths:
            # Convert glob patterns to actual file paths (simplified)
            if "*" not in pattern:
                allowed_files.add(pattern)

        environment = IsolationEnvironment(
            environment_id=environment_id,
            workflow_id=workflow_id,
            temp_directory=temp_dir,
            allowed_files=allowed_files,
            sandbox_root=sandbox_root,
            environment_variables=env_vars
        )

        self.active_environments[workflow_id] = environment
        return environment

    def validate_file_access(self, workflow_id: str, file_path: str,
                           access_mode: AccessMode) -> bool:
        """Validate if workflow can access file with specified mode."""

        if workflow_id not in self.active_contexts:
            self._log_violation(SecurityViolation(
                violation_type="context_not_found",
                description=f"No security context found for workflow {workflow_id}",
                workflow_id=workflow_id,
                severity="high"
            ))
            return False

        context = self.active_contexts[workflow_id]

        # Check forbidden paths first
        for forbidden_pattern in context.forbidden_paths:
            if self._path_matches_pattern(file_path, forbidden_pattern):
                self._log_violation(SecurityViolation(
                    violation_type="forbidden_path",
                    description=f"Access to forbidden path: {file_path}",
                    workflow_id=workflow_id,
                    severity="high",
                    context={"file_path": file_path, "access_mode": access_mode.value}
                ))
                return False

        # Check allowed paths
        allowed = False
        for allowed_pattern in context.allowed_paths:
            if self._path_matches_pattern(file_path, allowed_pattern):
                allowed = True
                break

        if not allowed:
            self._log_violation(SecurityViolation(
                violation_type="unauthorized_path",
                description=f"Access to unauthorized path: {file_path}",
                workflow_id=workflow_id,
                severity="medium",
                context={"file_path": file_path, "access_mode": access_mode.value}
            ))
            return False

        # Check specific access mode restrictions
        if file_path in context.file_access_modes:
            required_mode = context.file_access_modes[file_path]
            if not self._access_mode_compatible(required_mode, access_mode):
                self._log_violation(SecurityViolation(
                    violation_type="access_mode_violation",
                    description=f"Incompatible access mode for {file_path}",
                    workflow_id=workflow_id,
                    severity="medium",
                    context={
                        "file_path": file_path,
                        "required_mode": required_mode.value,
                        "requested_mode": access_mode.value
                    }
                ))
                return False

        return True

    def validate_command_execution(self, workflow_id: str, command: str) -> bool:
        """Validate if workflow can execute specified command."""

        if workflow_id not in self.active_contexts:
            return False

        context = self.active_contexts[workflow_id]

        # Check forbidden commands
        for forbidden_cmd in context.forbidden_commands:
            if command.startswith(forbidden_cmd):
                self._log_violation(SecurityViolation(
                    violation_type="forbidden_command",
                    description=f"Execution of forbidden command: {command}",
                    workflow_id=workflow_id,
                    severity="high",
                    context={"command": command}
                ))
                return False

        # Check allowed commands
        if context.allowed_commands:  # If allowlist is defined
            allowed = False
            for allowed_cmd in context.allowed_commands:
                if command.startswith(allowed_cmd):
                    allowed = True
                    break

            if not allowed:
                self._log_violation(SecurityViolation(
                    violation_type="unauthorized_command",
                    description=f"Execution of unauthorized command: {command}",
                    workflow_id=workflow_id,
                    severity="medium",
                    context={"command": command}
                ))
                return False

        return True

    def cleanup_environment(self, workflow_id: str) -> bool:
        """Clean up isolation environment for workflow."""

        try:
            if workflow_id in self.active_environments:
                environment = self.active_environments[workflow_id]

                # Clean up temporary directory
                if environment.temp_directory.exists():
                    import shutil
                    shutil.rmtree(environment.temp_directory, ignore_errors=True)

                # Remove from active environments
                del self.active_environments[workflow_id]

            # Remove security context
            if workflow_id in self.active_contexts:
                del self.active_contexts[workflow_id]

            return True

        except Exception as e:
            self._log_violation(SecurityViolation(
                violation_type="cleanup_error",
                description=f"Failed to cleanup environment: {str(e)}",
                workflow_id=workflow_id,
                severity="low",
                context={"error": str(e)}
            ))
            return False

    def get_security_summary(self, coordination_id: str) -> Dict[str, Any]:
        """Get security summary for coordination session."""

        violations = []
        try:
            if self.violation_log.exists():
                with open(self.violation_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            violation_data = json.loads(line.strip())
                            # Filter by coordination context (simplified)
                            violations.append(violation_data)
        except Exception:
            pass

        return {
            'coordination_id': coordination_id,
            'active_contexts': len(self.active_contexts),
            'active_environments': len(self.active_environments),
            'total_violations': len(violations),
            'high_severity_violations': len([v for v in violations if v.get('severity') == 'high']),
            'violations': violations[-10:],  # Last 10 violations
            'timestamp': datetime.now().isoformat()
        }

    def _get_forbidden_paths(self, security_level: SecurityLevel) -> List[str]:
        """Get forbidden file paths based on security level."""

        base_forbidden = [
            "/etc/**",
            "/root/**",
            "/home/*/.ssh/**",
            "/home/*/.aws/**",
            "**/.env",
            "**/secrets/**",
            "**/credentials/**"
        ]

        if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            base_forbidden.extend([
                "/usr/bin/**",
                "/bin/**",
                "/sbin/**",
                "**/.git/config",
                "**/node_modules/**"
            ])

        return base_forbidden

    def _get_allowed_commands(self, security_level: SecurityLevel) -> List[str]:
        """Get allowed commands based on security level."""

        if security_level == SecurityLevel.LOW:
            return []  # No restrictions

        base_allowed = [
            "git status",
            "git diff",
            "git log",
            "ls",
            "cat",
            "head",
            "tail",
            "grep",
            "find",
            "python",
            "pytest",
            "ruff",
            "black",
            "isort",
            "mypy"
        ]

        if security_level == SecurityLevel.MEDIUM:
            base_allowed.extend([
                "git add",
                "git commit",
                "git checkout",
                "mkdir",
                "cp",
                "mv"
            ])

        return base_allowed

    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches glob-like pattern."""
        import fnmatch
        return fnmatch.fnmatch(path, pattern)

    def _access_mode_compatible(self, required: AccessMode, requested: AccessMode) -> bool:
        """Check if requested access mode is compatible with required mode."""

        if required == AccessMode.READ_ONLY:
            return requested in [AccessMode.READ_ONLY]
        elif required == AccessMode.WRITE_ONLY:
            return requested in [AccessMode.WRITE_ONLY]
        elif required == AccessMode.READ_WRITE:
            return requested in [AccessMode.READ_ONLY, AccessMode.WRITE_ONLY, AccessMode.READ_WRITE]
        elif required == AccessMode.EXECUTE:
            return requested == AccessMode.EXECUTE
        elif required == AccessMode.NONE:
            return False

        return True

    def _log_violation(self, violation: SecurityViolation) -> None:
        """Log security violation to file."""

        try:
            with open(self.violation_log, 'a') as f:
                violation_dict = {
                    'violation_type': violation.violation_type,
                    'description': violation.description,
                    'workflow_id': violation.workflow_id,
                    'severity': violation.severity,
                    'timestamp': violation.timestamp,
                    'context': violation.context
                }
                f.write(json.dumps(violation_dict) + '\n')
        except Exception:
            pass  # Best effort logging


# Export main classes
__all__ = [
    'SecurityLevel',
    'AccessMode',
    'SecurityContext',
    'SecurityViolation',
    'IsolationEnvironment',
    'SecurityManager'
]