# -*- coding: utf-8 -*-
"""
Generic G-code parser state machine (Phase 2).

Streaming, slicer-independent. Maintains coordinate/extrusion/tool/feed/temp/fan
state and emits normalized MoveEvent records. Unknown commands are preserved as
raw events rather than discarded. Reuses arc-length geometry only (no duplicate
toolpath analyzers downstream).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

PI = math.pi


@dataclass
class MoveEvent:
    __slots__ = ("line_number", "tool", "x0", "y0", "z0", "x1", "y1", "z1",
                 "e_delta", "feedrate_mm_s", "extruding", "retracting", "travel",
                 "arc", "length_xy", "dz", "concept")
    line_number: int
    tool: int
    x0: float
    y0: float
    z0: float
    x1: float
    y1: float
    z1: float
    e_delta: float
    feedrate_mm_s: float
    extruding: bool
    retracting: bool
    travel: bool
    arc: bool
    length_xy: float
    dz: float
    concept: Optional[str]


@dataclass
class GenericState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    e: float = 0.0
    abs_xyz: bool = True
    abs_e: bool = True
    tool: int = 0
    feedrate: float = 0.0          # mm/min (raw F)
    volumetric: bool = False
    flow_override: float = 1.0     # M221 / runtime
    concept: Optional[str] = None
    filament_diameter: float = 1.75
    # collected, non per-line:
    tools_used: set = field(default_factory=set)
    temps: list = field(default_factory=list)        # (tool, temp)
    bed_temps: list = field(default_factory=list)
    fan_events: list = field(default_factory=list)    # (line, value0_255)
    motion_limits: dict = field(default_factory=dict)
    unknown_commands: dict = field(default_factory=dict)  # head -> count
    line_number: int = 0


def _axes(cmd):
    out = {}
    for tok in cmd.split()[1:]:
        if not tok:
            continue
        a = tok[0].upper()
        if a in "XYZEFIJRSD":
            try:
                out[a] = float(tok[1:])
            except ValueError:
                pass
    return out


def _arc_length(cw, x0, y0, x1, y1, ax):
    if "I" in ax or "J" in ax:
        i, j = ax.get("I", 0.0), ax.get("J", 0.0)
        cx, cy, r = x0 + i, y0 + j, math.hypot(i, j)
    elif "R" in ax:
        return None  # R-form deferred; treat as unsupported arc length
    else:
        return None
    if r < 1e-9:
        return math.hypot(x1 - x0, y1 - y0)
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    da = a1 - a0
    if cw and da > 0:
        da -= 2 * PI
    elif (not cw) and da < 0:
        da += 2 * PI
    if abs(da) < 1e-9:
        da = 2 * PI
    return abs(da) * r


class GenericParser:
    """Drives over lines, updating state and yielding MoveEvent for moves.
    Comment classification is delegated to a MarkerClassifier passed in."""
    def __init__(self, classifier, filament_diameter=1.75):
        self.s = GenericState(filament_diameter=filament_diameter)
        self.mc = classifier

    @property
    def state(self):
        return self.s

    def feed_line(self, raw):
        """Process one line. Returns a MoveEvent or None."""
        s = self.s
        s.line_number += 1
        line = raw.strip().strip('"').strip()
        if not line:
            return None
        if line.startswith(";"):
            self._comment(line)
            return None
        code_part = line
        if ";" in line:
            code_part, after = line.split(";", 1)
            self._comment(";" + after)
        code_part = code_part.strip()
        if not code_part:
            return None
        return self._command(code_part)

    def _comment(self, line):
        h = self.mc.height_hint(line)
        concept, _conf = self.mc.classify(line)
        if concept is not None and concept not in ("layer", "tool_change",
                                                   "object_boundary"):
            self.s.concept = concept

    def _command(self, cmd):
        s = self.s
        head = cmd.split()[0].upper()
        if head in ("G0", "G1"):
            return self._move(cmd, head)
        if head in ("G2", "G3"):
            return self._arc(cmd, head)
        if head == "G90":
            s.abs_xyz = True
        elif head == "G91":
            s.abs_xyz = False
        elif head == "M82":
            s.abs_e = True
        elif head == "M83":
            s.abs_e = False
        elif head == "G92":
            self._g92(cmd)
        elif head == "M200":
            ax = _axes(cmd)
            s.volumetric = "D" in ax and ax["D"] > 0
            if s.volumetric:
                s.filament_diameter = ax["D"]
        elif head == "M221":
            ax = _axes(cmd)
            if "S" in ax and ax["S"] > 0:
                s.flow_override = ax["S"] / 100.0
        elif head in ("M104", "M109"):
            ax = _axes(cmd)
            if "S" in ax and ax["S"] > 0:
                s.temps.append((s.tool, ax["S"]))
        elif head in ("M140", "M190"):
            ax = _axes(cmd)
            if "S" in ax:
                s.bed_temps.append(ax["S"])
        elif head == "M106":
            ax = _axes(cmd)
            if "S" in ax:
                s.fan_events.append((s.line_number, ax["S"]))
        elif head == "M107":
            s.fan_events.append((s.line_number, 0.0))
        elif head in ("M201", "M203", "M204", "M205", "M566", "SET_VELOCITY_LIMIT"):
            s.motion_limits.setdefault(head, cmd)
        elif head.startswith("T") and head[1:].isdigit():
            s.tool = int(head[1:])
            s.tools_used.add(s.tool)
        else:
            s.unknown_commands[head] = s.unknown_commands.get(head, 0) + 1
        return None

    def _g92(self, cmd):
        ax = _axes(cmd)
        if "E" in ax:
            self.s.e = ax["E"]
        if "X" in ax:
            self.s.x = ax["X"]
        if "Y" in ax:
            self.s.y = ax["Y"]
        if "Z" in ax:
            self.s.z = ax["Z"]

    def _resolve(self, ax):
        s = self.s
        if s.abs_xyz:
            nx, ny, nz = ax.get("X", s.x), ax.get("Y", s.y), ax.get("Z", s.z)
        else:
            nx, ny, nz = s.x + ax.get("X", 0.0), s.y + ax.get("Y", 0.0), s.z + ax.get("Z", 0.0)
        if "F" in ax:
            s.feedrate = ax["F"]
        if "E" in ax:
            de = ax["E"] if not s.abs_e else (ax["E"] - s.e)
            s.e = (s.e + ax["E"]) if not s.abs_e else ax["E"]
        else:
            de = 0.0
        return nx, ny, nz, de

    def _emit(self, nx, ny, nz, de, length, arc):
        s = self.s
        x0, y0, z0 = s.x, s.y, s.z
        speed = s.feedrate / 60.0 if s.feedrate else 0.0
        extruding = de > 1e-9 and length > 1e-9
        retracting = de < -1e-9 and length <= 1e-9
        travel = (not extruding) and (not retracting) and length > 1e-9
        ev = MoveEvent(s.line_number, s.tool, x0, y0, z0, nx, ny, nz,
                       de, speed, extruding, retracting, travel, arc,
                       length, nz - z0, s.concept)
        s.x, s.y, s.z = nx, ny, nz
        return ev

    def _move(self, cmd, head):
        ax = _axes(cmd)
        nx, ny, nz, de = self._resolve(ax)
        length = math.hypot(nx - self.s.x, ny - self.s.y)
        return self._emit(nx, ny, nz, de, length, arc=False)

    def _arc(self, cmd, head):
        ax = _axes(cmd)
        nx, ny, nz, de = self._resolve(ax)
        length = _arc_length(head == "G2", self.s.x, self.s.y, nx, ny, ax)
        if length is None:
            length = math.hypot(nx - self.s.x, ny - self.s.y)
        return self._emit(nx, ny, nz, de, length, arc=True)
