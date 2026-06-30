# -*- coding: utf-8 -*-
"""OrcaSlicer native writer (Phase 5)."""
from __future__ import annotations

from .base import NativeWriteResult, block_if_critical, entries_by_kind, json_text

ORCA_PROFILE_VERSION = "2.2.0.0"


def write_orca(plan, name="Recovered"):
    critical = block_if_critical(plan)
    if critical:
        return NativeWriteResult("orca", blocked=True, required_user_inputs=critical,
                                 warnings=["critical user input is unresolved"])
    grouped, unsupported = entries_by_kind(plan)
    files = []
    process = _header("process", name)
    process.update(_stringify(grouped.get("process", {})))
    files.append((f"{name}.process.json", json_text(process)))

    filament = _header("filament", f"{name}.filament")
    filament.update(_array_values(_stringify(grouped.get("filament", {}))))
    files.append((f"{name}.filament.json", json_text(filament)))

    machine = _header("machine", f"{name}.machine")
    machine.update(_array_values(_stringify(grouped.get("printer", {}))))
    files.append((f"{name}.machine.json", json_text(machine)))
    return NativeWriteResult("orca", files=files, unsupported=unsupported,
                             warnings=list(plan.get("warnings", [])))


def _header(kind, name):
    return {"type": kind, "name": name, "from": "User",
            "is_custom_defined": "1", "version": ORCA_PROFILE_VERSION}


def _stringify(values):
    out = {}
    for k, v in values.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = "1" if v else "0"
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = str(int(v)) if float(v).is_integer() else str(v)
        else:
            out[k] = str(v)
    return out


def _array_values(values):
    out = {}
    for k, v in values.items():
        if k in {"nozzle_temperature", "nozzle_temperature_initial_layer", "hot_plate_temp",
                 "fan_max_speed", "nozzle_diameter", "retraction_length",
                 "retraction_speed", "z_hop"}:
            out[k] = [v]
        else:
            out[k] = v
    return out

