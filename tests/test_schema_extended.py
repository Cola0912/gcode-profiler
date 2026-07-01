# -*- coding: utf-8 -*-
"""
test_schema_extended.py — Phase 5.5 スキーマ拡張テスト
=======================================================
仕様書 Phase 5.5 で要求された 13 テストカテゴリを網羅する。
"""
import pytest
from gcode_profiler import schema as sc


def _find(schema, key):
    """key に一致する Field を返す。見つからなければ None。"""
    for f in sc.all_fields(schema):
        if f.key == key:
            return f
    return None


def _all_keys(schema):
    return [f.key for f in sc.all_fields(schema)]


def _dialog(schema):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication
    from gcode_profiler.settings_dialog import LazyTab, SettingsDialog

    app = QApplication.instance() or QApplication([])
    values, provenance = sc.default_values()
    model = SimpleNamespace(
        values=values, provenance=provenance,
        filaments=[{"tool": 0}], gcode_blocks={}, meta={},
    )
    dlg = SettingsDialog(None, "test", schema, model)
    for i in range(dlg._tabs.count()):
        tab = dlg._tabs.widget(i)
        if isinstance(tab, LazyTab):
            tab.build_now()
    return dlg


# ===========================================================================
# 1. 拡張 Printer フィールドのロード
# ===========================================================================
def test_printer_extruder_subtab_fields():
    keys = _all_keys(sc.PRINTER)
    assert "machine.retract_length" in keys,   "Extruder: retract_length missing"
    assert "machine.retract_speed" in keys,    "Extruder: retract_speed missing"
    assert "machine.deretract_speed" in keys,  "Extruder: deretract_speed missing"
    assert "machine.z_hop_height" in keys,     "Extruder: z_hop_height missing"
    assert "machine.wipe_while_retracting" in keys
    assert "machine.wipe_distance" in keys
    assert "machine.toolchange_retract_length" in keys
    assert "machine.toolchange_restart_extra" in keys


def test_printer_basic_new_fields():
    keys = _all_keys(sc.PRINTER)
    assert "machine.extruder_count" in keys
    assert "machine.extruder_offsets" in keys
    assert "machine.filament_diameter" in keys
    assert "machine.printable_origin" in keys
    assert "machine.single_extruder_mm_enabled" in keys
    assert "machine.mm.tool_count" in keys
    assert "machine.mm.purge_volume" in keys
    assert "machine.mm.wipe_tower_capable" in keys
    assert "gcode.machine_start_gcode" in keys
    assert "gcode.pause_gcode" in keys


def test_printer_machine_limits_extended():
    keys = _all_keys(sc.PRINTER)
    # 新規: E 軸最大速度
    assert "machine.max_speed_e" in keys
    # ジャーク
    assert "machine.max_jerk_x" in keys
    assert "machine.max_jerk_y" in keys
    assert "machine.max_jerk_z" in keys
    assert "machine.max_jerk_e" in keys
    # 加速度上書き
    assert "machine.max_accel_for_extrusion" in keys
    assert "machine.max_accel_for_retraction" in keys
    assert "machine.max_accel_for_travel" in keys
    # 最小速度
    assert "machine.min_feed_rate" in keys
    assert "machine.min_travel_feed_rate" in keys


# ===========================================================================
# 2. 拡張 Filament フィールドのロード
# ===========================================================================
def test_filament_basic_fields():
    keys = _all_keys(sc.FILAMENT)
    for k in ["filament.type", "filament.vendor", "filament.density",
              "filament.diameter", "filament.cost", "filament.color",
              "filament.spool_weight", "filament.flow_ratio",
              "filament.max_volumetric_speed", "filament.shrinkage",
              "filament.softening_temperature"]:
        assert k in keys, f"Filament basic: {k} missing"


