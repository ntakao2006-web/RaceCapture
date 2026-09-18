param(
    [string]$Godot = 'Godot_v4.7.2-stable_mono_win64_console.exe',
    [switch]$LinuxArm64
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$godotCommand = (Get-Command $Godot -ErrorAction Stop).Source
Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force artifacts, dist/EcoCapture | Out-Null
    & dotnet run --project tests/EcoCapture.Tests.csproj
    if ($LASTEXITCODE -ne 0) { throw 'Core tests failed' }
    & $godotCommand --headless --editor --path . --import --quit *> artifacts/import.log
    if ($LASTEXITCODE -ne 0 -or (Select-String artifacts/import.log -Pattern 'ERROR:')) { throw 'Resource import failed; see artifacts/import.log' }
    $exports = @(@{ Preset='Windows Desktop'; Folder='EcoCapture-0.3.11'; Binary='EcoCapture.exe'; Tag='windows-x64' })
    if ($LinuxArm64) { $exports += @{ Preset='Linux ARM64'; Folder='EcoCapture-linux-arm64'; Binary='EcoCapture.arm64'; Tag='linux-arm64' } }
    foreach ($item in $exports) {
        $directory = Join-Path dist $item.Folder
        $distRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'dist')) + [IO.Path]::DirectorySeparatorChar
        $directoryFull = [IO.Path]::GetFullPath((Join-Path $projectRoot $directory))
        if (-not $directoryFull.StartsWith($distRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe export directory' }
        if (Test-Path -LiteralPath $directoryFull) { Remove-Item -LiteralPath $directoryFull -Recurse -Force }
        New-Item -ItemType Directory -Force $directory | Out-Null
        $log = 'artifacts/export-' + $item.Tag + '.log'
        & $godotCommand --headless --path . --export-release $item.Preset *> $log
        if ($LASTEXITCODE -ne 0 -or (Select-String $log -Pattern 'ERROR:|Failed to export|Build failed')) { throw "Export failed; see $log" }
        if (-not (Test-Path -LiteralPath (Join-Path $directory $item.Binary))) { throw 'Export did not produce executable' }
        Copy-Item -LiteralPath README.md, SYSTEM_REQUIREMENTS.md, LINUX.md, RPI4_SETUP.md, BUILD.md, VERIFICATION.md, UX250H_TEST.md, NCEC_V1.md -Destination $directory -Force
        Copy-Item -LiteralPath licenses -Destination $directory -Recurse -Force
        if ($item.Tag -eq 'linux-arm64') {
            Copy-Item -Path packaging/linux-arm64/* -Destination $directory -Force
        }
        $archive = Join-Path dist ('EcoCapture-0.3.11-' + $item.Tag + '.zip')
        Compress-Archive -Path $directory -DestinationPath $archive -Force
        Get-FileHash -LiteralPath $archive -Algorithm SHA256
    }
}
finally { Pop-Location }
