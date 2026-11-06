# Put "EcoLogger Ver.2" on the desktop: opens ecologger_menu.py with pythonw (no console window).
# Run Make-Shortcut.cmd again after moving the repository or reinstalling Python.
$ErrorActionPreference = 'Stop'
$py = (Get-Command pythonw).Source
$dir = $PSScriptRoot
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'EcoLogger Ver.2.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$s.TargetPath = $py
$s.Arguments = '"' + (Join-Path $dir 'ecologger_menu.py') + '"'
$s.WorkingDirectory = $dir
$s.Description = 'EcoLogger Ver.2 (UNO Q) menu: status, video, screen, laps'
$s.Save()
Write-Host ('Created: ' + $lnk)
