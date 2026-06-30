# -*- coding: utf-8 -*-
"""
OrcaSlicer 風 プロファイル復元・編集ツール (メインウィンドウ)
============================================================
G-code を解析して値をプリフィル → プリンター/フィラメント/プロセスの各カードをクリックで
詳細設定ダイアログを開いて編集 → 指定スライサー形式で書き出す。
"""
from __future__ import annotations

import copy
import os
import sys

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QLineEdit, QComboBox, QMessageBox,
    QProgressBar, QStatusBar, QFrame, QDoubleSpinBox,
)

try:
    from .analyzer import analyze
    from . import schema as sc
    from . import exporters
    from .settings_dialog import SettingsDialog
except ImportError:
    from analyzer import analyze
    import schema as sc
    import exporters
    from settings_dialog import SettingsDialog


DARK_QSS = """
QWidget { background:#2b2d30; color:#dfe1e5; font-size:13px; }
QLineEdit, QComboBox, QDoubleSpinBox {
    background:#1e1f22; border:1px solid #3a3d41; border-radius:4px; padding:5px; }
QLineEdit:focus, QComboBox:focus { border:1px solid #00a98f; }
QPushButton { background:#3a3d41; border:1px solid #4a4d51; border-radius:6px; padding:7px 14px; }
QPushButton:hover { background:#46494d; }
QPushButton:disabled { color:#777; }
QPushButton#accent { background:#00a98f; color:#08110f; font-weight:bold; border:none; padding:9px 18px; }
QPushButton#accent:hover { background:#13c2a6; }
QFrame#card { background:#323438; border:1px solid #3a3d41; border-radius:10px; }
QFrame#card:hover { border:1px solid #00a98f; }
QLabel#cardtitle { font-size:15px; font-weight:bold; color:#e8eaed; }
QLabel#cardsub { color:#9aa0a6; font-size:12px; }
QLabel#info { color:#00c2a8; font-weight:bold; }
QProgressBar { border:1px solid #3a3d41; border-radius:4px; background:#1e1f22; }
QProgressBar::chunk { background:#00a98f; }
"""


class Model:
    """編集対象の単一プロファイル(プリンター/フィラメント/プロセス共有の値ストア)。"""
    def __init__(self):
        self.values, self.provenance = sc.default_values()
        self.filaments = [{"tool": 0, "nozzle_temp": None, "bed_temp": None, "retract_length": None}]
        self.gcode_blocks = {"start_gcode": "", "end_gcode": "", "toolchange_gcode": ""}
        self.meta = {"source": "新規作成", "method": "手動", "tool_count": 1, "total_layers": "—"}

    def load(self, result):
        self.values, self.provenance = sc.prefill_values(result)
        self.filaments = copy.deepcopy(result.get("filaments")) or self.filaments
        gb = result.get("gcode_blocks", {})
        self.gcode_blocks = {k: gb.get(k, "") for k in ("start_gcode", "end_gcode", "toolchange_gcode")}
        self.meta = dict(result.get("meta", {}))

    def to_result(self):
        result = {"meta": dict(self.meta), "quality": {}, "speed": {}, "strength": {},
                  "temperature": {}, "retraction": {}, "machine": {}, "filament": {}}
        for key, v in self.values.items():
            sec, fld = key.split(".", 1)
            result.setdefault(sec, {})[fld] = v
        result["filaments"] = self.filaments
        result["meta"]["tool_count"] = len(self.filaments)
        result["meta"]["tools_used"] = [f.get("tool", i) for i, f in enumerate(self.filaments)]
        result["gcode_blocks"] = self.gcode_blocks
        if self.filaments and self.filaments[0].get("nozzle_temp") is not None:
            result["temperature"]["nozzle_temp"] = self.filaments[0]["nozzle_temp"]
        return result


class AnalyzeWorker(QThread):
    done = Signal(dict)
    failed = Signal(str)

    def __init__(self, path, diameter):
        super().__init__()
        self.path, self.diameter = path, diameter

    def run(self):
        try:
            self.done.emit(analyze(self.path, filament_diameter=self.diameter))
        except Exception as exc:  # noqa
            import traceback
            self.failed.emit(f"{exc}\n{traceback.format_exc()}")


