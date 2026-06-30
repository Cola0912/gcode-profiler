# -*- coding: utf-8 -*-
import math

from gcode_profiler.nozzle_estimator import estimate_lines

PI = math.pi


def de_rect(L, h, w, d=1.75):
    return (w * h * L) / (PI * (d / 2) ** 2)


def test_04_nozzle(square_gcode):
    r = estimate_lines(square_gcode(h=0.2, w=0.42))
    assert r["tools"]["0"]["estimated_nozzle_diameter"] == 0.4


def test_06_nozzle(square_gcode):
    r = estimate_lines(square_gcode(h=0.3, w=0.65))
    assert r["tools"]["0"]["estimated_nozzle_diameter"] == 0.6


def test_rect_primary_model(square_gcode):
    t = estimate_lines(square_gcode(h=0.2, w=0.42))["tools"]["0"]
    assert t["cross_section_model"] == "rectangular_effective"
    assert abs(t["representative_line_width"] - 0.42) < 0.03


def test_marker_stack_isolates_infill():
    """Proprietary ;Marker enter/exit must not bleed infill into outer_wall."""
    lines = ["G21", "G90", "M82", "G92 E0"]
    e = 0.0
    for layer in range(8):
        z = round(0.3 * (layer + 1), 3)
        lines.append(f"G1 Z{z} F9000")
        # outer wall: width 0.6 (rect)
        lines.append(";Marker ModelContour 1")
        lines.append("G1 X100 Y100 F1800")
        for (a, b) in [(140, 100), (140, 140), (100, 140), (100, 100)]:
            e += de_rect(40, 0.3, 0.6)
            lines.append(f"G1 X{a} Y{b} E{e:.5f}")
        lines.append(";Marker ModelContour 0")
        # infill: width 0.72 (rect) -- must NOT be counted as outer_wall
        lines.append(";Marker InvisibleInfill 1")
        y = 105
        while y < 135:
            lines.append(f"G1 X105 Y{y} F3000")
            e += de_rect(30, 0.3, 0.72)
            lines.append(f"G1 X135 Y{y} E{e:.5f}")
            y += 4
        lines.append(";Marker InvisibleInfill 0")
    t = estimate_lines(lines)["tools"]["0"]
    ew = t["feature_effective_widths"]
    assert ew["outer_wall"] is not None
    assert abs(ew["outer_wall"] - 0.6) < 0.04          # outer kept clean
    assert ew["sparse_infill"] is not None and ew["sparse_infill"] > 0.68
    assert t["estimated_nozzle_diameter"] == 0.6        # not 0.8


def test_pressure_advance_explicit_zero():
    lines = ["M900 K0", "G21", "G90", "M82", "G92 E0", "G1 Z0.2",
             ";TYPE:External perimeter", "G1 X10 Y10 F1800", "G1 X40 Y10 E1.0"]
    pa = estimate_lines(lines)["pressure_advance"]
    assert pa["detected"] is True and pa["enabled"] is False  # explicit 0 != unknown


def test_pressure_advance_not_found():
    lines = ["G21", "G90", "M82", "G1 Z0.2", ";TYPE:External perimeter",
             "G1 X10 Y10 F1800", "G1 X40 Y10 E1.0"]
    pa = estimate_lines(lines)["pressure_advance"]
    assert pa["detected"] is False and pa["value"] is None  # null, not zero
