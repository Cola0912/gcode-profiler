# -*- coding: utf-8 -*-
from gcode_profiler import canonical as cn
from gcode_profiler.canonical import model as m


def test_effective_precedence():
    v = m.CanonicalValue(observed=60, configured=80)
    assert v.effective == 80               # configured > observed
    v.edited = 50
    assert v.effective == 50               # edited wins
    v2 = m.CanonicalValue(target_default=200, observed=None)
    assert v2.effective == 200             # falls back to target default


def test_target_default_not_recovered():
    td = m.target_default(250)
    d = td.to_dict()
    assert d["status"] == "application_default"
    assert d["source"] == "target_default"
    assert d["observed"] is None and d["configured"] is None  # not a recovered value


def test_configured_emitted_observed_separate_and_conflict():
    v = m.CanonicalValue(configured=80, emitted=60)
    d = v.to_dict()
    assert d["configured"] == 80 and d["emitted"] == 60   # both preserved
    assert d["status"] == "conflict"                      # disagreement flagged
    assert d["effective"] == 80                           # configured > emitted


def _result(**over):
    r = {"meta": {"source": "Unknown", "method": "ツールパス逆算",
                  "feature_style": "なし(幾何のみ)", "tool_count": 1},
         "quality": {"layer_height": 0.2}, "speed": {"outer_wall_speed": 120,
         "travel_speed": 500, "outer_wall_accel": 3000},
         "strength": {"wall_loops": 3, "has_support": None, "has_raft": None},
         "temperature": {"nozzle_temp": 210}, "retraction": {},
         "filaments": [{"tool": 0, "nozzle_temp": 210}]}
    for k, v in over.items():
        r[k] = v
    return r


def test_legacy_migration_maps_keys():
    prof = cn.migrate(_result())
    assert prof["schema_version"] == m.SCHEMA_VERSION
    assert cn.effective_of(prof, "process.quality.layer_height") == 0.2
    assert cn.effective_of(prof, "process.speed.outer_wall") == 120


def test_process_accel_not_in_printer_limits():
    prof = cn.migrate(_result())
    # process acceleration is owned by process.acceleration, NOT printer motion limits
    assert cn.effective_of(prof, "process.acceleration.default") == 3000
    assert cn.get_value(prof, "printer.motion_ability.max_acceleration") is None


def test_travel_speed_not_in_machine_max_speed():
    prof = cn.migrate(_result())
    assert cn.effective_of(prof, "process.speed.travel") == 500
    assert cn.get_value(prof, "printer.motion_ability.max_speed") is None


def test_support_absent_enabled_state_unknown():
    prof = cn.migrate(_result(strength={"wall_loops": 2, "has_support": None,
                                         "has_raft": None}))
    enabled = cn.get_value(prof, "process.support.setting_enabled_state")
    assert enabled["status"] == "unknown"
    # path present observed False, but enabled-state must remain unknown
    assert cn.effective_of(prof, "process.support.path_present") is False
    assert enabled["effective"] is None


def test_raft_absent_enabled_state_unknown():
    prof = cn.migrate(_result())
    enabled = cn.get_value(prof, "process.support.raft.setting_enabled_state")
    assert enabled["status"] == "unknown" and enabled["effective"] is None


def test_wall_loops_estimated_not_explicit():
    prof = cn.migrate(_result())
    wl = cn.get_value(prof, "process.strength.wall_loops")
    assert wl["status"] == "estimated"


def test_embedded_value_is_configured():
    r = _result()
    r["meta"]["embedded_fields"] = ["quality.layer_height"]
    r["meta"]["method"] = "埋め込み設定（PrusaSlicer）を直接読込"
    prof = cn.migrate(r)
    lh = cn.get_value(prof, "process.quality.layer_height")
    assert lh["configured"] == 0.2 and lh["status"] == "explicit"
    assert prof["source"]["analysis_mode"] == "native_metadata"


def test_backward_compat_read():
    prof = cn.migrate(_result())
    legacy = cn.canonical_to_legacy(prof)
    assert legacy["quality"]["layer_height"] == 0.2
    assert legacy["speed"]["outer_wall_speed"] == 120


def test_old_keys_still_load():
    # a legacy dict without schema_version must still migrate
    legacy = _result()
    assert not cn.is_canonical(legacy)
    prof = cn.migrate(legacy)
    assert cn.is_canonical(prof)
    assert "strength.wall_loops" in cn.deprecated_keys_present(legacy)


def test_migrate_idempotent_on_canonical():
    prof = cn.migrate(_result())
    again = cn.migrate(prof)            # already canonical -> unchanged version
    assert again["schema_version"] == m.SCHEMA_VERSION
