# -*- coding: utf-8 -*-
"""
ノズル径推定エンジン + ライン幅誤差評価
=======================================
FFF/FDM 用 G-code を1パス・ストリーム処理で解析し、使用ノズル径を推定する。
ライン幅は「単一の正解」ではなく、誤差要因を評価して推定値・誤差範囲・信頼度・
品質グレードとして出力する(理論ライン幅であり実測値ではない)。

仕様 §14 の役割分担:
  LineWidthCalculator          : 線分/グループの理論ライン幅 (stadium断面)
  SegmentReliabilityScorer     : 造形種類/線分長/リトラクト/工具交換/層厚信頼度 → 重み
  LineWidthDistributionAnalyzer: 重み付き中央値/最頻値/ピーク/可変線幅判定
  UncertaintyEstimator         : 一次誤差伝播(既定) / 最悪値評価
  ErrorSourceDetector          : PA/流量変更/短線分過多/径不明/層厚不明 等の検出

公開 API:
    estimate(path, **opts) -> dict
    estimate_lines(lines, **opts) -> dict
    format_human(result) -> str
"""
from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict

PI = math.pi
C_STADIUM = 1 - PI / 4  # ライン幅式の第2項係数

DEFAULT_NOZZLES = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60, 0.80, 1.00, 1.20, 1.50, 2.00]

EXCLUDED_FEATURES = {
    "skirt", "brim", "raft", "support", "support_interface", "bridge", "gap_fill",
    "ironing", "wipe", "wipe_tower", "prime_tower", "prime", "purge",
    "ooze_shield", "draft_shield", "thin_wall",
}

# 造形種類別の信頼度重み (§6.1)
FEATURE_WEIGHT = {
    "outer_wall": 1.00, "inner_wall": 0.90, "sparse_infill": 0.75,
    "solid_infill": 0.65, "top_surface": 0.65, "bottom_surface": 0.65,
    "unknown": 0.50, "thin_wall": 0.40, "gap_fill": 0.20,
}

MAX_SAMPLES_PER_KEY = 200_000


# ---------------------------------------------------------------------------
# フィーチャ分類
# ---------------------------------------------------------------------------
_FEATURE_LOOKUP = {
    "external perimeter": "outer_wall", "perimeter": "inner_wall",
    "overhang perimeter": "outer_wall", "internal infill": "sparse_infill",
    "solid infill": "solid_infill", "top solid infill": "top_surface",
    "bridge infill": "bridge", "gap fill": "gap_fill", "skirt": "skirt",
    "skirt/brim": "skirt", "brim": "brim", "support material": "support",
    "support material interface": "support_interface", "wipe tower": "wipe_tower",
    "ironing": "ironing", "thin wall": "thin_wall",
    "outer wall": "outer_wall", "inner wall": "inner_wall",
    "sparse infill": "sparse_infill", "internal solid infill": "solid_infill",
    "top surface": "top_surface", "bottom surface": "bottom_surface",
    "bridge": "bridge", "support": "support", "support interface": "support_interface",
    "prime tower": "prime_tower",
    "wall-outer": "outer_wall", "wall-inner": "inner_wall", "fill": "sparse_infill",
    "skin": "top_surface", "support-interface": "support_interface",
    "prime-tower": "prime_tower",
    "outer perimeter": "outer_wall", "inner perimeter": "inner_wall",
    "infill": "sparse_infill", "solid layer": "solid_infill", "dense support": "support_interface",
    "modelcontour": "outer_wall", "modelinvisiblecontour": "inner_wall",
    "invisibleinfill": "sparse_infill", "visibletopinfill": "top_surface",
    "supportinfill": "support",
}


def classify_feature(text: str):
    t = text.strip().lower()
    if t in _FEATURE_LOOKUP:
        return _FEATURE_LOOKUP[t]
    for key, val in _FEATURE_LOOKUP.items():
        if key in t:
            return val
    return None


# ---------------------------------------------------------------------------
# メタデータ解析 (§2)
# ---------------------------------------------------------------------------
_META_PATTERNS = {
    "nozzle_diameter": ["nozzlediameter", "nozzlesize"],
    "filament_diameter": ["filamentdiameter"],
    "layer_height": ["layerheight"],
    "first_layer_height": ["firstlayerheight", "initiallayerprintheight"],
    "extrusion_width": ["extrusionwidth", "linewidth", "outerwalllinewidth"],
    "flow": ["extrusionmultiplier", "flowratio", "filamentflowratio"],
}
_KV_RE = re.compile(r"^\s*;?\s*([A-Za-z0-9_\-\. \[\]]+?)\s*(?:=|:)\s*(.+?)\s*$")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _norm_key(k):
    return re.sub(r"[\s_\-]", "", k.strip().lower())


def _numbers(s):
    return [float(x) for x in _NUM_RE.findall(s)]


class Metadata:
    def __init__(self):
        self.nozzle_diameter = {}
        self.filament_diameter = {}
        self.layer_height = None
        self.first_layer_height = None
        self.extrusion_width = None
        self.flow = None
        self.raw_hits = {}

    def feed_comment(self, line):
        m = _KV_RE.match(line)
        if not m:
            return
        rawkey, rawval = m.group(1), m.group(2)
        idx = None
        bracket = re.search(r"\[(\d+)\]", rawkey)
        if bracket:
            idx = int(bracket.group(1))
            rawkey = rawkey[:bracket.start()]
        nk = _norm_key(rawkey)
        for canon, aliases in _META_PATTERNS.items():
            if nk in aliases:
                nums = _numbers(rawval)
                if not nums:
                    return
                self.raw_hits.setdefault(canon, rawval)
                if canon in ("nozzle_diameter", "filament_diameter"):
                    target = getattr(self, canon)
                    if idx is not None:
                        target[idx] = nums[0]
                    else:
                        for i, v in enumerate(nums):
                            target[i] = v
                else:
                    setattr(self, canon, nums[0])
                return


