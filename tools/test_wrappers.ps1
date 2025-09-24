$ErrorActionPreference = 'Continue'
$tools = @('claude','aider','gh','openai','code','git','docker','pnpm','node','python','git-lfs','jq','yq','markdownlint','yamllint','detect-secrets','gitleaks')
$rep = @()

foreach($t in $tools) {
    $w = Join-Path 'bin' ($t + '.cmd')
    $found = Test-Path $w
    $out = ''

    if($found) {
        try {
            $out = & $w --version 2>&1 | Out-String
        } catch {
            $out = $_.ToString()
        }
    }

    $rep += [pscustomobject]@{
        tool = $t
        wrapper = $found
        output = $out.Trim()
    }
}

$rep | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 'artifacts/tool_wiring_report.json'
