# -*- coding: utf-8 -*-
"""
Migration helpers (Phase 1).

Loads either a legacy analyzer result dict or an already-canonical profile and
returns a current-schema canonical profile. Old keys keep loading.
"""
from __future__ import annotations

from . import model as m
from .adapter import legacy_to_canonical, LEGACY_MAP

# legacy keys that have a canonical owner are deprecated for direct reads
DEPRECATED_LEGACY_KEYS = set(LEGACY_MAP.keys())


def is_canonical(obj):
    return isinstance(obj, dict) and "schema_version" in obj


def migrate(obj):
    """Return a canonical profile at the current SCHEMA_VERSION.
    Accepts a legacy result dict or a canonical profile of any known version."""
    if not isinstance(obj, dict):
        raise TypeError("migrate expects a dict (legacy result or canonical profile)")
    if not is_canonical(obj):
        return legacy_to_canonical(obj)
    ver = obj.get("schema_version")
    if ver == m.SCHEMA_VERSION:
        return obj
    return _migrate_version(obj, ver)


def _migrate_version(prof, from_version):
    """Forward-migrate an older canonical profile. Currently 1.0 is the only
    version; unknown older versions are passed through with a warning marker."""
    prof = dict(prof)
    prof["schema_version"] = m.SCHEMA_VERSION
    prof.setdefault("metadata", {})["migrated_from"] = from_version
    return prof


def deprecated_keys_present(legacy_result):
    """Report which deprecated legacy keys a result still carries (for diagnostics)."""
    out = []
    for key in DEPRECATED_LEGACY_KEYS:
        sec, fld = key.split(".", 1)
        if legacy_result.get(sec, {}).get(fld) is not None:
            out.append(key)
    return sorted(out)
