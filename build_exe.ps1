# G-code プロファイル復元ツール を単一 exe にビルド
# 使い方:  powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "=== 依存インストール ===" -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "=== PyInstaller ビルド ===" -ForegroundColor Cyan
python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "GcodeProfiler" `
    --icon "GCode_Profile_Reverse_Engineer.ico" `
    --add-data "GCode_Profile_Reverse_Engineer.ico;." `
    --collect-submodules gcode_profiler `
    app.py

Write-Host "=== 完了 ===" -ForegroundColor Green
Write-Host "出力: $PSScriptRoot\dist\GcodeProfiler.exe"
