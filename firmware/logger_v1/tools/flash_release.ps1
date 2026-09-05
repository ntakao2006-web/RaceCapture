param(
    [Parameter(Mandatory=$true)][ValidatePattern('^COM[1-9][0-9]*$')][string]$Port,
    [string]$Python='python',
    [switch]$ConfirmVehicleDisconnected,
    [switch]$ConfirmSdClosed
)
$ErrorActionPreference='Stop'
if(-not $ConfirmVehicleDisconnected -or -not $ConfirmSdClosed) {
    throw 'Disconnect vehicle OBD and safely close SD first. Both confirmation switches are required.'
}
$releaseDirectory=$PSScriptRoot
$hashes=Get-Content -LiteralPath (Join-Path $releaseDirectory 'SHA256SUMS.txt')
foreach($name in @('bootloader.bin','partitions.bin','firmware.bin')) {
    $entry=$hashes | Where-Object { $_ -match ('^[a-fA-F0-9]{64}  '+[regex]::Escape($name)+'$') }
    if(@($entry).Count -ne 1) { throw "Missing or ambiguous checksum: $name" }
    $actual=(Get-FileHash -LiteralPath (Join-Path $releaseDirectory $name) -Algorithm SHA256).Hash
    if($actual -ne $entry.Substring(0,64)) { throw "Checksum mismatch: $name" }
}
& $Python -m esptool version
if($LASTEXITCODE -ne 0) { throw 'Python with esptool is required: python -m pip install esptool==4.11.0' }
# Existing logger_v1 partition layout only. Never erase_flash or overwrite NVS.
& $Python -m esptool --chip esp32s3 --port $Port --baud 115200 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_freq 80m --flash_size 16MB 0x0 (Join-Path $releaseDirectory 'bootloader.bin') 0x8000 (Join-Path $releaseDirectory 'partitions.bin') 0x10000 (Join-Path $releaseDirectory 'firmware.bin')
if($LASTEXITCODE -ne 0) { throw 'Programming/verification failed. Do not connect to the vehicle until checked.' }
Write-Output 'Programming completed. This is not a vehicle test. Check getVer and saved OBD acquisition state before connecting.'
