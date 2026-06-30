# Phase 5 Native Writers Spec

最終更新: 2026-07-01

## 目的

Phase 5 は `conversion.build_plan()` の出力を入力にして、target-native profile files を生成する層である。

重要:

- writer は legacy analyzer result dict を受け取らない
- writer は canonical conversion plan entries だけを消費する
- unresolved critical input がある場合は block する
- `target_default` は復元値として書かない
- Orca/Bambu、Prusa/SuperSlicer は別 writer module として分離する

## 実装ファイル

| ファイル | 役割 |
|---|---|
| `gcode_profiler/writers/base.py` | writer result / grouping / formatting helpers |
| `gcode_profiler/writers/orca.py` | OrcaSlicer JSON writer |
| `gcode_profiler/writers/bambu.py` | Bambu Studio JSON writer |
| `gcode_profiler/writers/prusa.py` | PrusaSlicer INI writer |
| `gcode_profiler/writers/superslicer.py` | SuperSlicer INI writer |
| `gcode_profiler/writers/cura.py` | Cura quality-changes CFG writer |
| `gcode_profiler/writers/simplify3d.py` | Simplify3D FFF writer |
| `gcode_profiler/writers/__init__.py` | dispatch API |
| `tests/test_writers.py` | writer behavior tests |

## Public API

```python
from gcode_profiler.writers import write_native

plan = build_plan(canonical_profile, "orca")
result = write_native(plan, name="Recovered")
```

`result`:

```python
{
  "target": "orca",
  "files": [("Recovered.process.json", "...")],
  "blocked": false,
  "required_user_inputs": [],
  "unsupported": [],
  "warnings": []
}
```

## 現在の実装範囲

Implemented:

- plan entries を `profile_kind` ごとに process/filament/printer へ分ける
- writable statuses:
  - `ready`
  - `derived`
  - `one_to_many`
  - `many_to_one`
  - `conflict`
- skip `target_default`
- collect unsupported entries
- block unresolved critical required inputs
- per-target modules

Not implemented yet:

- native profile inheritance
- same-slicer native-only preservation
- imported native profile round-trip
- per-tool array expansion from catalog extruder count
- complete target-native schema validation
- replacing legacy `exporters.py`
- GUI connection

## Writer notes

### OrcaSlicer

Files:

- `{name}.process.json`
- `{name}.filament.json`
- `{name}.machine.json`

### Bambu Studio

Files:

- `{name}.bambu.process.json`
- `{name}.bambu.filament.json`
- `{name}.bambu.machine.json`

Bambu currently shares Orca-family JSON vocabulary, but writer module is separate.

### PrusaSlicer

File:

- `{name}.prusa.ini`

### SuperSlicer

File:

- `{name}.superslicer.ini`

### Cura

File:

- `{name}.cura.cfg`

### Simplify3D

File:

- `{name}.simplify3d.fff`

## Tests

`tests/test_writers.py` verifies:

- Orca output profile subtype files
- Bambu writer is separate from Orca writer
- Prusa/SuperSlicer writers are separate
- Cura CFG output
- Simplify3D FFF output with derived percentage
- critical required input blocks writer output
- `target_default` values are not written as recovered values

## Next work

1. ~~Connect GUI export flow to `conversion.build_plan()` + `writers.write_native()`.~~
   DONE in v0.4.1 via `gcode_profiler/export_flow.py` (preview + critical-input block).
2. Keep old `exporters.py` as a compatibility wrapper. (retained)
3. Add snapshot tests for richer plans.
4. Add target-native schema validation using parameter catalogs.
5. Add same-slicer native-only preservation after native import is implemented (Phase 6).
6. Carry G-code start/end/toolchange blocks and extra machine fields through the
   canonical mapping so the native writers can emit them (currently only the
   registry-mapped subset is written).