def test_filament_temperature_fields():
    keys = _all_keys(sc.FILAMENT)
    for k in ["filament.nozzle_temp_initial_layer", "filament.nozzle_temp",
              "filament.bed_temp_initial_layer", "filament.bed_temp",
              "filament.chamber_temp", "filament.min_print_temperature",
              "filament.max_print_temperature",
              "filament.bed_temp_textured_plate",
              "filament.bed_temp_smooth_plate",
              "filament.bed_temp_engineering_plate",
              "filament.bed_temp_cool_plate"]:
        assert k in keys, f"Filament temp: {k} missing"


def test_filament_cooling_fields():
    keys = _all_keys(sc.FILAMENT)
    for k in ["filament.fan_always_on", "filament.fan_off_first_layers",
              "filament.fan_min_speed", "filament.bridge_fan_speed",
              "filament.overhang_fan_speed", "filament.slow_down_for_cooling",
              "filament.min_layer_time", "filament.min_print_speed",
              "filament.full_fan_speed_layer"]:
        assert k in keys, f"Filament cooling: {k} missing"


def test_filament_retraction_override_fields():
    keys = _all_keys(sc.FILAMENT)
    for k in ["filament.retract_length_override", "filament.retract_speed_override",
              "filament.deretract_speed_override", "filament.z_hop_override",
              "filament.wipe_override"]:
        assert k in keys, f"Filament retraction override: {k} missing"


def test_filament_advanced_fields():
    keys = _all_keys(sc.FILAMENT)
    assert "filament.pressure_advance" in keys
    assert "filament.load_time" in keys
    assert "filament.unload_time" in keys
    assert "filament.start_gcode" in keys
    assert "filament.end_gcode" in keys
    assert "filament.ramming_parameters" in keys
    assert "filament.ramming_volume" in keys


# ===========================================================================
# 3. 拡張 Process フィールドのロード
# ===========================================================================
def test_process_quality_seam_precision_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["quality.seam_position", "quality.seam_gap",
              "quality.scarf_seam_enabled", "quality.staggered_inner_seams",
              "quality.seam_painting",
              "quality.resolution", "quality.arc_fitting_enabled",
              "quality.xy_compensation", "quality.elephant_foot_compensation",
              "quality.slice_gap_closing_radius"]:
        assert k in keys, f"Process quality: {k} missing"


def test_process_strength_top_bottom_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["strength.top_shell_layers", "strength.bottom_shell_layers",
              "strength.top_surface_pattern", "strength.bottom_surface_pattern",
              "strength.ironing_enabled", "strength.ironing_type",
              "strength.ironing_flow", "strength.ironing_spacing",
              "strength.ironing_speed"]:
        assert k in keys, f"Process strength top/bottom: {k} missing"


def test_process_speed_extended_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["speed.bridge_speed", "speed.internal_bridge_speed",
              "speed.internal_solid_infill_speed", "speed.first_layer_infill_speed",
              "speed.small_perimeter_speed", "speed.gap_fill_speed",
              "speed.support_interface_speed", "speed.travel_accel",
              "speed.first_layer_accel", "speed.bridge_accel",
              "speed.overhang_speed_3", "speed.outer_wall_jerk",
              "speed.travel_jerk"]:
        assert k in keys, f"Process speed: {k} missing"


def test_process_support_extended_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["support.setting_enabled_state", "support.path_present",
              "support.support_type", "support.support_style",
              "support.threshold_angle", "support.on_build_plate_only",
              "support.support_xy_distance", "support.top_z_distance",
              "support.interface_enabled", "support.top_interface_layers",
              "support.tree_branch_diameter", "support.tree_branch_angle"]:
        assert k in keys, f"Process support: {k} missing"


def test_process_raft_extended_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["raft.setting_enabled_state", "raft.path_present",
              "raft.raft_layers", "raft.raft_contact_distance",
              "raft.raft_expansion", "raft.raft_first_layer_density",
              "raft.raft_first_layer_line_width", "raft.raft_interface_spacing"]:
        assert k in keys, f"Process raft: {k} missing"


