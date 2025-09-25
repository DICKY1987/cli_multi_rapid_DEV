#!/usr/bin/env pwsh
param(
  [ValidateSet("json","files")] [string]$io_mode = "json",
  [string]$io_in = "-",
  [string]$io_out = "-",
  [string]$io_events = "stdout",
  [string]$io_artifacts_dir = ".apf/run"
)

$IO_VERSION = "io.v1"
function Emit-Event([string]$id, [string]$type, [string]$message, $data=$null, [string]$step=$null){
  $evt = @{ version=$IO_VERSION; id=$id; type=$type; ts=(Get-Date).ToUniversalTime().ToString("s") + "Z"; message=$message }
  if ($null -ne $data) { $evt.data = $data }
  if ($null -ne $step) { $evt.step = $step }
  "##io_event " + ($evt | ConvertTo-Json -Compress)
}

# Read input
if ($io_in -eq "-") { $raw = [Console]::In.ReadToEnd() } else { $raw = Get-Content -Raw -Path $io_in }
try { $req = $raw | ConvertFrom-Json } catch {
  $resp = @{ version=$IO_VERSION; id=[guid]::NewGuid().ToString(); status="error"; exit_code=30; errors=@(@{code="bad_input"; message="Invalid JSON"}) }
  if ($io_out -eq "-") { $resp | ConvertTo-Json -Compress } else { $resp | ConvertTo-Json -Compress | Set-Content -Path $io_out -Encoding UTF8 }
  exit 30
}

$run_id = if ($req.id) { $req.id } else { [guid]::NewGuid().ToString() }
if ($req.version -ne $IO_VERSION) {
  Emit-Event $run_id "error" "Protocol version mismatch" @{ expected=$IO_VERSION; got=$($req.version) } | Write-Output
  $resp = @{ version=$IO_VERSION; id=$run_id; status="error"; exit_code=20; errors=@(@{code="version_mismatch"; message="Unsupported version"}) }
  if ($io_out -eq "-") { $resp | ConvertTo-Json -Compress } else { $resp | ConvertTo-Json -Compress | Set-Content -Path $io_out -Encoding UTF8 }
  exit 20
}

Emit-Event $run_id "progress" "Starting task" $null "init" | Write-Output

$resp = @{
  version=$IO_VERSION; id=$run_id; status="ok"; exit_code=0;
  outputs=@{ report=@{ summary="No-op adapter example"; changes=0 }; patches=@() };
  metrics=@{ duration_ms=0 }
}

if ($io_out -eq "-") { $resp | ConvertTo-Json -Compress } else { $resp | ConvertTo-Json -Compress | Set-Content -Path $io_out -Encoding UTF8 }
exit 0