# ---------------------------------------------------------------------------
# PressureAdvanceTracker — PA/Linear Advance の検出(別仕様)
# ---------------------------------------------------------------------------
_PA_COMMENT_KEYS = {"pressureadvance", "linearadvance", "advancek", "pavalue",
                    "filamentpressureadvance", "linearadvancek"}


def _ext_to_tool(name):
    if not name:
        return None
    m = re.search(r"(\d+)\s*$", str(name))
    return int(m.group(1)) if m else 0


def _kw_params(cmd):
    out = {}
    for tok in cmd.split()[1:]:
        if "=" in tok:
            k, v = tok.split("=", 1)
            out[k.strip().upper()] = v.strip()
    return out


def _letter_params(cmd, allowed):
    out = {}
    for tok in cmd.split()[1:]:
        if tok and tok[0].upper() in allowed:
            try:
                out[tok[0].upper()] = float(tok[1:])
            except ValueError:
                pass
    return out


def _fnum(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pa_from_comment(line):
    m = _KV_RE.match(line)
    if not m:
        return None
    if _norm_key(m.group(1)) in _PA_COMMENT_KEYS:
        nums = _numbers(m.group(2))
        return nums[0] if nums else None
    return None


class PressureAdvanceTracker:
    """ツール/押出機ごとに PA(=Klipper) / Linear Advance(=Marlin K) / M572 を追跡。
    明示命令 > メタデータ > 不明 の優先順位。明示的な 0 と未設定(null)を区別する。"""
    def __init__(self):
        self.per_tool = {}
        self.unknown_commands = []

    def _state(self, tool):
        return self.per_tool.setdefault(tool, {
            "detected": False, "enabled": None, "value": None,
            "source": "not_found", "firmware": None, "smooth_time": None,
            "history": [],
        })

    def _close(self, s, line):
        if s["history"] and s["history"][-1]["end_line"] is None:
            s["history"][-1]["end_line"] = line - 1

    def apply_command(self, tool, value, firmware, line, smooth_time=None):
        s = self._state(tool)
        self._close(s, line)
        s.update(detected=True, enabled=(value > 0), value=value,
                 source="gcode_command", firmware=firmware)
        if smooth_time is not None:
            s["smooth_time"] = smooth_time
        s["history"].append({"start_line": line, "end_line": None, "value": value})

    def apply_comment(self, tool, value, firmware="unknown"):
        s = self._state(tool)
        if s["source"] == "gcode_command":
            return  # 実行命令を優先
        s.update(detected=True, enabled=(value > 0), value=value,
                 source="metadata", firmware=firmware)

    def any_active(self):
        return any(s["enabled"] for s in self.per_tool.values())

    def summary(self, tool):
        s = self.per_tool.get(tool)
        if not s:
            return {"detected": False, "enabled": None, "value": None,
                    "firmware": None, "source": "not_found", "smooth_time": None,
                    "confidence_percent": 0, "history": [],
                    "used_for_line_width_correction": False}
        conf = 100 if s["source"] == "gcode_command" else (70 if s["source"] == "metadata" else 0)
        return {**s, "confidence_percent": conf, "used_for_line_width_correction": False}


# ---------------------------------------------------------------------------
# LineWidthCalculator (§1/§3)
# ---------------------------------------------------------------------------
def line_width(volume, length, h):
    """stadium 断面モデルの理論ライン幅。"""
    if length <= 0 or h <= 0 or volume <= 0:
        return None
    return volume / (length * h) + h * C_STADIUM


# ---------------------------------------------------------------------------
# SegmentReliabilityScorer (§6)
# ---------------------------------------------------------------------------
class SegmentReliabilityScorer:
    @staticmethod
    def length_weight(L):
        if L < 0.5:
            return 0.0
        if L < 2.0:
            return 0.25
        if L < 5.0:
            return 0.60
        if L < 10.0:
            return 0.85
        return 1.0

    @staticmethod
    def retract_weight(since_retract):
        if since_retract <= 0:
            return 0.25
        if since_retract == 1:
            return 0.60
        return 1.0

    @staticmethod
    def tool_weight(since_tool):
        if since_tool <= 0:
            return 0.0
        if since_tool == 1:
            return 0.50
        return 1.0

    @staticmethod
    def lh_weight(source):
        return {"comment": 1.0, "zdiff": 0.90, "variable": 0.75,
                "ambiguous": 0.40, "assumed": 0.20}.get(source, 0.4)

    @classmethod
    def score(cls, feature, L, since_retract, since_tool, lh_source):
        fw = FEATURE_WEIGHT.get(feature, 0.5)
        return (fw * cls.length_weight(L) * cls.retract_weight(since_retract)
                * cls.tool_weight(since_tool) * cls.lh_weight(lh_source))


# ---------------------------------------------------------------------------
# UncertaintyEstimator (§4/§5) — 一次誤差伝播
# ---------------------------------------------------------------------------
class UncertaintyEstimator:
    def __init__(self, filament_sigma=0.02, flow_sigma=0.02, layer_sigma=0.005,
                 length_rel_sigma=0.001):
        self.filament_sigma = filament_sigma
        self.flow_sigma = flow_sigma
        self.layer_sigma = layer_sigma
        self.length_rel_sigma = length_rel_sigma

    def propagate(self, rep_w, L, h, d_fil, layer_assumed=False):
        """代表 (w,L,h) と入力不確かさからライン幅の標準不確かさと95%区間を返す。"""
        if not rep_w or not L or not h or L <= 0 or h <= 0:
            return None
        term1 = max(1e-6, rep_w - C_STADIUM * h)
        V = term1 * L * h
        sig_d = self.filament_sigma
        rel_V = math.sqrt((2 * sig_d / d_fil) ** 2 + self.flow_sigma ** 2)
        sigma_V = V * rel_V
        sigma_L = self.length_rel_sigma * L
        sigma_h = 0.01 if layer_assumed else self.layer_sigma
        dw_dV = 1.0 / (L * h)
        dw_dL = -V / (L * L * h)
        dw_dh = -V / (L * h * h) + C_STADIUM
        sigma_w = math.sqrt((dw_dV * sigma_V) ** 2 + (dw_dL * sigma_L) ** 2
                            + (dw_dh * sigma_h) ** 2)
        return {
            "method": "error_propagation",
            "standard_deviation": round(sigma_w, 4),
            "confidence_interval_95": {
                "lower": round(rep_w - 1.96 * sigma_w, 4),
                "upper": round(rep_w + 1.96 * sigma_w, 4),
            },
        }


# ---------------------------------------------------------------------------
# 集計コンテナ
# ---------------------------------------------------------------------------
class WidthSamples:
    def __init__(self):
        # (feature, lh) -> [(width, weight, length, volume), ...]
        self.groups = defaultdict(list)
        self.count = 0

    def add(self, width, weight, feature, lh, length, volume):
        key = (feature, round(lh, 2))
        b = self.groups[key]
        if len(b) < MAX_SAMPLES_PER_KEY:
            b.append((width, weight, length, volume))
            self.count += 1


class ToolState:
    def __init__(self, filament_diameter=1.75):
        self.current_e = 0.0
        self.filament_diameter = filament_diameter
        self.filament_diameter_source = "default"
        self.flow_ratio = 1.0
        self.volumetric_mode = False


# ===========================================================================
# メインエンジン
# ===========================================================================
class NozzleEstimator:
    LAYER_HEIGHT_COMMENT = re.compile(r";\s*HEIGHT\s*:\s*([\d.]+)", re.I)
    LAYER_LINE_COMMENT = re.compile(r";\s*layer\s+-?\d+\s*,\s*Z\s*=\s*([\d.]+)", re.I)
    TYPE_COMMENT = re.compile(r";\s*(?:TYPE|FEATURE)\s*:\s*(.+)", re.I)
    FEATURE_WORD = re.compile(r";\s*feature\s+(.+)", re.I)
    MARKER_COMMENT = re.compile(r";Marker\s+([A-Za-z]+)\s+1\b")

    def __init__(self, nozzles=None, min_segment_len=0.5, max_dz=0.05,
                 default_filament=1.75, filament_uncertainty=0.02):
        self.nozzles = sorted(nozzles or DEFAULT_NOZZLES)
        self.min_segment_len = min_segment_len
        self.max_dz = max_dz
        self.default_filament = default_filament
        self.meta = Metadata()
        self.uncert = UncertaintyEstimator(filament_sigma=filament_uncertainty)
        # 状態
        self.x = self.y = self.z = 0.0
        self.abs_xyz = True
        self.abs_e = True
        self.active_tool = 0
        self.tools = defaultdict(lambda: ToolState(default_filament))
        self.runtime_flow = 1.0
        self.cur_feature = "unknown"
        self.height_comment = None
        self.last_ext_z = None
        self.derived_lh = None
        self._lh_source = "assumed"
        # 集計
        self.samples = defaultdict(WidthSamples)
        self.excluded = defaultdict(int)
        self.arc_unsupported = 0
        self.arc_handled = 0
        self.arachne_hint = False
        # 誤差要因検出フラグ (ErrorSourceDetector 用)
        self.pa = PressureAdvanceTracker()
        self.pressure_advance = False
        self.flow_change_count = 0
        self.eval_seg = 0
        self.short_seg = 0
        self._since_retract = 99
        self._since_tool = 99
        self.line_no = 0
        self.error_lines = []

    # ------------------------------------------------------------------
    def run(self, lines):
        for raw in lines:
            self.line_no += 1
            try:
                self._process(raw)
            except Exception as exc:  # noqa
                if len(self.error_lines) < 50:
                    self.error_lines.append((self.line_no, str(exc)))
        return self.build()

    def _process(self, raw):
        line = raw.strip().strip('"').strip()
        if not line:
            return
        if line.startswith(";"):
            self._comment(line)
            return
        code_part = line
        if ";" in line:
            code_part, after = line.split(";", 1)
            self._comment(";" + after)
        code_part = code_part.strip()
        if code_part:
            self._command(code_part)

    def _comment(self, line):
        self.meta.feed_comment(line[1:] if line.startswith(";") else line)
        m = self.LAYER_HEIGHT_COMMENT.search(line)
        if m:
            self.height_comment = float(m.group(1))
        if self.LAYER_LINE_COMMENT.search(line):
            self.height_comment = None
        m = self.TYPE_COMMENT.match(line) or self.FEATURE_WORD.match(line)
        if m:
            self.cur_feature = classify_feature(m.group(1)) or "unknown"
        else:
            mk = self.MARKER_COMMENT.search(line)
            if mk:
                f = classify_feature(mk.group(1))
                if f:
                    self.cur_feature = f
        if "arachne" in line.lower():
            self.arachne_hint = True
        pav = _pa_from_comment(line)
        if pav is not None:
            self.pa.apply_comment(self.active_tool, pav)
            self.pressure_advance = self.pa.any_active()

    def _command(self, cmd):
        head = cmd.split()[0].upper()
        if head in ("G0", "G1"):
            self._move(cmd)
        elif head in ("G2", "G3"):
            self._arc(cmd)
        elif head == "G90":
            self.abs_xyz = True
        elif head == "G91":
            self.abs_xyz = False
        elif head == "M82":
            self.abs_e = True
        elif head == "M83":
            self.abs_e = False
        elif head == "G92":
            self._g92(cmd)
        elif head == "M200":
            self._m200(cmd)
        elif head == "M221":
            ax = _axes(cmd)
            if "S" in ax and ax["S"] > 0:
                self.runtime_flow = ax["S"] / 100.0
                self.flow_change_count += 1
        elif head == "M900":                       # Marlin Linear Advance
            p = _letter_params(cmd, "TK")
            if "K" in p:
                tool = int(p["T"]) if "T" in p else self.active_tool
                self.pa.apply_command(tool, p["K"], "marlin", self.line_no)
                self.pressure_advance = self.pa.any_active()
        elif head == "SET_PRESSURE_ADVANCE":       # Klipper
            kw = _kw_params(cmd)
            val = _fnum(kw.get("ADVANCE"))
            if val is not None:
                t = _ext_to_tool(kw.get("EXTRUDER"))
                tool = t if t is not None else self.active_tool
                self.pa.apply_command(tool, val, "klipper", self.line_no,
                                      _fnum(kw.get("SMOOTH_TIME")))
                self.pressure_advance = self.pa.any_active()
        elif head == "M572":                       # RepRapFirmware
            p = _letter_params(cmd, "DS")
            if "S" in p:
                tool = int(p["D"]) if "D" in p else self.active_tool
                self.pa.apply_command(tool, p["S"], "reprap_firmware", self.line_no)
                self.pressure_advance = self.pa.any_active()
        elif head in ("SET_FLOW_PERCENTAGE", "SET_EXTRUDE_FACTOR", "M220"):
            self.flow_change_count += 1
        elif re.match(r"^T\d+$", head):
            self.active_tool = int(head[1:])
            self._since_tool = 0
        elif head == "ACTIVATE_EXTRUDER":
            m = re.search(r"(\d+)", cmd)
            if m:
                self.active_tool = int(m.group(1))
                self._since_tool = 0

    def _g92(self, cmd):
        ax = _axes(cmd)
        ts = self.tools[self.active_tool]
        if "E" in ax:
            ts.current_e = ax["E"]
        if "X" in ax:
            self.x = ax["X"]
        if "Y" in ax:
            self.y = ax["Y"]
        if "Z" in ax:
            self.z = ax["Z"]

    def _m200(self, cmd):
        ax = _axes(cmd)
        ts = self.tools[self.active_tool]
        if "D" in ax:
            if ax["D"] > 0:
                ts.volumetric_mode = True
                ts.filament_diameter = ax["D"]
            else:
                ts.volumetric_mode = False

    def _resolve_filament(self, tool):
        ts = self.tools[tool]
        if tool in self.meta.filament_diameter:
            ts.filament_diameter = self.meta.filament_diameter[tool]
            ts.filament_diameter_source = "metadata"
        return ts

    def _delta_e(self, ax, ts):
        if "E" not in ax:
            return 0.0
        if self.abs_e:
            d = ax["E"] - ts.current_e
            ts.current_e = ax["E"]
        else:
            d = ax["E"]
            ts.current_e += ax["E"]
        return d

    def _new_xy(self, ax):
        if self.abs_xyz:
            return ax.get("X", self.x), ax.get("Y", self.y), ax.get("Z", self.z)
        return (self.x + ax.get("X", 0.0), self.y + ax.get("Y", 0.0),
                self.z + ax.get("Z", 0.0))

    def _move(self, cmd):
        ax = _axes(cmd)
        ts = self._resolve_filament(self.active_tool)
        nx, ny, nz = self._new_xy(ax)
        de = self._delta_e(ax, ts)
        length = math.hypot(nx - self.x, ny - self.y)
        self._consume(ts, de, length, nz - self.z, nz)
        self.x, self.y, self.z = nx, ny, nz

    def _arc(self, cmd):
        ax = _axes(cmd)
        ts = self._resolve_filament(self.active_tool)
        nx, ny, nz = self._new_xy(ax)
        de = self._delta_e(ax, ts)
        length = _arc_length(cmd, self.x, self.y, nx, ny, ax)
        if length is None:
            self.arc_unsupported += 1
            self.x, self.y, self.z = nx, ny, nz
            return
        self.arc_handled += 1
        self._consume(ts, de, length, nz - self.z, nz)
        self.x, self.y, self.z = nx, ny, nz

    def _consume(self, ts, de, length, dz, nz):
        if de <= 0 or length <= 0:
            if de < 0 and length <= 1e-9:
                self._since_retract = 0      # リトラクト
            elif length <= 1e-9 and de > 0:
                pass                          # プライム(移動なし)
            return
        lh = self._layer_height(nz)
        if lh is None or lh <= 0:
            self.excluded[self.active_tool] += 1
            return
        if ts.volumetric_mode:
            volume = de
        else:
            area = PI * (ts.filament_diameter / 2.0) ** 2
            volume = area * de * self.runtime_flow

        self.eval_seg += 1
        if length < 2.0:
            self.short_seg += 1
        self._since_retract += 1
        self._since_tool += 1

        if (length < self.min_segment_len or abs(dz) > self.max_dz
                or self.cur_feature in EXCLUDED_FEATURES or volume <= 0):
            self.excluded[self.active_tool] += 1
            return
        w = line_width(volume, length, lh)
        if w is None or not (0.05 < w < 3.0) or math.isnan(w) or math.isinf(w):
            self.excluded[self.active_tool] += 1
            return
        weight = SegmentReliabilityScorer.score(
            self.cur_feature, length, self._since_retract, self._since_tool, self._lh_source)
        if weight <= 0:
            self.excluded[self.active_tool] += 1
            return
        self.samples[self.active_tool].add(w, weight, self.cur_feature, lh, length, volume)

    def _layer_height(self, z):
        if self.height_comment and self.height_comment > 0:
            self._lh_source = "comment"
            self._track_lh(self.height_comment)
            return self.height_comment
        if self.last_ext_z is None:
            self.last_ext_z = z
            self.derived_lh = (self.derived_lh or self.meta.first_layer_height
                               or self.meta.layer_height or (round(z, 3) if z > 0 else None))
            self._lh_source = "zdiff" if self.derived_lh else "assumed"
        elif z - self.last_ext_z > 0.01:
            d = round(z - self.last_ext_z, 3)
            if 0.01 < d < 2.0:
                self.derived_lh = d
                self._lh_source = "zdiff"
            self.last_ext_z = z
        lh = self.derived_lh or self.meta.layer_height
        if lh is None:
            lh = 0.2
            self._lh_source = "assumed"
        self._track_lh(lh)
        return lh

    def _track_lh(self, lh):
        if not hasattr(self, "_lh_min"):
            self._lh_min = self._lh_max = lh
        else:
            self._lh_min = min(self._lh_min, lh)
            self._lh_max = max(self._lh_max, lh)

    # ==================================================================
    def build(self):
        tools_out = {}
        for tool in sorted(set(list(self.samples.keys()) + [0])):
            if tool not in self.samples and tool != 0:
                continue
            tools_out[str(tool)] = self._build_tool(tool)
        if not tools_out:
            tools_out["0"] = self._build_tool(0)
        active = sorted(self.samples.keys()) or [0]
        best = tools_out.get(str(active[0])) or next(iter(tools_out.values()))
        return {
            "estimated_nozzle_diameter": best["estimated_nozzle_diameter"],
            "confidence_percent": best["confidence_percent"],
            "confidence_level": best["confidence_level"],
            "active_tools": [int(t) for t in tools_out.keys()],
            "tools": tools_out,
            "pressure_advance": self.pa.summary(active[0]),
            "arc_segments_unsupported": self.arc_unsupported,
            "disclaimer": "本結果は押出量からの理論ライン幅に基づく推定であり、"
                          "ノズル径や実測線幅を保証するものではない。",
        }

    def _build_tool(self, tool):
        ws = self.samples.get(tool, WidthSamples())
        ts = self.tools[tool]
        # 外れ値除去(グループごとに MAD, 重みも維持) §14
        filt = {}
        for key, samples in ws.groups.items():
            filt[key] = _mad_filter(samples)
        all_s = [s for lst in filt.values() for s in lst]
        feat_s = defaultdict(list)
        for (feat, _lh), lst in filt.items():
            feat_s[feat].extend(lst)

        widths = [s[0] for s in all_s]
        dist = LineWidthDistributionAnalyzer(all_s, feat_s)
        stats = dist.statistics()
        rep, rep_method = dist.representative()
        meta_nozzle = self.meta.nozzle_diameter.get(tool)
        if meta_nozzle is None and len(self.meta.nozzle_diameter) == 1:
            meta_nozzle = next(iter(self.meta.nozzle_diameter.values()))

        lh_min = getattr(self, "_lh_min", None)
        lh_max = getattr(self, "_lh_max", None)
        cv = (stats["standard_deviation"] / stats["mean"]) if (stats and stats["mean"]) else 0.0
        peaks = dist.peaks()
        variable = bool(self.arachne_hint or (cv > 0.20 and len(peaks) <= 2)
                        or (stats and stats["sample_count"] >= 50 and cv > 0.25))

        # 不確かさ (§4/§5)
        outer = feat_s.get("outer_wall", [])
        rep_L = statistics.median([s[2] for s in (outer or all_s)]) if (outer or all_s) else None
        rep_lh = _mode_hist([round(k[1], 2) for k in filt.keys() for _ in filt[k]]) or (lh_max or 0.2)
        layer_assumed = (self._lh_source == "assumed")
        uncertainty = None
        if rep and rep_L:
            uncertainty = self.uncert.propagate(rep, rep_L, rep_lh, ts.filament_diameter,
                                                layer_assumed)
        ci = uncertainty["confidence_interval_95"] if uncertainty else None

        # 候補スコアリング(区間重複 §10 を含む)
        candidates = []
        for d in self.nozzles:
            sc = self._score(d, rep, stats, widths, outer, lh_max, meta_nozzle, ci)
            candidates.append({"diameter": d, "score": round(sc, 4)})
        candidates.sort(key=lambda c: c["score"], reverse=True)
        top = candidates[:3]
        best = top[0] if top else {"diameter": None, "score": 0.0}
        second = top[1] if len(top) > 1 else {"diameter": None, "score": 0.0}

        high_conf = [s for s in all_s if s[1] >= 0.7]
        confidence = self._confidence(best, second, meta_nozzle, stats, outer, ts,
                                      lh_max, variable, cv, len(high_conf))
        errors = ErrorSourceDetector.detect(self, ts, stats, cv, variable, layer_assumed)
        grade = _quality_grade(stats, len(high_conf), len(outer),
                               ts.filament_diameter_source != "default",
                               self._lh_source, cv, variable, meta_nozzle,
                               self.flow_change_count)
        evidence, warnings = self._evidence(rep, stats, lh_max, best, meta_nozzle, ts,
                                            variable, peaks, ci, grade)

        return {
            "estimated_nozzle_diameter": best["diameter"],
            "confidence_percent": confidence,
            "confidence_level": _confidence_level(confidence),
            "quality_grade": grade,
            "metadata_nozzle_diameter": meta_nozzle,
            "filament_diameter": round(ts.filament_diameter, 3),
            "filament_diameter_source": ts.filament_diameter_source,
            "volumetric_extrusion": ts.volumetric_mode,
            "pressure_advance": self.pa.summary(tool),
            "theoretical_line_width": True,
            "representative_line_width": _r(rep, 3),
            "representative_method": rep_method,
            "line_width_uncertainty": uncertainty,
            "line_width_statistics": stats,
            "minimum_layer_height": _r(lh_min, 3),
            "maximum_layer_height": _r(lh_max, 3),
            "valid_segment_count": stats["sample_count"] if stats else 0,
            "high_confidence_sample_count": len(high_conf),
            "excluded_segment_count": self.excluded.get(tool, 0),
            "outer_wall_sample_count": len(outer),
            "variable_line_width_suspected": variable,
            "line_width_peaks": [round(p, 3) for p in peaks[:4]],
            "input_assumptions": {
                "filament_diameter": round(ts.filament_diameter, 3),
                "filament_diameter_source": ts.filament_diameter_source,
                "layer_height_source": self._lh_source,
                "runtime_flow_multiplier_detected": self.flow_change_count > 0,
                "pressure_advance_detected": self.pressure_advance,
                "volumetric_extrusion": ts.volumetric_mode,
            },
            "error_sources": errors,
            "candidate_nozzles": top,
            "evidence": evidence,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    def _score(self, d, rep, stats, widths, outer, lh_max, meta_nozzle, ci):
        lw = 0.0
        if rep and d > 0:
            r = rep / d
            lw = math.exp(-((r - 1.05) / 0.20) ** 2)
        lhs = 0.5
        if lh_max and d > 0:
            rh = lh_max / d
            if rh <= 0.8:
                lhs = 1.0
            elif rh <= 1.0:
                lhs = 1.0 - (rh - 0.8) / 0.2 * 0.5
            else:
                lhs = max(0.0, 0.3 - (rh - 1.0))
        dscore = 0.0
        if widths and d > 0:
            lo, hi = 0.7 * d, 1.6 * d
            dscore = sum(1 for w in widths if lo <= w <= hi) / len(widths)
        # 区間重複スコア (§10)
        overlap = 0.5
        if ci and d > 0:
            cand_lo, cand_hi = 0.85 * d, 1.30 * d
            est_lo, est_hi = ci["lower"], ci["upper"]
            inter = max(0.0, min(cand_hi, est_hi) - max(cand_lo, est_lo))
            span = max(1e-6, est_hi - est_lo)
            overlap = min(1.0, inter / span)
        meta = None
        if meta_nozzle is not None:
            meta = math.exp(-((meta_nozzle - d) / 0.05) ** 2)
        feat = 0.5
        if outer and d > 0:
            ro = statistics.median([s[0] for s in outer]) / d
            feat = 1.0 if 0.85 <= ro <= 1.35 else (0.6 if 0.7 <= ro <= 1.6 else 0.2)
        if meta is None:
            parts = [(lw, 0.40), (lhs, 0.18), (dscore, 0.13), (overlap, 0.12), (feat, 0.05)]
        else:
            parts = [(lw, 0.38), (lhs, 0.16), (dscore, 0.12), (overlap, 0.10),
                     (meta, 0.15), (feat, 0.04)]
        tot = sum(wt for _v, wt in parts)
        return sum(v * wt for v, wt in parts) / tot

    def _confidence(self, best, second, meta_nozzle, stats, outer, ts, lh_max,
                    variable, cv, high_conf_count):
        c = (best["score"] or 0.0) * 55.0
        if meta_nozzle is not None and best["diameter"] is not None \
                and abs(meta_nozzle - best["diameter"]) <= 0.01:
            c += 25
        n = stats["sample_count"] if stats else 0
        if n >= 1000:
            c += 10
        elif n >= 100:
            c += 5
        if len(outer) >= 100:
            c += 10
        if high_conf_count >= 100:
            c += 5
        if cv and cv < 0.10:
            c += 10
        diff = (best["score"] or 0) - (second["score"] or 0)
        if diff > 0.15:
            c += 10
        elif diff > 0.08:
            c += 5
        if ts.filament_diameter_source == "default":
            c -= 15
        if lh_max is None or self._lh_source == "assumed":
            c -= 20
        if n < 50:
            c -= 20
        if variable:
            c -= 10
        if cv and cv > 0.30:
            c -= 15
        if self.flow_change_count > 0:
            c -= 5
        return int(max(0, min(100, round(c))))

    def _evidence(self, rep, stats, lh_max, best, meta_nozzle, ts, variable, peaks, ci, grade):
        ev, wn = [], []
        if rep:
            ev.append(f"代表ライン幅(外周優先・重み付き)が約 {rep:.3f} mm")
        if ci:
            ev.append(f"95%推定範囲 {ci['lower']:.3f}〜{ci['upper']:.3f} mm")
        if peaks:
            ev.append("主要ライン幅ピーク: " + ", ".join(f"{p:.2f}" for p in peaks[:3]) + " mm")
        if lh_max:
            ev.append(f"最大レイヤー高さ {lh_max:.3f} mm")
        if best["diameter"] and rep:
            ev.append(f"{best['diameter']} mm ノズルに対するライン幅比 {rep / best['diameter']:.3f}")
        if stats:
            ev.append(f"有効押出線分 {stats['sample_count']} 件 / 解析品質グレード {grade}")
        if meta_nozzle is None:
            wn.append("G-code内にノズル径メタデータが存在しない")
        else:
            ev.append(f"メタデータ上のノズル径 {meta_nozzle} mm")
            if best["diameter"] and abs(meta_nozzle - best["diameter"]) > 0.05:
                wn.append(f"メタデータ({meta_nozzle}mm)と推定径({best['diameter']}mm)が矛盾 — "
                          "太線設定/流量変更/フィラメント径誤認/体積押出の解析ミスの可能性")
        if ts.filament_diameter_source == "default":
            wn.append("フィラメント径が取得できず既定値を仮定(信頼度低下)")
        if ts.volumetric_mode:
            wn.append("体積押出モード(M200)を検出 — E値を体積として解析")
        if self.pressure_advance:
            wn.append("Pressure/Linear Advance を検出 — 短線分の瞬間押出量がE値と異なる可能性")
        if self.flow_change_count:
            wn.append("実行時流量変更(M221等)を検出 — ライン幅に追加誤差の可能性")
        if variable:
            wn.append("可変線幅(Arachne等)の可能性 — 単一代表値ではなく範囲で解釈すること")
        wn.append("算出値はG-code上の理論ライン幅であり、造形物の実測線幅とは一致しない場合がある")
        return ev, wn


# ===========================================================================
# LineWidthDistributionAnalyzer (§7/§11)
# ===========================================================================
class LineWidthDistributionAnalyzer:
    def __init__(self, all_samples, feat_samples):
        self.all = all_samples           # [(w,weight,length,volume),...]
        self.feat = feat_samples

    def statistics(self):
        if not self.all:
            return None
        widths = [s[0] for s in self.all]
        weights = [s[1] for s in self.all]
        wmean = _weighted_mean(widths, weights)
        wmed = _weighted_median(widths, weights)
        return {
            "sample_count": len(widths),
            "min": round(min(widths), 4),
            "max": round(max(widths), 4),
            "mean": round(statistics.fmean(widths), 4),
            "weighted_mean": _r(wmean, 4),
            "median": round(statistics.median(widths), 4),
            "weighted_median": _r(wmed, 4),
            "mode": _r(_mode_hist(widths), 4),
            "standard_deviation": round(statistics.pstdev(widths) if len(widths) > 1 else 0.0, 4),
            "coefficient_of_variation": round(
                (statistics.pstdev(widths) / statistics.fmean(widths))
                if len(widths) > 1 and statistics.fmean(widths) else 0.0, 4),
            "percentile_10": _r(_percentile(widths, 10), 4),
            "percentile_25": _r(_percentile(widths, 25), 4),
            "percentile_75": _r(_percentile(widths, 75), 4),
            "percentile_90": _r(_percentile(widths, 90), 4),
        }

    def representative(self):
        # 高信頼外周の重み付き最頻値 > 重み付き中央値 > 通常押出ピーク > 全体中央値
        for feat in ("outer_wall", "inner_wall", "sparse_infill", "solid_infill"):
            lst = self.feat.get(feat)
            if lst and len(lst) >= 5:
                widths = [s[0] for s in lst]
                weights = [s[1] for s in lst]
                wm = _weighted_mode(widths, weights)
                if wm is not None:
                    method = ("weighted_external_perimeter_mode" if feat == "outer_wall"
                              else f"weighted_{feat}_mode")
                    return wm, method
        if self.all:
            widths = [s[0] for s in self.all]
            return (_mode_hist(widths) or statistics.median(widths)), "global_mode"
        return None, "none"

    def peaks(self):
        return _find_peaks([s[0] for s in self.all])


# ===========================================================================
# ErrorSourceDetector (§2/§8)
# ===========================================================================
class ErrorSourceDetector:
    @staticmethod
    def detect(engine, ts, stats, cv, variable, layer_assumed):
        out = []

        def add(t, sev, desc):
            out.append({"type": t, "severity": sev, "description": desc})

        if engine.pressure_advance:
            add("pressure_advance", "medium",
                "短い線分では実際の瞬間押出量がG-code上のE値と異なる可能性がある")
        if engine.flow_change_count:
            sev = "medium" if engine.flow_change_count > 3 else "low"
            add("runtime_flow_change", sev, "M221等の実行時流量変更を検出")
        if ts.filament_diameter_source == "default":
            add("filament_diameter", "low", "実測フィラメント径が不明(既定値を仮定)")
        if layer_assumed:
            add("layer_height", "high", "レイヤー高さを取得できず仮定値を使用")
        if engine.eval_seg and engine.short_seg / engine.eval_seg > 0.5:
            add("short_segments", "medium", "短い線分が全体の50%を超える")
        if variable:
            add("variable_line_width", "medium", "可変線幅(Arachne等)の可能性")
        if engine.arc_unsupported:
            add("arc_approximation", "low",
                f"円弧 {engine.arc_unsupported} 件を距離算出できず除外")
        if ts.volumetric_mode:
            add("volumetric_extrusion", "low", "体積押出モードでE値を体積として解析")
        return out


# ===========================================================================
# 数値ユーティリティ
# ===========================================================================
def _axes(cmd):
    out = {}
    for tok in cmd.split()[1:]:
        if not tok:
            continue
        a = tok[0].upper()
        if a in "XYZEFIJRSDK":
            try:
                out[a] = float(tok[1:])
            except ValueError:
                pass
    return out


def _arc_length(cmd, x0, y0, x1, y1, ax):
    cw = cmd.split()[0].upper() == "G2"
    if "I" in ax or "J" in ax:
        i, j = ax.get("I", 0.0), ax.get("J", 0.0)
        cx, cy = x0 + i, y0 + j
        r = math.hypot(i, j)
    elif "R" in ax:
        r = abs(ax["R"])
        cx, cy = _center_from_r(x0, y0, x1, y1, ax["R"], cw)
        if cx is None:
            return None
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


def _center_from_r(x0, y0, x1, y1, R, cw):
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    dx, dy = x1 - x0, y1 - y0
    q = math.hypot(dx, dy)
    if q < 1e-9 or abs(R) < q / 2.0:
        return None, None
    h = math.sqrt(max(0.0, R * R - (q / 2.0) ** 2))
    ux, uy = -dy / q, dx / q
    sign = 1.0 if (R > 0) ^ cw else -1.0
    return mx + sign * h * ux, my + sign * h * uy


def _mad_filter(samples):
    """samples: [(w,weight,length,volume)] を幅で MAD 外れ値除去。"""
    if len(samples) < 5:
        return [s for s in samples if 0.05 < s[0] < 3.0]
    widths = [s[0] for s in samples]
    med = statistics.median(widths)
    mad = statistics.median([abs(w - med) for w in widths])
    if mad <= 1e-9:
        q1, q3 = _percentile(widths, 25), _percentile(widths, 75)
        iqr = q3 - q1
        if iqr <= 1e-9:
            return samples
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        return [s for s in samples if lo <= s[0] <= hi]
    thr = 3.5 * 1.4826 * mad
    return [s for s in samples if abs(s[0] - med) <= thr]


def _percentile(data, p):
    if not data:
        return None
    s = sorted(data)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)


def _mode_hist(data, binw=0.01):
    if not data:
        return None
    buckets = defaultdict(int)
    for v in data:
        buckets[round(v / binw)] += 1
    return max(buckets.items(), key=lambda kv: kv[1])[0] * binw


def _weighted_mean(values, weights):
    sw = sum(weights)
    if sw <= 0:
        return statistics.fmean(values) if values else None
    return sum(v * w for v, w in zip(values, weights)) / sw


def _weighted_median(values, weights):
    pairs = sorted(zip(values, weights))
    sw = sum(weights)
    if sw <= 0:
        return statistics.median(values) if values else None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= sw / 2.0:
            return v
    return pairs[-1][0]


def _weighted_mode(values, weights, binw=0.01):
    if not values:
        return None
    buckets = defaultdict(float)
    for v, w in zip(values, weights):
        buckets[round(v / binw)] += w
    return max(buckets.items(), key=lambda kv: kv[1])[0] * binw


def _find_peaks(widths, binw=0.02, min_frac=0.08):
    if len(widths) < 10:
        return []
    buckets = defaultdict(int)
    for v in widths:
        buckets[round(v / binw)] += 1
    keys = sorted(buckets)
    total = len(widths)
    peaks = []
    for i, k in enumerate(keys):
        cnt = buckets[k]
        left = buckets[keys[i - 1]] if i > 0 else 0
        right = buckets[keys[i + 1]] if i < len(keys) - 1 else 0
        if cnt >= left and cnt >= right and cnt / total >= min_frac:
            peaks.append((k * binw, cnt))
    peaks.sort(key=lambda kv: kv[1], reverse=True)
    return [round(p, 3) for p, _ in peaks]


def _quality_grade(stats, high_conf, outer, fil_known, lh_source, cv, variable,
                   meta_present, flow_changes):
    if not stats or stats["sample_count"] == 0 or lh_source == "assumed" and not stats:
        return "E"
    n = stats["sample_count"]
    if (meta_present and fil_known and lh_source in ("comment", "zdiff")
            and outer >= 1000 and cv < 0.08 and flow_changes == 0):
        return "A"
    if fil_known and lh_source in ("comment", "zdiff") and outer >= 100 and cv < 0.15:
        return "B"
    if n < 50 or high_conf < 20 or variable or (cv and cv > 0.20) or flow_changes > 3:
        return "D"
    return "C"


def _confidence_level(c):
    if c >= 90:
        return "very_high"
    if c >= 75:
        return "high"
    if c >= 55:
        return "medium"
    if c >= 30:
        return "low"
    return "very_low"


def _r(v, nd):
    if v is None:
        return None
    try:
        return round(v, nd)
    except (TypeError, ValueError):
        return None


# ===========================================================================
# 公開 API
# ===========================================================================
def estimate(path, nozzles=None, default_filament=1.75, min_segment_len=0.5,
             filament_uncertainty=0.02):
    try:
        from .containers import open_gcode
    except ImportError:
        from containers import open_gcode
    src = open_gcode(path)
    est = NozzleEstimator(nozzles=nozzles, default_filament=default_filament,
                          min_segment_len=min_segment_len,
                          filament_uncertainty=filament_uncertainty)
    return est.run(src["lines"])


def estimate_lines(lines, **kw):
    return NozzleEstimator(**kw).run(lines)


_LEVEL_JA = {"very_high": "非常に高い", "high": "高い", "medium": "中程度",
             "low": "低い", "very_low": "非常に低い"}
_GRADE_JA = {"A": "高精度", "B": "実用上十分", "C": "参考値", "D": "不確実", "E": "算出不能"}


def format_human(result):
    out = []
    for tool, t in result["tools"].items():
        out.append(f"=== ツール T{tool} ===")
        d = t["estimated_nozzle_diameter"]
        out.append(f"推定ノズル径：{d} mm" if d else "推定ノズル径：不明")
        out.append(f"信頼度：{t['confidence_percent']} %（{_LEVEL_JA.get(t['confidence_level'],'')}）")
        out.append(f"解析品質：{t['quality_grade']}（{_GRADE_JA.get(t['quality_grade'],'')}）")
        rep = t["representative_line_width"]
        if rep:
            out.append(f"推定ライン幅：{rep} mm")
        ci = (t.get("line_width_uncertainty") or {}).get("confidence_interval_95")
        if ci:
            out.append(f"95 %推定範囲：{ci['lower']}〜{ci['upper']} mm")
        cand = t["candidate_nozzles"]
        if len(cand) > 1:
            out.append(f"第2候補：{cand[1]['diameter']} mm (スコア {cand[1]['score']})")
        pa = t.get("pressure_advance", {})
        if pa.get("detected"):
            st = "有効" if pa.get("enabled") else "明示的に無効(0)"
            out.append(f"Pressure Advance：{pa.get('value')}（{pa.get('firmware')} / "
                       f"{pa.get('source')} / {st}）")
        else:
            out.append("Pressure Advance：不明（G-code内に設定なし・補正未適用）")
        out.append("\n推定根拠：")
        out += [f"・{e}" for e in t["evidence"]]
        if t.get("error_sources"):
            out.append("\n主な誤差要因：")
            out += [f"・[{e['severity']}] {e['description']}" for e in t["error_sources"]]
        if t["warnings"]:
            out.append("\n警告：")
            out += [f"・{w}" for w in t["warnings"]]
        out.append("")
    return "\n".join(out).rstrip()
