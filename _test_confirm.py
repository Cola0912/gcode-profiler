# -*- coding: utf-8 -*-
import sys, os, collections
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PySide6.QtWidgets import QApplication
from gcode_profiler.analyzer import analyze
from gcode_profiler.gui import MainWindow
from gcode_profiler import schema as sc
from gcode_profiler.settings_dialog import SettingsDialog

app = QApplication(sys.argv)
win = MainWindow()
win.model.load(analyze(os.path.join(os.path.dirname(__file__), "sample_gcode", "豆腐.gcode")))
print("before:", collections.Counter(win.model.provenance.values()))
for grp in ("printer", "filament", "process"):
    t, s = sc.GROUPS[grp]
    SettingsDialog(win, t, s, win.model)._accept(confirm_defaults=True)
print("after :", collections.Counter(win.model.provenance.values()))