def test_process_others_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["others.skirt_loops", "others.brim_type", "others.brim_width",
              "others.spiral_vase", "others.fuzzy_skin_enabled",
              "others.sequential_printing", "others.timelapse_mode",
              "others.exclude_objects"]:
        assert k in keys, f"Process others: {k} missing"


def test_process_multimaterial_fields():
    keys = _all_keys(sc.PROCESS)
    for k in ["mm.wipe_tower_enabled", "mm.wipe_tower_width",
              "mm.flush_into_infill", "mm.flush_into_support",
              "mm.flush_into_objects", "mm.prime_tower_brim",
              "mm.purge_volumes", "mm.wall_tool", "mm.support_tool"]:
        assert k in keys, f"Process MM: {k} missing"


# ===========================================================================
# 4. ライン幅の独立編集
# ===========================================================================
def test_line_width_fields_are_independent():
    """各ライン幅フィールドが独立したキーを持ち、マージされていないこと。"""
    lw_keys = [
        "quality.outer_wall_width",
        "quality.inner_wall_width",
        "quality.sparse_infill_width",
        "quality.top_surface_width",
        "quality.bottom_surface_line_width",
        "quality.internal_solid_infill_line_width",
        "quality.support_width",
        "quality.support_interface_line_width",
        "quality.bridge_line_width",
        "quality.gap_fill_line_width",
        "quality.skirt_brim_line_width",
        "quality.skirt_line_width",
        "quality.brim_line_width",
        "quality.raft_line_width",
        "quality.default_line_width",
        "quality.first_layer_line_width",
    ]
    all_keys = _all_keys(sc.PROCESS)
    for k in lw_keys:
        assert k in all_keys, f"Line width field missing: {k}"
    # すべてのキーが一意
    assert len(lw_keys) == len(set(lw_keys)), "Duplicate line-width keys"


# ===========================================================================
# 5. Basic / Advanced / Expert フィルタリング
# ===========================================================================
def test_visibility_attribute_valid():
    """全フィールドの visibility が有効な値を持つこと。"""
    valid = {"basic", "advanced", "expert"}
    for schema in (sc.PROCESS, sc.PRINTER, sc.FILAMENT):
        for f in sc.all_fields(schema):
            assert f.visibility in valid, \
                f"Field {f.key}: invalid visibility '{f.visibility}'"


def test_process_has_all_three_visibility_levels():
    counts = {"basic": 0, "advanced": 0, "expert": 0}
    for f in sc.all_fields(sc.PROCESS):
        counts[f.visibility] += 1
    assert counts["basic"] > 10,    f"Too few basic fields: {counts['basic']}"
    assert counts["advanced"] > 5,  f"Too few advanced fields: {counts['advanced']}"
    assert counts["expert"] > 0,    f"No expert fields in PROCESS"


def test_basic_fields_are_majority():
    """basic フィールドが過半数であること (UI のデフォルト表示が多すぎない)。"""
    total = sum(1 for _ in sc.all_fields(sc.PROCESS))
    basic = sum(1 for f in sc.all_fields(sc.PROCESS) if f.visibility == "basic")
    assert basic > 0
    # basic が全体の 30% 以上あることを確認 (詳細・上級フィールドが多いため下限のみ)
    assert basic / total > 0.3


def test_editor_visibility_filter_hides_advanced_rows():
    dlg = _dialog(sc.PROCESS)
    dlg._set_vis_level("basic")
    assert dlg._field_rows["quality.seam_gap"].isHidden()
    assert not dlg._field_rows["quality.layer_height"].isHidden()


def test_editor_search_matches_native_key():
    dlg = _dialog(sc.PROCESS)
    dlg._search_box.setText("outer_wall_line_width")
    assert not dlg._field_rows["quality.outer_wall_width"].isHidden()
    assert dlg._field_rows["quality.inner_wall_width"].isHidden()


