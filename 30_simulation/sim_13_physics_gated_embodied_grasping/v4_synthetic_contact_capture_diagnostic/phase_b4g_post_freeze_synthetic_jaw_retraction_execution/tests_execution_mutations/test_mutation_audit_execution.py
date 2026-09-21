from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import sys
from types import MethodType

import numpy as np
import pytest


PHASE_ROOT = Path(__file__).resolve().parents[1]
if str(PHASE_ROOT) not in sys.path:
    sys.path.insert(0, str(PHASE_ROOT))

import run_phase_b4g_mutation_audit as mutation  # noqa: E402
from b4g_validation.core import canonical_sha256  # noqa: E402
from b4g_validation.mutation_replay import (  # noqa: E402
    apply_restricted_patch,
    evaluate_payload,
    validate_patch_semantics,
)
from b4g_validation.supplemental_replay import (  # noqa: E402
    validate_supplemental_trace,
)


@pytest.fixture(scope="module")
def temp_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("b4g_mutation_adapter")


def new_audit(temp_root: Path, name: str) -> mutation.MutationAudit:
    return mutation.MutationAudit(output_root=temp_root / name)


def artifact_path(record: dict) -> Path:
    path = Path(record["path"])
    return path if path.is_absolute() else mutation.PROJECT_ROOT / path


def independently_replay(audit: mutation.MutationAudit, receipt) -> tuple[bool, bool]:
    base = mutation._read_json(artifact_path(receipt.base_artifact))
    mutant = mutation._read_json(artifact_path(receipt.mutant_artifact))
    patch = mutation._read_json(artifact_path(receipt.patch_artifact))
    assert apply_restricted_patch(base, patch) == mutant
    assert validate_patch_semantics(
        parent_id=receipt.parent_id,
        subvariant_index=receipt.subvariant_index,
        target=receipt.target,
        patch=patch,
        base_payload=base["payload"],
        mutation_spec=audit.spec,
        frozen_q_ref=mutation.forced.REFERENCE_FORCE_N,
    )
    kwargs = {
        "parent_id": receipt.parent_id,
        "frozen_schedule": audit.schedule,
        "frozen_q_ref": mutation.forced.REFERENCE_FORCE_N,
        "mutation_spec": audit.spec,
        "required_false": audit.governance["required_false"],
        "required_null_names": audit.governance["required_null_physical_inputs"],
        "project_root": mutation.PROJECT_ROOT,
        "phase_root": mutation.PHASE_ROOT,
    }
    replay_type = receipt.base_artifact["replay_type"]
    return (
        evaluate_payload(replay_type, receipt.expected_gate, base["payload"], **kwargs),
        evaluate_payload(replay_type, receipt.expected_gate, mutant["payload"], **kwargs),
    )


def independently_replay_supplemental(audit: mutation.MutationAudit, receipt):
    bundle = mutation._read_json(artifact_path(receipt.base_artifact))
    return validate_supplemental_trace(
        receipt.parent_id,
        receipt.subvariant_index,
        bundle["artifact_records"],
        project_root=mutation.PROJECT_ROOT,
        phase_root=mutation.PHASE_ROOT,
        mutation_spec=audit.spec,
        frozen_schedule=audit.schedule,
        frozen_q_ref=mutation.forced.REFERENCE_FORCE_N,
        base_payload=bundle["payload"],
    )


def test_frozen_inventory_and_preregistration_anchors_are_exact(temp_root):
    audit = new_audit(temp_root, "inventory")
    assert audit.spec["required_parent_ids"] == [f"B4FNC{i:02d}" for i in range(1, 23)]
    assert sum(row["count"] for row in audit.variant_rows) == 65
    assert audit.source_binding["all_verified"] is True
    assert len(audit.source_binding["bound_parent_sources"]) == 11
    assert all(row["passed"] for row in audit.source_binding["bound_parent_sources"])


def test_duplicate_json_keys_fail_closed(temp_root):
    path = temp_root / "duplicate.json"
    path.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(mutation.MutationAuditError, match="JSON_READ_FAILED"):
        mutation._read_json(path)


