# Parameter Catalog Spec

最終更新: 2026-07-01

## 目的

固定 `schema.py` から脱出し、slicer/version/profile_kind ごとの native parameter catalog を UI と exporter/importer の共通入力にする。

この catalog は canonical semantic schema ではない。native parameter catalog は slicer 固有の事実を保持し、`canonical_key` は可能な場合だけ付ける。

## ディレクトリ

```text
parameter_catalogs/
  orca/
    2.3/
      parameters.json
      coverage.json
  bambu/
    2.8/
      parameters.json
      coverage.json
```

現在は OrcaSlicer 2.3 と Bambu Studio 2.8 の reference catalog が実装済み。

## Parameter schema

各 parameter は以下の形を持つ。

```json
{
  "slicer": "OrcaSlicer",
  "version_range": "v2.3.0",
  "profile_kind": "printer|filament|process|extruder|material|quality",
  "native_key": "",
  "canonical_key": null,
  "mapping_status": "mapped|native_only|deprecated|unsupported",
  "label": "",
  "label_ja": null,
  "description": "",
  "category": "",
  "section": "",
  "order": 0,
  "native_type": "float|int|bool|string|enum|array|percentage|expression",
  "unit": null,
  "value_mode": "absolute|percentage|ratio|count|enum|expression|unknown",
  "default": null,
  "minimum": null,
  "maximum": null,
  "step": null,
  "enum_values": [],
  "per_tool": false,
  "nullable": true,
  "visibility": "basic|advanced|expert|hidden",
  "enabled_if": [],
  "visible_if": [],
  "conflicts_with": [],
  "requires": [],
  "deprecated": false,
  "replacement_key": null,
  "recovery_capability": {
    "explicit_metadata_recoverable": false,
    "runtime_command_recoverable": false,
    "geometry_recoverable": false,
    "statistically_estimable": false,
    "profile_only": true,
    "target_only": false
  },
  "source_reference": {
    "repository": "OrcaSlicer/OrcaSlicer",
    "tag": "v2.3.0",
    "file": "src/libslic3r/PrintConfig.cpp",
    "line": 0
  },
  "verification_status": "verified|partially_verified|unverified",
  "importable": true,
  "exportable": true
}
```

## Runtime API

```python
from gcode_profiler.parameter_catalogs import (
    list_catalogs,
    load_catalog,
    filter_parameters,
    group_for_ui,
    coverage_report,
)
from gcode_profiler.catalog_editor import CatalogEditorModel, EditorState
```

`CatalogEditorModel` は non-GUI model。GUI はこれを使って lazy section creation / search / visibility filtering を実装する。

## Development tools

```text
tools/extract_orca_parameters.py
tools/validate_parameter_catalog.py
tools/diff_parameter_versions.py
```

他 slicer の extractor file は placeholder として存在するが未実装。

## 現在の制限

- OrcaSlicer 2.3 / Bambu Studio 2.8 は `PrintConfig.cpp` から抽出した factual catalog。
- UI grouping は source の `category/mode` と heuristic `section` の混合で、完全な native UI reproduction ではない。
- dependencies はまだ未抽出（空配列）。
- native-only は import/edit/same-slicer export の対象だが cross-slicer mapping には使わない。
- current GUI はまだ固定 schema を使う。catalog-driven GUI は次の実装で接続する。
