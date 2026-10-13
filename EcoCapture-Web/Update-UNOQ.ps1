param([string]$Serial='3263089125',[switch]$Firmware)
$ErrorActionPreference='Stop'
$taskTools=Join-Path $PSScriptRoot '..\other\uno_q_tools'
$taskAdb=Join-Path $taskTools 'platform-tools\adb.exe'
if(-not (Test-Path -LiteralPath $taskAdb)){
    # Fall back to adb on PATH or the Android SDK tools installed by the Claude app.
    $taskAdbCommand=Get-Command adb -ErrorAction SilentlyContinue
    if($taskAdbCommand){$taskAdb=$taskAdbCommand.Source}else{$taskAdb=Join-Path $env:LOCALAPPDATA 'AndroidSdkTools\platform-tools\adb.exe'}
}
New-Item -ItemType Directory -Force -Path $taskTools | Out-Null
function Invoke-CheckedAdb([string[]]$TaskArguments){& $taskAdb @TaskArguments;if($LASTEXITCODE -ne 0){throw 'UNO Qとの通信・更新に失敗しました。USB接続を確認してください。'}}
$taskState=& $taskAdb -s $Serial get-state 2>$null
if($LASTEXITCODE -ne 0 -or $taskState.Trim() -ne 'device'){throw 'UNO QがUSBで接続されていません。USBを抜き差しし、起動を待ってください。'}
Invoke-CheckedAdb @('-s',$Serial,'forward','tcp:8080','tcp:8080')
$taskStatus=$null
try{$taskStatus=Invoke-RestMethod http://127.0.0.1:8080/api/status -TimeoutSec 4}catch{}
if($taskStatus.logging.active){throw '更新前に記録を停止してください。'}
$taskBinary=Join-Path $taskTools 'cloudflared-linux-arm64'
if(-not (Test-Path -LiteralPath $taskBinary)){
    Invoke-WebRequest 'https://github.com/cloudflare/cloudflared/releases/download/2026.8.3/cloudflared-linux-arm64' -OutFile $taskBinary
}
if((Get-FileHash -LiteralPath $taskBinary -Algorithm SHA256).Hash.ToLowerInvariant() -ne '4bcfd35521a7cbc545ebfd5d57334a71ee180e2a64874981f374c81472118391'){throw 'Cloudflaredの検証に失敗しました。'}
$taskTar=Join-Path $taskTools 'ecocapture-device-update.tar'
tar -cf $taskTar --exclude=build --exclude=artifacts --exclude=__pycache__ -C $PSScriptRoot .
if($LASTEXITCODE -ne 0){throw '更新ファイルを作成できませんでした。'}
Invoke-CheckedAdb @('-s',$Serial,'push',$taskTar,'/tmp/ecocapture-device-update.tar')
Invoke-CheckedAdb @('-s',$Serial,'push',$taskBinary,'/home/arduino/ecocapture-cloudflared')
Invoke-CheckedAdb @('-s',$Serial,'shell','tar -xf /tmp/ecocapture-device-update.tar -C /home/arduino/EcoCapture-Web')
# Reload an already-running supervisor so it uses the shared maintenance lock.
# Preserve an intentionally stopped/disabled service.
Invoke-CheckedAdb @('-s',$Serial,'shell','docker run --rm --privileged --pid=host --user 0 --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 -t 1 -m -p -- /bin/sh -c "if systemctl is-active --quiet ecocapture-mcu-supervisor; then timeout 25 systemctl restart ecocapture-mcu-supervisor; fi"')
Invoke-CheckedAdb @('-s',$Serial,'shell','sh /home/arduino/EcoCapture-Web/install-device-agent.sh && sh /home/arduino/EcoCapture-Web/deploy.sh')
if($Firmware){
    # Preserve the device-side source before replacing a potentially different version.
    $taskSourceStamp=Get-Date -Format 'yyyyMMdd_HHmmss'
    $taskSourceBackup="/home/arduino/ecologger-source-backups/ecologger_v2_$taskSourceStamp.tar"
    $taskLocalSourceBackup=Join-Path $taskTools "source-backups\ecologger_v2_$taskSourceStamp.tar"
    New-Item -ItemType Directory -Force -Path (Split-Path $taskLocalSourceBackup) | Out-Null
    Invoke-CheckedAdb @('-s',$Serial,'shell',"mkdir -p /home/arduino/ecologger-source-backups && tar -cf $taskSourceBackup -C /home/arduino ecologger_v2")
    Invoke-CheckedAdb @('-s',$Serial,'pull',$taskSourceBackup,$taskLocalSourceBackup)
    $taskFirmware=Join-Path $PSScriptRoot '..\firmware\ecologger_v2'
    $taskFirmwareTar=Join-Path $taskTools 'ecologger-firmware-update.tar'
    tar -cf $taskFirmwareTar -C $taskFirmware .
    if($LASTEXITCODE -ne 0){throw 'ファームの転送準備に失敗しました。'}
    Invoke-CheckedAdb @('-s',$Serial,'push',$taskFirmwareTar,'/tmp/ecologger-firmware-update.tar')
    Invoke-CheckedAdb @('-s',$Serial,'shell','mkdir -p /home/arduino/ecologger_v2 && tar -xf /tmp/ecologger-firmware-update.tar -C /home/arduino/ecologger_v2 && sh /home/arduino/EcoCapture-Web/build-mcu.sh')
}
Invoke-CheckedAdb @('-s',$Serial,'shell','docker run --rm --privileged --pid=host --user 0 --entrypoint /usr/bin/nsenter ecocapture-web:0.2.0 -t 1 -m -p -- /bin/sh /home/arduino/EcoCapture-Web/install-boot.sh')

Write-Host 'UNO Qの管理画面と閲覧専用サイトを更新しました。'
