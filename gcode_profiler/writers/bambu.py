# -*- coding: utf-8 -*-
"""Bambu Studio native writer (Phase 5).

Currently uses Bambu's Orca-family JSON vocabulary through a separate writer
module so Bambu-specific keys can diverge safely.
"""
from __future__ import annotations

from .orca import _array_values, _header, _stringify
from .base import NativeWriteResult, block_if_critical, entries_by_kind, json_text


def write_bambu(plan, name="Recovered"):
    critical = block_if_critical(plan)
    if critical:
        return NativeWriteResult("bambu", blocked=True, required_user_inputs=critical,
                                 warnings=["critical user input is unresolved"])
    grouped, unsupported = entries_by_kind(plan)
    files = []
    process = _header("process", name)
    process.update(_stringify(grouped.get("process", {})))
    files.append((f"{name}.bambu.process.json", json_text(process)))

    filament = _header("filament", f"{name}.filament")
    filament.update(_array_values(_stringify(grouped.get("filament", {}))))
    files.append((f"{name}.bambu.filament.json", json_text(filament)))

    machine = _header("machine", f"{name}.machine")
    machine.update(_array_values(_stringify(grouped.get("printer", {}))))
    files.append((f"{name}.bambu.machine.json", json_text(machine)))
    return NativeWriteResult("bambu", files=files, unsupported=unsupported,
                             warnings=list(plan.get("warnings", [])))

