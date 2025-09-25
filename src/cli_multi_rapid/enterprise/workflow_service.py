"""
Enterprise Workflow Service for CLI Orchestrator.

Demonstrates how to use BaseEnterpriseService to create an HTTP API
around the CLI Orchestrator's workflow execution capabilities.
"""

import json
from pathlib import Path
from typing import Optional

try:
    from fastapi import HTTPException
    from pydantic import BaseModel

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    BaseModel = object

from ..workflow_runner import WorkflowRunner
from .base_service import BaseEnterpriseService, ServiceMetadata
from .config import ServiceConfig

if FASTAPI_AVAILABLE:

    class WorkflowRequest(BaseModel):
        """Request model for workflow execution."""

        workflow_file: str
        dry_run: bool = False
        files: Optional[str] = None
        lane: Optional[str] = None
        max_tokens: Optional[int] = None

    class WorkflowResponse(BaseModel):
        """Response model for workflow execution."""

        success: bool
        error: Optional[str] = None
        artifacts: list[str] = []
        tokens_used: int = 0
        steps_completed: int = 0
        execution_time_seconds: Optional[float] = None


class EnterpriseWorkflowService(BaseEnterpriseService):
    """
    Enterprise wrapper for CLI Orchestrator workflow execution.

    Provides HTTP API, metrics, health checks, and enterprise features
    around the core workflow execution functionality.
    """

    def __init__(self):
        metadata = ServiceMetadata(
            name="cli-orchestrator-workflow-service",
            version="1.0.0",
            description="Enterprise HTTP API for CLI Orchestrator workflows",
            dependencies=["workflow-schemas", "artifacts-storage"],
            health_check_interval=30,
            metrics_enabled=True,
            api_enabled=True,
        )

        config = ServiceConfig.from_env()
        super().__init__(metadata, config)

        # Initialize workflow runner
        self.workflow_runner = WorkflowRunner()

        # Add custom health checks
        self._setup_health_checks()

    async def service_logic(self) -> None:
        """Initialize service-specific components."""
        self.logger.info("Initializing CLI Orchestrator workflow service")

        # Setup workflow-specific routes
        if self.app:
            self._setup_workflow_routes()

        # Verify workflow schemas are available
        schema_dir = Path(self.config.workflow_schema_dir)
        if not schema_dir.exists():
            self.logger.warning(f"Schema directory not found: {schema_dir}")

        # Ensure artifacts directory exists
        artifacts_dir = Path(self.config.artifacts_dir)
        artifacts_dir.mkdir(exist_ok=True)

        self.logger.info("Workflow service initialization complete")

    async def cleanup(self) -> None:
        """Cleanup workflow service resources."""
        self.logger.info("Cleaning up workflow service")
        # Cleanup any async resources here if needed

    def _setup_health_checks(self) -> None:
        """Setup workflow-specific health checks."""

        def check_workflow_schemas() -> bool:
            """Check if workflow schemas are available and valid."""
            try:
                schema_dir = Path(self.config.workflow_schema_dir)
                if not schema_dir.exists():
                    return False

                # Check for required schema files
                required_schemas = ["workflow.schema.json"]
                for schema_file in required_schemas:
                    if not (schema_dir / schema_file).exists():
                        return False

                return True
            except Exception:
                return False

        def check_artifacts_directory() -> bool:
            """Check if artifacts directory is writable."""
            try:
                artifacts_dir = Path(self.config.artifacts_dir)
                artifacts_dir.mkdir(exist_ok=True)

                # Try to create a test file
                test_file = artifacts_dir / ".health_check"
                test_file.write_text("ok")
                test_file.unlink()
                return True
            except Exception:
                return False

        self.add_custom_health_check(
            "workflow_schemas",
            check_workflow_schemas,
            "Verify workflow schemas are available",
        )

        self.add_custom_health_check(
            "artifacts_directory",
            check_artifacts_directory,
            "Verify artifacts directory is writable",
        )

    def _setup_workflow_routes(self) -> None:
        """Setup workflow execution HTTP endpoints."""
        if not FASTAPI_AVAILABLE or not self.app:
            return

        @self.app.post("/api/v1/workflows/execute", response_model=WorkflowResponse)
        async def execute_workflow(request: WorkflowRequest):
            """Execute a workflow with enterprise monitoring."""
            import time

            start_time = time.time()

            try:
                # Validate workflow file exists
                workflow_path = Path(request.workflow_file)
                if not workflow_path.exists():
                    if self.metrics:
                        self.metrics.inc_counter(
                            "workflow_errors_total", 1, {"type": "file_not_found"}
                        )
                    raise HTTPException(
                        status_code=404,
                        detail=f"Workflow file not found: {request.workflow_file}",
                    )

                # Execute workflow
                result = self.workflow_runner.run(
                    workflow_file=workflow_path,
                    dry_run=request.dry_run,
                    files=request.files,
                    lane=request.lane,
                    max_tokens=request.max_tokens,
                )

                # Record metrics
                execution_time = time.time() - start_time
                if self.metrics:
                    self.metrics.workflow_metrics(
                        workflow_name=workflow_path.stem,
                        success=result.success,
                        duration=execution_time,
                        tokens_used=result.tokens_used,
                        steps_completed=result.steps_completed,
                    )

                return WorkflowResponse(
                    success=result.success,
                    error=result.error,
                    artifacts=result.artifacts,
                    tokens_used=result.tokens_used,
                    steps_completed=result.steps_completed,
                    execution_time_seconds=execution_time,
                )

            except HTTPException:
                raise
            except Exception as e:
                execution_time = time.time() - start_time
                error_msg = f"Workflow execution failed: {str(e)}"

                self.logger.error(error_msg, exc_info=True)

                if self.metrics:
                    self.metrics.inc_counter(
                        "workflow_errors_total", 1, {"type": "execution_error"}
                    )
                    self.metrics.histogram(
                        "workflow_duration_seconds", execution_time, {"status": "error"}
                    )

                raise HTTPException(status_code=500, detail=error_msg)

        @self.app.get("/api/v1/workflows/schemas")
        async def list_workflow_schemas():
            """List available workflow schemas."""
            try:
                schema_dir = Path(self.config.workflow_schema_dir)
                if not schema_dir.exists():
                    return {"schemas": []}

                schemas = []
                for schema_file in schema_dir.glob("*.schema.json"):
                    try:
                        with open(schema_file) as f:
                            schema_data = json.load(f)
                        schemas.append(
                            {
                                "name": schema_file.name,
                                "title": schema_data.get("title", schema_file.stem),
                                "description": schema_data.get("description", ""),
                                "version": schema_data.get("version", "unknown"),
                            }
                        )
                    except Exception as e:
                        self.logger.warning(f"Failed to read schema {schema_file}: {e}")

                return {"schemas": schemas}

            except Exception as e:
                self.logger.error(f"Failed to list schemas: {e}")
                raise HTTPException(status_code=500, detail="Failed to list schemas")

        @self.app.get("/api/v1/workflows/artifacts")
        async def list_artifacts():
            """List available workflow artifacts."""
            try:
                artifacts_dir = Path(self.config.artifacts_dir)
                if not artifacts_dir.exists():
                    return {"artifacts": []}

                artifacts = []
                for artifact_file in artifacts_dir.glob("**/*"):
                    if artifact_file.is_file():
                        artifacts.append(
                            {
                                "name": artifact_file.name,
                                "path": str(artifact_file.relative_to(artifacts_dir)),
                                "size": artifact_file.stat().st_size,
                                "modified": artifact_file.stat().st_mtime,
                            }
                        )

                return {"artifacts": artifacts}

            except Exception as e:
                self.logger.error(f"Failed to list artifacts: {e}")
                raise HTTPException(status_code=500, detail="Failed to list artifacts")

        @self.app.get("/api/v1/metrics/summary")
        async def get_metrics_summary():
            """Get workflow execution metrics summary."""
            if not self.metrics:
                raise HTTPException(status_code=404, detail="Metrics not enabled")

            return self.metrics.get_metrics_summary()


def main():
    """Main entry point for the enterprise workflow service."""
    service = EnterpriseWorkflowService()
    service.run()


if __name__ == "__main__":
    main()
