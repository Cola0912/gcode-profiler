# -*- coding: utf-8 -*-
"""
スライサー判定 & 埋め込み設定の取り込み
======================================
PrusaSlicer / SuperSlicer / Slic3r / OrcaSlicer / BambuStudio は G-code 末尾に
"; key = value" 形式で全設定を埋め込む。Simplify3D はヘッダに ";   key,value"。
これらが在る場合はツールパス逆算より正確なので、その値で上書きする。
Cura / Klipper / 生 RepRap / この産業機 など設定が無いものはツールパス逆算のまま。
"""
from __future__ import annotations

# "; key = value" 形式を使うスライサー(キー語彙は2系統)
PRUSA_FAMILY = {"PrusaSlicer", "SuperSlicer", "Slic3r", "OrcaSlicer", "BambuStudio"}


def detect_source(header: list, cfg: dict, s3d: dict) -> str:
    text = "\n".join(header).lower()
    table = [
        ("prusaslicer", "PrusaSlicer"),
        ("superslicer", "SuperSlicer"),
        ("orcaslicer", "OrcaSlicer"),
        ("bambustudio", "BambuStudio"),
        ("bambu", "BambuStudio"),
        ("slic3r", "Slic3r"),
        ("simplify3d", "Simplify3D"),
        ("ideamaker", "ideaMaker"),
        ("kisslicer", "KISSlicer"),
        ("cura", "Cura"),
    ]
    for needle, name in table:
        if needle in text:
            return name
    # ヘッダに署名が無い場合はキー語彙で推定
    if s3d:
        return "Simplify3D"
    if "outer_wall_speed" in cfg or "sparse_infill_density" in cfg:
        return "OrcaSlicer"
    if "external_perimeter_speed" in cfg or "perimeter_speed" in cfg:
        return "PrusaSlicer"
    if ";flavor:" in text or "cura" in text:
        return "Cura"
    return "不明"


def _clean(s: str) -> str:
    s = s.strip()
    if "," in s:                 # マルチエクストルーダ等のリストは先頭値
        s = s.split(",")[0].strip()
    return s


def _num(s, base=None):
    """数値/百分率をパース。% は base に対する割合。auto(=0/空)は None。"""
    if s is None:
        return None
    s = _clean(str(s))
    if s == "" or s == "0" or s == "nil":
        return None
    try:
        if s.endswith("%"):
            p = float(s[:-1])
            return p / 100.0 * base if base is not None else None
        return float(s)
    except ValueError:
        return None


def _first(cfg: dict, keys):
    for k in keys:
        if k in cfg and str(cfg[k]).strip() != "":
            return cfg[k]
    return None


def apply_embedded(result: dict) -> dict:
    raw = result.get("_embedded", {})
    cfg = raw.get("config_kv", {}) or {}
    s3d = raw.get("s3d_kv", {}) or {}
    header = raw.get("header", []) or []

    source = detect_source(header, cfg, s3d)
    result["meta"]["source"] = source

    fields = []
    if cfg and source in PRUSA_FAMILY:
        fields = _overlay_prusa_orca(result, cfg)
    elif s3d and source == "Simplify3D":
        fields = _overlay_s3d(result, s3d)

    if fields:
        result["meta"]["method"] = f"埋め込み設定（{source}）を直接読込"
        result["meta"]["embedded_fields"] = fields
    result.pop("_embedded", None)
    return result


def apply_bambu_config(result: dict, cfg: dict) -> list:
    """BambuStudio/OrcaSlicer の 3mf 内 project_settings.config(JSON) を上書き適用。
    キー語彙は Orca と共通なので _overlay_prusa_orca を再利用する。"""
    # 配列は先頭値に潰してフラット化
    flat = {}
    for k, v in cfg.items():
        if isinstance(v, list):
            if v:
                flat[k] = v[0]
        elif isinstance(v, (str, int, float)):
            flat[k] = v
    flat = {k: str(v) for k, v in flat.items()}
    fields = _overlay_prusa_orca(result, flat)

    # マルチフィラメント: nozzle_temperature 配列からツール別に復元
    temps = cfg.get("nozzle_temperature") or cfg.get("nozzle_temperature_initial_layer")
    beds = cfg.get("hot_plate_temp") or cfg.get("bed_temperature")
    if isinstance(temps, list) and len(temps) > 1:
        fils = []
        for i, t in enumerate(temps):
            bed = beds[i] if isinstance(beds, list) and i < len(beds) else None
            fils.append({"tool": i, "nozzle_temp": _num(t),
                         "bed_temp": _num(bed) if bed is not None else None,
                         "retract_length": _num(_first(cfg, ["retraction_length"]))})
        result["filaments"] = fils
        result["meta"]["tool_count"] = len(fils)
        result["meta"]["tools_used"] = list(range(len(fils)))

    result["meta"]["source"] = "BambuStudio/OrcaSlicer (3mf)"
    result["meta"]["method"] = "3mf埋め込み設定（JSON）を直接読込"
    if fields:
        result["meta"]["embedded_fields"] = fields
    return fields


def _set(result, path, value, fields):
    if value is None:
        return
    sec, field = path.split(".")
    result[sec][field] = value
    fields.append(path)