def test_bundle_has_non_circular_replay_and_exact_underlying_inventory(temp_root):
    audit = new_audit(temp_root, "nc01")
    audit.nc01()
    receipt = audit.receipts[0]
    row = receipt.as_dict()
    assert not {"actual_failed_gate", "nominal_gate_sha256", "mutant_gate_sha256"} & set(row)
    assert set(row["replay"]) == {
        "schema", "evaluator_id", "independent_validator_path",
        "independent_validator_sha256",
    }
    base = mutation._read_json(artifact_path(receipt.base_artifact))
    records = base["artifact_records"]
    assert len(records) >= 2
    assert records[0]["role"] == "EXECUTION_SOURCE_MANIFEST"
    assert base["execution_provenance"]["underlying_artifact_inventory_sha256"] == canonical_sha256(records)
    assert independently_replay(audit, receipt) == (True, False)


def test_classifier_and_schedule_groups_replay_to_exact_single_gate_failures(temp_root):
    audit = new_audit(temp_root, "classifier_schedule")
    audit.nc09(); audit.nc10(); audit.nc16()
    assert len(audit.receipts) == 5
    assert all(independently_replay(audit, row) == (True, False) for row in audit.receipts)
    for index, receipt in enumerate(row for row in audit.receipts if row.parent_id == "B4FNC16"):
        patch = mutation._read_json(artifact_path(receipt.patch_artifact))
        assert patch["operations"] == [{
            "op": "add", "path": "/payload/schedule/slots/-",
            "value": audit.targets["unregistered_levels"][index],
        }]


def test_governance_and_reporting_cover_all_exact_frozen_fields(temp_root):
    audit = new_audit(temp_root, "governance")
    audit.nc18_20(); audit.nc22()
    assert len(audit.receipts) == 24
    assert [row.parent_id for row in audit.receipts].count("B4FNC19") == 10
    assert [row.parent_id for row in audit.receipts].count("B4FNC20") == 11
    assert all(independently_replay(audit, row) == (True, False) for row in audit.receipts)


def _mock_registered_raw(audit: mutation.MutationAudit, root: Path) -> None:
    root.mkdir(parents=True)
    qref = mutation.forced.REFERENCE_FORCE_N
    a0_id = audit.targets["a0_slot"]
    a1_id = audit.targets["default_registered_forced_slot"]
    a0_slot = next(row for row in audit.schedule["slots"] if row["case_id"] == a0_id)
    a1_slot = next(row for row in audit.schedule["slots"] if row["case_id"] == a1_id)

    def metadata(slot, command, name, *, event=None, acquisition=None):
        path = root / f"{name}.json"
        acquisition_time = 0.0 if acquisition is None else float(acquisition.acquisition_time_s)
        certificate_payload = None
        if event is not None and acquisition is not None:
            certificate_payload = {
                "lane_id": slot["lane_id"],
                "case_id": slot["case_id"],
                "event": mutation.forced.b4e.event_to_json(event),
                "acquisition": mutation.forced.b4e.acquisition_to_json(
                    acquisition, include_matrices=False,
                ),
            }
        value = {
            "case_id": slot["case_id"], "terminal_status": "TEST_EXECUTED",
            "event_provenance": {
                "acquisition_time_s": acquisition_time,
                "acquisition_certificate_payload": certificate_payload,
            },
            "command_parameters": {
                "Q_ref_per_finger_N": qref,
                "left": deepcopy(command.left.__dict__),
                "right": deepcopy(command.right.__dict__),
            },
        }
        mutation._atomic_write_json(path, value)
        return value, path

    a0_command = mutation.forced.ForcedCommand.zero()
    a1_command = mutation.campaign.command_for_slot(a1_slot, selected_parent=None)
    event = mutation.forced.b4e.rerun_b3_to_event(
        a1_id, a1_slot["method"], a1_slot["step_s"],
    )
    model = mutation.forced.b4e.BranchedGripperServiceModel()
    acquisition = mutation.forced.b4e.acquisition_projection(model, event)
    service = mutation.forced.b4e.ServiceState(
        event.service.base_position_inertial_m.copy(),
        event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(),
        acquisition.eta_plus.copy(),
    )
    service_vector = mutation.forced.b4e._service_to_active_vector(service)
    opening = mutation.forced.opening_signs(model, service, acquisition.snapshot)
    a0_meta, a0_meta_path = metadata(a0_slot, a0_command, "a0")
    a1_meta, a1_meta_path = metadata(
        a1_slot, a1_command, "a1", event=event, acquisition=acquisition,
    )
    a0_time = np.asarray([0.0]); a0_q = np.zeros((1, 14))
    times = float(acquisition.acquisition_time_s) + np.asarray([0.0, 0.005, 0.01])
    a1_q = np.asarray([
        mutation.forced.force_vector(
            a1_command, time, float(acquisition.acquisition_time_s), qref,
        ) for time in times
    ])
    state = np.repeat(service_vector[None, :], 3, axis=0)
    state[:, 27:29] = [[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]]
    power = np.sum(a1_q[:, 12:14] * state[:, 27:29], axis=1)
    work = np.asarray([
        0.0,
        0.5 * (power[0] + power[1]) * (times[1] - times[0]),
        0.5 * (power[0] + power[1]) * (times[1] - times[0])
        + 0.5 * (power[1] + power[2]) * (times[2] - times[1]),
    ])
    stages = {
        "stage_time_s": np.asarray([float(acquisition.acquisition_time_s)]),
        "stage_service_state_29": service_vector[None, :],
        "stage_P_coordinates_m": opening.p_coordinates_m[None, :],
        "stage_gap_jacobian_P": opening.raw_gap_jacobian[None, :, :],
    }
    a0_arrays = {"time_s": a0_time, "command_Q_14": a0_q, **stages}
    a1_arrays = {
        "time_s": times, "command_Q_14": a1_q, "service_state_29": state,
        "signed_W_act_J": work, "energy_minus_work_residual_J": np.zeros(3),
        **stages,
    }
    a0_npz = root / "a0.npz"; a1_npz = root / "a1.npz"
    np.savez(a0_npz, **a0_arrays); np.savez(a1_npz, **a1_arrays)
    table = {
        a0_id: (a0_meta, a0_arrays, a0_meta_path, a0_npz),
        a1_id: (a1_meta, a1_arrays, a1_meta_path, a1_npz),
    }

    def registered(self, case_id):
        return table[case_id]

    audit._registered_case = MethodType(registered, audit)


