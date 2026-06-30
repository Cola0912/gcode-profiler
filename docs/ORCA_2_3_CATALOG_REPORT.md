# OrcaSlicer 2.3 Catalog Report

最終更新: 2026-07-01

## Source

- Slicer: OrcaSlicer
- Version inventoried: `v2.3.0`
- Official repository: `https://github.com/OrcaSlicer/OrcaSlicer`
- Commit: `70931e5321fa66966a5bfb251efca0e82307d427`
- Source file used: `src/libslic3r/PrintConfig.cpp`
- Extraction tool: `tools/extract_orca_parameters.py`

## Coverage

`parameter_catalogs/orca/2.3/coverage.json`

```json
{
  "native_parameters_found": 505,
  "catalog_parameters": 505,
  "mapped_to_canonical": 33,
  "native_only": 472,
  "deprecated": 0,
  "unverified": 472,
  "coverage_percent": 100.0,
  "discovered": 505,
  "verified": 0,
  "partially_verified": 33,
  "mapped": 33,
  "editable": 505,
  "exportable": 505,
  "importable": 505,
  "recoverable_from_gcode": 33
}
```

## Line-width fields implemented

Mapped Orca native keys:

| native_key | canonical_key |
|---|---|
| `line_width` | `process.quality.line_width.default` |
| `initial_layer_line_width` | `process.quality.line_width.initial_layer` |
| `outer_wall_line_width` | `process.quality.line_width.outer_wall` |
| `inner_wall_line_width` | `process.quality.line_width.inner_wall` |
| `top_surface_line_width` | `process.quality.line_width.top_surface` |
| `internal_solid_infill_line_width` | `process.quality.line_width.internal_solid_infill` |
| `sparse_infill_line_width` | `process.quality.line_width.sparse_infill` |
| `support_line_width` | `process.quality.line_width.support` |

No independent Orca native keys were discovered for:

- `process.quality.line_width.bottom_surface`
- `process.quality.line_width.support_interface`
- `process.quality.line_width.bridge`
- `process.quality.line_width.gap_fill`
- `process.quality.line_width.skirt`
- `process.quality.line_width.brim`
- `process.quality.line_width.raft`

These must not be invented as native Orca fields.

## UI sections implemented

The catalog contains native `category` and generated `section` fields. Current runtime APIs:

- `filter_parameters()`
- `group_for_ui()`
- `CatalogEditorModel`

Implemented editor features at model level:

- slicer/version selection
- profile_kind filtering
- Basic/Advanced/Expert filtering
- search by label/native_key/canonical_key/category/description
- reset to native default
- section tree generation for lazy UI creation

The actual PySide GUI still uses the legacy fixed schema. Connecting the generated editor is the next UI task.

## Remaining unverified parameters

472 parameters are `native_only` and `unverified`.

Reason:

- native key/type/default/category/mode were extracted from official source
- canonical meaning was not reviewed yet
- UI dependencies were not extracted yet
- native writer behavior is Phase 5

## Plan for next slicer

Recommended next slicer: Bambu Studio.

Reason:

- it is close to OrcaSlicer
- diff against Orca catalog will expose fork-specific fields
- same catalog format can be reused

Suggested order:

1. Implement `tools/extract_bambu_parameters.py`
2. Generate `parameter_catalogs/bambu/<version>/parameters.json`
3. Run `tools/diff_parameter_versions.py` against Orca where useful
4. Add Bambu catalog tests
5. Only then connect Bambu native writer behavior

