# -*- coding: utf-8 -*-
"""
G-code コンテナ読み込み
======================
通常の .gcode テキストに加え、BambuStudio / OrcaSlicer がエクスポートする
.3mf (ZIP コンテナ) に対応する。3mf 内には:
  - Metadata/plate_1.gcode            : 実 G-code
  - Metadata/project_settings.config  : 全設定の JSON (高精度復元に利用)
が含まれる。
"""
from __future__ import annotations

import json
import os
import zipfile


def _file_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            yield line


def _find_member(names, suffix):
    # Metadata/ 配下を優先し、無ければ全体から探す
    cands = [n for n in names if n.lower().endswith(suffix)]
    if not cands:
        return None
    cands.sort(key=lambda n: (0 if "metadata/" in n.lower() else 1, len(n)))
    return cands[0]


def open_gcode(path: str) -> dict:
    """G-code ソースを開いて {lines, bambu_config, source_name} を返す。"""
    is_zip = path.lower().endswith((".3mf", ".zip")) or zipfile.is_zipfile(path)
    if not is_zip:
        return {"lines": _file_lines(path), "bambu_config": None, "source_name": None}

    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        # 実 G-code を取り出す (最大の .gcode を採用)
        gcode_members = [n for n in names if n.lower().endswith(".gcode")]
        if not gcode_members:
            raise ValueError("3mf 内に G-code が見つかりません(モデルのみの3mfの可能性があります)。"
                             " スライス済みの 3mf を指定してください。")
        gcode_members.sort(key=lambda n: zf.getinfo(n).file_size, reverse=True)
        text = zf.read(gcode_members[0]).decode("utf-8", errors="replace")
        lines = text.splitlines()

        # 埋め込み設定 JSON (project_settings.config)
        bambu_config = None
        cfg_member = _find_member(names, "project_settings.config")
        if cfg_member is None:
            cfg_member = _find_member(names, ".config")
        if cfg_member:
            try:
                raw = zf.read(cfg_member).decode("utf-8", errors="replace")
                bambu_config = json.loads(raw)
            except (ValueError, json.JSONDecodeError):
                bambu_config = None

    return {"lines": lines, "bambu_config": bambu_config, "source_name": "BambuStudio/OrcaSlicer(3mf)"}
