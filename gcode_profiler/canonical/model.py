# -*- coding: utf-8 -*-
"""
Canonical value model (Phase 1 foundation for v0.2.0).

A single shared value record separates the layers a setting can come from and
resolves an `effective` value by explicit precedence. This is additive: the
legacy analyzer/exporters keep working; conversion to/from canonical is done by
adapter.py.

Precedence for `effective`:
    edited > configured > emitted > observed > target_default
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

SCHEMA_VERSION = "1.0"

# status: how the effective value was obtained
STATUS = ("explicit", "calculated", "estimated", "unknown", "user",
          "target_default", "application_default", "conflict")
# source: where the evidence came from
SOURCE = ("command", "metadata", "geometry", "statistics", "user",
          "target_default", "not_found")
# value_mode: how the raw value should be interpreted
VALUE_MODE = ("absolute", "percentage", "ratio", "count", "enum", "text", "unknown")


def _first_present(*vals):
    for v in vals:
        if v is not None:
            return v
    return None


@dataclass
class CanonicalValue:
    """One canonical setting. Layers are kept separate and never overwrite each other."""
    configured: Any = None        # explicit source-profile value (embedded)
    emitted: Any = None           # value explicitly emitted as command/metadata
    observed: Any = None          # value calculated from toolpaths
    edited: Any = None            # user override inside this application
    target_default: Any = None    # target-slicer / application default (NOT recovered)
    unit: Optional[str] = None
    value_mode: str = "unknown"
    status: str = "unknown"
    source: str = "not_found"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    source_keys: List[str] = field(default_factory=list)
    source_ranges: List[Any] = field(default_factory=list)

    @property
    def effective(self):
        return _first_present(self.edited, self.configured, self.emitted,
                              self.observed, self.target_default)

    @property
    def is_conflict(self):
        """configured and emitted both present and disagree."""
        return (self.configured is not None and self.emitted is not None
                and self.configured != self.emitted)

    def to_dict(self):
        d = {
            "configured": self.configured, "emitted": self.emitted,
            "observed": self.observed, "edited": self.edited,
            "target_default": self.target_default, "effective": self.effective,
            "unit": self.unit, "value_mode": self.value_mode,
            "status": "conflict" if self.is_conflict else self.status,
            "source": self.source, "confidence": round(self.confidence, 3),
            "evidence": list(self.evidence), "warnings": list(self.warnings),
            "source_keys": list(self.source_keys),
        }
        return d

    @classmethod
    def from_dict(cls, d):
        return cls(
            configured=d.get("configured"), emitted=d.get("emitted"),
            observed=d.get("observed"), edited=d.get("edited"),
            target_default=d.get("target_default"),
            unit=d.get("unit"), value_mode=d.get("value_mode", "unknown"),
            status=d.get("status", "unknown"), source=d.get("source", "not_found"),
            confidence=d.get("confidence", 0.0),
            evidence=list(d.get("evidence", [])), warnings=list(d.get("warnings", [])),
            source_keys=list(d.get("source_keys", [])),
        )


# Convenience constructors for each provenance layer ------------------------
def observed(value, source="geometry", confidence=0.6, status="calculated",
             unit=None, value_mode="absolute", evidence=None, keys=None):
    if value is None:
        return CanonicalValue(unit=unit, value_mode=value_mode)
    return CanonicalValue(observed=value, source=source, confidence=confidence,
                          status=status, unit=unit, value_mode=value_mode,
                          evidence=evidence or [], source_keys=keys or [])


def configured(value, confidence=0.9, unit=None, value_mode="absolute",
               evidence=None, keys=None):
    if value is None:
        return CanonicalValue(unit=unit, value_mode=value_mode)
    return CanonicalValue(configured=value, source="metadata", confidence=confidence,
                          status="explicit", unit=unit, value_mode=value_mode,
                          evidence=evidence or [], source_keys=keys or [])


def emitted(value, confidence=0.85, unit=None, value_mode="absolute",
            evidence=None, keys=None):
    if value is None:
        return CanonicalValue(unit=unit, value_mode=value_mode)
    return CanonicalValue(emitted=value, source="command", confidence=confidence,
                          status="explicit", unit=unit, value_mode=value_mode,
                          evidence=evidence or [], source_keys=keys or [])


def estimated(value, source="statistics", confidence=0.4, unit=None,
              value_mode="absolute", evidence=None, warnings=None, keys=None):
    if value is None:
        return CanonicalValue(unit=unit, value_mode=value_mode,
                              warnings=warnings or [])
    return CanonicalValue(observed=value, source=source, confidence=confidence,
                          status="estimated", unit=unit, value_mode=value_mode,
                          evidence=evidence or [], warnings=warnings or [],
                          source_keys=keys or [])


def target_default(value, unit=None, value_mode="absolute"):
    """Application/target default. NEVER reported as a recovered source value."""
    return CanonicalValue(target_default=value, source="target_default",
                          status="application_default", confidence=0.0,
                          unit=unit, value_mode=value_mode)


def unknown(unit=None, value_mode="unknown", warnings=None):
    return CanonicalValue(unit=unit, value_mode=value_mode, status="unknown",
                          source="not_found", warnings=warnings or [])


# Canonical profile container ----------------------------------------------
def empty_profile():
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {},        # source classification (slicer/version/analysis_mode)
        "printer": {},
        "material": {},
        "process": {},
        "metadata": {},
        "unmapped": {},      # native fields that could not be mapped
    }


def set_value(profile, canonical_key, cval):
    """Set a CanonicalValue at a dotted canonical key, e.g.
    'process.speed.outer_wall'. Stored as a plain dict for serializability."""
    parts = canonical_key.split(".")
    node = profile
    for p in parts[:-1]:
        node = node.setdefault(p, {})
    node[parts[-1]] = cval.to_dict() if isinstance(cval, CanonicalValue) else cval


def get_value(profile, canonical_key):
    parts = canonical_key.split(".")
    node = profile
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return None
        node = node[p]
    return node


def effective_of(profile, canonical_key):
    d = get_value(profile, canonical_key)
    if isinstance(d, dict) and "effective" in d:
        return d["effective"]
    return None