def test_registered_raw_groups_nc02_to_nc06_and_nc21(temp_root):
    audit = new_audit(temp_root, "registered_raw")
    _mock_registered_raw(audit, audit.output_root / "mock_campaign")
    audit.nc02(); audit.nc03(); audit.nc04(); audit.nc05_06(); audit.nc21()
    assert len(audit.receipts) == 24
    assert all(independently_replay(audit, row) == (True, False) for row in audit.receipts)
    assert all(
        mutation._read_json(artifact_path(row.base_artifact))["payload"].get("trace_origin")
        == "REGISTERED_CAMPAIGN_CASE"
        for row in audit.receipts if row.parent_id in {"B4FNC02", "B4FNC03"}
    )
    nc21_rows = [row for row in audit.receipts if row.parent_id == "B4FNC21"]
    assert len(nc21_rows) == 6
    for receipt in nc21_rows:
        supplemental = independently_replay_supplemental(audit, receipt)
        assert supplemental.role == "GEOMETRY_CLIP_EXTRAPOLATE_TRACE"
        assert supplemental.diagnostics["independent_g16_predicate"] is False


@pytest.fixture(scope="module")
def finite_audit(temp_root):
    audit = new_audit(temp_root, "finite")
    fixture = audit.finite_fixture()
    audit._finite_harness_raw_path(fixture)
    return audit


def test_finite_harness_raw_is_complete_and_precondition_is_not_credit(finite_audit):
    fixture = finite_audit.finite_fixture(); precondition = fixture["precondition"]
    assert precondition["passed"] is True
    assert precondition["finite_removal_event"] is True
    assert precondition["abs_W_act_at_removal_J"] > 1.0e-12
    assert precondition["physical_current_or_formal_credit"] is False
    raw = mutation._read_json(finite_audit._finite_harness_raw_path(fixture))
    assert raw["event"] and raw["acquisition"] and raw["command"]
    assert raw["post_release"]["mapping"] and raw["post_release"]["instrumented_trace"]
    for field in (
        "time_s", "command_Q_14", "service_state_29", "signed_W_act_J",
        "left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
        "ledger_interval_certified",
    ):
        assert field in raw["raw"]


