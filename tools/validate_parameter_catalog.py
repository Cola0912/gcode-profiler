# -*- coding: utf-8 -*-
"""Validate generated parameter catalogs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gcode_profiler.parameter_catalogs import CATALOG_SCHEMA_VERSION  # noqa


VALID_TYPES = {"float", "int", "bool", "string", "enum", "array", "percentage", "expression"}
VALID_MODES = {"absolute", "percentage", "ratio", "count", "enum", "expression", "unknown"}
VALID_VIS = {"basic", "advanced", "expert", "hidden"}
VALID_VERIFY = {"verified", "partially_verified", "unverified"}
VALID_MAPPING = {"mapped", "native_only", "deprecated", "unsupported"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog")
    ns = ap.parse_args()
    errors = validate(Path(ns.catalog))
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        raise SystemExit(1)
    print(f"OK: {ns.catalog}")


def validate(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    if data.get("schema_version") != CATALOG_SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    params = data.get("parameters")
    if not isinstance(params, list):
        return ["parameters must be a list"]
    seen = set()
    for i, p in enumerate(params):
        key = p.get("native_key")
        if not key:
            errors.append(f"[{i}] native_key missing")
            continue
        if key in seen:
            errors.append(f"duplicate native_key: {key}")
        seen.add(key)
        _check_enum(errors, p, key, "native_type", VALID_TYPES)
        _check_enum(errors, p, key, "value_mode", VALID_MODES)
        _check_enum(errors, p, key, "visibility", VALID_VIS)
        _check_enum(errors, p, key, "verification_status", VALID_VERIFY)
        ms = p.get("mapping_status")
        if ms not in VALID_MAPPING:
            errors.append(f"{key}: invalid mapping_status {ms!r}")
        if ms == "mapped" and not p.get("canonical_key"):
            errors.append(f"{key}: mapped requires canonical_key")
        if ms == "native_only" and p.get("canonical_key") is not None:
            errors.append(f"{key}: native_only must have canonical_key null")
        for dep_key in ("enabled_if", "visible_if", "conflicts_with", "requires"):
            if not isinstance(p.get(dep_key, []), list):
                errors.append(f"{key}: {dep_key} must be a list")
        src = p.get("source_reference", {})
        if not src.get("repository") or not src.get("file"):
            errors.append(f"{key}: source_reference incomplete")
    return errors


def _check_enum(errors, p, key, field, valid):
    if p.get(field) not in valid:
        errors.append(f"{key}: invalid {field} {p.get(field)!r}")


if __name__ == "__main__":
    main()

