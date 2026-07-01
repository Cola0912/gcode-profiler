# -*- coding: utf-8 -*-
"""Safe handling of untrusted imported profiles / archives (Phase 6)."""
from __future__ import annotations

import os
import zipfile

MAX_ENTRIES = 2000
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024


class UnsafeArchive(Exception):
    pass


def _is_within(base, target):
    base = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base, target))
    return os.path.commonpath([base, target]) == base


def safe_zip_members(zf: zipfile.ZipFile):
    """Yield zip member names that are safe (no traversal, bounded). Raises on abuse."""
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise UnsafeArchive("too many archive entries")
    total = 0
    for info in infos:
        name = info.filename
        if name.endswith("/"):
            continue
        if os.path.isabs(name) or ".." in name.replace("\\", "/").split("/"):
            raise UnsafeArchive(f"path traversal entry: {name}")
        if not _is_within("safe_root", name):
            raise UnsafeArchive(f"escapes root: {name}")
        if info.file_size > MAX_ENTRY_BYTES:
            raise UnsafeArchive(f"entry too large: {name}")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise UnsafeArchive("archive too large")
        yield name
