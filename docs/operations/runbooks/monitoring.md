# CLI Orchestrator Monitoring & Troubleshooting Runbook

This runbook provides comprehensive monitoring procedures, alert handling, and troubleshooting guides for the CLI Orchestrator system.

## Table of Contents

1. [Monitoring Overview](#monitoring-overview)
2. [Key Performance Indicators](#key-performance-indicators)
3. [Alert Response Procedures](#alert-response-procedures)
4. [Troubleshooting Guide](#troubleshooting-guide)
5. [Performance Optimization](#performance-optimization)
6. [Capacity Planning](#capacity-planning)
7. [Incident Management](#incident-management)

## Monitoring Overview

### Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Prometheus    │────│    Grafana      │────│   AlertManager  │
│   (Metrics)     │    │  (Dashboards)   │    │    (Alerts)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ELK Stack     │    │  CLI Orchestrator│    │   PagerDuty     │
│    (Logs)       │    │    Services     │    │  (Incidents)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Monitoring Stack Components

- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **ELK Stack**: Log aggregation and analysis
- **AlertManager**: Alert routing and notification
- **PagerDuty**: Incident management and escalation

### Data Sources

1. **Application Metrics**: HTTP requests, workflow executions, token usage
2. **System Metrics**: CPU, memory, disk, network usage
3. **Business Metrics**: Success rates, user activity, cost tracking
4. **Security Metrics**: Authentication failures, permission denials
5. **Infrastructure Metrics**: Database, Redis, Docker containers

## Key Performance Indicators

### System Health KPIs

| Metric | Target | Warning Threshold | Critical Threshold |
|--------|--------|------------------|-------------------|
| API Response Time (p95) | <200ms | >500ms | >1000ms |
| API Error Rate | <0.5% | >2% | >5% |
| Workflow Success Rate | >98% | <95% | <90% |
| Service Uptime | >99.9% | <99.5% | <99% |
| Memory Usage | <75% | >85% | >95% |
| CPU Usage | <70% | >85% | >95% |
| Disk Usage | <80% | >90% | >95% |

### Business KPIs

| Metric | Target | Warning Threshold | Critical Threshold |
|--------|--------|------------------|-------------------|
| Daily Active Users | Growing | Declining 3 days | Declining 7 days |
| Token Efficiency | >80% budget | >95% budget | Budget exceeded |
| Workflow Completion Time | <2 min avg | >5 min avg | >10 min avg |
| Artifact Generation Rate | >95% success | <90% success | <80% success |

### Security KPIs

| Metric | Target | Warning Threshold | Critical Threshold |
|--------|--------|------------------|-------------------|
| Failed Authentication Rate | <1% | >5% | >10% |
| Permission Denials | <2% | >10% | >20% |
| Suspicious Activity | 0 incidents | 1+ incidents | 3+ incidents |
| API Key Misuse | 0 incidents | 1+ incidents | Multiple incidents |

## Alert Response Procedures

### Critical Alerts (Page Immediately)

#### Service Down Alert

```
Alert: CLI Orchestrator service is not responding
Severity: Critical
Response Time: <5 minutes
```

**Investigation Steps:**

1. Check service health endpoint: `curl -f https://api.your-domain.com/health`
2. Verify container status: `docker-compose ps`
3. Check recent logs: `docker-compose logs --tail=100 cli-orchestrator`
4. Check system resources: `docker stats`

**Resolution Actions:**

```bash
# Quick restart
docker-compose restart cli-orchestrator

# If restart fails, check for issues:
docker-compose logs cli-orchestrator | grep ERROR

# Check configuration
docker exec cli-orchestrator python -c "
from src.cli_multi_rapid.enterprise.config import ServiceConfig;
config = ServiceConfig.from_env();
errors = config.validate();
print('Config errors:' if errors else 'Config OK', errors)
"

# Emergency rollback if needed
docker-compose -f docker-compose.previous.yml up -d
```

#### High Error Rate Alert

```
Alert: API error rate >5% for 5 minutes
Severity: Critical
Response Time: <10 minutes
```

**Investigation Steps:**

```bash
# Check error breakdown
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/metrics/summary | jq .errors

# Check recent error logs
docker-compose logs cli-orchestrator --since=10m | grep ERROR

# Check specific failing endpoints
grep "HTTP 5" logs/access.log | tail -20

# Check database connectivity
docker exec cli-orchestrator python -c "
import psycopg2;
conn = psycopg2.connect('$DATABASE_URL');
print('DB connection OK')
"
```

**Resolution Actions:**

```bash
# If database issues:
docker-compose restart postgres
# Wait for recovery
sleep 30
docker-compose restart cli-orchestrator

# If memory issues:
docker exec cli-orchestrator python -c "
import psutil;
print(f'Memory: {psutil.virtual_memory().percent}%')
"
# Restart if > 90%
docker-compose restart cli-orchestrator

# If workflow failures:
# Check adapter status
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/adapters/status
```

#### Workflow Execution Failures

```
Alert: >50% workflows failing for 5 minutes
Severity: Critical
Response Time: <10 minutes
```

**Investigation Steps:**

```bash
# Check workflow error patterns
grep "workflow_execution_failed" logs/cli-orchestrator.log | tail -10

# Check adapter health
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/workflows/health-check/status

# Check schema validation
ls -la .ai/schemas/*.json
cli-orchestrator verify .ai/workflows/SAMPLE.yaml

# Check file system permissions
ls -la artifacts/ logs/ security/
```

**Resolution Actions:**

```bash
# Fix common schema issues
git pull origin main  # Get latest schemas

# Reset adapter registry
docker-compose restart cli-orchestrator

# Clear corrupted artifacts
find artifacts/ -name "*.tmp" -delete
find artifacts/ -size 0 -delete

# Check disk space
df -h
# Clean up if needed
docker system prune -f
```

### Warning Alerts (Investigate within 30 minutes)

#### High Response Time Alert

```bash
# Check current load
docker stats cli-orchestrator

# Check slow queries
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC LIMIT 10;
"

# Check for resource constraints
free -h
iostat -x 1 5
```

#### High Memory Usage Alert

```bash
# Check memory breakdown
docker exec cli-orchestrator python -c "
import psutil, gc
process = psutil.Process()
print(f'RSS: {process.memory_info().rss / 1024**2:.1f}MB')
print(f'VMS: {process.memory_info().vms / 1024**2:.1f}MB')
print(f'Open files: {len(process.open_files())}')
gc.collect()
"

# Check for memory leaks
docker exec cli-orchestrator python -m memory_profiler your_script.py

# Restart if memory usage >90%
if [[ $(docker stats --no-stream --format "{{.MemPerc}}" cli-orchestrator | cut -d'%' -f1) > 90 ]]; then
  echo "High memory usage detected, restarting service"
  docker-compose restart cli-orchestrator
fi
```

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: "Workflow Schema Validation Failed"

**Symptoms:**

- Workflow execution returns validation errors
- New workflows cannot be executed
- Schema-related error messages in logs

**Diagnosis:**

```bash
# Check schema files exist
ls -la .ai/schemas/

# Validate specific workflow
cli-orchestrator verify .ai/workflows/FAILING_WORKFLOW.yaml \
  --schema .ai/schemas/workflow.schema.json

# Check schema syntax
python -c "import json; json.load(open('.ai/schemas/workflow.schema.json'))"

# Check for recent schema changes
git log --oneline .ai/schemas/ | head -5
```

**Resolution:**

```bash
# Update to latest schemas
git pull origin main

# Fix common schema issues
# 1. Missing required fields
jq '.steps[].id //= "auto-generated"' .ai/workflows/FAILING_WORKFLOW.yaml

# 2. Invalid step format
# Check step IDs follow X.YYY format
# Check actor names are valid

# 3. Regenerate schema if corrupted
python scripts/generate_schema.py > .ai/schemas/workflow.schema.json

# Restart service after schema fixes
docker-compose restart cli-orchestrator
```

#### Issue: "Adapter Not Available"

**Symptoms:**

- Steps fail with "adapter not available" errors
- Certain workflow types always fail
- Adapter registry appears empty

**Diagnosis:**

```bash
# Check adapter registry
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/adapters/list

# Check adapter configuration
docker exec cli-orchestrator python -c "
from src.cli_multi_rapid.router import Router
router = Router()
print('Available adapters:', router.list_adapters())
"

# Check for adapter dependencies
docker exec cli-orchestrator python -c "
import importlib
adapters = ['aider', 'anthropic', 'openai']
for adapter in adapters:
    try:
        importlib.import_module(adapter)
        print(f'{adapter}: OK')
    except ImportError as e:
        print(f'{adapter}: MISSING - {e}')
"
```

**Resolution:**

```bash
# Install missing adapter dependencies
docker exec cli-orchestrator pip install aider-chat anthropic openai

# Or rebuild with latest requirements
docker-compose build --no-cache cli-orchestrator
docker-compose up -d

# Reset adapter registry
docker-compose restart cli-orchestrator

# Verify adapters loaded
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/adapters/health
```

#### Issue: "Token Budget Exceeded"

**Symptoms:**

- Workflows fail with token limit errors
- Costs higher than expected
- Token usage metrics spiking

**Diagnosis:**

```bash
# Check current token usage
curl -H "X-API-Key: $API_KEY" \
  https://api.your-domain.com/api/v1/metrics/tokens

# Check token usage by workflow
grep "tokens_used" logs/cli-orchestrator.log | \
  jq -r '.workflow_name + ": " + (.tokens_used | tostring)' | \
  sort | uniq -c | sort -nr

# Check for runaway workflows
ps aux | grep -i workflow | grep -v grep
```

**Resolution:**

```bash
# Update token limits in configuration
nano config/production/.env
# CLI_ORCHESTRATOR_MAX_TOKENS_DEFAULT=200000

# Restart with new limits
docker-compose restart cli-orchestrator

# Optimize token-heavy workflows
# 1. Use more deterministic adapters
# 2. Reduce file scope with specific patterns
# 3. Implement workflow caching

# Monitor token usage
watch -n 30 "curl -s -H 'X-API-Key: $API_KEY' \
  https://api.your-domain.com/api/v1/metrics/tokens | jq .daily_usage"
```

### Performance Issues

#### Issue: Slow Workflow Execution

**Investigation:**

```bash
# Profile workflow execution
time cli-orchestrator run .ai/workflows/SLOW_WORKFLOW.yaml \
  --files "**/*.py" --dry-run

# Check step-by-step timing
grep "step_duration" logs/cli-orchestrator.log | \
  jq -r '"\(.step_name): \(.duration_seconds)s"' | \
  sort -k2 -nr

# Check I/O wait time
iostat -x 1 10

# Check network latency to AI services
ping -c 5 api.anthropic.com
ping -c 5 api.openai.com
```

**Optimization:**

```bash
# Enable workflow parallelization
# Update workflow YAML to use depends_on instead of sequential steps

# Implement caching
mkdir -p cache/workflows
# Add cache configuration to .env
CLI_ORCHESTRATOR_CACHE_ENABLED=true
CLI_ORCHESTRATOR_CACHE_TTL=3600

# Scale up resources
docker-compose up -d --scale cli-orchestrator=3
```

#### Issue: High Database Load

**Investigation:**

```bash
# Check active connections
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
SELECT count(*) as connections, state
FROM pg_stat_activity
GROUP BY state;
"

# Check slow queries
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
SELECT query, mean_time, calls
FROM pg_stat_statements
WHERE mean_time > 1000
ORDER BY mean_time DESC LIMIT 5;
"

# Check lock contention
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
SELECT blocked_locks.pid AS blocked_pid,
       blocking_locks.pid AS blocking_pid,
       blocked_activity.query AS blocked_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity
  ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks
  ON blocking_locks.locktype = blocked_locks.locktype
WHERE NOT blocked_locks.granted;
"
```

**Resolution:**

```bash
# Add database indexes
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
CREATE INDEX CONCURRENTLY idx_workflows_created_at ON workflows(created_at);
CREATE INDEX CONCURRENTLY idx_executions_status ON executions(status);
CREATE INDEX CONCURRENTLY idx_artifacts_workflow_id ON artifacts(workflow_id);
"

# Optimize connection pooling
# Update docker-compose.yml
environment:
  - DATABASE_POOL_SIZE=20
  - DATABASE_MAX_OVERFLOW=30

# Run database maintenance
docker exec postgres psql -U cli_user -d cli_orchestrator -c "
VACUUM ANALYZE;
REINDEX DATABASE cli_orchestrator;
"
```

## Performance Optimization

### Workflow Performance

**Optimization Strategies:**

1. **Use Deterministic Adapters**: Prefer tools over AI when possible
2. **Optimize File Patterns**: Use specific patterns to reduce scope
3. **Implement Caching**: Cache adapter results and workflow artifacts
4. **Parallel Execution**: Design workflows for concurrent step execution

**Implementation:**

```yaml
# Example optimized workflow
name: "Optimized Python Triage"
policy:
  max_tokens: 50000
  prefer_deterministic: true
  enable_caching: true
  parallel_execution: true

steps:
  - id: "1.001"
    name: "Fast Linting"
    actor: "ruff_checker"  # Deterministic
    with:
      files: "**/*.py"
      parallel: true

  - id: "1.002"
    name: "Type Checking"
    actor: "mypy_checker"  # Deterministic
    depends_on: []  # Can run in parallel with linting

  - id: "2.001"
    name: "AI Analysis"
    actor: "ai_editor"  # Only for complex issues
    depends_on: ["1.001", "1.002"]
    when: "has_errors('artifacts/linting.json')"
```

### System Performance

**Resource Optimization:**

```bash
# Optimize Docker containers
# Add to docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '0.5'
      memory: 1G

# Enable container health checks
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s

# Optimize logging
logging:
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "5"
```

**Application Tuning:**

```bash
# Optimize Python settings
export PYTHONOPTIMIZE=2
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Optimize async settings
export CLI_ORCHESTRATOR_ASYNC_POOL_SIZE=50
export CLI_ORCHESTRATOR_ASYNC_TIMEOUT=30

# Enable performance profiling
export CLI_ORCHESTRATOR_PROFILING_ENABLED=true
export CLI_ORCHESTRATOR_PROFILING_SAMPLE_RATE=0.1
```

## Capacity Planning

### Growth Monitoring

**Key Growth Metrics:**

```bash
# Daily active users
grep "workflow_execution" logs/cli-orchestrator.log | \
  jq -r '.user_id' | sort -u | wc -l

# Workflow execution trends
grep "workflow_completed" logs/cli-orchestrator.log | \
  jq -r '.timestamp[:10]' | sort | uniq -c

# Token usage trends
grep "tokens_used" logs/cli-orchestrator.log | \
  jq -r '"\(.timestamp[:10]) \(.tokens_used)"' | \
  awk '{date[$1] += $2} END {for (d in date) print d, date[d]}' | sort
```

**Capacity Thresholds:**

| Resource | Current Capacity | Scale Trigger | Action |
|----------|------------------|---------------|---------|
| CPU | 4 cores | >70% for 1 hour | Add 2 cores |
| Memory | 8GB | >80% for 30 min | Add 4GB |
| Storage | 100GB | >80% used | Add 100GB |
| Database | 1000 conn | >800 conn | Scale up DB |
| API Requests | 1000 RPS | >800 RPS | Add instance |

### Scaling Procedures

**Horizontal Scaling:**

```bash
# Scale application containers
docker-compose up -d --scale cli-orchestrator=3

# Add load balancer configuration
# Update nginx.conf
upstream cli_orchestrator {
    server cli-orchestrator_cli-orchestrator_1:8080;
    server cli-orchestrator_cli-orchestrator_2:8080;
    server cli-orchestrator_cli-orchestrator_3:8080;
}
```

**Vertical Scaling:**

```bash
# Update resource limits in docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '4.0'    # Increased from 2.0
      memory: 8G     # Increased from 4G

# Restart with new limits
docker-compose up -d --force-recreate
```

## Incident Management

### Incident Classification

| Severity | Definition | Response Time | Example |
|----------|------------|---------------|---------|
| Critical | Service completely down | 5 minutes | API returning 500s |
| High | Major functionality impacted | 30 minutes | Workflows failing >50% |
| Medium | Minor functionality impacted | 2 hours | Slow response times |
| Low | Cosmetic or minor issues | Next business day | UI inconsistencies |

### Incident Response Process

**1. Detection and Alert (0-5 minutes)**

```bash
# Automated detection
# - Monitoring alerts trigger PagerDuty
# - Health checks fail
# - Error rates spike

# Manual reporting
# - User reports issues
# - Support ticket escalation
```

**2. Initial Response (5-15 minutes)**

```bash
#!/bin/bash
# incident-response.sh

echo "🚨 Incident Response Initiated: $(date)"

# Gather basic information
echo "Service Status:"
curl -s https://api.your-domain.com/health | jq .

echo "Container Status:"
docker-compose ps

echo "Recent Errors:"
docker-compose logs --tail=20 cli-orchestrator | grep ERROR

echo "Resource Usage:"
docker stats --no-stream

# Document incident
INCIDENT_ID="INC-$(date +%Y%m%d%H%M%S)"
echo "Incident ID: $INCIDENT_ID" > "incidents/$INCIDENT_ID.md"
```

**3. Diagnosis and Resolution (15-60 minutes)**

```bash
# Follow runbook procedures based on alert type
# - Service down → deployment runbook
# - High error rate → troubleshooting guide
# - Performance issues → optimization guide

# Keep stakeholders informed
# Send updates every 30 minutes during active incidents
```

**4. Post-Incident (1-24 hours)**

```bash
# Document resolution
echo "## Resolution" >> "incidents/$INCIDENT_ID.md"
echo "- Root cause: ..." >> "incidents/$INCIDENT_ID.md"
echo "- Resolution: ..." >> "incidents/$INCIDENT_ID.md"
echo "- Preventive measures: ..." >> "incidents/$INCIDENT_ID.md"

# Schedule post-mortem if severity > Medium
# Update monitoring/alerting based on lessons learned
```

### Communication Templates

**Initial Incident Notification:**

```
🚨 INCIDENT: CLI Orchestrator Service Issues
Severity: [Critical/High/Medium/Low]
Start Time: [timestamp]
Impact: [description of user impact]
Current Status: Investigating
Next Update: In 30 minutes
Incident ID: [INC-YYYYMMDDHHMMSS]
```

**Resolution Notification:**

```
✅ RESOLVED: CLI Orchestrator Service Issues
Incident ID: [INC-YYYYMMDDHHMMSS]
Resolution Time: [timestamp]
Duration: [total time]
Root Cause: [brief explanation]
Resolution: [what was done to fix]
Post-Mortem: [link to detailed analysis if applicable]
```

This monitoring and troubleshooting runbook provides comprehensive procedures for maintaining the health, performance, and availability of the CLI Orchestrator system. Regular review and updates ensure the procedures remain current with system evolution and operational experience.
