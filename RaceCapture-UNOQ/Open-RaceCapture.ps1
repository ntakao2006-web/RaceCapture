param([string]$Serial='3263089125')
$ErrorActionPreference='Stop'
$taskAdb=Join-Path $PSScriptRoot '..\other\uno_q_tools\platform-tools\adb.exe'
& $taskAdb -s $Serial forward tcp:6080 tcp:6080
if($LASTEXITCODE -ne 0){throw 'LoggerV2のUSB接続と起動を確認してください。'}
& $taskAdb -s $Serial forward tcp:8080 tcp:8080
if($LASTEXITCODE -ne 0){throw 'LoggerV2設定画面へのUSB転送に失敗しました。'}
$null=Invoke-WebRequest 'http://127.0.0.1:6080/' -UseBasicParsing -TimeoutSec 10
Start-Process 'http://127.0.0.1:6080/'
