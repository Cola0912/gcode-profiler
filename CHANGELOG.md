# Changelog

All notable changes to Gcode Profiler are documented in this file.
The format is based on Keep a Changelog; this project uses Semantic Versioning.

## [Unreleased]

## [0.3.1] - 2026-07-01

### Added
- Version-aware native parameter catalog foundation:
  `gcode_profiler/parameter_catalogs.py`, `catalog_editor.py`, generated catalog
  filtering/grouping, coverage reports, and validation tooling.
- OrcaSlicer 2.3 reference catalog generated from official `OrcaSlicer/OrcaSlicer`
  `v2.3.0` `src/libslic3r/PrintConfig.cpp`: 505 native FFF/common parameters,
  33 mapped to canonical, 472 native-only/unverified, with coverage report and
  source references.
- Development tools for catalog extraction/validation/diff:
  `tools/extract_orca_parameters.py`, `validate_parameter_catalog.py`,
  `diff_parameter_versions.py`; placeholder extractors for Bambu/Prusa/
  SuperSlicer/Cura/Simplify3D.
- Catalog handoff docs:
  `docs/PARAMETER_CATALOG_SPEC.md` and `docs/ORCA_2_3_CATALOG_REPORT.md`.

## [0.3.0] - 2026-07-01

### Added
- Phase 4 conversion planning (`gcode_profiler/conversion/`, additive): explicit
  target capability registry, canonical-to-target mapping registry, conversion
  plan engine, required-user-input detection, conversion score, value-layer
  preservation (`configured`/`emitted`/`observed`/`edited`/`target_default`),
  preview grouping, enum translation, derived percentage conversion,
  one-to-many and many-to-one conversion annotations. Native target serialization
  remains Phase 5. 14 tests.

## [0.2.0] - 2026-07-01

### Added
- Phase 3 auxiliary-structure classification (`pipeline/regions.py`, `pipeline/auxiliary.py`):
  per-layer region model + bounded adjacent-layer vertical overlap graph; marker-led
  (with light geometry) classification of support/interface, raft (layer_count from
  actually-classified layers), brim, skirt, purge line, purge tower (fixed-XY repeated
  layers), wipe, and unknown_auxiliary. `path_present` (observed) is strictly separated
  from `setting_enabled_state` (always unknown without metadata); legacy
  `has_support`/`has_raft` are True only when present, else null. Canonical outputs
  under `process.support.*` / `process.others.*` / `process.multimaterial.*`. 6 tests;
  validated on proprietary sample (support present, raft layer_count=2). Tree/organic
  support parameter extraction deferred.
- Phase 2 generic analysis pipeline (`gcode_profiler/pipeline/`, additive): a
  slicer-independent streaming parser (`parser.py`), token/fuzzy marker
  normalization with unknown-marker collection (`markers.py`), comment-free
  logical layer reconstruction with Z-hop/spiral handling (`layers.py`), path
  segmentation with non-destructive ranked feature candidates and
  purge/wipe/prime/short exclusion (`paths.py`), and an orchestrator with
  diagnostics + legacy-compat adapter (`runner.py`). Validated on the
  proprietary sample (outer 0.602 / inner 0.596 / infill 0.716, 49 layers).
  9 tests. Full support/raft geometry classification deferred to Phase 3.
- Phase 1 foundation (`gcode_profiler/canonical/`): versioned canonical value model
  (`CanonicalValue` with configured/emitted/observed/edited/target_default +
  `effective` precedence edited>configured>emitted>observed>target_default),
  `schema_version`, legacy<->canonical adapter, migration of legacy result dicts,
  support/raft `path_present` separated from `setting_enabled_state`, target
  defaults marked `application_default` (never reported as recovered). 13 tests.
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
- Phase 4 conversion planning is not part of v0.2.0; it is currently in
  Unreleased on `main`.
- Phase 5–6, 8 architecture (separate native importers/writers,
  semantic round-trip validation, performance/cache layer) is specified but not
  yet implemented in this release.
- Slicer profile exports are verified against synthetic fixtures only; they have
  not been imported into the native slicer applications.

## [0.1.0] - unreleased
Initial packaged version.
