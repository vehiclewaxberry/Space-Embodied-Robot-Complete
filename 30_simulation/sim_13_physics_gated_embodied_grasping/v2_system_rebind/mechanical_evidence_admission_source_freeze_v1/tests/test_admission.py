from __future__ import annotations

from mechanical_admission.evaluator import GATE_CEILING, STATUS_ENUM, validate_publication_candidate


def test_source_only_admission_passes_at_ceiling(evaluation):
    assert evaluation["source_only_validation_pass"] is True
    assert evaluation["evaluation_status"] == GATE_CEILING
    assert evaluation["checks_passed"] == evaluation["checks_total"]


def test_required_topology_and_b601_subtree_are_reconstructed(evaluation):
    checks = evaluation["checks"]
    for name in (
        "topology_total_links_exact",
        "topology_physical_links_exact",
        "topology_frame_only_links_exact",
        "topology_joints_exact",
        "topology_actuated_dof_exact",
        "topology_fixed_10",
        "topology_revolute_6",
        "topology_prismatic_2",
        "b601_link_subtree_exact_10",
        "b601_joint_subtree_exact_9_ordered",
        "accepted_urdf_exact_fields_match_frame_tree",
    ):
        assert checks[name] is True


def test_D_M_numeric_equality_never_becomes_semantic_alias(evaluation):
    assert evaluation["checks"]["D_M_numeric_transforms_equal"] is True
    assert evaluation["checks"]["D_M_semantic_identities_distinct"] is True
    assert evaluation["checks"]["physical_load_path_exact_and_excludes_M"] is True


def test_mass_anti_double_count(evaluation):
    assert evaluation["checks"]["bus_mass_recomposes_without_double_count"] is True
    assert evaluation["checks"]["prohibited_double_count_is_not_selected_total"] is True
    assert evaluation["quantities"]["whole_system_design_mass"]["value"] == 31.022864807342987
    assert evaluation["quantities"]["whole_system_design_mass"]["status"] == "DESIGN_CANDIDATE"


def test_machine_policy_separations(evaluation):
    policy = evaluation["machine_policy_results"]
    assert policy == {
        "mesh_loadable_is_collision_authority": False,
        "urdf_velocity_is_physical_velocity_authority": False,
        "candidate_trajectory_is_released_trajectory": False,
        "physical_contact_zero_fill_permitted": False,
    }
    assert evaluation["checks"]["mesh_loadable_does_not_imply_collision_authority"] is True
    assert evaluation["checks"]["urdf_velocity_not_physical_velocity"] is True
    assert evaluation["checks"]["candidate_trajectory_is_not_released"] is True


def test_every_exposed_quantity_has_full_semantics(evaluation):
    required = {"value", "unit", "coordinate_frame", "reference_point", "authority", "status", "source_artifact", "source_field"}
    assert evaluation["quantities"]
    for quantity in evaluation["quantities"].values():
        assert set(quantity) == required
        assert quantity["status"] in STATUS_ENUM


def test_status_enum_is_exact_and_all_states_are_used(evaluation):
    observed = {item["status"] for item in evaluation["domain_ledger"].values()}
    assert observed == set(STATUS_ENUM)


def test_all_execution_and_release_outputs_remain_false(evaluation):
    for field in (
        "system_urdf_available",
        "current_system_bound",
        "physical_contact_ready",
        "dynamics_capture_entry_authorized",
        "next_stage_authorized",
    ):
        assert evaluation[field] is False
    validate_publication_candidate(evaluation)
