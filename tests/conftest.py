# -*- coding: utf-8 -*-
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PI = math.pi


def de_rect(L, h, w, d_fil=1.75):
    """E delta producing a rectangular effective width w (V = w*h*L)."""
    area = PI * (d_fil / 2) ** 2
    return (w * h * L) / area


@pytest.fixture
def square_gcode():
    """Build a minimal absolute-E G-code wall stack with ;TYPE markers."""
    def _make(h=0.2, w=0.42, layers=30, feature="External perimeter", d_fil=1.75):
        lines = [f"; filament_diameter = {d_fil}", "G21", "G90", "M82", "G92 E0"]
        e = 0.0
        pts = [(100, 100), (140, 100), (140, 140), (100, 140), (100, 100)]
        for i in range(layers):
            z = round(h * (i + 1), 3)
            lines += [f";HEIGHT:{h}", f"G1 Z{z} F9000", f";TYPE:{feature}", "G1 F1800",
                      f"G1 X{pts[0][0]} Y{pts[0][1]}"]
            for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
                seg = math.hypot(x1 - x0, y1 - y0)
                e += de_rect(seg, h, w, d_fil)
                lines.append(f"G1 X{x1} Y{y1} E{e:.5f}")
            lines += [f"G1 E{e-0.8:.5f} F2100", f"G1 E{e:.5f} F1500"]
        return lines
    return _make
