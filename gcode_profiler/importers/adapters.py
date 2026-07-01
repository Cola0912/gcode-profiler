# -*- coding: utf-8 -*-
"""Per-slicer semantic adapters (Phase 6).

Each adapter binds a parser (structure) to a registry target (semantics). Orca
and Bambu, and Prusa and SuperSlicer, are kept as *separate* adapters even
though they share a parser and most of their vocabulary — divergent keys and
enum tables must not leak across families.
"""
from __future__ import annotations

from . import json_family, ini_family, xml_family
from . import to_canonical as tc


class Adapter:
    def __init__(self, slicer, target, parse_fn):
        self.slicer = slicer          # detection label, e.g. "OrcaSlicer"
        self.target = target          # registry key, e.g. "orca"
        self._parse_fn = parse_fn

    def parse(self, text, path):
        return self._parse_fn(text, path, self.slicer)

    def to_canonical(self, native_profile, version=None):
        return tc.to_canonical(native_profile, self.target,
                               source_slicer=self.slicer, source_version=version)


ADAPTERS = {
    "OrcaSlicer":  Adapter("OrcaSlicer",  "orca",        json_family.parse_json),
    "BambuStudio": Adapter("BambuStudio", "bambu",       json_family.parse_json),
    "PrusaSlicer": Adapter("PrusaSlicer", "prusa",       ini_family.parse_ini),
    "SuperSlicer": Adapter("SuperSlicer", "superslicer", ini_family.parse_ini),
    "Cura":        Adapter("Cura",        "cura",        ini_family.parse_ini),
    "Simplify3D":  Adapter("Simplify3D",  "simplify3d",  xml_family.parse_xml),
}


def for_slicer(slicer):
    return ADAPTERS.get(slicer)
