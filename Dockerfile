# Multi-stage Dockerfile for CLI Orchestrator
# Optimized for security, size, and development workflow

# ========================================
# Base Stage: System Dependencies
# ========================================
FROM python:3.11-slim as base

# Install system dependencies required for Python packages and tools
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 orchestrator \
    && useradd --uid 1000 --gid orchestrator --shell /bin/bash --create-home orchestrator

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# ========================================
# Development Stage: Dev Tools & Testing
# ========================================
FROM base as development

# Install additional development dependencies
RUN pip install --no-cache-dir \
    pytest \
    pytest-cov \
    pytest-asyncio \
    ruff \
    mypy \
    black \
    isort \
    bandit \
    pre-commit

# Copy source code
COPY --chown=orchestrator:orchestrator . .

# Install CLI orchestrator in development mode
RUN pip install -e .

# Switch to non-root user
USER orchestrator

# Create necessary directories for artifacts and logs
RUN mkdir -p artifacts logs cost .ai/workflows .ai/schemas

# Set environment variables for development
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV CLI_ORCHESTRATOR_ENV="development"

# Default command for development
CMD ["cli-orchestrator", "--help"]

# ========================================
# Production Stage: Minimal Runtime
# ========================================
FROM base as production

# Copy only necessary files
COPY --chown=orchestrator:orchestrator src/ ./src/
COPY --chown=orchestrator:orchestrator .ai/ ./.ai/
COPY --chown=orchestrator:orchestrator pyproject.toml ./

# Install CLI orchestrator
RUN pip install .

# Switch to non-root user
USER orchestrator

# Create necessary directories
RUN mkdir -p artifacts logs cost

# Set production environment variables
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV CLI_ORCHESTRATOR_ENV="production"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD cli-orchestrator --help > /dev/null || exit 1

# Expose ports (if needed for API mode)
EXPOSE 8000

# Default command
ENTRYPOINT ["cli-orchestrator"]
CMD ["--help"]

# ========================================
# Testing Stage: Isolated Test Environment
# ========================================
FROM development as testing

# Install test-specific dependencies
RUN pip install --no-cache-dir \
    coverage \
    hypothesis

# Copy test files
COPY --chown=orchestrator:orchestrator tests/ ./tests/

# Set testing environment
ENV CLI_ORCHESTRATOR_ENV="testing"

# Default test command
CMD ["python", "-m", "pytest", "tests/", "-v", "--cov=src"]