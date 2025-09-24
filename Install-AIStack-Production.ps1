<#
.SYNOPSIS
    Production-Ready Zero-Touch AI Stack Installer

.DESCRIPTION
    Idempotent installer for Redis (Windows), Ollama, Aider, and Gemini CLI
    - Robust error handling with actionable messages
    - Preflight validation (admin, network, winget)
    - Safe PATH management (no duplicates)
    - Service verification and health checks
    - Full transcript logging

.PARAMETER OpenAIKey
    OpenAI API key for Aider configuration

.PARAMETER GeminiKey
    Google Gemini API key for Gemini CLI

.PARAMETER OllamaModel
    Ollama model to download (default: llama3.2)

.PARAMETER SkipModelPull
    Skip automatic Ollama model download

.PARAMETER PauseOnExit
    Wait for keypress before exiting (useful for debugging)

.EXAMPLE
    .\Install-AIStack-Production.ps1 -OpenAIKey 'sk-...' -GeminiKey 'AI...'

.EXAMPLE
    .\Install-AIStack-Production.ps1 -OllamaModel 'llama3.2:latest' -SkipModelPull
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$OpenAIKey = $env:OPENAI_API_KEY,
    [string]$GeminiKey = $env:GEMINI_API_KEY,
    [ValidateNotNullOrEmpty()]
    [string]$OllamaModel = "llama3.2",
    [switch]$SkipModelPull,
    [switch]$PauseOnExit
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

#region Logging Functions
function Write-Info {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Fail {
    param(
        [Parameter(Mandatory = $true)][string]$Message,
        [int]$Code = 1
    )
    Write-Err $Message
    throw ([System.Exception]::new($Message))
}
#endregion

#region Directory Setup
$Root    = Join-Path $env:USERPROFILE 'ai-stack'
$Bin     = Join-Path $Root 'bin'
$Secrets = Join-Path $Root 'secrets'
$Logs    = Join-Path $Root 'logs'
$RedisH  = Join-Path $Root 'redis'

# Create directory structure
$null = New-Item -ItemType Directory -Force -Path $Root, $Bin, $Secrets, $Logs, $RedisH

# Start transcript
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$transcriptPath = Join-Path $Logs "install-$timestamp.log"
try {
    Start-Transcript -Path $transcriptPath -ErrorAction SilentlyContinue | Out-Null
    Write-Info "Transcript started: $transcriptPath"
} catch {
    Write-Warn "Could not start transcript"
}

# Harden secrets directory ACL (current user only)
try {
    $acl = Get-Acl $Secrets
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $rule = New-Object Security.AccessControl.FileSystemAccessRule(
        $identity,
        'FullControl',
        'ContainerInherit,ObjectInherit',
        'None',
        'Allow'
    )
    $acl.SetAccessRuleProtection($true, $false)
    $acl.ResetAccessRule($rule)
    Set-Acl -Path $Secrets -AclObject $acl
    Write-OK "Secrets directory ACL hardened"
} catch {
    Write-Warn "Could not harden ACL on $Secrets (continuing)"
}
#endregion

#region Admin Elevation
function Ensure-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).
        IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Info "Elevating to Administrator..."

        $argList = @(
            '-NoProfile'
            '-ExecutionPolicy', 'Bypass'
            '-File', "`"$PSCommandPath`""
            '-OllamaModel', "`"$OllamaModel`""
        )

        if ($OpenAIKey) { $argList += '-OpenAIKey', "`"$OpenAIKey`"" }
        if ($GeminiKey) { $argList += '-GeminiKey', "`"$GeminiKey`"" }
        if ($SkipModelPull) { $argList += '-SkipModelPull' }
        if ($PauseOnExit) { $argList += '-PauseOnExit' }

        $params = @{
            FilePath     = 'powershell.exe'
            ArgumentList = $argList -join ' '
            Verb         = 'RunAs'
        }

        Start-Process @params
        exit
    }
}

# Check if running as admin but don't force elevation
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).
    IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($isAdmin) {
    Write-OK "Running with Administrator privileges"
} else {
    Write-Warn "Running without Administrator privileges. Some features (Redis service, system installs) may be limited."
}
#endregion

