# -*- coding: utf-8 -*-
"""Simplify3D FFF (XML) parser (Phase 6).

Uses defusedxml when available; falls back to the stdlib parser with entity
resolution disabled paths avoided (imported profiles are untrusted).
"""
from __future__ import annotations

import os

try:
    from defusedxml.ElementTree import fromstring as _xml_fromstring  # type: ignore
except Exception:  # pragma: no cover - defusedxml is optional
    from xml.etree.ElementTree import fromstring as _xml_fromstring

from .base import NativeProfile, make_value


def parse_xml(text, path, slicer):
    """Parse a Simplify3D <profile> document into a NativeProfile."""
    root = _xml_fromstring(text)
    profile_el = root if root.tag == "profile" else root.find(".//profile")
    if profile_el is None:
        profile_el = root

    prof = NativeProfile(
        source_path=path,
        slicer=slicer,
        version=profile_el.get("version"),
        profile_kind="process",
        display_name=profile_el.get("name") or os.path.basename(path),
    )

    # Attributes on <profile> itself are settings too (name/version excluded).
    for attr, val in profile_el.attrib.items():
        if attr in ("name", "version"):
            continue
        prof.raw_fields[attr] = make_value(attr, val)
        prof.ordering.append(attr)

    # Leaf child elements: <layerHeight>0.2</layerHeight> etc.
    for child in profile_el:
        tag = child.tag
        # elements with their own children (e.g. <autoConfigureQuality>) → skip
        # container, but still capture attribute-bearing leaves.
        if len(list(child)) == 0:
            raw = (child.text or "").strip()
            if raw != "" or child.attrib:
                # some settings carry the value in attributes
                if raw == "" and child.attrib:
                    raw = _flatten_attrs(child.attrib)
                if tag not in prof.raw_fields:
                    prof.raw_fields[tag] = make_value(tag, raw)
                    prof.ordering.append(tag)
    return prof


def _flatten_attrs(attrib):
    return ",".join(f"{k}={v}" for k, v in attrib.items())
