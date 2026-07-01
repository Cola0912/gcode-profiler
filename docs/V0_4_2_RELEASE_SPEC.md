# v0.4.2 Release Spec

最終更新: 2026-07-01

## 目的

v0.4.2 は、Phase 6 full migration の前に current settings editor を
OrcaSlicer 風の Printer / Filament / Process 設定へ広げる中間リリースです。
あわせて、入力済みの造形領域が export 時に未入力扱いになる不具合を修正します。

## 含める範囲

- fixed legacy UI schema の可視・編集フィールド拡張
- `Field` metadata 拡張
- provenance badge と default confirmation の維持
- Basic / Advanced / Expert filter
- search by label / native_key / canonical_key
- section expand/collapse
- lazy tab creation
- `enabled_if` / `visible_if` の UI 反映
- `kind="gcode"` multi-line editor
- legacy key aliases
- independent line-width fields
- support/raft path presence と setting enabled state の分離
- `machine.printable_area` / `machine.printable_height` の canonical export 接続
- Orca/Bambu/Prusa/SuperSlicer 用 bed shape / printable height mapping
- Orca machine writer の `printable_area` / `printable_height` 出力
- native profile import foundation の現状スナップショット

## 含めない範囲

- all slicer version-aware catalog の完成
- full native profile importer architecture の完成
- same-slicer exact round-trip preservation
- native slicer application での import 実検証
- clean-machine compatibility claim
- exporter rewrite

## Field counts

Before this increment:

- Printer: 51
- Filament: 40
- Process: 143
- Total: 234

After this increment:

- Printer: 68
- Filament: 50
- Process: 165
- Total: 283

## Key migration notes

- `machine.printable_area` is preserved as the UI/legacy key.
- Its canonical owner is now `printer.basic_information.bed_shape`.
- `machine.printable_height` maps to `printer.basic_information.printable_height`.
- `strength.has_support` and `strength.has_raft` remain as legacy keys.
- New UI fields separate:
  - `support.setting_enabled_state`
  - `support.path_present`
  - `raft.setting_enabled_state`
  - `raft.path_present`

## Native key policy

Verified OrcaSlicer native keys are stored in `Field.native_key`.
Unverified fields keep `native_key=None` and use the description to note that the
native key is not verified. Do not invent native keys.

Current unverified counts:

- Printer: 19
- Filament: 15
- Process: 25

## Export fix

Bug:

入力済みの造形領域が export preview / writer で未入力扱いになる。

Cause:

UI stored the value under `machine.printable_area`, while conversion required
`printer.basic_information.bed_shape`.

Fix:

- `canonical.adapter.LEGACY_MAP` maps `machine.printable_area` to
  `printer.basic_information.bed_shape`.
- `conversion.registry` maps the canonical key to native `printable_area`
  for Orca/Bambu and `bed_shape` for Prusa/SuperSlicer.
- `writers/orca.py` emits `printable_area` and `printable_height` as machine
  profile array values.

## Verification

Required before release:

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:QT_QPA_PLATFORM="offscreen"
python -m pytest -q
python app.py --smoke-test
```

Expected current result:

- tests: 162 passed
- smoke-test: OK, 6 targets

Packaged artifact checks:

- PyInstaller `parameter_catalogs` data is bundled into onefile/onedir builds.
- `GcodeProfiler.exe --smoke-test` validates bundled Orca/Bambu catalogs without
  project source files.
- `GCODE_PROFILER_SMOKE_LOG=<path>` may be used only for build diagnostics.
- `SHA256SUMS.txt` includes both the installer and portable zip release assets.

## Build and release

Build requirement:

- Inno Setup 6 is required only on the developer/build machine.

End-user requirement:

- Inno Setup, Python, pip, PyInstaller, and source code are not required.

The generated installer must bundle the PyInstaller onedir output and must not
download or compile anything on the end-user machine.

Do not claim clean-machine compatibility unless it has actually been tested on a
clean supported Windows machine.

## Next work

After v0.4.2 release, resume with explicit approval:

1. `unmapped` / unsupported / conflict detail UI
2. catalog editor integration
3. same-slicer preservation path
4. semantic round-trip tests
5. official slicer import/export validation
