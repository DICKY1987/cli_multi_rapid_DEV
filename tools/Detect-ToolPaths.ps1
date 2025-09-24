[CmdletBinding()]
param(
  [switch]$CreateWrappers = $true,
  [string]$AdaptersYaml = "config/tool_adapters.yaml",
  [string]$BinDir = "bin",
  [string[]]$Tools
)
$ErrorActionPreference = "Stop"
function Resolve-Exe { param([string]$Name)
  $p = (Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1).Path
  if ($p) { return (Resolve-Path $p).Path }
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Claude\claude.exe",
    "$env:APPDATA\npm\$Name.cmd",
    "$env:USERPROFILE\.local\bin\$Name.exe",
    "$env:USERPROFILE\.local\bin\$Name",
    "$env:ProgramFiles\$Name\$Name.exe",
    "$env:ProgramFiles\Git\cmd\git.exe",
    "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe",
    "$env:LOCALAPPDATA\Programs\Microsoft VS Code\bin\code.cmd",
    "$env:USERPROFILE\scoop\shims\$Name.exe",
    "$env:ChocolateyInstall\bin\$Name.exe",
    "$env:ChocolateyInstall\bin\$Name.cmd"
  ) | Where-Object { $_ -and (Test-Path $_) }
  if ($candidates) { return (Resolve-Path ($candidates | Select-Object -First 1)).Path }
  return $null }
$map = @{}
foreach ($t in $Tools) {
  try {
    $result = Resolve-Exe -Name $t
    $map[$t] = if ($result) { $result } else { "" }
  } catch {
    $map[$t] = ""
  }
}
New-Item -ItemType Directory -Force -Path (Split-Path $AdaptersYaml) | Out-Null
$yaml = @()
$yaml += "paths:"
foreach ($k in ($map.Keys | Sort-Object)) {
  $v = $map[$k]
  if ($v) { $yaml += "  ${k}: `"$v`"" } else { $yaml += "  ${k}: `"`"  # NOT FOUND" }
}
$yamlText = ($yaml -join "`r`n")
$yamlText | Out-File -Encoding utf8 -FilePath $AdaptersYaml
if ($CreateWrappers) {
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
  foreach ($k in $map.Keys) {
    $v = $map[$k]
    $wrapper = Join-Path $BinDir ("$k.cmd")
    if ($v) { "@echo off`r`n`"$v`" %*" | Out-File -Encoding ascii -FilePath $wrapper -Force }
    else { "@echo off`r`necho [$k] not found. Configure in $AdaptersYaml`r`nexit /b 1" | Out-File -Encoding ascii -FilePath $wrapper -Force }
  }
}
$rows = $map.GetEnumerator() | ForEach-Object {
  [pscustomobject]@{
    Tool = $_.Key;
    Path = if ($_.Value) { $_.Value } else { "<NOT FOUND>" }
  }
}
$rows | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 "artifacts/tool_paths_raw.json"
