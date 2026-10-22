param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Cmsis', 'Mplab')]
    [string]$Mode,
    [switch]$CheckOnly
)

$ErrorActionPreference = 'Stop'
$pythonCandidates = @(
    'C:\Users\lintaroh\AppData\Local\Microchip\snap-uart-tools\Scripts\python.exe',
    'C:\Users\lintaroh\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\Microchip\snap-uart-tools\Scripts\python.exe'
)
$pythonExe = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $pythonExe) { throw 'Microchip pycmsisdapswitcher environment not found.' }

$images = @{
    Cmsis = @{
        Name = 'snap_app_cmsis-dap.hex'
        Hash = 'FA6A5984576E56E3B76AF23DA4602DF4B4A4C67583921F7F5B26B34660E3A5ED'
        Type = 'cmsis'
        Expected = 'cmsisv2'
    }
    Mplab = @{
        Name = 'snap_app.hex'
        Hash = '73A845EDB45D5CFE8417A16CEA27FF1C9719818D1183E78D84058753170C5B04'
        Type = 'mplab'
        Expected = 'mplab'
    }
}
$image = $images[$Mode]
$firmware = Join-Path $PSScriptRoot ('firmware\' + $image.Name)
if ((Get-FileHash -LiteralPath $firmware -Algorithm SHA256).Hash -ne $image.Hash) {
    throw 'Firmware hash does not match the saved official Snap_TP 3.0.1942 image.'
}

$previousEncoding = $env:PYTHONIOENCODING
try {
    $env:PYTHONIOENCODING = 'utf-8'
    $preflight = @'
from pycmsisdapswitcher.switcher_main import _get_libusb1_backend, _find_device
target, device, firmware = _find_device(_get_libusb1_backend(), False)
assert target == 'snap' and device.serial_number == '021038102RYN014624', 'Unexpected debugger; no write performed'
print('Verified:', target, device.serial_number, firmware)
'@
    & $pythonExe -c $preflight
    if ($LASTEXITCODE -ne 0) { throw 'Snap identity check failed; no write performed.' }
    if ($CheckOnly) {
        Write-Output "Check passed. Selected firmware: $Mode. No write performed."
        return
    }

    $logPath = Join-Path $PSScriptRoot ('switch_' + $Mode.ToLowerInvariant() + '_' + (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '.log')
    & $pythonExe -m pycmsisdapswitcher --action switch --target snap --fwtype $image.Type --appsource $firmware --verbose info 2>&1 | Tee-Object -FilePath $logPath
    if ($LASTEXITCODE -ne 0) { throw "Firmware switch failed. See $logPath" }

    $postflight = @'
import sys
from pycmsisdapswitcher.switcher_main import _get_libusb1_backend, _find_device
from serial.tools import list_ports
target, device, firmware = _find_device(_get_libusb1_backend(), False)
assert target == 'snap' and device.serial_number == '021038102RYN014624', 'Unexpected debugger'
assert firmware == sys.argv[1], f'Unexpected firmware mode: {firmware}'
print('Verified final mode:', firmware)
for port in list_ports.comports():
    if port.serial_number == '021038102RYN014624':
        print('Snap serial port:', port.device, port.hwid)
'@
    & $pythonExe -c $postflight $image.Expected
    if ($LASTEXITCODE -ne 0) { throw "Final mode could not be verified. See $logPath" }
} finally {
    $env:PYTHONIOENCODING = $previousEncoding
}
