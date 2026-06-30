# -*- coding: utf-8 -*-
"""Target-native profile writer helpers (Phase 5)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field


WRITABLE_STATUSES = {"ready", "derived", "one_to_many", "many_to_one", "conflict"}


@dataclass
class NativeWriteResult:
    target: str
    files: list = field(default_factory=list)
    blocked: bool = False
    required_user_inputs: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def block_if_critical(plan):
    return [r for r in plan.get("required_user_inputs", [])
            if r.get("safety_level") == "critical"]


def entries_by_kind(plan):
    grouped = {"process": {}, "filament": {}, "printer": {}, "material": {}, "quality": {}}
    unsupported = []
    for e in plan.get("entries", []):
        if e.get("status") == "unsupported":
            unsupported.append(e)
            continue
        if e.get("status") == "target_default":
            continue
        if e.get("status") not in WRITABLE_STATUSES:
            continue
        kind = e.get("profile_kind") or "process"
        grouped.setdefault(kind, {})
        for key in e.get("target_keys", []):
            grouped[kind][key] = e.get("effective_value")
    return grouped, unsupported


def json_text(obj):
    return json.dumps(obj, ensure_ascii=False, indent=4)


def ini_text(kv, header=None):
    lines = []
    if header:
        lines.append(header)
    for k in sorted(kv):
        v = kv[k]
        if isinstance(v, list):
            v = ",".join(str(x) for x in v)
        lines.append(f"{k} = {v}")
    return "\n".join(lines) + "\n"


def xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def native_scalar(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return str(int(v)) if float(v).is_integer() else str(v)
    return str(v)
