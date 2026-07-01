# -*- coding: utf-8 -*-
"""
Target capability registry + version-aware mapping registry (Phase 4).

All conversion goes through canonical keys (no pairwise source->target). Each
mapping declares a relation; the plan engine (plan.py) resolves it. Capability
is NOT inferred from key-name similarity: only keys listed here are supported.

relation:
  exact | rename | unit_conversion | derived_percent | one_to_many |
  many_to_one | enum | approximated | unsupported
"""
from __future__ import annotations

# enum translation tables (extend as needed). Never copy enum strings blindly.
ENUM_MAPS = {
    "gcode_flavor": {
        "_canonical": ["marlin", "klipper", "reprap", "reprapfirmware", "smoothie"],
        "orca": {"marlin": "marlin", "klipper": "klipper", "reprap": "reprap",
                 "reprapfirmware": "reprapfirmware", "smoothie": "smoothie"},
        "prusa": {"marlin": "marlin", "klipper": "klipper", "reprap": "reprapsprinter",
                  "reprapfirmware": "reprapfirmware", "smoothie": "smoothie"},
    },
}


def _m(relation, target_keys, unit=None, scale=None, base=None, loss="none",
       profile_kind="process", value_mode="absolute"):
    return {"relation": relation, "target_keys": list(target_keys), "unit": unit,
            "scale": scale, "base": base, "loss_risk": loss,
            "profile_kind": profile_kind, "value_mode": value_mode}


# Speed canonical keys shared by builders
_SPEEDS = ["outer_wall", "inner_wall", "sparse_infill", "top_surface", "support",
           "travel", "initial_layer"]

