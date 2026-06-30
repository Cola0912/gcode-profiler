# -*- coding: utf-8 -*-
"""
Generic pipeline orchestrator (Phase 2).

Wires parser -> layer reconstruction -> path segmentation and produces a
GenericAnalysis with diagnostics. A compatibility adapter exposes a legacy-style
subset (quality.layer_height, per-feature widths/speeds) tagged with explicit
provenance, without replacing the legacy analyzer.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Optional

from .markers import MarkerClassifier
from .parser import GenericParser
from .layers import LayerReconstructor
from .paths import PathSegmenter


@dataclass
class GenericAnalysis:
    absolute_xyz: bool
    absolute_e: bool
    volumetric: bool
    tools_used: list
    layers: list
    paths: list
    dominant_layer_height: Optional[float]
    recognized_markers: dict
    unknown_recurring_markers: dict
    unknown_commands: dict
    field_provenance: str = "pipeline"

    # ------------------------------------------------------------------
    @property
    def path_count(self):
        return len(self.paths)

    @property
    def excluded_path_count(self):
        return sum(1 for p in self.paths if p.excluded)

    def feature_candidate_distribution(self):
        dist = defaultdict(int)
        for p in self.paths:
            if p.excluded or not p.candidate_features:
                continue
            dist[p.candidate_features[0][0]] += 1
        return dict(dist)

    def low_confidence_paths(self, thr=0.5):
        return sum(1 for p in self.paths if not p.excluded and p.confidence < thr)

    def _by_concept_width(self):
        g = defaultdict(list)
        for p in self.paths:
            if p.excluded or p.effective_width is None or not p.concept:
                continue
            g[p.concept].append(p.effective_width)
        return {k: round(statistics.median(v), 3) for k, v in g.items()}

    def _by_concept_speed(self):
        g = defaultdict(list)
        for p in self.paths:
            if p.excluded or not p.speed_stats or not p.concept:
                continue
            g[p.concept].append(p.speed_stats["median"])
        return {k: round(statistics.median(v), 1) for k, v in g.items()}

    def to_legacy_compat(self):
        """Legacy-style subset with explicit pipeline provenance. Does not replace
        the legacy analyzer; offered for adapters that want pipeline-derived values."""
        widths = self._by_concept_width()
        speeds = self._by_concept_speed()
        return {
            "_provenance": "pipeline",
            "quality": {
                "layer_height": self.dominant_layer_height,
                "outer_wall_width": widths.get("outer_wall"),
                "inner_wall_width": widths.get("inner_wall"),
                "sparse_infill_width": widths.get("sparse_infill"),
                "top_surface_width": widths.get("top_surface"),
            },
            "speed": {
                "outer_wall_speed": speeds.get("outer_wall"),
                "inner_wall_speed": speeds.get("inner_wall"),
                "sparse_infill_speed": speeds.get("sparse_infill"),
            },
            "meta": {
                "tool_count": len(self.tools_used) or 1,
                "total_layers": len(self.layers),
            },
        }

    def diagnostics(self):
        return {
            "coordinate_mode": "absolute" if self.absolute_xyz else "relative",
            "extrusion_mode": ("volumetric" if self.volumetric else
                               ("absolute" if self.absolute_e else "relative")),
            "tools_used": self.tools_used,
            "logical_layer_count": len(self.layers),
            "spiral_layers": sum(1 for l in self.layers if l.kind == "spiral"),
            "path_count": self.path_count,
            "excluded_path_count": self.excluded_path_count,
            "recognized_markers": self.recognized_markers,
            "unknown_recurring_markers": self.unknown_recurring_markers,
            "feature_candidate_distribution": self.feature_candidate_distribution(),
            "low_confidence_paths": self.low_confidence_paths(),
            "unknown_commands": dict(sorted(self.unknown_commands.items(),
                                            key=lambda kv: -kv[1])[:20]),
            "dominant_layer_height": self.dominant_layer_height,
        }


def analyze_lines(lines, filament_diameter=1.75):
    mc = MarkerClassifier()
    parser = GenericParser(mc, filament_diameter)
    layers = LayerReconstructor()
    seg = PathSegmenter(filament_diameter)
    cur_layer_id = None

    for raw in lines:
        ev = parser.feed_line(raw)
        if ev is None:
            continue
        lid = layers.feed(ev)
        if lid:
            cur_layer_id = lid
        lh = (layers.layers[-1].height if (layers.layers and layers.layers[-1].height)
              else None)
        seg.feed(ev, cur_layer_id, lh)

    layer_records = layers.finalize()
    dom_h = layers.dominant_height()
    path_records = seg.finalize(dom_h)
    s = parser.state
    return GenericAnalysis(
        absolute_xyz=s.abs_xyz, absolute_e=s.abs_e, volumetric=s.volumetric,
        tools_used=sorted(s.tools_used) or [0],
        layers=layer_records, paths=path_records, dominant_layer_height=dom_h,
        recognized_markers=dict(mc.recognized_counts),
        unknown_recurring_markers=mc.unknown_recurring(),
        unknown_commands=dict(s.unknown_commands),
    )


def analyze_generic(path, filament_diameter=1.75):
    try:
        from ..containers import open_gcode
    except ImportError:
        from gcode_profiler.containers import open_gcode
    src = open_gcode(path)
    return analyze_lines(src["lines"], filament_diameter)
