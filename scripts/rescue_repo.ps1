<#
.SYNOPSIS
Rescue polluted HOME repo: export diffs, fresh clone, reapply, pre-commit, commit to rescue/*, push.

.DESCRIPTION
Use ONLY if you suspect the current working tree is polluted (e.g., repo root = HOME).
This script will:
1. Export current work as patches and diffs
2. Backup and remove the polluted .git from HOME
3. Clone fresh repository to proper location
4. Reapply saved work
5. Run pre-commit hooks
6. Commit to a rescue branch and push

.PARAMETER RepoUrl
The Git repository URL to clone from. Auto-detected from current remote if not specified.

.EXAMPLE
.\rescue_repo.ps1
# Automatically detects repository and performs rescue operation
#>

[CmdletBinding()]
param(
    [string]$RepoUrl = ""
)

$ErrorActionPreference = "Stop"

# Get current state
$home = $env:USERPROFILE.Trim()
$toplevel = (git rev-parse --show-toplevel 2>$null).Trim()

if (-not $toplevel) {
    throw "Not inside a Git repository. If your HOME has a .git, cd to HOME and run again."
}

if ($toplevel -ne $home) {
    Write-Host "Current repo root is not HOME. This rescue script is intended for polluted HOME repos." -ForegroundColor Yellow
    Write-Host "Current repo root: $toplevel" -ForegroundColor Yellow
    Write-Host "If you still want to proceed from here, press Ctrl+C and follow standard recovery." -ForegroundColor Yellow
    exit 1
}

Write-Host "Detected polluted HOME repository. Starting rescue operation..." -ForegroundColor Red

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$export = Join-Path $home "rescue_export_$stamp"
New-Item -ItemType Directory -Path $export | Out-Null

Write-Host "Exporting current work to: $export" -ForegroundColor Cyan

# Export current work
git diff > (Join-Path $export "working.diff")
git diff --cached > (Join-Path $export "staged.diff")

# Export recent commits as patches
New-Item -ItemType Directory -Path (Join-Path $export "patches") | Out-Null
try {
    git format-patch --no-stat -o (Join-Path $export "patches") HEAD~10 2>$null | Out-Null
    Write-Host "Exported recent commits as patches" -ForegroundColor Green
} catch {
    Write-Host "Could not export patches (may be no commits)" -ForegroundColor Yellow
}

# Get remote URL
if (-not $RepoUrl) {
    try {
        $RepoUrl = (git remote get-url origin 2>$null).Trim()
    } catch {
        throw "Cannot find origin URL. Please specify -RepoUrl parameter."
    }
}

if (-not $RepoUrl) {
    throw "Cannot find origin URL. Please specify -RepoUrl parameter."
}

Write-Host "Repository URL: $RepoUrl" -ForegroundColor Cyan

# Backup and remove polluted .git
$backup = Join-Path $home ".git_HOME_BACKUP_$stamp"
Write-Host "Backing up polluted .git to: $backup" -ForegroundColor Yellow
Rename-Item -Path (Join-Path $home ".git") -NewName (Split-Path $backup -Leaf)

# Determine destination directory
$repoName = ($RepoUrl -replace '.*[:/](.+?)(?:\.git)?$','$1')
$dest = Join-Path $home $repoName
if (Test-Path $dest) {
    $dest = "${dest}_clean_$stamp"
}

Write-Host "Cloning fresh repository to: $dest" -ForegroundColor Cyan
git clone $RepoUrl $dest
Set-Location $dest

# Apply saved work
Write-Host "Applying saved work..." -ForegroundColor Cyan

# Apply diffs (may have conflicts, that's ok)
try {
    git apply (Join-Path $export "working.diff") 2>$null
    Write-Host "Applied working diff" -ForegroundColor Green
} catch {
    Write-Host "Working diff had conflicts (normal)" -ForegroundColor Yellow
}

try {
    git apply (Join-Path $export "staged.diff") 2>$null
    Write-Host "Applied staged diff" -ForegroundColor Green
} catch {
    Write-Host "Staged diff had conflicts (normal)" -ForegroundColor Yellow
}

# Apply patches
$patchFiles = Get-ChildItem -Path (Join-Path $export "patches") -Filter *.patch
foreach ($patch in $patchFiles) {
    try {
        git am $patch.FullName
        Write-Host "Applied patch: $($patch.Name)" -ForegroundColor Green
    } catch {
        Write-Host "Patch apply failed: $($patch.Name)" -ForegroundColor Yellow
        # Abort the failed am attempt
        git am --abort 2>$null
    }
}

# Create rescue branch
$branch = "rescue/$stamp"
git switch -c $branch
Write-Host "Created rescue branch: $branch" -ForegroundColor Cyan

# Run pre-commit if available
if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
    Write-Host "Running pre-commit hooks..." -ForegroundColor Cyan
    pre-commit run --all-files
} else {
    Write-Host "pre-commit not available, skipping hooks" -ForegroundColor Yellow
}

# Stage and commit all changes
git add -A
$commitMsg = "chore(rescue): salvage from polluted HOME repo ($stamp)"
git commit -m $commitMsg 2>$null

# Push rescue branch
Write-Host "Pushing rescue branch..." -ForegroundColor Cyan
git push -u origin $branch

Write-Host ""
Write-Host "========== RESCUE COMPLETE ==========" -ForegroundColor Green
Write-Host "Rescued work saved in: $export" -ForegroundColor Cyan
Write-Host "Fresh repository at: $dest" -ForegroundColor Cyan
Write-Host "Rescue branch pushed: $branch" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Review the rescue branch and open a PR" -ForegroundColor White
Write-Host "2. Delete the backup if everything looks good: $backup" -ForegroundColor White
Write-Host "3. Use the clean repository at: $dest" -ForegroundColor White
