# -*- coding: utf-8 -*-
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze

base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_gcode")
for f in ["豆腐.gcode", "CPEEK豆腐.gcode"]:
    p = os.path.join(base, f)
    r = analyze(p)
    print("==== ", f, "====")
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