def _overlay_prusa_orca(result, cfg) -> list:
    """PrusaSlicer系/Orca系の "; key = value" を canonical 結果へ上書き"""
    f = []

    # --- 品質 ---
    lh = _num(_first(cfg, ["layer_height"]))
    _set(result, "quality.layer_height", lh, f)
    flh = _num(_first(cfg, ["first_layer_height", "initial_layer_print_height"]), base=lh)
    _set(result, "quality.first_layer_height", flh, f)

    default_w = _num(_first(cfg, ["extrusion_width", "line_width"]), base=lh)
    for path, keys in [
        ("quality.outer_wall_width", ["external_perimeter_extrusion_width", "outer_wall_line_width"]),
        ("quality.inner_wall_width", ["perimeter_extrusion_width", "inner_wall_line_width"]),
        ("quality.sparse_infill_width", ["infill_extrusion_width", "sparse_infill_line_width"]),
        ("quality.top_surface_width", ["top_infill_extrusion_width", "top_surface_line_width"]),
        ("quality.support_width", ["support_material_extrusion_width", "support_line_width"]),
    ]:
        w = _num(_first(cfg, keys), base=lh)
        _set(result, path, w if w is not None else default_w, f)

    # --- 速度 (mm/s) ---
    inner = _num(_first(cfg, ["perimeter_speed", "inner_wall_speed"]))
    _set(result, "speed.inner_wall_speed", inner, f)
    outer = _num(_first(cfg, ["external_perimeter_speed", "outer_wall_speed"]), base=inner)
    _set(result, "speed.outer_wall_speed", outer, f)
    infill = _num(_first(cfg, ["infill_speed", "sparse_infill_speed"]))
    _set(result, "speed.sparse_infill_speed", infill, f)
    solid = _num(_first(cfg, ["solid_infill_speed", "internal_solid_infill_speed"]), base=infill)
    top = _num(_first(cfg, ["top_solid_infill_speed", "top_surface_speed"]),
               base=(solid if solid else infill))
    _set(result, "speed.top_surface_speed", top, f)
    _set(result, "speed.support_speed",
         _num(_first(cfg, ["support_material_speed", "support_speed"])), f)
    _set(result, "speed.travel_speed", _num(_first(cfg, ["travel_speed"])), f)
    _set(result, "speed.first_layer_speed",
         _num(_first(cfg, ["first_layer_speed", "initial_layer_speed"]), base=inner), f)
    _set(result, "speed.outer_wall_accel",
         _num(_first(cfg, ["outer_wall_acceleration", "perimeter_acceleration",
                           "default_acceleration"])), f)

    # --- 強度 ---
    _set(result, "strength.wall_loops",
         _int(_first(cfg, ["perimeters", "wall_loops"])), f)
    dens_raw = _first(cfg, ["fill_density", "sparse_infill_density"])
    if dens_raw is not None:
        ds = _clean(str(dens_raw)).rstrip("%")
        try:
            dv = float(ds)
        except ValueError:
            dv = None
        if dv is not None:
            # "20%"->20, "0.2"->20%(0..1 割合表記)
            _set(result, "strength.sparse_infill_density_pct",
                 round(dv * 100) if dv <= 1.0 else round(dv), f)
    sup = _first(cfg, ["support_material", "enable_support"])
    if sup is not None:
        _set(result, "strength.has_support", _clean(sup) in ("1", "true"), f)

    # --- 温度/ファン ---
    _set(result, "temperature.nozzle_temp",
         _num(_first(cfg, ["temperature", "nozzle_temperature"])), f)
    _set(result, "temperature.bed_temp",
         _num(_first(cfg, ["bed_temperature", "first_layer_bed_temperature", "hot_plate_temp"])), f)
    _set(result, "temperature.chamber_temp",
         _num(_first(cfg, ["chamber_temperature"])), f)
    _set(result, "temperature.fan_max_pct",
         _num(_first(cfg, ["max_fan_speed", "fan_max_speed"])), f)

    # --- リトラクト ---
    _set(result, "retraction.retract_length",
         _num(_first(cfg, ["retract_length", "retraction_length"])), f)
    _set(result, "retraction.retract_speed",
         _num(_first(cfg, ["retract_speed", "retraction_speed"])), f)
    _set(result, "retraction.deretract_speed",
         _num(_first(cfg, ["deretract_speed", "retract_speed", "deretraction_speed"])), f)
    _set(result, "retraction.z_hop_height",
         _num(_first(cfg, ["retract_lift", "z_hop"])), f)

    fd = _num(_first(cfg, ["filament_diameter"]))
    if fd:
        result["meta"]["filament_diameter"] = fd
    return f


def _int(s):
    v = _num(s)
    return int(round(v)) if v is not None else None


def _overlay_s3d(result, s3d) -> list:
    """Simplify3D ";   key,value"。明確に取れる項目のみ上書き(速度等は逆算を優先)。"""
    f = []
    _set(result, "quality.layer_height", _num(s3d.get("layerHeight")), f)
    _set(result, "strength.wall_loops", _int(s3d.get("perimeterOutlines")), f)
    dens = _num(s3d.get("infillPercentage"))
    _set(result, "strength.sparse_infill_density_pct",
         round(dens) if dens is not None else None, f)
    # 既定速度(mm/min)から外周/インフィルを近似
    base = _num(s3d.get("defaultSpeed"))
    if base:
        base_mms = base / 60.0
        ou = _num(s3d.get("outlineUnderspeed"))
        _set(result, "speed.outer_wall_speed",
             round(base_mms * ou, 1) if ou else round(base_mms, 1), f)
        _set(result, "speed.inner_wall_speed", round(base_mms, 1), f)
        _set(result, "speed.sparse_infill_speed", round(base_mms, 1), f)
    rx = _num(s3d.get("rapidXYspeed"))
    if rx:
        _set(result, "speed.travel_speed", round(rx / 60.0, 1), f)
    _set(result, "retraction.retract_length", _num(s3d.get("extruderRetractionDistance")), f)
    rs = _num(s3d.get("extruderRetractionSpeed"))
    if rs:
        _set(result, "retraction.retract_speed", round(rs / 60.0, 1), f)
    return f
