"""
CLI Orchestrator Enterprise Services Package

Provides enterprise-grade capabilities for the CLI Orchestrator including:
- Base service patterns with health checks and metrics
- Security framework integration
- Audit logging and monitoring
- Service discovery and configuration management
"""

__version__ = "1.0.0"

from .base_service import BaseEnterpriseService, ServiceMetadata
from .config import ServiceConfig
from .health_checks import HealthCheckManager
from .metrics import MetricsCollector

__all__ = [
    "BaseEnterpriseService",
    "ServiceMetadata",
    "ServiceConfig",
    "HealthCheckManager",
    "MetricsCollector",
]
