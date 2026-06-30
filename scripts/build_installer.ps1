# Build the onedir application and compile the Windows installer.
# Output: dist\installer\GcodeProfiler-Setup-<version>-x64.exe
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$version = & "$PSScriptRoot\print_version.ps1"
Write-Host "=== Gcode Profiler $version (installer) ===" -ForegroundColor Cyan

python --version
python -m pip install -r requirements-build.txt
Write-Host "--- tests ---" -ForegroundColor Cyan
python -m pytest -q; if (-not $?) { Write-Error "tests failed"; exit 1 }

Remove-Item -Recurse -Force "$root\build\GcodeProfiler", "$root\dist\app", "$root\dist\installer" -ErrorAction SilentlyContinue
Remove-Item Env:\GP_ONEFILE -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --distpath "dist\app" --workpath "build" GcodeProfiler.spec

$appExe = "$root\dist\app\GcodeProfiler\GcodeProfiler.exe"
if (-not (Test-Path $appExe)) { Write-Error "onedir app not produced"; exit 1 }

Write-Host "--- application smoke test ---" -ForegroundColor Cyan
$p = Start-Process $appExe -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
if ($p.ExitCode -ne 0) { Write-Error "smoke-test failed (exit $($p.ExitCode))"; exit 1 }
Write-Host "smoke-test OK"

# locate ISCC.exe
$iscc = $env:ISCC_PATH
if (-not $iscc) {
    foreach ($c in @("C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                     "C:\Program Files\Inno Setup 6\ISCC.exe",
                     "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $c) { $iscc = $c; break }
    }
}
if (-not $iscc -or -not (Test-Path $iscc)) {
    Write-Host ""
    Write-Host "ISCC.exe (Inno Setup 6) not found." -ForegroundColor Red
    Write-Host "Inno Setup is a BUILD-machine tool used only to CREATE the installer." -ForegroundColor Yellow
    Write-Host "End users do not need it; it is not bundled into the generated Setup.exe." -ForegroundColor Yellow
    Write-Host "Resolve with one of:" -ForegroundColor Yellow
    Write-Host "  1) winget install --id JRSoftware.InnoSetup -e" -ForegroundColor Yellow
    Write-Host "  2) install from https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host '  3) set $env:ISCC_PATH to the full path of ISCC.exe' -ForegroundColor Yellow
    exit 1
}

New-Item -ItemType Directory -Force "$root\dist\installer" | Out-Null
& $iscc "/DMyAppVersion=$version" "installer\GcodeProfiler.iss"
if (-not $?) { Write-Error "ISCC compilation failed"; exit 1 }

$setup = "$root\dist\installer\GcodeProfiler-Setup-$version-x64.exe"
if (-not (Test-Path $setup)) { Write-Error "installer not produced"; exit 1 }
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash
Write-Host "OK installer: $setup" -ForegroundColor Green
Write-Host "SHA256: $hash"