#region Preflight Checks
function Assert-Preflight {
    Write-Info "Running preflight checks..."

    # PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Fail "PowerShell 5.0 or higher required. Current: $($PSVersionTable.PSVersion)"
    }
    Write-OK "PowerShell version: $($PSVersionTable.PSVersion)"

    # Enable TLS 1.2
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Write-OK "TLS 1.2 enabled"
    } catch {
        Write-Warn "Could not enable TLS 1.2"
    }

    # DNS check
    try {
        [System.Net.Dns]::GetHostEntry("api.github.com") | Out-Null
        Write-OK "DNS resolution working"
    } catch {
        Fail "DNS resolution failed for api.github.com. Check network connection."
    }

    # HTTPS connectivity
    try {
        $request = [System.Net.HttpWebRequest]::Create("https://api.github.com/")
        $request.UserAgent = "ai-stack-installer/1.0"
        $request.Timeout = 10000
        $response = $request.GetResponse()
        $response.Close()
        Write-OK "HTTPS connectivity verified"
    } catch {
        Write-Warn "HTTPS check to GitHub failed. Downloads may fail."
    }
}

Assert-Preflight
#endregion

#region Command Resolution
function Resolve-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [string[]]$FallbackPaths = @()
    )

    # Try Get-Command first
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    # Try fallback paths
    foreach ($path in ($FallbackPaths | Where-Object { $_ })) {
        $candidate = Join-Path $path $Name
        if (Test-Path $candidate) { return $candidate }
        if (Test-Path "$candidate.exe") { return "$candidate.exe" }
    }

    return $null
}
#endregion

#region PATH Management
function Add-UserPathOnce {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Segments
    )

    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User") -as [string]
    if (-not $currentPath) { $currentPath = "" }

    # Split and normalize existing paths
    $existingParts = ($currentPath -split ';') |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        ForEach-Object { $_.Trim() } |
        Select-Object -Unique

    # Use HashSet for efficient lookups
    $pathSet = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $existingParts | ForEach-Object { [void]$pathSet.Add($_) }

    # Add new segments
    $added = @()
    foreach ($segment in $Segments) {
        if ([string]::IsNullOrWhiteSpace($segment)) { continue }
        $normalized = $segment.TrimEnd('\')

        if (-not $pathSet.Contains($normalized)) {
            [void]$pathSet.Add($normalized)
            $added += $normalized
        }
    }

    if ($added.Count -gt 0) {
        $newPath = ($pathSet.ToArray() -join ';')
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")

        # Broadcast environment change
        $signature = @'
using System;
using System.Runtime.InteropServices;
public class EnvRefresh {
    [DllImport("user32.dll", SetLastError=true, CharSet=CharSet.Auto)]
    public static extern IntPtr SendMessageTimeout(
        IntPtr hWnd, int Msg, IntPtr wParam, string lParam,
        int fuFlags, int uTimeout, out IntPtr result);
}
'@
        try {
            Add-Type $signature -ErrorAction SilentlyContinue | Out-Null
            $HWND_BROADCAST = [IntPtr]0xffff
            $WM_SETTINGCHANGE = 0x1A
            $result = [IntPtr]::Zero
            [void][EnvRefresh]::SendMessageTimeout(
                $HWND_BROADCAST, $WM_SETTINGCHANGE,
                [IntPtr]::Zero, "Environment", 2, 5000, [ref]$result
            )
        } catch {
            Write-Warn "Could not broadcast environment change"
        }

        Write-OK "PATH updated: $($added -join '; ')"
    } else {
        Write-OK "PATH already contains all required entries"
    }
}
#endregion

#region Winget Package Management
function Ensure-Winget {
    $winget = Resolve-Command -Name "winget.exe"
    if (-not $winget) {
        Fail @"
winget is required but not found.

Install App Installer from Microsoft Store:
  https://apps.microsoft.com/store/detail/app-installer/9NBLGGH4NNS1

Or install via PowerShell:
  Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe
"@
    }
    Write-OK "winget found: $winget"
    return $winget
}

$WingetExe = Ensure-Winget

function Ensure-WingetPackage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Id,
        [ValidateSet('user', 'machine')]
        [string]$Scope = 'machine'
    )

    # Check if already installed
    $listOutput = & $WingetExe list --id $Id 2>&1 | Out-String
    if ($listOutput -match [regex]::Escape($Id)) {
        Write-OK "$Id already installed"
        return
    }

    Write-Info "Installing $Id via winget..."

    $args = @(
        'install', '-e'
        '--id', $Id
        '--scope', $Scope
        '--silent'
        '--accept-package-agreements'
        '--accept-source-agreements'
    )

    $process = Start-Process -FilePath $WingetExe -ArgumentList ($args -join ' ') -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -eq 0) {
        Write-OK "$Id installed successfully"
    } elseif ($process.ExitCode -eq -1978335189) {
        Write-OK "$Id already installed (winget reports no changes needed)"
    } else {
        Fail "winget failed installing $Id (exit code: $($process.ExitCode)). Try updating winget sources."
    }
}
#endregion

