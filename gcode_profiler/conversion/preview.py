# -*- coding: utf-8 -*-
"""Conversion preview grouping (Phase 4). Groups plan entries for UI review."""
from __future__ import annotations

from collections import defaultdict

_GROUP = {
    "ready": "Exact / Renamed",
    "derived": "Derived",
    "one_to_many": "One-to-many",
    "many_to_one": "Many-to-one",
    "approximated": "Approximated",
    "target_default": "Target default",
    "unsupported": "Unsupported",
    "unresolved": "Unresolved",
    "conflict": "Conflict",
}


def group_plan(plan):
    groups = defaultdict(list)
    for e in plan["entries"]:
        groups[_GROUP.get(e["status"], e["status"])].append(e)
    out = {g: groups[g] for g in groups}
    out["_required_user_inputs"] = plan["required_user_inputs"]
    out["_conversion_score"] = plan["conversion_score"]
    return out


def summary_ja(plan):
    n = len(plan["entries"])
    ready = sum(1 for e in plan["entries"] if e["status"] in ("ready",))
    derived = sum(1 for e in plan["entries"] if e["status"] == "derived")
    unsup = sum(1 for e in plan["entries"] if e["status"] == "unsupported")
    req = len(plan["required_user_inputs"])
    return (f"{plan['target']}: 変換スコア {plan['conversion_score']} / "
            f"項目 {n}（確定 {ready}・導出 {derived}・未対応 {unsup}）/ "
            f"要ユーザー入力 {req}")
