# -*- coding: utf-8 -*-
from gcode_profiler import export_flow


def _legacy():
    return {
        "meta": {"source": "Unknown", "method": "ツールパス逆算", "tool_count": 1,
                 "tools_used": [0], "nozzle_diameter_est": 0.4, "nozzle_confidence": 80},
        "quality": {"layer_height": 0.2, "first_layer_height": 0.2,
                    "outer_wall_width": 0.45, "inner_wall_width": 0.45},
        "speed": {"outer_wall_speed": 120, "inner_wall_speed": 150,
                  "sparse_infill_speed": 180, "travel_speed": 500,
                  "outer_wall_accel": 3000},
        "strength": {"wall_loops": 3, "sparse_infill_density_pct": 20,
                     "has_support": True, "has_raft": None},
        "temperature": {"nozzle_temp": 210, "bed_temp": 60},
        "retraction": {"retract_length": 0.8, "retract_speed": 35},
        "machine": {}, "filaments": [{"tool": 0, "nozzle_temp": 210, "bed_temp": 60}],
        "gcode_blocks": {},
    }


def test_target_id_mapping():
    assert export_flow.target_id("OrcaSlicer (JSON)") == "orca"
    assert export_flow.target_id("simplify3d") == "simplify3d"


def test_plan_and_preview_all_targets():
    for _disp, tid in export_flow.TARGET_CHOICES:
        prof, plan = export_flow.build_plan_from_legacy(_legacy(), tid)
        assert plan["target"] == tid
        pv = export_flow.preview(plan)
        assert pv["conversion_score"] >= 0
        # bed shape is a critical required input (not recoverable from G-code)
        assert pv["has_critical"] is True


def test_printable_area_input_satisfies_required_bed_shape():
    legacy = _legacy()
    legacy["machine"] = {
        "printable_area": "0x0,220x0,220x220,0x220",
        "printable_height": 250,
    }
    _prof, plan = export_flow.build_plan_from_legacy(legacy, "orca")
    required = {r["canonical_key"] for r in plan["required_user_inputs"]}
    assert "printer.basic_information.bed_shape" not in required
    assert "printer.basic_information.printable_height" not in required
    entry = next(e for e in plan["entries"]
                 if e["canonical_key"] == "printer.basic_information.bed_shape")
    assert entry["target_keys"] == ["printable_area"]
    assert entry["effective_value"] == "0x0,220x0,220x220,0x220"


def test_writer_blocks_on_critical_then_unblocks_on_override():
    _prof, plan = export_flow.build_plan_from_legacy(_legacy(), "orca")
    blocked = export_flow.write_native(plan, name="T")
    assert blocked.blocked is True            # critical bed_shape blocks
    # expert override: downgrade criticals
    for r in plan["required_user_inputs"]:
        r["safety_level"] = "important"
    wres = export_flow.write_native(plan, name="T")
    assert wres.blocked is False
    names = [f for f, _ in wres.files]
    assert any(n.endswith(".process.json") for n in names)


def test_each_target_writes_files_after_override():
    for _disp, tid in export_flow.TARGET_CHOICES:
        _prof, plan = export_flow.build_plan_from_legacy(_legacy(), tid)
        for r in plan["required_user_inputs"]:
            r["safety_level"] = "important"
        wres = export_flow.write_native(plan, name="T")
        assert not wres.blocked
        assert wres.files and all(content for _f, content in wres.files)


def test_simplify3d_derived_percent_present():
    _prof, plan = export_flow.build_plan_from_legacy(_legacy(), "simplify3d")
    # outer wall is a percentage of the base speed (defaultSpeed)
    derived = [e for e in plan["entries"] if e["relation"] == "derived_percent"]
    assert derived and any(str(e["effective_value"]).endswith("%") for e in derived)
