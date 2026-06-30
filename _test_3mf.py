# -*- coding: utf-8 -*-
"""合成 Bambu .3mf を作って 3mf 読み込み/設定JSON取り込みを検証する。"""
import json, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.analyzer import analyze

root = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(root, "sample_synth", "bambu_sample.gcode.3mf")

# 実 G-code (Bambu風ヘッダ + ;TYPE: マーカ + 簡単な押出)
gcode = "\n".join([
    "; HEADER_BLOCK_START",
    "; BambuStudio 1.9.0",
    "; HEADER_BLOCK_END",
    "M104 S220", "M140 S60", "G21", "G90", "M83", "G92 E0",
    ";LAYER_CHANGE", ";Z:0.2", ";HEIGHT:0.2", "G1 Z0.2 F9000",
    ";TYPE:Outer wall", ";WIDTH:0.42", "G1 F1800",
    "G1 X100 Y100", "G1 X120 Y100 E0.6", "G1 X120 Y120 E0.6",
    ";TYPE:Sparse infill", "G1 F3600",
    "G1 X105 Y105", "G1 X115 Y115 E0.5",
    "G1 E-0.8 F1800",
])

# project_settings.config (Orca/Bambu キー語彙の JSON)
settings = {
    "layer_height": "0.2",
    "initial_layer_print_height": "0.2",
    "outer_wall_speed": "200",
    "inner_wall_speed": "250",
    "sparse_infill_speed": "270",
    "outer_wall_line_width": "0.42",
    "sparse_infill_density": "15%",
    "wall_loops": "3",
    "nozzle_temperature": ["220"],
    "hot_plate_temp": ["60"],
    "retraction_length": ["0.8"],
    "retraction_speed": ["30"],
    "fan_max_speed": ["100"],
    "filament_diameter": ["1.75"],
}

os.makedirs(os.path.dirname(out), exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr("3D/3dmodel.model", "<model/>")
    zf.writestr("Metadata/plate_1.gcode", gcode)
    zf.writestr("Metadata/project_settings.config", json.dumps(settings))
print("wrote", out)

r = analyze(out)
print("source :", r["meta"]["source"])
print("method :", r["meta"]["method"])
print("layer_height       :", r["quality"]["layer_height"], "(期待 0.2)")
print("outer_wall_speed   :", r["speed"]["outer_wall_speed"], "(期待 200)")
print("outer_wall_width   :", r["quality"]["outer_wall_width"], "(期待 0.42)")
print("wall_loops         :", r["strength"]["wall_loops"], "(期待 3)")
print("infill_density     :", r["strength"]["sparse_infill_density_pct"], "(期待 15)")
print("nozzle_temp        :", r["temperature"]["nozzle_temp"], "(期待 220)")
print("bed_temp           :", r["temperature"]["bed_temp"], "(期待 60)")
print("retract_length     :", r["retraction"]["retract_length"], "(期待 0.8)")
