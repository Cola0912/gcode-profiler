# -*- coding: utf-8 -*-
import json

from gcode_profiler.canonical import model as m
from gcode_profiler.conversion import build_plan
from gcode_profiler.writers import write_native


def _profile(with_required=True):
    p = m.empty_profile()
    m.set_value(p, "process.quality.layer_height", m.observed(0.2, unit="mm"))
    m.set_value(p, "process.quality.line_width.outer_wall", m.observed(0.42, unit="mm"))
    m.set_value(p, "process.strength.wall_loops", m.estimated(3, value_mode="count"))
    m.set_value(p, "process.speed.outer_wall", m.observed(80, unit="mm/s"))
    m.set_value(p, "process.speed.inner_wall", m.observed(100, unit="mm/s"))
    m.set_value(p, "material.temperature.nozzle", m.emitted(220, unit="C"))
    m.set_value(p, "material.cooling.fan_max",
                m.target_default(100, unit="%", value_mode="percentage"))
    m.set_value(p, "material.filament.diameter", m.observed(1.75, unit="mm"))
    m.set_value(p, "printer.extruder.nozzle_diameter", m.estimated(0.4, unit="mm", confidence=0.9))
    m.set_value(p, "printer.firmware.gcode_flavor", m.emitted("klipper", value_mode="enum"))
    if with_required:
        m.set_value(p, "printer.basic_information.bed_shape",
                    m.configured("0x0,250x0,250x250,0x250", value_mode="text"))
        m.set_value(p, "printer.basic_information.printable_height",
                    m.configured(250, unit="mm"))
    return p


def _content(result, suffix):
    for name, text in result.files:
        if name.endswith(suffix):
            return text
    raise AssertionError(f"missing file ending {suffix}: {[n for n, _ in result.files]}")


def test_orca_writer_outputs_profile_subtype_files_from_plan():
    result = write_native(build_plan(_profile(), "orca"), name="T")
    assert not result.blocked
    assert [n for n, _ in result.files] == [
        "T.process.json", "T.filament.json", "T.machine.json",
    ]
    proc = json.loads(_content(result, ".process.json"))
    assert proc["type"] == "process"
    assert proc["layer_height"] == "0.2"
    assert proc["outer_wall_speed"] == "80"
    fil = json.loads(_content(result, ".filament.json"))
    assert fil["nozzle_temperature"] == ["220"]
    assert "fan_max_speed" not in fil  # target_default is not a recovered value


def test_bambu_writer_is_separate_from_orca_writer():
    result = write_native(build_plan(_profile(), "bambu"), name="T")
    names = [n for n, _ in result.files]
    assert "T.bambu.process.json" in names
    assert "T.process.json" not in names


def test_prusa_and_superslicer_writers_are_separate_ini_outputs():
    prusa = write_native(build_plan(_profile(), "prusa"), name="T")
    superp = write_native(build_plan(_profile(), "superslicer"), name="T")
    assert prusa.files[0][0] == "T.prusa.ini"
    assert superp.files[0][0] == "T.superslicer.ini"
    assert "external_perimeter_speed = 80" in prusa.files[0][1]
    assert "external_perimeter_speed = 80" in superp.files[0][1]


def test_cura_writer_outputs_cfg_values():
    result = write_native(build_plan(_profile(), "cura"), name="T")
    text = result.files[0][1]
    assert result.files[0][0] == "T.cura.cfg"
    assert "[values]" in text
    assert "speed_wall_0 = 80" in text


def test_simplify3d_writer_outputs_fff_and_derived_percent():
    result = write_native(build_plan(_profile(), "simplify3d"), name="T")
    text = result.files[0][1]
    assert result.files[0][0] == "T.simplify3d.fff"
    assert "<defaultSpeed>6000</defaultSpeed>" in text
    assert "<outlineUnderspeed>80%</outlineUnderspeed>" in text


def test_writer_blocks_unresolved_critical_required_inputs():
    result = write_native(build_plan(_profile(with_required=False), "orca"), name="T")
    assert result.blocked
    keys = {r["canonical_key"] for r in result.required_user_inputs}
    assert "printer.basic_information.bed_shape" in keys

