param([string]$Serial = '3263089125', [int]$Port = 8080)
$ErrorActionPreference = 'Stop'
$taskAdb = Join-Path $PSScriptRoot '..\other\uno_q_tools\platform-tools\adb.exe'
if (-not (Test-Path -LiteralPath $taskAdb)) {
    $taskAdb = (Get-Command adb -ErrorAction Stop).Source
}
$taskState=& $taskAdb -s $Serial get-state 2>$null
if($LASTEXITCODE -ne 0 -or "$taskState".Trim() -ne 'device'){
    $taskUsb=Get-PnpDevice -PresentOnly -InstanceId "USB\VID_2341&PID_0078\$Serial" -ErrorAction SilentlyContinue
    if($taskUsb){
        & $taskAdb kill-server
        & $taskAdb start-server
        $taskState=& $taskAdb -s $Serial get-state 2>$null
    }
    if($LASTEXITCODE -ne 0 -or "$taskState".Trim() -ne 'device'){throw 'UNO QのUSB接続を確認してください。'}
}
& $taskAdb -s $Serial forward "tcp:$Port" tcp:8080
if ($LASTEXITCODE -ne 0) { throw 'USBポート転送を設定できませんでした。' }
$taskUrl = "http://127.0.0.1:$Port/"
$taskStatus = Invoke-RestMethod "${taskUrl}api/status" -TimeoutSec 10
Write-Host "EcoLogger V2 / MCU connected: $($taskStatus.connected) / Source: $($taskStatus.source)"
Start-Process $taskUrl
