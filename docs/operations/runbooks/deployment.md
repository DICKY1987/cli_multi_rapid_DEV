# CLI Orchestrator Deployment Runbook

This runbook provides comprehensive deployment procedures for the CLI Orchestrator system and its enterprise components.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Development Deployment](#development-deployment)
3. [Production Deployment](#production-deployment)
4. [Rolling Updates](#rolling-updates)
5. [Rollback Procedures](#rollback-procedures)
6. [Monitoring and Verification](#monitoring-and-verification)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Linux (Ubuntu 20.04+), macOS, or Windows 10+
- **Python**: 3.11 or higher
- **Docker**: 20.10+ with Docker Compose v2
- **Git**: 2.30+ for workflow and schema management
- **Node.js**: 16+ (for optional web UI components)

### Infrastructure Requirements

| Component | Development | Production |
|-----------|-------------|------------|
| CPU | 2 cores | 4+ cores |
| RAM | 4GB | 8GB+ |
| Storage | 10GB | 50GB+ |
| Network | Local | Load balancer |

### Access Requirements

- [ ] Git repository access
- [ ] Docker registry access (if using private registry)
- [ ] Environment configuration files
- [ ] SSL certificates (production only)
- [ ] Monitoring system access

## Development Deployment

### Quick Start

1. **Clone Repository**

   ```bash
   git clone https://github.com/your-org/cli-orchestrator.git
   cd cli-orchestrator
   ```

2. **Setup Development Environment**

   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows

   # Install dependencies
   pip install -e .[dev]
   ```

3. **Initialize Configuration**

   ```bash
   # Create required directories
   mkdir -p artifacts logs security

   # Copy environment template
   cp .env.template .env

   # Edit configuration
   nano .env  # Update with your settings
   ```

4. **Verify Installation**

   ```bash
   # Run CLI help
   cli-orchestrator --help

   # Verify workflow schemas
   cli-orchestrator verify artifacts/example.json --schema .ai/schemas/workflow.schema.json

   # Check service health
   python -m src.cli_multi_rapid.enterprise.workflow_service &
   curl http://localhost:8080/health
   ```

### Development Services

**Start Basic CLI Orchestrator:**

```bash
# Terminal 1: Start the service
python -m src.cli_multi_rapid.enterprise.workflow_service

# Terminal 2: Test execution
cli-orchestrator run .ai/workflows/PY_EDIT_TRIAGE.yaml --files "**/*.py" --dry-run
```

**Start with Docker Compose (Recommended):**

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f cli-orchestrator

# Execute workflow
curl -X POST http://localhost:8080/api/v1/workflows/execute \
  -H "X-API-Key: $(curl -s -X POST http://localhost:8080/api/v1/auth/api-key | jq -r .api_key)" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/PY_EDIT_TRIAGE.yaml",
    "files": "**/*.py",
    "dry_run": true
  }'
```

## Production Deployment

### Pre-deployment Checklist

- [ ] All tests pass in CI/CD pipeline
- [ ] Security scan completed with no critical issues
- [ ] Performance benchmarks meet SLA requirements
- [ ] Database migration scripts prepared and tested
- [ ] Monitoring dashboards updated
- [ ] Rollback plan documented and tested
- [ ] Stakeholder notification sent
- [ ] Maintenance window scheduled

### Deployment Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load Balancer │────│  CLI Orchestrator│────│     Database    │
│   (nginx/ALB)   │    │     Services     │    │  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                       ┌────────┴────────┐
                       │                 │
                   ┌───▼───┐         ┌───▼───┐
                   │ Redis │         │ File  │
                   │ Cache │         │Storage│
                   └───────┘         └───────┘
```

### Step 1: Infrastructure Preparation

**1.1 Server Setup**

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application user
sudo useradd -m -s /bin/bash cli-orchestrator
sudo usermod -aG docker cli-orchestrator
```

**1.2 Directory Structure**

```bash
sudo mkdir -p /opt/cli-orchestrator/{config,logs,artifacts,security,backups}
sudo chown -R cli-orchestrator:cli-orchestrator /opt/cli-orchestrator
sudo chmod -R 755 /opt/cli-orchestrator
```

**1.3 SSL Certificate Setup**

```bash
# Using Let's Encrypt
sudo apt install certbot
sudo certbot certonly --standalone -d api.cli-orchestrator.yourcompany.com

# Or use your existing certificates
sudo cp your-cert.pem /opt/cli-orchestrator/config/ssl.crt
sudo cp your-key.pem /opt/cli-orchestrator/config/ssl.key
sudo chown cli-orchestrator:cli-orchestrator /opt/cli-orchestrator/config/ssl.*
```

### Step 2: Application Deployment

**2.1 Code Deployment**

```bash
# Switch to application user
sudo su - cli-orchestrator

# Clone application
cd /opt/cli-orchestrator
git clone https://github.com/your-org/cli-orchestrator.git app
cd app

# Checkout specific version
git checkout v1.0.0
```

**2.2 Configuration Setup**

```bash
# Copy production configuration
cp config/production/.env.template config/production/.env

# Edit configuration (use secure values!)
nano config/production/.env

# Example production configuration:
CLI_ORCHESTRATOR_ENVIRONMENT=production
CLI_ORCHESTRATOR_SERVICE_PORT=8080
CLI_ORCHESTRATOR_JWT_SECRET=your-secure-jwt-secret-here
CLI_ORCHESTRATOR_DATABASE_URL=postgresql://user:password@db-server:5432/cli_orchestrator
CLI_ORCHESTRATOR_REDIS_URL=redis://redis-server:6379
CLI_ORCHESTRATOR_LOG_LEVEL=INFO
```

**2.3 Database Setup**

```bash
# Run database migrations
docker run --rm \
  --env-file config/production/.env \
  --network host \
  cli-orchestrator:latest \
  alembic upgrade head

# Verify database
docker run --rm \
  --env-file config/production/.env \
  --network host \
  cli-orchestrator:latest \
  python -c "from src.cli_multi_rapid.enterprise.config import ServiceConfig; print('DB connection OK')"
```

### Step 3: Service Deployment

**3.1 Production Docker Compose**

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  cli-orchestrator:
    image: cli-orchestrator:${VERSION:-latest}
    ports:
      - "8080:8080"
      - "9090:9090"  # Metrics
    env_file:
      - config/production/.env
    volumes:
      - ./artifacts:/app/artifacts
      - ./logs:/app/logs
      - ./security:/app/security
      - ./.ai:/app/.ai:ro
    networks:
      - cli-orchestrator-network
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./config/ssl.crt:/etc/ssl/certs/cli-orchestrator.crt:ro
      - ./config/ssl.key:/etc/ssl/private/cli-orchestrator.key:ro
    depends_on:
      - cli-orchestrator
    networks:
      - cli-orchestrator-network
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    networks:
      - cli-orchestrator-network
    restart: unless-stopped

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: cli_orchestrator
      POSTGRES_USER: cli_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    networks:
      - cli-orchestrator-network
    restart: unless-stopped

networks:
  cli-orchestrator-network:
    driver: bridge

volumes:
  redis_data:
  postgres_data:
```

**3.2 Start Services**

```bash
# Build application image
docker build -t cli-orchestrator:v1.0.0 .

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Verify deployment
docker-compose ps
docker-compose logs cli-orchestrator
```

### Step 4: Verification and Testing

**4.1 Health Checks**

```bash
# Service health
curl -f https://api.cli-orchestrator.yourcompany.com/health

# Database connectivity
curl -f https://api.cli-orchestrator.yourcompany.com/info

# Authentication system
curl -X POST https://api.cli-orchestrator.yourcompany.com/api/v1/auth/api-key
```

**4.2 Smoke Tests**

```bash
# Execute test workflow
API_KEY=$(curl -s -X POST https://api.cli-orchestrator.yourcompany.com/api/v1/auth/api-key | jq -r .api_key)

curl -X POST https://api.cli-orchestrator.yourcompany.com/api/v1/workflows/execute \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_file": ".ai/workflows/HEALTH_CHECK.yaml",
    "dry_run": true
  }'

# Check metrics
curl -H "X-API-Key: $API_KEY" \
  https://api.cli-orchestrator.yourcompany.com/api/v1/metrics/summary
```

## Rolling Updates

### Zero-Downtime Update Process

**1. Blue-Green Deployment Setup**

```bash
# Deploy to staging environment (green)
docker-compose -f docker-compose.green.yml up -d

# Wait for green to be healthy
while ! curl -f http://green.cli-orchestrator.internal/health; do
  echo "Waiting for green environment..."
  sleep 10
done

# Run smoke tests against green
./scripts/smoke-test.sh green.cli-orchestrator.internal
```

**2. Traffic Switch**

```bash
# Update load balancer to point to green
# (This depends on your load balancer - nginx, ALB, etc.)

# Example for nginx:
sed -i 's/blue.cli-orchestrator.internal/green.cli-orchestrator.internal/' /etc/nginx/sites-enabled/cli-orchestrator
nginx -s reload

# Verify traffic is flowing
curl -f https://api.cli-orchestrator.yourcompany.com/health
```

**3. Cleanup Old Version**

```bash
# Wait 10 minutes to ensure stability
sleep 600

# Stop blue environment
docker-compose -f docker-compose.blue.yml down

# Update tags
docker tag cli-orchestrator:green cli-orchestrator:stable
docker tag cli-orchestrator:blue cli-orchestrator:previous
```

### Configuration-Only Updates

**1. Update Configuration**

```bash
# Update configuration file
nano config/production/.env

# Restart services with new config
docker-compose -f docker-compose.prod.yml up -d --force-recreate
```

**2. Verify Configuration**

```bash
# Check service picks up new config
curl https://api.cli-orchestrator.yourcompany.com/info | jq .

# Test affected functionality
./scripts/integration-test.sh
```

## Rollback Procedures

### Emergency Rollback

**Immediate Service Rollback (< 2 minutes)**

```bash
#!/bin/bash
# emergency-rollback.sh

echo "🚨 EMERGENCY ROLLBACK INITIATED"

# Switch load balancer back to previous version
if [ -f /etc/nginx/sites-enabled/cli-orchestrator ]; then
  sed -i 's/green.cli-orchestrator.internal/blue.cli-orchestrator.internal/' /etc/nginx/sites-enabled/cli-orchestrator
  nginx -s reload
fi

# Start previous version if not running
docker-compose -f docker-compose.blue.yml up -d

# Wait for health check
for i in {1..30}; do
  if curl -f http://blue.cli-orchestrator.internal/health; then
    echo "✅ Rollback successful - service healthy"
    exit 0
  fi
  echo "Waiting for service to start... ($i/30)"
  sleep 10
done

echo "❌ Rollback failed - service not healthy"
exit 1
```

### Database Rollback

**Schema Rollback**

```bash
# Rollback database schema
docker run --rm \
  --env-file config/production/.env \
  cli-orchestrator:previous \
  alembic downgrade -1  # Go back 1 migration

# Verify database integrity
docker run --rm \
  --env-file config/production/.env \
  cli-orchestrator:previous \
  python -c "from src.cli_multi_rapid.enterprise.config import ServiceConfig; print('DB rollback OK')"
```

**Full Database Restore**

```bash
# Stop application
docker-compose -f docker-compose.prod.yml stop cli-orchestrator

# Restore database from backup
docker exec postgres pg_restore \
  -U cli_user \
  -d cli_orchestrator \
  -c --if-exists \
  /backups/cli_orchestrator_$(date +%Y%m%d).dump

# Restart application with previous version
docker-compose -f docker-compose.blue.yml up -d
```

### Rollback Verification

```bash
# Verify service is running previous version
curl https://api.cli-orchestrator.yourcompany.com/info | jq .version

# Run integration tests
./scripts/integration-test.sh

# Check error rates in monitoring
./scripts/check-error-rates.sh
```

## Monitoring and Verification

### Health Monitoring

**Service Health Dashboard**

```bash
# Create health check script
cat > /opt/cli-orchestrator/scripts/health-check.sh << 'EOF'
#!/bin/bash

ENDPOINTS=(
  "https://api.cli-orchestrator.yourcompany.com/health"
  "https://api.cli-orchestrator.yourcompany.com/ready"
  "https://api.cli-orchestrator.yourcompany.com/metrics"
)

for endpoint in "${ENDPOINTS[@]}"; do
  if curl -f -s "$endpoint" > /dev/null; then
    echo "✅ $endpoint - OK"
  else
    echo "❌ $endpoint - FAILED"
  fi
done
EOF

chmod +x /opt/cli-orchestrator/scripts/health-check.sh

# Run health check
/opt/cli-orchestrator/scripts/health-check.sh
```

### Performance Monitoring

**Key Metrics to Monitor**

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| API Response Time | <200ms | >500ms | >1s |
| Workflow Success Rate | >95% | <90% | <85% |
| Token Usage Rate | <80% budget | >90% budget | >95% budget |
| Error Rate | <1% | >2% | >5% |
| Memory Usage | <80% | >85% | >90% |
| CPU Usage | <70% | >80% | >90% |

**Monitoring Setup**

```bash
# Prometheus configuration
cat > config/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'cli-orchestrator'
    static_configs:
      - targets: ['cli-orchestrator:9090']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'cli-orchestrator-health'
    static_configs:
      - targets: ['cli-orchestrator:8080']
    metrics_path: '/health'
    scrape_interval: 10s
EOF

# Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d prometheus grafana
```

### Log Monitoring

**Centralized Logging**

```bash
# Configure log forwarding to ELK stack or similar
docker-compose -f docker-compose.logging.yml up -d

# Monitor key log patterns
tail -f logs/cli-orchestrator.log | grep -E "(ERROR|WARN|workflow_execution_failed)"
```

## Troubleshooting

### Common Issues

**Issue: Service Won't Start**

```bash
# Check Docker logs
docker-compose logs cli-orchestrator

# Common causes:
# 1. Configuration errors
docker run --rm cli-orchestrator:latest python -c "from src.cli_multi_rapid.enterprise.config import ServiceConfig; ServiceConfig.from_env().validate()"

# 2. Database connection
docker run --rm --env-file config/production/.env cli-orchestrator:latest \
  python -c "import psycopg2; psycopg2.connect('your-db-url')"

# 3. Port conflicts
netstat -tlnp | grep :8080
```

**Issue: High Memory Usage**

```bash
# Check container memory usage
docker stats cli-orchestrator

# Check for memory leaks
docker exec cli-orchestrator python -c "
import psutil
process = psutil.Process()
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.1f}MB')
print(f'Open files: {len(process.open_files())}')
"

# Restart if necessary
docker-compose restart cli-orchestrator
```

**Issue: Workflow Execution Failures**

```bash
# Check workflow file syntax
cli-orchestrator verify .ai/workflows/PROBLEM_WORKFLOW.yaml

# Check adapter availability
curl -H "X-API-Key: $API_KEY" \
  https://api.cli-orchestrator.yourcompany.com/api/v1/adapters/status

# Review execution logs
grep "workflow_execution_failed" logs/cli-orchestrator.log | tail -10
```

### Emergency Procedures

**Complete System Recovery**

```bash
#!/bin/bash
# disaster-recovery.sh

echo "🚨 Starting disaster recovery procedure"

# 1. Stop all services
docker-compose -f docker-compose.prod.yml down

# 2. Restore from backup
./scripts/restore-from-backup.sh $(date +%Y%m%d)

# 3. Start services
docker-compose -f docker-compose.prod.yml up -d

# 4. Wait for health
for i in {1..60}; do
  if curl -f https://api.cli-orchestrator.yourcompany.com/health; then
    echo "✅ Disaster recovery successful"
    exit 0
  fi
  sleep 10
done

echo "❌ Disaster recovery failed"
exit 1
```

### Support Escalation

**Level 1: Self-Service (0-15 minutes)**

- Check service health endpoints
- Review recent logs
- Verify configuration
- Restart services if needed

**Level 2: Engineering Team (15-60 minutes)**

- Contact on-call engineer
- Provide incident details and steps taken
- Implement advanced troubleshooting
- Consider rollback if recent deployment

**Level 3: Emergency Response (60+ minutes)**

- Escalate to senior engineering
- Engage vendor support if needed
- Consider maintenance window
- Implement disaster recovery if necessary

### Contact Information

- **On-Call Engineer**: Slack @oncall-engineer
- **Engineering Team**: eng-team@yourcompany.com
- **Platform Team**: platform@yourcompany.com
- **Emergency**: +1-555-EMERGENCY