def test_all_finite_dependent_groups_share_raw_and_replay(finite_audit):
    before = len(finite_audit.receipts)
    finite_audit.nc07(); finite_audit.nc08(); finite_audit.nc11()
    finite_audit.nc12(); finite_audit.nc13(); finite_audit.nc14()
    receipts = finite_audit.receipts[before:]
    assert len(receipts) == 7
    replay_results = {
        row.receipt_id: independently_replay(finite_audit, row) for row in receipts
    }
    for receipt_id, value in replay_results.items():
        assert value == (True, False), f"{receipt_id}:{value}"
    raw_paths = {
        next(
            record["path"] for record in mutation._read_json(artifact_path(row.base_artifact))["artifact_records"]
            if record["role"] == "EXECUTED_FINITE_HARNESS_RAW_OUTPUT"
        )
        for row in receipts
    }
    assert len(raw_paths) == 1
    for row in (item for item in receipts if item.parent_id == "B4FNC08"):
        base = mutation._read_json(artifact_path(row.base_artifact))["payload"]
        assert base["trace_origin"] == "FROZEN_FINITE_EVENT_HARNESS"
        assert base["observed_Q_14"] == [0.0] * 14
        supplemental = independently_replay_supplemental(finite_audit, row)
        assert supplemental.role == "MUTANT_DWELL_FORCE_TRACE"
        assert supplemental.diagnostics["independent_g08_predicate"] is False

    nc11 = next(row for row in receipts if row.parent_id == "B4FNC11")
    nc11_base = mutation._read_json(artifact_path(nc11.base_artifact))["payload"]
    finite_raw = mutation._read_json(
        finite_audit._finite_harness_raw_path(finite_audit.finite_fixture())
    )
    mapping = finite_raw["post_release"]["mapping"]
    assert nc11_base == {
        field: mapping[field] for field in (
            "z_before", "z_after", "linear_impulse_N_s",
            "angular_impulse_N_m_s", "kinetic_energy_jump_J",
            "ideal_constraint_stored_energy_J",
        )
    }
    assert nc11_base["angular_impulse_N_m_s"][0] == 2.7755575615628914e-17

    nc12 = next(row for row in receipts if row.parent_id == "B4FNC12")
    detail = nc12.execution_detail
    assert detail["root_selection_rule"] == "MINIMUM_ABSOLUTE_BETA_TIES_CHOOSE_POSITIVE"
    assert min(
        (detail["root_minus"], detail["root_plus"]),
        key=lambda value: (abs(value), value < 0.0),
    ) == detail["selected_beta"]
    assert abs(
        detail["achieved_kinetic_increment_J"]
        - finite_audit.finite_fixture()["acquisition"].energy_audit["D_switch_J"]
    ) <= 1.0e-10


def _campaign_pair_fixture(audit: mutation.MutationAudit) -> None:
    root = audit.output_root / "mock_pair_campaign"; root.mkdir(parents=True)
    suffix = "__A1__ALPHA_2__TCMD_MS_10"

    def case(lane, acq, cert, clear, work):
        return {
            "event_provenance": {
                "lane_id": lane, "fresh_b3_reconstruction": True,
                "acquisition_time_s": acq, "removal_time_s": acq + 0.002,
                "acquisition_certificate_sha256": cert,
                "clearance_certificate_sha256": clear,
            },
            "responses": {
                "signed_work_terminal_J": work, "finite_removal_event": True,
                "post_release_passed": True, "selector_case_integrity_pass": True,
            },
        }

    metadata = {}
    for lane, acq, cert, clear, work in (
        ("RK4_REFERENCE", 0.1, "A" * 64, "B" * 64, 1.0e-5),
        ("MIDPOINT_REFERENCE", 0.1001, "C" * 64, "D" * 64, 1.00001e-5),
    ):
        case_id = lane + suffix; path = root / f"{lane}.json"
        value = case(lane, acq, cert, clear, work)
        mutation._atomic_write_json(path, value); metadata[case_id] = (value, path)
    a2_slots = [row for row in audit.schedule["slots"] if row["arm"] == "A2"]
    for slot in a2_slots:
        value = {
            "arm": "A2", "execution_status": "EXECUTED_FRESH_REGISTERED_SLOT",
            "registered_slot": slot,
        }
        path = root / f"{slot['case_id']}.json"
        mutation._atomic_write_json(path, value); metadata[slot["case_id"]] = (value, path)
    assert len(a2_slots) == 24
    audit._campaign_summary = {
        "selector": {"selected_parent_level": {"alpha": 2.0, "command_duration_s": 0.01}}
    }
    audit._metadata_cache = metadata


