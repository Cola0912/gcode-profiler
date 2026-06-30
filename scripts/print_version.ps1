# Prints the canonical application version from gcode_profiler/version.py
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$verFile = Join-Path $root "gcode_profiler\version.py"
$m = Select-String -Path $verFile -Pattern '__version__\s*=\s*"([^"]+)"'
if (-not $m) { Write-Error "version not found in $verFile"; exit 1 }
$m.Matches[0].Groups[1].Value