#region Python Installation
Write-Info "Installing Python 3.12..."
$scope = if ($isAdmin) { 'machine' } else { 'user' }
Ensure-WingetPackage -Id 'Python.Python.3.12' -Scope $scope

$pythonPaths = @(
    "$env:ProgramFiles\Python312\python.exe"
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
    "$env:USERPROFILE\AppData\Local\Programs\Python\Python312\python.exe"
)

# First try to find Python 3.12 specifically
$pythonExe = $null
foreach ($path in $pythonPaths) {
    if (Test-Path $path) {
        $pythonExe = $path
        break
    }
}

# If not found, try the fallback resolution but only if it's Python 3.12
if (-not $pythonExe) {
    $fallbackPython = Resolve-Command -Name "python.exe" -FallbackPaths ($pythonPaths | Split-Path -Parent)
    if ($fallbackPython) {
        $version = & $fallbackPython --version 2>&1 | Out-String
        if ($version -match "Python 3\.12") {
            $pythonExe = $fallbackPython
        }
    }
}

if (-not $pythonExe) {
    Fail "Python 3.12 not found after installation. Checked: $($pythonPaths -join ', ')"
}

Write-OK "Python found: $pythonExe"

# Install pipx
Write-Info "Installing pipx..."
$ErrorActionPreference = 'Continue'
try {
    & $pythonExe -m pip install --quiet --disable-pip-version-check --user pipx 2>&1 | Where-Object { $_ -notmatch "WARNING:" } | Out-Null
    & $pythonExe -m pipx ensurepath --force 2>&1 | Where-Object { $_ -notmatch "WARNING:" } | Out-Null
} catch {
    Write-Warn "pip warnings encountered but continuing: $($_.Exception.Message)"
}
$ErrorActionPreference = 'Stop'

# Check if pipx is available as a module (preferred method)
$ErrorActionPreference = 'Continue'
try {
    $pipxOutput = & $pythonExe -m pipx --version 2>&1
    $pipxVersion = $pipxOutput | Where-Object { $_ -match "\d+\.\d+\.\d+" } | Select-Object -First 1
    if ($pipxVersion) {
        $pipxExe = "$pythonExe -m pipx"
        Write-OK "pipx found as module: version $($pipxVersion.Trim())"
    } else {
        throw "pipx module not working"
    }
} catch {
    $pipxPaths = @(
        "$env:USERPROFILE\.local\bin"
        "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
        "$env:APPDATA\Python\Scripts"
    )

    $pipxExe = Resolve-Command -Name "pipx.exe" -FallbackPaths $pipxPaths
    if (-not $pipxExe) {
        Fail "pipx not found after installation. Checked: $($pipxPaths -join ', ')"
    }
    Write-OK "pipx found: $pipxExe"
}
$ErrorActionPreference = 'Stop'
#endregion

#region Node.js Installation
Write-Info "Installing Node.js LTS..."
Ensure-WingetPackage -Id 'OpenJS.NodeJS.LTS' -Scope $scope

$nodePaths = @(
    "$env:ProgramFiles\nodejs"
    "$env:LOCALAPPDATA\Programs\nodejs"
)

$nodeExe = Resolve-Command -Name "node.exe" -FallbackPaths $nodePaths
$npmExe = Resolve-Command -Name "npm.cmd" -FallbackPaths $nodePaths

if (-not $nodeExe -or -not $npmExe) {
    Fail "Node.js or npm not found after installation"
}

Write-OK "Node.js found: $nodeExe"
Write-OK "npm found: $npmExe"
#endregion

#region Aider Installation
Write-Info "Installing Aider..."

$aiderPaths = @(
    "$env:USERPROFILE\.local\bin"
    "$env:APPDATA\Python\Scripts"
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
    "$env:USERPROFILE\AppData\Local\pipx\venvs\aider-chat\Scripts"
)
$aiderExe = Resolve-Command -Name "aider.exe" -FallbackPaths $aiderPaths

