# -*- coding: utf-8 -*-
"""Extract OrcaSlicer parameter catalog from official source definitions.

Usage:
  python tools/extract_orca_parameters.py --source .catalog_sources/OrcaSlicer-v2.3.0 --version 2.3
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gcode_profiler.conversion.registry import CAPABILITIES  # noqa
from gcode_profiler.parameter_catalogs import CATALOG_SCHEMA_VERSION, coverage_report  # noqa


TYPE_MAP = {
    "coBool": ("bool", None, "absolute"),
    "coFloat": ("float", None, "absolute"),
    "coFloats": ("array", None, "absolute"),
    "coInt": ("int", None, "count"),
    "coInts": ("array", None, "count"),
    "coString": ("string", None, "absolute"),
    "coStrings": ("array", None, "absolute"),
    "coEnum": ("enum", None, "enum"),
    "coEnums": ("array", None, "enum"),
    "coPercent": ("percentage", "%", "percentage"),
    "coPercents": ("array", "%", "percentage"),
    "coPoints": ("array", None, "absolute"),
}

MODE_MAP = {
    "comSimple": "basic",
    "comAdvanced": "advanced",
    "comExpert": "expert",
    "comDevelop": "expert",
}

LINE_WIDTH_MAP = {
    "line_width": "process.quality.line_width.default",
    "initial_layer_line_width": "process.quality.line_width.initial_layer",
    "outer_wall_line_width": "process.quality.line_width.outer_wall",
    "inner_wall_line_width": "process.quality.line_width.inner_wall",
    "top_surface_line_width": "process.quality.line_width.top_surface",
    "bottom_surface_line_width": "process.quality.line_width.bottom_surface",
    "internal_solid_infill_line_width": "process.quality.line_width.internal_solid_infill",
    "sparse_infill_line_width": "process.quality.line_width.sparse_infill",
    "support_line_width": "process.quality.line_width.support",
    "support_interface_line_width": "process.quality.line_width.support_interface",
    "bridge_line_width": "process.quality.line_width.bridge",
    "gap_fill_line_width": "process.quality.line_width.gap_fill",
    "skirt_line_width": "process.quality.line_width.skirt",
    "brim_line_width": "process.quality.line_width.brim",
    "raft_line_width": "process.quality.line_width.raft",
}

CANONICAL_OVERRIDES = {
    "layer_height": "process.quality.layer_height",
    "initial_layer_print_height": "process.quality.initial_layer_height",
    "wall_loops": "process.strength.wall_loops",
    "sparse_infill_density": "process.strength.sparse_infill_density",
    "outer_wall_speed": "process.speed.outer_wall",
    "inner_wall_speed": "process.speed.inner_wall",
    "sparse_infill_speed": "process.speed.sparse_infill",
    "top_surface_speed": "process.speed.top_surface",
    "support_speed": "process.speed.support",
    "travel_speed": "process.speed.travel",
    "initial_layer_speed": "process.speed.initial_layer",
    "default_acceleration": "process.acceleration.default",
    "nozzle_temperature": "material.temperature.nozzle",
    "nozzle_temperature_initial_layer": "material.temperature.nozzle.initial_layer",
    "hot_plate_temp": "material.temperature.bed",
    "fan_max_speed": "material.cooling.fan_max",
    "filament_diameter": "material.filament.diameter",
    "nozzle_diameter": "printer.extruder.nozzle_diameter",
    "retraction_length": "printer.extruder.retraction_length",
    "retraction_speed": "printer.extruder.retraction_speed",
    "deretraction_speed": "printer.extruder.deretraction_speed",
    "z_hop": "printer.extruder.z_hop",
    "printable_area": "printer.basic_information.bed_shape",
    "printable_height": "printer.basic_information.printable_height",
    "gcode_flavor": "printer.firmware.gcode_flavor",
}
CANONICAL_OVERRIDES.update(LINE_WIDTH_MAP)

JA_LABELS = {
    "line_width": "デフォルトライン幅",
    "outer_wall_line_width": "外壁ライン幅",
    "inner_wall_line_width": "内壁ライン幅",
    "sparse_infill_line_width": "スパースインフィルライン幅",
    "top_surface_line_width": "上面ライン幅",
    "support_line_width": "サポートライン幅",
    "layer_height": "積層ピッチ",
    "initial_layer_print_height": "初期レイヤー高さ",
    "wall_loops": "壁ループ数",
    "sparse_infill_density": "インフィル密度",
    "outer_wall_speed": "外壁速度",
    "inner_wall_speed": "内壁速度",
    "travel_speed": "移動速度",
    "nozzle_temperature": "ノズル温度",
    "hot_plate_temp": "ベッド温度",
    "nozzle_diameter": "ノズル径",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="OrcaSlicer source checkout")
    ap.add_argument("--version", default="2.3")
    ap.add_argument("--tag", default="v2.3.0")
    ap.add_argument("--output", default=None)
    ns = ap.parse_args()

    source = Path(ns.source)
    cpp = source / "src" / "libslic3r" / "PrintConfig.cpp"
    if not cpp.exists():
        raise SystemExit(f"PrintConfig.cpp not found: {cpp}")

    text = cpp.read_text(encoding="utf-8", errors="replace")
    extruder_keys = _option_key_set(text, "m_extruder_option_keys")
    filament_keys = _option_key_set(text, "m_filament_option_keys")
    params = []
    fff_text = text
    sla_pos = text.find("void PrintConfigDef::init_sla_params")
    if sla_pos > 0:
        fff_text = text[:sla_pos]
    for order, block in enumerate(_option_blocks(fff_text)):
        p = _parse_block(block, order, cpp, ns.tag, extruder_keys, filament_keys)
        if p:
            params.append(p)
    params = _dedupe(params)
    data = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "slicer": "OrcaSlicer",
        "version": ns.version,
        "source": {
            "official_repository": "https://github.com/OrcaSlicer/OrcaSlicer",
            "tag": ns.tag,
            "files": ["src/libslic3r/PrintConfig.cpp"],
            "date_checked": str(date.today()),
        },
        "generated_at": str(date.today()),
        "parameters": params,
        "coverage": coverage_report(params),
    }
    out = Path(ns.output) if ns.output else Path("parameter_catalogs") / "orca" / ns.version / "parameters.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.parent / "coverage.json").write_text(
        json.dumps(data["coverage"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out} ({len(params)} parameters)")
    print(json.dumps(data["coverage"], ensure_ascii=False, indent=2))


def _option_blocks(text):
    pat = re.compile(r'def\s*=\s*this->add\("([^"]+)",\s*(co\w+)\);')
    matches = list(pat.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield text[m.start():end]


def _parse_block(block, order, cpp, tag, extruder_keys, filament_keys):
    m = re.search(r'def\s*=\s*this->add\("([^"]+)",\s*(co\w+)\);', block)
    if not m:
        return None
    key, ctype = m.group(1), m.group(2)
    native_type, unit, value_mode = TYPE_MAP.get(ctype, ("string", None, "unknown"))
    unit = _unit(block) or unit
    canonical_key = _canonical_key(key)
    visibility = MODE_MAP.get(_assign(block, "mode"), "advanced")
    category = _string_assign(block, "category") or _category_for(key)
    section = _section_for(key, category)
    profile_kind = _profile_kind(key, category, extruder_keys, filament_keys)
    default = _default_value(block)
    enum_values = re.findall(r'enum_values\.push_back\("([^"]+)"\)', block)
    return {
        "slicer": "OrcaSlicer",
        "version_range": tag,
        "profile_kind": profile_kind,
        "native_key": key,
        "canonical_key": canonical_key,
        "mapping_status": "mapped" if canonical_key else "native_only",
        "label": _string_assign(block, "label") or _string_assign(block, "full_label") or key,
        "label_ja": JA_LABELS.get(key),
        "description": _string_assign(block, "tooltip") or "",
        "category": category,
        "section": section,
        "order": order,
        "native_type": native_type,
        "unit": unit,
        "value_mode": value_mode,
        "default": default,
        "minimum": _number_assign(block, "min"),
        "maximum": _number_assign(block, "max"),
        "step": _number_assign(block, "step"),
        "enum_values": enum_values,
        "per_tool": key in extruder_keys or key in filament_keys or native_type == "array",
        "nullable": True,
        "visibility": visibility,
        "enabled_if": [],
        "visible_if": [],
        "conflicts_with": [],
        "requires": [],
        "deprecated": False,
        "replacement_key": None,
        "recovery_capability": _recovery_capability(key, canonical_key),
        "source_reference": {
            "repository": "OrcaSlicer/OrcaSlicer",
            "tag": tag,
            "file": "src/libslic3r/PrintConfig.cpp",
            "line": _line_number(cpp, block),
        },
        "verification_status": "partially_verified" if canonical_key else "unverified",
        "importable": True,
        "exportable": True,
    }


def _dedupe(params):
    out = {}
    for p in params:
        out[p["native_key"]] = p
    return sorted(out.values(), key=lambda p: p["order"])


def _option_key_set(text, name):
    m = re.search(name + r"\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        return set()
    return set(re.findall(r'"([^"]+)"', m.group(1)))


def _string_assign(block, attr):
    m = re.search(rf'def->{attr}\s*=\s*(.*?);', block, re.S)
    if not m:
        return None
    return _join_cpp_strings(m.group(1)).strip() or None


def _join_cpp_strings(expr):
    strings = re.findall(r'(?:L|_)?\("([^"]*)"\)|"([^"]*)"', expr, re.S)
    parts = []
    for a, b in strings:
        parts.append(a or b)
    return " ".join(p.replace("\\n", " ").strip() for p in parts if p is not None)


def _assign(block, attr):
    m = re.search(rf'def->{attr}\s*=\s*([^;]+);', block)
    return m.group(1).strip() if m else None


def _number_assign(block, attr):
    m = re.search(rf'def->{attr}\s*=\s*(-?\d+(?:\.\d+)?)', block)
    if not m:
        return None
    v = float(m.group(1))
    return int(v) if v.is_integer() else v


def _unit(block):
    return _string_assign(block, "sidetext")


def _default_value(block):
    m = re.search(r'set_default_value\(new\s+ConfigOption(\w+)\((.*?)\)\)', block, re.S)
    if not m:
        return None
    typ, raw = m.group(1), m.group(2).strip()
    if typ == "Bool":
        return raw.lower() == "true"
    if typ in ("Float", "Percent"):
        return _to_float(raw)
    if typ == "Int":
        try:
            return int(float(raw))
        except ValueError:
            return None
    if typ == "String":
        s = _join_cpp_strings(raw)
        return s if s != "" else ""
    if typ == "Enum":
        return raw
    return None


def _to_float(raw):
    m = re.search(r'-?\d+(?:\.\d+)?', raw)
    if not m:
        return None
    v = float(m.group(0))
    return int(v) if v.is_integer() else v


def _canonical_key(native_key):
    if native_key in CANONICAL_OVERRIDES:
        return CANONICAL_OVERRIDES[native_key]
    for ckey, spec in CAPABILITIES["orca"].items():
        if native_key in spec.get("target_keys", []):
            return ckey
    return None


def _profile_kind(key, category, extruder_keys, filament_keys):
    if key in filament_keys or key.startswith("filament_") or "temperature" in key or "fan_" in key:
        return "filament"
    if key in extruder_keys or key in {
        "printable_area", "bed_exclude_area", "printable_height", "gcode_flavor",
        "machine_max_acceleration_x", "machine_max_speed_x", "nozzle_diameter",
    } or key.startswith(("machine_", "extruder_", "retraction_", "retract_", "wipe", "z_hop")):
        return "printer"
    return "process"


def _category_for(key):
    if key.startswith(("support", "tree_", "organic_")):
        return "Support"
    if "infill" in key:
        return "Strength"
    if "speed" in key or "acceleration" in key or "jerk" in key:
        return "Speed"
    if "temperature" in key or "fan" in key or "cool" in key:
        return "Filament"
    if "line_width" in key or "layer" in key or "seam" in key:
        return "Quality"
    if "brim" in key or "skirt" in key or "raft" in key:
        return "Bed adhesion"
    if "machine" in key or "printable" in key or "gcode" in key:
        return "Printer"
    return "Other"


def _section_for(key, category):
    if "line_width" in key:
        return "Line width"
    if "layer" in key:
        return "Layering"
    if "wall" in key or "perimeter" in key:
        return "Walls"
    if "infill" in key:
        return "Infill"
    if "support" in key:
        return "Support"
    if "temperature" in key or "temp" in key:
        return "Temperature"
    if "fan" in key or "cool" in key:
        return "Cooling"
    if "speed" in key:
        return "Speed"
    if "acceleration" in key or "jerk" in key:
        return "Acceleration"
    if "retract" in key or "wipe" in key or "z_hop" in key:
        return "Retraction"
    if "gcode" in key:
        return "Custom G-code"
    return category or "General"


def _recovery_capability(key, canonical_key):
    caps = {
        "explicit_metadata_recoverable": bool(canonical_key),
        "runtime_command_recoverable": key in {
            "nozzle_temperature", "hot_plate_temp", "fan_max_speed", "gcode_flavor",
        },
        "geometry_recoverable": key in LINE_WIDTH_MAP or key in {
            "layer_height", "initial_layer_print_height",
        },
        "statistically_estimable": key in {
            "wall_loops", "sparse_infill_density", "nozzle_diameter",
        },
        "profile_only": canonical_key is None,
        "target_only": False,
    }
    return caps


def _line_number(path, block):
    # Cheap line lookup; enough for a source reference.
    text = path.read_text(encoding="utf-8", errors="replace")
    idx = text.find(block[:80])
    return text[:idx].count("\n") + 1 if idx >= 0 else None


if __name__ == "__main__":
    main()
