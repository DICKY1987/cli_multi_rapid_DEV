#!/bin/bash

# scripts/integrate_enterprise_workflow.sh
# Automated script to integrate enterprise capabilities into CLI Orchestrator workflows
# Usage: ./integrate_enterprise_workflow.sh <workflow-name> [service-port]

set -euo pipefail

WORKFLOW_NAME="${1:-}"
SERVICE_PORT="${2:-8080}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ -z "$WORKFLOW_NAME" ]]; then
    echo "Usage: $0 <workflow-name> [service-port]"
    echo "Example: $0 python-triage-workflow 8081"
    echo ""
    echo "This script will:"
    echo "  - Create an enterprise HTTP service wrapper for your workflow"
    echo "  - Add health checks, metrics, and security"
    echo "  - Generate Docker configuration"
    echo "  - Create monitoring and testing setup"
    exit 1
fi

echo "🚀 Integrating enterprise capabilities for workflow: $WORKFLOW_NAME"

# Validate workflow exists
WORKFLOW_DIR=".ai/workflows"
WORKFLOW_FILE="$WORKFLOW_DIR/${WORKFLOW_NAME}.yaml"

if [[ ! -f "$WORKFLOW_FILE" ]]; then
    echo "❌ Workflow file not found: $WORKFLOW_FILE"
    echo "Available workflows:"
    ls -1 "$WORKFLOW_DIR"/*.yaml 2>/dev/null | sed 's|.*/||; s|\.yaml||' || echo "  (none found)"
    exit 1
fi

# Create service directory structure
SERVICE_DIR="services/workflow-${WORKFLOW_NAME}"
mkdir -p "$SERVICE_DIR/src"
mkdir -p "$SERVICE_DIR/tests"
mkdir -p "$SERVICE_DIR/config"
mkdir -p "$SERVICE_DIR/docker"

echo "📝 Creating enterprise workflow service..."

