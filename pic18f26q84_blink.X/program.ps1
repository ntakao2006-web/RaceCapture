$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $projectRoot 'build.ps1')

$ipeCmdCandidates = @(
    'C:\Users\lintaroh\AppData\Local\Microchip\MPLABX\v6.35\mplab_platform\mplab_ipe\ipecmd.exe',
    'C:\Users\lintaroh\AppData\Local\Microchip\MPLABX\v6.35\mplab_platform\mplab_ipe\ipecmd.bat',
    'C:\Program Files\Microchip\MPLABX\v6.35\mplab_platform\mplab_ipe\ipecmd.exe',
    'C:\Program Files\Microchip\MPLABX\v6.35\mplab_platform\mplab_ipe\ipecmd.bat'
)
$ipeCmd = $ipeCmdCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $ipeCmd) {
    throw 'MPLAB IPE command-line programmer was not found.'
}

$hexFile = Join-Path $projectRoot 'dist\default\production\pic18f26q84_blink.X.production.hex'

$ipeOutput = & $ipeCmd '-TPsnap' '-P18F26Q84' '-M' '-Y' '-OL' "-F$hexFile" 2>&1
$ipeExitCode = $LASTEXITCODE
$ipeOutput | Write-Output

if ($ipeExitCode -ne 0 -or ($ipeOutput -match 'Connection Failed|Operation Failed|Programming failed|Verify failed')) {
    throw "MPLAB IPE programming failed with exit code $ipeExitCode."
}

Write-Output 'Programming completed successfully.'
