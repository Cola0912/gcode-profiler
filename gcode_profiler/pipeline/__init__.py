# -*- coding: utf-8 -*-
"""
Slicer-independent generic G-code analysis pipeline (Phase 2).

Additive and backward-compatible: the legacy `analyzer.py` is untouched. This
package reconstructs logical layers, segments paths, normalizes markers, and
produces non-destructive feature-candidate scores even when the source slicer
is unknown and no embedded profile exists. Full support/raft geometry
classification and native importers/exporters are out of scope here.

Entry points:
    analyze_generic(path)  -> GenericAnalysis
    analyze_lines(lines)   -> GenericAnalysis
"""
from .runner import analyze_generic, analyze_lines, GenericAnalysis  # noqa: F401
from .markers import MarkerClassifier, classify_concept, normalize  # noqa: F401
from .regions import build_regions, Region  # noqa: F401
from .auxiliary import (  # noqa: F401
    classify_auxiliary, AuxResult, to_canonical as aux_to_canonical,
    to_legacy_compat as aux_to_legacy, diagnostics as aux_diagnostics,
)
