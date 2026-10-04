param([string]$Serial = '3263089125')

$ErrorActionPreference = 'Stop'
$adb = Join-Path $PSScriptRoot '..\other\uno_q_tools\platform-tools\adb.exe'
$state = & $adb -s $Serial get-state 2>$null
if ($LASTEXITCODE -ne 0 -or $state.Trim() -ne 'device') {
    throw 'UNO QのADB接続がありません。USBを抜き差しし、起動を待ってから再実行してください。'
}

& $adb -s $Serial forward tcp:8080 tcp:8080 | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'EcoCaptureへのUSB転送を開始できませんでした。' }

$base = 'http://127.0.0.1:8080'
$status = Invoke-RestMethod "$base/api/status" -TimeoutSec 5
if ($status.logging.active) {
    Invoke-RestMethod "$base/api/log/stop" -Method Post -TimeoutSec 10 | Out-Null
}

$config = Invoke-RestMethod "$base/api/config" -TimeoutSec 5
$signals = @($config.signals | Where-Object { $_.name -ne 'OilTemp' })
$signals += [pscustomobject]@{
    channel = 2
    name = 'OilTemp'
    unit = [char]0x00B0 + 'C'
    can_id = 0x600
    extended = $false
    byte_offset = 0
    data_type = 'int16'
    endian = 'little'
    scale = 0.01
    offset = 0.0
    bit_mask = $null
}
$config.signals = $signals
$body = $config | ConvertTo-Json -Depth 10
$result = Invoke-RestMethod "$base/api/config" -Method Post -ContentType 'application/json; charset=utf-8' -Body $body -TimeoutSec 10

Write-Host 'RaceCapture channel configured: OilTemp, CAN2, ID 0x600, int16 LE, 0.01 C/bit'
$result | ConvertTo-Json -Depth 10
