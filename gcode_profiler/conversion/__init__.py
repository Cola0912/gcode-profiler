# -*- coding: utf-8 -*-
"""
Canonical -> target conversion engine (Phase 4).

Capability registry + version-aware mapping registry + conversion-plan engine
with dependency resolution (percentage base selection), required-user-input
generation, and conversion preview. Native serialization is Phase 5.
"""
from .registry import (  # noqa: F401
    CAPABILITIES, ENUM_MAPS, REQUIRED_FIELDS, capability, mapping, supported,
)
from .plan import build_plan  # noqa: F401
from .preview import group_plan, summary_ja  # noqa: F401

TARGETS = tuple(CAPABILITIES.keys())
