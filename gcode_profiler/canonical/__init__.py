# -*- coding: utf-8 -*-
"""Canonical semantic profile model and adapters (Phase 1 foundation)."""
from .model import (  # noqa: F401
    SCHEMA_VERSION, CanonicalValue, empty_profile, set_value, get_value,
    effective_of, observed, configured, emitted, estimated, target_default, unknown,
)
from .adapter import (  # noqa: F401
    legacy_to_canonical, canonical_to_legacy, LEGACY_MAP, CANONICAL_TO_LEGACY,
)
from .migration import migrate, is_canonical, deprecated_keys_present  # noqa: F401
