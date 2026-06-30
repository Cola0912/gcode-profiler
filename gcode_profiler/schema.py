# -*- coding: utf-8 -*-
"""
設定項目スキーマ (OrcaSlicer のプリンター/フィラメント/プロセス設定画面を踏襲)
=============================================================================
各設定グループ(printer/filament/process)を「サブタブ → セクション → フィールド」で定義。
G-code から復元可能な項目は src(解析結果パス)を持ち、自動でプリフィルされる。
"""
from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional


@dataclass
class Field:
    key: str                       # 値ストアの一意キー(canonical: "quality.layer_height" 等)
    label: str
    unit: str = ""
    kind: str = "num"              # num / int / bool / text / choice / xy
    choices: Optional[list] = None
    default: object = None
    src: Optional[str] = None      # 解析結果からのプリフィル元 "sec.field"
    low_conf: bool = False


@dataclass
class SubTab:
    title: str
    sections: list = dc_field(default_factory=list)  # [(section_title, [Field,...]), ...]
    special: Optional[str] = None   # None / "filaments" / "gcode"


# ===========================================================================
# プロセス設定 (品質/強度/速度/サポート/Multimaterial/その他/G-code)
# ===========================================================================
PROCESS = [
    SubTab("品質", [
        ("積層", [
            Field("quality.layer_height", "積層ピッチ", "mm", src="quality.layer_height"),
            Field("quality.first_layer_height", "最初の層の高さ", "mm", src="quality.first_layer_height"),
        ]),
        ("ライン幅", [
            Field("quality.outer_wall_width", "外壁", "mm", src="quality.outer_wall_width"),
            Field("quality.inner_wall_width", "内壁", "mm", src="quality.inner_wall_width"),
            Field("quality.sparse_infill_width", "インフィル", "mm", src="quality.sparse_infill_width"),
            Field("quality.top_surface_width", "上面", "mm", src="quality.top_surface_width"),
        ]),
    ]),
    SubTab("強度", [
        ("ウォール", [
            Field("strength.wall_loops", "ウォールのループ数", "本", kind="int",
                  src="strength.wall_loops", low_conf=True),
        ]),
        ("インフィル", [
            Field("strength.sparse_infill_density_pct", "インフィル密度", "%",
                  src="strength.sparse_infill_density_pct", low_conf=True),
        ]),
    ]),
    SubTab("速度", [
        ("ウォール", [
            Field("speed.outer_wall_speed", "外壁", "mm/s", src="speed.outer_wall_speed"),
            Field("speed.inner_wall_speed", "内壁", "mm/s", src="speed.inner_wall_speed"),
        ]),
        ("インフィル/上面", [
            Field("speed.sparse_infill_speed", "インフィル", "mm/s", src="speed.sparse_infill_speed"),
            Field("speed.top_surface_speed", "上面", "mm/s", src="speed.top_surface_speed"),
        ]),
        ("移動/その他", [
            Field("speed.travel_speed", "移動速度", "mm/s", src="speed.travel_speed"),
            Field("speed.first_layer_speed", "最初の層", "mm/s", src="speed.first_layer_speed"),
            Field("speed.outer_wall_accel", "加速度", "mm/s²", src="speed.outer_wall_accel"),
        ]),
    ]),
    SubTab("サポート", [
        ("サポート", [
            Field("strength.has_support", "サポート材を有効化", kind="bool", src="strength.has_support"),
            Field("speed.support_speed", "サポート速度", "mm/s", src="speed.support_speed"),
            Field("quality.support_width", "サポートのライン幅", "mm", src="quality.support_width"),
        ]),
        ("ラフト", [
            Field("strength.has_raft", "ラフトを有効化", kind="bool", src="strength.has_raft"),
        ]),
    ]),
    SubTab("Multimaterial", special="filaments"),
    SubTab("その他", [
        ("リトラクション", [
            Field("retraction.retract_length", "リトラクト長", "mm", src="retraction.retract_length"),
            Field("retraction.retract_speed", "リトラクト速度", "mm/s", src="retraction.retract_speed"),
            Field("retraction.deretract_speed", "戻し速度", "mm/s", src="retraction.deretract_speed"),
            Field("retraction.z_hop_height", "Zホップ高さ", "mm", src="retraction.z_hop_height"),
        ]),
    ]),
    SubTab("G-code", special="gcode"),
]


