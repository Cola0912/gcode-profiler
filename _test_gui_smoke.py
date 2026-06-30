# -*- coding: utf-8 -*-
"""GUI 全体(モデル/詳細ダイアログ/エクスポート)を offscreen で通す。"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from gcode_profiler.analyzer import analyze
from gcode_profiler.gui import MainWindow, Model
from gcode_profiler import schema as sc, exporters
from gcode_profiler.settings_dialog import SettingsDialog

app = QApplication(sys.argv)
root = os.path.dirname(os.path.abspath(__file__))

win = MainWindow()
r = analyze(os.path.join(root, "sample_gcode", "豆腐.gcode"))
win.model.load(r)
win._refresh_cards()
print("info:", win.info.text())
print("process card:", win.card_process.sub.text())
print("printer card:", win.card_printer.sub.text())
print("filament card:", win.card_filament.sub.text())

# 各詳細ダイアログを構築して書き戻し(編集UIの健全性確認)
for grp in ("printer", "filament", "process"):
    title, schema = sc.GROUPS[grp]
    dlg = SettingsDialog(win, title, schema, win.model)
    dlg._accept()
    print(f"dialog {grp}: OK (fields={len(dlg.widgets)})")

# 値が保持されているか + マシン諸元
res = win.model.to_result()
print("gcode_flavor:", res["machine"].get("gcode_flavor"),
      "| printable_height:", res["machine"].get("printable_height"))
print("layer_height:", res["quality"].get("layer_height"))

# 全ターゲットへエクスポート
for t in exporters.TARGETS:
    files = exporters.export(res, "Smoke", t, printer_name="MyPrinter", filament_name="MyFil")
    print(f"  export {t}: {[f for f,_ in files]}")
print("ALL OK")
