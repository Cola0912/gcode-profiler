# -*- coding: utf-8 -*-
from gcode_profiler import canonical as cn
from gcode_profiler.canonical import model as m
from gcode_profiler.conversion import TARGETS, build_plan, capability, group_plan, summary_ja
from gcode_profiler.conversion.registry import CAPABILITIES


def _profile():
    p = m.empty_profile()
    m.set_value(p, "process.quality.layer_height", m.observed(0.2, unit="mm"))
    m.set_value(p, "process.quality.initial_layer_height", m.observed(0.24, unit="mm"))
    m.set_value(p, "process.quality.line_width.default", m.observed(0.45, unit="mm"))
    m.set_value(p, "process.quality.line_width.outer_wall", m.observed(0.42, unit="mm"))
    m.set_value(p, "process.strength.wall_loops", m.estimated(3, value_mode="count"))
    m.set_value(p, "process.strength.sparse_infill_density",
                m.estimated(15, value_mode="percentage"))
    m.set_value(p, "process.speed.inner_wall", m.observed(60, unit="mm/s"))
    m.set_value(p, "process.speed.outer_wall", m.observed(30, unit="mm/s"))
    m.set_value(p, "process.speed.travel", m.observed(180, unit="mm/s"))
    m.set_value(p, "process.speed.bridge_external", m.observed(25, unit="mm/s"))
    m.set_value(p, "material.temperature.nozzle", m.emitted(220, unit="C"))
    m.set_value(p, "material.temperature.bed", m.emitted(60, unit="C"))
    m.set_value(p, "material.cooling.fan_max",
                m.target_default(100, unit="%", value_mode="percentage"))
    m.set_value(p, "material.filament.diameter", m.observed(1.75, unit="mm"))
    m.set_value(p, "printer.firmware.gcode_flavor",
                m.emitted("klipper", value_mode="enum"))
    m.set_value(p, "printer.extruder.nozzle_diameter",
                m.estimated(0.4, confidence=0.9, unit="mm"))
    m.set_value(p, "printer.extruder.retraction_length", m.observed(0.8, unit="mm"))
    return p


def _entry(plan, key):
    for e in plan["entries"]:
        if e["canonical_key"] == key:
            return e
    raise AssertionError(f"missing entry: {key}")


def test_targets_are_separate_registry_entries():
    assert "orca" in TARGETS and "bambu" in TARGETS
    assert "prusa" in TARGETS and "superslicer" in TARGETS
    assert CAPABILITIES["orca"] is not CAPABILITIES["bambu"]
    assert CAPABILITIES["prusa"] is not CAPABILITIES["superslicer"]


def test_capability_is_explicit_not_key_similarity():
    c = capability("orca", "process.quality.layer_height")
    assert c["supported"] is True
    assert c["target_keys"] == ["layer_height"]
    assert capability("orca", "process.quality.magic_setting")["supported"] is False


def test_plan_maps_exact_rename_and_percentage_values():
    plan = build_plan(_profile(), "orca")
    assert _entry(plan, "process.quality.layer_height")["effective_value"] == 0.2
    dens = _entry(plan, "process.strength.sparse_infill_density")
    assert dens["effective_value"] == "15%"
    assert dens["target_keys"] == ["sparse_infill_density"]


def test_one_to_many_keeps_single_effective_value_and_multiple_targets():
    plan = build_plan(_profile(), "orca")
    e = _entry(plan, "process.quality.line_width.default")
    assert e["status"] == "one_to_many"
    assert e["effective_value"] == 0.45
    assert "outer_wall_line_width" in e["target_keys"]
    assert "inherited_from_default" in e["information_loss"]


def test_simplify3d_derived_percent_and_unit_conversion():
    plan = build_plan(_profile(), "simplify3d")
    base = _entry(plan, "process.speed.inner_wall")
    outer = _entry(plan, "process.speed.outer_wall")
    travel = _entry(plan, "process.speed.travel")
    assert base["effective_value"] == 3600
    assert outer["status"] == "derived"
    assert outer["effective_value"] == "50%"
    assert travel["effective_value"] == 10800