if (-not $aiderExe) {
    $ErrorActionPreference = 'Continue'
    try {
        if ($pipxExe -like "*-m pipx") {
            # Use module form - need to handle the path with spaces properly
            $pythonPath = $pipxExe.Replace(" -m pipx", "")
            & $pythonPath -m pipx install aider-chat 2>&1 | Where-Object { $_ -notmatch "WARNING:" -and $_ -notmatch "Found a space" } | Out-Null
        } else {
            # Use executable form
            & $pipxExe install aider-chat 2>&1 | Where-Object { $_ -notmatch "WARNING:" } | Out-Null
        }
    } catch {
        Write-Warn "pipx warnings encountered but continuing: $($_.Exception.Message)"
    }
    $ErrorActionPreference = 'Stop'

    $aiderExe = Resolve-Command -Name "aider.exe" -FallbackPaths $aiderPaths

    if (-not $aiderExe) {
        Fail "Aider installation failed"
    }
}

Write-OK "Aider installed: $aiderExe"

# Configure Aider
if ($OpenAIKey) {
    $aiderConfig = Join-Path $env:USERPROFILE '.aider.conf.yml'
    $configContent = @"
# Aider Configuration
model: gpt-4
auto-commits: true
dark-mode: true

api_keys:
  openai: $OpenAIKey
"@
    $configContent | Set-Content -Path $aiderConfig -Encoding UTF8
    Write-OK "Aider configured with OpenAI key"
} else {
    Write-Warn "No OpenAI key provided. Aider will prompt for key when used."
}
#endregion

#region Gemini CLI Installation
Write-Info "Installing Gemini CLI..."

$geminiExe = Resolve-Command -Name "gemini.cmd" -FallbackPaths @("$env:APPDATA\npm")

if (-not $geminiExe) {
    & $npmExe install -g @google/gemini-cli --silent 2>&1 | Out-Null
    $geminiExe = Resolve-Command -Name "gemini.cmd" -FallbackPaths @("$env:APPDATA\npm")
}

if ($geminiExe) {
    Write-OK "Gemini CLI installed: $geminiExe"

    if ($GeminiKey) {
        $geminiConfigDir = Join-Path $env:USERPROFILE '.gemini'
        $null = New-Item -ItemType Directory -Force -Path $geminiConfigDir

        @{
            apiKey = $GeminiKey
        } | ConvertTo-Json | Set-Content -Path (Join-Path $geminiConfigDir 'config.json') -Encoding UTF8

        Write-OK "Gemini CLI configured with API key"
    } else {
        Write-Warn "No Gemini key provided. Run 'gemini auth login' to authenticate."
    }
} else {
    Write-Warn "Gemini CLI not found after installation"
}
#endregion

#region Ollama Installation
Write-Info "Installing Ollama..."
Ensure-WingetPackage -Id 'Ollama.Ollama' -Scope $scope

$ollamaPaths = @(
    "$env:LOCALAPPDATA\Programs\Ollama"
    "$env:ProgramFiles\Ollama"
)

$ollamaExe = Resolve-Command -Name "ollama.exe" -FallbackPaths $ollamaPaths
if (-not $ollamaExe) {
    Fail "Ollama not found after installation"
}

Write-OK "Ollama found: $ollamaExe"

# Start Ollama service
$ollamaService = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue

if ($ollamaService) {
    if ($ollamaService.Status -ne 'Running') {
        Write-Info "Starting Ollama service..."
        Start-Service -Name "Ollama"
        Start-Sleep -Seconds 2
    }
    Write-OK "Ollama service running"
} else {
    # Start as background process if no service
    if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
        Write-Info "Starting Ollama background process..."
        Start-Process -FilePath $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-OK "Ollama started"
    } else {
        Write-OK "Ollama already running"
    }
}

# Pull model
if (-not $SkipModelPull) {
    Write-Info "Checking for Ollama model: $OllamaModel"

    $modelList = & $ollamaExe list 2>&1 | Out-String
    $modelExists = $modelList -match [regex]::Escape($OllamaModel)

    if (-not $modelExists) {
        Write-Info "Pulling Ollama model: $OllamaModel (this may take several minutes)..."

        if ($PSCmdlet.ShouldProcess($OllamaModel, "Pull Ollama model")) {
            & $ollamaExe pull $OllamaModel

            $modelList = & $ollamaExe list 2>&1 | Out-String
            if ($modelList -match [regex]::Escape($OllamaModel)) {
                Write-OK "Model '$OllamaModel' downloaded successfully"
            } else {
                Write-Warn "Model pull completed but verification failed. Run 'ollama list' to check."
            }
        }
    } else {
        Write-OK "Model '$OllamaModel' already available"
    }
}
#endregion

#region Redis Installation
Write-Info "Installing Redis (Windows build)..."