# --- OrcaSlicer (and BambuStudio share the same key vocabulary; separate entry) ---
_ORCA = {
    "printer.basic_information.bed_shape": _m("rename", ["printable_area"],
                                              profile_kind="printer", value_mode="text"),
    "printer.basic_information.printable_height": _m("rename", ["printable_height"],
                                                     "mm", profile_kind="printer"),
    "printer.firmware.gcode_flavor": _m("enum", ["gcode_flavor"], profile_kind="printer", value_mode="enum"),
    "process.quality.layer_height": _m("exact", ["layer_height"], "mm"),
    "process.quality.initial_layer_height": _m("rename", ["initial_layer_print_height"], "mm"),
    "process.quality.line_width.default": _m("one_to_many", [
        "line_width", "outer_wall_line_width", "inner_wall_line_width",
        "sparse_infill_line_width", "top_surface_line_width",
    ], "mm"),
    "process.strength.wall_loops": _m("exact", ["wall_loops"], value_mode="count"),
    "process.strength.sparse_infill_density": _m("exact", ["sparse_infill_density"], value_mode="percentage"),
    "process.acceleration.default": _m("exact", ["default_acceleration"], "mm/s2"),
    "material.temperature.nozzle": _m("rename", ["nozzle_temperature"], "C", profile_kind="filament"),
    "material.temperature.bed": _m("rename", ["hot_plate_temp"], "C", profile_kind="filament"),
    "material.cooling.fan_max": _m("rename", ["fan_max_speed"], "%", profile_kind="filament", value_mode="percentage"),
    "printer.extruder.nozzle_diameter": _m("rename", ["nozzle_diameter"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_length": _m("rename", ["retraction_length"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_speed": _m("rename", ["retraction_speed"], "mm/s", profile_kind="printer"),
    "printer.extruder.z_hop": _m("rename", ["z_hop"], "mm", profile_kind="printer"),
}
for f in _SPEEDS:
    ok = {"outer_wall": "outer_wall_speed", "inner_wall": "inner_wall_speed",
          "sparse_infill": "sparse_infill_speed", "top_surface": "top_surface_speed",
          "support": "support_speed", "travel": "travel_speed",
          "initial_layer": "initial_layer_speed"}[f]
    _ORCA[f"process.speed.{f}"] = _m("rename" if f != "outer_wall" else "exact", [ok], "mm/s")
for f in ["outer_wall", "inner_wall", "sparse_infill", "top_surface", "support"]:
    _ORCA[f"process.quality.line_width.{f}"] = _m("rename", [f"{f}_line_width"], "mm")

# --- PrusaSlicer (SuperSlicer shares most; separate entry) ---
_PRUSA = {
    "printer.basic_information.bed_shape": _m("rename", ["bed_shape"],
                                              profile_kind="printer", value_mode="text"),
    "printer.basic_information.printable_height": _m("rename", ["max_print_height"],
                                                     "mm", profile_kind="printer"),
    "printer.firmware.gcode_flavor": _m("enum", ["gcode_flavor"], profile_kind="printer", value_mode="enum"),
    "process.quality.layer_height": _m("exact", ["layer_height"], "mm"),
    "process.quality.initial_layer_height": _m("rename", ["first_layer_height"], "mm"),
    "process.quality.line_width.default": _m("one_to_many", [
        "extrusion_width", "perimeter_extrusion_width",
        "external_perimeter_extrusion_width", "infill_extrusion_width",
    ], "mm"),
    "process.strength.wall_loops": _m("rename", ["perimeters"], value_mode="count"),
    "process.strength.sparse_infill_density": _m("rename", ["fill_density"], value_mode="percentage"),
    "process.acceleration.default": _m("exact", ["default_acceleration"], "mm/s2"),
    "material.temperature.nozzle": _m("rename", ["temperature"], "C", profile_kind="filament"),
    "material.temperature.bed": _m("rename", ["bed_temperature"], "C", profile_kind="filament"),
    "material.cooling.fan_max": _m("rename", ["max_fan_speed"], "%", profile_kind="filament", value_mode="percentage"),
    "material.filament.diameter": _m("rename", ["filament_diameter"], "mm", profile_kind="filament"),
    "printer.extruder.nozzle_diameter": _m("rename", ["nozzle_diameter"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_length": _m("rename", ["retract_length"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_speed": _m("rename", ["retract_speed"], "mm/s", profile_kind="printer"),
    "printer.extruder.z_hop": _m("rename", ["retract_lift"], "mm", profile_kind="printer"),
}
for f in _SPEEDS:
    pk = {"outer_wall": "external_perimeter_speed", "inner_wall": "perimeter_speed",
          "sparse_infill": "infill_speed", "top_surface": "top_solid_infill_speed",
          "support": "support_material_speed", "travel": "travel_speed",
          "initial_layer": "first_layer_speed"}[f]
    _PRUSA[f"process.speed.{f}"] = _m("rename", [pk], "mm/s")
for f, pk in [("outer_wall", "external_perimeter_extrusion_width"),
              ("inner_wall", "perimeter_extrusion_width"),
              ("sparse_infill", "infill_extrusion_width"),
              ("top_surface", "top_infill_extrusion_width"),
              ("support", "support_material_extrusion_width")]:
    _PRUSA[f"process.quality.line_width.{f}"] = _m("rename", [pk], "mm")

# --- Simplify3D: speeds are PERCENT of a base (defaultSpeed, mm/min) ---
_S3D = {
    "printer.firmware.gcode_flavor": _m("enum", ["firmwareConfiguration"], profile_kind="printer", value_mode="enum"),
    "process.quality.layer_height": _m("rename", ["layerHeight"], "mm"),
    "process.strength.wall_loops": _m("rename", ["perimeterOutlines"], value_mode="count"),
    "process.strength.sparse_infill_density": _m("rename", ["infillPercentage"], value_mode="percentage"),
    "process.quality.line_width.inner_wall": _m("rename", ["extruderWidth"], "mm"),
    "material.temperature.nozzle": _m("rename", ["temperatureSetpointTemperatures"], "C"),
    "printer.extruder.retraction_length": _m("rename", ["extruderRetractionDistance"], "mm", profile_kind="printer"),
    # base speed (mm/min) derived from the canonical speeds:
    "process.speed.inner_wall": _m("unit_conversion", ["defaultSpeed"], "mm/min", scale=60.0),
    # percentages of defaultSpeed:
    "process.speed.outer_wall": _m("derived_percent", ["outlineUnderspeed"],
                                   base="process.speed._base", value_mode="percentage"),
    "process.speed.support": _m("derived_percent", ["supportUnderspeed"],
                                base="process.speed._base", value_mode="percentage"),
    "process.speed.travel": _m("unit_conversion", ["rapidXYspeed"], "mm/min", scale=60.0),
    "printer.extruder.retraction_speed": _m("unit_conversion", ["extruderRetractionSpeed"],
                                            "mm/min", scale=60.0, profile_kind="printer"),
    "process.speed.bridge_external": _m("many_to_one", ["bridgeUnderspeed"],
                                        base="process.speed._base", value_mode="percentage"),
    "process.speed.bridge_internal": _m("many_to_one", ["bridgeUnderspeed"],
                                        base="process.speed._base", value_mode="percentage"),
}

# --- Cura: rename + unit; densities as count/percent ---
_CURA = {
    "printer.firmware.gcode_flavor": _m("enum", ["machine_gcode_flavor"], profile_kind="printer", value_mode="enum"),
    "process.quality.layer_height": _m("rename", ["layer_height"], "mm"),
    "process.quality.initial_layer_height": _m("rename", ["layer_height_0"], "mm"),
    "process.strength.wall_loops": _m("rename", ["wall_line_count"], value_mode="count"),
    "process.strength.sparse_infill_density": _m("rename", ["infill_sparse_density"], value_mode="percentage"),
    "process.speed.outer_wall": _m("rename", ["speed_wall_0"], "mm/s"),
    "process.speed.inner_wall": _m("rename", ["speed_wall_x"], "mm/s"),
    "process.speed.sparse_infill": _m("rename", ["speed_infill"], "mm/s"),
    "process.speed.travel": _m("rename", ["speed_travel"], "mm/s"),
    "process.speed.initial_layer": _m("rename", ["speed_layer_0"], "mm/s"),
    "material.temperature.nozzle": _m("rename", ["material_print_temperature"], "C", profile_kind="filament"),
    "material.temperature.bed": _m("rename", ["material_bed_temperature"], "C", profile_kind="filament"),
    "printer.extruder.nozzle_diameter": _m("rename", ["machine_nozzle_size"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_length": _m("rename", ["retraction_amount"], "mm", profile_kind="printer"),
    "printer.extruder.retraction_speed": _m("rename", ["retraction_speed"], "mm/s", profile_kind="printer"),
    "printer.extruder.z_hop": _m("rename", ["retraction_hop"], "mm", profile_kind="printer"),
    "process.speed.bridge_external": _m("many_to_one", ["speed_print_layer_0"], "mm/s",
                                        loss="medium"),
    "process.speed.bridge_internal": _m("many_to_one", ["speed_print_layer_0"], "mm/s",
                                        loss="medium"),
}

CAPABILITIES = {
    "orca": _ORCA, "bambu": dict(_ORCA), "prusa": _PRUSA,
    "superslicer": dict(_PRUSA), "cura": _CURA, "simplify3d": _S3D,
}

# fields each target REQUIRES from the user when not recoverable (safety-critical)
REQUIRED_FIELDS = {
    "printer.basic_information.bed_shape": {"safety_level": "critical",
                                            "reason": "造形可能領域はG-codeから復元不可"},
    "printer.basic_information.printable_height": {"safety_level": "important",
                                                   "reason": "造形可能高さは要確認"},
    "printer.firmware.gcode_flavor": {"safety_level": "important",
                                      "reason": "ファームウェア種別は誤ると危険"},
}


def supported(target):
    return target in CAPABILITIES


def mapping(target, canonical_key):
    return CAPABILITIES.get(target, {}).get(canonical_key)


def capability(target, canonical_key):
    mp = mapping(target, canonical_key)
    if mp is None:
        return {"supported": False, "representation": "unsupported", "loss_risk": "high"}
    return {"supported": True, "representation": mp["relation"],
            "target_keys": mp["target_keys"], "loss_risk": mp["loss_risk"],
            "profile_kind": mp["profile_kind"]}