def test_reference_pair_and_full_a2_six_lane_adapter(temp_root):
    audit = new_audit(temp_root, "reference_a2")
    _campaign_pair_fixture(audit)
    audit.nc15(); audit.nc17()
    assert len(audit.receipts) == 4
    assert all(independently_replay(audit, row) == (True, False) for row in audit.receipts)
    for receipt in audit.receipts[2:]:
        assert receipt.target == [f"/payload/lanes/{index}/right_Q_2/1" for index in range(6)]


def test_nc17_no_parent_runs_full_algorithm_only_six_lane_detector(temp_root):
    audit = new_audit(temp_root, "nc17_no_parent")
    audit._campaign_summary = {"selector": {"selected_parent_level": None}}
    audit._metadata_cache = {}
    audit.nc17()
    assert len(audit.receipts) == 2
    assert all(row.killed for row in audit.receipts)
    records = [
        next(
            record for record in mutation._read_json(artifact_path(row.base_artifact))[
                "artifact_records"
            ]
            if record["role"] == "A2_DETECTOR_SIX_LANE_TRACE"
        )
        for row in audit.receipts
    ]
    assert records[0] == records[1]
    raw = mutation._read_json(artifact_path(records[0]))
    assert raw["harness_id"] == "ALGORITHM_ONLY_A2_DETECTOR_HARNESS"
    assert len(raw["lanes"]) == 6
    assert all(len(row["traces"]) == 6 for row in raw["lanes"])
    assert all(row["relative_time_s"][0] == 0.0 for row in raw["lanes"])
    assert all(row["relative_time_s"][-1] == 0.08 for row in raw["lanes"])
    assert raw["capabilities"] == {
        "a1_outcome_credit": False,
        "a2_outcome_credit": False,
        "physical_credit": False,
        "current_system_bound": False,
    }
    for receipt in audit.receipts:
        supplemental = independently_replay_supplemental(audit, receipt)
        assert supplemental.role == "A2_DETECTOR_SIX_LANE_TRACE"
        assert supplemental.diagnostics["detector_pair_count"] == 24
        assert supplemental.diagnostics["all_base_pair_predicates_true"] is True
        assert supplemental.diagnostics["all_mutant_pair_predicates_false"] is True


def test_stale_full_is_invalidated_only_inside_exact_output_root(temp_root):
    audit = new_audit(temp_root, "stale")
    mutation._atomic_write_json(audit._output_path(mutation.FULL_OUTPUT_PATH.name), {"stale": True})
    (audit.output_root / "artifacts").mkdir(); (audit.output_root / "artifacts" / "x").write_text("x")
    (audit.output_root / "underlying").mkdir(); (audit.output_root / "underlying" / "x").write_text("x")
    unrelated = audit.output_root / "preserve.txt"; unrelated.write_text("preserve")
    audit._prepare_attempt(mode="FULL_65")
    assert not audit._output_path(mutation.FULL_OUTPUT_PATH.name).exists()
    assert not (audit.output_root / "artifacts").exists()
    assert not (audit.output_root / "underlying").exists()
    assert unrelated.read_text() == "preserve"
    incomplete = mutation._read_json(audit._output_path(mutation.INCOMPLETE_OUTPUT_PATH.name))
    assert incomplete["status"] == "INCOMPLETE" and incomplete["final"] is False


