# -*- coding: utf-8 -*-
"""Target-native writers (Phase 5)."""
from __future__ import annotations

from .bambu import write_bambu
from .cura import write_cura
from .orca import write_orca
from .prusa import write_prusa
from .simplify3d import write_simplify3d
from .superslicer import write_superslicer

WRITERS = {
    "orca": write_orca,
    "bambu": write_bambu,
    "prusa": write_prusa,
    "superslicer": write_superslicer,
    "cura": write_cura,
    "simplify3d": write_simplify3d,
}


def write_native(plan, name="Recovered"):
    target = plan.get("target")
    if target not in WRITERS:
        raise ValueError(f"unknown writer target: {target}")
    return WRITERS[target](plan, name=name)

