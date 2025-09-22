#!/bin/bash
# CLI Orchestrator Docker Development Helper Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log() {
    echo -e "${BLUE}[CLI-ORCHESTRATOR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check prerequisites
check_prereqs() {
    log "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
    fi

    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed or not in PATH"
    fi

    success "Prerequisites check passed"
}

# Setup environment
setup_env() {
    log "Setting up environment..."

    # Create required directories
    mkdir -p artifacts logs cost

    # Create .env if it doesn't exist
    if [[ ! -f .env ]]; then
        if [[ -f .env.template ]]; then
            cp .env.template .env
            warn ".env file created from template. Please edit it with your API keys."
        else
            error ".env.template not found. Please create .env manually."
        fi
    fi

    success "Environment setup completed"
}

# Build containers
build() {
    log "Building containers..."
    docker-compose build "$@"
    success "Build completed"
}

# Start development environment
start() {
    log "Starting development environment..."
    setup_env
    docker-compose up -d

    # Wait for services to be healthy
    log "Waiting for services to be ready..."
    sleep 10

    # Check if services are healthy
    if docker-compose ps | grep -q "unhealthy"; then
        warn "Some services may not be healthy. Check with: docker-compose ps"
    fi

    success "Development environment started"
    log "CLI Orchestrator available at: http://localhost:8000"
    log "Redis available at: localhost:6379"
    log "View logs with: docker-compose logs -f"
}

# Stop environment
stop() {
    log "Stopping development environment..."
    docker-compose down
    success "Environment stopped"
}

# Restart environment
restart() {
    log "Restarting development environment..."
    stop
    start
}

# Run CLI command
run_cli() {
    if [[ $# -eq 0 ]]; then
        docker-compose exec cli-orchestrator cli-orchestrator --help
    else
        docker-compose exec cli-orchestrator cli-orchestrator "$@"
    fi
}

# Run tests
test() {
    log "Running tests..."
    docker-compose --profile testing run --rm cli-orchestrator-test
    success "Tests completed"
}

# Show logs
logs() {
    if [[ $# -eq 0 ]]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$@"
    fi
}

# Enter container
shell() {
    local service="${1:-cli-orchestrator}"
    log "Entering $service container..."
    docker-compose exec "$service" bash
}

# Clean up
clean() {
    log "Cleaning up containers and volumes..."
    docker-compose down -v --remove-orphans
    docker system prune -f
    success "Cleanup completed"
}

# Show status
status() {
    log "Service Status:"
    docker-compose ps

    log "Container Resource Usage:"
    docker stats --no-stream $(docker-compose ps -q) 2>/dev/null || true
}

# Production deployment
prod() {
    log "Starting production environment..."
    setup_env
    docker-compose --profile production up -d cli-orchestrator-prod redis
    success "Production environment started"
}

# Show help
show_help() {
    cat << EOF
CLI Orchestrator Docker Development Helper

Usage: $0 <command> [options]

Commands:
    setup       Setup environment and create required directories
    build       Build Docker containers
    start       Start development environment
    stop        Stop development environment
    restart     Restart development environment
    cli [args]  Run CLI orchestrator command
    test        Run test suite
    logs [svc]  Show logs (optionally for specific service)
    shell [svc] Enter container shell (default: cli-orchestrator)
    clean       Clean up containers and volumes
    status      Show service status and resource usage
    prod        Start production environment
    help        Show this help message

Examples:
    $0 start                                    # Start dev environment
    $0 cli run .ai/workflows/PY_EDIT_TRIAGE.yaml --dry-run
    $0 logs cli-orchestrator                    # Show app logs
    $0 shell redis                              # Enter Redis container
    $0 test                                     # Run tests

Environment:
    .env file is required with API keys and configuration.
    Use .env.template as a starting point.

EOF
}

# Main script logic
main() {
    check_prereqs

    case "${1:-help}" in
        setup)
            setup_env
            ;;
        build)
            shift
            build "$@"
            ;;
        start)
            start
            ;;
        stop)
            stop
            ;;
        restart)
            restart
            ;;
        cli)
            shift
            run_cli "$@"
            ;;
        test)
            test
            ;;
        logs)
            shift
            logs "$@"
            ;;
        shell)
            shift
            shell "$@"
            ;;
        clean)
            clean
            ;;
        status)
            status
            ;;
        prod)
            prod
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $1. Use '$0 help' for usage information."
            ;;
    esac
}

# Run main function with all arguments
main "$@"
