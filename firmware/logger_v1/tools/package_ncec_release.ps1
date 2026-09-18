$ErrorActionPreference='Stop'
$firmwareRoot=Split-Path -Parent $PSScriptRoot
$repository=Split-Path -Parent (Split-Path -Parent $firmwareRoot)
$build=Join-Path $firmwareRoot '.pio/build/logger-v1'
$release=Join-Path $firmwareRoot 'artifacts/release_20260915_ncec'
New-Item -ItemType Directory -Force -Path $release | Out-Null
foreach($name in @('firmware.bin','bootloader.bin','partitions.bin')) {
    Copy-Item -LiteralPath (Join-Path $build $name) -Destination (Join-Path $release $name) -Force
}
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'flash_release.ps1') -Destination (Join-Path $release 'flash.ps1') -Force
Copy-Item -LiteralPath (Join-Path $repository 'EcoCapture/NCEC_V1.md') -Destination (Join-Path $release 'README.md') -Force
Copy-Item -LiteralPath (Join-Path $repository 'EcoCapture/licenses/opendbc-MIT.txt') -Destination $release -Force
$checks=foreach($name in @('firmware.bin','bootloader.bin','partitions.bin')) {
    (Get-FileHash -LiteralPath (Join-Path $release $name) -Algorithm SHA256).Hash.ToLowerInvariant()+'  '+$name
}
$checks | Set-Content -LiteralPath (Join-Path $release 'SHA256SUMS.txt') -Encoding ascii
$archive=Join-Path $firmwareRoot 'artifacts/logger-v1-ncec-20260915a.zip'
Compress-Archive -LiteralPath $release -DestinationPath $archive -Force
Get-FileHash -LiteralPath $archive -Algorithm SHA256
