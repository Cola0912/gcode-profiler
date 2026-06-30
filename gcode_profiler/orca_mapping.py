# -*- coding: utf-8 -*-
"""
解析結果 -> OrcaSlicer パラメータへのマッピング
==============================================
OrcaSlicer の設定 JSON はキー/値ともに文字列、百分率は "15%" のように保持する。
品質/速度/強度 はプロセス設定、温度/ファンはフィラメント設定、リトラクト/Zホップは
プリンタ(マシン)設定に属するため、profile を分けて持つ。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Param:
    key: str                 # 解析結果内のキー (section.field)
    label: str               # 画面表示名(日本語)
    orca_key: Optional[str]  # Orca 設定キー (None は表示のみ)
    unit: str = ""
    profile: str = "process"  # process / filament / printer / info
    fmt: Optional[Callable] = None  # Orca 値への整形
    kind: str = "num"         # num / int / bool — 入力欄の種別

    def get_value(self, result: dict):
        sec, field = self.key.split(".", 1)
        return result.get(sec, {}).get(field)

    def set_value(self, result: dict, value):
        sec, field = self.key.split(".", 1)
        result.setdefault(sec, {})[field] = value


def _round_str(ndigits=0):
    def f(v):
        if v is None:
            return None
        if ndigits == 0:
            return str(int(round(v)))
        return str(round(v, ndigits))
    return f


def _pct_str(v):
    if v is None:
        return None
    return f"{int(round(v))}%"


def _bool_str(v):
    return "1" if v else "0"


def _array1(inner):
    def f(v):
        s = inner(v)
        return None if s is None else [s]
    return f


# ---------------------------------------------------------------------------
# カテゴリ定義  (画面はこの順/グルーピングで表示)
# ---------------------------------------------------------------------------
# OrcaSlicer のプロセス設定タブ構成に合わせる: 品質 / 強度 / 速度 / サポート / その他
CATEGORIES = {
    "品質": [
        Param("quality.layer_height", "積層ピッチ", "layer_height", "mm", "process", _round_str(2)),
        Param("quality.first_layer_height", "最初の層の高さ", "initial_layer_print_height", "mm", "process", _round_str(2)),
        Param("quality.outer_wall_width", "外壁のライン幅", "outer_wall_line_width", "mm", "process", _round_str(2)),
        Param("quality.inner_wall_width", "内壁のライン幅", "inner_wall_line_width", "mm", "process", _round_str(2)),
        Param("quality.sparse_infill_width", "インフィルのライン幅", "sparse_infill_line_width", "mm", "process", _round_str(2)),
        Param("quality.top_surface_width", "上面のライン幅", "top_surface_line_width", "mm", "process", _round_str(2)),
    ],
    "強度": [
        Param("strength.wall_loops", "ウォールのループ数", "wall_loops", "本", "process", _round_str(0), "int"),
        Param("strength.sparse_infill_density_pct", "インフィル密度", "sparse_infill_density", "%", "process", _pct_str),
    ],
    "速度": [
        Param("speed.outer_wall_speed", "外壁", "outer_wall_speed", "mm/s", "process", _round_str(0)),
        Param("speed.inner_wall_speed", "内壁", "inner_wall_speed", "mm/s", "process", _round_str(0)),
        Param("speed.sparse_infill_speed", "インフィル", "sparse_infill_speed", "mm/s", "process", _round_str(0)),
        Param("speed.top_surface_speed", "上面", "top_surface_speed", "mm/s", "process", _round_str(0)),
        Param("speed.travel_speed", "移動", "travel_speed", "mm/s", "process", _round_str(0)),
        Param("speed.first_layer_speed", "最初の層", "initial_layer_speed", "mm/s", "process", _round_str(0)),
        Param("speed.outer_wall_accel", "加速度", "default_acceleration", "mm/s²", "process", _round_str(0)),
    ],
    "サポート": [
        Param("strength.has_support", "サポート材を有効化", "enable_support", "", "process", _bool_str, "bool"),
        Param("speed.support_speed", "サポート速度", "support_speed", "mm/s", "process", _round_str(0)),
        Param("quality.support_width", "サポートのライン幅", "support_line_width", "mm", "process", _round_str(2)),
        Param("strength.has_raft", "ラフトを有効化", None, "", "info", None, "bool"),
    ],
    "その他": [
        Param("temperature.bed_temp", "ベッド温度", "hot_plate_temp", "℃", "filament", _array1(_round_str(0))),
        Param("temperature.chamber_temp", "チャンバー温度", "chamber_temperature", "℃", "filament", _array1(_round_str(0))),
        Param("temperature.fan_max_pct", "最大ファン速度", "fan_max_speed", "%", "filament", _array1(_round_str(0))),
        Param("retraction.retract_length", "リトラクト長", "retraction_length", "mm", "printer", _array1(_round_str(2))),
        Param("retraction.retract_speed", "リトラクト速度", "retraction_speed", "mm/s", "printer", _array1(_round_str(0))),
        Param("retraction.deretract_speed", "リトラクト戻し速度", "deretraction_speed", "mm/s", "printer", _array1(_round_str(0))),
        Param("retraction.z_hop_height", "Zホップ高さ", "z_hop", "mm", "printer", _array1(_round_str(2))),
    ],
}

# Orca のタブ表示順 (Multimaterial / G-code は GUI 側で特別扱い)
TAB_ORDER = ["品質", "強度", "速度", "サポート", "Multimaterial", "その他", "G-code"]

# 推定の信頼度が低い項目(画面で注記)
LOW_CONFIDENCE = {
    "strength.sparse_infill_density_pct",
    "strength.wall_loops",
}

ORCA_VERSION = "2.2.0.0"


def build_export(result: dict, profile_name: str = "Recovered Profile") -> dict:
    """process / filament / printer の3つの Orca JSON を生成して返す"""
    out = {
        "process": {"type": "process", "name": profile_name, "from": "User",
                    "is_custom_defined": "1", "version": ORCA_VERSION},
        "filament": {"type": "filament", "name": profile_name, "from": "User",
                     "is_custom_defined": "1", "version": ORCA_VERSION},
        "printer": {"type": "machine", "name": profile_name, "from": "User",
                    "is_custom_defined": "1", "version": ORCA_VERSION},
    }
    for params in CATEGORIES.values():
        for p in params:
            if not p.orca_key or p.profile == "info":
                continue
            raw = p.get_value(result)
            if raw is None:
                continue
            value = p.fmt(raw) if p.fmt else str(raw)
            if value is None:
                continue
            out[p.profile][p.orca_key] = value
    # 追加: ラフトはレイヤ数として
    if result.get("strength", {}).get("has_raft"):
        out["process"]["raft_layers"] = out["process"].get("raft_layers", "2")
    return out


def rows_for_display(result: dict):
    """(カテゴリ名, [ (label, value_str, unit, orca_key, profile, low_conf) ]) のリスト"""
    out = []
    for cat, params in CATEGORIES.items():
        rows = []
        for p in params:
            raw = p.get_value(result)
            if raw is None:
                disp = "—"
            elif isinstance(raw, bool):
                disp = "有効" if raw else "無効"
            elif isinstance(raw, float):
                if raw == int(raw):
                    disp = str(int(raw))
                else:
                    disp = f"{raw:.3f}".rstrip("0").rstrip(".")
            else:
                disp = str(raw)
            rows.append({
                "label": p.label,
                "value": disp,
                "unit": p.unit,
                "orca_key": p.orca_key or "(表示のみ)",
                "profile": p.profile,
                "low_conf": p.key in LOW_CONFIDENCE,
            })
        out.append((cat, rows))
    return out
