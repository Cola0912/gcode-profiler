# -*- coding: utf-8 -*-
"""
復元プロファイルを各スライサーのプロファイル形式で書き出す。
返り値は (ファイル名, 文字列内容) のリスト。GUI 側がフォルダへ保存する。

対応ターゲット:
  - OrcaSlicer / BambuStudio : JSON (process + filament×ツール数 + machine)
  - PrusaSlicer / SuperSlicer : 単一 .ini (key = value)
  - Simplify3D               : .fff (XML)
  - Cura                     : .cfg (instance container, best-effort)
"""
from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# 共通アクセサ
# ---------------------------------------------------------------------------
def _get(result, path, default=None):
    sec, field = path.split(".")
    v = result.get(sec, {}).get(field)
    return default if v is None else v


def _num(result, path):
    v = _get(result, path)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _mget(result, key):
    return result.get("machine", {}).get(key)


# G-codeスタイル(画面表記) -> 各スライサーの flavor 値
_FLAVOR_ORCA = {
    "Marlin(legacy)": "marlin", "Marlin(firmware retract)": "marlin",
    "Klipper": "klipper", "RepRap/Sprinter": "reprap",
    "RepRapFirmware": "reprapfirmware", "Smoothieware": "smoothie",
    "産業機(独自)": "marlin",
}
_FLAVOR_PRUSA = {
    "Marlin(legacy)": "marlin", "Marlin(firmware retract)": "marlin",
    "Klipper": "klipper", "RepRap/Sprinter": "reprapsprinter",
    "RepRapFirmware": "reprapfirmware", "Smoothieware": "smoothie",
    "産業機(独自)": "marlin",
}


def _i(v):
    return None if v is None else str(int(round(v)))


def _f(v, nd=2):
    if v is None:
        return None
    return str(int(v)) if float(v) == int(v) else str(round(v, nd))


ORCA_VERSION = "2.2.0.0"


# ===========================================================================
# OrcaSlicer / BambuStudio  (JSON)
# ===========================================================================
def export_orca(result, name, printer_name=None, filament_name=None):
    files = []
    multi = result.get("meta", {}).get("tool_count", 1) > 1

    proc = {"type": "process", "name": name, "from": "User",
            "is_custom_defined": "1", "version": ORCA_VERSION}
    pmap = [
        ("layer_height", _f(_num(result, "quality.layer_height"))),
        ("initial_layer_print_height", _f(_num(result, "quality.first_layer_height"))),
        ("outer_wall_line_width", _f(_num(result, "quality.outer_wall_width"))),
        ("inner_wall_line_width", _f(_num(result, "quality.inner_wall_width"))),
        ("sparse_infill_line_width", _f(_num(result, "quality.sparse_infill_width"))),
        ("top_surface_line_width", _f(_num(result, "quality.top_surface_width"))),
        ("support_line_width", _f(_num(result, "quality.support_width"))),
        ("outer_wall_speed", _i(_num(result, "speed.outer_wall_speed"))),
        ("inner_wall_speed", _i(_num(result, "speed.inner_wall_speed"))),
        ("sparse_infill_speed", _i(_num(result, "speed.sparse_infill_speed"))),
        ("top_surface_speed", _i(_num(result, "speed.top_surface_speed"))),
        ("support_speed", _i(_num(result, "speed.support_speed"))),
        ("travel_speed", _i(_num(result, "speed.travel_speed"))),
        ("initial_layer_speed", _i(_num(result, "speed.first_layer_speed"))),
        ("default_acceleration", _i(_num(result, "speed.outer_wall_accel"))),
        ("wall_loops", _i(_num(result, "strength.wall_loops"))),
    ]
    dens = _num(result, "strength.sparse_infill_density_pct")
    if dens is not None:
        proc["sparse_infill_density"] = f"{int(round(dens))}%"
    if _get(result, "strength.has_support"):
        proc["enable_support"] = "1"
    if _get(result, "strength.has_raft"):
        proc["raft_layers"] = "2"
    for k, v in pmap:
        if v is not None:
            proc[k] = v
    files.append((f"{name}.process.json", _json(proc)))

    # フィラメント(ツールごと)
    fbase = filament_name or name
    for fl in result.get("filaments", [{"tool": 0}]):
        fname = fbase + (f".T{fl['tool']}" if multi else "")
        fil = {"type": "filament", "name": fname, "from": "User",
               "is_custom_defined": "1", "version": ORCA_VERSION}
        if fl.get("material"):
            fil["filament_type"] = [_orca_material(fl["material"])]
        if fl.get("nozzle_temp") is not None:
            fil["nozzle_temperature"] = [_i(fl["nozzle_temp"])]
            fil["nozzle_temperature_initial_layer"] = [_i(fl["nozzle_temp"])]
        if fl.get("bed_temp"):
            fil["hot_plate_temp"] = [_i(fl["bed_temp"])]
        fan = _num(result, "temperature.fan_max_pct")
        if fan is not None:
            fil["fan_max_speed"] = [_i(fan)]
        files.append((f"{fname}.filament.json", _json(fil)))

    # プリンタ(リトラクト + start/end/toolchange G-code + マシン諸元)
    tools = result.get("meta", {}).get("tool_count", 1)
    machine = {"type": "machine", "name": printer_name or name, "from": "User",
               "is_custom_defined": "1", "version": ORCA_VERSION}
    _orca_machine_extras(result, machine)
    rl = _num(result, "retraction.retract_length")
    rs = _num(result, "retraction.retract_speed")
    drs = _num(result, "retraction.deretract_speed")
    zh = _num(result, "retraction.z_hop_height")
    if rl is not None:
        machine["retraction_length"] = [_f(rl)] * tools
    if rs is not None:
        machine["retraction_speed"] = [_i(rs)] * tools
    if drs is not None:
        machine["deretraction_speed"] = [_i(drs)] * tools
    if zh is not None:
        machine["z_hop"] = [_f(zh)] * tools
    blocks = result.get("gcode_blocks", {})
    if blocks.get("start_gcode"):
        machine["machine_start_gcode"] = blocks["start_gcode"]
    if blocks.get("end_gcode"):
        machine["machine_end_gcode"] = blocks["end_gcode"]
    if blocks.get("toolchange_gcode"):
        machine["change_filament_gcode"] = blocks["toolchange_gcode"]
    files.append((f"{name}.machine.json", _json(machine)))
    return files


