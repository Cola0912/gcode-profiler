# -*- coding: utf-8 -*-
"""Native profile importers (Phase 6).

Public API
----------
    detect(path)                      -> DetectionResult dict
    import_profile(path)              -> canonical profile (configured layer)
    import_and_merge(path, gcode)     -> canonical profile (configured + observed)

All conversion goes through canonical keys. Imported profiles are untrusted:
archives are opened through the security-bounded reader, and unknown native
fields are preserved (never silently dropped) in `canonical.unmapped`.
"""
from __future__ import annotations

import os
import zipfile

from . import detection as _detection
from . import adapters as _adapters
from . import security as _security
from .repository import Repository
from . import inheritance as _inheritance
from . import merge as _merge
from ..canonical import model as _m
from ..canonical import adapter as _legacy_adapter

# config entry names to look for inside archives (.3mf / .zip), most specific first
_ARCHIVE_CANDIDATES = (
    "Metadata/project_settings.config",
    "project_settings.config",
)
_ARCHIVE_EXTS = (".json", ".ini", ".config", ".cfg", ".fff")


class ImportError_(Exception):
    """Raised when a profile cannot be imported (unknown slicer, bad content)."""


def detect(path):
    """Return a detection result dict (without the cached text)."""
    res = _read_and_detect(path)
    res.pop("_text", None)
    res.pop("_source_path", None)
    return res


def import_profile(path):
    """Parse, resolve inheritance, and map a native profile to a canonical
    profile (configured layer)."""
    det = _read_and_detect(path)
    slicer = det.get("slicer")
    adapter = _adapters.for_slicer(slicer)
    if adapter is None:
        raise ImportError_(f"未対応または未判定のスライサー: {slicer}")

    text = det["_text"]
    real_path = det.get("_source_path", path)
    native = adapter.parse(text, real_path)

    # Build a repository from bundle members and sibling files for inheritance.
    repo = Repository()
    for sub in native.sub_profiles:
        repo.add(sub)
    repo.add(native)
    _index_siblings(repo, real_path, adapter)

    version = det.get("version")

    if native.profile_kind == "bundle":
        canonical = _m.empty_profile()
        canonical["source"] = {"source_slicer": slicer, "source_version": version,
                               "analysis_mode": "native_profile", "confidence": 0.9}
        kinds = []
        for sub in native.sub_profiles:
            resolved = _inheritance.resolve(sub, repo)
            part = adapter.to_canonical(resolved, version)
            _union(canonical, part)
            kinds.append(sub.profile_kind)
        canonical["metadata"]["bundle_kinds"] = kinds
        canonical["detection"] = _public(det)
        return canonical

    resolved = _inheritance.resolve(native, repo)
    canonical = adapter.to_canonical(resolved, version)
    canonical["detection"] = _public(det)
    return canonical


def import_and_merge(path, gcode_result):
    """Import a native profile and merge it with a G-code analysis result.
    `configured` (profile) + `observed`/`emitted` (G-code), conflicts recorded."""
    configured = import_profile(path)
    observed = _legacy_adapter.legacy_to_canonical(gcode_result or {})
    merged = _merge.merge(configured, observed)
    merged["detection"] = configured.get("detection")
    return merged


# ---------------------------------------------------------------------------
def _read_and_detect(path):
    """Detect from a file or from a config entry inside an archive."""
    if zipfile.is_zipfile(path):
        text, entry = _read_archive_config(path)
        res = _detection.detect_text(text, os.path.splitext(entry)[1])
        res["_text"] = text
        res["_source_path"] = f"{path}!{entry}"
        res["container_type"] = "archive"
        return res
    res = _detection.detect(path)          # sets _text
    res["_source_path"] = path
    return res


def _read_archive_config(path):
    """Return (text, entry_name) for the settings config inside an archive.
    Uses the security-bounded member iterator to reject malicious archives."""
    with zipfile.ZipFile(path) as zf:
        safe = list(_security.safe_zip_members(zf))   # raises UnsafeArchive
        for cand in _ARCHIVE_CANDIDATES:
            for name in safe:
                if name.replace("\\", "/") == cand:
                    return zf.read(name).decode("utf-8", "replace"), name
        for name in safe:
            if name.lower().endswith(_ARCHIVE_EXTS):
                return zf.read(name).decode("utf-8", "replace"), name
    raise ImportError_("アーカイブ内に設定ファイルが見つかりません")


def _index_siblings(repo, real_path, adapter):
    """Add sibling files in the same directory as parent-preset candidates."""
    if "!" in real_path:            # archive entry — no filesystem siblings
        return
    directory = os.path.dirname(real_path)
    if not directory or not os.path.isdir(directory):
        return

    def parse_fn(p):
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                return adapter.parse(f.read(), p)
        except Exception:
            return None

    for prof in Repository.from_directory(directory, parse_fn).\
            _by_name.values():          # noqa: SLF001 (intentional reuse)
        repo.add(prof)


def _union(dst, src):
    """Deep-union canonical value nodes from src into dst (src wins on leaves)."""
    for section in ("printer", "material", "process", "unmapped"):
        _union_node(dst.setdefault(section, {}), src.get(section, {}))
    # carry metadata bits
    for k, v in src.get("metadata", {}).items():
        dst.setdefault("metadata", {}).setdefault(k, v)


def _union_node(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and "effective" not in v:
            _union_node(dst.setdefault(k, {}), v)
        else:
            dst[k] = v


def _public(det):
    return {k: v for k, v in det.items() if not k.startswith("_")}
