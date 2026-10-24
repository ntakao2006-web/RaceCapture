$ErrorActionPreference='Stop'
$taskWatcher=Join-Path $PSScriptRoot 'Watch-EcoCapture-USB.ps1'
$taskStartup=Join-Path ([Environment]::GetFolderPath('Startup')) 'EcoCapture-Web USB.lnk'
$taskShell=New-Object -ComObject WScript.Shell
$taskShortcut=$taskShell.CreateShortcut($taskStartup)
$taskShortcut.TargetPath=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$taskShortcut.Arguments='-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "'+$taskWatcher+'"'
$taskShortcut.WorkingDirectory=$PSScriptRoot
$taskShortcut.WindowStyle=7
$taskShortcut.Description='UNO Q接続時にEcoCapture-Webを既定ブラウザで開く'
$taskShortcut.Save()
Start-Process -FilePath $taskShortcut.TargetPath -ArgumentList $taskShortcut.Arguments -WindowStyle Hidden
Write-Host 'USB自動起動を登録しました。Windowsログイン時にバックグラウンドで開始します。'
