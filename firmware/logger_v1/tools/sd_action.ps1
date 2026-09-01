param([ValidateSet('status','stop','eject','resume')][string]$Action = 'status')
$ErrorActionPreference = 'Stop'
$loggerPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$loggerDeps = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\v1_test\.tools'))
if (-not (Test-Path -LiteralPath $loggerPython)) { throw 'Python runtime not found.' }
$env:PYTHONPATH = $loggerDeps
& $loggerPython -X utf8 (Join-Path $PSScriptRoot 'sd_control.py') $Action
if ($LASTEXITCODE -ne 0) { throw 'Command failed. Do not remove SD without safeToRemove: true.' }
