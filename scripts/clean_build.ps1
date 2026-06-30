# Remove known build/output directories only. Never deletes source or user files.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$targets = @("build", "dist\app", "dist\portable", "dist\installer", "build_version_info.txt",
             "__pycache__")
foreach ($t in $targets) {
    $p = Join-Path $root $t
    if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Host "removed $t" }
}
Write-Host "clean done" -ForegroundColor Green
