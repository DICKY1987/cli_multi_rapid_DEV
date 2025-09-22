"""
Configuration management for CLI Orchestrator enterprise services.

Provides typed configuration loading with validation,
environment variable support, and hierarchical merging.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ServiceConfig:
    """CLI Orchestrator service configuration."""

    # Service identification
    service_name: str = "cli-orchestrator"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Network settings
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])

    # Database (optional for CLI services)
    database_url: str = ""
    redis_url: str = ""

    # Security settings
    jwt_secret: str = "cli-orchestrator-dev-secret"
    jwt_expiry_hours: int = 24
    api_key_header: str = "X-API-Key"

    # Logging and monitoring
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True
    prometheus_port: int = 9090

    # Feature flags
    features: dict[str, bool] = field(
        default_factory=lambda: {
            "health_checks": True,
            "metrics": True,
            "circuit_breaker": True,
            "audit_logging": True,
            "rate_limiting": False,
        }
    )

    # CLI Orchestrator specific
    workflow_schema_dir: str = ".ai/schemas"
    artifacts_dir: str = "artifacts"
    logs_dir: str = "logs"
    max_tokens_default: int = 120000

    @classmethod
    def from_env(cls, prefix: str = "CLI_ORCHESTRATOR_") -> "ServiceConfig":
        """Create config from environment variables."""
        config_data = {}

        for key, value in os.environ.items():
            if key.startswith(prefix):
                config_key = key[len(prefix) :].lower()
                # Convert boolean strings
                if value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                # Convert numeric strings
                elif value.isdigit():
                    value = int(value)
                config_data[config_key] = value

        return cls(**config_data)

    @classmethod
    def from_file(cls, config_path: Path) -> "ServiceConfig":
        """Load configuration from JSON file."""
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            config_data = json.load(f)

        return cls(**config_data)

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        # Validate JWT secret in production
        if (
            self.environment == "production"
            and self.jwt_secret
            == "cli-orchestrator-dev-secret"  # pragma: allowlist secret
        ):
            errors.append("JWT secret must be changed in production")

        # Validate port ranges
        if not (1024 <= self.port <= 65535):
            errors.append(f"Port {self.port} must be between 1024 and 65535")

        if not (1024 <= self.prometheus_port <= 65535):
            errors.append(
                f"Prometheus port {self.prometheus_port} must be between 1024 and 65535"
            )

        # Validate directories
        schema_dir = Path(self.workflow_schema_dir)
        if not schema_dir.exists():
            errors.append(f"Schema directory not found: {schema_dir}")

        return errors

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            field.name: getattr(self, field.name)
            for field in self.__dataclass_fields__.values()
        }
