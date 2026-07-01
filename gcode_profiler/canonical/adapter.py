# -*- coding: utf-8 -*-
"""
Legacy <-> canonical adapter (Phase 1).

Converts the existing analyzer result dictionary into the canonical profile
with explicit provenance, and back (for exporters that still read legacy keys).
No source-slicer identity is required.
"""
from __future__ import annotations

from . import model as m

# legacy "section.field" -> canonical dotted key. One canonical owner per concept.
LEGACY_MAP = {
    "quality.layer_height": "process.quality.layer_height",
    "quality.first_layer_height": "process.quality.initial_layer_height",
    "quality.outer_wall_width": "process.quality.line_width.outer_wall",
    "quality.inner_wall_width": "process.quality.line_width.inner_wall",
    "quality.sparse_infill_width": "process.quality.line_width.sparse_infill",
    "quality.top_surface_width": "process.quality.line_width.top_surface",
    "quality.support_width": "process.quality.line_width.support",
    "speed.outer_wall_speed": "process.speed.outer_wall",
    "speed.inner_wall_speed": "process.speed.inner_wall",
    "speed.sparse_infill_speed": "process.speed.sparse_infill",
    "speed.top_surface_speed": "process.speed.top_surface",
    "speed.support_speed": "process.speed.support",
    "speed.travel_speed": "process.speed.travel",
    "speed.first_layer_speed": "process.speed.initial_layer",
    "speed.outer_wall_accel": "process.acceleration.default",
    "strength.wall_loops": "process.strength.wall_loops",
    "strength.sparse_infill_density_pct": "process.strength.sparse_infill_density",
    "temperature.nozzle_temp": "material.temperature.nozzle",
    "temperature.bed_temp": "material.temperature.bed",
    "temperature.chamber_temp": "material.temperature.chamber",
    "temperature.fan_max_pct": "material.cooling.fan_max",
    "retraction.retract_length": "printer.extruder.retraction_length",
    "retraction.retract_speed": "printer.extruder.retraction_speed",
    "retraction.deretract_speed": "printer.extruder.deretraction_speed",
    "retraction.z_hop_height": "printer.extruder.z_hop",
    "machine.printable_area": "printer.basic_information.bed_shape",
    "machine.printable_height": "printer.basic_information.printable_height",
    "machine.gcode_flavor": "printer.firmware.gcode_flavor",
    "machine.nozzle_diameter": "printer.extruder.nozzle_diameter",
    "meta.nozzle_diameter_est": "printer.extruder.nozzle_diameter",
    "meta.filament_diameter": "material.filament.diameter",
}
CANONICAL_TO_LEGACY = {v: k for k, v in LEGACY_MAP.items()}

_PERCENT_KEYS = {"strength.sparse_infill_density_pct", "temperature.fan_max_pct"}
_LOW_CONF_KEYS = {"strength.wall_loops", "strength.sparse_infill_density_pct",
                  "meta.nozzle_diameter_est"}
_EMITTED_PREFIX = ("temperature.",)


def _get(result, legacy_key):
    sec, fld = legacy_key.split(".", 1)
    return result.get(sec, {}).get(fld)


def _analysis_mode(result):
    meta = result.get("meta", {})
    method = str(meta.get("method", ""))
    if "埋め込み" in method or "直接読込" in method or "3mf" in method:
        return "native_metadata"
    if meta.get("feature_style") in ("Marker(産業機)", ";TYPE:/feature"):
        return "dialect_assisted"
    return "geometry_only"


