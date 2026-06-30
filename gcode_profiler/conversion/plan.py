# -*- coding: utf-8 -*-
"""
Conversion-plan engine (Phase 4).

Consumes a canonical profile + target and produces a conversion plan: per-key
entries with status/confidence/information-loss, required user inputs, and an
explanatory conversion score. All routing is canonical -> target (no pairwise).
Native serialization is Phase 5; this plan is the boundary.
"""
from __future__ import annotations

from . import registry as reg

# quality weight per relation/status
_QUALITY = {
    "ready": 1.0, "exact": 1.0, "rename": 1.0, "unit_conversion": 0.98,
    "derived": 0.90, "one_to_many": 0.85, "many_to_one": 0.65,
    "approximated": 0.55, "target_default": 0.35, "unsupported": 0.0,
    "unresolved": 0.0, "conflict": 0.6,
}
# settings weighted more heavily in the conversion score
_IMPORTANT = {
    "printer.extruder.nozzle_diameter": 3.0,
    "process.quality.layer_height": 3.0,
    "material.temperature.nozzle": 2.5,
    "process.strength.wall_loops": 2.0,
    "process.quality.line_width.outer_wall": 2.0,
    "process.speed.outer_wall": 1.5,
}


def _iter_leaves(node, prefix=""):
    for k, v in node.items():
        if k in ("schema_version", "source", "metadata", "unmapped"):
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict) and "effective" in v:
            yield key, v
        elif isinstance(v, dict):
            yield from _iter_leaves(v, key)


def _entry(ckey, source_value, effective_value, target_keys, relation, status,
           confidence, loss=None, warnings=None, value_layers=None, profile_kind=None):
    return {
        "canonical_key": ckey, "source_value": source_value,
        "effective_value": effective_value, "target_keys": list(target_keys),
        "relation": relation, "status": status, "confidence": round(confidence, 3),
        "information_loss": loss or [], "warnings": warnings or [],
        "value_layers": value_layers or {}, "profile_kind": profile_kind,
    }


def _fmt(value, value_mode):
    if value is None:
        return None
    if value_mode == "percentage":
        return f"{int(round(value))}%"
    if value_mode == "count":
        return int(round(value))
    return value


def build_plan(profile, target, output_mode="assisted_complete"):
    if not reg.supported(target):
        raise ValueError(f"unknown target: {target}")
    base_speed = _base_speed(profile)
    entries = []
    leaves = dict(_iter_leaves(profile))
    for ckey, vd in leaves.items():
        eff = vd.get("effective")
        mp = reg.mapping(target, ckey)
        conflict = vd.get("status") == "conflict"
        if mp is None:
            if eff is not None:
                entries.append(_entry(ckey, eff, None, [], "unsupported", "unsupported",
                                      0.0, loss=["ターゲットが未対応"]))
            continue
        if eff is None:
            continue
        rel = mp["relation"]
        if vd.get("status") == "application_default" or vd.get("source") == "target_default":
            tval, status, conf, loss, warn = (
                _fmt(eff, mp["value_mode"]), "target_default", 0.0,
                ["ターゲット既定値であり復元値ではない"], []
            )
        else:
            tval, status, conf, loss, warn = _resolve(rel, eff, mp, base_speed, target)
        if conflict:
            status = "conflict"
            warn = (warn or []) + [f"configured と emitted が不一致（{vd.get('configured')} vs {vd.get('emitted')}）"]
        entries.append(_entry(ckey, eff, tval, mp["target_keys"], rel, status, conf,
                              loss, warn, value_layers=_layers(vd),
                              profile_kind=mp.get("profile_kind")))
    required = _required_inputs(profile, leaves)
    score = _score(entries)
    return {
        "target": target,
        "entries": entries,
        "required_user_inputs": required,
        "warnings": ["native serialization は Phase 5（互換アダプタ経由）"],
        "conversion_score": score,
    }


def _base_speed(profile):
    """Base print speed for percentage-based targets (Simplify3D defaultSpeed)."""
    from ..canonical import effective_of
    return effective_of(profile, "process.speed.inner_wall")