function Get-LatestRedisRelease {
    try {
        $headers = @{ "User-Agent" = "ai-stack-installer/1.0" }
        $apiUrl = "https://api.github.com/repos/tporadowski/redis/releases/latest"

        $release = Invoke-RestMethod -Uri $apiUrl -Headers $headers -TimeoutSec 30
        $asset = $release.assets | Where-Object { $_.name -match 'x64.*\.zip$' } | Select-Object -First 1

        if (-not $asset) {
            throw "No x64 Windows build found in latest release"
        }

        return @{
            Name = $asset.name
            Url  = $asset.browser_download_url
            Size = $asset.size
        }
    } catch {
        Fail "Failed to fetch Redis release info: $($_.Exception.Message)"
    }
}

$redisRelease = Get-LatestRedisRelease
Write-Info "Downloading Redis: $($redisRelease.Name)"

$redisZip = Join-Path $env:TEMP $redisRelease.Name

try {
    $headers = @{ "User-Agent" = "ai-stack-installer/1.0" }

    # Use Invoke-WebRequest without -UseBasicParsing (PS7 compatibility)
    Invoke-WebRequest -Uri $redisRelease.Url -OutFile $redisZip -Headers $headers -TimeoutSec 300

    Write-OK "Redis downloaded: $redisZip"
} catch {
    Fail "Redis download failed: $($_.Exception.Message)"
}

# Extract Redis
if (Test-Path $RedisH) {
    try {
        Remove-Item $RedisH -Recurse -Force
    } catch {
        Write-Warn "Could not fully clean Redis directory"
    }
    $null = New-Item -ItemType Directory -Force -Path $RedisH
}

Expand-Archive -Path $redisZip -DestinationPath $RedisH -Force

# Find executables
$redisServer = Get-ChildItem -Path $RedisH -Recurse -Filter 'redis-server.exe' | Select-Object -First 1
$redisCli = Get-ChildItem -Path $RedisH -Recurse -Filter 'redis-cli.exe' | Select-Object -First 1

if (-not $redisServer) {
    Fail "redis-server.exe not found in extracted files"
}

Write-OK "Redis executables found"

# Create configuration
$redisConfig = Join-Path $RedisH 'redis.windows.conf'
$configContent = @"
# Redis Configuration for AI Stack
bind 127.0.0.1
protected-mode yes
port 6379
logfile "$($Logs -replace '\\','/')/redis.log"
dir "$($RedisH -replace '\\','/')"
save 900 1
save 300 10
save 60 10000
"@
$configContent | Set-Content -Path $redisConfig -Encoding ASCII

Write-OK "Redis configured: $redisConfig"

