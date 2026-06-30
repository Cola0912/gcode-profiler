# -*- coding: utf-8 -*-
"""
Generic comment/marker normalization and concept classification (Phase 2).

Not hard-coded to one slicer: comments are normalized (lowercase, punctuation
stripped, whitespace collapsed, tokenized) and matched against concept aliases
using longest-phrase containment. Unknown recurring markers are collected for
later inspection. A single weak token yields low confidence, never a forced
classification.
"""
from __future__ import annotations

import re
from collections import defaultdict

# concept -> alias phrases (normalized form). Longer phrases win over shorter.
_CONCEPT_ALIASES = {
    "outer_wall": ["external perimeter", "outer wall", "wall outer", "outer perimeter",
                   "modelcontour", "wall 0"],
    "inner_wall": ["internal perimeter", "inner wall", "wall inner", "inner perimeter",
                   "modelinvisiblecontour", "perimeter", "wall x"],
    "overhang_wall": ["overhang perimeter", "overhang wall", "overhang"],
    "solid_infill": ["internal solid infill", "solid infill", "solid layer"],
    "top_surface": ["top solid infill", "top surface", "visibletopinfill", "skin"],
    "bottom_surface": ["bottom surface", "bottom shell"],
    "sparse_infill": ["internal infill", "sparse infill", "invisibleinfill", "infill", "fill"],
    "gap_fill": ["gap fill", "gapfill"],
    "bridge": ["bridge infill", "external bridge", "internal bridge", "bridge"],
    "ironing": ["ironing", "iron"],
    "support_interface": ["support material interface", "support interface", "dense support"],
    "support": ["support material", "supportinfill", "support"],
    "raft": ["raft interface", "raft grid", "raft base", "raft"],
    "brim": ["skirt brim", "brim"],
    "skirt": ["skirt"],
    "wipe": ["wipe tower", "wipe"],
    "purge": ["prime tower", "purge tower", "purge", "priming"],
    "prime": ["prime line", "prime"],
    "tool_change": ["tool change", "toolchange"],
    "object_boundary": ["printing object", "exclude object", "object start", "object end",
                        "stop printing object"],
    "layer": ["layer change", "layer"],
}

# precompute (phrase, concept, word_count) sorted by length desc
_ALIAS_INDEX = sorted(
    ((phrase, concept, len(phrase.split()))
     for concept, phrases in _CONCEPT_ALIASES.items() for phrase in phrases),
    key=lambda t: -t[2],
)

_PREFIX_RE = re.compile(r"^\s*;+\s*(type|feature|marker)\s*[:=]?\s*", re.I)
_WIDTH_RE = re.compile(r";\s*width\s*[:=]\s*([\d.]+)", re.I)
_HEIGHT_RE = re.compile(r";\s*height\s*[:=]\s*([\d.]+)", re.I)
_PUNCT_RE = re.compile(r"[^a-z0-9]+")


def normalize(text):
    """Lowercase, strip a known prefix, remove punctuation, collapse whitespace."""
    t = _PREFIX_RE.sub("", text or "")
    t = t.lower()
    t = _PUNCT_RE.sub(" ", t)
    return " ".join(t.split())


class MarkerClassifier:
    """Stateful: classifies comments to concepts and records unknown recurring markers."""
    def __init__(self):
        self.unknown_counts = defaultdict(int)
        self.recognized_counts = defaultdict(int)

    def width_hint(self, raw):
        m = _WIDTH_RE.search(raw)
        return float(m.group(1)) if m else None

    def height_hint(self, raw):
        m = _HEIGHT_RE.search(raw)
        return float(m.group(1)) if m else None

    def classify(self, raw):
        """Return (concept, confidence) or (None, 0.0). Records unknown markers
        only for marker-like comments (TYPE/FEATURE/Marker prefixed)."""
        is_marker = bool(_PREFIX_RE.match(raw or ""))
        norm = normalize(raw)
        if not norm:
            return None, 0.0
        tokens = norm.split()
        token_set = set(tokens)
        for phrase, concept, wc in _ALIAS_INDEX:
            pw = phrase.split()
            if all(w in token_set for w in pw) and _contiguous_or_subset(tokens, pw):
                conf = 0.9 if wc >= 2 else 0.6
                self.recognized_counts[concept] += 1
                return concept, conf
        if is_marker:
            self.unknown_counts[norm] += 1
        return None, 0.0

    def unknown_recurring(self, min_count=3):
        return {k: v for k, v in self.unknown_counts.items() if v >= min_count}


def _contiguous_or_subset(tokens, phrase_words):
    """Accept if the phrase words appear (as a subset). For single-word phrases
    this is just membership; multi-word phrases require all words present."""
    if len(phrase_words) == 1:
        return phrase_words[0] in tokens
    return all(w in tokens for w in phrase_words)


def classify_concept(raw):
    """Stateless convenience wrapper."""
    return MarkerClassifier().classify(raw)
