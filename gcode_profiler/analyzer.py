# -*- coding: utf-8 -*-
"""
G-code 解析エンジン
====================
スライサーが設定ブロックをコメントに残していない G-code から、ツールパス実データ
（座標・押出量・速度・温度・レイヤ）を逆算してプロファイル設定を復元する。

この素材の G-code は ;Marker <Feature> <1|0> 形式で各押出区間の意味
(壁/インフィル/サポート/ラフト等) が付与されているため、特徴量ごとに集計できる。
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# 特徴(マーカー) -> 論理フィーチャ分類
# ---------------------------------------------------------------------------
# Orca のカテゴリにマッピングしやすい論理名へ寄せる
FEATURE_MAP = {
    # 外周(見える壁) = アウターウォール
    "ModelContour": "outer_wall",
    "ModelContourEntrance": "outer_wall",
    "ModelContourExit": "outer_wall",
    "ModelContourBottom": "outer_wall",
    "ModelContourBottomEntrance": "outer_wall",
    # 内周(見えない壁) = インナーウォール
    "ModelInvisibleContour": "inner_wall",
    "ModelInvisibleContourBottom": "inner_wall",
    # 疎インフィル
    "InvisibleInfill": "sparse_infill",
    # ソリッド(上下面)
    "VisibleTopInfill": "top_surface",
    "VisibleDefTopInfill": "top_surface",
    "VisibleBottomInfill": "bottom_surface",
    "VisibleDefBottomInfill": "bottom_surface",
    "VisibleDefBottomContour": "bottom_surface",
    # サポート
    "SupportInfill": "support",
    "SupportSmallInfill": "support",
    "SupportInterfaceInfill": "support_interface",
    "SupportInterfaceContour": "support_interface",
    "FirstLayerSupportBase": "support",
    # ラフト
    "Raft": "raft",
    "RaftInterface": "raft",
    "RaftGrid": "raft",
}

WALL_FEATURES = {"outer_wall", "inner_wall"}
INFILL_FEATURES = {"sparse_infill", "top_surface", "bottom_surface"}

# ---------------------------------------------------------------------------
# 他スライサーの ;TYPE: / ; feature コメント -> 論理フィーチャ
#   Cura / PrusaSlicer / SuperSlicer / Slic3r / OrcaSlicer / Simplify3D 各方言を網羅
#   (キーは大文字化・前後空白除去して照合)
# ---------------------------------------------------------------------------
TYPE_FEATURE_MAP = {
    # --- Cura ---
    "WALL-OUTER": "outer_wall",
    "WALL-INNER": "inner_wall",
    "SKIN": "top_surface",
    "FILL": "sparse_infill",
    "SUPPORT": "support",
    "SUPPORT-INTERFACE": "support_interface",
    "SKIRT": "skirt",
    "PRIME-TOWER": "prime_tower",
    # --- PrusaSlicer / SuperSlicer / Slic3r ---
    "EXTERNAL PERIMETER": "outer_wall",
    "PERIMETER": "inner_wall",
    "OVERHANG PERIMETER": "outer_wall",
    "INTERNAL INFILL": "sparse_infill",
    "SOLID INFILL": "bottom_surface",
    "TOP SOLID INFILL": "top_surface",
    "BRIDGE INFILL": "bottom_surface",
    "GAP FILL": "inner_wall",
    "SKIRT/BRIM": "skirt",
    "SUPPORT MATERIAL": "support",
    "SUPPORT MATERIAL INTERFACE": "support_interface",
    "WIPE TOWER": "prime_tower",
    # --- Simplify3D ("; feature outer perimeter") ---
    "OUTER PERIMETER": "outer_wall",
    "INNER PERIMETER": "inner_wall",
    "INFILL": "sparse_infill",
    "SOLID LAYER": "top_surface",
    "SUPPORT": "support",
    "DENSE SUPPORT": "support_interface",
    # --- OrcaSlicer / Bambu ---
    "OUTER WALL": "outer_wall",
    "INNER WALL": "inner_wall",
    "SPARSE INFILL": "sparse_infill",
    "INTERNAL SOLID INFILL": "bottom_surface",
    "TOP SURFACE": "top_surface",
    "BOTTOM SURFACE": "bottom_surface",
    "BRIDGE": "bottom_surface",
    "SUPPORT INTERFACE": "support_interface",
}


def classify_type(text: str):
    """;TYPE: / ; feature の値を論理フィーチャに変換 (不明なら None)"""
    return TYPE_FEATURE_MAP.get(text.strip().upper())


@dataclass
class Segment:
    """1つの押出/移動区間の実測値"""
    feature: str          # 論理フィーチャ名 or "travel"
    length: float         # XY 移動距離 (mm)
    e_delta: float        # フィラメント押出量 (mm)
    speed: float          # mm/s
    z: float              # この区間の Z
    layer: Optional[int]  # レイヤ番号
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class FeatureStats:
    """フィーチャ単位の集計"""
    count: int = 0
    total_length: float = 0.0
    total_e: float = 0.0
    widths: list = field(default_factory=list)
    speeds: list = field(default_factory=list)


def _median(values, default=None):
    vals = [v for v in values if v is not None]
    if not vals:
        return default
    return statistics.median(vals)


def _mode_round(values, ndigits=2, default=None):
    """丸めた上で最頻値を返す(離散的な設定値の復元向き)"""
    vals = [round(v, ndigits) for v in values if v is not None]
    if not vals:
        return default
    counts = defaultdict(int)
    for v in vals:
        counts[v] += 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


class GCodeAnalyzer:
    """G-code を1パスで走査し、特徴量を抽出する"""

    LAYER_RE = re.compile(r";\s*layer\s+(-?\d+)\s*,\s*Z\s*=\s*([-\d.]+)", re.IGNORECASE)
    MARKER_RE = re.compile(r";Marker\s+(.+)")
    # 他スライサーの特徴/レイヤ/寸法コメント
    TYPE_RE = re.compile(r";\s*TYPE\s*:\s*(.+)", re.IGNORECASE)
    FEATURE_RE = re.compile(r";\s*feature\s+(.+)", re.IGNORECASE)   # Simplify3D
    CURA_LAYER_RE = re.compile(r";\s*LAYER\s*:\s*(-?\d+)", re.IGNORECASE)
    WIDTH_RE = re.compile(r";\s*WIDTH\s*:\s*([\d.]+)", re.IGNORECASE)
    HEIGHT_RE = re.compile(r";\s*HEIGHT\s*:\s*([\d.]+)", re.IGNORECASE)
    PRUSA_Z_RE = re.compile(r";\s*Z\s*:\s*([\d.]+)", re.IGNORECASE)
    TEMP_RE = re.compile(r"M10[49].*?\bS([\d.]+)")
    BED_RE = re.compile(r"M1[49]0.*?\bS([\d.]+)")
    CHAMBER_RE = re.compile(r"M141.*?\bS([\d.]+)")
    FAN_RE = re.compile(r"M106.*?\bS([\d.]+)")
    ACCEL_RE = re.compile(r"M204.*?\b[PS]([\d.]+)")
    M207_LEN_RE = re.compile(r"M207.*?\bS([\d.]+)")
    M207_F_RE = re.compile(r"M207.*?\bF([\d.]+)")
    M207_Z_RE = re.compile(r"M207.*?\bZ([\d.]+)")

    def __init__(self, filament_diameter: float = 1.75):
        self.filament_diameter = filament_diameter
        self.reset()

    def reset(self):
        self.x = self.y = self.z = 0.0
        self.e = 0.0
        self.f = 0.0
        self.rel_e = False              # M83 で相対押出
        self.rel_xyz = False            # G91 で相対座標
        self.cur_layer: Optional[int] = None
        self.layer_z: dict = {}         # layer -> Z
        self.feature_stack: list = []   # ;Marker 形式の有効マーカー
        self.cur_type_feature: Optional[str] = None  # ;TYPE: / ; feature 形式の現在フィーチャ
        self.stats: dict = defaultdict(FeatureStats)
        # ;WIDTH: / ;HEIGHT: のヒント(PrusaSlicer/Orca が押出ごとに出力)
        self.width_hint: Optional[float] = None
        self.height_hint: Optional[float] = None
        self.height_hints: list = []
        # 復元用の生データ
        self.temps: list = []
        self.bed_temps: list = []
        self.chamber_temps: list = []
        self.fan_values: list = []
        self.accels: list = []
        self.retractions: list = []     # (length, speed)
        self.deretractions: list = []
        self.zhops: list = []
        self.travel_speeds: list = []
        self.first_layer_speeds: list = []
        self.print_z_set: set = set()   # 押出が起きた Z (層厚算出のフォールバック)
        self._lh_dirty = True            # 層厚キャッシュの再計算フラグ
        self._cached_lh = 0.2
        self.fw_retract_count = 0       # G10/G11 ファーム内リトラクト回数
        self.fw_retract_len: Optional[float] = None   # M207 由来
        self.fw_retract_speed: Optional[float] = None
        self.fw_zhop: Optional[float] = None
        self.has_raft = False
        self.has_support = False
        self.infill_lines: list = []     # (angle, perp_offset) 密度推定用
        self._marker_style_seen = False
        self._type_style_seen = False
        # 埋め込み設定の取り込み(主流スライサーはコメントに設定を残す)
        self.header_comments: list = []   # 先頭付近のコメント(スライサー判定用)
        self.config_kv: dict = {}         # "; key = value" 形式 (PrusaSlicer/Orca系)
        self.s3d_kv: dict = {}            # ";   key,value" 形式 (Simplify3D)
        # スタート/エンド/ツールチェンジ G-code ブロック抽出
        self.printing_started = False
        self.start_lines: list = []       # 最初の押出より前(=スタートG-code)
        self.tail_lines: list = []        # 最後の押出より後ろ(=エンドG-code)。押出ごとにクリア
        self.tool_changes: list = []      # 観測した工具番号(順序)
        self.tools_used: set = set()
        self.active_tool = 0
        self.temps_by_tool: dict = defaultdict(list)       # tool -> [温度,...]
        self.bed_by_tool: dict = defaultdict(list)
        self.retract_by_tool: dict = defaultdict(list)     # tool -> [長さ,...]
        self._tc_capturing = False
        self._tc_buf: list = []
        self.toolchange_gcode: list = []  # 代表的なツールチェンジ列
        self._extrusion_events = 0

    # -- フィラメント断面積 --
    @property
    def filament_area(self) -> float:
        return math.pi * (self.filament_diameter / 2.0) ** 2

    # -- 現在の論理フィーチャ --
    def current_feature(self) -> str:
        # ;Marker 形式を優先(この産業機)。無ければ ;TYPE:/; feature 形式。
        for name in reversed(self.feature_stack):
            mapped = FEATURE_MAP.get(name)
            if mapped:
                return mapped
        if self.cur_type_feature:
            return self.cur_type_feature
        return "unknown"

    def analyze_file(self, path: str, progress_cb=None):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            self.analyze_lines(fh, progress_cb=progress_cb)
        return self.build_result()

    def analyze_lines(self, lines, progress_cb=None):
        for i, raw in enumerate(lines):
            line = raw.strip().strip('"').strip()  # この素材はコメント行が "..." で囲まれる場合がある
            if not line:
                continue
            before = self._extrusion_events
            if line.startswith(";"):
                self._handle_comment(line)
            else:
                cmd = line.split(";", 1)[0].strip()  # 行末コメント除去
                if cmd:
                    self._handle_command(cmd)
            self._capture_block_line(line, extruded=(self._extrusion_events > before))
            if progress_cb and (i & 0xFFFF) == 0:
                progress_cb(i)

    def _capture_block_line(self, line: str, extruded: bool):
        """スタート/エンド/ツールチェンジ G-code を行単位で抽出する。"""
        # 埋め込み設定の dump 行はブロックに含めない
        is_config = (self.CONFIG_KV_RE.match(line) or self.S3D_KV_RE.match(line)
                     or "_config = begin" in line or "_config = end" in line)
        if not self.printing_started:
            if extruded:
                self.printing_started = True   # この行(最初の押出)以降は本体
            elif not is_config:
                self.start_lines.append(line)
            return
        # 本体開始後: 最後の押出より後ろを末尾バッファに溜める(押出が来たらクリア)
        if extruded:
            self.tail_lines = []
        elif not is_config:
            self.tail_lines.append(line)
        # ツールチェンジ列の捕捉(最初の1回を代表として保存)
        if self._tc_capturing:
            if extruded:
                self._tc_capturing = False
                if not self.toolchange_gcode:
                    self.toolchange_gcode = self._tc_buf[:]
            else:
                self._tc_buf.append(line)

    CONFIG_KV_RE = re.compile(r"^;\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")
    S3D_KV_RE = re.compile(r"^;\s{2,}([A-Za-z][A-Za-z0-9_]*)\s*,\s*(.+?)\s*$")

    # ------------------------------------------------------------------
    def _handle_comment(self, line: str):
        # スライサー判定用にヘッダーコメントを保持
        if len(self.header_comments) < 80:
            self.header_comments.append(line)
        # 埋め込み設定 "; key = value" (PrusaSlicer/SuperSlicer/Slic3r/Orca)
        mkv = self.CONFIG_KV_RE.match(line)
        if mkv:
            self.config_kv[mkv.group(1)] = mkv.group(2)
        else:
            # Simplify3D ";   key,value"
            ms = self.S3D_KV_RE.match(line)
            if ms:
                self.s3d_kv[ms.group(1)] = ms.group(2)
        # この産業機: "; layer N, Z = z"
        m = self.LAYER_RE.search(line)
        if m:
            self.cur_layer = int(m.group(1))
            self.layer_z[self.cur_layer] = float(m.group(2))
            self._lh_dirty = True
            return
        # この産業機: ";Marker <Feature> <1|0>"
        m = self.MARKER_RE.match(line)
        if m:
            self._marker_style_seen = True
            self._handle_markers(m.group(1))
            return
        # Cura/Prusa/Orca/Slic3r: ";TYPE:<name>"
        m = self.TYPE_RE.match(line)
        if m:
            self._type_style_seen = True
            self.cur_type_feature = classify_type(m.group(1)) or "unknown"
            ft = self.cur_type_feature
            if ft == "support" or ft == "support_interface":
                self.has_support = True
            return
        # Simplify3D: "; feature <name>"
        m = self.FEATURE_RE.match(line)
        if m:
            self._type_style_seen = True
            self.cur_type_feature = classify_type(m.group(1)) or "unknown"
            if self.cur_type_feature in ("support", "support_interface"):
                self.has_support = True
            return
        # Cura: ";LAYER:N"
        m = self.CURA_LAYER_RE.match(line)
        if m:
            self.cur_layer = int(m.group(1))
            self.layer_z.setdefault(self.cur_layer, self.z)
            self._lh_dirty = True
            return
        # PrusaSlicer: ";WIDTH:x" / ";HEIGHT:x" (押出ごとの実寸)
        m = self.WIDTH_RE.match(line)
        if m:
            self.width_hint = float(m.group(1))
            return
        m = self.HEIGHT_RE.match(line)
        if m:
            h = float(m.group(1))
            self.height_hint = h
            if 0.01 < h < 2.0:
                self.height_hints.append(h)
            return
        # PrusaSlicer: ";Z:height" (LAYER_CHANGE 後)
        m = self.PRUSA_Z_RE.match(line)
        if m:
            z = float(m.group(1))
            idx = (max(self.layer_z) + 1) if self.layer_z else 0
            self.layer_z[idx] = z
            self.cur_layer = idx
            self._lh_dirty = True
            return

    def _handle_markers(self, payload: str):
        # 例: "ModelContour 1 | Layer -5"  /  "Raft 0 | Jump 1"
        for token in payload.split("|"):
            token = token.strip()
            parts = token.split()
            if len(parts) < 2:
                continue
            name, state = parts[0], parts[-1]
            if name in ("Layer",):
                continue
            if state == "1":
                self.feature_stack.append(name)
                if name.startswith("Raft"):
                    self.has_raft = True
                if name.startswith("Support") or name == "FirstLayerSupportBase":
                    self.has_support = True
            elif state == "0":
                # 末尾から該当を1つ除去
                for idx in range(len(self.feature_stack) - 1, -1, -1):
                    if self.feature_stack[idx] == name:
                        del self.feature_stack[idx]
                        break

    # ------------------------------------------------------------------
    TOOL_RE = re.compile(r"^T(\d+)\b")
    TEMP_TOOL_RE = re.compile(r"\bT(\d+)")

    def _handle_command(self, cmd: str):
        code = cmd.split()[0].upper()
        # ツールチェンジ (T0/T1/...) — マルチフィラメント
        mt = self.TOOL_RE.match(code)
        if mt:
            tool = int(mt.group(1))
            self.active_tool = tool
            self.tools_used.add(tool)
            self.tool_changes.append(tool)
            if self.printing_started and not self.toolchange_gcode:
                self._tc_capturing = True
                self._tc_buf = []
            return
        if code in ("G0", "G1"):
            self._handle_move(cmd, rapid=(code == "G0"))
        elif code in ("G2", "G3"):
            self._handle_arc(cmd)
        elif code == "G92":
            self._handle_g92(cmd)
        elif code in ("G10",):           # ファーム内リトラクト (Marlin/RepRap)
            self.fw_retract_count += 1
        elif code in ("G11",):           # ファーム内アンリトラクト
            pass
        elif code == "M207":             # ファーム内リトラクト設定
            m = self.M207_LEN_RE.search(cmd)
            if m:
                self.fw_retract_len = float(m.group(1))
            m = self.M207_F_RE.search(cmd)
            if m:
                self.fw_retract_speed = float(m.group(1)) / 60.0
            m = self.M207_Z_RE.search(cmd)
            if m:
                self.fw_zhop = float(m.group(1))
        elif code == "G90":
            self.rel_xyz = False
        elif code == "G91":
            self.rel_xyz = True
        elif code == "M82":
            self.rel_e = False
        elif code == "M83":
            self.rel_e = True
        elif code in ("M104", "M109"):
            m = self.TEMP_RE.search(cmd)
            if m:
                v = float(m.group(1))
                if v > 0:
                    self.temps.append(v)
                    mt2 = self.TEMP_TOOL_RE.search(cmd)
                    tool = int(mt2.group(1)) if mt2 else self.active_tool
                    self.temps_by_tool[tool].append(v)
        elif code in ("M140", "M190"):
            m = self.BED_RE.search(cmd)
            if m:
                v = float(m.group(1))
                self.bed_temps.append(v)
                self.bed_by_tool[self.active_tool].append(v)
        elif code == "M141":
            m = self.CHAMBER_RE.search(cmd)
            if m:
                self.chamber_temps.append(float(m.group(1)))
        elif code == "M106":
            m = self.FAN_RE.search(cmd)
            if m:
                self.fan_values.append(float(m.group(1)))
        elif code == "M107":
            self.fan_values.append(0.0)
        elif code == "M204":
            m = self.ACCEL_RE.search(cmd)
            if m:
                self.accels.append(float(m.group(1)))

    def _parse_axes(self, cmd: str):
        out = {}
        for tok in cmd.split()[1:]:
            if not tok:
                continue
            axis = tok[0].upper()
            if axis in "XYZEF":
                try:
                    out[axis] = float(tok[1:])
                except ValueError:
                    pass
        return out

    def _handle_g92(self, cmd: str):
        ax = self._parse_axes(cmd)
        if "E" in ax:
            self.e = ax["E"]

    def _handle_move(self, cmd: str, rapid: bool):
        ax = self._parse_axes(cmd)
        x0, y0, z0 = self.x, self.y, self.z
        if self.rel_xyz:
            nx = x0 + ax.get("X", 0.0)
            ny = y0 + ax.get("Y", 0.0)
            nz = z0 + ax.get("Z", 0.0)
        else:
            nx = ax.get("X", self.x)
            ny = ax.get("Y", self.y)
            nz = ax.get("Z", self.z)
        if "F" in ax:
            self.f = ax["F"]
        speed = self.f / 60.0 if self.f else 0.0
        e_delta = self._e_delta(ax)

        dx, dy = nx - x0, ny - y0
        length = math.hypot(dx, dy)
        dz = nz - z0

        # --- Z 変化(レイヤ移動 or Zホップ) ---
        if abs(dz) > 1e-6 and length < 1e-6:
            if dz > 0:
                self._pending_zhop = (z0, nz)
            else:
                pend = getattr(self, "_pending_zhop", None)
                if pend and abs(nz - pend[0]) < 0.05:
                    hop = round(pend[1] - pend[0], 3)
                    if 0.02 < hop < 2.0:
                        self.zhops.append(hop)
                self._pending_zhop = None
            self.z = nz
            self.x, self.y = nx, ny
            return

        # --- 純粋な E のみの動作(リトラクト/プライム) ---
        if length < 1e-6 and abs(e_delta) > 1e-9 and "X" not in ax and "Y" not in ax:
            if e_delta < 0:
                self.retractions.append((-e_delta, speed))
                self.retract_by_tool[self.active_tool].append(-e_delta)
            else:
                self.deretractions.append((e_delta, speed))
            self.z = nz
            return

        # --- 通常の移動/押出 ---
        if length >= 1e-6:
            if e_delta > 1e-9:
                self._record_extrusion(length, e_delta, speed, nz, x0, y0, nx, ny)
            else:
                if speed > 0:
                    self.travel_speeds.append(speed)

        self.x, self.y, self.z = nx, ny, nz

    def _e_delta(self, ax):
        if "E" not in ax:
            return 0.0
        if self.rel_e:
            d = ax["E"]
            self.e += ax["E"]
            return d
        d = ax["E"] - self.e
        self.e = ax["E"]
        return d

    def _handle_arc(self, cmd: str):
        """G2/G3 円弧。I/J 中心オフセットから弧長を求めて押出を記録する。"""
        ax = self._parse_axes_arc(cmd)
        x0, y0 = self.x, self.y
        nx = ax.get("X", x0)
        ny = ax.get("Y", y0)
        nz = ax.get("Z", self.z)
        if "F" in ax:
            self.f = ax["F"]
        speed = self.f / 60.0 if self.f else 0.0
        e_delta = self._e_delta(ax)
        i = ax.get("I", 0.0)
        j = ax.get("J", 0.0)
        cx, cy = x0 + i, y0 + j
        r = math.hypot(i, j)
        if r < 1e-9:
            length = math.hypot(nx - x0, ny - y0)
        else:
            a0 = math.atan2(y0 - cy, x0 - cx)
            a1 = math.atan2(ny - cy, nx - cx)
            da = a1 - a0
            # G2 は時計回り(角度減少)、G3 は反時計回り(角度増加)
            cw = cmd.split()[0].upper() == "G2"
            if cw and da > 0:
                da -= 2 * math.pi
            elif (not cw) and da < 0:
                da += 2 * math.pi
            length = abs(da) * r
        if length >= 1e-6 and e_delta > 1e-9:
            self._record_extrusion(length, e_delta, speed, nz, x0, y0, nx, ny)
        self.x, self.y, self.z = nx, ny, nz

    def _parse_axes_arc(self, cmd: str):
        out = {}
        for tok in cmd.split()[1:]:
            if not tok:
                continue
            axis = tok[0].upper()
            if axis in "XYZEFIJ":
                try:
                    out[axis] = float(tok[1:])
                except ValueError:
                    pass
        return out

    def _record_extrusion(self, length, e_delta, speed, z, x0, y0, x1, y1):
        feature = self.current_feature()
        layer = self.cur_layer
        if z > 0:
            n = len(self.print_z_set)
            self.print_z_set.add(round(z, 3))
            if len(self.print_z_set) != n:
                self._lh_dirty = True
        # ライン幅: ;WIDTH: ヒントがあれば最優先、無ければ体積から逆算
        if self.width_hint:
            width = self.width_hint
        else:
            h = self.height_hint or self._layer_height_for(z)
            volume = e_delta * self.filament_area
            width = volume / (length * h) if (length > 0 and h > 0) else None

        self._extrusion_events += 1
        st = self.stats[feature]
        st.count += 1
        st.total_length += length
        st.total_e += e_delta
        if width and 0.05 < width < 3.0:
            st.widths.append(width)
        if speed > 0:
            st.speeds.append(speed)

        # 初層速度
        if layer is not None and layer == self._first_print_layer():
            if speed > 0:
                self.first_layer_speeds.append(speed)

        # インフィル線の「向き」と「垂直位置」を記録(密度推定用)
        # 同方向の平行線群の垂直間隔 = ライン間隔 として後で集計する
        if feature == "sparse_infill" and length > 0.5:
            ang = math.atan2(y1 - y0, x1 - x0) % math.pi   # 0..pi
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            perp = -math.sin(ang) * mx + math.cos(ang) * my  # 法線方向の位置
            self.infill_lines.append((round(ang, 2), perp))

    # ------------------------------------------------------------------
    def _layer_heights(self):
        """layer コメントの Z 列から各層厚を算出"""
        items = sorted(self.layer_z.items())
        heights = []
        prev_z = None
        for _layer, z in items:
            if prev_z is not None:
                dz = round(z - prev_z, 4)
                if 0.01 < dz < 2.0:
                    heights.append(dz)
            prev_z = z
        # 明示レイヤが乏しければ、押出した Z 集合の差分を層厚として使う(全方言で機能)
        if len(heights) < 2 and len(self.print_z_set) >= 2:
            zs = sorted(self.print_z_set)
            for a, b in zip(zs, zs[1:]):
                dz = round(b - a, 4)
                if 0.01 < dz < 2.0:
                    heights.append(dz)
        return heights

    def _layer_height_for(self, z):
        """与えた Z の層厚。;HEIGHT: ヒント > 最頻層厚(キャッシュ) > 既定。
        毎押出で呼ばれるため、新レイヤ検出時のみ再計算してキャッシュする。"""
        if self.height_hint:
            return self.height_hint
        if self._lh_dirty:
            heights = self._layer_heights()
            self._cached_lh = _mode_round(heights, 3, 0.2) if heights else 0.2
            self._lh_dirty = False
        return self._cached_lh

    def _first_print_layer(self):
        # 0 以上の最小レイヤ (ラフト/サポートの負レイヤを除く)
        pos = [l for l in self.layer_z if l >= 0]
        if pos:
            return min(pos)
        if self.layer_z:
            return min(self.layer_z)
        return 0

    # ------------------------------------------------------------------
    def build_result(self) -> dict:
        if self.height_hints:
            layer_h = _mode_round(self.height_hints, 3, None)
        else:
            layer_h = _mode_round(self._layer_heights(), 3, None)
        # 初層高さ
        items = sorted(self.layer_z.items())
        first_layer_h = None
        if len(items) >= 2:
            # 最初の正レイヤの厚み
            for i in range(1, len(items)):
                first_layer_h = round(items[i][1] - items[i - 1][1], 3)
                if first_layer_h > 0:
                    break
        if first_layer_h is None and self.print_z_set:
            first_layer_h = round(min(self.print_z_set), 3)  # 幾何のみのフォールバック

        # 特徴マーカーが無い(生のRepRap/Klipper等)場合、全押出を代表値として使う
        geom_only = not (self._marker_style_seen or self._type_style_seen)
        unk_w = _median(self.stats["unknown"].widths)
        unk_s = _median(self.stats["unknown"].speeds)

        def feat_width(f):
            v = _median(self.stats[f].widths)
            if v is None and geom_only:
                return unk_w
            return v

        def feat_speed(f):
            v = _median(self.stats[f].speeds)
            if v is None and geom_only:
                return unk_s
            return v

        # 壁数推定: 各レイヤの outer+inner ループ数 / レイヤ数
        wall_loops = self._estimate_wall_loops()

        # インフィル密度推定
        infill_density = self._estimate_infill_density(feat_width("sparse_infill"))

        result = {
            "meta": {
                "filament_diameter": self.filament_diameter,
                "total_layers": len([l for l in self.layer_z if l >= 0]),
                "z_max": max(self.layer_z.values()) if self.layer_z else None,
                "features_seen": {f: self.stats[f].count for f in self.stats},
                "feature_style": ("Marker(産業機)" if self._marker_style_seen
                                  else ";TYPE:/feature" if self._type_style_seen
                                  else "なし(幾何のみ)"),
                "method": "ツールパス逆算",
                "source": "不明",
            },
            "_embedded": {
                "header": self.header_comments,
                "config_kv": self.config_kv,
                "s3d_kv": self.s3d_kv,
            },
            "quality": {
                "layer_height": layer_h,
                "first_layer_height": first_layer_h,
                "outer_wall_width": feat_width("outer_wall"),
                "inner_wall_width": feat_width("inner_wall"),
                "sparse_infill_width": feat_width("sparse_infill"),
                "top_surface_width": feat_width("top_surface"),
                "support_width": feat_width("support"),
            },
            "speed": {
                "outer_wall_speed": feat_speed("outer_wall"),
                "inner_wall_speed": feat_speed("inner_wall"),
                "sparse_infill_speed": feat_speed("sparse_infill"),
                "top_surface_speed": feat_speed("top_surface"),
                "support_speed": feat_speed("support"),
                "travel_speed": _median(self.travel_speeds),
                "first_layer_speed": _median(self.first_layer_speeds),
                "outer_wall_accel": _mode_round(self.accels, 0),
                "accels_seen": sorted(set(round(a) for a in self.accels)),
            },
            "strength": {
                "wall_loops": wall_loops,
                "sparse_infill_density_pct": infill_density,
                "infill_line_width": feat_width("sparse_infill"),
                "has_support": self.has_support,
                "has_raft": self.has_raft,
            },
            "temperature": {
                "nozzle_temp": _mode_round(self.temps, 0),
                "nozzle_temps_seen": sorted(set(round(t) for t in self.temps)),
                "bed_temp": _mode_round(self.bed_temps, 0),
                "chamber_temp": _mode_round(self.chamber_temps, 0),
                "fan_max_pct": self._fan_pct(),
            },
            "retraction": {
                # G1 ベースのリトラクトが無く M207(ファーム内)のみの場合はそちらを採用
                "retract_length": _mode_round([r[0] for r in self.retractions], 2)
                                  if self.retractions else self.fw_retract_len,
                "retract_speed": _mode_round([r[1] for r in self.retractions], 0)
                                 if self.retractions else self.fw_retract_speed,
                "deretract_speed": _mode_round([d[1] for d in self.deretractions], 0),
                "z_hop_height": _mode_round(self.zhops, 2) if self.zhops else self.fw_zhop,
                "retract_count": len(self.retractions) + self.fw_retract_count,
            },
            "filaments": self._build_filaments(),
            "gcode_blocks": {
                "start_gcode": "\n".join(self.start_lines).strip(),
                "end_gcode": "\n".join(self.tail_lines).strip(),
                "toolchange_gcode": "\n".join(self.toolchange_gcode).strip(),
            },
        }
        result["meta"]["tool_count"] = len(self.tools_used) or 1
        result["meta"]["tools_used"] = sorted(self.tools_used)
        return result

    def _build_filaments(self):
        """ツール(エクストルーダ)ごとのフィラメント設定を組み立てる。
        マルチフィラメント時は各ツールの温度/リトラクトを個別に保持。"""
        tools = sorted(self.tools_used) or [0]
        filaments = []
        for t in tools:
            temps = self.temps_by_tool.get(t, [])
            beds = self.bed_by_tool.get(t, [])
            rets = self.retract_by_tool.get(t, [])
            filaments.append({
                "tool": t,
                "nozzle_temp": _mode_round(temps, 0) if temps else _mode_round(self.temps, 0),
                "bed_temp": _mode_round(beds, 0) if beds else _mode_round(self.bed_temps, 0),
                "retract_length": _mode_round(rets, 2) if rets else None,
            })
        return filaments

    def _fan_pct(self):
        if not self.fan_values:
            return None
        mx = max(self.fan_values)
        return round(mx / 255.0 * 100) if mx > 0 else 0

    def _estimate_wall_loops(self):
        """壁ループ数の概算。outer+inner の押出区間数を総レイヤ数で割る…のは粗いので
        ループ(連続した同フィーチャ閉路)数で近似する簡易版。"""
        outer = self.stats["outer_wall"].count
        inner = self.stats["inner_wall"].count
        layers = max(1, len([l for l in self.layer_z if l >= 0]))
        # 1ループあたりおおよその区間数で割る代わりに、外周は通常1なので
        # inner/outer 区間比からループ数を推定
        if outer == 0:
            return None
        ratio = (outer + inner) / outer
        return max(1, round(ratio))

    def _estimate_infill_density(self, line_width):
        """同方向の平行インフィル線群の垂直間隔から密度を推定。
        density ≈ ライン幅 / ライン間隔 * 100"""
        if not self.infill_lines or not line_width:
            return None
        # 最も多い向き(支配的な充填方向)のみ採用
        by_angle = defaultdict(list)
        for ang, perp in self.infill_lines:
            by_angle[ang].append(perp)
        ang, perps = max(by_angle.items(), key=lambda kv: len(kv[1]))
        if len(perps) < 3:
            return None
        perps = sorted(perps)
        # 隣接する平行線の垂直間隔(同一線の重複は除外)
        diffs = [round(b - a, 3) for a, b in zip(perps, perps[1:]) if (b - a) > line_width * 0.5]
        spacing = _mode_round(diffs, 2) if diffs else None
        if not spacing or spacing <= 0:
            return None
        density = min(100.0, line_width / spacing * 100.0)
        return round(density)


def analyze(path: str, filament_diameter: float = 1.75, progress_cb=None) -> dict:
    try:
        from .containers import open_gcode
        from .sources import apply_embedded, apply_bambu_config
    except ImportError:
        from containers import open_gcode
        from sources import apply_embedded, apply_bambu_config

    src = open_gcode(path)
    an = GCodeAnalyzer(filament_diameter)
    an.analyze_lines(src["lines"], progress_cb=progress_cb)
    result = an.build_result()
    # コメント埋め込み設定(PrusaSlicer系 等)を上書き
    apply_embedded(result)
    # 3mf の project_settings.config(JSON)があれば最優先で上書き
    if src.get("bambu_config"):
        apply_bambu_config(result, src["bambu_config"])
    # ノズル径推定 + 素材推定を付加
    _attach_nozzle_and_material(result, path, filament_diameter)
    return result


def _attach_nozzle_and_material(result, path, filament_diameter):
    try:
        from .nozzle_estimator import estimate as estimate_nozzle
        from .material import estimate_material
    except ImportError:
        from nozzle_estimator import estimate_nozzle  # type: ignore
        from material import estimate_material
    try:
        nozzle = estimate_nozzle(path, default_filament=filament_diameter)
    except Exception:  # noqa  推定失敗は致命的ではない
        nozzle = None
    if nozzle:
        result["nozzle"] = nozzle
        result["meta"]["nozzle_diameter_est"] = nozzle.get("estimated_nozzle_diameter")
        result["meta"]["nozzle_confidence"] = nozzle.get("confidence_percent")
    chamber = result.get("temperature", {}).get("chamber_temp")
    for fl in result.get("filaments", []):
        tool = fl.get("tool", 0)
        if nozzle:
            t = nozzle.get("tools", {}).get(str(tool))
            if t:
                fl["nozzle_diameter"] = t.get("estimated_nozzle_diameter")
        mat = estimate_material(fl.get("nozzle_temp"), fl.get("bed_temp"), chamber)
        fl["material"] = mat["material"]
        fl["material_confidence"] = mat["confidence"]