def test_nonformal_mutation_output_requires_narrow_preowned_root(
    temp_root, monkeypatch,
):
    project = temp_root / "project"
    phase = project / "phase"
    phase.mkdir(parents=True)
    monkeypatch.setattr(mutation, "PROJECT_ROOT", project)
    monkeypatch.setattr(mutation, "PHASE_ROOT", phase)
    monkeypatch.setattr(mutation, "OUTPUT_ROOT", phase / "b4g_mutation_execution")
    with pytest.raises(mutation.MutationAuditError, match="OUTPUT_ROOT_TOO_BROAD"):
        mutation._safe_output_root(Path(temp_root.anchor))
    with pytest.raises(mutation.MutationAuditError, match="OUTPUT_ROOT_TOO_BROAD"):
        mutation._safe_output_root(project.parent)

    unmarked = temp_root / "existing_unmarked"
    unmarked.mkdir()
    sentinel = unmarked / "preserve.txt"
    sentinel.write_text("preserve\n", encoding="utf-8")
    with pytest.raises(
        mutation.MutationAuditError,
        match="MUTATION_EXISTING_NONEMPTY_OUTPUT_ROOT_REQUIRES_MARKER",
    ):
        mutation._safe_output_root(unmarked)
    assert sentinel.read_text(encoding="utf-8") == "preserve\n"
    assert not (unmarked / mutation.OUTPUT_ROOT_MARKER).exists()

    empty = temp_root / "existing_empty"
    empty.mkdir()
    owned, formal = mutation._safe_output_root(empty)
    assert owned == empty.resolve() and formal is False
    assert (owned / mutation.OUTPUT_ROOT_MARKER).read_text(
        encoding="utf-8",
    ) == "SIM13_V4B4G_MUTATION_OUTPUT_ROOT_V1\n"

    inside_phase = phase / "contracts/diagnostic_mutation"
    with pytest.raises(
        mutation.MutationAuditError,
        match="CUSTOM_OUTPUT_ROOT_OVERLAPS_PHASE_ROOT",
    ):
        mutation._safe_output_root(inside_phase)
    assert not inside_phase.exists()

    marker = owned / mutation.OUTPUT_ROOT_MARKER
    original = mutation._is_mutation_link_or_reparse
    monkeypatch.setattr(
        mutation,
        "_is_mutation_link_or_reparse",
        lambda path: True if Path(path) == marker else original(path),
    )
    with pytest.raises(
        mutation.MutationAuditError,
        match="OUTPUT_ROOT_MARKER_NOT_PLAIN_FILE",
    ):
        mutation._safe_output_root(owned)


def _old_full_output(root: Path) -> Path:
    safe_root, _ = mutation._safe_output_root(root)
    final = safe_root / mutation.FULL_OUTPUT_PATH.name
    mutation._atomic_write_json(final, {"schema": "STALE_FORMAL_CREDIT"})
    return final


def test_cli_invalidates_old_full_before_missing_campaign_failure(
    temp_root, monkeypatch,
):
    root = temp_root / "missing_campaign_attempt"
    stale = _old_full_output(root)
    monkeypatch.setattr(
        mutation, "CAMPAIGN_SUMMARY_PATH", root / "missing_campaign.json",
    )
    with pytest.raises(
        mutation.MutationAuditError,
        match="CAMPAIGN_SUMMARY_REQUIRED_FOR_FULL_MUTATION_EXECUTION",
    ):
        mutation.main(["--execute", "--output-root", str(root), "--no-write"])
    assert not stale.exists()
    incomplete = mutation._read_json(root / mutation.INCOMPLETE_OUTPUT_PATH.name)
    assert incomplete["status"] == "INCOMPLETE"


def test_cli_invalidates_old_full_before_constructor_source_drift(
    temp_root, monkeypatch,
):
    root = temp_root / "constructor_source_drift_attempt"
    stale = _old_full_output(root)

    def source_drift(self):
        raise mutation.MutationAuditError("TEST_CONSTRUCTOR_SOURCE_DRIFT")

    monkeypatch.setattr(mutation.MutationAudit, "_verify_source_binding", source_drift)
    with pytest.raises(mutation.MutationAuditError, match="TEST_CONSTRUCTOR_SOURCE_DRIFT"):
        mutation.main(["--execute", "--output-root", str(root), "--no-write"])
    assert not stale.exists()
    incomplete = mutation._read_json(root / mutation.INCOMPLETE_OUTPUT_PATH.name)
    assert incomplete["status"] == "INCOMPLETE"


def test_cleanup_failure_still_leaves_atomic_incomplete_and_no_stale_full(
    temp_root, monkeypatch,
):
    root = temp_root / "cleanup_failure_attempt"
    stale = _old_full_output(root)
    artifacts = root / "artifacts"
    artifacts.mkdir()
    (artifacts / "owned.json").write_text("{}", encoding="utf-8")

    def fail_cleanup(_path):
        raise OSError("TEST_OWNED_TREE_CLEANUP_FAILURE")

    monkeypatch.setattr(mutation.shutil, "rmtree", fail_cleanup)
    with pytest.raises(OSError, match="TEST_OWNED_TREE_CLEANUP_FAILURE"):
        mutation._bootstrap_attempt(root, mode="FULL_65")
    assert not stale.exists()
    incomplete = mutation._read_json(root / mutation.INCOMPLETE_OUTPUT_PATH.name)
    assert incomplete["status"] == "INCOMPLETE"


