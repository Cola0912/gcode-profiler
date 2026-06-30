# Verify produced artifacts and emit SHA256SUMS.txt.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$version = & "$PSScriptRoot\print_version.ps1"

$checks = @(
    "dist\app\GcodeProfiler\GcodeProfiler.exe",
    "dist\app\GcodeProfiler\_internal\LICENSE"
)
$ok = $true
foreach ($c in $checks) {
    if (Test-Path $c) { Write-Host "[ok]   $c" -ForegroundColor Green }
    else { Write-Host "[miss] $c" -ForegroundColor Red; $ok = $false }
}

# metadata check
$exe = "dist\app\GcodeProfiler\GcodeProfiler.exe"
if (Test-Path $exe) {
    $vi = (Get-Item $exe).VersionInfo
    Write-Host "FileVersion=$($vi.FileVersion) Product=$($vi.ProductName) Company=$($vi.CompanyName)"
    if ($vi.FileVersion -ne $version) { Write-Host "[warn] file version != $version" -ForegroundColor Yellow }
}

# hashes
$sums = @()
foreach ($a in @("dist\portable\GcodeProfiler.exe",
                 "dist\installer\GcodeProfiler-Setup-$version-x64.exe")) {
    if (Test-Path $a) { $sums += "{0}  {1}" -f (Get-FileHash $a -Algorithm SHA256).Hash, (Split-Path $a -Leaf) }
}
if ($sums.Count) {
    $sums | Set-Content -Encoding ascii "dist\SHA256SUMS.txt"
    Write-Host "wrote dist\SHA256SUMS.txt"
    $sums | ForEach-Object { Write-Host $_ }
}
if (-not $ok) { exit 1 }
Write-Host "verify done" -ForegroundColor Green
