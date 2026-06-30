# -*- coding: utf-8 -*-
"""Schema-driven editor model backed by native parameter catalogs."""
from __future__ import annotations

from dataclasses import dataclass

from .parameter_catalogs import filter_parameters, group_for_ui, list_catalogs, load_catalog


@dataclass
class EditorState:
    slicer: str
    version: str
    profile_kind: str = "process"
    visibility: str = "advanced"
    query: str = ""


class CatalogEditorModel:
    """Non-GUI model for target-aware settings editors."""

    def __init__(self, state: EditorState):
        self.state = state
        self.catalog = load_catalog(state.slicer, state.version)

    @classmethod
    def default(cls):
        catalogs = list_catalogs()
        if "orca" in catalogs:
            return cls(EditorState("orca", catalogs["orca"][-1]))
        if not catalogs:
            raise FileNotFoundError("no parameter catalogs available")
        slicer = sorted(catalogs)[0]
        return cls(EditorState(slicer, catalogs[slicer][-1]))

    def set_target(self, slicer, version):
        self.state.slicer = slicer
        self.state.version = version
        self.catalog = load_catalog(slicer, version)

    def set_filter(self, profile_kind=None, visibility=None, query=None):
        if profile_kind is not None:
            self.state.profile_kind = profile_kind
        if visibility is not None:
            self.state.visibility = visibility
        if query is not None:
            self.state.query = query

    def parameters(self):
        return filter_parameters(self.catalog, self.state.profile_kind,
                                 self.state.visibility, self.state.query)

    def sections(self):
        return group_for_ui(self.parameters())

    def coverage(self):
        return self.catalog.get("coverage", {})

    def reset_value(self, native_key, value_store):
        """Reset one native value to catalog default/inherited value."""
        for p in self.catalog.get("parameters", []):
            if p["native_key"] == native_key:
                value_store[native_key] = {
                    "edited": None,
                    "effective": p.get("default"),
                    "source": "native_default",
                    "parameter": native_key,
                }
                return value_store[native_key]
        raise KeyError(native_key)

