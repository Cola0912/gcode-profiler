# -*- coding: utf-8 -*-
"""Native profile model + value records (Phase 6). Preserves original representation."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class NativeValue:
    native_key: str
    raw_value: Any                 # original text / list / scalar
    parsed_value: Any = None       # numeric when applicable
    native_type: str = "text"      # number_string | number | bool | array | text
    unit: Optional[str] = None
    value_mode: str = "absolute"   # absolute | percentage | ...
    source_location: dict = field(default_factory=dict)


@dataclass
class NativeProfile:
    source_path: str
    slicer: str
    version: Optional[str] = None
    profile_kind: str = "unknown"   # process | filament | printer | bundle | unknown
    display_name: str = ""
    native_id: Optional[str] = None
    parent_refs: List[str] = field(default_factory=list)
    raw_fields: Dict[str, NativeValue] = field(default_factory=dict)
    unknown_fields: Dict[str, NativeValue] = field(default_factory=dict)
    comments: List[str] = field(default_factory=list)
    ordering: List[str] = field(default_factory=list)
    encoding: str = "utf-8"
    sub_profiles: List["NativeProfile"] = field(default_factory=list)  # bundle members


def make_value(key, raw, **kw):
    parsed, vmode, ntype = _parse(raw)
    return NativeValue(native_key=key, raw_value=raw, parsed_value=parsed,
                       native_type=ntype, value_mode=vmode, **kw)


def _parse(raw):
    """Return (parsed_value, value_mode, native_type). Keep 60 vs 60% distinct."""
    if isinstance(raw, list):
        return raw, "absolute", "array"
    if isinstance(raw, bool):
        return raw, "absolute", "bool"
    if isinstance(raw, (int, float)):
        return raw, "absolute", "number"
    s = str(raw).strip()
    if s.endswith("%"):
        try:
            return float(s[:-1]), "percentage", "number_string"
        except ValueError:
            return s, "text", "text"
    try:
        return (int(s) if s.lstrip("-").isdigit() else float(s)), "absolute", "number_string"
    except ValueError:
        return s, "text", "text"
