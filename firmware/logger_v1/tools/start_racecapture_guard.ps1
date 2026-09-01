param([int]$AttachPid = 0)
$ErrorActionPreference = 'Stop'
$loggerPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $loggerPython)) { throw 'Python runtime not found. Run racecapture_guard.py with Python 3.' }
$loggerScript = Join-Path $PSScriptRoot 'racecapture_guard.py'
$loggerLog = Join-Path $PSScriptRoot '..\artifacts\racecapture_guard.jsonl'
$loggerArgs = '-X utf8 "{0}" --log "{1}"' -f $loggerScript,$loggerLog
if ($AttachPid -eq 0) {
    $loggerApps = @(Get-Process racecapture -ErrorAction SilentlyContinue)
    if ($loggerApps.Count -gt 1) { throw 'Close duplicate RaceCapture instances first.' }
    if ($loggerApps.Count -eq 1) { $AttachPid = $loggerApps[0].Id }
}
if ($AttachPid -gt 0) { $loggerArgs += ' --pid {0}' -f $AttachPid }
Start-Process -FilePath $loggerPython -ArgumentList $loggerArgs -WindowStyle Hidden
