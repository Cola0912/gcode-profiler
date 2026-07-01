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

GCODE_FIELD_TO_BLOCK = {
    "gcode.machine_start_gcode": "start_gcode",
    "gcode.machine_end_gcode": "end_gcode",
    "gcode.layer_change_gcode": "layer_change_gcode",
    "gcode.timelapse_gcode": "timelapse_gcode",
    "gcode.toolchange_gcode": "toolchange_gcode",
    "gcode.pause_gcode": "pause_gcode",
    "gcode.template_custom_gcode": "template_custom_gcode",
    "gcode.before_layer_change_gcode": "before_layer_change_gcode",
    "gcode.process_layer_change_gcode": "process_layer_change_gcode",
    "gcode.process_toolchange_gcode": "process_toolchange_gcode",
    "gcode.process_pause_gcode": "process_pause_gcode",
    "gcode.process_custom_gcode": "process_custom_gcode",
}

try:
    from .analyzer import analyze
    from . import schema as sc
    from . import exporters
    from . import export_flow
    from . import importers
    from .canonical import model as cn_model
    from .canonical import adapter as cn_adapter
    from .settings_dialog import SettingsDialog
except ImportError:
    from analyzer import analyze
    import schema as sc
    import exporters
    import export_flow
    import importers
    from canonical import model as cn_model
    from canonical import adapter as cn_adapter
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
        self.gcode_blocks = {key: "" for key in set(GCODE_FIELD_TO_BLOCK.values())}
        self.meta = {"source": "新規作成", "method": "手動", "tool_count": 1, "total_layers": "—"}
        self.canonical_profile = None
        self.unmapped = {}
        self.conflicts = []

    def load(self, result):
        self.values, self.provenance = sc.prefill_values(result)
        self.filaments = copy.deepcopy(result.get("filaments")) or self.filaments
        gb = result.get("gcode_blocks", {})
        self.gcode_blocks = {k: gb.get(k, "") for k in set(GCODE_FIELD_TO_BLOCK.values())}
        for field_key, block_key in GCODE_FIELD_TO_BLOCK.items():
            if self.gcode_blocks.get(block_key):
                self.values[field_key] = self.gcode_blocks[block_key]
                self.provenance[field_key] = "explicit_metadata"
        self.meta = dict(result.get("meta", {}))
        self.canonical_profile = None
        self.unmapped = {}
        self.conflicts = []

    def load_canonical_profile(self, profile):
        """Load a native-imported canonical profile into the legacy UI model."""
        self.canonical_profile = copy.deepcopy(profile)
        self.values, self.provenance = sc.default_values()
        self.unmapped = copy.deepcopy(profile.get("unmapped", {}))
        meta = profile.get("metadata", {})
        self.conflicts = list(meta.get("conflicts", []))

        for f in self._all_ui_fields():
            ckey = self._field_canonical_key(f)
            if not ckey:
                continue
            node = cn_model.get_value(profile, ckey)
            if not self._is_value_node(node):
                continue
            value = node.get("effective")
            if value is None:
                continue
            self.values[f.key] = value
            self.provenance[f.key] = self._node_provenance(node)

        self._load_filament_summary(profile)
        src = profile.get("source", {})
        slicer = src.get("source_slicer") or "Unknown"
        version = src.get("source_version")
        source = f"{slicer} {version}".strip() if version else slicer
        self.meta = {
            "source": source,
            "method": "プロファイル読込",
            "tool_count": len(self.filaments),
            "total_layers": "—",
            "profile_kind": meta.get("profile_kind"),
            "unmapped_count": len(self.unmapped),
            "conflict_count": len(self.conflicts),
        }

    def to_canonical_profile(self):
        """Return canonical profile with UI edits layered as `edited` values."""
        if self.canonical_profile is None:
            return cn_adapter.legacy_to_canonical(self.to_result())
        profile = copy.deepcopy(self.canonical_profile)
        for f in self._all_ui_fields():
            if self.provenance.get(f.key) != "edited":
                continue
            ckey = self._field_canonical_key(f)
            if not ckey:
                continue
            value = self.values.get(f.key)
            node = cn_model.get_value(profile, ckey)
            cv = (cn_model.CanonicalValue.from_dict(node)
                  if self._is_value_node(node)
                  else cn_model.CanonicalValue(unit=f.unit or None, value_mode="absolute"))
            cv.edited = value
            cv.status = "user"
            cv.source = "user"
            if f.key not in cv.source_keys:
                cv.source_keys.append(f.key)
            cn_model.set_value(profile, ckey, cv)
        return profile

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
        for field_key, block_key in GCODE_FIELD_TO_BLOCK.items():
            value = self.values.get(field_key)
            if value:
                result["gcode_blocks"][block_key] = value
        if self.filaments and self.filaments[0].get("nozzle_temp") is not None:
            result["temperature"]["nozzle_temp"] = self.filaments[0]["nozzle_temp"]
        return result

    @staticmethod
    def _all_ui_fields():
        for _group, (_title, schema) in sc.GROUPS.items():
            yield from sc.all_fields(schema)

    @staticmethod
    def _is_value_node(node):
        return isinstance(node, dict) and "effective" in node

    @staticmethod
    def _node_provenance(node):
        if node.get("status") == "conflict":
            return "conflict"
        if node.get("edited") is not None:
            return "edited"
        if node.get("configured") is not None:
            return "imported_profile"
        if node.get("emitted") is not None:
            return "runtime_command"
        if node.get("observed") is not None:
            return "estimated" if node.get("status") == "estimated" else "recovered"
        if node.get("target_default") is not None:
            return "target_default"
        return "unknown"

    @staticmethod
    def _field_canonical_key(f):
        if f.key in cn_adapter.LEGACY_MAP:
            return cn_adapter.LEGACY_MAP[f.key]
        if f.src and f.src in cn_adapter.LEGACY_MAP:
            return cn_adapter.LEGACY_MAP[f.src]
        if f.key in sc.ALIASES:
            return sc.ALIASES[f.key]
        return f.canonical_key or None

    def _load_filament_summary(self, profile):
        fl = {"tool": 0, "nozzle_temp": None, "bed_temp": None,
              "retract_length": None, "diameter": None, "material": None}
        pairs = {
            "nozzle_temp": "material.temperature.nozzle",
            "bed_temp": "material.temperature.bed",
            "diameter": "material.filament.diameter",
            "retract_length": "printer.extruder.retraction_length",
            "material": "material.type",
        }
        for dst, ckey in pairs.items():
            value = cn_model.effective_of(profile, ckey)
            if value is not None:
                fl[dst] = value
        self.filaments = [fl]


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
        self.btn_import = QPushButton("📥 プロファイル読込"); self.btn_import.clicked.connect(self.on_import_profile)
        bar.addWidget(self.btn_import)
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
        self.target_combo = QComboBox()
        self.target_combo.addItems([d for d, _id in export_flow.TARGET_CHOICES])
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
            f"ツール数: {self.model.meta.get('tool_count','—')}"
            f"{self._import_summary_text()}")

    def _import_summary_text(self):
        unmapped = self.model.meta.get("unmapped_count") or 0
        conflicts = self.model.meta.get("conflict_count") or 0
        parts = []
        if unmapped:
            parts.append(f"未対応/native-only: {unmapped}")
        if conflicts:
            parts.append(f"競合: {conflicts}")
        return "   |   " + " / ".join(parts) if parts else ""

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

    def on_import_profile(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "プロファイルを選択", "",
            "スライサープロファイル (*.json *.ini *.config *.cfg *.fff *.3mf *.zip);;すべて (*.*)")
        if not path:
            return
        try:
            self.import_profile_path(path, show_message=True)
        except Exception as exc:  # noqa
            QMessageBox.critical(self, "プロファイル読込エラー", str(exc))

    def import_profile_path(self, path, show_message=False):
        """Import a native slicer profile into the editable model."""
        profile = importers.import_profile(path)
        self.model.load_canonical_profile(profile)
        base = os.path.splitext(os.path.basename(path))[0]
        display_name = profile.get("metadata", {}).get("display_name") or base
        self.card_process.name_edit.setText(display_name)
        self._refresh_cards()
        det = profile.get("detection", {})
        unmapped = len(profile.get("unmapped", {}))
        warnings = profile.get("metadata", {}).get("inheritance_warnings", [])
        self.statusBar().showMessage(
            f"プロファイル読込完了 — {det.get('slicer', 'Unknown')} / 未対応 {unmapped} 項目")
        if show_message:
            msg = (f"スライサー: {det.get('slicer', 'Unknown')}\n"
                   f"形式: {det.get('format', 'unknown')}\n"
                   f"未対応/native-only: {unmapped} 項目")
            if warnings:
                msg += "\n\n継承警告:\n" + "\n".join(f"・{w}" for w in warnings[:8])
            QMessageBox.information(self, "プロファイル読込完了", msg)

    def open_path(self, path):
        """Analyze the given file path (used by file dialog and CLI argument)."""
        self.gcode_path = path
        base = os.path.splitext(os.path.basename(path))[0]
        self.card_process.name_edit.setText(base)
        self.progress.show(); self.btn_open.setEnabled(False)
        self.btn_import.setEnabled(False); self.btn_new.setEnabled(False)
        self.statusBar().showMessage("解析中…")
        self.worker = AnalyzeWorker(path, self.dia_spin.value())
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def on_failed(self, msg):
        self.progress.hide(); self.btn_open.setEnabled(True)
        self.btn_import.setEnabled(True); self.btn_new.setEnabled(True)
        QMessageBox.critical(self, "解析エラー", msg); self.statusBar().showMessage("解析失敗")

    def on_done(self, result):
        self.progress.hide(); self.btn_open.setEnabled(True)
        self.btn_import.setEnabled(True); self.btn_new.setEnabled(True)
        self.model.load(result)
        self._refresh_cards()
        self.statusBar().showMessage("解析完了 — 各カードをクリックして編集できます")

    # ------------------------------------------------------------------
    def on_export(self):
        result = self.model.to_result()
        name = self.card_process.name_edit.text().strip() or "Recovered Profile"
        display = self.target_combo.currentText()
        target = export_flow.target_id(display)
        # 1) build conversion plan and show a preview (Phase 4/5 pipeline)
        try:
            if self.model.canonical_profile is not None:
                _prof, plan = export_flow.build_plan_from_canonical(
                    self.model.to_canonical_profile(), target)
            else:
                _prof, plan = export_flow.build_plan_from_legacy(result, target)
        except Exception as exc:  # noqa
            QMessageBox.critical(self, "変換エラー", str(exc)); return
        pv = export_flow.preview(plan)
        msg = (f"変換スコア: {pv['conversion_score']}\n"
               f"確定 {pv['ready']} / 導出 {pv['derived']} / "
               f"未対応 {pv['unsupported']} / 競合 {pv['conflict']}\n"
               f"要ユーザー入力: {len(pv['required_user_inputs'])} 件"
               + (f"（うち重大 {len(pv['critical_inputs'])}）" if pv['has_critical'] else ""))
        if pv["has_critical"]:
            crit = "\n".join(f"・{r['canonical_key']}: {r['reason']}" for r in pv["critical_inputs"])
            ans = QMessageBox.warning(
                self, "重大な必須入力が未解決",
                msg + "\n\n重大な項目が未確定です（エキスパート上書きで続行可）:\n" + crit
                + "\n\n続行しますか？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if ans != QMessageBox.Yes:
                return
            for r in plan["required_user_inputs"]:
                r["safety_level"] = "important"  # expert override: unblock writer
        else:
            ans = QMessageBox.question(self, "変換プレビュー", msg + "\n\n書き出しますか？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if ans != QMessageBox.Yes:
                return
        # 2) native write
        try:
            wres = export_flow.write_native(plan, name=name)
        except Exception as exc:  # noqa
            QMessageBox.critical(self, "書き出しエラー", str(exc)); return
        if wres.blocked:
            crit = "\n".join(f"・{r.get('canonical_key')}" for r in wres.required_user_inputs)
            QMessageBox.critical(self, "書き出しをブロックしました",
                                 "重大な必須入力が未解決のため出力できません:\n" + crit)
            return
        folder = QFileDialog.getExistingDirectory(self, "出力先フォルダを選択")
        if not folder:
            return
        written = []
        for fname, content in wres.files:
            with open(os.path.join(folder, fname), "w", encoding="utf-8") as fh:
                fh.write(content)
            written.append(fname)
        extra = (f"\n\n未対応 {len(wres.unsupported)} 項目（ターゲット非対応）"
                 if wres.unsupported else "")
        QMessageBox.information(self, "完了",
                               f"{display} 形式で書き出しました:\n\n" + "\n".join(written) + extra)
        self.statusBar().showMessage(f"{display} へ {len(written)} ファイル書き出し完了"
                                     f"（スコア {pv['conversion_score']}）")


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