def _orca_material(name):
    """素材表記を Orca/Bambu の filament_type 値に正規化。"""
    if not name:
        return "PLA"
    n = name.upper()
    table = {"PEI/ULTEM": "PEI", "PA (NYLON)": "PA", "PPS / PPS-CF": "PPS"}
    if name in table:
        return table[name]
    for key in ("PLA", "PETG", "ABS", "ASA", "TPU", "PC", "PA", "PEEK", "PEI", "PPS", "PP"):
        if key in n:
            return key
    return name


def _orca_machine_extras(result, machine):
    """復元可能なマシン諸元を Orca machine JSON へ。"""
    def mn(k):
        v = _mget(result, k)
        return None if v is None else (str(int(v)) if isinstance(v, (int, float)) and float(v) == int(v)
                                       else str(v))
    pa = _mget(result, "printable_area")
    if pa:
        machine["printable_area"] = pa
    if _mget(result, "bed_exclude_area"):
        machine["bed_exclude_area"] = _mget(result, "bed_exclude_area")
    for k, ok in [("printable_height", "printable_height"),
                  ("clearance_radius", "extruder_clearance_radius"),
                  ("height_to_rod", "extruder_clearance_height_to_rod"),
                  ("height_to_lid", "extruder_clearance_height_to_lid"),
                  ("max_accel_x", "machine_max_acceleration_x"),
                  ("max_accel_y", "machine_max_acceleration_y"),
                  ("max_accel_z", "machine_max_acceleration_z"),
                  ("max_accel_e", "machine_max_acceleration_e"),
                  ("max_speed_x", "machine_max_speed_x"),
                  ("max_speed_y", "machine_max_speed_y"),
                  ("max_speed_z", "machine_max_speed_z")]:
        val = mn(k)
        if val is not None:
            machine[ok] = [val] if ok.startswith("machine_max") else val
    fl = _mget(result, "gcode_flavor")
    if fl in _FLAVOR_ORCA:
        machine["gcode_flavor"] = _FLAVOR_ORCA[fl]
    nd = _mget(result, "nozzle_diameter")
    if isinstance(nd, (int, float)):
        machine["nozzle_diameter"] = [str(nd)]


def _json(d):
    return json.dumps(d, ensure_ascii=False, indent=4)