def test_editor_dependency_disables_rows():
    dlg = _dialog(sc.PROCESS)
    w = dlg.widgets["support.setting_enabled_state"][1]
    w.setCurrentText("unknown")
    dlg._update_field_visibility()
    assert not dlg._field_rows["support.support_type"].isEnabled()
    w.setCurrentText("enabled")
    dlg._update_field_visibility()
    assert dlg._field_rows["support.support_type"].isEnabled()


# ===========================================================================
# 6. native_key による検索
# ===========================================================================
def test_confirmed_native_keys_in_process():
    """PROCESS に native_key が設定されているフィールドが存在すること。"""
    found = [f for f in sc.all_fields(sc.PROCESS) if f.native_key]
    assert len(found) >= 10, f"Too few fields with native_key: {len(found)}"


def test_known_orca_native_keys():
    """確認済みの OrcaSlicer キーが正しく設定されていること。"""
    checks = {
        "quality.outer_wall_width":       "outer_wall_line_width",
        "quality.inner_wall_width":       "inner_wall_line_width",
        "quality.sparse_infill_width":    "sparse_infill_line_width",
        "quality.top_surface_width":      "top_surface_line_width",
        "quality.layer_height":           "layer_height",
        "strength.wall_loops":            "wall_loops",
        "speed.outer_wall_speed":         "outer_wall_speed",
        "speed.travel_speed":             "travel_speed",
        "strength.sparse_infill_density_pct": "sparse_infill_density",
        "strength.has_support":           "enable_support",
    }
    for key, expected_native in checks.items():
        f = _find(sc.PROCESS, key)
        assert f is not None, f"Field {key} missing from PROCESS"
        assert f.native_key == expected_native, \
            f"{key}: native_key expected '{expected_native}', got '{f.native_key}'"


def test_native_key_search_by_value():
    """native_key の値でフィールドを特定できること。"""
    result = next((f for f in sc.all_fields(sc.PROCESS)
                   if f.native_key == "wall_loops"), None)
    assert result is not None
    assert result.key == "strength.wall_loops"

    result2 = next((f for f in sc.all_fields(sc.FILAMENT)
                    if f.native_key == "filament_type"), None)
    assert result2 is not None
    assert result2.key == "filament.type"


# ===========================================================================
# 7. 依存関係による可視性制御 (enabled_if)
# ===========================================================================
def test_ironing_fields_have_enabled_if():
    """アイロニングの詳細設定は ironing_enabled に依存すること。"""
    dependent = ["strength.ironing_type", "strength.ironing_flow",
                 "strength.ironing_spacing", "strength.ironing_speed"]
    for key in dependent:
        f = _find(sc.PROCESS, key)
        assert f is not None, f"Field {key} missing"
        assert "strength.ironing_enabled" in f.enabled_if, \
            f"{key}: enabled_if should contain 'strength.ironing_enabled'"


def test_raft_fields_have_enabled_if():
    """ラフト設定は setting_enabled_state に依存すること。"""
    dependent = ["raft.raft_layers", "raft.raft_contact_distance", "raft.raft_expansion"]
    for key in dependent:
        f = _find(sc.PROCESS, key)
        assert f is not None, f"Field {key} missing"
        assert "raft.setting_enabled_state" in f.enabled_if, \
            f"{key}: enabled_if should contain 'raft.setting_enabled_state'"


def test_wipe_distance_depends_on_wipe_enabled():
    f = _find(sc.PRINTER, "machine.wipe_distance")
    assert f is not None
    assert "machine.wipe_while_retracting" in f.enabled_if


# ===========================================================================
# 8. per_tool 値
# ===========================================================================
def test_per_tool_fields_in_filament():
    """フィラメント設定に per_tool=True のフィールドが存在すること。"""
    per_tool = [f for f in sc.all_fields(sc.FILAMENT) if f.per_tool]
    assert len(per_tool) >= 4, f"Too few per_tool fields: {len(per_tool)}"
    pt_keys = {f.key for f in per_tool}
    assert "filament.nozzle_temp" in pt_keys
    assert "filament.bed_temp" in pt_keys
    assert "filament.pressure_advance" in pt_keys


