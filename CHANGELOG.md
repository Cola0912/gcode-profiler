# Changelog

All notable changes to Gcode Profiler are documented in this file.
The format is based on Keep a Changelog; this project uses Semantic Versioning.

## [Unreleased]

### Added
- Phase 7 packaging: `gcode_profiler/version.py` canonical version, `resources.py`
  (`resource_path`, `user_data_dir`), `--smoke-test` mode, command-line file open.
- `GcodeProfiler.spec` (PyInstaller onedir + onefile), Windows executable metadata.
- Build scripts (`scripts/clean_build.ps1`, `build_portable.ps1`,
  `build_installer.ps1`, `verify_artifacts.ps1`).
- Inno Setup installer (`installer/GcodeProfiler.iss`) with stable AppId,
  optional desktop shortcut, optional `.gcode` Open-With association.
- GitHub Actions: `windows-build.yml` (CI) and `release.yml` (tag-driven draft).
- LICENSE (Apache-2.0), NOTICE, THIRD_PARTY_LICENSES.md.
- pytest suite under `tests/`.

### Fixed
- Nozzle estimation: added proprietary `;Marker` enter/exit stack so infill is
  no longer attributed to wall features (outer_wall 3601 -> 132 segments on the
  reference sample); use rectangular effective width as the primary value;
  stabilize layer height via global modal Z-delta. Reference sample now reports
  outer 0.602 mm, inner 0.596 mm, infill 0.716 mm, layer 0.300 mm -> 0.6 mm nozzle.

### Changed
- Phase 1: machine motion limits (`machine.max_accel_*`, `machine.max_speed_*`)
  are no longer populated from process acceleration / travel speed. They remain
  unknown unless emitted via M201/M203/M205/M566/SET_VELOCITY_LIMIT.

### Known limitations (deferred)
- Phase 2–6, 8 architecture (generic parser pipeline, canonical conversion
  engine, separate native importers/writers, performance/cache layer) is
  specified but not yet implemented in this release.
- Slicer profile exports are verified against synthetic fixtures only; they have
  not been imported into the native slicer applications.

## [0.1.0] - unreleased
Initial packaged version.
