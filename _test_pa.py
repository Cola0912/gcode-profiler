# -*- coding: utf-8 -*-
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.nozzle_estimator import estimate_lines

PI = math.pi
def de(L, h, w, d=1.75):
    return (L*h*(w-h*(1-PI/4))) / (PI*(d/2)**2)

def body():
    L = ["; filament_diameter = 1.75", "G21", "G90", "M82", "G92 E0"]
    e = [0.0]
    for i in range(10):
        z = round(0.2*(i+1), 3)
        L += [f";HEIGHT:0.2", f"G1 Z{z} F9000", ";TYPE:External perimeter", "G1 F1800"]
        L.append("G1 X100 Y100")
        for (a, b) in [(120, 100), (120, 120), (100, 120), (100, 100)]:
            e[0] += de(20, 0.2, 0.42)
            L.append(f"G1 X{a} Y{b} E{e[0]:.5f}")
    return L

def show(name, head):
    r = estimate_lines(head + body())
    pa = r["pressure_advance"]
    print(f"{name}: detected={pa['detected']} enabled={pa['enabled']} value={pa['value']} "
          f"fw={pa['firmware']} src={pa['source']} conf={pa['confidence_percent']}%")
    return pa

show("Klipper SET_PRESSURE_ADVANCE", ["SET_PRESSURE_ADVANCE ADVANCE=0.040 SMOOTH_TIME=0.04"])
show("Marlin M900 K", ["M900 K0.05"])
show("RRF M572", ["M572 D0 S0.04"])
show("comment metadata", ["; pressure_advance = 0.035"])
show("explicit zero (Klipper)", ["SET_PRESSURE_ADVANCE ADVANCE=0"])
show("explicit zero (Marlin)", ["M900 K0"])
show("not found", [])

# ツール別 PA
ml = ["; filament_diameter = 1.75,1.75", "G21", "G90", "M82", "G92 E0",
      "T0", "SET_PRESSURE_ADVANCE ADVANCE=0.035"]
e = [0.0]
for i in range(8):
    ml += [";HEIGHT:0.2", f"G1 Z{round(0.2*(i+1),3)} F9000", ";TYPE:External perimeter", "G1 F1800", "G1 X100 Y100"]
    for (a, b) in [(120, 100), (120, 120), (100, 120), (100, 100)]:
        e[0] += de(20, 0.2, 0.42); ml.append(f"G1 X{a} Y{b} E{e[0]:.5f}")
ml += ["T1", "G92 E0", "SET_PRESSURE_ADVANCE EXTRUDER=extruder1 ADVANCE=0.060"]
e2 = [0.0]
for i in range(8):
    ml += [";HEIGHT:0.3", f"G1 Z{round(0.3*(i+1),3)} F9000", ";TYPE:External perimeter", "G1 F1800", "G1 X150 Y150"]
    for (a, b) in [(170, 150), (170, 170), (150, 170), (150, 150)]:
        e2[0] += de(20, 0.3, 0.65); ml.append(f"G1 X{a} Y{b} E{e2[0]:.5f}")
r = estimate_lines(ml)
print("\nマルチツール PA:")
for t in ("0", "1"):
    pa = r["tools"][t]["pressure_advance"]
    print(f"  T{t}: value={pa['value']} fw={pa['firmware']} enabled={pa['enabled']}")
