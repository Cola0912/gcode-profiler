# Release checklist

Mark items only after they are actually verified.

- [ ] Update `gcode_profiler/version.py` (`__version__`)
- [ ] Update `CHANGELOG.md`
- [ ] `python -m pytest` green
- [ ] `scripts/build_portable.ps1` produces `dist/portable/GcodeProfiler.exe`
- [ ] `scripts/build_installer.ps1` produces `dist/installer/GcodeProfiler-Setup-<version>-x64.exe`
- [ ] Clean-Windows validation (VM or Windows Sandbox): install, launch, `.gcode` Open With, uninstall, user-data preserved
- [ ] Antivirus / malware scan of artifacts (if available)
- [ ] Verify `THIRD_PARTY_LICENSES.md` matches actually bundled versions (`pip show PySide6 pyinstaller`)
- [ ] Verify artifact SHA-256 (`scripts/verify_artifacts.ps1` -> `dist/SHA256SUMS.txt`)
- [ ] Create signed Git tag `v<version>`
- [ ] Inspect draft GitHub Release produced by `release.yml`
- [ ] Publish release
- [ ] Re-download artifacts and verify hashes

## User-data location

`%LOCALAPPDATA%\GcodeProfiler` (settings, custom profiles, custom dialect rules, logs, cache).
Full manual removal: uninstall, then delete that folder.