# Install as Windows service (requires admin) or run as process
if ($isAdmin) {
    $existingService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue

    if ($existingService) {
        Write-Info "Removing existing Redis service..."
        try {
            Stop-Service -Name "Redis" -Force -ErrorAction SilentlyContinue
        } catch {
            Write-Warn "Could not stop existing Redis service"
        }

        & $redisServer.FullName --service-uninstall 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }

    Write-Info "Installing Redis as Windows service..."
    & $redisServer.FullName --service-install $redisConfig --service-name Redis 2>&1 | Out-Null
    & $redisServer.FullName --service-start 2>&1 | Out-Null

    Start-Sleep -Seconds 3

    # Verify service
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue

    if ($redisService -and $redisService.Status -eq 'Running') {
        Write-OK "Redis service installed and running"
    } else {
        Write-Warn "Redis service installation failed, but Redis executable is available"
    }
} else {
    Write-Info "Starting Redis as background process (no admin privileges for service installation)..."
    if (-not (Get-Process -Name "redis-server" -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $redisServer.FullName -ArgumentList $redisConfig -WindowStyle Hidden
        Start-Sleep -Seconds 3

        if (Get-Process -Name "redis-server" -ErrorAction SilentlyContinue) {
            Write-OK "Redis started as background process"
        } else {
            Write-Warn "Redis failed to start as background process"
        }
    } else {
        Write-OK "Redis already running as process"
    }
}
#endregion

#region Management Scripts
Write-Info "Creating management scripts..."

# Startup script
$startupScript = Join-Path $Bin 'start-ai-stack.cmd'
$startupContent = @'
@echo off
echo ========================================
echo Starting AI Stack Services
echo ========================================
echo.

REM Start Redis service
sc query Redis | find "RUNNING" >nul
if errorlevel 1 (
    echo Starting Redis...
    net start Redis >nul 2>&1
)

REM Start Ollama (service or process)
sc query Ollama | find "RUNNING" >nul
if errorlevel 1 (
    tasklist | find "ollama.exe" >nul
    if errorlevel 1 (
        echo Starting Ollama...
        start "" ollama serve
    )
)

echo.
echo AI Stack Ready!
echo ========================================
'@
$startupContent | Set-Content -Path $startupScript -Encoding ASCII

# Status script
$statusScript = Join-Path $Bin 'status.cmd'
$statusContent = @'
@echo off
echo ========================================
echo AI Stack Status
echo ========================================
echo.

echo [Redis]
sc query Redis | find "STATE"
echo.

echo [Ollama]
sc query Ollama 2>nul | find "STATE"
if errorlevel 1 (
    tasklist | find "ollama.exe" >nul && echo Process: Running || echo Process: Not running
)
echo.

echo [Aider]
where aider >nul 2>&1 && (
    aider --version 2>nul
) || echo Not found in PATH
echo.

echo [Gemini CLI]
where gemini >nul 2>&1 && (
    gemini --version 2>nul
) || echo Not found in PATH
echo.

echo ========================================
'@
$statusContent | Set-Content -Path $statusScript -Encoding ASCII

Write-OK "Management scripts created in: $Bin"
#endregion

#region Environment Configuration
Write-Info "Saving environment configuration..."

$envFile = Join-Path $Secrets '.env'
$envContent = @"
# AI Stack Environment Configuration
# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

OPENAI_API_KEY=$OpenAIKey
GEMINI_API_KEY=$GeminiKey
OLLAMA_HOST=http://localhost:11434
REDIS_HOST=localhost
REDIS_PORT=6379
"@

$envContent | Set-Content -Path $envFile -Encoding UTF8

if (-not $OpenAIKey) {
    Write-Warn "OPENAI_API_KEY is empty in $envFile"
}
if (-not $GeminiKey) {
    Write-Warn "GEMINI_API_KEY is empty in $envFile"
}

Write-OK "Environment saved: $envFile"
#endregion

#region PATH Updates
Write-Info "Updating system PATH..."

$pathsToAdd = @(
    $Bin
    "$env:USERPROFILE\.local\bin"
    "$env:LOCALAPPDATA\Programs\Python\Python312"
    "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
    "$env:ProgramFiles\Ollama"
    "$env:LOCALAPPDATA\Programs\Ollama"
    (Split-Path -Parent $redisServer.FullName)
)

Add-UserPathOnce -Segments $pathsToAdd
#endregion

#region Final Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

Write-Host "Installed Components:" -ForegroundColor Cyan
Write-Host "  • Python:     $(& $pythonExe --version 2>&1)"
Write-Host "  • Node.js:    $(& $nodeExe --version 2>&1)"
Write-Host "  • Aider:      $aiderExe"
Write-Host "  • Gemini CLI: $(if ($geminiExe) { $geminiExe } else { 'Not installed' })"
Write-Host "  • Ollama:     $ollamaExe"
Write-Host "  • Redis:      $($redisServer.FullName)"
Write-Host ""

Write-Host "Active Services:" -ForegroundColor Cyan
$redisStatus = (Get-Service -Name "Redis" -ErrorAction SilentlyContinue).Status
Write-Host "  • Redis:      $redisStatus"

$ollamaStatus = if (Get-Service -Name "Ollama" -ErrorAction SilentlyContinue) {
    (Get-Service -Name "Ollama").Status
} elseif (Get-Process -Name "ollama" -ErrorAction SilentlyContinue) {
    "Running (process)"
} else {
    "Stopped"
}
Write-Host "  • Ollama:     $ollamaStatus"
Write-Host ""

Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  • Workspace:  $Root"
Write-Host "  • Secrets:    $envFile"
Write-Host "  • Logs:       $Logs"
Write-Host "  • Transcript: $transcriptPath"
Write-Host ""

Write-Host "Quick Start:" -ForegroundColor Cyan
Write-Host "  • Launch all: $startupScript"
Write-Host "  • Status:     $statusScript"
Write-Host "  • Use Aider:  Open new terminal → type 'aider'"
Write-Host "  • Use Ollama: ollama run $OllamaModel"
Write-Host ""

Write-Host "========================================" -ForegroundColor Magenta
Write-Host ""

# Stop transcript
try {
    Stop-Transcript | Out-Null
} catch { }

# Optional pause
if ($PauseOnExit) {
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}
#endregion