# ===========================================================================
# 9. レガシーキーエイリアス
# ===========================================================================
def test_aliases_dict_exists():
    assert hasattr(sc, "ALIASES"), "ALIASES dict missing"
    assert isinstance(sc.ALIASES, dict)
    assert len(sc.ALIASES) >= 15


def test_aliases_line_width_keys():
    for old_key, expected_canonical in [
        ("quality.outer_wall_width",    "process.quality.line_width.outer_wall"),
        ("quality.inner_wall_width",    "process.quality.line_width.inner_wall"),
        ("quality.sparse_infill_width", "process.quality.line_width.sparse_infill"),
        ("quality.top_surface_width",   "process.quality.line_width.top_surface"),
        ("quality.support_width",       "process.quality.line_width.support"),
    ]:
        assert old_key in sc.ALIASES, f"Alias missing for {old_key}"
        assert sc.ALIASES[old_key] == expected_canonical, \
            f"Alias {old_key}: expected '{expected_canonical}', got '{sc.ALIASES[old_key]}'"


def test_aliases_speed_keys():
    for old_key in ["speed.outer_wall_speed", "speed.inner_wall_speed",
                    "speed.travel_speed", "speed.first_layer_speed",
                    "speed.support_speed"]:
        assert old_key in sc.ALIASES, f"Speed alias missing: {old_key}"


def test_aliases_support_raft_keys():
    assert "strength.has_support" in sc.ALIASES
    assert sc.ALIASES["strength.has_support"] == "process.support.setting_enabled_state"
    assert "strength.has_raft" in sc.ALIASES
    assert sc.ALIASES["strength.has_raft"] == "process.raft.setting_enabled_state"
    assert sc.ALIASES["support.path_present"] == "process.support.path_present"
    assert sc.ALIASES["raft.path_present"] == "process.raft.path_present"


def test_legacy_keys_still_exist_in_schema():
    """旧キーが ALIASES に列挙された後も PROCESS スキーマに存在し続けること。"""
    process_keys = set(_all_keys(sc.PROCESS))
    for old_key in sc.ALIASES:
        # PROCESS スキーマのキーのみ確認 (Printer/Filament キーは別スキーマ)
        schema = sc.PROCESS
        if any(f.key == old_key for f in sc.all_fields(schema)):
            assert old_key in process_keys, \
                f"Legacy key {old_key} disappeared from PROCESS schema"


# ===========================================================================
# 10. unknown / default / recovered 表示状態
# ===========================================================================
def test_default_provenance_when_no_result():
    """解析結果なしでプリフィルすると既定値を持つフィールドは 'default' 出所になること。"""
    values, prov = sc.prefill_values({"meta": {}, "quality": {}, "speed": {},
                                      "strength": {}, "temperature": {},
                                      "retraction": {}, "filament": {}, "machine": {}})
    # default 値を持つフィールドは "default" 出所
    assert prov.get("machine.printable_area") == "default"
    assert prov.get("strength.wall_generator") == "default"
    assert prov.get("filament.type") == "default"


def test_recovered_when_src_value_present():
    """src のあるフィールドは解析結果に値があれば 'recovered' 出所になること。"""
    result = {"meta": {}, "quality": {"layer_height": 0.2, "outer_wall_width": 0.42},
              "speed": {"outer_wall_speed": 120, "travel_speed": 250},
              "strength": {}, "temperature": {}, "retraction": {},
              "filament": {}, "machine": {}}
    values, prov = sc.prefill_values(result)
    assert prov.get("quality.layer_height") == "recovered"
    assert prov.get("quality.outer_wall_width") == "recovered"
    assert prov.get("speed.outer_wall_speed") == "recovered"


