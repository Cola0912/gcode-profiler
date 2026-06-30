# -*- coding: utf-8 -*-
"""SuperSlicer native INI writer (Phase 5)."""
from __future__ import annotations

from .base import NativeWriteResult, block_if_critical, entries_by_kind, ini_text


def write_superslicer(plan, name="Recovered"):
    critical = block_if_critical(plan)
    if critical:
        return NativeWriteResult("superslicer", blocked=True, required_user_inputs=critical,
                                 warnings=["critical user input is unresolved"])
    grouped, unsupported = entries_by_kind(plan)
    kv = {}
    for kind in ("process", "filament", "printer"):
        kv.update(grouped.get(kind, {}))
    files = [(f"{name}.superslicer.ini",
              ini_text(kv, f"# GcodeProfiler SuperSlicer profile: {name}"))]
    return NativeWriteResult("superslicer", files=files, unsupported=unsupported,
                             warnings=list(plan.get("warnings", [])))

