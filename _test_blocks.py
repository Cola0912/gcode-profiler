# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze

cases = [
    ("sample_gcode", "豆腐.gcode"),
    ("sample_synth", "prusa_synth.gcode"),
    ("sample_synth", "klipper_synth.gcode"),
]
root = os.path.dirname(os.path.abspath(__file__))
for folder, f in cases:
    r = analyze(os.path.join(root, folder, f))
    print(f"\n==================== {f} ====================")
    print("source:", r["meta"]["source"], "| tools:", r["meta"]["tools_used"],
          "| tool_count:", r["meta"]["tool_count"])
    print("--- filaments ---")
    for fl in r["filaments"]:
        print("   ", fl)
    b = r["gcode_blocks"]
    print("--- start_gcode (先頭5行) ---")
    print("\n".join(b["start_gcode"].splitlines()[:5]) or "(なし)")
    print("--- end_gcode (末尾5行) ---")
    print("\n".join(b["end_gcode"].splitlines()[-5:]) or "(なし)")
    print("--- toolchange_gcode ---")
    print(b["toolchange_gcode"] or "(なし)")
