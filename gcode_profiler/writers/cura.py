# -*- coding: utf-8 -*-
"""Cura quality-changes CFG writer (Phase 5)."""
from __future__ import annotations

from .base import NativeWriteResult, block_if_critical, entries_by_kind


def write_cura(plan, name="Recovered"):
    critical = block_if_critical(plan)
    if critical:
        return NativeWriteResult("cura", blocked=True, required_user_inputs=critical,
                                 warnings=["critical user input is unresolved"])
    grouped, unsupported = entries_by_kind(plan)
    values = {}
    for kind in ("process", "filament", "printer"):
        values.update(grouped.get(kind, {}))
    lines = [
        "[general]",
        "version = 4",
        f"name = {name}",
        "definition = fdmprinter",
        "",
        "[metadata]",
        "type = quality_changes",
        "quality_type = normal",
        "setting_version = 22",
        "",
        "[values]",
    ]
    for k in sorted(values):
        lines.append(f"{k} = {values[k]}")
    return NativeWriteResult("cura", files=[(f"{name}.cura.cfg", "\n".join(lines) + "\n")],
                             unsupported=unsupported,
                             warnings=list(plan.get("warnings", [])))

