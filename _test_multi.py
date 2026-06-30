# -*- coding: utf-8 -*-
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_synth")
for f in ["prusa_synth.gcode", "cura_synth.gcode", "klipper_synth.gcode"]:
    r = analyze(os.path.join(base, f))
    print(f"\n==================== {f} ====================")
    print("source :", r["meta"].get("source"), "| method:", r["meta"].get("method"))
    print("style  :", r["meta"].get("feature_style"))
    print("features:", r["meta"].get("features_seen"))
    for sec in ["quality", "speed", "strength", "temperature", "retraction"]:
        print(f" [{sec}]")
        for k, v in r[sec].items():
            if isinstance(v, float):
                v = round(v, 3)
            print(f"    {k:28} = {v}")