def test_formal_full_bootstrap_revokes_all_downstream_final_credit_before_constructor_failure(
    temp_root, monkeypatch,
):
    phase = temp_root / "formal_phase"
    formal_output = phase / "b4g_mutation_execution"
    monkeypatch.setattr(mutation, "PHASE_ROOT", phase)
    monkeypatch.setattr(mutation, "OUTPUT_ROOT", formal_output)
    for relative in mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS:
        path = phase / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        mutation._atomic_write_json(path, {"schema": "STALE_DOWNSTREAM_FINAL"})

    def source_drift(self):
        assert all(
            not (phase / relative).exists()
            for relative in mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS
        )
        raise mutation.MutationAuditError("TEST_FORMAL_CONSTRUCTOR_SOURCE_DRIFT")

    monkeypatch.setattr(mutation.MutationAudit, "_verify_source_binding", source_drift)
    with pytest.raises(
        mutation.MutationAuditError,
        match="TEST_FORMAL_CONSTRUCTOR_SOURCE_DRIFT",
    ):
        mutation.main(["--execute"])
    assert all(
        not (phase / relative).exists()
        for relative in mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS
    )
    incomplete = mutation._read_json(
        formal_output / mutation.INCOMPLETE_OUTPUT_PATH.name
    )
    assert incomplete["status"] == "INCOMPLETE"
    assert incomplete["formal_downstream_final_credit_revoked"] is True
    assert len(incomplete["downstream_final_artifacts_removed"]) == len(
        mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS
    )


def test_mutation_cleanup_unlinks_lexical_links_without_deleting_referents(
    temp_root, monkeypatch,
):
    phase = temp_root / "link_safe_phase"
    formal_output = phase / "b4g_mutation_execution"
    monkeypatch.setattr(mutation, "PHASE_ROOT", phase)
    monkeypatch.setattr(mutation, "OUTPUT_ROOT", formal_output)
    mutation._safe_output_root(formal_output)
    downstream = phase / mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS[0]
    downstream.parent.mkdir(parents=True, exist_ok=True)
    downstream.write_text("SIMULATED_LINK\n", encoding="utf-8")
    stale_full = formal_output / mutation.FULL_OUTPUT_PATH.name
    stale_full.write_text("SIMULATED_LINK\n", encoding="utf-8")
    artifacts = formal_output / "artifacts"
    artifacts.write_text("SIMULATED_LINK\n", encoding="utf-8")
    external = temp_root / "external_referent.bin"
    external.write_bytes(b"must-survive")
    simulated_links = {downstream, stale_full, artifacts}
    original_is_symlink = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: True if path in simulated_links else original_is_symlink(path),
    )

    removed = mutation._revoke_downstream_final_credit()
    assert removed[0]["object_type"] == "SYMLINK"
    assert not downstream.exists()
    mutation._bootstrap_attempt(formal_output, mode="FULL_65")
    assert not stale_full.exists()
    assert not artifacts.exists()
    assert external.read_bytes() == b"must-survive"


def test_smoke_requires_explicit_nonformal_output_and_preserves_formal_artifacts(
    temp_root, monkeypatch,
):
    phase = temp_root / "smoke_formal_phase"
    formal_output = phase / "b4g_mutation_execution"
    monkeypatch.setattr(mutation, "PHASE_ROOT", phase)
    monkeypatch.setattr(mutation, "OUTPUT_ROOT", formal_output)
    owned = formal_output / "artifacts" / "preserve.json"
    owned.parent.mkdir(parents=True)
    owned.write_text("{}", encoding="utf-8")
    with pytest.raises(
        mutation.MutationAuditError,
        match="MUTATION_SMOKE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT",
    ):
        mutation.main(["--smoke"])
    assert owned.is_file()
    with pytest.raises(
        mutation.MutationAuditError,
        match="MUTATION_SMOKE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT",
    ):
        mutation._bootstrap_attempt(formal_output, mode="SMOKE")
    assert owned.is_file()