class SectionCard(QFrame):
    """クリックで詳細設定ダイアログを開くカード(プリンター/フィラメント/プロセス)。"""
    def __init__(self, title, on_edit):
        super().__init__()
        self.setObjectName("card")
        self.on_edit = on_edit
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 12, 16, 12)
        top = QHBoxLayout()
        self.title_lbl = QLabel(title); self.title_lbl.setObjectName("cardtitle")
        top.addWidget(self.title_lbl); top.addStretch(1)
        self.btn = QPushButton("✎ 設定")
        self.btn.clicked.connect(on_edit)
        top.addWidget(self.btn)
        lay.addLayout(top)
        self.name_edit = QLineEdit()
        lay.addWidget(self.name_edit)
        self.sub = QLabel(""); self.sub.setObjectName("cardsub")
        lay.addWidget(self.sub)

    def mouseDoubleClickEvent(self, e):
        self.on_edit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("G-code プロファイル復元・編集ツール")
        self.resize(560, 620)
        self.model = Model()
        self.gcode_path = None
        self.worker = None
        self._build_ui()
        self._refresh_cards()

    def _build_ui(self):
        central = QWidget(); self.setCentralWidget(central)
        root = QVBoxLayout(central); root.setSpacing(10); root.setContentsMargins(14, 12, 14, 12)

        bar = QHBoxLayout()
        self.btn_open = QPushButton("📂 G-code を開く"); self.btn_open.clicked.connect(self.on_open)
        bar.addWidget(self.btn_open)
        self.btn_new = QPushButton("✚ 新規"); self.btn_new.clicked.connect(self.on_new)
        bar.addWidget(self.btn_new)
        bar.addWidget(QLabel("径"))
        self.dia_spin = QDoubleSpinBox(); self.dia_spin.setRange(1.0, 3.5)
        self.dia_spin.setSingleStep(0.05); self.dia_spin.setValue(1.75); self.dia_spin.setSuffix(" mm")
        bar.addWidget(self.dia_spin); bar.addStretch(1)
        root.addLayout(bar)

        self.progress = QProgressBar(); self.progress.setRange(0, 0); self.progress.hide()
        root.addWidget(self.progress)

        self.info = QLabel("スライサー: —   |   復元方法: —"); self.info.setObjectName("info")
        root.addWidget(self.info)

        # 3 カード
        self.card_printer = SectionCard("🖨  プリンター", lambda: self.open_dialog("printer"))
        self.card_filament = SectionCard("◎  フィラメント", lambda: self.open_dialog("filament"))
        self.card_process = SectionCard("≣  プロセス", lambda: self.open_dialog("process"))
        self.card_printer.name_edit.setText("Recovered Printer")
        self.card_filament.name_edit.setText("Recovered Filament")
        self.card_process.name_edit.setText("Recovered Profile")
        for c in (self.card_printer, self.card_filament, self.card_process):
            root.addWidget(c)
        root.addStretch(1)

        exp = QHBoxLayout()
        exp.addWidget(QLabel("出力先:"))
        self.target_combo = QComboBox(); self.target_combo.addItems(list(exporters.TARGETS.keys()))
        exp.addWidget(self.target_combo, 1)
        self.btn_export = QPushButton("プロファイル書き出し"); self.btn_export.setObjectName("accent")
        self.btn_export.clicked.connect(self.on_export)
        exp.addWidget(self.btn_export)
        root.addLayout(exp)

        self.setStatusBar(QStatusBar()); self.statusBar().showMessage("準備完了")
        self.setStyleSheet(DARK_QSS)

    # ------------------------------------------------------------------
    def open_dialog(self, group):
        title, schema = sc.GROUPS[group]
        dlg = SettingsDialog(self, title, schema, self.model)
        if dlg.exec():
            self._refresh_cards()
            self.statusBar().showMessage(f"{title} を更新しました")

    def _refresh_cards(self):
        v = self.model.values
        def g(k, unit=""):
            x = v.get(k)
            if x is None:
                return "—"
            if isinstance(x, float):
                x = int(x) if x == int(x) else round(x, 2)
            return f"{x}{unit}"
        self.card_process.sub.setText(
            f"積層 {g('quality.layer_height','mm')} / 外壁速度 {g('speed.outer_wall_speed','mm/s')} "
            f"/ 壁 {g('strength.wall_loops','本')} / 密度 {g('strength.sparse_infill_density_pct','%')}")
        t0 = self.model.filaments[0] if self.model.filaments else {}
        self.card_filament.sub.setText(
            f"ツール数 {len(self.model.filaments)} / 素材 {t0.get('material') or '—'} / "
            f"ノズル {t0.get('nozzle_temp','—')}℃ / ベッド {t0.get('bed_temp','—')}℃")
        nz = self.model.meta.get("nozzle_diameter_est")
        nzc = self.model.meta.get("nozzle_confidence")
        nz_txt = f"{nz}mm({nzc}%)" if nz else "—"
        self.card_printer.sub.setText(
            f"ノズル径(推定) {nz_txt} / G-codeスタイル {g('machine.gcode_flavor')} "
            f"/ 造形高さ {g('machine.printable_height','mm')}")
        self.info.setText(
            f"スライサー: {self.model.meta.get('source','—')}   |   "
            f"復元方法: {self.model.meta.get('method','—')}   |   "
            f"ツール数: {self.model.meta.get('tool_count','—')}")

    # ------------------------------------------------------------------
    def on_new(self):
        self.model = Model()
        self._refresh_cards()
        self.statusBar().showMessage("新規プロファイル")

    def on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "G-code を選択", "",
            "G-code / 3mf (*.gcode *.gco *.g *.nc *.3mf);;すべて (*.*)")
        if not path:
            return
        self.open_path(path)

    def open_path(self, path):
        """Analyze the given file path (used by file dialog and CLI argument)."""
        self.gcode_path = path
        base = os.path.splitext(os.path.basename(path))[0]
        self.card_process.name_edit.setText(base)
        self.progress.show(); self.btn_open.setEnabled(False); self.btn_new.setEnabled(False)
        self.statusBar().showMessage("解析中…")
        self.worker = AnalyzeWorker(path, self.dia_spin.value())
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_failed(self, msg):
        self.progress.hide(); self.btn_open.setEnabled(True); self.btn_new.setEnabled(True)
        QMessageBox.critical(self, "解析エラー", msg); self.statusBar().showMessage("解析失敗")

    def on_done(self, result):
        self.progress.hide(); self.btn_open.setEnabled(True); self.btn_new.setEnabled(True)
        self.model.load(result)
        self._refresh_cards()
        self.statusBar().showMessage("解析完了 — 各カードをクリックして編集できます")

    # ------------------------------------------------------------------
    def on_export(self):
        result = self.model.to_result()
        name = self.card_process.name_edit.text().strip() or "Recovered Profile"
        target = self.target_combo.currentText()
        try:
            files = exporters.export(result, name, target,
                                     printer_name=self.card_printer.name_edit.text().strip(),
                                     filament_name=self.card_filament.name_edit.text().strip())
        except Exception as exc:  # noqa
            QMessageBox.critical(self, "書き出しエラー", str(exc)); return
        folder = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択")
        if not folder:
            return
        written = []
        for fname, content in files:
            with open(os.path.join(folder, fname), "w", encoding="utf-8") as fh:
                fh.write(content)
            written.append(fname)
        QMessageBox.information(self, "完了",
                               f"{target} 形式で書き出しました:\n\n" + "\n".join(written))
        self.statusBar().showMessage(f"{target} へ {len(written)} ファイル書き出し完了")


ICON_NAME = "GCode_Profile_Reverse_Engineer.ico"


def _icon_path():
    try:
        from .resources import resource_path
    except ImportError:
        from resources import resource_path
    return resource_path(ICON_NAME)


def main(open_file=None):
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ip = _icon_path()
    if ip:
        app.setWindowIcon(QIcon(ip))
    win = MainWindow()
    if ip:
        win.setWindowIcon(QIcon(ip))
    win.show()
    # optional file passed on the command line
    if open_file:
        if os.path.exists(open_file):
            try:
                win.open_path(open_file)
            except Exception as exc:  # noqa
                QMessageBox.warning(win, "読み込みエラー", f"ファイルを開けませんでした:\n{exc}")
        else:
            QMessageBox.warning(win, "ファイルが見つかりません", f"指定パスが存在しません:\n{open_file}")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
