# -*- coding: utf-8 -*-
"""
スキーマ駆動の詳細設定ダイアログ
================================
OrcaSlicer の「プリンター設定 / フィラメント設定 / プロセス設定」画面を踏襲。
サブタブ + セクション見出し + 編集可能フィールドを描画し、共有 Model を読み書きする。

Phase 5.5 追加機能:
  - 11 種類の出所状態バッジ (recovered / default / estimated / unknown / unsupported …)
  - label / native_key / canonical_key による全タブ横断検索
  - Basic / Advanced / Expert 可視性フィルター
  - タブ選択時の遅延ウィジェット生成 (LazyTab)
  - セクション折りたたみ
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QScrollArea,
    QFormLayout, QLabel, QLineEdit, QCheckBox, QComboBox, QSpinBox, QPushButton,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QToolButton, QButtonGroup, QSizePolicy,
)

try:
    from . import material as material_mod
except ImportError:
    import material as material_mod


# ---------------------------------------------------------------------------
# 出所（provenance）バッジ設定
# {state: (表示ラベル, 背景色, 文字/枠色)}
# ---------------------------------------------------------------------------
PROV_BADGE: dict[str, tuple[str, str, str]] = {
    "recovered":          ("復元",        "#1a3a2a", "#00c2a8"),
    "estimated":          ("推定",         "#3b2a00", "#f0b13c"),
    "explicit_metadata":  ("メタデータ",   "#1a2a4a", "#4aade0"),
    "runtime_command":    ("コマンド",     "#1a3a3a", "#00c2c2"),
    "calculated":         ("計算値",       "#2a1a4a", "#a07adc"),
    "imported_profile":   ("プロファイル", "#1a3030", "#00a98f"),
    "conflict":           ("競合",         "#3a1010", "#ff6b6b"),
    "default":            ("既定値",       "#3b3000", "#f0b13c"),
    "application_default":("アプリ既定",   "#2a2a00", "#c0c020"),
    "target_default":     ("目標既定",     "#282828", "#808080"),
    "unknown":            ("不明",         "#2a2a2a", "#909090"),
    "unsupported":        ("未対応",       "#3a1010", "#cc4444"),
}

DIALOG_QSS = """
QDialog { background:#2b2d30; }
QWidget { color:#dfe1e5; font-size:13px; }
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit, QTableWidget {
    background:#1e1f22; border:1px solid #3a3d41; border-radius:4px; padding:3px; }
QLineEdit:focus, QComboBox:focus { border:1px solid #00a98f; }
QTabBar::tab { background:#2b2d30; padding:7px 14px; color:#9aa0a6;
               border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#fff; border-bottom:2px solid #00a98f; }
QTabWidget::pane { border:1px solid #3a3d41; }
QLabel#sec { color:#00c2a8; font-weight:bold; font-size:13px; }
QPushButton { background:#3a3d41; border:1px solid #4a4d51; border-radius:5px; padding:6px 16px; }
QPushButton#accent { background:#00a98f; color:#08110f; font-weight:bold; border:none; }
QPushButton#vis_btn { background:#2b2d30; border:1px solid #3a3d41; border-radius:4px;
                       padding:4px 10px; font-size:12px; }
QPushButton#vis_btn:checked { background:#00a98f; color:#08110f; border-color:#00a98f; }
QPushButton#sec_toggle { background:transparent; border:none; color:#00c2a8;
                          font-weight:bold; font-size:13px; text-align:left; padding:2px 0; }
QPushButton#sec_toggle:hover { color:#13c2a6; }
QFrame#hr { background:#3a3d41; max-height:1px; min-height:1px; }
QLineEdit#search { background:#1e1f22; border:1px solid #3a3d41; border-radius:4px;
                    padding:5px; font-size:13px; }
QLineEdit#search:focus { border:1px solid #00a98f; }
"""


# ---------------------------------------------------------------------------
# 遅延タブウィジェット
# ---------------------------------------------------------------------------
class LazyTab(QWidget):
    """タブが初めて選択された時点でコンテンツを生成する。"""
    def __init__(self, builder):
        super().__init__()
        self._builder = builder
        self._built = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._lay = lay
        loading = QLabel("　　読み込み中…")
        loading.setAlignment(Qt.AlignCenter)
        loading.setStyleSheet("color:#9aa0a6;")
        self._loading = loading
        lay.addWidget(loading)

    def build_now(self):
        if self._built:
            return
        self._built = True
        self._loading.hide()
        widget = self._builder()
        self._lay.addWidget(widget)


# ---------------------------------------------------------------------------
# メインダイアログ
# ---------------------------------------------------------------------------
class SettingsDialog(QDialog):
    def __init__(self, parent, title, schema, model):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 760)
        self.schema = schema
        self.model = model
        self.widgets: dict[str, tuple] = {}     # key -> (field, widget)
        self._field_rows: dict[str, QWidget] = {}    # key -> row container (for hide/show)
        self._section_widgets: list[tuple[QPushButton, QWidget]] = []  # (toggle_btn, container)
        self.default_decor: dict = {}
        self.fil_table = None
        self.fil_forms: list = []
        self.gcode_edits: dict = {}
        self._vis_level = "all"     # basic | advanced | expert | all
        self._search_active = False  # search triggered build of all tabs
        self._build()
        self.setStyleSheet(DIALOG_QSS)

    # ------------------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # 検索バー + 可視性フィルター
        top = QHBoxLayout()
        self._search_box = QLineEdit()
        self._search_box.setObjectName("search")
        self._search_box.setPlaceholderText(
            "🔍 検索 (ラベル / native_key / canonical_key)…")
        self._search_box.textChanged.connect(self._on_search_changed)
        top.addWidget(self._search_box, 1)

        # 可視性フィルターボタン
        top.addSpacing(10)
        vis_lbl = QLabel("表示:")
        vis_lbl.setStyleSheet("color:#9aa0a6; font-size:12px;")
        top.addWidget(vis_lbl)
        self._vis_btns: dict[str, QPushButton] = {}
        for level, label in [("all", "全て"), ("basic", "基本"),
                              ("advanced", "詳細"), ("expert", "上級")]:
            btn = QPushButton(label)
            btn.setObjectName("vis_btn")
            btn.setCheckable(True)
            btn.setChecked(level == "all")
            btn.clicked.connect(lambda _, lv=level: self._set_vis_level(lv))
            top.addWidget(btn)
            self._vis_btns[level] = btn
        root.addLayout(top)

        # タブウィジェット
        self._tabs = QTabWidget()
        root.addWidget(self._tabs, 1)
        self._tab_names: list[str] = []

        for st in self.schema:
            name = st.title
            self._tab_names.append(name)
            if st.special == "filaments":
                widget = self._filament_tab()
                self._tabs.addTab(widget, name)
            elif st.special == "per_filament":
                for i, fl in enumerate(self.model.filaments):
                    w = self._per_filament_tab(i, fl)
                    self._tabs.addTab(w, f"フィラメント T{i}")
                    self._tab_names.append(f"フィラメント T{i}")
            elif st.special == "gcode":
                widget = self._gcode_tab()
                self._tabs.addTab(widget, name)
            else:
                lazy = LazyTab(lambda st=st: self._form_tab(st))
                self._tabs.addTab(lazy, name)

        self._tabs.currentChanged.connect(self._on_tab_changed)
        self._on_tab_changed(0)  # 最初のタブを即ビルド

        # 凡例
        legend = QLabel(
            '<span style="color:#00c2a8;">■ 復元</span> G-codeから取得 　'
            '<span style="color:#f0b13c;">■ 既定値</span> 取得できず既定値 　'
            '<span style="color:#f0b13c;">■ 推定</span> ツールパスから推定 　'
            '<span style="color:#909090;">■ 不明</span> 信頼性不明 　'
            '<span style="color:#cc4444;">■ 未対応</span> 未対応')
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
    def _on_tab_changed(self, idx: int):
        tab = self._tabs.widget(idx)
        if isinstance(tab, LazyTab):
            tab.build_now()

    # ------------------------------------------------------------------
    def _set_vis_level(self, level: str):
        self._vis_level = level
        for lv, btn in self._vis_btns.items():
            btn.setChecked(lv == level)
        self._update_field_visibility()

    def _on_search_changed(self, text: str):
        if text and not self._search_active:
            self._search_active = True
            # 全タブを即ビルド (cross-tab search)
            for i in range(self._tabs.count()):
                tab = self._tabs.widget(i)
                if isinstance(tab, LazyTab):
                    tab.build_now()
        self._update_field_visibility()

    def _update_field_visibility(self):
        search = self._search_box.text().strip().lower()
        vis_levels = {
            "basic":    {"basic"},
            "advanced": {"basic", "advanced"},
            "expert":   {"basic", "advanced", "expert"},
            "all":      {"basic", "advanced", "expert"},
        }
        allowed = vis_levels.get(self._vis_level, {"basic", "advanced", "expert"})

        for key, (f, _w) in self.widgets.items():
            row = self._field_rows.get(key)
            if row is None:
                continue
            if f.visible_if and not all(self._condition_met(dep) for dep in f.visible_if):
                row.setVisible(False)
                continue
            # 可視性レベルフィルター
            if f.visibility not in allowed:
                row.setVisible(False)
                continue
            # 検索フィルター
            if search:
                tokens = " ".join(filter(None, [
                    f.label.lower(),
                    (f.native_key or "").lower(),
                    f.canonical_key.lower(),
                    f.key.lower(),
                    f.description.lower(),
                ]))
                row.setVisible(search in tokens)
            else:
                row.setVisible(True)
            if not row.isHidden():
                row.setEnabled(all(self._condition_met(dep) for dep in f.enabled_if))

    def _condition_met(self, key: str) -> bool:
        item = self.widgets.get(key)
        if item is None:
            value = self.model.values.get(key)
        else:
            _f, widget = item
            value = self._widget_value(widget)
        if isinstance(value, str):
            return value.strip().lower() not in ("", "0", "false", "no", "off",
                                                 "disabled", "unknown", "none")
        return bool(value)

    @staticmethod
    def _widget_value(widget):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QPlainTextEdit):
            return widget.toPlainText()
        if isinstance(widget, QLineEdit):
            return widget.text()
        return None

    # ------------------------------------------------------------------
    def _form_tab(self, subtab) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        v = QVBoxLayout(inner)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(4)

        for sec_title, fields in subtab.sections:
            # 折りたたみ可能なセクションヘッダー
            toggle_btn = QPushButton("▼  " + sec_title)
            toggle_btn.setObjectName("sec_toggle")
            toggle_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            v.addWidget(toggle_btn)

            hr = QFrame(); hr.setObjectName("hr"); v.addWidget(hr)

            container = QWidget()
            form = QFormLayout(container)
            form.setContentsMargins(6, 4, 6, 10)
            form.setSpacing(8)

            for f in fields:
                w = self._make_widget(f)
                self.widgets[f.key] = (f, w)

                row_widget = QWidget()
                row = QHBoxLayout(row_widget)
                row.setContentsMargins(0, 0, 0, 0)
                row.addWidget(w)

                if f.unit:
                    u = QLabel(f.unit)
                    u.setStyleSheet("color:#8a9099;")
                    row.addWidget(u)

                # 出所バッジ
                prov = self.model.provenance.get(f.key)
                cur_val = self.model.values.get(f.key)
                badge_chip = None

                if prov in PROV_BADGE and prov not in ("recovered", "edited", "confirmed"):
                    badge_lbl, bg, fg = PROV_BADGE[prov]
                    # default かつ値が None/"" の場合はバッジ不要
                    if prov == "default" and cur_val in (None, ""):
                        pass
                    else:
                        badge_chip = QLabel(badge_lbl)
                        badge_chip.setStyleSheet(
                            f"color:{fg}; background:{bg}; font-size:11px; font-weight:bold;"
                            f" border:1px solid {fg}; border-radius:3px; padding:0 5px;")
                        row.addWidget(badge_chip)
                        if prov == "default":
                            w.setStyleSheet(self._amber_style(w))

                # 推定バッジ (low_conf または prov=="estimated")
                if f.low_conf or prov == "estimated":
                    est_chip = QLabel("推定")
                    est_chip.setStyleSheet(
                        "color:#f0b13c; font-size:10px; border:1px solid #c08a1e;"
                        " border-radius:3px; padding:0 4px;")
                    row.addWidget(est_chip)

                # ツールチップ (description)
                if f.description:
                    w.setToolTip(f.description)

                row.addStretch(1)

                # ラベル (visibility に応じて色付け)
                vis_color = {"basic": "#dfe1e5", "advanced": "#b0b8c0", "expert": "#8090a0"}
                label_text = f.label
                lw = QLabel(label_text)
                lw.setStyleSheet(f"color:{vis_color.get(f.visibility, '#dfe1e5')};")
                if f.description:
                    lw.setToolTip(f.description)

                # 既定値の確定ボタン
                if prov == "default" and cur_val not in (None, ""):
                    confirm_btn = QToolButton()
                    confirm_btn.setText("✓ 確定")
                    confirm_btn.setToolTip("この項目を既定値のまま確定(ハイライト解除)")
                    confirm_btn.setStyleSheet(
                        "QToolButton{color:#9aa0a6; border:1px solid #4a4d51;"
                        " border-radius:3px; padding:1px 6px;}"
                        "QToolButton:hover{color:#00c2a8; border-color:#00a98f;}")
                    confirm_btn.clicked.connect(lambda _=False, k=f.key: self._confirm_field(k))
                    row.addWidget(confirm_btn)
                    self.default_decor[f.key] = {
                        "w": w, "label": lw, "chip": badge_chip, "btn": confirm_btn
                    }
                    self._connect_edit(f, w)

                form.addRow(lw, row_widget)
                self._field_rows[f.key] = row_widget

            v.addWidget(container)
            self._section_widgets.append((toggle_btn, container))
            toggle_btn.clicked.connect(
                lambda _=False, c=container, b=toggle_btn: self._toggle_section(c, b))

        v.addStretch(1)
        scroll.setWidget(inner)
        return scroll

    @staticmethod
    def _toggle_section(container: QWidget, btn: QPushButton):
        visible = not container.isVisible()
        container.setVisible(visible)
        text = btn.text()
        if visible:
            btn.setText(text.replace("▶", "▼"))
        else:
            btn.setText(text.replace("▼", "▶"))

    @staticmethod
    def _amber_style(_w):
        return "background:#3b3320; border:1px solid #c08a1e; border-radius:4px; padding:3px;"

    def _connect_edit(self, f, w):
        cb = lambda *a, k=f.key: self._field_edited(k)
        if isinstance(w, QCheckBox):
            w.toggled.connect(cb)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(cb)
        elif isinstance(w, QSpinBox):
            w.valueChanged.connect(cb)
        elif isinstance(w, QPlainTextEdit):
            w.textChanged.connect(cb)
        else:
            w.textEdited.connect(cb)

    def _field_edited(self, key):
        self.model.provenance[key] = "edited"
        self._clear_decor(key)
        self._update_field_visibility()

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
        if d.get("chip"):
            d["chip"].hide()
        if d.get("btn"):
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
        if f.kind == "int":
            w = QSpinBox()
            w.setRange(-999999, 999999)
            w.setMaximumWidth(130)
            try:
                w.setValue(int(cur) if cur is not None else 0)
            except (TypeError, ValueError):
                w.setValue(0)
            return w
        if f.kind == "gcode":
            w = QPlainTextEdit()
            w.setMinimumHeight(82)
            w.setStyleSheet("font-family:Consolas,monospace; font-size:12px;")
            w.setPlainText(self._fmt(cur))
            return w
        # num, text, color, gcode → QLineEdit
        w = QLineEdit()
        if f.kind in ("num",):
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
            return str(int(v)) if v == int(v) else str(round(v, 4))
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
        for key, (f, w) in self.widgets.items():
            old = self.model.values.get(key)
            if isinstance(w, QCheckBox):
                new = w.isChecked()
            elif isinstance(w, QComboBox):
                new = w.currentText()
            elif isinstance(w, QSpinBox):
                new = w.value()
            elif isinstance(w, QPlainTextEdit):
                new = w.toPlainText()
            else:
                txt = w.text().strip()
                if txt == "":
                    new = None
                elif f.kind in ("num",):
                    try:
                        new = float(txt)
                    except ValueError:
                        new = txt
                elif f.kind == "int":
                    try:
                        new = int(txt)
                    except ValueError:
                        new = txt
                else:
                    new = txt
            self.model.values[key] = new
            if new != old:
                self.model.provenance[key] = "edited"

        if confirm_defaults:
            for key in self.widgets:
                if self.model.provenance.get(key) == "default":
                    self.model.provenance[key] = "confirmed"

        if self.fil_table is not None:
            fils = []
            for r in range(self.fil_table.rowCount()):
                def cell(c, _r=r):
                    it = self.fil_table.item(_r, c)
                    t = it.text().strip() if it else ""
                    try:
                        return float(t) if t else None
                    except ValueError:
                        return None
                fils.append({"tool": r, "nozzle_temp": cell(1),
                             "bed_temp": cell(2), "retract_length": cell(3)})
            self.model.filaments = fils

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

        if self.gcode_edits:
            for key, ed in self.gcode_edits.items():
                self.model.gcode_blocks[key] = ed.toPlainText()

        self.accept()
