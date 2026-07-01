# -*- coding: utf-8 -*-
"""Inheritance graph resolution (Phase 6).

Resolves `inherits` chains into an effective field set while keeping the child's
declared fields distinct from inherited ones. Detects missing parents, cycles,
and depth-limit violations. Multiple-parent precedence beyond simple left-to-
right ordering is deferred.
"""
from __future__ import annotations

import copy

from .base import NativeProfile

MAX_DEPTH = 20


def resolve(profile, repository):
    """Return a resolved copy of `profile` with:
      * raw_fields = effective (inherited + declared, child wins)
      * declared_keys  : keys explicitly present on the child
      * inherited_keys : keys contributed only by ancestors
      * origin_map     : {native_key: source_profile_name}
      * inheritance_chain / warnings recorded on the returned profile.

    The returned object is a NativeProfile with extra attributes attached
    (declared_keys, inherited_keys, origin_map, inheritance_chain).
    """
    warnings = []
    chain = []
    origin = {}
    effective = {}

    declared_keys = set(profile.raw_fields.keys())

    # Walk ancestors from the root down so children override parents.
    ancestry = _linearize(profile, repository, warnings)
    for anc in ancestry:                 # root ... parent
        chain.append(anc.display_name or anc.native_id or "?")
        for k, v in anc.raw_fields.items():
            effective[k] = v
            origin[k] = anc.display_name or anc.native_id or "?"

    # Finally the child itself wins.
    for k, v in profile.raw_fields.items():
        effective[k] = v
        origin[k] = profile.display_name or "self"
    chain.append(profile.display_name or "self")

    resolved = _clone_shallow(profile)
    resolved.raw_fields = effective
    resolved.declared_keys = declared_keys
    resolved.inherited_keys = set(effective.keys()) - declared_keys
    resolved.origin_map = origin
    resolved.inheritance_chain = chain
    resolved.inheritance_warnings = warnings
    return resolved


def _linearize(profile, repository, warnings):
    """Return ancestors ordered root-first (excluding the profile itself)."""
    ancestry = []
    visited = set()

    def walk(node, depth):
        if depth > MAX_DEPTH:
            warnings.append(f"継承の深さが上限({MAX_DEPTH})を超えました")
            return
        node_id = node.display_name or node.native_id
        if node_id in visited:
            warnings.append(f"継承の循環を検出: {node_id}")
            return
        visited.add(node_id)
        for ref in node.parent_refs:
            parent = repository.find(ref)
            if parent is None:
                warnings.append(f"親プリセットが見つかりません: {ref}")
                continue
            walk(parent, depth + 1)
            ancestry.append(parent)

    walk(profile, 0)
    return ancestry


def _clone_shallow(profile):
    new = NativeProfile(
        source_path=profile.source_path,
        slicer=profile.slicer,
        version=profile.version,
        profile_kind=profile.profile_kind,
        display_name=profile.display_name,
        native_id=profile.native_id,
        parent_refs=list(profile.parent_refs),
        raw_fields=dict(profile.raw_fields),
        unknown_fields=dict(profile.unknown_fields),
        comments=list(profile.comments),
        ordering=list(profile.ordering),
        encoding=profile.encoding,
        sub_profiles=list(profile.sub_profiles),
    )
    return new