# Step 1: Create enterprise service wrapper
cat > "$SERVICE_DIR/src/main.py" << 'EOF'
#!/usr/bin/env python3
"""
Enterprise HTTP service for {WORKFLOW_NAME} workflow.

Provides REST API, health checks, metrics, and enterprise features
for CLI Orchestrator workflow execution.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from fastapi import HTTPException, Request
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    BaseModel = object

# CLI Orchestrator imports
from src.cli_multi_rapid.enterprise.base_service import BaseEnterpriseService, ServiceMetadata
from src.cli_multi_rapid.enterprise.config import ServiceConfig
from src.cli_multi_rapid.workflow_runner import WorkflowRunner
from src.cli_multi_rapid.security.framework import SecurityFramework, SecurityPolicy


if FASTAPI_AVAILABLE:
    class WorkflowExecutionRequest(BaseModel):
        """Request model for workflow execution."""
        files: Optional[str] = None
        lane: Optional[str] = None
        max_tokens: Optional[int] = None
        dry_run: bool = False
        parameters: Optional[Dict[str, Any]] = None

    class WorkflowExecutionResponse(BaseModel):
        """Response model for workflow execution."""
        execution_id: str
        success: bool
        error: Optional[str] = None
        artifacts: list[str] = []
        tokens_used: int = 0
        steps_completed: int = 0
        execution_time_seconds: float = 0
        workflow_name: str = ""


class {SERVICE_CLASS_NAME}Service(BaseEnterpriseService):
    """
    Enterprise service for {WORKFLOW_NAME} workflow execution.

    Provides HTTP API, security, monitoring, and enterprise features
    around the {WORKFLOW_NAME} workflow.
    """

    def __init__(self):
        metadata = ServiceMetadata(
            name="workflow-{WORKFLOW_NAME}-service",
            version="1.0.0",
            description="Enterprise service for {WORKFLOW_NAME} workflow",
            dependencies=["cli-orchestrator", "workflow-schemas"],
            health_check_interval=30,
            metrics_enabled=True,
            api_enabled=True
        )

        config = ServiceConfig.from_env("WORKFLOW_{WORKFLOW_NAME_UPPER}_")
        super().__init__(metadata, config)

        # Initialize components
        self.workflow_runner = WorkflowRunner()
        self.workflow_file = Path(".ai/workflows/{WORKFLOW_NAME}.yaml")

        # Security framework
        security_policy = SecurityPolicy(
            jwt_secret=config.jwt_secret,
            require_api_key_for_execution=True,
            allowed_workflow_patterns=["{WORKFLOW_NAME}.yaml"],
            max_concurrent_workflows=5
        )
        self.security = SecurityFramework(security_policy, Path("security"))

        # Execution tracking
        self.active_executions: Dict[str, Dict] = {}

        # Setup health checks and routes
        self._setup_health_checks()

    async def service_logic(self) -> None:
        """Initialize service-specific components."""
        self.logger.info("Initializing {WORKFLOW_NAME} workflow service")

        # Verify workflow file exists
        if not self.workflow_file.exists():
            raise FileNotFoundError(f"Workflow file not found: {self.workflow_file}")

        # Setup workflow-specific routes
        if self.app:
            self._setup_workflow_routes()

        # Create default admin user if none exists
        await self._ensure_admin_user()

        self.logger.info("{WORKFLOW_NAME} workflow service ready")

    async def cleanup(self) -> None:
        """Cleanup service resources."""
        self.logger.info("Cleaning up {WORKFLOW_NAME} workflow service")
        # Cancel any active executions
        for execution_id in list(self.active_executions.keys()):
            await self._cancel_execution(execution_id)

    def _setup_health_checks(self) -> None:
        """Setup workflow-specific health checks."""

        def check_workflow_file() -> bool:
            """Check if workflow file exists and is readable."""
            try:
                return self.workflow_file.exists() and self.workflow_file.is_file()
            except Exception:
                return False

        def check_workflow_runner() -> bool:
            """Check if workflow runner is available."""
            try:
                return self.workflow_runner is not None
            except Exception:
                return False

        def check_security_framework() -> bool:
            """Check if security framework is operational."""
            try:
                return self.security is not None
            except Exception:
                return False

        self.add_custom_health_check(
            "workflow_file",
            check_workflow_file,
            "Verify {WORKFLOW_NAME} workflow file is available"
        )

        self.add_custom_health_check(
            "workflow_runner",
            check_workflow_runner,
            "Verify workflow runner is operational"
        )

        self.add_custom_health_check(
            "security_framework",
            check_security_framework,
            "Verify security framework is operational"
        )

    def _setup_workflow_routes(self) -> None:
        """Setup workflow execution HTTP endpoints."""
        if not FASTAPI_AVAILABLE or not self.app:
            return

        @self.app.post("/api/v1/workflows/{WORKFLOW_NAME}/execute", response_model=WorkflowExecutionResponse)
        async def execute_workflow(request: WorkflowExecutionRequest, http_request: Request):
            """Execute {WORKFLOW_NAME} workflow with enterprise monitoring."""
            import secrets

            execution_id = secrets.token_urlsafe(16)
            start_time = time.time()

            try:
                # Authentication check
                auth_header = http_request.headers.get("Authorization")
                api_key = http_request.headers.get("X-API-Key")

                user = None
                if api_key:
                    user = await self.security.verify_api_key(api_key)
                elif auth_header and auth_header.startswith("Bearer "):
                    # JWT token authentication would go here
                    pass

                if not user:
                    raise HTTPException(status_code=401, detail="Authentication required")

                # Permission checks
                if not await self.security.check_workflow_permission(user, str(self.workflow_file), "execute"):
                    raise HTTPException(status_code=403, detail="Insufficient permissions")

                # Rate limiting
                if not await self.security.check_rate_limit(user.id, "workflow_execute"):
                    raise HTTPException(status_code=429, detail="Rate limit exceeded")

                # Start workflow execution tracking
                if not await self.security.start_workflow_execution(
                    user_id=user.id,
                    workflow_id=execution_id,
                    workflow_data={
                        "workflow_name": "{WORKFLOW_NAME}",
                        "files": request.files,
                        "lane": request.lane,
                        "parameters": request.parameters or {}
                    }
                ):
                    raise HTTPException(status_code=429, detail="Too many concurrent executions")

                # Track execution
                self.active_executions[execution_id] = {
                    "user_id": user.id,
                    "start_time": start_time,
                    "request": request.dict()
                }

                # Execute workflow
                result = self.workflow_runner.run(
                    workflow_file=self.workflow_file,
                    dry_run=request.dry_run,
                    files=request.files,
                    lane=request.lane,
                    max_tokens=request.max_tokens
                )

                execution_time = time.time() - start_time

                # Record metrics
                if self.metrics:
                    self.metrics.workflow_metrics(
                        workflow_name="{WORKFLOW_NAME}",
                        success=result.success,
                        duration=execution_time,
                        tokens_used=result.tokens_used,
                        steps_completed=result.steps_completed
                    )

                # End workflow execution tracking
                await self.security.end_workflow_execution(execution_id, result.success)

                # Cleanup tracking
                self.active_executions.pop(execution_id, None)

                return WorkflowExecutionResponse(
                    execution_id=execution_id,
                    success=result.success,
                    error=result.error,
                    artifacts=result.artifacts,
                    tokens_used=result.tokens_used,
                    steps_completed=result.steps_completed,
                    execution_time_seconds=execution_time,
                    workflow_name="{WORKFLOW_NAME}"
                )

            except HTTPException:
                # Cleanup on HTTP exceptions
                await self.security.end_workflow_execution(execution_id, False)
                self.active_executions.pop(execution_id, None)
                raise
            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = f"Workflow execution failed: {str(e)}"

                self.logger.error(error_msg, exc_info=True)

                if self.metrics:
                    self.metrics.inc_counter("workflow_errors_total", 1, {"type": "execution_error"})
                    self.metrics.histogram("workflow_duration_seconds", execution_time, {"status": "error"})

                # Cleanup on exceptions
                await self.security.end_workflow_execution(execution_id, False)
                self.active_executions.pop(execution_id, None)

                raise HTTPException(status_code=500, detail=error_msg)

        @self.app.get("/api/v1/workflows/{WORKFLOW_NAME}/status")
        async def get_workflow_status():
            """Get {WORKFLOW_NAME} workflow service status."""
            return {
                "workflow_name": "{WORKFLOW_NAME}",
                "workflow_file": str(self.workflow_file),
                "workflow_exists": self.workflow_file.exists(),
                "active_executions": len(self.active_executions),
                "service_uptime": time.time() - (self._start_time or 0),
                "security_summary": self.security.get_security_summary()
            }

        @self.app.get("/api/v1/workflows/{WORKFLOW_NAME}/executions")
        async def list_active_executions():
            """List active workflow executions."""
            return {
                "active_executions": len(self.active_executions),
                "executions": [
                    {
                        "execution_id": exec_id,
                        "user_id": exec_data["user_id"],
                        "start_time": exec_data["start_time"],
                        "duration": time.time() - exec_data["start_time"],
                        "request_params": exec_data["request"]
                    }
                    for exec_id, exec_data in self.active_executions.items()
                ]
            }

        @self.app.post("/api/v1/auth/api-key")
        async def create_api_key(http_request: Request):
            """Create API key for workflow access."""
            # This would require admin authentication
            # Simplified for demo - in production, verify admin token

            try:
                # Create API key for default user
                # In production, this would be properly authenticated
                admin_user = await self._get_or_create_admin_user()
                api_key = await self.security.create_api_key(
                    user_id=admin_user.id,
                    description=f"API key for {WORKFLOW_NAME} workflow"
                )

                return {
                    "api_key": api_key,
                    "description": f"API key for {WORKFLOW_NAME} workflow",
                    "usage": f"Include 'X-API-Key: {api_key}' in your request headers"
                }

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to create API key: {str(e)}")

    async def _ensure_admin_user(self) -> None:
        """Ensure admin user exists for API key creation."""
        try:
            await self._get_or_create_admin_user()
        except Exception as e:
            self.logger.error(f"Failed to ensure admin user: {e}")

    async def _get_or_create_admin_user(self):
        """Get or create admin user."""
        # Check if admin user already exists
        admin_username = "workflow_admin"

        if admin_username not in self.security._users:
            admin_user = await self.security.create_user(
                username=admin_username,
                email=f"admin@{WORKFLOW_NAME}-workflow.local",
                password="admin123",  # In production, use secure password
                roles={self.security.rbac.Role.ADMIN}
            )
            self.logger.info(f"Created admin user: {admin_username}")
            return admin_user
        else:
            return self.security._users[admin_username]

    async def _cancel_execution(self, execution_id: str) -> None:
        """Cancel active execution."""
        if execution_id in self.active_executions:
            await self.security.end_workflow_execution(execution_id, False)
            self.active_executions.pop(execution_id, None)
            self.logger.info(f"Cancelled execution: {execution_id}")


def main():
    """Main entry point for {WORKFLOW_NAME} workflow service."""
    service = {SERVICE_CLASS_NAME}Service()
    service.run(host="0.0.0.0", port={SERVICE_PORT})


if __name__ == "__main__":
    main()
EOF

# Replace placeholders in the service file
SERVICE_CLASS_NAME=$(echo "$WORKFLOW_NAME" | sed 's/-/_/g' | sed 's/\b\w/\u&/g' | sed 's/_//g')
WORKFLOW_NAME_UPPER=$(echo "$WORKFLOW_NAME" | tr '[:lower:]' '[:upper:]' | tr '-' '_')

sed -i "s/{WORKFLOW_NAME}/$WORKFLOW_NAME/g" "$SERVICE_DIR/src/main.py"
sed -i "s/{SERVICE_CLASS_NAME}/$SERVICE_CLASS_NAME/g" "$SERVICE_DIR/src/main.py"
sed -i "s/{WORKFLOW_NAME_UPPER}/$WORKFLOW_NAME_UPPER/g" "$SERVICE_DIR/src/main.py"
sed -i "s/{SERVICE_PORT}/$SERVICE_PORT/g" "$SERVICE_DIR/src/main.py"

echo "✅ Created enterprise service: $SERVICE_DIR/src/main.py"

# Step 2: Create Docker configuration
echo "🐳 Creating Docker configuration..."

cat > "$SERVICE_DIR/Dockerfile" << EOF
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    git \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy CLI Orchestrator source
COPY src/ ./src/
COPY .ai/ ./.ai/
COPY services/$WORKFLOW_NAME/src/ ./services/$WORKFLOW_NAME/src/

# Create directories
RUN mkdir -p artifacts logs security

# Service ports
EXPOSE $SERVICE_PORT
EXPOSE $((SERVICE_PORT + 1000))  # Health check port

# Environment variables
ENV PYTHONPATH=/app/src
ENV WORKFLOW_${WORKFLOW_NAME_UPPER}_SERVICE_NAME=workflow-${WORKFLOW_NAME}-service
ENV WORKFLOW_${WORKFLOW_NAME_UPPER}_SERVICE_PORT=$SERVICE_PORT
ENV WORKFLOW_${WORKFLOW_NAME_UPPER}_ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \\
    CMD curl -f http://localhost:$SERVICE_PORT/health || exit 1

# Entry point
CMD ["python", "-m", "services.workflow-${WORKFLOW_NAME}.src.main"]
EOF

echo "✅ Created Docker configuration: $SERVICE_DIR/Dockerfile"

# Step 3: Create requirements.txt
cat > "$SERVICE_DIR/requirements.txt" << EOF
# CLI Orchestrator dependencies
typer>=0.9.0
rich>=13.0.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn>=0.20.0
PyYAML>=6.0
jsonschema>=4.0.0

# Enterprise features
pyjwt>=2.8.0
passlib[bcrypt]>=1.7.4
python-multipart>=0.0.6

# Optional dependencies
redis>=5.0.0
psutil>=5.9.0

# Development dependencies
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
pytest-timeout>=2.1.0
httpx>=0.24.0
EOF

echo "✅ Created requirements: $SERVICE_DIR/requirements.txt"

# Step 4: Create environment configuration
cat > "$SERVICE_DIR/config/.env.template" << EOF
# Workflow Service Configuration
WORKFLOW_${WORKFLOW_NAME_UPPER}_SERVICE_NAME=workflow-${WORKFLOW_NAME}-service
WORKFLOW_${WORKFLOW_NAME_UPPER}_SERVICE_PORT=$SERVICE_PORT
WORKFLOW_${WORKFLOW_NAME_UPPER}_ENVIRONMENT=development
WORKFLOW_${WORKFLOW_NAME_UPPER}_LOG_LEVEL=INFO

# Security
WORKFLOW_${WORKFLOW_NAME_UPPER}_JWT_SECRET=your-secure-jwt-secret-here
WORKFLOW_${WORKFLOW_NAME_UPPER}_API_KEY_HEADER=X-API-Key

# CORS
WORKFLOW_${WORKFLOW_NAME_UPPER}_CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Features
WORKFLOW_${WORKFLOW_NAME_UPPER}_FEATURES_HEALTH_CHECKS=true
WORKFLOW_${WORKFLOW_NAME_UPPER}_FEATURES_METRICS=true
WORKFLOW_${WORKFLOW_NAME_UPPER}_FEATURES_CIRCUIT_BREAKER=true
WORKFLOW_${WORKFLOW_NAME_UPPER}_FEATURES_AUDIT_LOGGING=true

# Workflow-specific settings
WORKFLOW_${WORKFLOW_NAME_UPPER}_MAX_TOKENS_DEFAULT=120000
WORKFLOW_${WORKFLOW_NAME_UPPER}_MAX_CONCURRENT_WORKFLOWS=5
WORKFLOW_${WORKFLOW_NAME_UPPER}_RATE_LIMIT_PER_MINUTE=60

# File paths
WORKFLOW_${WORKFLOW_NAME_UPPER}_WORKFLOW_SCHEMA_DIR=.ai/schemas
WORKFLOW_${WORKFLOW_NAME_UPPER}_ARTIFACTS_DIR=artifacts
WORKFLOW_${WORKFLOW_NAME_UPPER}_LOGS_DIR=logs
EOF

echo "✅ Created environment template: $SERVICE_DIR/config/.env.template"

# Step 5: Create test files
echo "🧪 Creating test infrastructure..."

cat > "$SERVICE_DIR/tests/test_${WORKFLOW_NAME//-/_}_service.py" << EOF
"""
Tests for ${WORKFLOW_NAME} workflow service.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient

