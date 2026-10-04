$ErrorActionPreference='Stop'
$taskWatcher=Join-Path $PSScriptRoot 'Watch-RaceCapture-USB.ps1'
$taskStartup=Join-Path ([Environment]::GetFolderPath('Startup')) 'RaceCapture LoggerV2 USB.lnk'
$taskShell=New-Object -ComObject WScript.Shell
$taskShortcut=$taskShell.CreateShortcut($taskStartup)
$taskShortcut.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskShortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$taskWatcher+'"'
$taskShortcut.WorkingDirectory=$PSScriptRoot
$taskShortcut.WindowStyle=7
$taskShortcut.Description='LoggerV2接続時にUNO Q上のRaceCaptureをブラウザで表示'
$taskShortcut.Save()
Start-Process -FilePath $taskShortcut.TargetPath -ArgumentList $taskShortcut.Arguments -WindowStyle Hidden
