@echo off
REM CLI Orchestrator Docker Development Helper Script for Windows

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%\.."
cd /d "%PROJECT_ROOT%"

REM Check if command provided
if "%1"=="" goto :show_help
if "%1"=="help" goto :show_help
if "%1"=="--help" goto :show_help
if "%1"=="-h" goto :show_help

REM Check prerequisites
call :check_prereqs
if !errorlevel! neq 0 exit /b !errorlevel!

REM Route to appropriate function
if "%1"=="setup" call :setup_env
if "%1"=="build" call :build %*
if "%1"=="start" call :start_dev
if "%1"=="stop" call :stop_dev
if "%1"=="restart" call :restart_dev
if "%1"=="cli" call :run_cli %*
if "%1"=="test" call :run_tests
if "%1"=="logs" call :show_logs %*
if "%1"=="shell" call :enter_shell %*
if "%1"=="clean" call :cleanup
if "%1"=="status" call :show_status
if "%1"=="prod" call :start_prod

goto :eof

:check_prereqs
echo [CLI-ORCHESTRATOR] Checking prerequisites...
docker --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker is not installed or not in PATH
    exit /b 1
)

docker-compose --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Docker Compose is not installed or not in PATH
    exit /b 1
)

echo [SUCCESS] Prerequisites check passed
exit /b 0

:setup_env
echo [CLI-ORCHESTRATOR] Setting up environment...

REM Create required directories
if not exist artifacts mkdir artifacts
if not exist logs mkdir logs
if not exist cost mkdir cost

REM Create .env if it doesn't exist
if not exist .env (
    if exist .env.template (
        copy .env.template .env >nul
        echo [WARNING] .env file created from template. Please edit it with your API keys.
    ) else (
        echo [ERROR] .env.template not found. Please create .env manually.
        exit /b 1
    )
)

echo [SUCCESS] Environment setup completed
goto :eof

:build
echo [CLI-ORCHESTRATOR] Building containers...
shift
docker-compose build %*
if !errorlevel! equ 0 echo [SUCCESS] Build completed
goto :eof

:start_dev
echo [CLI-ORCHESTRATOR] Starting development environment...
call :setup_env
docker-compose up -d

echo [CLI-ORCHESTRATOR] Waiting for services to be ready...
timeout /t 10 >nul

echo [SUCCESS] Development environment started
echo [CLI-ORCHESTRATOR] CLI Orchestrator available at: http://localhost:8000
echo [CLI-ORCHESTRATOR] Redis available at: localhost:6379
echo [CLI-ORCHESTRATOR] View logs with: docker-compose logs -f
goto :eof

:stop_dev
echo [CLI-ORCHESTRATOR] Stopping development environment...
docker-compose down
echo [SUCCESS] Environment stopped
goto :eof

:restart_dev
echo [CLI-ORCHESTRATOR] Restarting development environment...
call :stop_dev
call :start_dev
goto :eof

:run_cli
shift
if "%1"=="" (
    docker-compose exec cli-orchestrator cli-orchestrator --help
) else (
    docker-compose exec cli-orchestrator cli-orchestrator %*
)
goto :eof

:run_tests
echo [CLI-ORCHESTRATOR] Running tests...
docker-compose --profile testing run --rm cli-orchestrator-test
if !errorlevel! equ 0 echo [SUCCESS] Tests completed
goto :eof

:show_logs
shift
if "%1"=="" (
    docker-compose logs -f
) else (
    docker-compose logs -f %1
)
goto :eof

:enter_shell
shift
if "%1"=="" (
    set "service=cli-orchestrator"
) else (
    set "service=%1"
)
echo [CLI-ORCHESTRATOR] Entering !service! container...
docker-compose exec !service! bash
goto :eof

:cleanup
echo [CLI-ORCHESTRATOR] Cleaning up containers and volumes...
docker-compose down -v --remove-orphans
docker system prune -f
echo [SUCCESS] Cleanup completed
goto :eof

:show_status
echo [CLI-ORCHESTRATOR] Service Status:
docker-compose ps

echo [CLI-ORCHESTRATOR] Container Resource Usage:
docker stats --no-stream
goto :eof

:start_prod
echo [CLI-ORCHESTRATOR] Starting production environment...
call :setup_env
docker-compose --profile production up -d cli-orchestrator-prod redis
echo [SUCCESS] Production environment started
goto :eof

:show_help
echo CLI Orchestrator Docker Development Helper
echo.
echo Usage: %~nx0 ^<command^> [options]
echo.
echo Commands:
echo     setup       Setup environment and create required directories
echo     build       Build Docker containers
echo     start       Start development environment
echo     stop        Stop development environment
echo     restart     Restart development environment
echo     cli [args]  Run CLI orchestrator command
echo     test        Run test suite
echo     logs [svc]  Show logs (optionally for specific service)
echo     shell [svc] Enter container shell (default: cli-orchestrator)
echo     clean       Clean up containers and volumes
echo     status      Show service status and resource usage
echo     prod        Start production environment
echo     help        Show this help message
echo.
echo Examples:
echo     %~nx0 start                                    # Start dev environment
echo     %~nx0 cli run .ai/workflows/PY_EDIT_TRIAGE.yaml --dry-run
echo     %~nx0 logs cli-orchestrator                    # Show app logs
echo     %~nx0 shell redis                              # Enter Redis container
echo     %~nx0 test                                     # Run tests
echo.
echo Environment:
echo     .env file is required with API keys and configuration.
echo     Use .env.template as a starting point.
goto :eof