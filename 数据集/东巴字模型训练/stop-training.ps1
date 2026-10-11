$run = Join-Path $PSScriptRoot 'checkpoints/cpu_v2'
New-Item -ItemType Directory -Path $run -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $run 'STOP') -Force | Out-Null
Write-Output 'Stop requested. Trainer checkpoints after a batch; validation finishes first if already running. Inspect status.json.'