def legacy_to_canonical(result):
    """Build a canonical profile from a legacy analyzer result dict."""
    prof = m.empty_profile()
    meta = result.get("meta", {})
    embedded = set(meta.get("embedded_fields", []))
    mode = _analysis_mode(result)

    prof["source"] = {
        "source_slicer": meta.get("source", "Unknown"),
        "source_version": None,
        "analysis_mode": mode,
        "firmware_candidate": None,
        "confidence": 0.0,
    }

    for legacy_key, canon_key in LEGACY_MAP.items():
        value = _get(result, legacy_key)
        vmode = "percentage" if legacy_key in _PERCENT_KEYS else "absolute"
        if value is None:
            cv = m.unknown(value_mode=vmode)
        elif legacy_key in embedded:
            cv = m.configured(value, value_mode=vmode, keys=[legacy_key],
                              evidence=["埋め込み設定（source profile）"])
        elif legacy_key.startswith(_EMITTED_PREFIX):
            cv = m.emitted(value, value_mode=vmode, keys=[legacy_key],
                           evidence=["G-codeコマンド由来"])
        elif legacy_key in _LOW_CONF_KEYS:
            cv = m.estimated(value, value_mode=vmode, keys=[legacy_key],
                             warnings=["ツールパスからの推定"])
        else:
            cv = m.observed(value, value_mode=vmode, keys=[legacy_key],
                            evidence=["ツールパス計算"])
        m.set_value(prof, canon_key, cv)

    _support_raft(result, prof)
    _filaments(result, prof)
    prof["metadata"] = {
        "total_layers": meta.get("total_layers"),
        "z_max": meta.get("z_max"),
        "tool_count": meta.get("tool_count"),
        "nozzle_confidence": meta.get("nozzle_confidence"),
    }
    return prof


def _support_raft(result, prof):
    strength = result.get("strength", {})
    has_sup = strength.get("has_support")
    has_raft = strength.get("has_raft")
    # path_present is observable from toolpaths; setting_enabled_state is NOT.
    m.set_value(prof, "process.support.path_present",
                m.observed(bool(has_sup), source="geometry", confidence=0.8,
                           value_mode="enum", evidence=["Support経路の有無"]))
    m.set_value(prof, "process.support.setting_enabled_state",
                m.unknown(value_mode="enum",
                          warnings=["サポート経路の有無からは設定の有効/無効を断定できない"]))
    m.set_value(prof, "process.support.raft.path_present",
                m.observed(bool(has_raft), source="geometry", confidence=0.8,
                           value_mode="enum", evidence=["Raft/負レイヤの有無"]))
    m.set_value(prof, "process.support.raft.setting_enabled_state",
                m.unknown(value_mode="enum",
                          warnings=["ラフト経路の有無からは設定の有効/無効を断定できない"]))
    # raft_layer_count must be derived from actual classified layers (deferred to Phase 3)
    m.set_value(prof, "process.support.raft.layer_count",
                m.unknown(value_mode="count",
                          warnings=["ラフト層数は実分類レイヤーから導出（Phase 3）"]))


def _filaments(result, prof):
    fils = result.get("filaments", [])
    for i, fl in enumerate(fils):
        base = f"material.per_tool.{i}"
        nt, bt = fl.get("nozzle_temp"), fl.get("bed_temp")
        m.set_value(prof, f"{base}.nozzle_temperature",
                    m.emitted(nt, unit="C") if nt is not None else m.unknown(unit="C"))
        m.set_value(prof, f"{base}.bed_temperature",
                    m.emitted(bt, unit="C") if bt is not None else m.unknown(unit="C"))
        mat = fl.get("material")
        m.set_value(prof, f"{base}.material_type",
                    m.estimated(mat, value_mode="enum",
                                confidence=(fl.get("material_confidence", 0) or 0) / 100.0,
                                warnings=["温度からの推定"]) if mat else m.unknown(value_mode="enum"))
        nd = fl.get("nozzle_diameter")
        if nd is not None:
            m.set_value(prof, f"{base}.nozzle_diameter",
                        m.estimated(nd, unit="mm", warnings=["ライン幅統計からの推定"]))


def canonical_to_legacy(prof):
    """Backward-compatible read: canonical effective values -> legacy result dict."""
    result = {"meta": {}, "quality": {}, "speed": {}, "strength": {},
              "temperature": {}, "retraction": {}, "machine": {}}
    for canon_key, legacy_key in CANONICAL_TO_LEGACY.items():
        eff = m.effective_of(prof, canon_key)
        if eff is None:
            continue
        sec, fld = legacy_key.split(".", 1)
        result.setdefault(sec, {})[fld] = eff
    # support/raft -> legacy booleans (true only when path present; else None)
    sp = m.get_value(prof, "process.support.path_present")
    rp = m.get_value(prof, "process.support.raft.path_present")
    result["strength"]["has_support"] = (sp or {}).get("effective") or None
    result["strength"]["has_raft"] = (rp or {}).get("effective") or None
    src = prof.get("source", {})
    result["meta"]["source"] = src.get("source_slicer")
    result["meta"]["analysis_mode"] = src.get("analysis_mode")
    return result
