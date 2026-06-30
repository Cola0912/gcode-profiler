# -*- coding: utf-8 -*-
"""
Comprehensive OrcaSlicer parameter recovery from sliced G-code.
===============================================================
Reuses the existing parser/state model (analyzer.GCodeAnalyzer), the nozzle
extrusion-width/PA estimator (nozzle_estimator), embedded-config metadata
(sources) and material inference (material). Does NOT duplicate parsing.

Every recovered parameter uses the envelope:
    {value, status, source, confidence, evidence, warnings}
  status : explicit | calculated | estimated | unknown
  source : command | metadata | geometry | statistics | not_found

Only observable values are recovered; missing evidence yields null/unknown.
User-facing strings are Japanese; identifiers/keys/comments are English.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

try:
    from .analyzer import GCodeAnalyzer
    from .containers import open_gcode
    from .sources import apply_embedded, apply_bambu_config
    from . import nozzle_estimator as nz
    from .material import estimate_material
except ImportError:
    from analyzer import GCodeAnalyzer
    from containers import open_gcode
    from sources import apply_embedded, apply_bambu_config
    import nozzle_estimator as nz
    from material import estimate_material

MODEL_FEATURES = ("outer_wall", "inner_wall", "sparse_infill", "solid_infill",
                  "top_surface", "bottom_surface")


# --------------------------------------------------------------------------
# Result envelope
# --------------------------------------------------------------------------
def field(value=None, status="unknown", source="not_found", confidence=0.0,
          evidence=None, warnings=None):
    return {"value": value, "status": status, "source": source,
            "confidence": round(confidence, 3),
            "evidence": evidence or [], "warnings": warnings or []}


def _wmedian(pairs):
    """Weighted median. pairs: [(value, weight)]."""
    pairs = sorted((v, w) for v, w in pairs if w > 0)
    tot = sum(w for _v, w in pairs)
    if tot <= 0:
        return None
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= tot / 2.0:
            return v
    return pairs[-1][0]


def _percentile(data, p):
    if not data:
        return None
    s = sorted(data)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    return s[int(k)] if f == c else s[f] * (c - k) + s[c] * (k - f)


def _mode(data, binw=0.01):
    if not data:
        return None
    b = defaultdict(int)
    for v in data:
        b[round(v / binw)] += 1
    return max(b.items(), key=lambda kv: kv[1])[0] * binw


# ==========================================================================
def recover(path, filament_diameter=1.75):
    src = open_gcode(path)
    an = GCodeAnalyzer(filament_diameter)
    an.analyze_lines(src["lines"])
    result = an.build_result()
    apply_embedded(result)
    if src.get("bambu_config"):
        apply_bambu_config(result, src["bambu_config"])
    nozzle = None
    try:
        nozzle = nz.estimate(path, default_filament=filament_diameter)
    except Exception:  # noqa
        nozzle = None

    cfg = an.config_kv
    rb = Recovery(an, result, nozzle, cfg)
    out = {
        "printer": rb.printer(),
        "material": rb.material(),
        "process": rb.process(),
    }
    out["summary_ja"] = rb.summary(out)
    return out


class Recovery:
    def __init__(self, an, result, nozzle, cfg):
        self.an = an
        self.result = result
        self.nozzle = nozzle or {}
        self.cfg = cfg or {}

    # -- helpers -----------------------------------------------------------
    def _feat_speed(self, feature):
        seg = self.an.seg_by_feature.get(feature, [])
        if not seg:
            return None, 0
        return _wmedian([(s, L) for s, L, _ in seg]), len(seg)

    def _feat_width(self, feature):
        w = self.an.stats.get(feature)
        return (statistics.median(w.widths) if (w and w.widths) else None)

    # ====================================================================
    # PRINTER
    # ====================================================================
    def printer(self):
        an, nzr = self.an, self.nozzle
        out = {}
        # firmware / flavor
        fw, fw_src, fw_ev = self._firmware()
        out["firmware"] = field(fw, "explicit" if fw_src == "command" else "estimated",
                                fw_src, 0.85 if fw_src == "command" else 0.4, fw_ev)
        out["gcode_flavor"] = field(self.result.get("machine", {}).get("gcode_flavor"),
                                    "estimated", "geometry", 0.5)
        out["absolute_xyz"] = field(not an.rel_xyz, "explicit", "command", 0.95,
                                    ["最終状態の座標モード(G90/G91)"])
        out["absolute_e"] = field(not an.rel_e, "explicit", "command", 0.95,
                                  ["最終状態の押出モード(M82/M83)"])
        out["volumetric_extrusion"] = field(
            any(t.get("volumetric_extrusion") for t in nzr.get("tools", {}).values()),
            "explicit" if nzr else "unknown", "command" if nzr else "not_found",
            0.9 if nzr else 0.0)
        tools = sorted(an.tools_used) or [0]
        out["used_tools"] = field(tools, "explicit", "command", 0.95)
        out["used_tool_count"] = field(len(tools), "explicit", "command", 0.95)

        # retraction (dominant per active tool overall)
        rl = _dom([r[0] for r in an.retractions]) if an.retractions else an.fw_retract_len
        rs = _dom([r[1] for r in an.retractions]) if an.retractions else an.fw_retract_speed
        ds = _dom([d[1] for d in an.deretractions]) if an.deretractions else None
        ev_r = [f"E反転 {len(an.retractions)} 回 / G10 {an.fw_retract_count} 回"]
        out["retraction_length"] = field(rl, "calculated" if rl else "unknown",
                                         "geometry" if rl else "not_found",
                                         0.8 if rl else 0.0, ev_r)
        out["retraction_speed"] = field(rs, "calculated" if rs else "unknown",
                                        "geometry" if rs else "not_found", 0.7 if rs else 0.0)
        out["deretraction_speed"] = field(ds, "calculated" if ds else "unknown",
                                          "geometry" if ds else "not_found", 0.6 if ds else 0.0)
        extra = self._extra_prime()
        out["extra_prime"] = field(extra, "calculated" if extra is not None else "unknown",
                                   "geometry" if extra is not None else "not_found",
                                   0.5 if extra is not None else 0.0)
        # z hop
        zh = _dom(an.zhops) if an.zhops else an.fw_zhop
        out["z_hop_height"] = field(zh, "calculated" if zh else "unknown",
                                    "geometry" if zh else "not_found", 0.7 if zh else 0.0,
                                    [f"リトラクト後のZ上昇/復帰 {len(an.zhops)} 回"] if an.zhops else [])
        out["z_hop_type"] = field("vertical" if zh else None,
                                  "estimated" if zh else "unknown",
                                  "geometry" if zh else "not_found", 0.4 if zh else 0.0,
                                  ["XY移動を伴わないZ上昇のため vertical と推定"] if zh else [])
        # motion limits
        out["motion_limits"] = self._motion_limits()
        out["default_acceleration"] = field(
            _dom(an.accels) if an.accels else None,
            "explicit" if an.accels else "unknown",
            "command" if an.accels else "not_found",
            0.8 if an.accels else 0.0, ["M204 P値の最頻値"] if an.accels else [])
        # pressure advance (reuse)
        out["pressure_advance"] = self._pa()
        # input shaper
        ish = an.input_shaper
        out["input_shaper"] = field(ish or None, "explicit" if ish else "unknown",
                                    "command" if ish else "not_found", 0.9 if ish else 0.0)
        # nozzle diameter (reuse estimate)
        nd = nzr.get("estimated_nozzle_diameter")
        out["nozzle_diameter"] = field(nd, "estimated" if nd else "unknown",
                                       "statistics" if nd else "not_found",
                                       (nzr.get("confidence_percent", 0) / 100.0) if nd else 0.0,
                                       ["ライン幅統計からの推定(別モジュール)"] if nd else [])
        # custom gcode sections
        gb = self.result.get("gcode_blocks", {})
        out["machine_start_gcode"] = field(gb.get("start_gcode") or None,
                                           "explicit" if gb.get("start_gcode") else "unknown",
                                           "geometry", 0.7 if gb.get("start_gcode") else 0.0,
                                           ["最初の押出より前の展開済みブロック"])
        out["machine_end_gcode"] = field(gb.get("end_gcode") or None,
                                         "explicit" if gb.get("end_gcode") else "unknown",
                                         "geometry", 0.7 if gb.get("end_gcode") else 0.0)
        out["change_filament_gcode"] = field(gb.get("toolchange_gcode") or None,
                                             "explicit" if gb.get("toolchange_gcode") else "unknown",
                                             "geometry", 0.6 if gb.get("toolchange_gcode") else 0.0)
        out["object_labels"] = field(sorted(an.object_labels) or None,
                                     "explicit" if an.object_labels else "unknown",
                                     "command" if an.object_labels else "not_found",
                                     0.9 if an.object_labels else 0.0)
        return out

    def _firmware(self):
        an = self.an
        ml = an.motion_limits
        pa_fw = (self.nozzle.get("pressure_advance") or {}).get("firmware")
        klipper = any(k in ml for k in ("accel", "square_corner_velocity", "max_velocity")) \
            or any("DAMPING" in str(k).upper() or k in ("shaper_type_x", "shaper_freq_x")
                   for k in an.input_shaper) or pa_fw == "klipper"
        marlin = any(k in ml for k in ("max_acceleration", "max_feedrate", "jerk")) \
            or pa_fw == "marlin" or "raw_m593" in an.input_shaper
        rrf = pa_fw == "reprap_firmware"
        if klipper and not (marlin or rrf):
            return "klipper", "command", ["Klipper固有命令(SET_VELOCITY_LIMIT/SET_PRESSURE_ADVANCE等)"]
        if rrf:
            return "reprap_firmware", "command", ["M566/M572 を検出"]
        if marlin:
            return "marlin", "command", ["Marlin固有命令(M201/M203/M204/M205/M900等)"]
        if an._marker_style_seen:
            return "industrial_custom", "geometry", ["産業機の独自マーカー形式"]
        return None, "not_found", []

    def _extra_prime(self):
        an = self.an
        if not an.retractions or not an.deretractions:
            return None
        rl = _dom([r[0] for r in an.retractions])
        pl = _dom([d[0] for d in an.deretractions])
        if rl is None or pl is None:
            return None
        return round(pl - rl, 3)

    def _motion_limits(self):
        ml = self.an.motion_limits
        if not ml:
            return field(None, "unknown", "not_found", 0.0,
                         warnings=["運動制限命令(M201/203/205/566/SET_VELOCITY_LIMIT)が出力されていない"])
        return field(ml, "explicit", "command", 0.9, ["明示的に出力された運動制御コマンド"])

    def _pa(self):
        pa = self.nozzle.get("pressure_advance")
        if not pa:
            return field(None, "unknown", "not_found", 0.0,
                         warnings=["PA設定命令・メタデータなし。0とは断定しない"])
        if not pa.get("detected"):
            return field(None, "unknown", "not_found", 0.0,
                         warnings=["PA設定なし。ライン幅へは未適用"])
        st = "explicit"
        return field(pa.get("value"), st,
                     "command" if pa.get("source") == "gcode_command" else "metadata",
                     pa.get("confidence_percent", 0) / 100.0,
                     [f"{pa.get('firmware')} / {pa.get('source')} / "
                      + ("有効" if pa.get("enabled") else "明示的に無効(0)")])

    # ====================================================================
    # MATERIAL (per tool)
    # ====================================================================
    def material(self):
        an = self.an
        chamber = _dom(an.chamber_temps) if an.chamber_temps else None
        # filament diameter
        fd, fd_src, fd_conf, fd_warn = self._filament_diameter()
        out = {
            "filament_diameter": field(fd, "explicit" if fd_src != "assumed" else "estimated",
                                       fd_src if fd_src != "assumed" else "not_found",
                                       fd_conf, warnings=fd_warn),
            "chamber_temperature": field(chamber, "explicit" if chamber else "unknown",
                                         "command" if chamber else "not_found",
                                         0.9 if chamber else 0.0),
            "per_tool": {},
        }
        # volumetric flow (observed demand)
        flows = [vf for f in MODEL_FEATURES for (_s, _L, vf) in an.seg_by_feature.get(f, [])]
        if flows:
            out["observed_volumetric_flow"] = field(
                {"average": round(statistics.fmean(flows), 2),
                 "max_p99": round(_percentile(flows, 99), 2),
                 "max_p999": round(_percentile(flows, 99.9), 2)},
                "calculated", "statistics", 0.7,
                ["各押出区間 volume*speed/length の集計(観測需要であり設定上限ではない)"])
        else:
            out["observed_volumetric_flow"] = field(None, "unknown", "not_found", 0.0)
        # runtime flow override
        rf = self.cfg.get("flow_ratio") or self.cfg.get("filament_flow_ratio")
        out["flow_ratio_metadata"] = field(_num(rf), "explicit" if rf else "unknown",
                                           "metadata" if rf else "not_found",
                                           0.9 if rf else 0.0,
                                           warnings=["スライサFlow RatioはE値に反映済み。再乗算しない"])
        # per-tool temperatures / fan / material
        tools = sorted(an.tools_used) or [0]
        fan_n, fan_max, fan_init = self._fan()
        for t in tools:
            temps = an.temps_by_tool.get(t, []) or an.temps
            beds = an.bed_by_tool.get(t, []) or an.bed_temps
            normal_t = _dom(temps) if temps else None
            init_t = an.initial_temps.get(t, (temps[0] if temps else None))
            normal_b = _dom(beds) if beds else None
            mat = estimate_material(normal_t, normal_b, chamber)
            self_tool = {
                "normal_nozzle_temperature": field(
                    normal_t, "explicit" if normal_t else "unknown",
                    "command" if normal_t else "not_found", 0.85 if normal_t else 0.0,
                    ["モデル区間で支配的な M104/M109 値"] if normal_t else []),
                "initial_layer_nozzle_temperature": field(
                    init_t, "explicit" if init_t else "unknown",
                    "command" if init_t else "not_found", 0.6 if init_t else 0.0,
                    ["最初に設定されたノズル温度"] if init_t else []),
                "normal_bed_temperature": field(
                    normal_b, "explicit" if normal_b else "unknown",
                    "command" if normal_b else "not_found", 0.85 if normal_b else 0.0),
                "initial_layer_bed_temperature": field(
                    (an.initial_bed if t == 0 else None),
                    "explicit" if (t == 0 and an.initial_bed) else "unknown",
                    "command" if (t == 0 and an.initial_bed) else "not_found",
                    0.6 if (t == 0 and an.initial_bed) else 0.0),
                "material_type": field(
                    mat["material"], "estimated" if mat["material"] else "unknown",
                    "statistics" if mat["material"] else "not_found",
                    mat["confidence"] / 100.0,
                    [mat["reason"]] if mat["material"] else [],
                    ["温度からの推定であり断定ではない"]),
                "fan_normal_speed_pct": field(fan_n, "calculated" if fan_n is not None else "unknown",
                                              "command" if fan_n is not None else "not_found",
                                              0.7 if fan_n is not None else 0.0,
                                              ["M106 を 255 スケールで%換算・時間相当で集計"]),
                "fan_max_speed_pct": field(fan_max, "calculated" if fan_max is not None else "unknown",
                                           "command" if fan_max is not None else "not_found",
                                           0.7 if fan_max is not None else 0.0),
            }
            out["per_tool"][str(t)] = self_tool
        return out

    def _filament_diameter(self):
        an = self.an
        if an.config_kv.get("filament_diameter"):
            return _num(an.config_kv["filament_diameter"]), "metadata", 0.95, []
        # M200 D from nozzle estimator tool state
        for t in (self.nozzle.get("tools") or {}).values():
            if t.get("filament_diameter_source") == "metadata":
                return t.get("filament_diameter"), "metadata", 0.9, []
        return an.filament_diameter, "assumed", 0.3, ["フィラメント径不明のため仮定値を使用"]

    def _fan(self):
        an = self.an
        nonzero = [v for v in an.fan_values if v > 0]
        if not an.fan_values:
            return None, None, None
        to_pct = lambda v: round(v / 255.0 * 100) if v > 1.0 else round(v * 100)
        normal = to_pct(_mode(nonzero)) if nonzero else 0
        mx = to_pct(max(an.fan_values))
        first_layer = an.fan_by_layer.get(an._first_print_layer(), [])
        init = to_pct(_mode(first_layer)) if first_layer else None
        return normal, mx, init

    # ====================================================================
    # PROCESS
    # ====================================================================
    def process(self):
        an, res = self.an, self.result
        out = {}
        q = res.get("quality", {})
        out["layer_height"] = field(q.get("layer_height"),
                                    "calculated" if q.get("layer_height") else "unknown",
                                    "geometry" if q.get("layer_height") else "not_found",
                                    0.85 if q.get("layer_height") else 0.0,
                                    ["モデルレイヤZ差の最頻値 / HEIGHTコメント"])
        out["initial_layer_height"] = field(q.get("first_layer_height"),
                                            "calculated" if q.get("first_layer_height") else "unknown",
                                            "geometry" if q.get("first_layer_height") else "not_found",
                                            0.7 if q.get("first_layer_height") else 0.0)
        heights = an._layer_heights()
        variable = bool(heights and (max(heights) - min(heights) > 0.02))
        out["variable_layer_height"] = field(variable, "estimated", "geometry", 0.5,
                                             ["層厚の分散から推定"])
        # line widths per feature
        widths = {}
        for f, key in [("outer_wall", "outer_wall_line_width"),
                       ("inner_wall", "inner_wall_line_width"),
                       ("sparse_infill", "sparse_infill_line_width"),
                       ("solid_infill", "internal_solid_infill_line_width"),
                       ("top_surface", "top_surface_line_width"),
                       ("support", "support_line_width")]:
            w = self._feat_width(f)
            widths[key] = field(round(w, 3) if w else None,
                                "calculated" if w else "unknown",
                                "geometry" if w else "not_found", 0.75 if w else 0.0)
        out["line_width"] = widths
        # default line width if all share dominant
        ow = self._feat_width("outer_wall"); iw = self._feat_width("inner_wall")
        if ow and iw and abs(ow - iw) < 0.02:
            out["default_line_width"] = field(round((ow + iw) / 2, 3), "calculated",
                                              "geometry", 0.6, ["主要フィーチャ幅が一致"])
        else:
            out["default_line_width"] = field(None, "unknown", "not_found", 0.0,
                                              warnings=["フィーチャ毎に幅が異なる/情報不足"])
        # walls
        wl = res.get("strength", {}).get("wall_loops")
        out["wall_loops"] = field(wl, "estimated" if wl else "unknown",
                                  "geometry" if wl else "not_found", 0.5 if wl else 0.0,
                                  ["島ごとのネスト壁数の支配値(概算)"])
        out["wall_order"] = self._wall_order()
        # infill
        dens = res.get("strength", {}).get("sparse_infill_density_pct")
        out["sparse_infill_density"] = field(f"{int(dens)}%" if dens is not None else None,
                                             "calculated" if dens is not None else "unknown",
                                             "geometry" if dens is not None else "not_found",
                                             0.5 if dens is not None else 0.0,
                                             ["平行線の法線間隔 ≈ ライン幅/間隔"])
        out["sparse_infill_direction"] = self._infill_direction()
        out["sparse_infill_pattern"] = field(None, "unknown", "not_found", 0.0,
                                             warnings=["パターン分類は未実装(方向のみ観測)"])
        # speeds per feature (distance-weighted)
        out["speeds"] = self._speeds()
        # acceleration per feature
        out["accelerations"] = self._accels()
        # presence flags
        feats = res.get("meta", {}).get("features_seen", {})
        out["support"] = self._support(feats)
        out["raft"] = field(res.get("strength", {}).get("has_raft"),
                            "calculated", "geometry", 0.8,
                            ["負レイヤ/Raftフィーチャの有無"])
        out["skirt_or_brim"] = field(
            bool(feats.get("skirt") or feats.get("brim")),
            "calculated" if (feats.get("skirt") or feats.get("brim")) else "unknown",
            "geometry", 0.5)
        out["spiral_vase"] = self._spiral(feats)
        out["arc_fitting"] = field(
            {"present": an.arc_count > 0, "arc_count": an.arc_count,
             "radius_p50": round(_percentile(an.arc_radii, 50), 3) if an.arc_radii else None}
            if an.arc_count else None,
            "explicit" if an.arc_count else "unknown",
            "command" if an.arc_count else "not_found", 0.9 if an.arc_count else 0.0)
        out["multimaterial"] = self._mmu()
        return out

    def _wall_order(self):
        # outer/inner どちらが先に現れるかを区間順から推定するのは現状データで困難
        return field(None, "unknown", "not_found", 0.0,
                     warnings=["壁実行順は区間順の保持が必要。現状未観測"])

    def _infill_direction(self):
        lines = self.an.infill_lines
        if not lines:
            return field(None, "unknown", "not_found", 0.0)
        angs = [round(math.degrees(a)) % 180 for a, _p in lines]
        dom = _mode([float(a) for a in angs], binw=5)
        return field(round(dom) if dom is not None else None, "calculated", "geometry", 0.5,
                     ["押出線の角度 atan2 を mod180 で集計した支配方向(°)"])

    def _speeds(self):
        out = {}
        for f, key in [("outer_wall", "outer_wall"), ("inner_wall", "inner_wall"),
                       ("sparse_infill", "sparse_infill"), ("solid_infill", "internal_solid_infill"),
                       ("top_surface", "top_surface"), ("support", "support"),
                       ("bottom_surface", "bottom_surface")]:
            sp, n = self._feat_speed(f)
            out[key] = field(round(sp, 1) if sp else None,
                             "calculated" if sp else "unknown",
                             "geometry" if sp else "not_found", 0.75 if sp else 0.0,
                             [f"{f} 区間F値の距離加重中央値(n={n})"] if sp else [],
                             ["指令速度であり到達速度ではない"] if sp else [])
        tv = _wmedian([(s, 1) for s in self.an.travel_speeds]) if self.an.travel_speeds else None
        out["travel"] = field(round(tv, 1) if tv else None,
                              "calculated" if tv else "unknown",
                              "geometry" if tv else "not_found", 0.7 if tv else 0.0)
        fls = self.an.first_layer_speeds
        out["initial_layer"] = field(round(statistics.median(fls), 1) if fls else None,
                                     "calculated" if fls else "unknown",
                                     "geometry" if fls else "not_found", 0.6 if fls else 0.0)
        return out

    def _accels(self):
        out = {}
        for f in ("outer_wall", "inner_wall", "sparse_infill", "solid_infill", "top_surface"):
            vals = self.an.accel_by_feature.get(f, [])
            a = _dom(vals) if vals else None
            out[f] = field(a, "explicit" if a else "unknown",
                           "command" if a else "not_found", 0.6 if a else 0.0,
                           ["フィーチャ区間で有効だった M204 値の最頻値"] if a else [])
        return out

    def _support(self, feats):
        has = self.result.get("strength", {}).get("has_support")
        if has:
            stype = "unknown"
            return field({"present": True, "geometry_type": stype,
                          "interface_present": bool(feats.get("support_interface"))},
                         "calculated", "geometry", 0.8,
                         ["Support系フィーチャを検出"],
                         ["木/オーガニック等の種別は未分類"])
        return field({"present": False}, "unknown", "not_found", 0.0,
                     warnings=["サポート経路なし。対象モデルが不要だった可能性があり無効とは断定しない"])

    def _spiral(self, feats):
        outer = feats.get("outer_wall", 0)
        infill = feats.get("sparse_infill", 0) + feats.get("solid_infill", 0)
        top = feats.get("top_surface", 0)
        inner = feats.get("inner_wall", 0)
        likely = outer > 0 and infill == 0 and top == 0 and inner == 0
        return field(likely, "estimated", "geometry", 0.5 if likely else 0.2,
                     ["単一壁・インフィル/上面なしの構造から推定"] if likely else [],
                     ["連続Z上昇の厳密判定は未実装"])

    def _mmu(self):
        an = self.an
        n = len(an.tool_changes)
        if not an.tools_used or len(an.tools_used) <= 1:
            return field({"tool_change_count": n, "multi": False}, "calculated",
                         "command", 0.7, ["単一ツール"])
        return field({"tool_change_count": n, "tool_sequence": an.tool_changes[:50],
                      "tools": sorted(an.tools_used),
                      "wipe_tower_present": None},
                     "calculated", "command", 0.7,
                     [f"工具交換 {n} 回 / ツール {sorted(an.tools_used)}"],
                     ["パージ量/ワイプタワー位置は本実装では未集計"])

    # ====================================================================
    def summary(self, out):
        s = []
        pr, ma, pc = out["printer"], out["material"], out["process"]
        if pr["firmware"]["value"]:
            s.append(f"ファームウェアは {pr['firmware']['value']} と推定（{pr['firmware']['source']}）。")
        nd = pr["nozzle_diameter"]
        if nd["value"]:
            s.append(f"ノズル径は {nd['value']} mm（信頼度 {int(nd['confidence']*100)}%、ライン幅統計）。")
        lh = pc["layer_height"]
        if lh["value"]:
            s.append(f"積層ピッチは {lh['value']} mm と算出（{lh['source']}）。")
        ows = pc["speeds"]["outer_wall"]
        if ows["value"]:
            s.append(f"外壁速度は {ows['value']} mm/s（F値の距離加重中央値）。")
        t0 = ma["per_tool"].get("0", {})
        if t0.get("material_type", {}).get("value"):
            mt = t0["material_type"]
            s.append(f"素材は {mt['value']} の可能性（信頼度 {int(mt['confidence']*100)}%、温度推定）。")
        sup = pc["support"]
        if sup["value"] and sup["value"].get("present"):
            s.append("サポートは有効（Support経路を検出）。")
        else:
            s.append("サポート有効化は不明（経路なし。モデルが不要だった可能性）。")
        pa = pr["pressure_advance"]
        if pa["value"] is not None:
            s.append(f"Pressure Advance は {pa['value']}（{pa['source']}）。")
        else:
            s.append("Pressure Advance は不明（設定なし。0とは断定しない）。")
        return s


def _dom(values):
    """Dominant (rounded mode) of numeric values."""
    if not values:
        return None
    b = defaultdict(int)
    for v in values:
        b[round(v, 2)] += 1
    return max(b.items(), key=lambda kv: kv[1])[0]


def _num(s):
    if s is None:
        return None
    try:
        return float(str(s).split(",")[0].strip().rstrip("%"))
    except (ValueError, TypeError):
        return None


# CLI: python -m gcode_profiler.recovery <file> [--json]
if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m gcode_profiler.recovery <gcode|3mf> [--json]")
        sys.exit(1)
    res = recover(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("=== 復元サマリ ===")
        for line in res["summary_ja"]:
            print("・" + line)
