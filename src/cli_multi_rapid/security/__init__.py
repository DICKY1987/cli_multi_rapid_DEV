"""
CLI Orchestrator Security Framework

Provides enterprise-grade security capabilities including:
- JWT-based authentication
- Role-based access control (RBAC)
- API key management
- Audit logging
- Rate limiting
- Secure workflow execution
"""

__version__ = "1.0.0"

from .audit import AuditLogger
from .auth import APIKeyManager, JWTManager
from .framework import Permission, Role, SecurityFramework, User
from .rbac import RoleBasedAccessControl

__all__ = [
    "SecurityFramework",
    "Permission",
    "Role",
    "User",
    "JWTManager",
    "APIKeyManager",
    "RoleBasedAccessControl",
    "AuditLogger",
]
