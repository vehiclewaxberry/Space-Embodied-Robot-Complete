import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("validate_odr60_option_a_preflight.py")
SPEC = importlib.util.spec_from_file_location("odr60_preflight", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_integrity_and_frozen_endpoints_pass():
    result = MODULE.evaluate()
    assert result["package_integrity_pass"] is True
    assert result["endpoints"]["start_match"] is True
    assert result["endpoints"]["goal_match"] is True
    assert result["endpoints"]["robust_inset_pass"] is True
    assert result["urdf"]["links"] == 10
    assert result["urdf"]["joints"] == 9
    assert result["urdf"]["revolute"] == 6
    assert result["urdf"]["prismatic"] == 2


def test_collision_semantics_are_narrow_and_fail_closed():
    result = MODULE.evaluate()
    collision = result["collision_semantics"]
    assert collision["adjacent_pair_count"] == 9
    assert collision["adjacent_pairs_match"] is True
    assert collision["finger_pair_collision_enabled"] is True
    assert collision["route_c_interface_rule_count"] == 15
    assert collision["route_c_interface_rules_normalized"] is True
    assert collision["candidate_local_window_pair_records"] == 55
    assert collision["candidate_windows_active_as_exceptions"] is False
    assert collision["legacy_segment_wide_groups_rejected"] == 8
    assert collision["legacy_segment_part_memberships_rejected"] == 91
    assert collision["j4_whole_segment_exemption_forbidden"] is True
    assert collision["known_active_object_count"] == 150
    assert collision["object_counts"] == {"F": 4, "A": 10, "S": 6, "R": 121, "C": 9}
    assert collision["pair_universe_count"] == 11175
    assert collision["adjacent_pair_exceptions"] == 9
    assert collision["unassessed_fail_closed_pairs"] == 11166
    assert collision["conditional_solar_keepouts_not_activated"] == 10
    assert collision["raw_urdf_base_link_mesh_consumed"] is False
    assert collision["base_link_raw_mesh_conflict_contained"] is True
    assert collision["base_link_operational_proxy_pass"] is True
    assert collision["base_link_v2_receipt_and_validation_consistent"] is True
    assert collision["complete_hash_bound_acm"] is False
    assert collision["complete_system_collision_pass"] is False


def test_preflight_does_not_authorize_search_or_release():
    result = MODULE.evaluate()
    assert result["owner_authority_present"] is False
    assert result["pre_search_ready"] is False
    assert result["system_pair_evaluation_authorized"] is False
    assert result["path_search_authorized"] is False
    assert result["path_search_executed"] is False
    assert result["next_stage_authorized"] is False
    assert result["release_credit"] is False
    assert "ODR60_OPTION_A_OWNER_SELECTION_ABSENT" in result["blockers"]
    assert "BASE_LINK_OPERATIONAL_COLLISION_PROXY_HOLD" not in result["blockers"]
    assert "COMPLETE_HASH_BOUND_ACM_ABSENT" in result["blockers"]
    assert result["scene_state"]["complete"] is False
