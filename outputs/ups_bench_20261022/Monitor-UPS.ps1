$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$taskAdb = Join-Path $PSScriptRoot '../../other/uno_q_tools/platform-tools/adb.exe'
$taskLog = Join-Path $PSScriptRoot 'monitor.jsonl'
function Write-Sample($value) {
    $value | ConvertTo-Json -Compress | Add-Content -LiteralPath $taskLog -Encoding UTF8
}
Write-Sample @{time=[DateTimeOffset]::Now.ToString('o'); event='START'; address='192.168.10.128'; interval_seconds=1}
$taskRemote = 'i=0; while [ $i -lt 1800 ]; do echo $(cat /proc/sys/kernel/random/boot_id) $(cat /proc/uptime); i=$((i+1)); sleep 1; done'
$ErrorActionPreference = 'Continue'
& ssh -i "$PSScriptRoot/wifi_key" -o IdentitiesOnly=yes -o "UserKnownHostsFile=$PSScriptRoot/known_hosts" -o StrictHostKeyChecking=yes -o BatchMode=yes -o ConnectTimeout=4 -o ServerAliveInterval=2 -o ServerAliveCountMax=2 arduino@192.168.10.128 $taskRemote 2> "$PSScriptRoot/ssh_stderr.log" | ForEach-Object {
    $taskParts = $_.Trim() -split '\s+'
    $taskUsb = (& $taskAdb devices 2>$null) -match '^3263089125\s+device'
    Write-Sample @{time=[DateTimeOffset]::Now.ToString('o'); event='SAMPLE'; boot_id=$taskParts[0]; uptime_seconds=$taskParts[1]; usb_connected=[bool]$taskUsb}
}
Write-Sample @{time=[DateTimeOffset]::Now.ToString('o'); event='WIFI_STREAM_ENDED'; exit_code=$LASTEXITCODE}
