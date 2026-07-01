# -*- coding: utf-8 -*-
"""native -> canonical mapping via reverse conversion.registry lookup (Phase 6).

The conversion registry declares canonical -> native mappings per target. Import
reverses that: native fields become the `configured` layer of a canonical
profile. Unit / percentage transforms are inverted. Unmapped native fields are
kept in `canonical.unmapped` (never discarded).

Only 1:1 relations (exact / rename / unit_conversion / enum) are inverted here.
one_to_many / many_to_one / derived_percent are ambiguous to reverse and are
left to their per-feature sibling entries (which map on their own); anything not
consumed lands in `unmapped`.
"""
from __future__ import annotations

from ..canonical import model as m
from ..conversion.registry import CAPABILITIES, ENUM_MAPS

# detection slicer label -> registry target key
SLICER_TO_TARGET = {
    "OrcaSlicer": "orca",
    "BambuStudio": "bambu",
    "PrusaSlicer": "prusa",
    "SuperSlicer": "superslicer",
    "Cura": "cura",
    "Simplify3D": "simplify3d",
}

_REVERSIBLE = {"exact", "rename", "unit_conversion", "enum"}


def build_reverse_index(target):
    """native_key -> (canonical_key, mapping) for 1:1 reversible relations."""
    index = {}
    for canonical_key, mp in CAPABILITIES.get(target, {}).items():
        if mp["relation"] not in _REVERSIBLE:
            continue
        keys = mp["target_keys"]
        if len(keys) != 1:
            continue
        native_key = keys[0]
        # first mapping wins (keeps the most specific/earliest declaration)
        index.setdefault(native_key, (canonical_key, mp))
    return index


def to_canonical(native_profile, target, source_slicer=None, source_version=None):
    """Build a canonical profile (configured layer) from a resolved
    NativeProfile. `native_profile.raw_fields` is expected to be effective
    (post-inheritance)."""
    prof = m.empty_profile()
    prof["source"] = {
        "source_slicer": source_slicer or native_profile.slicer,
        "source_version": source_version or native_profile.version,
        "analysis_mode": "native_profile",
        "firmware_candidate": None,
        "confidence": 0.9,
    }

    index = build_reverse_index(target)
    origin_map = getattr(native_profile, "origin_map", {})

    for native_key, nv in native_profile.raw_fields.items():
        hit = index.get(native_key)
        if hit is None:
            prof["unmapped"][native_key] = _unmapped_entry(nv)
            continue
        canonical_key, mp = hit
        value, warnings = _reverse_value(nv, mp)
        if value is None:
            prof["unmapped"][native_key] = _unmapped_entry(nv, note="値の逆変換に失敗")
            continue
        evidence = ["native profile (configured)"]
        origin = origin_map.get(native_key)
        if origin:
            evidence.append(f"origin: {origin}")
        cv = m.configured(value, unit=mp.get("unit"),
                          value_mode=mp.get("value_mode", "absolute"),
                          evidence=evidence, keys=[native_key])
        cv.warnings.extend(warnings)
        m.set_value(prof, canonical_key, cv)

    prof["metadata"] = {
        "display_name": native_profile.display_name,
        "profile_kind": native_profile.profile_kind,
        "inheritance_chain": getattr(native_profile, "inheritance_chain", []),
        "inheritance_warnings": getattr(native_profile, "inheritance_warnings", []),
    }
    return prof


# ---------------------------------------------------------------------------
def _reverse_value(nv, mp):
    """Invert a native value back to canonical units. Returns (value, warnings)."""
    warnings = []
    relation = mp["relation"]
    value = _scalar(nv, warnings)

    if value is None:
        return None, warnings

    if relation == "enum":
        canon = _reverse_enum(value)
        if canon is None:
            warnings.append(f"未知のenum値: {value}")
            return value, warnings   # keep raw; flag it
        return canon, warnings

    if relation == "unit_conversion" and mp.get("scale"):
        try:
            return float(value) / float(mp["scale"]), warnings
        except (TypeError, ValueError):
            warnings.append("単位逆変換に失敗")
            return None, warnings

    # exact / rename: value already in canonical representation
    return value, warnings


def _scalar(nv, warnings):
    """Unwrap Orca-style single-element arrays; warn on per-extruder arrays."""
    val = nv.parsed_value if nv.parsed_value is not None else nv.raw_value
    if isinstance(val, list):
        if len(val) == 1:
            return _coerce(val[0])
        if len(val) > 1:
            warnings.append("per-extruder配列: 先頭値のみ採用")
            return _coerce(val[0])
        return None
    return val


def _coerce(v):
    s = str(v).strip()
    if s.endswith("%"):
        try:
            return float(s[:-1])
        except ValueError:
            return s
    try:
        return int(s) if s.lstrip("-").isdigit() else float(s)
    except ValueError:
        return v


def _reverse_enum(native_value):
    """Search ENUM_MAPS for a native value; return the canonical enum token."""
    nv = str(native_value).strip().lower()
    for _name, table in ENUM_MAPS.items():
        for target, mapping in table.items():
            if target == "_canonical":
                continue
            for canon, native in mapping.items():
                if str(native).lower() == nv:
                    return canon
    return None


def _unmapped_entry(nv, note=None):
    d = {
        "raw_value": nv.raw_value,
        "parsed_value": nv.parsed_value,
        "native_type": nv.native_type,
        "value_mode": nv.value_mode,
    }
    if note:
        d["note"] = note
    return d
