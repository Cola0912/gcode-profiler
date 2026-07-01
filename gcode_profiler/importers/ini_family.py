# -*- coding: utf-8 -*-
"""Shared INI/CFG parser for the Prusa/SuperSlicer family and Cura containers.

Handles two shapes:
  * flat `key = value` (PrusaSlicer/SuperSlicer single-config export)
  * sectioned `[print:Name] ... [filament:Name] ...` (config bundle) or Cura
    `[general]/[metadata]/[values]` instance containers.

Structure only; semantics live in the adapter layer.
"""
from __future__ import annotations

import os
import re

from .base import NativeProfile, make_value

_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KV_RE = re.compile(r"^\s*([^=;#]+?)\s*=\s*(.*)$")

# INI bundle section prefix -> profile_kind
_KIND_FROM_SECTION = {"print": "process", "filament": "filament",
                      "printer": "printer", "printer_model": "printer"}

# meta keys that describe the preset, not printable settings
_META_KEYS = {"inherits", "name", "type", "definition", "setting_version"}


def parse_ini(text, path, slicer):
    """Parse INI/CFG text. Returns a single NativeProfile, or a bundle
    NativeProfile whose sub_profiles hold each section when sections are present."""
    lines = text.splitlines()
    sections = _split_sections(lines)

    if not sections or (len(sections) == 1 and sections[0][0] is None):
        # flat config (Prusa/SuperSlicer single export)
        _hdr, body = sections[0] if sections else (None, lines)
        return _profile_from_lines(body, path, slicer, kind="process",
                                   name=os.path.basename(path))

    # Cura instance container: [general]/[metadata]/[values]
    header_names = {(_section_name(h) or "").lower() for h, _ in sections}
    if header_names & {"general", "metadata", "values"}:
        return _parse_cura(sections, path, slicer)

    # Prusa/SuperSlicer config bundle: one sub-profile per section
    bundle = NativeProfile(source_path=path, slicer=slicer,
                           profile_kind="bundle",
                           display_name=os.path.basename(path))
    for header, body in sections:
        if header is None:
            continue
        prefix, _, sect_name = header.partition(":")
        kind = _KIND_FROM_SECTION.get(prefix.strip().lower(), "unknown")
        sub = _profile_from_lines(body, path, slicer, kind=kind,
                                  name=sect_name.strip() or prefix.strip())
        bundle.sub_profiles.append(sub)
    return bundle


# ---------------------------------------------------------------------------
def _split_sections(lines):
    """Return [(header_or_None, [body_lines])]. Leading body before any
    section header gets header None."""
    sections = []
    header = None
    body = []
    started = False
    for ln in lines:
        m = _SECTION_RE.match(ln)
        if m:
            if started or body:
                sections.append((header, body))
            header = m.group(1).strip()
            body = []
            started = True
        else:
            body.append(ln)
    if started or body:
        sections.append((header, body))
    return sections


def _section_name(header):
    return header if header is not None else None


def _profile_from_lines(lines, path, slicer, kind, name):
    prof = NativeProfile(source_path=path, slicer=slicer, profile_kind=kind,
                         display_name=name)
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            if s:
                prof.comments.append(s)
            continue
        m = _KV_RE.match(ln)
        if not m:
            continue
        key = m.group(1).strip()
        val = m.group(2).strip()
        if key == "inherits" and val:
            prof.parent_refs = [p.strip() for p in val.split(";") if p.strip()]
            continue
        if key == "name" and val and prof.display_name == name:
            prof.display_name = val
            continue
        if key in _META_KEYS:
            continue
        prof.raw_fields[key] = make_value(key, val)
        prof.ordering.append(key)
    return prof


def _parse_cura(sections, path, slicer):
    prof = NativeProfile(source_path=path, slicer=slicer, profile_kind="unknown",
                         display_name=os.path.basename(path))
    for header, body in sections:
        name = (header or "").lower()
        kv = _kv_dict(body)
        if name == "general":
            prof.display_name = kv.get("name", prof.display_name)
            if kv.get("definition"):
                prof.parent_refs = [kv["definition"]]
        elif name == "metadata":
            qtype = kv.get("type", "")
            if "quality" in qtype:
                prof.profile_kind = "process"
            elif "material" in qtype:
                prof.profile_kind = "filament"
            prof.version = kv.get("setting_version", prof.version)
        elif name == "values":
            for k, v in kv.items():
                prof.raw_fields[k] = make_value(k, v)
                prof.ordering.append(k)
    return prof


def _kv_dict(lines):
    out = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(";"):
            continue
        m = _KV_RE.match(ln)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out
