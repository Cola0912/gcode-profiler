# -*- coding: utf-8 -*-
"""
Region model and vertical relationship graph (Phase 3).

Groups Phase 2 path records into per-layer regions by XY proximity, then builds
a bounded vertical overlap graph (adjacent layers only -> no all-pairs/all-layer
O(n^2)). Shared by support/raft detection in aux.py.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Region:
    region_id: str
    layer_index: int
    physical_z: float
    tool: int
    path_ids: List[str]
    bbox: tuple                       # (minx, miny, maxx, maxy)
    concept: Optional[str]
    closed_loop_count: int
    area_estimate: float
    centroid: tuple
    overlaps_above: List[str] = field(default_factory=list)
    overlaps_below: List[str] = field(default_factory=list)
    overlap_ratio_above: float = 0.0
    starts_on_bed: bool = False
    candidate_types: list = field(default_factory=list)
    confidence: float = 0.0
    evidence: list = field(default_factory=list)


def _area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _inter_area(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    return ix * iy


def _near(a, b, gap):
    return not (a[0] - gap > b[2] or b[0] - gap > a[2]
                or a[1] - gap > b[3] or b[1] - gap > a[3])


def _cluster(paths, gap):
    """Union-find clustering of paths whose bboxes are within `gap`."""
    n = len(paths)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if paths[i].tool == paths[j].tool and _near(paths[i].bbox, paths[j].bbox, gap):
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(paths[i])
    return list(groups.values())


def build_regions(paths, layers, gap=3.0):
    """paths: Phase 2 PathRecords; layers: LayerRecords. Returns list[Region]."""
    idx_of = {l.layer_id: l.logical_index for l in layers}
    z_of = {l.logical_index: l.physical_z for l in layers}
    per_layer = defaultdict(list)
    for p in paths:
        li = idx_of.get(p.layer_id)
        if li is None:
            continue
        per_layer[li].append(p)

    regions = []
    rid = 0
    for li in sorted(per_layer):
        for g in _cluster(per_layer[li], gap):
            bbox = g[0].bbox
            for p in g[1:]:
                bbox = _union(bbox, p.bbox)
            concepts = Counter(p.concept for p in g if p.concept)
            dom = concepts.most_common(1)[0][0] if concepts else None
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            rid += 1
            regions.append(Region(
                region_id=f"R{rid}", layer_index=li, physical_z=z_of.get(li, 0.0),
                tool=g[0].tool, path_ids=[p.path_id for p in g], bbox=bbox,
                concept=dom, closed_loop_count=sum(1 for p in g if p.closed),
                area_estimate=round(_area(bbox), 2), centroid=(round(cx, 2), round(cy, 2))))
    _vertical_graph(regions)
    return regions


def _vertical_graph(regions):
    """Bounded adjacent-layer overlap graph."""
    by_layer = defaultdict(list)
    for r in regions:
        by_layer[r.layer_index].append(r)
    min_layer = min((r.layer_index for r in regions), default=0)
    for r in regions:
        a = by_layer.get(r.layer_index + 1, [])
        below = by_layer.get(r.layer_index - 1, [])
        ra = _area(r.bbox) or 1.0
        for u in a:
            if _inter_area(r.bbox, u.bbox) > 0:
                r.overlaps_above.append(u.region_id)
                r.overlap_ratio_above = max(
                    r.overlap_ratio_above, _inter_area(r.bbox, u.bbox) / ra)
        for d in below:
            if _inter_area(r.bbox, d.bbox) > 0:
                r.overlaps_below.append(d.region_id)
        r.starts_on_bed = (r.layer_index <= min_layer + 1) and not r.overlaps_below
