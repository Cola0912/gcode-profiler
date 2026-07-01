# -*- coding: utf-8 -*-
"""Shared JSON parser for the Orca/Bambu profile family (Phase 6).

Parses a native JSON preset into a NativeProfile preserving the original
representation. Slicer-specific semantics are handled by the adapter layer;
this module only parses structure (meta keys vs setting keys, inherits, arrays).
"""
from __future__ import annotations

import json
import os

from .base import NativeProfile, make_value

# Keys that describe the profile itself, not printable settings.
META_KEYS = {
    "name", "type", "inherits", "from", "version", "setting_id",
    "is_custom_defined", "filament_id", "instantiation", "filament_settings_id",
    "print_settings_id", "printer_settings_id", "compatible_printers",
    "compatible_printers_condition", "compatible_prints",
}

_KIND_FROM_TYPE = {"process": "process", "filament": "filament",
                   "machine": "printer", "printer": "printer"}


def parse_json(text, path, slicer):
    """Parse Orca/Bambu JSON text into a NativeProfile. Raises ValueError on
    malformed JSON."""
    obj = json.loads(text)
    if not isinstance(obj, dict):
        raise ValueError("JSON profile root must be an object")

    prof = NativeProfile(
        source_path=path,
        slicer=slicer,
        version=_as_scalar(obj.get("version")),
        profile_kind=_KIND_FROM_TYPE.get(str(obj.get("type", "")).lower(), "unknown"),
        display_name=_as_scalar(obj.get("name")) or os.path.basename(path),
        native_id=_as_scalar(obj.get("setting_id")),
    )

    inh = obj.get("inherits")
    if inh:
        # Orca/Bambu use a single string; be defensive about ';' separators.
        prof.parent_refs = [p.strip() for p in str(inh).split(";") if p.strip()]

    for key, raw in obj.items():
        if key in META_KEYS:
            continue
        prof.raw_fields[key] = make_value(key, raw)
        prof.ordering.append(key)
    return prof


def _as_scalar(v):
    """Orca stores many values as single-element arrays; unwrap for meta reads."""
    if isinstance(v, list):
        return v[0] if len(v) == 1 else v
    return v
