# Bambu Studio 2.8 Catalog Report

最終更新: 2026-07-01

## Source

- Slicer: Bambu Studio
- Version inventoried: `v02.08.00.50`
- Official repository: `https://github.com/bambulab/BambuStudio`
- Commit: `a78684a11de4abddad9a6d19eeb75a6a1d2e82a5`
- Source file used: `src/libslic3r/PrintConfig.cpp`
- Extraction tool: `tools/extract_bambu_parameters.py`

## Coverage

`parameter_catalogs/bambu/2.8/coverage.json`

```json
{
  "native_parameters_found": 567,
  "catalog_parameters": 567,
  "mapped_to_canonical": 33,
  "native_only": 534,
  "deprecated": 0,
  "unverified": 534,
  "coverage_percent": 100.0,
  "discovered": 567,
  "verified": 0,
  "partially_verified": 33,
  "mapped": 33,
  "editable": 567,
  "exportable": 567,
  "importable": 567,
  "recoverable_from_gcode": 33
}
```

## Diff against OrcaSlicer 2.3

Generated file:

- `parameter_catalogs/bambu/2.8/diff_from_orca_2.3.json`

Summary:

- Bambu Studio 2.8 has more FFF/common native parameters than OrcaSlicer 2.3 in the extracted source range.
- The catalogs are intentionally separate. Bambu is not treated as just an alias of Orca.
- Existing canonical mappings are reused where native keys match.

## Line-width fields implemented

Mapped Bambu native keys currently match the Orca-compatible line-width subset:

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

Independent native keys for bridge/gap_fill/skirt/brim/raft line width were not discovered in this pass and must not be invented.

## Remaining unverified parameters

534 parameters are `native_only` and `unverified`.

Reason:

- native key/type/default/category/mode were extracted from official source
- canonical meaning has not been reviewed yet
- dependencies are not extracted yet
- native writer behavior is still Phase 5

## Next step

Proceed to Phase 5:

1. Create target-native writer interfaces.
2. Split Orca and Bambu writers despite similar native keys.
3. Feed writers from `conversion.build_plan()` instead of direct legacy result dicts.
4. Preserve native-only same-slicer values once native import is implemented.

