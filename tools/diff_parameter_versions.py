# -*- coding: utf-8 -*-
"""Diff two generated parameter catalogs by native_key."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old_catalog")
    ap.add_argument("new_catalog")
    ns = ap.parse_args()
    old = _load(ns.old_catalog)
    new = _load(ns.new_catalog)
    old_keys, new_keys = set(old), set(new)
    changed = sorted(k for k in old_keys & new_keys if _meaningful(old[k]) != _meaningful(new[k]))
    report = {
        "old": ns.old_catalog,
        "new": ns.new_catalog,
        "added": sorted(new_keys - old_keys),
        "removed": sorted(old_keys - new_keys),
        "changed": changed,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def _load(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {p["native_key"]: p for p in data.get("parameters", [])}


def _meaningful(p):
    return {k: p.get(k) for k in (
        "profile_kind", "canonical_key", "native_type", "unit", "value_mode",
        "default", "minimum", "maximum", "enum_values", "deprecated",
        "replacement_key", "visibility",
    )}


if __name__ == "__main__":
    main()

