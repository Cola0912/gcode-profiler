# -*- coding: utf-8 -*-
"""Extract Bambu Studio parameter catalog from official source definitions.

Usage:
  python tools/extract_bambu_parameters.py --source .catalog_sources/BambuStudio-v02.08.00.50 --version 2.8
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gcode_profiler.parameter_catalogs import CATALOG_SCHEMA_VERSION, coverage_report  # noqa
from tools import extract_orca_parameters as common  # noqa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Bambu Studio source checkout")
    ap.add_argument("--version", default="2.8")
    ap.add_argument("--tag", default="v02.08.00.50")
    ap.add_argument("--output", default=None)
    ns = ap.parse_args()

    source = Path(ns.source)
    cpp = source / "src" / "libslic3r" / "PrintConfig.cpp"
    if not cpp.exists():
        raise SystemExit(f"PrintConfig.cpp not found: {cpp}")

    text = cpp.read_text(encoding="utf-8", errors="replace")
    fff_text = text
    sla_pos = text.find("void PrintConfigDef::init_sla_params")
    if sla_pos > 0:
        fff_text = text[:sla_pos]
    extruder_keys = common._option_key_set(text, "m_extruder_option_keys")
    filament_keys = common._option_key_set(text, "m_filament_option_keys")

    params = []
    for order, block in enumerate(common._option_blocks(fff_text)):
        p = common._parse_block(block, order, cpp, ns.tag, extruder_keys, filament_keys)
        if not p:
            continue
        p["slicer"] = "Bambu Studio"
        p["source_reference"]["repository"] = "bambulab/BambuStudio"
        p["source_reference"]["tag"] = ns.tag
        # Bambu shares a Slic3r-family option model, but keep verification
        # conservative until a Bambu-specific UI grouping pass is added.
        if p.get("verification_status") == "partially_verified":
            p["verification_status"] = "partially_verified"
        params.append(p)
    params = common._dedupe(params)

    data = {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "slicer": "Bambu Studio",
        "version": ns.version,
        "source": {
            "official_repository": "https://github.com/bambulab/BambuStudio",
            "tag": ns.tag,
            "commit": _commit(source),
            "files": ["src/libslic3r/PrintConfig.cpp"],
            "date_checked": str(date.today()),
        },
        "generated_at": str(date.today()),
        "parameters": params,
        "coverage": coverage_report(params),
    }
    out = Path(ns.output) if ns.output else Path("parameter_catalogs") / "bambu" / ns.version / "parameters.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out.parent / "coverage.json").write_text(
        json.dumps(data["coverage"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out} ({len(params)} parameters)")
    print(json.dumps(data["coverage"], ensure_ascii=False, indent=2))


def _commit(source):
    head = source / ".git" / "HEAD"
    if not head.exists():
        return None
    txt = head.read_text(encoding="utf-8", errors="replace").strip()
    if len(txt) == 40:
        return txt
    return None


if __name__ == "__main__":
    main()

