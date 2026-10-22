$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$xc8Candidates = @(
    'C:\Users\lintaroh\AppData\Local\Microchip\xc8\xc8-v4.00\bin\xc8-cc.exe',
    'C:\Program Files\Microchip\xc8\v4.00\bin\xc8-cc.exe'
)
$dfpCandidates = @(
    'C:\Users\lintaroh\.mchp_packs\Microchip\PIC18F-Q_DFP\1.30.487\xc8'
)

$xc8Cc = $xc8Candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$dfpXc8 = $dfpCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $xc8Cc) {
    throw 'MPLAB XC8 v4.00 was not found.'
}
if (-not $dfpXc8) {
    throw 'Microchip PIC18F-Q_DFP v1.30.487 was not found.'
}

$outputDir = Join-Path $projectRoot 'dist\default\production'
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$outputBase = Join-Path $outputDir 'pic18f26q84_blink.X.production'
$outputElf = "$outputBase.elf"
$mapFile = "$outputBase.map"

& $xc8Cc `
    '-mcpu=18F26Q84' `
    "-mdfp=$dfpXc8" `
    '-O1' `
    '-std=c99' `
    "-Wl,-Map=$mapFile" `
    "-o$outputElf" `
    (Join-Path $projectRoot 'main.c')

if ($LASTEXITCODE -ne 0) {
    throw "XC8 build failed with exit code $LASTEXITCODE."
}

$outputHex = "$outputBase.hex"
if (-not (Test-Path -LiteralPath $outputHex)) {
    throw "XC8 completed but did not create $outputHex."
}

Write-Output "Built: $outputHex"
