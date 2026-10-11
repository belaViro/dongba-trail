$run = Join-Path $PSScriptRoot 'checkpoints/cpu_v2_threads8'
New-Item -ItemType Directory -Path $run -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $run 'STOP') -Force | Out-Null
Write-Output 'Stop requested for threads8 run. Inspect its status.json for stopped_resumable.'
