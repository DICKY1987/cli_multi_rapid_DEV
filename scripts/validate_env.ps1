[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# First, run the guard check
& "$PSScriptRoot/guard_cwd.ps1"

$failures = @()
$ignored = $false

# Check if .claude.json is properly ignored
try {
    git check-ignore -q .claude.json
    if ($LASTEXITCODE -eq 0) {
        $ignored = $true
    }
} catch {
    # If command fails, assume not ignored
}

if (-not $ignored) {
    $failures += ".claude.json is not ignored (security risk)"
}

# Check for pre-commit configuration and run hooks
if (Test-Path ".pre-commit-config.yaml") {
    if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
        Write-Host "Running pre-commit hooks (may modify files)..." -ForegroundColor Yellow
        pre-commit run --all-files
        if ($LASTEXITCODE -ne 0) {
            $failures += "pre-commit hooks reported issues"
        }
    } else {
        Write-Host "pre-commit not installed; skipping hook validation." -ForegroundColor Yellow
    }
} else {
    $failures += ".pre-commit-config.yaml not found"
}

# Report results
if ($failures.Count -gt 0) {
    Write-Host "== VALIDATE: FAIL ==" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}

Write-Host "== VALIDATE: OK ==" -ForegroundColor Green