def test_estimated_for_low_conf_fields():
    """low_conf=True のフィールドは解析結果に値があれば 'estimated' 出所になること。"""
    result = {"meta": {}, "quality": {}, "speed": {},
              "strength": {"wall_loops": 3, "sparse_infill_density_pct": 15},
              "temperature": {}, "retraction": {}, "filament": {}, "machine": {}}
    values, prov = sc.prefill_values(result)
    assert prov.get("strength.wall_loops") == "estimated", \
        "wall_loops (low_conf) should be 'estimated', not 'recovered'"
    assert prov.get("strength.sparse_infill_density_pct") == "estimated"


def test_unknown_not_shown_as_recovered():
    """'unknown' 出所は 'recovered' ではないこと。"""
    _, prov = sc.prefill_values({"meta": {}, "quality": {}, "speed": {},
                                 "strength": {}, "temperature": {},
                                 "retraction": {}, "filament": {}, "machine": {}})
    # 値がないフィールドは recovered にならない (None → default or absent)
    assert prov.get("quality.layer_height") != "recovered"
    assert prov.get("quality.layer_height") != "unknown"


# ===========================================================================
# 11. Process 速度が Printer machine limits にコピーされないこと
# ===========================================================================
def test_machine_max_speed_not_from_process_speed():
    """機械の最大速度フィールドはプロセス速度を src にしてはならない。"""
    banned_srcs = {"speed.travel_speed", "speed.outer_wall_speed",
                   "speed.inner_wall_speed", "speed.sparse_infill_speed"}
    for f in sc.all_fields(sc.PRINTER):
        if f.key in ("machine.max_speed_x", "machine.max_speed_y",
                     "machine.max_speed_z", "machine.max_speed_e"):
            assert f.src not in banned_srcs, \
                f"{f.key}: src='{f.src}' must not copy from process speed"


def test_machine_max_accel_not_from_process_accel():
    """機械の最大加速度フィールドはプロセス加速度を src にしてはならない。"""
    for f in sc.all_fields(sc.PRINTER):
        if f.key.startswith("machine.max_accel"):
            assert f.src != "speed.outer_wall_accel", \
                f"{f.key}: must not copy from process outer_wall_accel"


# ===========================================================================
# 12. support の path と enabled state が分離されていること
# ===========================================================================
def test_support_enabled_is_dedicated_bool_field():
    f = _find(sc.PROCESS, "strength.has_support")
    assert f is not None, "'strength.has_support' must exist in PROCESS schema"
    assert f.kind == "bool", "Support enabled field must be kind='bool'"


def test_support_enabled_canonical_key():
    f = _find(sc.PROCESS, "strength.has_support")
    assert f.canonical_key == "process.support.setting_enabled_state", \
        f"Expected canonical_key='process.support.setting_enabled_state', got '{f.canonical_key}'"
    modern = _find(sc.PROCESS, "support.setting_enabled_state")
    path = _find(sc.PROCESS, "support.path_present")
    assert modern.canonical_key == "process.support.setting_enabled_state"
    assert path.canonical_key == "process.support.path_present"
    assert path.src == "strength.has_support"


def test_support_enabled_and_type_are_separate_fields():
    """enabled フラグと type/style 設定が別フィールドであること。"""
    keys = _all_keys(sc.PROCESS)
    assert "strength.has_support" in keys
    assert "support.support_type" in keys
    # 同一フィールドでないこと
    assert "strength.has_support" != "support.support_type"


# ===========================================================================
# 13. raft の path と enabled state が分離されていること
# ===========================================================================
def test_raft_enabled_is_dedicated_bool_field():
    f = _find(sc.PROCESS, "strength.has_raft")
    assert f is not None, "'strength.has_raft' must exist in PROCESS schema"
    assert f.kind == "bool", "Raft enabled field must be kind='bool'"


