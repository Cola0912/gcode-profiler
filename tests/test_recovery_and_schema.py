# -*- coding: utf-8 -*-
from gcode_profiler import schema as sc
from gcode_profiler import exporters
from gcode_profiler.nozzle_estimator import estimate_lines


def _field(key):
    for f in sc.all_fields(sc.PRINTER):
        if f.key == key:
            return f
    return None


def test_machine_accel_not_from_process_accel():
    f = _field("machine.max_accel_x")
    assert f is not None
    assert f.src != "speed.outer_wall_accel"  # must not copy process acceleration


def test_machine_speed_not_from_travel_speed():
    f = _field("machine.max_speed_x")
    assert f is not None
    assert f.src != "speed.travel_speed"       # must not copy travel speed


def test_default_values_marked_not_recovered():
    # prefill of an empty result: defaults must have provenance "default", not recovered
    values, prov = sc.prefill_values({"meta": {}, "quality": {}, "speed": {},
                                      "strength": {}, "temperature": {}, "retraction": {}})
    # printable_area has a default and no analysis source -> default provenance
    assert prov.get("machine.printable_area") == "default"


def test_exporters_emit_all_targets():
    result = {
        "meta": {"tool_count": 1, "tools_used": [0]},
        "quality": {"layer_height": 0.2}, "speed": {"outer_wall_speed": 120},
        "strength": {"wall_loops": 3}, "temperature": {"nozzle_temp": 210},
        "retraction": {}, "filaments": [{"tool": 0, "nozzle_temp": 210}],
        "gcode_blocks": {}, "machine": {},
    }
    for target in exporters.TARGETS:
        files = exporters.export(result, "T", target)
        assert files and all(content for _name, content in files)


def test_pa_block_present_in_estimate():
    lines = ["G21", "G90", "M82", "G1 Z0.2", ";TYPE:External perimeter",
             "G1 X10 Y10 F1800", "G1 X40 Y10 E1.0"]
    r = estimate_lines(lines)
    assert "pressure_advance" in r and "detected" in r["pressure_advance"]
