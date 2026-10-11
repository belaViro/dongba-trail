param([switch]$Resume)
$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$python = Join-Path $workspace '.venv/Scripts/python.exe'
$entry = Join-Path $PSScriptRoot 'src/pipeline.py'
$run = Join-Path $PSScriptRoot 'checkpoints/cpu_v2'
$logs = Join-Path $PSScriptRoot 'logs'
if (Test-Path -LiteralPath (Join-Path $run 'STOP')) {
    throw 'STOP exists. Remove that file explicitly before resuming.'
}
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'reports/cpu_v2_sanity.json'))) {
    throw 'Run src/sanity.py first. It must pass before full training.'
}
New-Item -ItemType Directory -Path $logs -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$arguments = @('-X', 'utf8', '-u', ('"' + $entry + '"'))
if ($Resume) { $arguments += '--resume' }
$process = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $workspace -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logs "$stamp.stdout.log") -RedirectStandardError (Join-Path $logs "$stamp.stderr.log")
Write-Output "Started PID $($process.Id). Status: $run/status.json. Logs: $logs"
