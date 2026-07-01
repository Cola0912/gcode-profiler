# -*- coding: utf-8 -*-
"""Merge profile-derived (configured) and G-code-derived (observed) canonical
profiles into one (Phase 6).

`configured` comes from a native profile import; `observed`/`emitted` come from
G-code analysis. Layers are never overwritten — they are combined into a single
CanonicalValue per key so that conflicts (profile says X, G-code shows Y) stay
visible.
"""
from __future__ import annotations

from ..canonical import model as m

# canonical top-level sections that hold value nodes
_SECTIONS = ("printer", "material", "process")


def merge(configured_profile, observed_profile):
    """Return a merged canonical profile. Both inputs are canonical profile
    dicts (from canonical.model.empty_profile)."""
    merged = m.empty_profile()

    # keep provenance of both sources
    merged["source"] = {
        "configured": configured_profile.get("source", {}),
        "observed": observed_profile.get("source", {}),
        "analysis_mode": "profile+gcode",
    }
    merged["metadata"] = {
        "configured": configured_profile.get("metadata", {}),
        "observed": observed_profile.get("metadata", {}),
    }
    merged["unmapped"] = dict(configured_profile.get("unmapped", {}))

    conf_keys = _leaf_keys(configured_profile)
    obs_keys = _leaf_keys(observed_profile)
    conflicts = []

    for key in sorted(conf_keys | obs_keys):
        cconf = _get_cv(configured_profile, key)
        cobs = _get_cv(observed_profile, key)
        combined, conflict = _combine(cconf, cobs)
        m.set_value(merged, key, combined)
        if conflict:
            conflicts.append({
                "canonical_key": key,
                "configured": combined.configured,
                "observed": combined.observed or combined.emitted,
            })

    merged["metadata"]["conflicts"] = conflicts
    return merged


def _combine(cconf, cobs):
    """Fold a configured-side and observed-side CanonicalValue into one.
    Returns (CanonicalValue, is_conflict)."""
    cv = m.CanonicalValue()

    if cconf is not None:
        cv.configured = cconf.configured
        cv.unit = cconf.unit
        cv.value_mode = cconf.value_mode
        cv.evidence = list(cconf.evidence)
        cv.warnings = list(cconf.warnings)
        cv.source_keys = list(cconf.source_keys)
        cv.status = cconf.status
        cv.source = cconf.source
        cv.confidence = cconf.confidence

    if cobs is not None:
        # observed side may hold observed OR emitted (G-code command)
        cv.observed = cobs.observed
        cv.emitted = cobs.emitted
        if cconf is None:
            cv.unit = cobs.unit
            cv.value_mode = cobs.value_mode
            cv.evidence = list(cobs.evidence)
            cv.warnings = list(cobs.warnings)
            cv.source_keys = list(cobs.source_keys)
            cv.status = cobs.status
            cv.source = cobs.source
            cv.confidence = cobs.confidence
        else:
            cv.evidence += cobs.evidence
            cv.source_keys += cobs.source_keys

    conflict = _is_conflict(cv)
    if conflict:
        cv.status = "conflict"
        cv.warnings.append("プロファイル値とG-code値が不一致")
    return cv, conflict


def _is_conflict(cv):
    conf = cv.configured
    obs = cv.observed if cv.observed is not None else cv.emitted
    if conf is None or obs is None:
        return False
    return not _approx_equal(conf, obs)


def _approx_equal(a, b):
    try:
        return abs(float(a) - float(b)) <= 1e-6 + 1e-3 * abs(float(a))
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


# ---------------------------------------------------------------------------
def _leaf_keys(profile):
    """Collect dotted canonical keys pointing at CanonicalValue dicts."""
    keys = set()
    for section in _SECTIONS:
        node = profile.get(section)
        if isinstance(node, dict):
            _walk(node, section, keys)
    return keys


def _walk(node, prefix, out):
    if _is_cv_dict(node):
        out.add(prefix)
        return
    for k, v in node.items():
        if isinstance(v, dict):
            _walk(v, f"{prefix}.{k}", out)


def _is_cv_dict(d):
    return isinstance(d, dict) and "effective" in d and (
        "configured" in d or "observed" in d or "emitted" in d)


def _get_cv(profile, key):
    d = m.get_value(profile, key)
    if _is_cv_dict(d):
        return m.CanonicalValue.from_dict(d)
    return None
