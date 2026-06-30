# -*- coding: utf-8 -*-
import math

from gcode_profiler.pipeline import analyze_lines, classify_auxiliary, aux_to_legacy

PI = math.pi


def de(L, h, w, d=1.75):
    return (w * h * L) / (PI * (d / 2) ** 2)


def _square(lines, e, cx, cy, half, w=0.45, h=0.2, concept=None, f=1800):
    if concept:
        lines.append(f";TYPE:{concept}")
    pts = [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half),
           (cx - half, cy + half), (cx - half, cy - half)]
    lines.append(f"G1 X{pts[0][0]} Y{pts[0][1]} F{f}")
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        e[0] += de(seg, h, w)
        lines.append(f"G1 X{x1} Y{y1} E{e[0]:.5f}")


def test_support_marker_present_enabled_unknown():
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(4):
        lines.append(f"G1 Z{round(0.2*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 15, concept="External perimeter")
        _square(lines, e, 140, 140, 8, concept="Support material")
    res = classify_auxiliary(analyze_lines(lines))
    assert res.support_path_present is True
    assert res.support_enabled_state() is None        # enabled-state unknown
    assert aux_to_legacy(res)["has_support"] is True


def test_support_absent_enabled_unknown_not_false():
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(4):
        lines.append(f"G1 Z{round(0.2*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 15, concept="External perimeter")
    res = classify_auxiliary(analyze_lines(lines))
    assert res.support_path_present is False
    assert res.support_enabled_state() is None        # unknown, NOT False
    assert aux_to_legacy(res)["has_support"] is None  # null, not False


def test_multi_layer_raft_layer_count_from_classified_layers():
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    # 3 raft layers (broad), then model
    for i in range(3):
        lines.append(f"G1 Z{round(0.3*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 30, w=0.6, h=0.3, concept="Raft")
    for i in range(3, 6):
        lines.append(f"G1 Z{round(0.3*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 15, concept="External perimeter")
    res = classify_auxiliary(analyze_lines(lines))
    assert res.raft_path_present is True
    assert res.raft_layer_count == 3                  # actual classified raft layers


def test_skirt_vs_brim_markers():
    lines = ["G21", "G90", "M82", "G92 E0", "G1 Z0.2 F9000"]
    e = [0.0]
    _square(lines, e, 100, 100, 30, concept="Skirt")        # separated loop
    _square(lines, e, 100, 100, 15, concept="External perimeter")
    res = classify_auxiliary(analyze_lines(lines))
    assert res.skirt_path_present is True
    assert aux_to_legacy(res)["has_support"] is None


def test_purge_tower_repeated_layers():
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(5):
        lines.append(f"G1 Z{round(0.2*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 15, concept="External perimeter")
        _square(lines, e, 180, 180, 5, concept="Prime tower")   # fixed-XY across layers
    res = classify_auxiliary(analyze_lines(lines))
    assert res.purge_tower_present is True


def test_canonical_support_ownership():
    from gcode_profiler.canonical import empty_profile, get_value
    from gcode_profiler.pipeline import aux_to_canonical
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(3):
        lines.append(f"G1 Z{round(0.2*(i+1),3)} F9000")
        _square(lines, e, 100, 100, 15, concept="External perimeter")
        _square(lines, e, 140, 140, 8, concept="Support material")
    res = classify_auxiliary(analyze_lines(lines))
    prof = aux_to_canonical(res, empty_profile())
    assert get_value(prof, "process.support.path_present")["effective"] is True
    assert get_value(prof, "process.support.setting_enabled_state")["status"] == "unknown"
