# -*- coding: utf-8 -*-
"""
スキーマ駆動の詳細設定ダイアログ
================================
OrcaSlicer の「プリンター設定 / フィラメント設定 / プロセス設定」画面を踏襲。
サブタブ + セクション見出し + 編集可能フィールドを描画し、共有 Model を読み書きする。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QScrollArea,
    QFormLayout, QLabel, QLineEdit, QCheckBox, QComboBox, QSpinBox, QPushButton,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QToolButton,
)

try:
    from . import material as material_mod
except ImportError:
    import material as material_mod

DIALOG_QSS = """
QDialog { background:#2b2d30; }
QWidget { color:#dfe1e5; font-size:13px; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTableWidget {
    background:#1e1f22; border:1px solid #3a3d41; border-radius:4px; padding:3px; }
QLineEdit:focus, QComboBox:focus { border:1px solid #00a98f; }
QTabBar::tab { background:#2b2d30; padding:7px 14px; color:#9aa0a6; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#fff; border-bottom:2px solid #00a98f; }
QTabWidget::pane { border:1px solid #3a3d41; }
QLabel#sec { color:#00c2a8; font-weight:bold; font-size:13px; }
QPushButton { background:#3a3d41; border:1px solid #4a4d51; border-radius:5px; padding:6px 16px; }
QPushButton#accent { background:#00a98f; color:#08110f; font-weight:bold; border:none; }
QFrame#hr { background:#3a3d41; max-height:1px; min-height:1px; }
"""


class SettingsDialog(QDialog):
    def __init__(self, parent, title, schema, model):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 720)
        self.schema = schema
        self.model = model
        self.widgets = {}      # key -> (field, widget)
        self.default_decor = {}  # key -> dict(widget,label,chip,btn) 既定値ハイライト装飾
        self.fil_table = None
        self.fil_forms = []      # per_filament: [dict(index, material, nozzle, bed, retract, diameter)]
        self.gcode_edits = {}
        self._build()
        self.setStyleSheet(DIALOG_QSS)

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)
        for st in self.schema:
            if st.special == "filaments":
                tabs.addTab(self._filament_tab(), st.title)
            elif st.special == "per_filament":
                for i, fl in enumerate(self.model.filaments):
                    tabs.addTab(self._per_filament_tab(i, fl), f"フィラメント T{i}")
            elif st.special == "gcode":
                tabs.addTab(self._gcode_tab(), st.title)
            else:
                tabs.addTab(self._form_tab(st), st.title)
        legend = QLabel(
            '<span style="color:#f0b13c;">■ 既定値</span> = G-codeから取得できず既定値を使用'
            '　　<span style="color:#f0b13c;">⚠推定</span> = ツールパスからの推定値')
        legend.setStyleSheet("font-size:11px;")
        root.addWidget(legend)

        btns = QHBoxLayout()
        confirm = QPushButton("既定値のまま確定")
        confirm.setToolTip("既定値の項目を確認済みとして確定し、ハイライトを解除します")
        confirm.clicked.connect(lambda: self._accept(confirm_defaults=True))
        btns.addWidget(confirm)
        btns.addStretch(1)
        cancel = QPushButton("キャンセル"); cancel.clicked.connect(self.reject)
        ok = QPushButton("OK"); ok.setObjectName("accent"); ok.clicked.connect(self._accept)
        btns.addWidget(cancel); btns.addWidget(ok)
        root.addLayout(btns)

    # ------------------------------------------------------------------
    def _form_tab(self, subtab):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(20, 16, 20, 16); v.setSpacing(6)
        for sec_title, fields in subtab.sections:
            head = QLabel("● " + sec_title); head.setObjectName("sec")
            v.addWidget(head)
            hr = QFrame(); hr.setObjectName("hr"); v.addWidget(hr)
            form = QFormLayout(); form.setContentsMargins(6, 4, 6, 10); form.setSpacing(9)
            for f in fields:
                w = self._make_widget(f)
                self.widgets[f.key] = (f, w)
                row = QHBoxLayout(); row.addWidget(w)
                if f.unit:
                    u = QLabel(f.unit); u.setStyleSheet("color:#8a9099;"); row.addWidget(u)
                # 出所ハイライト: G-codeから取得できず既定値の項目を強調
                # (空文字が既定の項目=Notes/除外領域等 はバッジ不要)
                prov = self.model.provenance.get(f.key)
                cur_val = self.model.values.get(f.key)
                is_default = (prov == "default" and cur_val not in (None, ""))
                lab = f.label + ("  ⚠推定" if f.low_conf else "")
                lw = QLabel(lab)
                chip = btn = None
                if is_default:
                    w.setStyleSheet(self._amber_style(w))
                    chip = QLabel("既定値")
                    chip.setStyleSheet("color:#f0b13c; font-size:11px; font-weight:bold;"
                                       " border:1px solid #c08a1e; border-radius:3px; padding:0 5px;")
                    row.addWidget(chip)
                    btn = QToolButton(); btn.setText("✓ 確定")
                    btn.setToolTip("この項目を既定値のまま確定(ハイライト解除)")
                    btn.setStyleSheet("QToolButton{color:#9aa0a6; border:1px solid #4a4d51;"
                                      " border-radius:3px; padding:1px 6px;}"
                                      "QToolButton:hover{color:#00c2a8; border-color:#00a98f;}")
                    btn.clicked.connect(lambda _=False, k=f.key: self._confirm_field(k))
                    row.addWidget(btn)
                    lw.setStyleSheet("color:#f0b13c;")
                    self.default_decor[f.key] = {"w": w, "label": lw, "chip": chip, "btn": btn}
                    self._connect_edit(f, w)
                row.addStretch(1)
                holder = QWidget(); holder.setLayout(row)
                form.addRow(lw, holder)
            v.addLayout(form)
        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    @staticmethod
    def _amber_style(w):
        base = "background:#3b3320; border:1px solid #c08a1e; border-radius:4px; padding:3px;"
        return base

    def _connect_edit(self, f, w):
        """既定値フィールドが編集されたら即ハイライト解除する。"""
        cb = lambda *a, k=f.key: self._field_edited(k)
        if isinstance(w, QCheckBox):
            w.toggled.connect(cb)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(cb)
        else:
            w.textEdited.connect(cb)

    def _field_edited(self, key):
        if self.model.provenance.get(key) == "default":
            self.model.provenance[key] = "edited"
        self._clear_decor(key)

    def _confirm_field(self, key):
        if self.model.provenance.get(key) == "default":
            self.model.provenance[key] = "confirmed"
        self._clear_decor(key)

    def _clear_decor(self, key):
        d = self.default_decor.get(key)
        if not d:
            return
        d["w"].setStyleSheet("")
        d["label"].setStyleSheet("")
        if d["chip"]:
            d["chip"].hide()
        if d["btn"]:
            d["btn"].hide()

    def _make_widget(self, f):
        cur = self.model.values.get(f.key, f.default)
        if f.kind == "bool":
            w = QCheckBox(); w.setChecked(bool(cur)); return w
        if f.kind == "choice":
            w = QComboBox(); w.addItems(f.choices or [])
            if cur in (f.choices or []):
                w.setCurrentText(str(cur))
            return w
        w = QLineEdit()
        if not (f.kind == "num" or f.kind == "int"):
            pass
        else:
            w.setMaximumWidth(150)
        w.setText(self._fmt(cur))
        return w

    @staticmethod
    def _fmt(v):
        if v is None or v == "":
            return ""
        if isinstance(v, bool):
            return "1" if v else "0"
        if isinstance(v, float):
            return str(int(v)) if v == int(v) else str(round(v, 3))
        return str(v)

    # ------------------------------------------------------------------
    def _filament_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(18, 14, 18, 14)
        top = QHBoxLayout(); top.addWidget(QLabel("フィラメント数(ツール):"))
        self.tool_spin = QSpinBox(); self.tool_spin.setRange(1, 16)
        self.tool_spin.setValue(max(1, len(self.model.filaments)))
        self.tool_spin.valueChanged.connect(self._resize_fil)
        top.addWidget(self.tool_spin); top.addStretch(1); lay.addLayout(top)
        self.fil_table = QTableWidget(0, 4)
        self.fil_table.setHorizontalHeaderLabels(
            ["ツール", "ノズル温度(℃)", "ベッド温度(℃)", "リトラクト長(mm)"])
        self.fil_table.verticalHeader().setVisible(False)
        for c in range(4):
            self.fil_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.Stretch)
        lay.addWidget(self.fil_table, 1)
        self._load_fil()
        return w

    def _load_fil(self):
        fils = self.model.filaments or [{"tool": 0}]
        self.fil_table.setRowCount(len(fils))
        for r, fl in enumerate(fils):
            self._set_cell(r, 0, f"T{fl.get('tool', r)}", editable=False)
            self._set_cell(r, 1, self._fmt(fl.get("nozzle_temp")))
            self._set_cell(r, 2, self._fmt(fl.get("bed_temp")))
            self._set_cell(r, 3, self._fmt(fl.get("retract_length")))

    def _set_cell(self, r, c, text, editable=True):
        it = QTableWidgetItem(text)
        if not editable:
            it.setFlags(Qt.ItemIsEnabled)
            it.setTextAlignment(Qt.AlignCenter)
        self.fil_table.setItem(r, c, it)

    def _resize_fil(self, n):
        cur = self.fil_table.rowCount()
        self.fil_table.setRowCount(n)
        for r in range(cur, n):
            self._set_cell(r, 0, f"T{r}", editable=False)
            for c in range(1, 4):
                self._set_cell(r, c, "")

    # ------------------------------------------------------------------
    def _per_filament_tab(self, idx, fl):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        inner = QWidget(); v = QVBoxLayout(inner); v.setContentsMargins(20, 16, 20, 16)
        head = QLabel(f"● フィラメント T{idx}"); head.setObjectName("sec")
        v.addWidget(head)
        form = QFormLayout(); form.setSpacing(9)

        mat = QComboBox(); mat.addItems(material_mod.MATERIAL_CHOICES)
        cur_mat = fl.get("material")
        if cur_mat in material_mod.MATERIAL_CHOICES:
            mat.setCurrentText(cur_mat)
        mat_row = QHBoxLayout(); mat_row.addWidget(mat)
        if fl.get("material_confidence"):
            chip = QLabel(f"推定 {fl['material_confidence']}%")
            chip.setStyleSheet("color:#00c2a8; font-size:11px; border:1px solid #00a98f;"
                               " border-radius:3px; padding:0 5px;")
            mat_row.addWidget(chip)
        mat_row.addStretch(1)
        mh = QWidget(); mh.setLayout(mat_row)
        form.addRow(QLabel("素材(推定)"), mh)

        nozzle = QLineEdit(self._fmt(fl.get("nozzle_temp")))
        bed = QLineEdit(self._fmt(fl.get("bed_temp")))
        retract = QLineEdit(self._fmt(fl.get("retract_length")))
        diameter = QLineEdit(self._fmt(fl.get("diameter") or 1.75))
        form.addRow(QLabel("ノズル温度 (℃)"), nozzle)
        form.addRow(QLabel("ベッド温度 (℃)"), bed)
        form.addRow(QLabel("リトラクト長 (mm)"), retract)
        form.addRow(QLabel("フィラメント径 (mm)"), diameter)
        if fl.get("nozzle_diameter"):
            nd = QLabel(f"{fl['nozzle_diameter']} mm (G-codeから推定)")
            nd.setStyleSheet("color:#9aa0a6;")
            form.addRow(QLabel("ノズル径"), nd)
        v.addLayout(form); v.addStretch(1)
        scroll.setWidget(inner)
        self.fil_forms.append({"index": idx, "material": mat, "nozzle": nozzle,
                               "bed": bed, "retract": retract, "diameter": diameter})
        return scroll

    # ------------------------------------------------------------------
    def _gcode_tab(self):
        w = QWidget(); lay = QVBoxLayout(w); lay.setContentsMargins(12, 10, 12, 10)
        for title, key in [("■ スタート G-code", "start_gcode"),
                           ("■ エンド G-code", "end_gcode"),
                           ("■ ツールチェンジ G-code", "toolchange_gcode")]:
            lay.addWidget(QLabel(title))
            ed = QPlainTextEdit()
            ed.setStyleSheet("font-family:Consolas,monospace; font-size:12px;")
            ed.setPlainText(self.model.gcode_blocks.get(key, "") or "")
            self.gcode_edits[key] = ed
            lay.addWidget(ed, 1)
        return w

    # ------------------------------------------------------------------
    def _accept(self, confirm_defaults=False):
        # フォーム値 -> model.values (編集されたら出所を 'edited' にしてハイライト解除)
        for key, (f, w) in self.widgets.items():
            old = self.model.values.get(key)
            if isinstance(w, QCheckBox):
                new = w.isChecked()
            elif isinstance(w, QComboBox):
                new = w.currentText()
            else:
                txt = w.text().strip()
                if txt == "":
                    new = None
                elif f.kind in ("num", "int"):
                    try:
                        new = int(txt) if f.kind == "int" else float(txt)
                    except ValueError:
                        new = txt
                else:
                    new = txt
            self.model.values[key] = new
            if new != old and self.model.provenance.get(key) == "default":
                self.model.provenance[key] = "edited"
        # 「既定値のまま確定」: 残る既定値を確認済みにしてハイライト解除
        if confirm_defaults:
            for key, _w in self.widgets.items():
                if self.model.provenance.get(key) == "default":
                    self.model.provenance[key] = "confirmed"
        # フィラメント表
        if self.fil_table is not None:
            fils = []
            for r in range(self.fil_table.rowCount()):
                def cell(c):
                    it = self.fil_table.item(r, c)
                    t = it.text().strip() if it else ""
                    try:
                        return float(t) if t else None
                    except ValueError:
                        return None
                fils.append({"tool": r, "nozzle_temp": cell(1),
                             "bed_temp": cell(2), "retract_length": cell(3)})
            self.model.filaments = fils
        # per_filament フォーム -> model.filaments
        def _num(le):
            t = le.text().strip()
            try:
                return float(t) if t else None
            except ValueError:
                return None
        for ff in self.fil_forms:
            i = ff["index"]
            if i < len(self.model.filaments):
                fl = self.model.filaments[i]
                fl["material"] = ff["material"].currentText()
                fl["nozzle_temp"] = _num(ff["nozzle"])
                fl["bed_temp"] = _num(ff["bed"])
                fl["retract_length"] = _num(ff["retract"])
                fl["diameter"] = _num(ff["diameter"])
        # G-code
        if self.gcode_edits:
            for key, ed in self.gcode_edits.items():
                self.model.gcode_blocks[key] = ed.toPlainText()
        self.accept()