def _layers(vd):
    return {k: vd.get(k) for k in ("configured", "emitted", "observed", "edited", "target_default")
            if vd.get(k) is not None}


def _resolve(rel, eff, mp, base_speed, target):
    vmode = mp["value_mode"]
    if rel in ("exact", "rename"):
        return _fmt(eff, vmode), "ready", _QUALITY[rel], [], []
    if rel == "unit_conversion":
        return round(eff * (mp["scale"] or 1.0), 3), "ready", _QUALITY["unit_conversion"], [], []
    if rel == "derived_percent":
        if not base_speed:
            return None, "unresolved", 0.0, ["ベース速度未確定"], ["ベース速度が必要"]
        pct = round(eff / base_speed * 100.0)
        loss = [] if pct <= 100 else ["%が100超（ベース速度要確認）"]
        return f"{pct}%", "derived", _QUALITY["derived"], loss, []
    if rel == "one_to_many":
        return _fmt(eff, vmode), "one_to_many", _QUALITY["one_to_many"], \
            ["inherited_from_default"], []
    if rel == "many_to_one":
        if mp.get("base"):
            if not base_speed:
                return None, "unresolved", 0.0, ["ベース速度未確定"], ["ベース速度が必要"]
            return f"{round(eff / base_speed * 100.0)}%", "many_to_one", _QUALITY["many_to_one"], \
                ["複数値を1つに集約"], []
        return _fmt(eff, vmode), "many_to_one", _QUALITY["many_to_one"], \
            ["複数値を1つに集約"], []
    if rel == "enum":
        return _resolve_enum(eff, target)
    return None, "unsupported", 0.0, ["未対応 relation"], []


def _resolve_enum(eff, target):
    table = reg.ENUM_MAPS.get("gcode_flavor", {})
    key = str(eff).lower().replace(" ", "").replace("-", "_")
    target_key = target
    if target_key == "bambu":
        target_key = "orca"
    elif target_key == "superslicer":
        target_key = "prusa"
    target_map = table.get(target_key, {})
    if key in target_map:
        return target_map[key], "ready", _QUALITY["rename"], [], []
    return key, "approximated", _QUALITY["approximated"], \
        ["enumを近似変換"], [f"{target} の正確なenum対応が未登録"]


def _required_inputs(profile, leaves):
    from ..canonical import effective_of
    out = []
    for ckey, meta in reg.REQUIRED_FIELDS.items():
        if effective_of(profile, ckey) is None:
            out.append({"canonical_key": ckey, "reason": meta["reason"],
                        "required_for": ["printer profile"], "suggested_value": None,
                        "suggestion_source": None, "confidence": 0.0,
                        "safety_level": meta["safety_level"]})
    # low-confidence nozzle diameter -> require confirmation
    nd = leaves.get("printer.extruder.nozzle_diameter")
    if nd and nd.get("status") == "estimated" and nd.get("confidence", 0) < 0.6:
        out.append({"canonical_key": "printer.extruder.nozzle_diameter",
                    "reason": "ノズル径が低信頼の推定値", "required_for": ["printer profile"],
                    "suggested_value": nd.get("effective"),
                    "suggestion_source": "statistics",
                    "confidence": nd.get("confidence", 0), "safety_level": "important"})
    # filament diameter absent
    if effective_of(profile, "material.filament.diameter") is None:
        out.append({"canonical_key": "material.filament.diameter",
                    "reason": "フィラメント径が不明", "required_for": ["filament profile"],
                    "suggested_value": 1.75, "suggestion_source": "assumption",
                    "confidence": 0.3, "safety_level": "important"})
    return out


def _score(entries):
    num = den = 0.0
    for e in entries:
        if e["effective_value"] is None and e["status"] != "unsupported":
            continue
        w = _IMPORTANT.get(e["canonical_key"], 1.0)
        q = _QUALITY.get(e["status"], 0.0)
        num += w * q
        den += w
    return round(num / den, 3) if den else 0.0