# ===========================================================================
# PrusaSlicer / SuperSlicer  (.ini)
# ===========================================================================
def export_prusa(result, name, printer_name=None, filament_name=None):
    lines = [f"# Recovered by GcodeProfiler  (name: {name})"]
    kv = []

    def add(k, v):
        if v is not None:
            kv.append((k, v))

    add("layer_height", _f(_num(result, "quality.layer_height")))
    add("first_layer_height", _f(_num(result, "quality.first_layer_height")))
    add("external_perimeter_extrusion_width", _f(_num(result, "quality.outer_wall_width")))
    add("perimeter_extrusion_width", _f(_num(result, "quality.inner_wall_width")))
    add("infill_extrusion_width", _f(_num(result, "quality.sparse_infill_width")))
    add("top_infill_extrusion_width", _f(_num(result, "quality.top_surface_width")))
    add("support_material_extrusion_width", _f(_num(result, "quality.support_width")))
    add("external_perimeter_speed", _i(_num(result, "speed.outer_wall_speed")))
    add("perimeter_speed", _i(_num(result, "speed.inner_wall_speed")))
    add("infill_speed", _i(_num(result, "speed.sparse_infill_speed")))
    add("top_solid_infill_speed", _i(_num(result, "speed.top_surface_speed")))
    add("support_material_speed", _i(_num(result, "speed.support_speed")))
    add("travel_speed", _i(_num(result, "speed.travel_speed")))
    add("first_layer_speed", _i(_num(result, "speed.first_layer_speed")))
    add("default_acceleration", _i(_num(result, "speed.outer_wall_accel")))
    add("perimeters", _i(_num(result, "strength.wall_loops")))
    dens = _num(result, "strength.sparse_infill_density_pct")
    if dens is not None:
        add("fill_density", f"{int(round(dens))}%")
    add("support_material", "1" if _get(result, "strength.has_support") else "0")

    # フィラメント(マルチはカンマ区切り)
    temps = [fl.get("nozzle_temp") for fl in result.get("filaments", [])]
    temps = [t for t in temps if t is not None] or [_num(result, "temperature.nozzle_temp")]
    temps = [t for t in temps if t is not None]
    if temps:
        add("temperature", ",".join(_i(t) for t in temps))
    bed = _num(result, "temperature.bed_temp")
    add("bed_temperature", _i(bed))
    add("retract_length", _f(_num(result, "retraction.retract_length")))
    add("retract_speed", _i(_num(result, "retraction.retract_speed")))
    add("deretract_speed", _i(_num(result, "retraction.deretract_speed")))
    add("retract_lift", _f(_num(result, "retraction.z_hop_height")))

    # マシン諸元
    ph = _mget(result, "printable_height")
    if isinstance(ph, (int, float)):
        add("max_print_height", _i(ph))
    fl = _mget(result, "gcode_flavor")
    if fl in _FLAVOR_PRUSA:
        add("gcode_flavor", _FLAVOR_PRUSA[fl])
    nd = _mget(result, "nozzle_diameter")
    if isinstance(nd, (int, float)):
        add("nozzle_diameter", _f(nd))
    mats = [f.get("material") for f in result.get("filaments", []) if f.get("material")]
    if mats:
        add("filament_type", ",".join(_orca_material(m) for m in mats))

    blocks = result.get("gcode_blocks", {})
    if blocks.get("start_gcode"):
        add("start_gcode", blocks["start_gcode"].replace("\n", "\\n"))
    if blocks.get("end_gcode"):
        add("end_gcode", blocks["end_gcode"].replace("\n", "\\n"))
    if blocks.get("toolchange_gcode"):
        add("toolchange_gcode", blocks["toolchange_gcode"].replace("\n", "\\n"))

    for k, v in kv:
        lines.append(f"{k} = {v}")
    return [(f"{name}.ini", "\n".join(lines) + "\n")]