# ===========================================================================
# プリンター設定 (基本情報/プリンタG-code/Multimaterial/移動能力/Notes)
# ===========================================================================
PRINTER = [
    SubTab("基本情報", [
        ("造形可能領域", [
            Field("machine.printable_area", "造形可能領域", "", kind="text",
                  default="0x0,250x0,250x250,0x250"),
            Field("machine.bed_exclude_area", "除外領域", "", kind="text", default=""),
            Field("machine.printable_height", "造形可能高さ", "mm", src="meta.z_max"),
            Field("machine.nozzle_diameter", "ノズル径(推定)", "mm",
                  src="meta.nozzle_diameter_est", low_conf=True),
            Field("machine.nozzle_volume", "内腔容積", "mm³", default=0),
            Field("machine.z_offset", "Zオフセット", "mm", default=0),
        ]),
        ("高度な設定", [
            Field("machine.printer_structure", "Printer structure", "", kind="choice",
                  choices=["CoreXY", "i3", "Delta", "Hangprinter", "MarkForged"], default="CoreXY"),
            Field("machine.gcode_flavor", "G-codeスタイル", "", kind="choice",
                  choices=["Marlin(legacy)", "Marlin(firmware retract)", "Klipper",
                           "RepRap/Sprinter", "RepRapFirmware", "Smoothieware", "産業機(独自)"],
                  default="Marlin(legacy)"),
            Field("machine.inspect_first_layer", "1層目を検査", kind="bool", default=True),
        ]),
        ("冷却ファン", [
            Field("machine.fan_speedup_time", "Fan speed-up time", "s", default=0),
            Field("machine.fan_kickstart_time", "Fan kick-start time", "s", default=0),
        ]),
        ("押出機クリアランス", [
            Field("machine.clearance_radius", "半径", "mm", default=45),
            Field("machine.height_to_rod", "レールまでの高さ", "mm", default=40),
            Field("machine.height_to_lid", "蓋までの高さ", "mm", default=120),
        ]),
    ]),
    SubTab("プリンタG-code", special="gcode"),
    SubTab("Multimaterial", special="filaments"),
    SubTab("移動能力", [
        ("最大加速度", [
            Field("machine.max_accel_x", "X", "mm/s²", src="speed.outer_wall_accel"),
            Field("machine.max_accel_y", "Y", "mm/s²", src="speed.outer_wall_accel"),
            Field("machine.max_accel_z", "Z", "mm/s²", default=500),
            Field("machine.max_accel_e", "E", "mm/s²", default=5000),
        ]),
        ("最大速度", [
            Field("machine.max_speed_x", "X", "mm/s", src="speed.travel_speed"),
            Field("machine.max_speed_y", "Y", "mm/s", src="speed.travel_speed"),
            Field("machine.max_speed_z", "Z", "mm/s", default=20),
        ]),
    ]),
    SubTab("Notes", [
        ("メモ", [Field("machine.notes", "Notes", "", kind="text", default="")]),
    ]),
]


# ===========================================================================
# フィラメント設定 (基本情報/冷却/Multimaterial/Notes)
# ===========================================================================
# フィラメントは「フィラメントごとのタブ」を動的生成(special="per_filament")
FILAMENT = [
    SubTab("フィラメント", special="per_filament"),
    SubTab("冷却", [
        ("ファン", [
            Field("temperature.fan_max_pct", "最大ファン速度", "%", src="temperature.fan_max_pct"),
        ]),
    ]),
    SubTab("Notes", [
        ("メモ", [Field("filament.notes", "Notes", "", kind="text", default="")]),
    ]),
]


GROUPS = {
    "printer": ("🖨  プリンター設定", PRINTER),
    "filament": ("◎  フィラメント設定", FILAMENT),
    "process": ("≣  プロセス設定", PROCESS),
}


def all_fields(schema):
    for st in schema:
        for _sec, fields in st.sections:
            for f in fields:
                yield f


def default_values():
    """解析なしの既定値ストアと出所(全て default)を返す。"""
    values, prov = {}, {}
    for _gk, (_t, schema) in GROUPS.items():
        for f in all_fields(schema):
            if f.default is not None:
                values[f.key] = f.default
                prov[f.key] = "default"
    return values, prov


def prefill_values(result: dict):
    """解析結果から値ストアと出所を初期化する。
    返り値: (values, provenance)。provenance[key] は 'recovered' / 'default'。
    'recovered'=G-codeから復元, 'default'=取得できず既定値。"""
    values, prov = default_values()

    def get(path):
        sec, fld = path.split(".")
        return result.get(sec, {}).get(fld)

    for _gk, (_t, schema) in GROUPS.items():
        for f in all_fields(schema):
            if f.src:
                v = get(f.src)
                if v is not None:
                    values[f.key] = v
                    prov[f.key] = "recovered"
    # G-codeスタイルの推定(復元扱い)
    fs = result.get("meta", {}).get("feature_style", "")
    if "産業機" in fs:
        values["machine.gcode_flavor"] = "産業機(独自)"
        prov["machine.gcode_flavor"] = "recovered"
    return values, prov
