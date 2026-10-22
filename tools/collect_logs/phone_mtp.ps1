# Copy the Android logger's CSVs (Download\EcoLogger) from every phone connected over USB "File transfer" (MTP).
# MTP devices have no drive letter, so this goes through the Explorer shell. Output: <Dest>\<device name>\EL_*.csv
param([Parameter(Mandatory)][string]$Dest)
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject Shell.Application
$thisPc = $shell.NameSpace(17)

function Find-Child($folder, [string[]]$names) {
    foreach ($item in $folder.Items()) {
        if ($item.IsFolder -and $names -contains $item.Name) { return $item.GetFolder }
    }
    return $null
}

$found = 0
foreach ($device in $thisPc.Items()) {
    if ($device.IsFileSystem -or -not $device.IsFolder) { continue }  # ordinary drives are handled by the Python side
    foreach ($storage in $device.GetFolder.Items()) {
        if (-not $storage.IsFolder) { continue }
        $download = Find-Child $storage.GetFolder @('Download', 'Downloads')
        if (-not $download) { continue }
        $logs = Find-Child $download @('EcoLogger')
        if (-not $logs) { continue }
        $files = @($logs.Items() | Where-Object { -not $_.IsFolder -and $_.Name -like 'EL_*.csv' })
        Write-Output "PHONE $($device.Name) $($files.Count)"
        if (-not $files.Count) { continue }
        $target = Join-Path $Dest ($device.Name -replace '[\\/:*?"<>|]', '_')
        New-Item -ItemType Directory -Force $target | Out-Null
        $targetFolder = $shell.NameSpace($target)
        foreach ($file in $files) {
            # 4: no progress dialog, 16: yes to all, 1024: no error dialog. CopyHere returns before the copy ends.
            $targetFolder.CopyHere($file, 4 + 16 + 1024)
            $path = Join-Path $target $file.Name
            $deadline = (Get-Date).AddSeconds(300)
            while ((Get-Date) -lt $deadline) {
                if ((Test-Path $path) -and (Get-Item $path).Length -ge $file.Size) { break }
                Start-Sleep -Milliseconds 200
            }
            if (-not (Test-Path $path)) { Write-Output "FAILED $($file.Name)" } else { $found++ }
        }
    }
}
Write-Output "DONE $found"
