[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Get the Git repository root
$toplevel = (git rev-parse --show-toplevel 2>$null).Trim()
if (-not $toplevel) {
    throw "Not inside a Git repository."
}

# Get the user's HOME directory
$home = $env:USERPROFILE.Trim()

# Check if repo root equals HOME (the core issue)
if ($toplevel -eq $home) {
    throw "Refusing: repo root equals HOME ($home). cd to the real project root."
}

Write-Host "Repo root OK: $toplevel" -ForegroundColor Green
