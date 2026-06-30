# -*- coding: utf-8 -*-
import json
from pathlib import Path

from gcode_profiler.catalog_editor import CatalogEditorModel, EditorState
from gcode_profiler.parameter_catalogs import (
    filter_parameters, group_for_ui, list_catalogs, load_catalog,
)
from tools.validate_parameter_catalog import validate


CATALOG = Path("parameter_catalogs/orca/2.3/parameters.json")
BAMBU_CATALOG = Path("parameter_catalogs/bambu/2.8/parameters.json")


def test_orca_catalog_loads_and_reports_coverage():
    cat = load_catalog("orca", "2.3")
    assert cat["slicer"] == "OrcaSlicer"
    assert cat["version"] == "2.3"
    assert len(cat["parameters"]) == 505
    assert cat["coverage"]["catalog_parameters"] == 505
    assert cat["coverage"]["mapped_to_canonical"] >= 30
    assert cat["coverage"]["native_only"] > 400


def test_bambu_catalog_loads_as_separate_target_catalog():
    cat = load_catalog("bambu", "2.8")
    assert cat["slicer"] == "Bambu Studio"
    assert cat["version"] == "2.8"
    assert len(cat["parameters"]) == 567
    assert cat["coverage"]["mapped_to_canonical"] >= 30
    assert cat["coverage"]["native_only"] > 500


def test_orca_catalog_has_no_duplicate_native_keys():
    cat = load_catalog("orca", "2.3")
    keys = [p["native_key"] for p in cat["parameters"]]
    assert len(keys) == len(set(keys))


def test_every_parameter_has_explicit_mapping_state():
    cat = load_catalog("orca", "2.3")
    valid = {"mapped", "native_only", "deprecated", "unsupported"}
    for p in cat["parameters"]:
        assert p["mapping_status"] in valid
        if p["mapping_status"] == "mapped":
            assert p["canonical_key"]
        if p["mapping_status"] == "native_only":
            assert p["canonical_key"] is None


def test_line_width_canonical_fields_are_distinct_where_supported():
    cat = load_catalog("orca", "2.3")
    by_key = {p["native_key"]: p for p in cat["parameters"]}
    expected = {
        "line_width": "process.quality.line_width.default",
        "initial_layer_line_width": "process.quality.line_width.initial_layer",
        "outer_wall_line_width": "process.quality.line_width.outer_wall",
        "inner_wall_line_width": "process.quality.line_width.inner_wall",
        "top_surface_line_width": "process.quality.line_width.top_surface",
        "internal_solid_infill_line_width": "process.quality.line_width.internal_solid_infill",
        "sparse_infill_line_width": "process.quality.line_width.sparse_infill",
        "support_line_width": "process.quality.line_width.support",
    }
    for native_key, canonical_key in expected.items():
        assert by_key[native_key]["canonical_key"] == canonical_key


def test_filtering_visibility_profile_kind_and_search():
    cat = load_catalog("orca", "2.3")
    process_basic = filter_parameters(cat, profile_kind="process", visibility="basic")
    process_expert = filter_parameters(cat, profile_kind="process", visibility="expert")
    assert len(process_expert) >= len(process_basic)

    search = filter_parameters(cat, profile_kind="process", visibility="expert", query="outer_wall_line_width")
    assert [p["native_key"] for p in search] == ["outer_wall_line_width"]


def test_ui_grouping_uses_native_categories_and_sections():
    cat = load_catalog("orca", "2.3")
    params = filter_parameters(cat, profile_kind="process", visibility="expert", query="line_width")
    tree = group_for_ui(params)
    titles = {t["title"] for t in tree}
    assert "Quality" in titles
    sections = [s["title"] for t in tree for s in t["sections"]]
    assert "Line width" in sections


def test_catalog_editor_model_can_reset_to_native_default():
    model = CatalogEditorModel(EditorState("orca", "2.3", profile_kind="process", visibility="expert"))
    assert model.parameters()
    store = {"outer_wall_line_width": {"edited": 0.6}}
    reset = model.reset_value("outer_wall_line_width", store)
    assert reset["source"] == "native_default"
    assert reset["parameter"] == "outer_wall_line_width"


def test_catalog_validator_accepts_generated_orca_catalog():
    assert validate(CATALOG) == []


def test_catalog_list_exposes_orca_23():
    cats = list_catalogs()
    assert "orca" in cats
    assert "2.3" in cats["orca"]
    assert "bambu" in cats
    assert "2.8" in cats["bambu"]


def test_coverage_json_matches_embedded_coverage():
    embedded = json.loads(CATALOG.read_text(encoding="utf-8"))["coverage"]
    separate = json.loads(Path("parameter_catalogs/orca/2.3/coverage.json").read_text(encoding="utf-8"))
    assert separate == embedded


def test_bambu_catalog_validator_accepts_generated_catalog():
    assert validate(BAMBU_CATALOG) == []


def test_bambu_and_orca_are_not_the_same_catalog():
    orca = json.loads(CATALOG.read_text(encoding="utf-8"))["parameters"]
    bambu = json.loads(BAMBU_CATALOG.read_text(encoding="utf-8"))["parameters"]
    orca_keys = {p["native_key"] for p in orca}
    bambu_keys = {p["native_key"] for p in bambu}
    assert len(bambu_keys - orca_keys) > 0
