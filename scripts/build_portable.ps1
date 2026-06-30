# Build the portable single-file exe: dist\portable\GcodeProfiler.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = & "$PSScriptRoot\print_version.ps1"
Write-Host "=== Gcode Profiler $version (portable) ===" -ForegroundColor Cyan

python --version
python -m pip install -r requirements-build.txt
Write-Host "--- tests ---" -ForegroundColor Cyan
python -m pytest -q; if (-not $?) { Write-Error "tests failed"; exit 1 }

Remove-Item -Recurse -Force "$root\build\GcodeProfiler", "$root\dist\portable" -ErrorAction SilentlyContinue
$env:GP_ONEFILE = "1"
python -m PyInstaller --noconfirm --distpath "dist\portable" --workpath "build" GcodeProfiler.spec
Remove-Item Env:\GP_ONEFILE

$exe = "$root\dist\portable\GcodeProfiler.exe"
if (-not (Test-Path $exe)) { Write-Error "portable exe not produced"; exit 1 }
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
Write-Host "OK portable: $exe" -ForegroundColor Green
Write-Host "SHA256: $hash"
