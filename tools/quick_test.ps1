$ErrorActionPreference = 'Continue'
$tools = @('claude','aider','gh','openai','code','git','docker','node','python')
$rep = @()

foreach($t in $tools) {
    $w = Join-Path 'bin' ($t + '.cmd')
    $found = Test-Path $w
    $out = ''

    if($found) {
        try {
            $job = Start-Job -ScriptBlock { param($wrapper) & $wrapper --version 2>&1 | Out-String } -ArgumentList $w
            $out = Wait-Job $job -Timeout 10 | Receive-Job
            Remove-Job $job -Force
            if (!$out) { $out = "Timeout after 10s" }
        } catch {
            $out = "Error: " + $_.Exception.Message
        }
    } else {
        $out = "Wrapper not found"
    }

    $rep += [pscustomobject]@{
        tool = $t
        wrapper = $found
        output = $out.ToString().Trim()
    }
    Write-Host "Tested $t : $($out.ToString().Trim().Split([Environment]::NewLine)[0])"
}

$rep | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 'artifacts/tool_wiring_report.json'
