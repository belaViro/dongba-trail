$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $workspace '.venv/Scripts/python.exe'
$entry = Join-Path $PSScriptRoot 'tools/thread8_pipeline.py'
$run = Join-Path $PSScriptRoot 'checkpoints/cpu_v2_threads8'
$logs = Join-Path $PSScriptRoot 'logs'
if (Test-Path -LiteralPath (Join-Path $run 'STOP')) {
    throw 'STOP exists. Remove that exact file explicitly before resuming.'
}
if (-not (Test-Path -LiteralPath (Join-Path $run 'migration.json'))) {
    throw 'Approved migration record is missing.'
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$process = Start-Process -FilePath $python -ArgumentList @('-X', 'utf8', '-u', ('"' + $entry + '"')) -WorkingDirectory $workspace -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "$stamp.threads8.stdout.log") -RedirectStandardError (Join-Path $logs "$stamp.threads8.stderr.log")
Write-Output "Started PID $($process.Id). Status: $run/status.json. Logs: $logs"
