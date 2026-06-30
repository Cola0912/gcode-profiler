# -*- coding: utf-8 -*-
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze
from gcode_profiler import orca_mapping as om

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_gcode")
p = os.path.join(base, "CPEEK豆腐.gcode")
r = analyze(p)
print("=== 画面表示プレビュー ===")
for cat, rows in om.rows_for_display(r):
    print(f"\n[{cat}]")
    for row in rows:
        conf = " (推定)" if row["low_conf"] else ""
        print(f"  {row['label']:<16} {row['value']:>8} {row['unit']:<5} -> {row['orca_key']}{conf}")

print("\n=== Orca プロセス JSON ===")
bundle = om.build_export(r, "CPEEK_Recovered")
print(json.dumps(bundle["process"], ensure_ascii=False, indent=4))
print("\n=== filament JSON ===")
print(json.dumps(bundle["filament"], ensure_ascii=False, indent=4))
print("\n=== printer JSON ===")
print(json.dumps(bundle["printer"], ensure_ascii=False, indent=4))
