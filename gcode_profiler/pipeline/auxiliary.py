# -*- coding: utf-8 -*-
"""
Auxiliary toolpath structure classification (Phase 3).

Classifies support / support interface / raft / brim / skirt / purge line /
purge tower / wipe / unknown_auxiliary from regions and the vertical graph.
Marker concepts dominate when present; light geometry provides candidates for
unknown slicers. Critically:
  - path_present is observable from geometry.
  - setting_enabled_state stays unknown unless metadata says enabled/disabled.
Absence of paths never proves a setting was disabled. Full tree/organic support
parameter extraction and exact thresholds are out of scope (low-confidence
candidates only).

(Module name is 'auxiliary' rather than 'aux' because AUX is a reserved Windows
device name and cannot be a filename.)
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Optional

from .regions import build_regions, _area

_SUPPORT = {"support", "support_interface"}
_RAFT = {"raft"}
_PURGE = {"purge", "prime"}
_WIPE = {"wipe"}


@dataclass
class AuxResult:
    # support
    support_path_present: bool = False
    support_interface_present: bool = False
    support_type_candidate: str = "unknown"
    # raft
    raft_path_present: bool = False
    raft_layer_count: Optional[int] = None
    # brim / skirt
    brim_path_present: bool = False
    skirt_path_present: bool = False
    skirt_loop_count: Optional[int] = None
    # multimaterial purge / wipe
    purge_line_present: bool = False
    purge_tower_present: bool = False
    wipe_structure_present: bool = False
    # leftovers
    unknown_auxiliary_regions: int = 0
    evidence: dict = field(default_factory=dict)

    # setting_enabled_state is ALWAYS unknown from geometry alone
    def support_enabled_state(self):
        return None

    def raft_enabled_state(self):
        return None


def classify_auxiliary(analysis):
    """analysis: pipeline.GenericAnalysis. Returns AuxResult."""
    regions = build_regions(analysis.paths, analysis.layers)
    res = AuxResult()
    ev = res.evidence
    if not regions:
        return res

    min_layer = min(r.layer_index for r in regions)
    by_concept = defaultdict(list)
    for r in regions:
        by_concept[r.concept].append(r)

    # --- support (marker) + geometry candidate ---
    sup_regions = [r for r in regions if r.concept in _SUPPORT]
    geom_support = _geometry_support(regions, min_layer) if not sup_regions else []
    if sup_regions or geom_support:
        res.support_path_present = True
        res.support_interface_present = any(r.concept == "support_interface" for r in regions)
        res.support_type_candidate = _support_type(sup_regions or geom_support)
        ev["support"] = (f"marker regions={len(sup_regions)}, "
                         f"geometry candidates={len(geom_support)}")

    # --- raft ---
    raft_regions = [r for r in regions if r.concept in _RAFT]
    if not raft_regions:
        raft_regions = _geometry_raft(regions, min_layer)
    if raft_regions:
        res.raft_path_present = True
        res.raft_layer_count = len({r.layer_index for r in raft_regions})  # actual layers
        ev["raft"] = f"raft layers={res.raft_layer_count}"

    # --- brim vs skirt (first printed layers) ---
    base_layers = {min_layer, min_layer + 1}
    model_first = [r for r in regions
                   if r.layer_index in base_layers and r.concept in ("outer_wall", "inner_wall")]
    for r in regions:
        if r.layer_index not in base_layers:
            continue
        if r.concept == "brim" or (r.concept is None and _touches_any(r, model_first)):
            res.brim_path_present = res.brim_path_present or (r.concept == "brim")
        if r.concept == "skirt" or (r.concept is None and r.closed_loop_count
                                    and not _touches_any(r, model_first)
                                    and not res.support_path_present):
            if r.concept == "skirt":
                res.skirt_path_present = True
    if res.skirt_path_present:
        res.skirt_loop_count = sum(r.closed_loop_count for r in regions
                                   if r.concept == "skirt")

    # --- purge line / tower / wipe ---
    purge_regions = [r for r in regions if r.concept in _PURGE]
    wipe_regions = [r for r in regions if r.concept in _WIPE]
    if purge_regions:
        # tower: same XY repeated across many layers; line: first-layer only
        layers_per_xy = _repeated_xy_layers(purge_regions + wipe_regions)
        if max(layers_per_xy.values(), default=0) >= 3:
            res.purge_tower_present = True
            ev["purge"] = f"tower across {max(layers_per_xy.values())} layers"
        if any(r.layer_index <= min_layer + 1 for r in purge_regions):
            res.purge_line_present = True
    if wipe_regions:
        res.wipe_structure_present = True

    # --- unknown auxiliary ---
    classified = set()
    for grp in (sup_regions, geom_support, raft_regions, purge_regions, wipe_regions):
        classified.update(id(r) for r in grp)
    res.unknown_auxiliary_regions = sum(
        1 for r in regions
        if r.concept is None and id(r) not in classified
        and r.layer_index > min_layer + 1 and _looks_auxiliary(r, regions))
    return res


# --- geometry helpers ------------------------------------------------------
def _geometry_support(regions, min_layer):
    """Low-confidence: an unknown region under (overlapped by) a region above,
    not on the very first layer. Real support detection is marker-led."""
    out = []
    for r in regions:
        if r.concept is None and r.layer_index > min_layer and r.overlaps_above \
                and r.area_estimate < 5000:
            out.append(r)
    return out


def _geometry_raft(regions, min_layer):
    """Broad filled regions on the lowest layers covering the model footprint."""
    base = [r for r in regions if r.layer_index <= min_layer + 2]
    if not base:
        return []
    big = sorted(base, key=lambda r: -r.area_estimate)
    biggest = big[0]
    out = [r for r in base if r.area_estimate >= 0.8 * biggest.area_estimate
           and r.concept is None]
    # require multiple stacked auxiliary layers and a model region above
    return out if len({r.layer_index for r in out}) >= 2 else []


def _support_type(regions):
    # tree/organic detection deferred; report normal when grid-like, else unknown
    return "normal" if regions else "unknown"


def _touches_any(r, others, gap=2.0):
    for o in others:
        if not (r.bbox[0] - gap > o.bbox[2] or o.bbox[0] - gap > r.bbox[2]
                or r.bbox[1] - gap > o.bbox[3] or o.bbox[1] - gap > r.bbox[3]):
            return True
    return False


def _repeated_xy_layers(regions, tol=5.0):
    buckets = defaultdict(set)
    for r in regions:
        key = (round(r.centroid[0] / tol), round(r.centroid[1] / tol))
        buckets[key].add(r.layer_index)
    return {k: len(v) for k, v in buckets.items()}


def _looks_auxiliary(r, regions):
    return r.area_estimate < 5000 and bool(r.overlaps_above or r.overlaps_below)


# --- canonical / legacy / diagnostics -------------------------------------
def to_canonical(res, profile):
    """Write auxiliary results into a canonical profile (unique ownership)."""
    try:
        from ..canonical import model as m
    except ImportError:
        from gcode_profiler.canonical import model as m

    def boolval(present):
        return m.observed(bool(present), source="geometry", confidence=0.7,
                          value_mode="enum")

    m.set_value(profile, "process.support.path_present", boolval(res.support_path_present))
    m.set_value(profile, "process.support.setting_enabled_state",
                m.unknown(value_mode="enum",
                          warnings=["経路の有無から設定の有効/無効は断定不可"]))
    m.set_value(profile, "process.support.type_candidate",
                m.estimated(res.support_type_candidate, value_mode="enum", confidence=0.3))
    m.set_value(profile, "process.support.interface_present",
                boolval(res.support_interface_present))
    m.set_value(profile, "process.support.raft.path_present", boolval(res.raft_path_present))
    m.set_value(profile, "process.support.raft.setting_enabled_state",
                m.unknown(value_mode="enum"))
    m.set_value(profile, "process.support.raft.layer_count",
                m.observed(res.raft_layer_count, source="geometry", value_mode="count")
                if res.raft_layer_count else m.unknown(value_mode="count"))
    m.set_value(profile, "process.others.brim.path_present", boolval(res.brim_path_present))
    m.set_value(profile, "process.others.skirt.path_present", boolval(res.skirt_path_present))
    m.set_value(profile, "process.multimaterial.purge.line_present",
                boolval(res.purge_line_present))
    m.set_value(profile, "process.multimaterial.purge.tower_present",
                boolval(res.purge_tower_present))
    m.set_value(profile, "process.multimaterial.wipe.structure_present",
                boolval(res.wipe_structure_present))
    return profile


def to_legacy_compat(res):
    """Legacy booleans: true only when present; None (unknown) when absent."""
    return {
        "has_support": True if res.support_path_present else None,
        "has_raft": True if res.raft_path_present else None,
    }


def diagnostics(res):
    return {
        "support_path_present": res.support_path_present,
        "support_setting_enabled_state": res.support_enabled_state(),
        "support_interface_present": res.support_interface_present,
        "support_type_candidate": res.support_type_candidate,
        "raft_path_present": res.raft_path_present,
        "raft_setting_enabled_state": res.raft_enabled_state(),
        "raft_layer_count": res.raft_layer_count,
        "brim_path_present": res.brim_path_present,
        "skirt_path_present": res.skirt_path_present,
        "purge_line_present": res.purge_line_present,
        "purge_tower_present": res.purge_tower_present,
        "wipe_structure_present": res.wipe_structure_present,
        "unknown_auxiliary_regions": res.unknown_auxiliary_regions,
        "evidence": res.evidence,
    }
