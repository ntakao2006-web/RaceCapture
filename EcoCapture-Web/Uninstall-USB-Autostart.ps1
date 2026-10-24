$ErrorActionPreference='Stop'
$taskStartup=Join-Path ([Environment]::GetFolderPath('Startup')) 'EcoCapture-Web USB.lnk'
if(Test-Path -LiteralPath $taskStartup){Remove-Item -LiteralPath $taskStartup}
$taskWatcher=Join-Path $PSScriptRoot 'Watch-EcoCapture-USB.ps1'
Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'powershell.exe' -and $_.CommandLine -like ('*"'+$taskWatcher+'"*')} | ForEach-Object {Stop-Process -Id $_.ProcessId}
Write-Host 'USB自動起動を解除しました。'