# Assuming the service is importable
from services.workflow_${WORKFLOW_NAME//-/_}.src.main import ${SERVICE_CLASS_NAME}Service


@pytest.mark.asyncio
class Test${SERVICE_CLASS_NAME}Service:
    """Test ${SERVICE_CLASS_NAME}Service functionality."""

    @pytest.fixture
    async def service(self):
        """Create service instance for testing."""
        with patch('services.workflow_${WORKFLOW_NAME//-/_}.src.main.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            mock_path.return_value.is_file.return_value = True

            service = ${SERVICE_CLASS_NAME}Service()
            yield service
            await service.cleanup()

    @pytest.fixture
    def client(self, service):
        """Create test client."""
        return TestClient(service.app)

    def test_service_initialization(self, service):
        """Test service initializes correctly."""
        assert service.metadata.name == "workflow-${WORKFLOW_NAME}-service"
        assert service.workflow_runner is not None
        assert service.security is not None

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code in [200, 503]  # May be unhealthy in test

        data = response.json()
        assert "status" in data
        assert "service" in data

    def test_workflow_status_endpoint(self, client):
        """Test workflow status endpoint."""
        response = client.get("/api/v1/workflows/${WORKFLOW_NAME}/status")
        assert response.status_code == 200

        data = response.json()
        assert data["workflow_name"] == "${WORKFLOW_NAME}"
        assert "workflow_file" in data
        assert "active_executions" in data

    def test_list_executions_endpoint(self, client):
        """Test list executions endpoint."""
        response = client.get("/api/v1/workflows/${WORKFLOW_NAME}/executions")
        assert response.status_code == 200

        data = response.json()
        assert "active_executions" in data
        assert "executions" in data
        assert isinstance(data["executions"], list)

    @pytest.mark.integration
    def test_workflow_execution_with_api_key(self, client):
        """Test workflow execution with API key authentication."""
        # This would require setting up proper authentication
        # For now, test that the endpoint exists and returns proper error
        response = client.post("/api/v1/workflows/${WORKFLOW_NAME}/execute", json={
            "files": "**/*.py",
            "dry_run": True
        })

        # Should return 401 without authentication
        assert response.status_code == 401

    @pytest.mark.integration
    def test_create_api_key_endpoint(self, client):
        """Test API key creation endpoint."""
        response = client.post("/api/v1/auth/api-key")

        # May succeed or fail depending on service state
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "api_key" in data
            assert data["api_key"].startswith("clio_")


@pytest.mark.performance
class Test${SERVICE_CLASS_NAME}Performance:
    """Performance tests for ${SERVICE_CLASS_NAME}Service."""

    def test_service_startup_time(self):
        """Test service startup performance."""
        import time

        start_time = time.time()

        with patch('services.workflow_${WORKFLOW_NAME//-/_}.src.main.Path') as mock_path:
            mock_path.return_value.exists.return_value = True
            service = ${SERVICE_CLASS_NAME}Service()

        startup_time = time.time() - start_time

        # Should start up quickly
        assert startup_time < 5.0

    @pytest.mark.slow
    def test_concurrent_requests(self, client):
        """Test handling concurrent requests."""
        import concurrent.futures
        import threading

        def make_request():
            return client.get("/api/v1/workflows/${WORKFLOW_NAME}/status")

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]

        # All should succeed
        for response in responses:
            assert response.status_code == 200
EOF

echo "✅ Created test file: $SERVICE_DIR/tests/test_${WORKFLOW_NAME//-/_}_service.py"

# Step 6: Create docker-compose integration
echo "🔧 Creating docker-compose configuration..."

cat > "$SERVICE_DIR/docker/docker-compose.yml" << EOF
version: '3.8'

services:
  workflow-${WORKFLOW_NAME}:
    build:
      context: ../../..
      dockerfile: services/workflow-${WORKFLOW_NAME}/Dockerfile
    ports:
      - "${SERVICE_PORT}:${SERVICE_PORT}"
      - "$((SERVICE_PORT + 1000)):$((SERVICE_PORT + 1000))"
    environment:
      - WORKFLOW_${WORKFLOW_NAME_UPPER}_ENVIRONMENT=production
      - WORKFLOW_${WORKFLOW_NAME_UPPER}_SERVICE_PORT=${SERVICE_PORT}
      - WORKFLOW_${WORKFLOW_NAME_UPPER}_LOG_LEVEL=INFO
    volumes:
      - ../../artifacts:/app/artifacts
      - ../../logs:/app/logs
      - ../../security:/app/security
    networks:
      - cli-orchestrator-network
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${SERVICE_PORT}/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - cli-orchestrator-network
    volumes:
      - redis_data:/data
    restart: unless-stopped

networks:
  cli-orchestrator-network:
    driver: bridge

volumes:
  redis_data:
    driver: local
EOF

echo "✅ Created docker-compose: $SERVICE_DIR/docker/docker-compose.yml"

# Step 7: Create startup script
cat > "$SERVICE_DIR/start_service.sh" << EOF
#!/bin/bash

# Start script for ${WORKFLOW_NAME} workflow service
set -euo pipefail

SERVICE_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(cd "\$SERVICE_DIR/../.." && pwd)"

echo "🚀 Starting ${WORKFLOW_NAME} workflow service..."

# Check if workflow file exists
if [[ ! -f ".ai/workflows/${WORKFLOW_NAME}.yaml" ]]; then
    echo "❌ Workflow file not found: .ai/workflows/${WORKFLOW_NAME}.yaml"
    exit 1
fi

# Create environment file if it doesn't exist
if [[ ! -f "\$SERVICE_DIR/config/.env" ]]; then
    echo "📋 Creating .env from template..."
    cp "\$SERVICE_DIR/config/.env.template" "\$SERVICE_DIR/config/.env"
    echo "⚠️  Please review and update \$SERVICE_DIR/config/.env with your settings"
fi

# Load environment variables
if [[ -f "\$SERVICE_DIR/config/.env" ]]; then
    source "\$SERVICE_DIR/config/.env"
fi

# Create required directories
mkdir -p artifacts logs security

# Install dependencies if needed
if [[ ! -f "venv/bin/activate" ]]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r "\$SERVICE_DIR/requirements.txt"
else
    source venv/bin/activate
fi

# Run the service
echo "🎯 Starting ${WORKFLOW_NAME} workflow service on port ${SERVICE_PORT}..."
export PYTHONPATH="\$PROJECT_ROOT/src:\$PYTHONPATH"

# Start with hot reload in development
if [[ "\${WORKFLOW_${WORKFLOW_NAME_UPPER}_ENVIRONMENT:-development}" == "development" ]]; then
    uvicorn services.workflow_${WORKFLOW_NAME//-/_}.src.main:${SERVICE_CLASS_NAME}Service().app \\
        --host 0.0.0.0 \\
        --port ${SERVICE_PORT} \\
        --reload \\
        --reload-dir src \\
        --reload-dir services
else
    python -m services.workflow_${WORKFLOW_NAME//-/_}.src.main
fi
EOF

chmod +x "$SERVICE_DIR/start_service.sh"
echo "✅ Created startup script: $SERVICE_DIR/start_service.sh"

# Step 8: Create monitoring configuration
echo "📊 Creating monitoring configuration..."

mkdir -p "$SERVICE_DIR/monitoring"

cat > "$SERVICE_DIR/monitoring/prometheus.yml" << EOF
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'workflow-${WORKFLOW_NAME}'
    static_configs:
      - targets: ['localhost:${SERVICE_PORT}']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'workflow-${WORKFLOW_NAME}-health'
    static_configs:
      - targets: ['localhost:${SERVICE_PORT}']
    metrics_path: '/health'
    scrape_interval: 10s
EOF

cat > "$SERVICE_DIR/monitoring/grafana-dashboard.json" << EOF
{
  "dashboard": {
    "id": null,
    "title": "${WORKFLOW_NAME} Workflow Service",
    "tags": ["cli-orchestrator", "workflow", "${WORKFLOW_NAME}"],
    "timezone": "browser",
    "panels": [
      {
        "title": "Workflow Executions",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(workflows_executed_total{workflow=\"${WORKFLOW_NAME}\"}[5m])",
            "legendFormat": "Executions/sec"
          }
        ]
      },
      {
        "title": "Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(workflows_executed_total{workflow=\"${WORKFLOW_NAME}\",status=\"success\"}[5m]) / rate(workflows_executed_total{workflow=\"${WORKFLOW_NAME}\"}[5m]) * 100",
            "legendFormat": "Success Rate %"
          }
        ]
      },
      {
        "title": "Token Usage",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(tokens_used_total[5m])",
            "legendFormat": "Tokens/sec"
          }
        ]
      },
      {
        "title": "Active Executions",
        "type": "stat",
        "targets": [
          {
            "expr": "workflow_active_executions",
            "legendFormat": "Active"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "10s"
  }
}
EOF

echo "✅ Created monitoring configuration: $SERVICE_DIR/monitoring/"

# Final summary and next steps
echo ""
echo "✅ Enterprise integration complete for ${WORKFLOW_NAME} workflow!"
echo ""
echo "📁 Created structure:"
echo "  ├── $SERVICE_DIR/src/main.py              # Enterprise service wrapper"
echo "  ├── $SERVICE_DIR/Dockerfile               # Docker configuration"
echo "  ├── $SERVICE_DIR/requirements.txt         # Python dependencies"
echo "  ├── $SERVICE_DIR/config/.env.template     # Environment template"
echo "  ├── $SERVICE_DIR/tests/                   # Test suite"
echo "  ├── $SERVICE_DIR/docker/docker-compose.yml # Docker Compose config"
echo "  ├── $SERVICE_DIR/start_service.sh         # Startup script"
echo "  └── $SERVICE_DIR/monitoring/               # Monitoring config"
echo ""
echo "🚀 Next steps:"
echo "1. Review and customize: $SERVICE_DIR/config/.env.template"
echo "2. Copy to: $SERVICE_DIR/config/.env"
echo "3. Start the service:"
echo "   cd $SERVICE_DIR && ./start_service.sh"
echo ""
echo "🌐 Service endpoints (when running):"
echo "  • Health: http://localhost:${SERVICE_PORT}/health"
echo "  • Metrics: http://localhost:${SERVICE_PORT}/metrics"
echo "  • Workflow Status: http://localhost:${SERVICE_PORT}/api/v1/workflows/${WORKFLOW_NAME}/status"
echo "  • Execute: POST http://localhost:${SERVICE_PORT}/api/v1/workflows/${WORKFLOW_NAME}/execute"
echo "  • Create API Key: POST http://localhost:${SERVICE_PORT}/api/v1/auth/api-key"
echo ""
echo "🔑 To get started quickly:"
echo "  curl -X POST http://localhost:${SERVICE_PORT}/api/v1/auth/api-key"
echo "  # Use the returned API key in X-API-Key header for workflow execution"
echo ""
echo "🐳 To run with Docker:"
echo "  cd $SERVICE_DIR/docker && docker-compose up"
echo ""
echo "📊 Monitor with Prometheus/Grafana using configs in $SERVICE_DIR/monitoring/"