def test_no_write_rejects_formal_root_before_any_attempt_write(
    temp_root, monkeypatch,
):
    phase = temp_root / "no_write_formal_phase"
    formal_output = phase / "b4g_mutation_execution"
    monkeypatch.setattr(mutation, "PHASE_ROOT", phase)
    monkeypatch.setattr(mutation, "OUTPUT_ROOT", formal_output)
    owned = formal_output / "artifacts" / "preserve.json"
    owned.parent.mkdir(parents=True)
    owned.write_text("{}", encoding="utf-8")
    stale_full = _old_full_output(formal_output)
    downstream = phase / mutation.DOWNSTREAM_FINAL_RELATIVE_PATHS[0]
    downstream.parent.mkdir(parents=True, exist_ok=True)
    mutation._atomic_write_json(downstream, {"schema": "STALE_TERMINAL"})

    with pytest.raises(
        mutation.MutationAuditError,
        match="MUTATION_NO_WRITE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT",
    ):
        mutation.main(["--execute", "--no-write"])

    assert owned.is_file()
    assert stale_full.is_file()
    assert downstream.is_file()
    assert not (formal_output / mutation.INCOMPLETE_OUTPUT_PATH.name).exists()


@pytest.mark.skipif(
    os.environ.get("B4G_RUN_REAL_PRIVATE_SMOKE") != "1",
    reason="explicit bounded runner-to-adapter integration only",
)
def test_real_runner_private_smoke_feeds_registered_mutation_paths(temp_root):
    from b4g_execution.evidence import executed_case_payload
    from b4g_execution.io import atomic_write_npz
    from b4g_execution.orchestrator import _a0_comparison
    from b4g_solver import campaign

    audit = new_audit(temp_root, "real_private_smoke_adapter")
    case_ids = (
        audit.targets["a0_slot"],
        audit.targets["default_registered_forced_slot"],
        "MIDPOINT_REFERENCE__A1__ALPHA_2__TCMD_MS_10",
    )
    slots = {
        row["case_id"]: row for row in audit.schedule["slots"]
        if row["case_id"] in case_ids
    }
    assert set(slots) == set(case_ids)
    q_ref_n = campaign.recompute_reference_force().individual_finger_reference_force_n

    actual: dict[str, tuple[dict, dict[str, np.ndarray], Path, Path]] = {}
    for ordinal, case_id in enumerate(case_ids):
        smoke_root = temp_root / f"runner_private_smoke_{ordinal}"
        slot = slots[case_id]
        result = campaign.run_registered_slot(slot, q_ref_n=q_ref_n)
        metadata, arrays = executed_case_payload(
            result, slot=slot, execution_ordinal=ordinal,
            q_ref_n=q_ref_n,
            source_hashes={"private_noncredit_registered_smoke": True},
            a0_comparison=(
                _a0_comparison(result) if slot["arm"] == "A0" else None
            ),
        )
        metadata_path = smoke_root / f"{case_id}.json"
        npz_path = smoke_root / f"{case_id}.npz"
        receipt = atomic_write_npz(npz_path, arrays)
        metadata.update({
            "npz_path": npz_path.resolve().as_posix(),
            "npz_bytes": receipt["bytes"],
            "npz_sha256": receipt["sha256"],
            "npz_arrays": receipt["arrays"],
        })
        mutation._atomic_write_json(metadata_path, metadata)
        actual[case_id] = (metadata, arrays, metadata_path, npz_path)

    def registered(self, case_id):
        return actual[case_id]

    audit._registered_case = MethodType(registered, audit)
    audit.nc02(); audit.nc03(); audit.nc04(); audit.nc05_06(); audit.nc21()
    registered_receipts = list(audit.receipts)
    assert len(registered_receipts) == 24
    assert all(row.killed for row in registered_receipts)
    nc21 = [row for row in registered_receipts if row.parent_id == "B4FNC21"]
    assert len(nc21) == 6
    assert all(
        row.execution_detail["registered_base_stage_exact_match"] is True
        for row in nc21
    )

    rk_id = audit.targets["default_registered_forced_slot"]
    midpoint_id = "MIDPOINT_REFERENCE__A1__ALPHA_2__TCMD_MS_10"
    audit._campaign_summary = {"selector": {"selected_parent_level": None}}
    audit._metadata_cache = {
        rk_id: (actual[rk_id][0], actual[rk_id][2]),
        midpoint_id: (actual[midpoint_id][0], actual[midpoint_id][2]),
    }
    before = len(audit.receipts)
    audit.nc15()
    reference_receipts = audit.receipts[before:]
    assert len(reference_receipts) == 2
    assert all(row.killed for row in reference_receipts)
    assert all(
        row.execution_detail["time_and_full_provenance_replaced"] is True
        for row in reference_receipts
    )
