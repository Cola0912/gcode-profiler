# Clean-machine validation checklist

The compiled `GcodeProfiler-Setup-<version>-x64.exe` is a **self-contained**
Windows installer. End users do **not** need Inno Setup, Python, PyInstaller,
pip, or any development tools; the installer embeds the complete PyInstaller
`--onedir` output (Python runtime + Qt included).

Inno Setup is required **only** on the developer/build machine (and CI), used by
`scripts/build_installer.ps1` / the GitHub Actions workflow to *compile* the
installer. It is never bundled into the user installer and never runs at install
time.

## Validation steps (run on a clean Windows VM / Windows Sandbox)

Preconditions on the test machine:

- [ ] Inno Setup is NOT installed
- [ ] Python is NOT installed
- [ ] Project source code is absent
- [ ] Internet connection is disabled

Then verify:

- [ ] Installer completes successfully (interactive)
- [ ] Silent install works: `GcodeProfiler-Setup-<version>-x64.exe /VERYSILENT /NORESTART`
- [ ] Application launches from the Start Menu shortcut
- [ ] Bundled resources load (icon shows; no "missing module/resource" error)
- [ ] `GcodeProfiler.exe --smoke-test` exits 0
- [ ] G-code analysis starts successfully (open a `.gcode` file; analysis runs)
- [ ] Optional `.gcode` "Open With Gcode Profiler" launches and opens the file
- [ ] Japanese install path and Japanese file path both work
- [ ] No console window appears
- [ ] Upgrade over a previous version preserves `%LOCALAPPDATA%\GcodeProfiler`
- [ ] Uninstall removes program files/shortcuts but preserves user data
- [ ] Silent uninstall works: `unins000.exe /VERYSILENT /NORESTART`

## Status

> NOT YET EXECUTED on a clean machine. The installer has only been *compiled* and
> the application *launched* on a developer machine that already has Python. Do
> not claim clean-machine compatibility until the steps above are actually run on
> a machine without Python/Inno Setup and with networking disabled.
