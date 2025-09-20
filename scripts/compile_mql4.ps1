# MQL4 Compilation Script for CI/CD Pipeline
# Compiles MQL4 files using MetaEditor or validates structure

param(
    [Parameter(Mandatory=$false)]
    [string]$SourcePath = "P_mql4",

    [Parameter(Mandatory=$false)]
    [string]$OutputPath = "artifacts/mql4",

    [Parameter(Mandatory=$false)]
    [switch]$ValidateOnly = $false
)

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Test-MQL4Structure {
    param([string]$FilePath)

    $content = Get-Content $FilePath -Raw
    $issues = @()

    # Check for basic MQL4 structure
    if (-not ($content -match "//\+------------------------------------------------------------------\+|//\s*Expert\s*Advisor|//\s*Indicator|//\s*Script")) {
        $issues += "Missing standard MQL4 header comment"
    }

    # Check for required includes
    if ($content -match "#include") {
        Write-Log "Found includes in $FilePath" "DEBUG"
    }

    # Check for main functions
    $hasTick = $content -match "OnTick\s*\("
    $hasInit = $content -match "OnInit\s*\("
    $hasDeinit = $content -match "OnDeinit\s*\("
    $hasStart = $content -match "start\s*\("

    if (-not ($hasTick -or $hasStart)) {
        $issues += "Missing main execution function (OnTick or start)"
    }

    # Check for syntax issues
    $openBraces = ($content | Select-String "\{" -AllMatches).Matches.Count
    $closeBraces = ($content | Select-String "\}" -AllMatches).Matches.Count
    if ($openBraces -ne $closeBraces) {
        $issues += "Mismatched braces: $openBraces open, $closeBraces close"
    }

    return @{
        IsValid = $issues.Count -eq 0
        Issues = $issues
        HasTick = $hasTick
        HasInit = $hasInit
        HasDeinit = $hasDeinit
        HasStart = $hasStart
    }
}

function Compile-MQL4File {
    param([string]$FilePath, [string]$OutputDir)

    $fileName = [System.IO.Path]::GetFileNameWithoutExtension($FilePath)
    $outputFile = Join-Path $OutputDir "$fileName.ex4"

    # Check if MetaEditor is available
    $metaEditor = Get-Command "MetaEditor64.exe" -ErrorAction SilentlyContinue
    if (-not $metaEditor) {
        $metaEditor = Get-Command "MetaEditor.exe" -ErrorAction SilentlyContinue
    }

    if ($metaEditor) {
        Write-Log "Compiling $FilePath with MetaEditor"
        $result = & $metaEditor.Source /compile:$FilePath /log

        if ($LASTEXITCODE -eq 0 -and (Test-Path $outputFile)) {
            Write-Log "Successfully compiled $fileName"
            return @{
                Success = $true
                OutputFile = $outputFile
                Message = "Compilation successful"
            }
        } else {
            Write-Log "Compilation failed for $fileName" "ERROR"
            return @{
                Success = $false
                OutputFile = $null
                Message = "Compilation failed with exit code $LASTEXITCODE"
            }
        }
    } else {
        Write-Log "MetaEditor not found, skipping compilation" "WARN"
        return @{
            Success = $false
            OutputFile = $null
            Message = "MetaEditor not available"
        }
    }
}

# Main execution
Write-Log "Starting MQL4 compilation process"
Write-Log "Source path: $SourcePath"
Write-Log "Output path: $OutputPath"
Write-Log "Validate only: $ValidateOnly"

# Create output directory
if (-not (Test-Path $OutputPath)) {
    New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
    Write-Log "Created output directory: $OutputPath"
}

# Find MQL4 files
$mql4Files = Get-ChildItem -Path $SourcePath -Filter "*.mq4" -Recurse

if ($mql4Files.Count -eq 0) {
    Write-Log "No MQL4 files found in $SourcePath" "WARN"
    exit 0
}

Write-Log "Found $($mql4Files.Count) MQL4 files to process"

$results = @()
$totalSuccess = 0
$totalFailed = 0

foreach ($file in $mql4Files) {
    Write-Log "Processing: $($file.Name)"

    # Validate structure
    $validation = Test-MQL4Structure $file.FullName

    $result = @{
        File = $file.Name
        Path = $file.FullName
        RelativePath = $file.FullName.Replace("$PWD\", "")
        Validation = $validation
        Compilation = $null
    }

    if ($validation.IsValid) {
        Write-Log "Validation passed for $($file.Name)"

        if (-not $ValidateOnly) {
            $compilation = Compile-MQL4File $file.FullName $OutputPath
            $result.Compilation = $compilation

            if ($compilation.Success) {
                $totalSuccess++
            } else {
                $totalFailed++
            }
        }
    } else {
        Write-Log "Validation failed for $($file.Name):" "ERROR"
        foreach ($issue in $validation.Issues) {
            Write-Log "  - $issue" "ERROR"
        }
        $totalFailed++
    }

    $results += $result
}

# Generate report
$report = @{
    Timestamp = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    SourcePath = $SourcePath
    OutputPath = $OutputPath
    ValidateOnly = $ValidateOnly
    TotalFiles = $mql4Files.Count
    TotalSuccess = $totalSuccess
    TotalFailed = $totalFailed
    Results = $results
}

$reportPath = Join-Path $OutputPath "compilation-report.json"
$report | ConvertTo-Json -Depth 10 | Out-File -FilePath $reportPath -Encoding UTF8

Write-Log "Generated compilation report: $reportPath"

# Summary
Write-Log "=== MQL4 Compilation Summary ==="
Write-Log "Total files processed: $($mql4Files.Count)"
Write-Log "Successful: $totalSuccess"
Write-Log "Failed: $totalFailed"

if ($totalFailed -gt 0) {
    Write-Log "Some files failed processing" "ERROR"
    exit 1
} else {
    Write-Log "All files processed successfully"
    exit 0
}