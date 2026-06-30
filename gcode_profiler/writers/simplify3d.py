# -*- coding: utf-8 -*-
"""Simplify3D FFF writer (Phase 5)."""
from __future__ import annotations

from .base import NativeWriteResult, block_if_critical, entries_by_kind, native_scalar, xml_escape


def write_simplify3d(plan, name="Recovered"):
    critical = block_if_critical(plan)
    if critical:
        return NativeWriteResult("simplify3d", blocked=True, required_user_inputs=critical,
                                 warnings=["critical user input is unresolved"])
    grouped, unsupported = entries_by_kind(plan)
    values = {}
    for kind in ("process", "filament", "printer"):
        values.update(grouped.get(kind, {}))
    lines = ['<?xml version="1.0"?>', f'<profile name="{xml_escape(name)}" version="2023">']
    for k in sorted(values):
        lines.append(f"  <{k}>{xml_escape(native_scalar(values[k]))}</{k}>")
    lines.append("</profile>")
    return NativeWriteResult("simplify3d",
                             files=[(f"{name}.simplify3d.fff", "\n".join(lines) + "\n")],
                             unsupported=unsupported,
                             warnings=list(plan.get("warnings", [])))