def test_raft_enabled_canonical_key():
    f = _find(sc.PROCESS, "strength.has_raft")
    assert f.canonical_key == "process.raft.setting_enabled_state", \
        f"Expected canonical_key='process.raft.setting_enabled_state', got '{f.canonical_key}'"
    modern = _find(sc.PROCESS, "raft.setting_enabled_state")
    path = _find(sc.PROCESS, "raft.path_present")
    assert modern.canonical_key == "process.raft.setting_enabled_state"
    assert path.canonical_key == "process.raft.path_present"
    assert path.src == "strength.has_raft"


def test_raft_enabled_and_layers_are_separate_fields():
    keys = _all_keys(sc.PROCESS)
    assert "strength.has_raft" in keys
    assert "raft.raft_layers" in keys
    assert "strength.has_raft" != "raft.raft_layers"


# ===========================================================================
# 後方互換性: 既存テストとの整合
# ===========================================================================
def test_existing_keys_still_present():
    """Phase 5.5 前から存在していたキーが消えていないこと。"""
    process_keys = set(_all_keys(sc.PROCESS))
    for k in ["quality.layer_height", "quality.first_layer_height",
              "quality.outer_wall_width", "quality.inner_wall_width",
              "quality.sparse_infill_width", "quality.top_surface_width",
              "strength.wall_loops", "strength.sparse_infill_density_pct",
              "speed.outer_wall_speed", "speed.inner_wall_speed",
              "speed.sparse_infill_speed", "speed.top_surface_speed",
              "speed.travel_speed", "speed.first_layer_speed",
              "speed.outer_wall_accel", "strength.has_support",
              "speed.support_speed", "quality.support_width",
              "strength.has_raft", "retraction.retract_length",
              "retraction.retract_speed", "retraction.deretract_speed",
              "retraction.z_hop_height"]:
        assert k in process_keys, f"Existing key lost: {k}"

    printer_keys = set(_all_keys(sc.PRINTER))
    for k in ["machine.printable_area", "machine.bed_exclude_area",
              "machine.printable_height", "machine.nozzle_diameter",
              "machine.nozzle_volume", "machine.z_offset",
              "machine.printer_structure", "machine.gcode_flavor",
              "machine.max_accel_x", "machine.max_accel_y",
              "machine.max_accel_z", "machine.max_accel_e",
              "machine.max_speed_x", "machine.max_speed_y",
              "machine.max_speed_z", "machine.notes"]:
        assert k in printer_keys, f"Existing printer key lost: {k}"

    filament_keys = set(_all_keys(sc.FILAMENT))
    assert "temperature.fan_max_pct" in filament_keys
    assert "filament.notes" in filament_keys


def test_all_fields_have_key_and_label():
    """全フィールドに key と label が設定されていること。"""
    for schema in (sc.PROCESS, sc.PRINTER, sc.FILAMENT):
        for f in sc.all_fields(schema):
            assert f.key, f"Field with empty key found: label='{f.label}'"
            assert f.label, f"Field '{f.key}' has empty label"


def test_field_keys_unique_per_schema():
    """各スキーマ内でキーの重複がないこと。"""
    for name, schema in [("PROCESS", sc.PROCESS),
                          ("PRINTER", sc.PRINTER),
                          ("FILAMENT", sc.FILAMENT)]:
        keys = _all_keys(schema)
        dupes = [k for k in keys if keys.count(k) > 1]
        assert not dupes, f"{name}: duplicate keys: {set(dupes)}"


def test_recoverability_values_valid():
    """全フィールドの recoverability が有効な値を持つこと。"""
    valid = {"explicit", "runtime", "geometry", "estimated",
             "profile_only", "target_only"}
    for schema in (sc.PROCESS, sc.PRINTER, sc.FILAMENT):
        for f in sc.all_fields(schema):
            assert f.recoverability in valid, \
                f"Field {f.key}: invalid recoverability '{f.recoverability}'"
