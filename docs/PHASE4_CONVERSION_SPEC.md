# Phase 4 Conversion Planning Spec

最終更新: 2026-07-01  
対象: `gcode_profiler/conversion/`  
状態: 実装済み（native serialization は Phase 5）

## 目的

Phase 4 は、Phase 1 の canonical semantic profile を入力にして、各スライサー形式へ変換するための **conversion plan** を作る層である。

この層はファイルを書き出さない。OrcaSlicer/Bambu Studio/PrusaSlicer/SuperSlicer/Cura/Simplify3D の native writer は Phase 5 で実装する。

重要な境界:

- source slicer から target slicer への直接変換は禁止
- すべて `canonical_key -> target_key(s)` で変換する
- 不明値を勝手に補完しない
- `target_default` は復元値として扱わない
- `configured` / `emitted` / `observed` / `edited` / `target_default` は plan 内に保持する
- Bambu Studio と OrcaSlicer、SuperSlicer と PrusaSlicer は registry entry を分ける

## 実装ファイル

| ファイル | 役割 |
|---|---|
| `gcode_profiler/conversion/registry.py` | target capability registry + mapping registry |
| `gcode_profiler/conversion/plan.py` | conversion plan builder |
| `gcode_profiler/conversion/preview.py` | UI/レビュー用 grouping と日本語 summary |
| `gcode_profiler/conversion/__init__.py` | public API |
| `tests/test_conversion.py` | Phase 4 の仕様固定テスト |

## Public API

```python
from gcode_profiler.conversion import (
    TARGETS,
    CAPABILITIES,
    build_plan,
    capability,
    mapping,
    supported,
    group_plan,
    summary_ja,
)
```

## Conversion plan schema

`build_plan(profile, target)` は以下を返す。

```python
{
    "target": "orca",
    "entries": [...],
    "required_user_inputs": [...],
    "warnings": [...],
    "conversion_score": 0.0,
}
```

### Entry

```python
{
    "canonical_key": "process.quality.layer_height",
    "source_value": 0.2,
    "effective_value": 0.2,
    "target_keys": ["layer_height"],
    "relation": "exact",
    "status": "ready",
    "confidence": 1.0,
    "information_loss": [],
    "warnings": [],
    "value_layers": {
        "observed": 0.2
    },
    "profile_kind": "process",
}
```

### Required user input

```python
{
    "canonical_key": "printer.basic_information.bed_shape",
    "reason": "造形可能領域はG-codeから復元不可",
    "required_for": ["printer profile"],
    "suggested_value": None,
    "suggestion_source": None,
    "confidence": 0.0,
    "safety_level": "critical",
}
```

## Mapping relation

`registry.py` の `relation` は native writer に渡す変換意味を表す。

| relation | 意味 |
|---|---|
| `exact` | canonical key と target key が同じ意味 |
| `rename` | 名前だけ違う |
| `unit_conversion` | 単位変換が必要 |
| `derived_percent` | absolute 値を基準値から percentage に導出 |
| `one_to_many` | 1つの canonical value を複数 target keys に展開 |
| `many_to_one` | 複数概念を target の1値へ集約する可能性がある |
| `enum` | enum translation table を使う |
| `approximated` | 近似 |
| `unsupported` | target が未対応 |

## 実装済み target

`TARGETS`:

- `orca`
- `bambu`
- `prusa`
- `superslicer`
- `cura`
- `simplify3d`

注意:

- `bambu` は現時点では OrcaSlicer と同じ key vocabulary を複製しているが、registry entry は別。
- `superslicer` も PrusaSlicer と同じ初期 mapping を複製しているが、registry entry は別。
- Phase 5 で native writer は必ず target ごとに分割する。

## 現在固定済みの仕様

テストで保証している内容:

- target registry は明示 mapping のみを supported とする
- key-name similarity では capability を推測しない
- exact/rename/percentage formatting が動く
- one-to-many は単一 effective value と複数 target keys を保持する
- Simplify3D の speed は `defaultSpeed` と percentage fields に変換できる
- many-to-one は information loss を残す
- enum は target table に従う。未知 enum は `approximated` + warning
- required user input は不足時に出る
- low-confidence nozzle は確認要求になる
- target default は `target_default` status で復元値扱いしない
- conflict は `configured` と `emitted` を保持し warning を出す
- edited value は effective として勝つが value layers は残る
- legacy result は `canonical.migrate()` 経由で plan に入れる

## 未実装（Phase 5 以降）

Phase 4 では以下を実装しない。

- `.json` / `.ini` / `.fff` / `.cfg` の native serialization
- target profile subtype 分割
  - Orca/Bambu: process / filament / machine
  - Prusa/SuperSlicer: print / filament / printer
  - Cura: quality changes / material / machine
  - Simplify3D: fff
- target version ごとの exact native schema
- semantic round-trip validation
- GUI の conversion preview 表示
- existing `exporters.py` の完全置換

## Claude への引き継ぎメモ

次に作業するなら Phase 5 が自然。

推奨順:

1. `gcode_profiler/writers/` を新設する
2. `writers/base.py` に writer interface を作る
3. `writers/orca.py` と `writers/bambu.py` を分離して実装する
4. `writers/prusa.py` と `writers/superslicer.py` を分離して実装する
5. `conversion.build_plan()` の entries を writer 入力にする
6. 既存 `exporters.py` は deprecated compatibility wrapper にする
7. native writer の output を snapshot test で固定する

やってはいけないこと:

- legacy analyzer result から直接 target writer に流すこと
- support path absence を support disabled として出すこと
- process speed を printer max speed として使うこと
- process acceleration を printer max acceleration として使うこと
- `target_default` を recovered value として表示/出力すること
- Orca と Bambu、Prusa と SuperSlicer を同じ writer 関数で固定すること

