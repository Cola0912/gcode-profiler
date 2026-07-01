# -*- coding: utf-8 -*-
"""
Export orchestration (Phase 5 completion).

Bridges the GUI model -> legacy result -> canonical profile -> conversion plan
-> target-native writer. GUI-independent so it can be tested without Qt.

Pipeline:
    legacy_result (model.to_result)
      -> canonical.legacy_to_canonical
      -> conversion.build_plan(target)
      -> writers.write_native(plan, name)
"""
from __future__ import annotations

from . import canonical
from .conversion import build_plan
from .writers import write_native

# GUI display name -> internal target id (one writer module per slicer)
TARGET_CHOICES = [
    ("OrcaSlicer (JSON)", "orca"),
    ("BambuStudio (JSON)", "bambu"),
    ("PrusaSlicer (INI)", "prusa"),
    ("SuperSlicer (INI)", "superslicer"),
    ("Cura (CFG)", "cura"),
    ("Simplify3D (FFF)", "simplify3d"),
]
_DISPLAY_TO_ID = dict(TARGET_CHOICES)


def target_id(display_or_id):
    return _DISPLAY_TO_ID.get(display_or_id, display_or_id)


def build_plan_from_legacy(legacy_result, target):
    """legacy analyzer/model result dict -> (canonical_profile, conversion_plan)."""
    prof = canonical.legacy_to_canonical(legacy_result)
    return prof, build_plan(prof, target_id(target))


def build_plan_from_canonical(profile, target):
    """canonical profile -> (canonical_profile, conversion_plan)."""
    return profile, build_plan(profile, target_id(target))


def preview(plan):
    """Human-facing summary of a conversion plan for the export confirmation UI."""
    entries = plan.get("entries", [])
    counts = {}
    for e in entries:
        counts[e["status"]] = counts.get(e["status"], 0) + 1
    required = plan.get("required_user_inputs", [])
    critical = [r for r in required if r.get("safety_level") == "critical"]
    return {
        "target": plan.get("target"),
        "conversion_score": plan.get("conversion_score"),
        "counts": counts,
        "ready": counts.get("ready", 0),
        "derived": counts.get("derived", 0),
        "unsupported": counts.get("unsupported", 0),
        "conflict": counts.get("conflict", 0),
        "required_user_inputs": required,
        "critical_inputs": critical,
        "has_critical": bool(critical),
    }


def export(legacy_result, target, name="Recovered"):
    """Run the full pipeline. Returns (plan, NativeWriteResult)."""
    _prof, plan = build_plan_from_legacy(legacy_result, target)
    wres = write_native(plan, name=name)
    return plan, wres
