# -*- coding: utf-8 -*-
"""
Path segmentation, initial feature-candidate scoring, and exclusion rules
(Phase 2). Feature classification here is non-destructive (ranked candidates,
no forced selection). Full support/raft geometry classification is Phase 3.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import List, Optional

PI = math.pi

# concepts excluded from ordinary line-width / speed / wall / infill statistics
_EXCLUDE_CONCEPTS = {"purge", "prime", "wipe", "tool_change"}
_MIN_STABLE_LEN = 0.5


@dataclass
class PathRecord:
    path_id: str
    layer_id: Optional[str]
    tool: int
    closed: bool
    length: float
    extrusion_length: float
    extrusion_volume: Optional[float]
    effective_width: Optional[float]
    speed_stats: dict
    concept: Optional[str]
    candidate_features: List[tuple]   # [(feature, score), ...] ranked
    confidence: float
    excluded: bool
    exclusion_reason: Optional[str]
    bbox: tuple                       # (minx, miny, maxx, maxy)


class PathSegmenter:
    """Accumulates extruding events into paths; splits on travel/retract/
    tool-change/layer-change/concept-change."""
    def __init__(self, filament_diameter=1.75):
        self.area = PI * (filament_diameter / 2.0) ** 2
        self.records: List[PathRecord] = []
        self._reset()
        self._n = 0

    def _reset(self):
        self._pts = []
        self._e = 0.0
        self._len = 0.0
        self._speeds = []
        self._concept = None
        self._tool = 0
        self._layer = None
        self._start = None
        self._spanned_z = False

    def feed(self, ev, layer_id, layer_height):
        if ev.extruding:
            changed = (self._pts and
                       (ev.concept != self._concept or ev.tool != self._tool
                        or layer_id != self._layer))
            if changed:
                self._finalize(layer_height)
            if not self._pts:
                self._concept = ev.concept
                self._tool = ev.tool
                self._layer = layer_id
                self._start = (ev.x0, ev.y0)
                self._pts = [(ev.x0, ev.y0)]
            self._pts.append((ev.x1, ev.y1))
            self._len += ev.length_xy
            self._e += ev.e_delta
            if ev.feedrate_mm_s > 0:
                self._speeds.append(ev.feedrate_mm_s)
            if abs(ev.dz) > 0.01:
                self._spanned_z = True
        else:
            # travel / retraction is a path boundary
            if self._pts:
                self._finalize(layer_height)

    def finalize(self, layer_height):
        if self._pts:
            self._finalize(layer_height)
        return self.records

    def _finalize(self, layer_height):
        pts, length = self._pts, self._len
        if len(pts) < 2 or length <= 0:
            self._reset()
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        start, end = pts[0], pts[-1]
        closed = math.hypot(end[0] - start[0], end[1] - start[1]) < 0.6
        volume = self._e * self.area if self._e > 0 else None
        h = layer_height or 0.2
        eff_w = (volume / (length * h)) if (volume and length > 0 and h > 0) else None
        if eff_w is not None and not (0.05 < eff_w < 3.0):
            eff_w = None
        sp = self._speeds
        speed_stats = ({"min": round(min(sp), 1), "median": round(statistics.median(sp), 1),
                        "max": round(max(sp), 1)} if sp else {})
        candidates, conf = _score_features(self._concept, closed, length, eff_w, self._spanned_z)
        excluded, reason = _excluded(self._concept, length)
        self._n += 1
        self.records.append(PathRecord(
            path_id=f"P{self._n}", layer_id=self._layer, tool=self._tool, closed=closed,
            length=round(length, 3), extrusion_length=round(length, 3),
            extrusion_volume=round(volume, 4) if volume else None,
            effective_width=round(eff_w, 3) if eff_w else None,
            speed_stats=speed_stats, concept=self._concept,
            candidate_features=candidates, confidence=conf,
            excluded=excluded, exclusion_reason=reason, bbox=tuple(round(v, 2) for v in bbox)))
        self._reset()


def _score_features(concept, closed, length, eff_w, spanned_z):
    """Non-destructive ranked candidates. Marker concept dominates when present;
    otherwise light geometry heuristics with an 'unknown' fallback."""
    if concept:
        return [(concept, 0.85), ("unknown", 0.15)], 0.85
    cand = []
    if spanned_z:
        cand.append(("bridge", 0.2))
    if closed and length < 400:
        cand.append(("outer_wall", 0.35))
        cand.append(("inner_wall", 0.3))
    else:
        cand.append(("sparse_infill", 0.3))
    cand.append(("unknown", 0.4))
    cand.sort(key=lambda c: -c[1])
    return cand, cand[0][1]


def _excluded(concept, length):
    if concept in _EXCLUDE_CONCEPTS:
        return True, f"concept:{concept}"
    if length < _MIN_STABLE_LEN:
        return True, "short_segment"
    return False, None