# ===========================================================================
# Simplify3D  (.fff XML, best-effort)
# ===========================================================================
def export_simplify3d(result, name, printer_name=None, filament_name=None):
    def tag(k, v):
        return f"  <{k}>{v}</{k}>" if v is not None else None

    body = [f'<?xml version="1.0"?>', f'<profile name="{name}" version="2023">']
    rows = [
        tag("layerHeight", _f(_num(result, "quality.layer_height"))),
        tag("topSolidLayers", "3"),
        tag("bottomSolidLayers", "3"),
        tag("perimeterOutlines", _i(_num(result, "strength.wall_loops"))),
        tag("extruderWidth", _f(_num(result, "quality.inner_wall_width"))),
    ]
    dens = _num(result, "strength.sparse_infill_density_pct")
    if dens is not None:
        rows.append(tag("infillPercentage", str(int(round(dens)))))
    sp = _num(result, "speed.inner_wall_speed")
    if sp is not None:
        rows.append(tag("defaultSpeed", _i(sp * 60)))     # S3D は mm/min
    rl = _num(result, "retraction.retract_length")
    if rl is not None:
        rows.append(tag("extruderRetractionDistance", _f(rl)))
    rs = _num(result, "retraction.retract_speed")
    if rs is not None:
        rows.append(tag("extruderRetractionSpeed", _i(rs * 60)))
    temps = [fl.get("nozzle_temp") for fl in result.get("filaments", []) if fl.get("nozzle_temp")]
    if temps:
        rows.append(tag("temperatureSetpointTemperatures", _i(temps[0])))
    blocks = result.get("gcode_blocks", {})
    if blocks.get("start_gcode"):
        sg = "".join(f"<line>{ln}</line>" for ln in blocks["start_gcode"].splitlines())
        rows.append(f"  <startingGcode>{sg}</startingGcode>")
    if blocks.get("end_gcode"):
        eg = "".join(f"<line>{ln}</line>" for ln in blocks["end_gcode"].splitlines())
        rows.append(f"  <endingGcode>{eg}</endingGcode>")
    body += [r for r in rows if r]
    body.append("</profile>")
    return [(f"{name}.fff", "\n".join(body) + "\n")]


# ===========================================================================
# Cura  (.cfg instance container, best-effort)
# ===========================================================================
def export_cura(result, name, printer_name=None, filament_name=None):
    vals = []

    def add(k, v):
        if v is not None:
            vals.append((k, v))

    add("layer_height", _f(_num(result, "quality.layer_height")))
    add("layer_height_0", _f(_num(result, "quality.first_layer_height")))
    add("wall_line_width_0", _f(_num(result, "quality.outer_wall_width")))
    add("wall_line_width_x", _f(_num(result, "quality.inner_wall_width")))
    add("infill_line_width", _f(_num(result, "quality.sparse_infill_width")))
    add("wall_line_count", _i(_num(result, "strength.wall_loops")))
    dens = _num(result, "strength.sparse_infill_density_pct")
    if dens is not None:
        add("infill_sparse_density", str(int(round(dens))))
    add("speed_wall_0", _i(_num(result, "speed.outer_wall_speed")))
    add("speed_wall_x", _i(_num(result, "speed.inner_wall_speed")))
    add("speed_infill", _i(_num(result, "speed.sparse_infill_speed")))
    add("speed_travel", _i(_num(result, "speed.travel_speed")))
    add("speed_layer_0", _i(_num(result, "speed.first_layer_speed")))
    temps = [fl.get("nozzle_temp") for fl in result.get("filaments", []) if fl.get("nozzle_temp")]
    if temps:
        add("material_print_temperature", _i(temps[0]))
    add("material_bed_temperature", _i(_num(result, "temperature.bed_temp")))
    add("retraction_amount", _f(_num(result, "retraction.retract_length")))
    add("retraction_speed", _i(_num(result, "retraction.retract_speed")))
    add("retraction_hop", _f(_num(result, "retraction.z_hop_height")))
    blocks = result.get("gcode_blocks", {})
    if blocks.get("start_gcode"):
        add("machine_start_gcode", blocks["start_gcode"].replace("\n", "\\n"))
    if blocks.get("end_gcode"):
        add("machine_end_gcode", blocks["end_gcode"].replace("\n", "\\n"))

    out = ["[general]", "version = 4", f"name = {name}", "definition = fdmprinter",
           "", "[metadata]", "type = quality_changes", "quality_type = normal",
           "setting_version = 22", "", "[values]"]
    out += [f"{k} = {v}" for k, v in vals]
    return [(f"{name}.cfg", "\n".join(out) + "\n")]


# ターゲット登録 (表示名 -> 関数)
TARGETS = {
    "OrcaSlicer / BambuStudio (JSON)": export_orca,
    "PrusaSlicer / SuperSlicer (INI)": export_prusa,
    "Simplify3D (FFF)": export_simplify3d,
    "Cura (CFG)": export_cura,
}


def export(result, name, target, printer_name=None, filament_name=None):
    return TARGETS[target](result, name, printer_name, filament_name)
