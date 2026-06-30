# -*- coding: utf-8 -*-
"""ノズル径推定器の単体テスト(仕様 §28 の主要ケース)。"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.nozzle_estimator import estimate_lines, format_human

PI = math.pi


def de_for(L, h, w, d_fil=1.75, flow=1.0, volumetric=False):
    """目標 rectangular effective 幅 w になる押出量 E を計算 (V = w*h*L)。"""
    V = L * h * w
    if volumetric:
        return V / flow
    area = PI * (d_fil / 2) ** 2
    return V / (area * flow)


def square_layer(z, h, w, d_fil, half=20, rel_e=False, e_state=None,
                 feature="External perimeter", volumetric=False, flow=1.0):
    lines = [f";HEIGHT:{h}", f"G1 Z{z} F9000", f";TYPE:{feature}", "G1 F1800"]
    pts = [(-half, -half), (half, -half), (half, half), (-half, half), (-half, -half)]
    cx, cy = 100, 100
    lines.append(f"G1 X{cx+pts[0][0]} Y{cy+pts[0][1]}")
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0)
        de = de_for(L, h, w, d_fil, flow, volumetric)
        if rel_e:
            lines.append(f"G1 X{cx+x1} Y{cy+y1} E{de:.5f}")
        else:
            e_state[0] += de
            lines.append(f"G1 X{cx+x1} Y{cy+y1} E{e_state[0]:.5f}")
    return lines


def build(nozzle_meta=None, fil=1.75, h=0.2, w=0.42, rel_e=False, layers=40,
          volumetric=False, flow=1.0, header=None):
    L = list(header or [])
    if nozzle_meta is not None:
        L.append(f"; nozzle_diameter = {nozzle_meta}")
    L.append(f"; filament_diameter = {fil}")
    L += ["G21", "G90", ("M83" if rel_e else "M82"), "G92 E0"]
    if volumetric:
        L.append(f"M200 D{fil}")
    if flow != 1.0:
        L.append(f"M221 S{int(flow*100)}")
    e = [0.0]
    for i in range(layers):
        z = round(h * (i + 1), 3)
        L += square_layer(z, h, w, fil, rel_e=rel_e, e_state=e,
                          volumetric=volumetric, flow=flow)
        if not rel_e:
            L += ["G1 E{:.5f} F2100".format(e[0] - 0.8), "G1 E{:.5f} F1500".format(e[0])]
        else:
            L += ["G1 E-0.8 F2100", "G1 E0.8 F1500"]
    return L


def check(name, lines, expect_d, fil=1.75, tool="0"):
    r = estimate_lines(lines, default_filament=fil)
    t = r["tools"][tool]
    got = t["estimated_nozzle_diameter"]
    ok = (got == expect_d)
    print(f"[{'OK ' if ok else 'NG '}] {name}: 推定={got} 期待={expect_d} "
          f"信頼度={t['confidence_percent']}% rep={t['representative_line_width']} "
          f"samples={t['valid_segment_count']}")
    return ok


passed = 0; total = 0


def T(name, lines, exp, **kw):
    global passed, total
    total += 1
    if check(name, lines, exp, **kw):
        passed += 1


# 1. 0.4 / 0.2 / 0.42 (絶対E + G92)
T("1 0.4mm/0.2/0.42 absE", build(h=0.2, w=0.42), 0.4)
# 2. 0.6 / 0.3 / 0.65
T("2 0.6mm/0.3/0.65", build(h=0.3, w=0.65), 0.6)
# 3-4. 相対E
T("3 relativeE M83", build(h=0.2, w=0.42, rel_e=True), 0.4)
# 6-7. 2.85 フィラメント
T("4 2.85 filament", build(fil=2.85, h=0.2, w=0.42), 0.4, fil=2.85)
# 8. 体積押出 M200
T("5 volumetric M200", build(h=0.2, w=0.42, volumetric=True), 0.4)
# 9. 流量変更 M221 S95
T("6 flow M221 S95", build(h=0.2, w=0.42, flow=0.95), 0.4)
# 16. メタデータあり
T("7 metadata nozzle 0.4", build(nozzle_meta=0.4, h=0.2, w=0.42), 0.4)
# 17. メタデータなし(既出 case1 が該当) — 信頼度が低めになることを確認
r = estimate_lines(build(h=0.2, w=0.42))
print("   meta無し信頼度:", r["tools"]["0"]["confidence_percent"], "%")

# 15. マルチツール (T0=0.4, T1=0.6)
ml = ["; nozzle_diameter = 0.4,0.6", "; filament_diameter = 1.75,1.75",
      "G21", "G90", "M82", "G92 E0", "T0"]
e = [0.0]
for i in range(20):
    ml += square_layer(round(0.2*(i+1), 3), 0.2, 0.42, 1.75, e_state=e)
ml += ["T1", "G92 E0"]
e2 = [0.0]
for i in range(20):
    ml += square_layer(round(0.3*(i+1), 3), 0.3, 0.65, 1.75, e_state=e2)
rm = estimate_lines(ml)
print(f"[multi] active_tools={rm['active_tools']} "
      f"T0={rm['tools']['0']['estimated_nozzle_diameter']} "
      f"T1={rm['tools']['1']['estimated_nozzle_diameter']}")
total += 1
if rm['tools']['0']['estimated_nozzle_diameter'] == 0.4 and \
   rm['tools']['1']['estimated_nozzle_diameter'] == 0.6:
    passed += 1; print("[OK ] multi-tool")
else:
    print("[NG ] multi-tool")

# 18. メタと押出が矛盾 (メタ0.4 だが実幅0.8)
rc = estimate_lines(build(nozzle_meta=0.4, h=0.2, w=0.80))
print("   矛盾ケース 推定:", rc["tools"]["0"]["estimated_nozzle_diameter"],
      "警告:", [w for w in rc["tools"]["0"]["warnings"] if "矛盾" in w])

print(f"\n===== {passed}/{total} PASS =====")
print("\n--- 人間可読サンプル(ケース1) ---")
print(format_human(estimate_lines(build(h=0.2, w=0.42, nozzle_meta=0.4))))
