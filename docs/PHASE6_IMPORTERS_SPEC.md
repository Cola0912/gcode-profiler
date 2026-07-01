# Phase 6 Native Importers Spec

最終更新: 2026-07-01

この仕様書は、v0.4.1 公開後に進めている native profile import 機能の
引き継ぎ用スナップショットです。現在の実装は `gcode_profiler/importers/`
配下にあり、G-code 解析結果とは独立して slicer profile を canonical profile
へ取り込むための土台です。

## 目的

native slicer profile を読み込み、継承を解決し、canonical profile に正規化する。
source slicer から target slicer への pairwise 変換は作らず、必ず canonical layer
を経由する。

profile import では `configured` layer を作る。G-code 解析から得られる
`observed` / `emitted` layer とは混ぜず、必要な場合のみ `import_and_merge()` で
統合して conflict を記録する。

## 所有境界

- canonical semantic schema: `gcode_profiler/canonical/model.py`
- legacy G-code result -> canonical: `gcode_profiler/canonical/adapter.py`
- canonical -> target native mapping: `gcode_profiler/conversion/registry.py`
- target native writer: `gcode_profiler/writers/`
- native profile importer: `gcode_profiler/importers/`
- legacy UI presentation schema: `gcode_profiler/schema.py`

`gcode_profiler/schema.py` は現時点では UI presentation 兼 legacy field list です。
semantic schema の source of truth にはしない。新規 import/export は canonical
model と conversion registry を通す。

## Public API

```python
from gcode_profiler import importers

det = importers.detect(path)
profile = importers.import_profile(path)
merged = importers.import_and_merge(path, gcode_result)
```

戻り値:

- `detect(path)`: cached text を含まない detection dict
- `import_profile(path)`: canonical profile。native profile 値は `configured`
- `import_and_merge(path, gcode_result)`: configured + observed/emitted を保持した
  canonical profile

## 実装済みファイル

| ファイル | 役割 |
|---|---|
| `gcode_profiler/importers/__init__.py` | public API、archive 読み込み、sibling preset 探索 |
| `gcode_profiler/importers/base.py` | `NativeProfile` / `NativeValue` |
| `gcode_profiler/importers/detection.py` | content signature による format/slicer/profile_kind 判定 |
| `gcode_profiler/importers/security.py` | zip entry 数、サイズ、path traversal 制限 |
| `gcode_profiler/importers/repository.py` | parent preset repository |
| `gcode_profiler/importers/inheritance.py` | `inherits` 解決、declared/effective/origin_map |
| `gcode_profiler/importers/json_family.py` | Orca/Bambu JSON parser |
| `gcode_profiler/importers/ini_family.py` | Prusa/SuperSlicer INI と Cura CFG parser |
| `gcode_profiler/importers/xml_family.py` | Simplify3D FFF XML parser |
| `gcode_profiler/importers/adapters.py` | slicer 別 semantic adapter |
| `gcode_profiler/importers/to_canonical.py` | conversion registry 逆引き native -> canonical |
| `gcode_profiler/importers/merge.py` | configured profile + observed G-code merge |
| `gcode_profiler/gui.py` | native profile import button と canonical profile model bridge |
| `gcode_profiler/export_flow.py` | canonical profile から conversion plan を作る entry point |
| `tests/test_importers.py` | Phase 6 importer regression tests |

## 実装済み動作

- 拡張子だけに依存しない content-based detection
- OrcaSlicer / Bambu Studio JSON profile parsing
- PrusaSlicer / SuperSlicer flat INI と bundle INI parsing
- Cura `.cfg` style sectioned profile parsing
- Simplify3D `.fff` XML leaf setting parsing
- `.3mf` / zip 内 config file の安全読み込み
- sibling files からの parent preset 探索
- simple `inherits` chain の解決
- declared keys / inherited keys / origin map の保持
- native value の raw / parsed / value_mode 保持
- 1:1 reversible mapping の native -> canonical import
- unit conversion reverse mapping
- unknown native field の `canonical["unmapped"]` 保持
- configured と observed/emitted の merge
- configured と observed/emitted の conflict 記録
- Orca/Bambu、Prusa/SuperSlicer を別 adapter として保持
- GUI から native profile を読み込み、既存設定カードへ反映
- imported profile 値を `configured` として保持し、UI 編集値を `edited` として重ねる
- imported canonical profile から直接 export conversion plan を作成

## 現在のテスト状態

2026-07-01 時点:

- `python -m pytest -q tests/test_importers.py`: pass
- `python -m pytest -q`: pass
- `python app.py --smoke-test`: pass
- collected tests: 158

## 制限事項

- multiple-parent precedence の厳密再現は未実装
- vendor/system preset repository の探索は未実装
- Cura expression の評価は未実装。raw/native value として保持する
- Simplify3D nested auto-config section の完全復元は未実装
- same-slicer round-trip で順序、コメント、未知構造を完全保持する保証はまだない
- GUI の import action は接続済み。ただし unmapped/conflict の詳細表示は最小限
- native-only imported value は preserved されるが、writer 側の same-slicer 完全再出力とは未接続
- clean-machine import 動作や official slicer での再読み込み検証は未実施

## 重要ルール

- importer は legacy analyzer result dict に直接書かない
- native unknown field は捨てず `canonical["unmapped"]` に保持する
- `configured`, `emitted`, `observed`, `edited`, `target_default` を混ぜない
- feature/path presence を setting enabled として確定しない
- Orca/Bambu と Prusa/SuperSlicer は parser 共有可、semantic adapter は分離する
- writer は arbitrary fallback value を invent しない
- archive/profile input は untrusted として扱う

## 次の実装順

1. `unmapped` / unsupported / conflict の UI 詳細表示を追加する
2. import した canonical profile を catalog editor に流し込む
3. same-slicer preservation path を writer と接続する
4. semantic round-trip test を追加する
5. vendor/system preset repository を追加する
6. official slicer で import/export した profile の実機読み込み検証を行う

## リリース判断

Phase 6 の次リリース候補は v0.5.0。
最低条件:

- importer API tests pass
- full test suite pass
- GUI import が user-visible に動作する
- imported native-only / unmapped values が失われないことを report できる
- clean-machine installer の self-contained claim は、実機検証が終わるまで書かない
