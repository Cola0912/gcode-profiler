# -*- coding: utf-8 -*-
"""
Logical layer reconstruction (Phase 2), independent of slicer comments.

Uses extrusion Z plateaus. Travel-only Z moves (Z-hop) never create a layer
because only extruding events advance the layer Z. Continuous small Z rises
during extrusion are flagged as spiral. The first extruding layer is not assumed
to be model layer 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LayerRecord:
    layer_id: str
    physical_z: float
    logical_index: int
    height: Optional[float]
    kind: str = "model_candidate"   # model_candidate | auxiliary_candidate | spiral | unknown
    confidence: float = 0.6
    evidence: List[str] = field(default_factory=list)


class LayerReconstructor:
    def __init__(self, z_tol=0.01):
        self.z_tol = z_tol
        self.layers: List[LayerRecord] = []
        self.cur_z = None
        self._spiral_run = 0
        self._spiral_layers = set()

    def feed(self, ev):
        if not ev.extruding:
            return None
        z = ev.z1
        if self.cur_z is None or z > self.cur_z + self.z_tol:
            idx = len(self.layers)
            height = round(z - self.cur_z, 3) if self.cur_z is not None else None
            self.layers.append(LayerRecord(
                layer_id=f"L{idx}", physical_z=round(z, 3), logical_index=idx,
                height=height, evidence=["extrusion Z plateau"]))
            self.cur_z = z
            self._spiral_run = 0
            return self.layers[-1].layer_id
        if z > self.cur_z + 1e-4:
            # tiny continuous rise within a plateau -> spiral candidate
            self._spiral_run += 1
            if self._spiral_run > 20 and self.layers:
                self._spiral_layers.add(self.layers[-1].logical_index)
            self.cur_z = z
        return self.layers[-1].layer_id if self.layers else None

    def finalize(self):
        # first-layer height: assume bed at 0
        if self.layers and self.layers[0].height is None:
            self.layers[0].height = self.layers[0].physical_z
        for lr in self.layers:
            if lr.logical_index in self._spiral_layers:
                lr.kind = "spiral"
                lr.evidence.append("continuous Z rise during extrusion")
        return self.layers

    def dominant_height(self):
        hs = [lr.height for lr in self.layers if lr.height and 0.01 < lr.height < 2.0]
        if not hs:
            return None
        from collections import Counter
        return Counter(round(h, 3) for h in hs).most_common(1)[0][0]