def test_many_to_one_marks_information_loss():
    plan = build_plan(_profile(), "simplify3d")
    e = _entry(plan, "process.speed.bridge_external")
    assert e["status"] == "many_to_one"
    assert e["effective_value"] == "42%"
    assert "複数値を1つに集約" in e["information_loss"]


def test_enum_translation_and_unknown_enum_warning():
    plan = build_plan(_profile(), "prusa")
    assert _entry(plan, "printer.firmware.gcode_flavor")["effective_value"] == "klipper"

    p = _profile()
    m.set_value(p, "printer.firmware.gcode_flavor",
                m.emitted("industrial-custom", value_mode="enum"))
    e = _entry(build_plan(p, "prusa"), "printer.firmware.gcode_flavor")
    assert e["status"] == "approximated"
    assert e["warnings"]


def test_required_inputs_are_not_silenced_by_missing_paths():
    plan = build_plan(_profile(), "orca")
    keys = {r["canonical_key"] for r in plan["required_user_inputs"]}
    assert "printer.basic_information.bed_shape" in keys
    assert "printer.basic_information.printable_height" in keys
    assert "printer.firmware.gcode_flavor" not in keys


def test_low_confidence_nozzle_requires_confirmation():
    p = _profile()
    m.set_value(p, "printer.extruder.nozzle_diameter",
                m.estimated(0.4, confidence=0.4, unit="mm"))
    plan = build_plan(p, "orca")
    req = {r["canonical_key"]: r for r in plan["required_user_inputs"]}
    assert req["printer.extruder.nozzle_diameter"]["suggested_value"] == 0.4


def test_target_defaults_are_not_reported_as_recovered_values():
    plan = build_plan(_profile(), "orca")
    e = _entry(plan, "material.cooling.fan_max")
    assert e["status"] == "target_default"
    assert "復元値ではない" in e["information_loss"][0]


def test_conflict_preserves_value_layers_and_warns():
    p = _profile()
    v = m.CanonicalValue(configured=0.2, emitted=0.24, unit="mm", status="explicit")
    m.set_value(p, "process.quality.layer_height", v)
    e = _entry(build_plan(p, "orca"), "process.quality.layer_height")
    assert e["status"] == "conflict"
    assert e["effective_value"] == 0.2
    assert e["value_layers"]["configured"] == 0.2
    assert e["value_layers"]["emitted"] == 0.24
    assert e["warnings"]


def test_edited_value_wins_but_layers_remain_visible():
    p = _profile()
    v = m.CanonicalValue(observed=80, edited=120, unit="mm/s", status="user")
    m.set_value(p, "process.speed.outer_wall", v)
    e = _entry(build_plan(p, "orca"), "process.speed.outer_wall")
    assert e["effective_value"] == 120
    assert e["value_layers"]["observed"] == 80
    assert e["value_layers"]["edited"] == 120


def test_preview_summary_groups_plan_for_ui():
    plan = build_plan(_profile(), "simplify3d")
    grouped = group_plan(plan)
    assert "Exact / Renamed" in grouped
    assert "Derived" in grouped
    assert "_required_user_inputs" in grouped
    text = summary_ja(plan)
    assert "変換スコア" in text and "要ユーザー入力" in text


def test_legacy_result_can_enter_conversion_via_canonical_migration():
    legacy = {
        "meta": {"source": "Unknown", "method": "ツールパス逆算"},
        "quality": {"layer_height": 0.2, "outer_wall_width": 0.42},
        "speed": {"outer_wall_speed": 100, "inner_wall_speed": 80},
        "strength": {"wall_loops": 2, "has_support": None, "has_raft": None},
        "temperature": {"nozzle_temp": 215},
        "retraction": {},
    }
    plan = build_plan(cn.migrate(legacy), "orca")
    assert _entry(plan, "process.quality.layer_height")["effective_value"] == 0.2
    assert _entry(plan, "process.speed.outer_wall")["target_keys"] == ["outer_wall_speed"]
