# CLI Orchestrator - Docker Deployment Guide

This guide covers containerized deployment of the CLI Orchestrator system with multi-stage builds, development environments, and production configurations.

## 🚀 Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

### Development Setup

1. **Clone and setup environment:**
```bash
git clone https://github.com/DICKY1987/cli_multi_rapid_DEV.git
cd cli_multi_rapid_DEV
cp .env.template .env
# Edit .env with your API keys
```

2. **Start development environment:**
```bash
# Create required directories
mkdir -p artifacts logs cost

# Start services
docker-compose up -d
```

3. **Run CLI commands:**
```bash
# Run a workflow
docker-compose exec cli-orchestrator cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "src/**/*.py" --dry-run

# Check system status
docker-compose exec cli-orchestrator cli-orchestrator --help
```

## 🏗️ Architecture Overview

### Multi-Stage Dockerfile
- **Base Stage**: Python 3.11-slim with system dependencies
- **Development Stage**: Dev tools, hot reload, testing capabilities
- **Production Stage**: Minimal runtime, security hardened
- **Testing Stage**: Isolated test environment with coverage

### Services
- **cli-orchestrator**: Main application container
- **redis**: Caching and session state management
- **cli-orchestrator-prod**: Production-optimized container
- **cli-orchestrator-test**: Testing environment

## 📋 Available Commands

### Development Commands
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f cli-orchestrator

# Run specific workflow
docker-compose exec cli-orchestrator cli-orchestrator run .ai/workflows/CODE_QUALITY.yaml

# Enter development container
docker-compose exec cli-orchestrator bash

# Run tests
docker-compose --profile testing run --rm cli-orchestrator-test
```

### Production Commands
```bash
# Start production services
docker-compose --profile production up -d cli-orchestrator-prod redis

# Run production workflow
docker-compose --profile production exec cli-orchestrator-prod cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "src/**/*.py"

# Check production health
docker-compose --profile production exec cli-orchestrator-prod cli-orchestrator --help
```

### Build Commands
```bash
# Build specific stage
docker build --target development -t cli-orchestrator:dev .
docker build --target production -t cli-orchestrator:prod .
docker build --target testing -t cli-orchestrator:test .

# Multi-architecture build
docker buildx build --platform linux/amd64,linux/arm64 -t cli-orchestrator:latest --target production .
```

## 🔧 Configuration

### Environment Variables

Required variables in `.env`:
```bash
# AI Service API Keys
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# CLI Orchestrator Config
CLI_ORCHESTRATOR_ENV=development
MAX_TOKEN_BUDGET=500000
REDIS_URL=redis://redis:6379
```

### Volume Mounts
- **artifacts/**: Workflow execution outputs
- **logs/**: JSONL execution logs
- **cost/**: Token usage tracking
- **src/**: Source code (development only)
- **.ai/**: Workflow and schema definitions

### Port Mappings
- **8000**: CLI Orchestrator API (if enabled)
- **6379**: Redis (for external access)

## 🏭 Production Deployment

### Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml cli-orchestrator
```

### Kubernetes (with Helm)
```bash
# Add Helm chart (when available)
helm repo add cli-orchestrator https://charts.cli-orchestrator.com
helm install cli-orchestrator cli-orchestrator/cli-orchestrator
```

## 🧪 Development Workflow

### VS Code Dev Containers
1. Install "Dev Containers" extension
2. Open project in VS Code
3. Command Palette → "Dev Containers: Reopen in Container"
4. Development environment automatically configured

### Testing
```bash
# Run all tests
docker-compose --profile testing run --rm cli-orchestrator-test

# Run specific test
docker-compose --profile testing run --rm cli-orchestrator-test python -m pytest tests/test_specific.py -v

# Generate coverage report
docker-compose --profile testing run --rm cli-orchestrator-test python -m pytest tests/ --cov=src --cov-report=html:/app/artifacts/coverage
```

### Code Quality
```bash
# Run linting
docker-compose exec cli-orchestrator ruff check src/

# Format code
docker-compose exec cli-orchestrator black src/

# Type checking
docker-compose exec cli-orchestrator mypy src/
```

## 🔒 Security

### Production Hardening
- Non-root user (orchestrator:1000)
- Minimal attack surface
- Security scanned images
- Read-only filesystems where possible

### Secrets Management
```bash
# Using Docker secrets
echo "your_api_key" | docker secret create anthropic_api_key -

# Mount in compose
secrets:
  anthropic_api_key:
    external: true
```

## 📊 Monitoring & Logging

### Health Checks
All services include health checks:
```bash
# Check service health
docker-compose ps

# Manual health check
docker-compose exec cli-orchestrator cli-orchestrator --help
```

### Log Aggregation
```bash
# View aggregated logs
docker-compose logs -f

# Export logs
docker-compose logs --no-color > cli-orchestrator.log
```

## 🚨 Troubleshooting

### Common Issues

**Permission Errors:**
```bash
# Fix volume permissions
sudo chown -R 1000:1000 artifacts/ logs/ cost/
```

**Redis Connection Issues:**
```bash
# Test Redis connectivity
docker-compose exec cli-orchestrator redis-cli -h redis ping
```

**Build Failures:**
```bash
# Clear build cache
docker builder prune -a

# Rebuild without cache
docker-compose build --no-cache
```

### Debugging
```bash
# Debug container startup
docker-compose up --no-daemon

# Enter container for debugging
docker-compose exec cli-orchestrator bash

# Check container logs
docker-compose logs cli-orchestrator
```

## 📈 Performance Tuning

### Resource Limits
```yaml
# Add to docker-compose.yml services
deploy:
  resources:
    limits:
      cpus: "2"
      memory: 4G
    reservations:
      cpus: "0.5"
      memory: 1G
```

### Redis Configuration
```bash
# Optimize Redis for production
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

## 🔄 CI/CD Integration

The included `.github/workflows/docker-build.yml` provides:
- Multi-stage builds and testing
- Security scanning with Trivy
- Automated registry publishing
- Integration testing with docker-compose

### Manual Registry Push
```bash
# Tag and push
docker tag cli-orchestrator:prod ghcr.io/dicky1987/cli_multi_rapid_dev:latest
docker push ghcr.io/dicky1987/cli_multi_rapid_dev:latest
```

## 📚 Additional Resources

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Multi-stage Builds](https://docs.docker.com/develop/dev-best-practices/#use-multi-stage-builds)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Dev Containers Specification](https://containers.dev/)