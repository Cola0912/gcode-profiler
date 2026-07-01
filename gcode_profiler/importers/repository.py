# -*- coding: utf-8 -*-
"""Parent-preset repository for inheritance resolution (Phase 6).

A repository resolves a parent reference (by display name or native id) to a
NativeProfile. Members can be added explicitly (e.g. bundle sub-profiles) or
discovered by scanning sibling files in the same directory. Vendor/system preset
bundles are out of scope for this phase.
"""
from __future__ import annotations

import os


class Repository:
    def __init__(self):
        self._by_name = {}
        self._by_id = {}

    def add(self, profile):
        if profile is None:
            return
        if profile.display_name:
            self._by_name.setdefault(profile.display_name, profile)
        if profile.native_id:
            self._by_id.setdefault(profile.native_id, profile)
        for sub in profile.sub_profiles:
            self.add(sub)

    def find(self, ref):
        """Resolve a parent reference to a NativeProfile, or None."""
        if not ref:
            return None
        return self._by_name.get(ref) or self._by_id.get(ref)

    def names(self):
        return list(self._by_name.keys())

    @classmethod
    def from_profiles(cls, profiles):
        repo = cls()
        for p in profiles:
            repo.add(p)
        return repo

    @classmethod
    def from_directory(cls, directory, parse_fn, max_files=500):
        """Scan a directory for sibling presets and index them.

        parse_fn(path) -> NativeProfile | None. Parse failures are ignored so a
        single bad sibling never blocks the import.
        """
        repo = cls()
        if not directory or not os.path.isdir(directory):
            return repo
        count = 0
        for entry in sorted(os.listdir(directory)):
            if count >= max_files:
                break
            full = os.path.join(directory, entry)
            if not os.path.isfile(full):
                continue
            count += 1
            try:
                prof = parse_fn(full)
            except Exception:
                prof = None
            if prof is not None:
                repo.add(prof)
        return repo
