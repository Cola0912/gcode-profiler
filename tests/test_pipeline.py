# -*- coding: utf-8 -*-
import math

from gcode_profiler.pipeline import analyze_lines, classify_concept, normalize

PI = math.pi


def de_rect(L, h, w, d=1.75):
    return (w * h * L) / (PI * (d / 2) ** 2)


# ---- marker normalization ----
def test_normalize_punct_case():
    assert normalize(";TYPE:External-Perimeter") == "external perimeter"
    assert normalize("; FEATURE: Outer wall") == "outer wall"


def test_classify_known_and_fuzzy():
    assert classify_concept(";TYPE:External perimeter")[0] == "outer_wall"
    assert classify_concept(";TYPE:WALL-OUTER")[0] == "outer_wall"
    assert classify_concept("; feature inner perimeter")[0] == "inner_wall"
    assert classify_concept(";TYPE:Internal infill")[0] == "sparse_infill"
    assert classify_concept(";Marker ModelContour 1")[0] == "outer_wall"
    assert classify_concept("; random nonsense")[0] is None


def _wall(lines, e, z, w=0.45, h=0.2, concept="External perimeter"):
    lines.append(f";TYPE:{concept}")
    pts = [(100, 100), (140, 100), (140, 140), (100, 140), (100, 100)]
    lines.append(f"G1 X{pts[0][0]} Y{pts[0][1]} F1800")
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        e[0] += de_rect(40, h, w)
        lines.append(f"G1 X{x1} Y{y1} E{e[0]:.5f}")
    return lines


def test_unknown_gcode_no_comments_still_reconstructs_layers():
    # geometry-only: no TYPE comments at all
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(5):
        z = round(0.2 * (i + 1), 3)
        lines.append(f"G1 Z{z} F9000")
        pts = [(100, 100), (140, 100), (140, 140), (100, 140), (100, 100)]
        lines.append(f"G1 X{pts[0][0]} Y{pts[0][1]} F1800")
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            e[0] += de_rect(40, 0.2, 0.45)
            lines.append(f"G1 X{x1} Y{y1} E{e[0]:.5f}")
    a = analyze_lines(lines)
    assert len(a.layers) == 5
    assert abs(a.dominant_layer_height - 0.2) < 1e-6
    assert a.path_count >= 5


def test_zhop_not_a_layer_change():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000", ";TYPE:External perimeter"]
    e = [0.0]
    # extrude, z-hop up (travel only), come back, extrude same layer
    lines += ["G1 X100 Y100 F1800", f"G1 X140 Y100 E{(e.__setitem__(0, e[0]+de_rect(40,0.2,0.45)) or e[0]):.5f}",
              "G1 Z1.2 F9000",       # z-hop (no extrusion)
              "G1 X140 Y140 F9000",  # travel
              "G1 Z0.2 F9000",       # back down
              f"G1 X100 Y140 E{(e.__setitem__(0, e[0]+de_rect(40,0.2,0.45)) or e[0]):.5f}"]
    a = analyze_lines(lines)
    assert len(a.layers) == 1   # z-hop did not create a new logical layer


def test_relative_extrusion_paths():
    lines = ["G21", "G90", "M83", "G1 Z0.2 F9000", ";TYPE:External perimeter",
             "G1 X100 Y100 F1800"]
    for (x, y) in [(140, 100), (140, 140), (100, 140), (100, 100)]:
        lines.append(f"G1 X{x} Y{y} E{de_rect(40,0.2,0.45):.5f}")
    a = analyze_lines(lines)
    assert a.absolute_e is False
    assert a.path_count >= 1
    w = a._by_concept_width().get("outer_wall")
    assert w is not None and abs(w - 0.45) < 0.05


def test_purge_excluded_from_stats():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000",
             ";TYPE:Purge", "G1 X10 Y10 F1800"]
    e = [0.0]
    e[0] += de_rect(80, 0.2, 1.2)
    lines.append(f"G1 X90 Y10 E{e[0]:.5f}")     # fat purge line
    _wall(lines, e, 0.2)                          # real wall
    a = analyze_lines(lines)
    purge = [p for p in a.paths if p.concept == "purge"]
    assert purge and all(p.excluded for p in purge)
    assert a.excluded_path_count >= 1


def test_toolchange_tracked():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000", "T0",
             ";TYPE:External perimeter", "G1 X100 Y100 F1800"]
    e = [0.0]
    e[0] += de_rect(40, 0.2, 0.45); lines.append(f"G1 X140 Y100 E{e[0]:.5f}")
    lines += ["T1", ";TYPE:External perimeter", "G1 X100 Y100 F1800"]
    e[0] += de_rect(40, 0.2, 0.45); lines.append(f"G1 X140 Y100 E{e[0]:.5f}")
    a = analyze_lines(lines)
    assert a.tools_used == [0, 1]


def test_unknown_recurring_marker_collected():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000"]
    e = [0.0]
    for i in range(4):
        lines.append(";TYPE:FOOBAR_REGION")       # unknown marker, recurring
        e[0] += de_rect(40, 0.2, 0.45)
        lines.append("G1 X100 Y100 F1800")
        lines.append(f"G1 X140 Y100 E{e[0]:.5f}")
    a = analyze_lines(lines)
    assert any("foobar" in k for k in a.unknown_recurring_markers)


def test_diagnostics_shape():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000"]
    e = [0.0]
    _wall(lines, e, 0.2)
    d = analyze_lines(lines).diagnostics()
    for key in ("coordinate_mode", "extrusion_mode", "logical_layer_count",
                "path_count", "feature_candidate_distribution"):
        assert key in d
