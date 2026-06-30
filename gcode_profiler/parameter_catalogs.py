# -*- coding: utf-8 -*-
"""Versioned slicer parameter catalog loading and filtering."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


CATALOG_SCHEMA_VERSION = "1.0"

_VIS_ORDER = {"basic": 0, "advanced": 1, "expert": 2, "hidden": 3}


def catalog_root():
    return Path(__file__).resolve().parent.parent / "parameter_catalogs"


def list_catalogs():
    root = catalog_root()
    out = {}
    if not root.exists():
        return out
    for slicer_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        versions = []
        for ver_dir in sorted(p for p in slicer_dir.iterdir() if p.is_dir()):
            if (ver_dir / "parameters.json").exists():
                versions.append(ver_dir.name)
        if versions:
            out[slicer_dir.name] = versions
    return out


@lru_cache(maxsize=32)
def load_catalog(slicer, version):
    path = catalog_root() / slicer / version / "parameters.json"
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    params = data.get("parameters", [])
    return {
        "schema_version": data.get("schema_version"),
        "slicer": data.get("slicer"),
        "version": data.get("version"),
        "source": data.get("source", {}),
        "generated_at": data.get("generated_at"),
        "parameters": params,
        "coverage": data.get("coverage", coverage_report(params)),
    }


def filter_parameters(catalog, profile_kind=None, visibility="expert", query=None):
    """Return parameters matching profile kind, visibility, and search query."""
    max_vis = _VIS_ORDER.get(visibility, 2)
    q = (query or "").strip().lower()
    out = []
    for p in catalog.get("parameters", []):
        if profile_kind and p.get("profile_kind") != profile_kind:
            continue
        if _VIS_ORDER.get(p.get("visibility", "advanced"), 1) > max_vis:
            continue
        if q:
            hay = " ".join(str(p.get(k, "")) for k in (
                "native_key", "canonical_key", "label", "label_ja",
                "category", "section", "description",
            )).lower()
            if q not in hay:
                continue
        out.append(p)
    return sorted(out, key=lambda p: (p.get("profile_kind", ""), p.get("category", ""),
                                      p.get("section", ""), p.get("order", 0),
                                      p.get("native_key", "")))


def group_for_ui(parameters):
    """Build a lightweight tab/section tree for lazy UI creation."""
    tree = []
    idx = {}
    for p in parameters:
        tab = p.get("category") or p.get("profile_kind") or "Other"
        sec = p.get("section") or "General"
        tab_node = idx.get(tab)
        if tab_node is None:
            tab_node = {"title": tab, "sections": [], "_sections": {}}
            idx[tab] = tab_node
            tree.append(tab_node)
        sec_node = tab_node["_sections"].get(sec)
        if sec_node is None:
            sec_node = {"title": sec, "parameters": []}
            tab_node["_sections"][sec] = sec_node
            tab_node["sections"].append(sec_node)
        sec_node["parameters"].append(p)
    for tab_node in tree:
        tab_node.pop("_sections", None)
    return tree


def coverage_report(parameters, discovered_count=None):
    total = len(parameters)
    discovered = discovered_count if discovered_count is not None else total
    mapped = sum(1 for p in parameters if p.get("canonical_key"))
    deprecated = sum(1 for p in parameters if p.get("deprecated"))
    verified = sum(1 for p in parameters if p.get("verification_status") == "verified")
    partially_verified = sum(1 for p in parameters if p.get("verification_status") == "partially_verified")
    unverified = sum(1 for p in parameters if p.get("verification_status") == "unverified")
    editable = sum(1 for p in parameters if not p.get("deprecated") and p.get("visibility") != "hidden")
    exportable = sum(1 for p in parameters if p.get("exportable", True))
    importable = sum(1 for p in parameters if p.get("importable", True))
    def is_recoverable(p):
        caps = p.get("recovery_capability", {})
        return any(caps.get(k) for k in (
            "explicit_metadata_recoverable", "runtime_command_recoverable",
            "geometry_recoverable", "statistically_estimable",
        ))
    recoverable = sum(1 for p in parameters if is_recoverable(p))
    native_only = sum(1 for p in parameters if p.get("canonical_key") is None
                      and p.get("mapping_status") == "native_only")
    return {
        "native_parameters_found": discovered,
        "catalog_parameters": total,
        "mapped_to_canonical": mapped,
        "native_only": native_only,
        "deprecated": deprecated,
        "unverified": unverified,
        "coverage_percent": round((total / discovered * 100.0), 2) if discovered else 0.0,
        "discovered": discovered,
        "verified": verified,
        "partially_verified": partially_verified,
        "mapped": mapped,
        "editable": editable,
        "exportable": exportable,
        "importable": importable,
        "recoverable_from_gcode": recoverable,
    }
