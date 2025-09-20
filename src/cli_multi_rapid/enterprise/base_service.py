"""
Base Enterprise Service for CLI Orchestrator.

Provides enterprise-grade service foundation with:
- Automatic health checks and metrics
- Structured logging and error handling
- Configuration management
- Graceful startup and shutdown
- HTTP API with standard endpoints
"""

import asyncio
import logging
import signal
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, PlainTextResponse

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    FastAPI = None

from .config import ServiceConfig
from .health_checks import HealthCheckManager, HealthStatus
from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


@dataclass
class ServiceMetadata:
    """Service identification and configuration metadata."""

    name: str
    version: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    health_check_interval: int = 30
    metrics_enabled: bool = True
    api_enabled: bool = True


class BaseEnterpriseService(ABC):
    """
    Enterprise service foundation for CLI Orchestrator.

    Provides comprehensive enterprise capabilities with minimal configuration:
    - Health checks and readiness probes
    - Prometheus metrics collection
    - Structured logging
    - Configuration management
    - HTTP API (optional)
    - Graceful shutdown handling

    Usage: Inherit and implement service_logic()
    """

    def __init__(
        self, metadata: ServiceMetadata, config: Optional[ServiceConfig] = None
    ):
        self.metadata = metadata
        self.config = config or ServiceConfig.from_env()

        # Setup logging
        self._setup_logging()
        self.logger = logging.getLogger(f"service.{metadata.name}")

        # Core components
        self.health_manager = HealthCheckManager(metadata.name)

        if metadata.metrics_enabled:
            self.metrics = MetricsCollector(metadata.name)
        else:
            self.metrics = None

        # Service state
        self._is_ready = False
        self._is_healthy = True
        self._shutdown_event = asyncio.Event()
        self._start_time: Optional[float] = None

        # Optional FastAPI app
        if FASTAPI_AVAILABLE and metadata.api_enabled:
            self.app = FastAPI(
                title=metadata.name,
                description=metadata.description,
                version=metadata.version,
                lifespan=self.lifespan,
            )
            self._setup_middleware()
            self._setup_routes()
        else:
            self.app = None

        # Graceful shutdown handling
        self._setup_signal_handlers()

    def _setup_logging(self) -> None:
        """Setup structured logging configuration."""
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Reduce noise from third-party libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    def _setup_middleware(self) -> None:
        """Configure middleware for observability and security."""
        if not self.app:
            return

        # CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["*"],
        )

        # Request metrics middleware
        @self.app.middleware("http")
        async def metrics_middleware(request: Request, call_next):
            if not self.metrics:
                return await call_next(request)

            start_time = time.time()

            try:
                response = await call_next(request)
                duration = time.time() - start_time

                self.metrics.request_metrics(
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=response.status_code,
                    duration=duration,
                )

                return response

            except Exception:
                duration = time.time() - start_time
                self.metrics.request_metrics(
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=500,
                    duration=duration,
                )
                raise

    def _setup_routes(self) -> None:
        """Setup standard enterprise endpoints."""
        if not self.app:
            return

        @self.app.get("/health")
        async def health():
            """Health check endpoint."""
            try:
                health_result = await self.health_manager.get_overall_health()

                if health_result.status == HealthStatus.HEALTHY:
                    return JSONResponse(
                        content={
                            "status": health_result.status.value,
                            "service": self.metadata.name,
                            "version": self.metadata.version,
                            "checks": health_result.details.get("checks", {}),
                        },
                        status_code=200,
                    )
                else:
                    return JSONResponse(
                        content={
                            "status": health_result.status.value,
                            "service": self.metadata.name,
                            "message": health_result.message,
                            "checks": health_result.details.get("checks", {}),
                        },
                        status_code=503,
                    )
            except Exception as e:
                self.logger.error(f"Health check failed: {e}")
                return JSONResponse(
                    content={
                        "status": "unhealthy",
                        "service": self.metadata.name,
                        "message": f"Health check error: {str(e)}",
                    },
                    status_code=503,
                )

        @self.app.get("/ready")
        async def ready():
            """Readiness check endpoint."""
            if not self._is_ready:
                return JSONResponse(
                    content={
                        "status": "not_ready",
                        "service": self.metadata.name,
                        "message": "Service is not ready to accept requests",
                    },
                    status_code=503,
                )

            return JSONResponse(
                content={"status": "ready", "service": self.metadata.name}
            )

        @self.app.get("/metrics")
        async def metrics():
            """Prometheus metrics endpoint."""
            if not self.metrics:
                return JSONResponse(
                    content={"message": "Metrics not enabled"}, status_code=404
                )

            metrics_text = self.metrics.get_prometheus_metrics()
            return PlainTextResponse(content=metrics_text, media_type="text/plain")

        @self.app.get("/info")
        async def info():
            """Service information endpoint."""
            uptime = (time.time() - self._start_time) if self._start_time else 0

            return JSONResponse(
                content={
                    "name": self.metadata.name,
                    "version": self.metadata.version,
                    "description": self.metadata.description,
                    "dependencies": self.metadata.dependencies,
                    "uptime_seconds": uptime,
                    "ready": self._is_ready,
                    "healthy": self._is_healthy,
                    "environment": self.config.environment,
                    "features": self.config.features,
                }
            )

        @self.app.get("/config")
        async def get_config():
            """Get service configuration (sanitized)."""
            config_dict = self.config.to_dict()
            # Remove sensitive information
            config_dict.pop("jwt_secret", None)
            config_dict.pop("database_url", None)

            return JSONResponse(content=config_dict)

    def _setup_signal_handlers(self) -> None:
        """Setup graceful shutdown signal handlers."""

        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self._shutdown())

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    @abstractmethod
    async def service_logic(self) -> None:
        """
        Implement your service's core logic here.
        This method will be called during startup after all infrastructure is ready.
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup resources when service shuts down.
        Override to implement custom cleanup logic.
        """
        pass

    async def startup(self) -> None:
        """Service startup sequence."""
        self._start_time = time.time()
        self.logger.info(
            f"Starting service: {self.metadata.name} v{self.metadata.version}"
        )

        try:
            # Validate configuration
            config_errors = self.config.validate()
            if config_errors:
                raise ValueError(
                    f"Configuration validation failed: {', '.join(config_errors)}"
                )

            # Start health checks
            await self.health_manager.start()

            # Initialize metrics
            if self.metrics:
                self.metrics.gauge("service_started_timestamp", self._start_time)
                self.metrics.gauge(
                    "service_info",
                    1,
                    {
                        "version": self.metadata.version,
                        "environment": self.config.environment,
                    },
                )

            # Run service-specific logic
            await self.service_logic()

            # Mark as ready
            self._is_ready = True

            startup_duration = time.time() - self._start_time
            self.logger.info(f"Service started successfully in {startup_duration:.2f}s")

            if self.metrics:
                self.metrics.histogram("startup_duration_seconds", startup_duration)
                self.metrics.gauge("service_ready", 1)

        except Exception as e:
            self.logger.error(f"Service startup failed: {e}")
            self._is_healthy = False
            if self.metrics:
                self.metrics.inc_counter("startup_failures_total")
            raise

    async def _shutdown(self) -> None:
        """Internal shutdown method."""
        if self._shutdown_event.is_set():
            return

        self._shutdown_event.set()
        await self.shutdown()

    async def shutdown(self) -> None:
        """Graceful shutdown sequence."""
        self.logger.info("Shutting down service")

        try:
            # Mark as not ready (stop accepting new work)
            self._is_ready = False
            if self.metrics:
                self.metrics.gauge("service_ready", 0)

            # Run service cleanup
            await self.cleanup()

            # Stop health checks
            await self.health_manager.stop()

            # Log final metrics
            if self.metrics:
                uptime = (time.time() - self._start_time) if self._start_time else 0
                self.metrics.gauge("service_uptime_seconds", uptime)

                metrics_summary = self.metrics.get_metrics_summary()
                self.logger.info(f"Final metrics: {metrics_summary}")

            self.logger.info("Service shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """FastAPI lifespan manager."""
        await self.startup()
        try:
            yield
        finally:
            await self.shutdown()

    async def run_async(self) -> None:
        """Run service asynchronously without HTTP server."""
        await self.startup()

        try:
            # Wait for shutdown signal
            await self._shutdown_event.wait()
        finally:
            await self.shutdown()

    def run(self, host: str = "0.0.0.0", port: Optional[int] = None) -> None:
        """Run the service with HTTP server (if FastAPI available)."""
        if not FASTAPI_AVAILABLE or not self.app:
            self.logger.info("Running service without HTTP API (FastAPI not available)")
            asyncio.run(self.run_async())
            return

        import uvicorn

        port = port or self.config.port
        self.logger.info(f"Starting HTTP server on {host}:{port}")

        # Configure uvicorn to use our lifespan
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_config=None,  # Use our logging configuration
            access_log=False,  # We handle request logging in middleware
        )

    @property
    def is_ready(self) -> bool:
        """Check if service is ready to accept requests."""
        return self._is_ready

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._is_healthy

    def mark_unhealthy(self, reason: str = "") -> None:
        """Mark service as unhealthy."""
        self._is_healthy = False
        self.logger.warning(f"Service marked unhealthy: {reason}")
        if self.metrics:
            self.metrics.inc_counter(
                "service_unhealthy_total", labels={"reason": reason}
            )

    def add_custom_health_check(
        self, name: str, check_func, description: str = ""
    ) -> None:
        """Add a custom health check."""
        from .health_checks import HealthCheck

        health_check = HealthCheck(
            name=name, check_func=check_func, description=description
        )
        self.health_manager.add_check(health_check)
