# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze
from gcode_profiler import exporters

root = os.path.dirname(os.path.abspath(__file__))
r = analyze(os.path.join(root, "sample_synth", "mmu_synth.gcode"))
print("tools:", r["meta"]["tools_used"])
for target in exporters.TARGETS:
    print("\n" + "="*70)
    print("TARGET:", target)
    for fname, content in exporters.export(r, "MMU_Recovered", target):
        print(f"--- {fname} ---")
        print(content[:700])
