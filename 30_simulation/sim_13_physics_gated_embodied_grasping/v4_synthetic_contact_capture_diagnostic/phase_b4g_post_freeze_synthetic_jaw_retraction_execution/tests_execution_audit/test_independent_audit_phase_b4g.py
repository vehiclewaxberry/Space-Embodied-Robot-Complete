from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pytest


PHASE = Path(__file__).resolve().parents[1]
if str(PHASE) not in sys.path:
    sys.path.insert(0, str(PHASE))

import independent_audit_phase_b4g as audit


def write_bytes(path: Path, payload: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def make_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "project"
    phase = project / "phase_b4g"
    project.mkdir()
    phase.mkdir()
    write_bytes(project / "PROJECT_MAP.md", b"fixture\n")
    return project, phase


def valid_metadata(case_id: str = "A0_FIXTURE") -> dict:
    na = {
        "gate_id": "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
        "evaluation_status": "NOT_APPLICABLE",
        "scientific_predicate": None,
        "applicability_reason": "NO_FINITE_REMOVAL_EVENT",
        "detail": {"finite_removal": False},
    }
    return {
        "case_id": case_id,
        "arm": "A0",
        "event_provenance": {"acquisition_time_s": 0.0},
        "command_parameters": {
            "Q_ref_per_finger_N": 0.024542335689275555,
            "left": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
            "right": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
        },
        "responses": {
            "finite_removal_event": False,
            "signed_work_terminal_J": 0.0,
        },
        "gate_records": [na],
    }


def valid_arrays() -> dict[str, np.ndarray]:
    n = 2
    s = 2
    service = np.zeros((n, 29), dtype="<f8")
    service[:, 3] = 1.0
    service[:, 13:15] = 0.03
    target = np.zeros((n, 13), dtype="<f8")
    target[:, 3] = 1.0
    stage_service = service.copy()
    arrays = {
        "time_s": np.array([0.0, 0.08], dtype="<f8"),
        "service_state_29": service,
        "target_state_13": target,
        "command_Q_14": np.zeros((n, 14), dtype="<f8"),
        "signed_W_act_J": np.zeros(n, dtype="<f8"),
        "left_gap_m": np.ones(n, dtype="<f8") * 2.0e-6,
        "right_gap_m": np.ones(n, dtype="<f8") * 2.0e-6,
        "left_gap_rate_m_s": np.zeros(n, dtype="<f8"),
        "right_gap_rate_m_s": np.zeros(n, dtype="<f8"),
        "total_linear_momentum_N_s": np.zeros((n, 3), dtype="<f8"),
        "total_angular_momentum_N_m_s": np.zeros((n, 3), dtype="<f8"),
        "total_kinetic_energy_J": np.zeros(n, dtype="<f8"),
        "energy_minus_work_residual_J": np.zeros(n, dtype="<f8"),
        "ideal_constraint_power_W": np.zeros(n, dtype="<f8"),
        "contact_force_N": np.zeros(n, dtype="<f8"),
        "contact_torque_N_m": np.zeros(n, dtype="<f8"),
        "stage_time_s": np.array([0.0, 0.08], dtype="<f8"),
        "stage_code": np.array([0, 0], dtype="<i8"),
        "stage_service_state_29": stage_service,
        "stage_command_Q_14": np.zeros((s, 14), dtype="<f8"),
        "stage_power_W": np.zeros(s, dtype="<f8"),
        "stage_P_coordinates_m": np.ones((s, 2), dtype="<f8") * 0.03,
        "stage_gap_jacobian_P": np.repeat(np.eye(2, dtype="<f8")[None, :, :], s, axis=0),
        "stage_mass_cholesky_min_diagonal": np.ones(s, dtype="<f8"),
        "stage_domain_and_sign_pass": np.ones(s, dtype=np.bool_),
    }
    assert set(arrays) == set(audit.ACTIVE_ARRAYS)
    return arrays


def test_a0_quaternion_geodesic_is_stable_and_sign_invariant() -> None:
    pathological = np.asarray([
        -0.01568825063444881,
        0.8246611675132001,
        0.5249352596774691,
        -0.21007334608451503,
    ])
    assert float(np.dot(pathological, pathological)) == np.nextafter(1.0, 0.0)
    identity = np.asarray([1.0, 0.0, 0.0, 0.0])
    orthogonal = np.asarray([0.0, 1.0, 0.0, 0.0])
    raw = np.stack([pathological, identity, identity])
    parent = np.stack([pathological, -identity, orthogonal])

    geodesic = audit._a0_quaternion_geodesic_rows(raw, parent)

    assert geodesic[0] == 0.0
    assert geodesic[1] == 0.0
    assert geodesic[2] == pytest.approx(np.pi, abs=1.0e-15)


def test_a0_quaternion_replay_accepts_5e_minus_13_and_rejects_2e_minus_12_rad() -> None:
    identity = np.asarray([[1.0, 0.0, 0.0, 0.0]])
    theta_pass = 5.0e-13
    theta_fail = 2.0e-12
    within = np.asarray([[
        np.cos(theta_pass / 2.0), np.sin(theta_pass / 2.0), 0.0, 0.0,
    ]])
    outside = np.asarray([[
        np.cos(theta_fail / 2.0), np.sin(theta_fail / 2.0), 0.0, 0.0,
    ]])

    observed = audit._verify_a0_quaternion_replay(within, identity, "PASS")
    assert observed == pytest.approx(theta_pass, rel=1.0e-15)
    with pytest.raises(audit.B4GIndependentAuditError, match="A0_RAW_PARENT_REPLAY"):
        audit._verify_a0_quaternion_replay(outside, identity, "FAIL")


@pytest.mark.parametrize(
    ("raw", "parent", "error"),
    [
        (
            np.zeros((1, 4)),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "NONUNIT",
        ),
        (
            np.asarray([[1.0 + 2.0e-12, 0.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "NONUNIT",
        ),
        (
            np.asarray([[np.nan, 0.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "NONFINITE",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            np.asarray([[np.inf, 0.0, 0.0, 0.0]]),
            "NONFINITE",
        ),
        (
            np.asarray([1.0, 0.0, 0.0, 0.0]),
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            "SHAPE_MISMATCH",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0]]),
            np.asarray([[1.0, 0.0, 0.0]]),
            "SHAPE_MISMATCH",
        ),
        (
            np.asarray([[1.0, 0.0, 0.0, 0.0]]),
            np.asarray([
                [1.0, 0.0, 0.0, 0.0],
                [1.0, 0.0, 0.0, 0.0],
            ]),
            "SHAPE_MISMATCH",
        ),
    ],
)
def test_a0_quaternion_geodesic_rejects_invalid_inputs(
    raw: np.ndarray,
    parent: np.ndarray,
    error: str,
) -> None:
    with pytest.raises(audit.B4GIndependentAuditError, match=error):
        audit._a0_quaternion_geodesic_rows(raw, parent)


def test_a0_quaternion_replay_rejects_vector_norm_hidden_by_componentwise_check() -> None:
    identity = np.asarray([[1.0, 0.0, 0.0, 0.0]])
    vector_component = 8.0e-13
    adversarial = np.asarray([[
        np.sqrt(1.0 - 3.0 * vector_component**2),
        vector_component,
        vector_component,
        vector_component,
    ]])
    assert np.all(np.abs(adversarial - identity) < 1.0e-12)
    angle = audit._a0_quaternion_geodesic_rows(adversarial, identity)[0]
    assert angle > 1.0e-12
    with pytest.raises(audit.B4GIndependentAuditError, match="A0_RAW_PARENT_REPLAY"):
        audit._verify_a0_quaternion_replay(adversarial, identity, "ADVERSARIAL")


def test_audit_import_scan_accepts_only_stdlib_numpy_and_rejects_solver(tmp_path: Path) -> None:
    audit._assert_import_independence(Path(audit.__file__))
    bad = tmp_path / "bad_audit.py"
    bad.write_text("import b4g_solver\n", encoding="utf-8")
    with pytest.raises(audit.B4GIndependentAuditError, match="AUDIT_FORBIDDEN_IMPORT"):
        audit._assert_import_independence(bad)


def test_strict_json_rejects_duplicate_keys_and_noncanonical_bytes(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}\n', encoding="utf-8")
    with pytest.raises(audit.B4GIndependentAuditError, match="DUPLICATE_JSON_KEY"):
        audit.read_json(duplicate)
    pretty = tmp_path / "pretty.json"
    pretty.write_text('{\n  "a": 1\n}\n', encoding="utf-8")
    with pytest.raises(audit.B4GIndependentAuditError, match="JSON_NOT_CANONICAL"):
        audit.read_json(pretty, canonical=True)


def test_file_record_tamper_and_unsafe_path_fail_closed(tmp_path: Path) -> None:
    project, _ = make_project(tmp_path)
    payload = project / "evidence.bin"
    write_bytes(payload, b"original")
    record = audit.file_record(payload, "FIXTURE", project)
    audit.verify_record(record, project)
    payload.write_bytes(b"tampered")
    with pytest.raises(audit.B4GIndependentAuditError, match="FILE_RECORD_(SIZE|SHA)_DRIFT"):
        audit.verify_record(record, project)
    unsafe = {"path": "../escape", "role": "FIXTURE", "bytes": 1, "sha256": "0" * 64}
    with pytest.raises(audit.B4GIndependentAuditError, match="RECORD_PATH_UNSAFE"):
        audit.verify_record(unsafe, project)


def test_safe_record_path_rejects_intermediate_directory_reparse_before_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, _ = make_project(tmp_path)
    outside = tmp_path / "outside_record_tree"
    write_bytes(outside / "evidence.bin", b"outside-must-not-be-consumed")
    link = project / "bound"
    actual_reparse = False
    try:
        link.symlink_to(outside, target_is_directory=True)
        actual_reparse = True
    except OSError:
        write_bytes(link / "evidence.bin", b"simulated-reparse-node")
        original_is_junction = getattr(Path, "is_junction", None)

        def simulated_junction(self: Path) -> bool:
            if self == link:
                return True
            return bool(original_is_junction(self)) if callable(original_is_junction) else False

        monkeypatch.setattr(Path, "is_junction", simulated_junction, raising=False)
    with pytest.raises(audit.B4GIndependentAuditError, match="REPARSE_POINT_FORBIDDEN"):
        audit._safe_record_path("bound/evidence.bin", project)
    assert (outside / "evidence.bin").read_bytes() == b"outside-must-not-be-consumed"
    if actual_reparse:
        link.unlink()


def test_validation_missing_or_promoted_field_fails_closed() -> None:
    valid = {
        "schema": "SIM13_V4B4G_READ_ONLY_VALIDATION_REPORT_V1",
        "mode": "full", "status": "PASS", "passed": True, "final": False,
        "audited": False, "validator_pass_claimed": False,
        "campaign_or_scientific_credit": False, "check_count": 1,
        "failure_count": 0, "failures": [], "observations": {},
        "writes_performed": False, "solver_runner_mutation_modules_imported": False,
    }
    audit._verify_validation(valid)
    missing = dict(valid)
    missing.pop("writes_performed")
    with pytest.raises(audit.B4GIndependentAuditError, match="VALIDATION_KEY_SET"):
        audit._verify_validation(missing)
    promoted = dict(valid)
    promoted["validator_pass_claimed"] = True
    with pytest.raises(audit.B4GIndependentAuditError, match="VALIDATION_NOT_FULL"):
        audit._verify_validation(promoted)


def test_npz_shapes_dtypes_finite_and_p_only_are_independently_checked(tmp_path: Path) -> None:
    arrays = valid_arrays()
    path = tmp_path / "case.npz"
    np.savez_compressed(path, **arrays)
    loaded = audit._load_npz(path)
    audit._validate_npz_arrays(valid_metadata(), loaded)
    missing = dict(loaded)
    missing.pop("command_Q_14")
    with pytest.raises(audit.B4GIndependentAuditError, match="CASE_NPZ_ARRAY_SET"):
        audit._validate_npz_arrays(valid_metadata(), missing)
    non_p = {name: value.copy() for name, value in loaded.items()}
    non_p["command_Q_14"][0, 0] = 1.0
    with pytest.raises(audit.B4GIndependentAuditError, match="NON_P_GENERALIZED_FORCE"):
        audit._validate_npz_arrays(valid_metadata(), non_p)
    nonfinite = {name: value.copy() for name, value in arrays.items()}
    nonfinite["left_gap_m"][0] = np.nan
    bad = tmp_path / "nonfinite.npz"
    np.savez_compressed(bad, **nonfinite)
    with pytest.raises(audit.B4GIndependentAuditError, match="NPZ_NONFINITE"):
        audit._load_npz(bad)


def test_missing_registered_raw_case_fails_before_any_campaign_execution(tmp_path: Path) -> None:
    project, phase = make_project(tmp_path)
    (phase / "evidence" / "raw_cases").mkdir(parents=True)
    schedule = audit.read_json(PHASE / "contracts" / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    with pytest.raises(audit.B4GIndependentAuditError, match="RAW_CASE_METADATA_NOT_MANIFESTED"):
        audit._load_cases(
            phase, project, schedule,
            {"REGISTERED_CASE_METADATA": [], "EXECUTED_CASE_NPZ": []},
        )


def test_raw_directory_extra_temp_or_directory_is_rejected(tmp_path: Path) -> None:
    raw = tmp_path / "raw_cases"
    raw.mkdir()
    (raw / "leftover.tmp").write_text("partial", encoding="utf-8")
    with pytest.raises(audit.B4GIndependentAuditError, match="RAW_CASE_DIRECTORY_INVENTORY"):
        audit._assert_exact_raw_entries(raw, set())
    (raw / "leftover.tmp").unlink()
    (raw / "nested").mkdir()
    with pytest.raises(audit.B4GIndependentAuditError, match="RAW_CASE_DIRECTORY_NONPLAIN_ENTRY"):
        audit._assert_exact_raw_entries(raw, set())


def test_manifest_empty_and_manifested_hash_tamper_fail_closed(tmp_path: Path) -> None:
    project, phase = make_project(tmp_path)
    manifest_path = phase / audit.MANIFEST_REL
    manifest_path.parent.mkdir(parents=True)
    empty = {
        "schema": "SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1",
        "scope": audit.SCOPE, "self_excluded": True, "acyclic": True,
        "source_freeze_terminal": {}, "execution_validation": {},
        "records": [], "record_count": 0,
        "records_canonical_sha256": audit.canonical_sha256([]),
        "excluded_future_outputs": audit._expected_future_outputs(phase, project),
        "claim_boundary": audit.CLAIM_BOUNDARY,
    }
    audit.atomic_write_json(manifest_path, empty)
    with pytest.raises(audit.B4GIndependentAuditError, match="EVIDENCE_MANIFEST_ROLE_COUNT"):
        audit._verify_manifest(manifest_path, project, phase)
    evidence = project / "bound.bin"
    write_bytes(evidence, b"bound")
    forged = deepcopy(empty)
    forged["records"] = [{
        "path": evidence.relative_to(project).as_posix(), "role": "CAMPAIGN_SUMMARY",
        "bytes": evidence.stat().st_size, "sha256": "0" * 64,
    }]
    forged["record_count"] = 1
    forged["records_canonical_sha256"] = audit.canonical_sha256(forged["records"])
    audit.atomic_write_json(manifest_path, forged)
    with pytest.raises(audit.B4GIndependentAuditError, match="FILE_RECORD_SHA_DRIFT"):
        audit._verify_manifest(manifest_path, project, phase)


def test_missing_mutation_evidence_fails_closed() -> None:
    spec = audit.read_json(PHASE / "contracts" / "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json")
    schedule = audit.read_json(PHASE / "contracts" / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    reference = audit.read_json(PHASE / "contracts" / "PHASE_B4G_REFERENCE_FORCE_V1.json")
    governance = audit.read_json(PHASE / "contracts" / "PHASE_B4G_GOVERNANCE_V1.json")
    with pytest.raises(audit.B4GIndependentAuditError, match="NEGATIVE_CONTROL_HEADER_OR_COUNTS"):
        audit._verify_mutations(
            {}, spec, {"selector": {"selected_parent_level": None}},
            PHASE.parents[4], PHASE, schedule, reference, governance, {},
            {"observations": {}},
        )


def test_all_22_mutation_parents_have_independent_gate_predicates() -> None:
    spec = audit.read_json(PHASE / "contracts" / "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json")
    assert set(audit.MUTATION_REPLAY_TYPE_BY_PARENT) == set(spec["required_parent_ids"])
    assert set(audit.MUTATION_REPLAY_TYPE_BY_PARENT.values()) == set(audit.MUTATION_PAYLOAD_FIELDS)


def test_forged_validator_kill_cannot_replace_independent_gate_recomputation(tmp_path: Path) -> None:
    project, _ = make_project(tmp_path)
    schedule = audit.read_json(PHASE / "contracts" / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json")
    reference = audit.read_json(PHASE / "contracts" / "PHASE_B4G_REFERENCE_FORCE_V1.json")
    spec = audit.read_json(PHASE / "contracts" / "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json")
    governance = audit.read_json(PHASE / "contracts" / "PHASE_B4G_GOVERNANCE_V1.json")
    candidate = {
        **governance["required_false"],
        **{field: None for field in governance["required_null_physical_inputs"]},
    }
    base = {"replay_type": "GOVERNANCE_CANDIDATE", "payload": {"candidate": candidate}}
    unchanged_mutant = deepcopy(base)
    forged_validator_replay = {
        "actual_failed_gate": "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
        "killed": True,
        "independently_killed": True,
    }
    assert forged_validator_replay["killed"] is True
    with pytest.raises(audit.B4GIndependentAuditError, match="NOT_INDEPENDENTLY_GATE_KILLED"):
        audit._verify_independent_mutation_kill(
            parent_id="B4FNC19",
            gate_id="B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
            base=base, mutant=unchanged_mutant, frozen_schedule=schedule,
            frozen_q_ref=reference["individual_finger_reference_force_N"],
            mutation_spec=spec, governance=governance, project_root=project,
        )
    real_mutant = deepcopy(base)
    real_mutant["payload"]["candidate"]["owner_authorized"] = True
    nominal, mutant = audit._verify_independent_mutation_kill(
        parent_id="B4FNC19",
        gate_id="B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
        base=base, mutant=real_mutant, frozen_schedule=schedule,
        frozen_q_ref=reference["individual_finger_reference_force_N"],
        mutation_spec=spec, governance=governance, project_root=project,
    )
    assert nominal["failed_gate_ids"] == []
    assert mutant["failed_gate_ids"] == ["B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS"]


def test_restricted_patch_supports_frozen_nc16_list_append() -> None:
    base = {"payload": {"schedule": {"slots": []}}}
    level = {"alpha": 32.0}
    result = audit._apply_patch(
        base,
        [{"op": "add", "path": "/payload/schedule/slots/-", "value": level}],
    )
    assert result["payload"]["schedule"]["slots"] == [level]


def test_governance_promotion_fails_closed() -> None:
    governance = audit.read_json(PHASE / "contracts" / "PHASE_B4G_GOVERNANCE_V1.json")
    run_spec = audit.read_json(PHASE / "contracts" / "PHASE_B4G_RUN_SPEC_V1.json")
    summary = {
        "governance": {
            "required_false": governance["required_false"],
            "required_null_physical_inputs": {name: None for name in governance["required_null_physical_inputs"]},
            "formal_sim13_v2_state_unchanged": audit.FORMAL_STATE,
            "memory": audit.MEMORY,
        }
    }
    negative = {
        "capabilities": {
            "registered_negative_controls_executed": True,
            "physical_release_implemented": False, "current_system_bound": False,
            "formal_nc19_credit": False, "owner_authorized": False,
            "production_ready": False, "release_authorized": False,
            "next_stage_authorized": False,
        },
        "memory": audit.MEMORY,
    }
    post = {"runtime_identity": dict(audit.MEMORY)}
    audit._verify_governance(governance, run_spec, summary, negative, post)
    promoted = deepcopy(negative)
    promoted["capabilities"]["owner_authorized"] = True
    with pytest.raises(audit.B4GIndependentAuditError, match="GOVERNANCE_PROMOTION"):
        audit._verify_governance(governance, run_spec, summary, promoted, post)


def test_active_attempt_invalidation_and_supersession_are_hard_blocks(tmp_path: Path) -> None:
    _, phase = make_project(tmp_path)
    incomplete = phase / "b4g_mutation_execution" / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    audit.atomic_write_json(incomplete, {"status": "INCOMPLETE"})
    with pytest.raises(audit.B4GIndependentAuditError, match="INCOMPLETE_MARKER_PRESENT"):
        audit._verify_no_active_attempt_or_invalidation(phase)
    incomplete.unlink()
    invalidated = phase / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    audit.atomic_write_json(invalidated, {"schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1", "active": True})
    with pytest.raises(audit.B4GIndependentAuditError, match="ACTIVE_INVALIDATION"):
        audit._verify_no_active_attempt_or_invalidation(phase)
    audit.atomic_write_json(invalidated, {"schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1", "active": False})
    audit._verify_no_active_attempt_or_invalidation(phase)


def test_marker_directories_fail_closed_under_lexists(tmp_path: Path) -> None:
    _, phase = make_project(tmp_path)
    incomplete = phase / "b4g_mutation_execution" / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    incomplete.mkdir(parents=True)
    with pytest.raises(audit.B4GIndependentAuditError, match="INCOMPLETE_MARKER_PRESENT"):
        audit._verify_no_active_attempt_or_invalidation(phase)
    incomplete.rmdir()
    inactive = phase / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    inactive.mkdir(parents=True)
    with pytest.raises(audit.B4GIndependentAuditError, match="MARKER_NOT_REGULAR_FILE"):
        audit._verify_no_active_attempt_or_invalidation(phase)


def test_external_and_broken_marker_symlinks_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, phase = make_project(tmp_path)
    marker = phase / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    marker.parent.mkdir(parents=True)
    outside = tmp_path / "outside_marker.json"
    audit.atomic_write_json(
        outside, {"schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1", "active": False},
    )

    def assert_symlink_rejected(target: Path) -> None:
        created = False
        try:
            marker.symlink_to(target)
            created = True
        except OSError:
            original_lexists = audit.os.path.lexists
            original_is_symlink = Path.is_symlink
            monkeypatch.setattr(
                audit.os.path, "lexists",
                lambda value: True if Path(value) == marker else original_lexists(value),
            )
            monkeypatch.setattr(
                Path, "is_symlink",
                lambda self: True if self == marker else original_is_symlink(self),
            )
        with pytest.raises(audit.B4GIndependentAuditError, match="MARKER_SYMLINK_FORBIDDEN"):
            audit._verify_no_active_attempt_or_invalidation(phase)
        if created:
            marker.unlink()
        monkeypatch.undo()

    assert_symlink_rejected(outside)
    assert_symlink_rejected(tmp_path / "missing_external_marker.json")


def test_forbidden_scan_prunes_generated_long_tree_but_catches_hidden_urdf(tmp_path: Path) -> None:
    _, phase = make_project(tmp_path)
    generated = phase / ".pytest-very-long"
    for index in range(18):
        generated /= f"segment_{index:02d}"
    write_bytes(generated / "ignored.urdf", b"generated")
    governance = {"forbidden_local_artifacts": ["*.urdf", "execution.lock"]}
    audit._scan_forbidden_local_artifacts(phase, governance)
    write_bytes(phase / ".hidden_business" / "model.urdf", b"forbidden")
    with pytest.raises(audit.B4GIndependentAuditError, match="FORBIDDEN_LOCAL_ARTIFACT"):
        audit._scan_forbidden_local_artifacts(phase, governance)


def test_terminal_self_exclusion_and_order_are_enforced(tmp_path: Path) -> None:
    project, phase = make_project(tmp_path)
    records = []
    for index, role in enumerate((
        "PREAUDIT_GATE", "EVIDENCE_MANIFEST_SELF_EXCLUDED",
        "INDEPENDENT_AUDIT_RECEIPT", "AUDITED_FINAL_GATE",
    )):
        path = phase / "signed" / f"{index}.json"
        audit.atomic_write_json(path, {"index": index})
        records.append(audit.file_record(path, role, project))
    terminal_path = phase / audit.TERMINAL_REL
    terminal = {
        "schema": "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True, "acyclic": True, "records": records,
        "record_count": 4,
        "excluded_self_path": audit._project_relative(terminal_path, project),
        "claim_boundary": audit.CLAIM_BOUNDARY,
    }
    audit._verify_terminal_payload(terminal, terminal_path, project)
    forged = deepcopy(terminal)
    forged["records"][-1]["path"] = forged["excluded_self_path"]
    with pytest.raises(audit.B4GIndependentAuditError, match="TERMINAL_SELF_EXCLUSION"):
        audit._verify_terminal_payload(forged, terminal_path, project)


def test_clean_final_removes_only_owned_final_artifacts(tmp_path: Path) -> None:
    _, phase = make_project(tmp_path)
    for relative in (audit.RECEIPT_REL, audit.AUDITED_GATE_REL, audit.TERMINAL_REL):
        write_bytes(phase / relative, b"stale")
    keep = phase / "results" / "keep.json"
    write_bytes(keep, b"user")
    audit.clean_final(phase)
    assert all(not (phase / relative).exists() for relative in (audit.RECEIPT_REL, audit.AUDITED_GATE_REL, audit.TERMINAL_REL))
    assert keep.read_bytes() == b"user"


def test_clean_final_unlinks_symlink_without_deleting_its_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, phase = make_project(tmp_path)
    target = tmp_path / "external_keep.json"
    write_bytes(target, b"external")
    link = phase / audit.RECEIPT_REL
    link.parent.mkdir(parents=True)
    simulated = False
    try:
        link.symlink_to(target)
    except OSError:
        simulated = True
        write_bytes(link, b"simulated-link-node")
        original_lstat = Path.lstat
        class SimulatedSymlinkStatus:
            st_mode = audit.stat.S_IFLNK
        monkeypatch.setattr(
            Path, "lstat",
            lambda self: SimulatedSymlinkStatus() if self == link else original_lstat(self),
        )
    audit.clean_final(phase)
    assert not audit.os.path.lexists(link)
    assert target.read_bytes() == b"external"
    if simulated:
        monkeypatch.undo()


def test_clean_final_rejects_results_parent_directory_reparse_or_junction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, phase = make_project(tmp_path)
    outside_results = tmp_path / "outside_results"
    outside_gate = outside_results / audit.AUDITED_GATE_REL.name
    write_bytes(outside_gate, b"external-gate-must-survive")
    results = phase / "results"
    actual_reparse = False
    try:
        results.symlink_to(outside_results, target_is_directory=True)
        actual_reparse = True
        protected_gate = outside_gate
    except OSError:
        protected_gate = results / audit.AUDITED_GATE_REL.name
        write_bytes(protected_gate, b"simulated-junction-gate")
        original_is_junction = getattr(Path, "is_junction", None)

        def simulated_junction(self: Path) -> bool:
            if self == results:
                return True
            return bool(original_is_junction(self)) if callable(original_is_junction) else False

        monkeypatch.setattr(Path, "is_junction", simulated_junction, raising=False)
    with pytest.raises(audit.B4GIndependentAuditError, match="CLEANUP_FAILED_CLOSED"):
        audit.clean_final(phase)
    assert protected_gate.read_bytes() in {
        b"external-gate-must-survive", b"simulated-junction-gate",
    }
    if actual_reparse:
        results.unlink()


def test_clean_final_rejects_file_attribute_reparse_point_on_evidence_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, phase = make_project(tmp_path)
    receipt = phase / audit.RECEIPT_REL
    write_bytes(receipt, b"must-not-cross-reparse-parent")
    evidence = receipt.parent
    original_lstat = Path.lstat
    real_status = original_lstat(evidence)

    class ReparseStatus:
        st_mode = real_status.st_mode
        st_file_attributes = (
            int(getattr(real_status, "st_file_attributes", 0))
            | audit.FILE_ATTRIBUTE_REPARSE_POINT
        )

    monkeypatch.setattr(
        Path, "lstat",
        lambda self: ReparseStatus() if self == evidence else original_lstat(self),
    )
    with pytest.raises(audit.B4GIndependentAuditError, match="CLEANUP_FAILED_CLOSED"):
        audit.clean_final(phase)
    assert receipt.read_bytes() == b"must-not-cross-reparse-parent"


def test_clean_final_is_consumer_first_and_best_effort_on_baseexception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, phase = make_project(tmp_path)
    for relative in audit.FINAL_CONSUMER_FIRST_RELATIVES:
        write_bytes(phase / relative, b"partial-final")
    original_unlink = Path.unlink
    calls: list[str] = []
    interrupted = False

    def flaky_unlink(self: Path, *args, **kwargs) -> None:
        nonlocal interrupted
        relative = self.relative_to(phase).as_posix()
        calls.append(relative)
        if self == phase / audit.TERMINAL_REL and not interrupted:
            interrupted = True
            raise KeyboardInterrupt("injected cleanup interrupt")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", flaky_unlink)
    with pytest.raises(audit.B4GIndependentAuditError, match="CLEANUP_FAILED_CLOSED"):
        audit.clean_final(phase)
    assert calls[:3] == [
        relative.as_posix() for relative in audit.FINAL_CONSUMER_FIRST_RELATIVES
    ]
    assert calls[3] == audit.TERMINAL_REL.as_posix()
    assert all(
        not audit.os.path.lexists(phase / relative)
        for relative in audit.FINAL_CONSUMER_FIRST_RELATIVES
    )


@pytest.mark.parametrize("exception_type", [KeyboardInterrupt, SystemExit])
def test_baseexception_after_partial_signing_rolls_back_every_final_node(
    tmp_path: Path, exception_type: type[BaseException],
) -> None:
    _, phase = make_project(tmp_path)
    write_bytes(phase / audit.RECEIPT_REL, b"signed-receipt")
    write_bytes(phase / audit.AUDITED_GATE_REL, b"signed-gate")
    with pytest.raises(exception_type):
        audit._cleanup_final_then_reraise(
            phase, exception_type("injected signing interruption"),
        )
    assert all(
        not audit.os.path.lexists(phase / relative)
        for relative in audit.FINAL_CONSUMER_FIRST_RELATIVES
    )


def test_formal_audit_routes_both_baseexception_boundaries_through_rollback() -> None:
    tree = audit.ast.parse(Path(audit.__file__).read_text(encoding="utf-8"))
    audit_function = next(
        node for node in tree.body
        if isinstance(node, audit.ast.FunctionDef) and node.name == "audit_phase"
    )
    rollback_handlers = []
    for handler in (
        node for node in audit.ast.walk(audit_function)
        if isinstance(node, audit.ast.ExceptHandler)
        and isinstance(node.type, audit.ast.Name)
        and node.type.id == "BaseException"
    ):
        called = {
            node.func.id for node in audit.ast.walk(handler)
            if isinstance(node, audit.ast.Call) and isinstance(node.func, audit.ast.Name)
        }
        if "_cleanup_final_then_reraise" in called:
            rollback_handlers.append(handler)
    assert len(rollback_handlers) == 2


def test_custom_root_formal_signing_is_rejected_before_any_write(tmp_path: Path) -> None:
    project, phase = make_project(tmp_path)
    with pytest.raises(audit.B4GIndependentAuditError, match="FORMAL_SIGNING_REQUIRES_MODULE_PHASE_ROOT"):
        audit.audit_phase(phase, project_root=project, sign=True)
    assert all(not (phase / relative).exists() for relative in (audit.RECEIPT_REL, audit.AUDITED_GATE_REL, audit.TERMINAL_REL))


def test_formal_phase_lexical_chain_rejects_junction_before_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, phase = make_project(tmp_path)
    monkeypatch.setattr(audit, "PHASE_ROOT", phase)
    original_is_junction = getattr(Path, "is_junction", None)

    def simulated_junction(self: Path) -> bool:
        if self == phase:
            return True
        return bool(original_is_junction(self)) if callable(original_is_junction) else False

    monkeypatch.setattr(Path, "is_junction", simulated_junction, raising=False)
    with pytest.raises(audit.B4GIndependentAuditError, match="FORMAL_SIGNING_PHASE_CHAIN_REPARSE"):
        audit.audit_phase(phase, project_root=project, sign=True)
    assert all(
        not audit.os.path.lexists(phase / relative)
        for relative in audit.FINAL_CONSUMER_FIRST_RELATIVES
    )


def test_failed_formal_audit_removes_old_final_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project, phase = make_project(tmp_path)
    for relative in (audit.RECEIPT_REL, audit.AUDITED_GATE_REL, audit.TERMINAL_REL):
        write_bytes(phase / relative, b"stale")
    monkeypatch.setattr(audit, "PHASE_ROOT", phase)
    with pytest.raises(audit.B4GIndependentAuditError):
        audit.audit_phase(phase, project_root=project, sign=True)
    assert all(not (phase / relative).exists() for relative in (audit.RECEIPT_REL, audit.AUDITED_GATE_REL, audit.TERMINAL_REL))


def test_source_inventory_prunes_generated_trees_and_includes_audit_tests(tmp_path: Path) -> None:
    project, phase = make_project(tmp_path)
    for name in (
        "run_phase_b4g_solver.py", "run_phase_b4g_mutation_audit.py",
        "validate_phase_b4g_evidence.py", "publish_phase_b4g_preaudit.py",
        "independent_audit_phase_b4g.py",
    ):
        write_bytes(phase / name, b"pass\n")
    write_bytes(phase / "tests_execution_audit" / "test_audit.py", b"pass\n")
    write_bytes(phase / ".pytest-long" / "ignored.py", b"pass\n")
    inventory = audit._current_source_inventory(project, phase)
    paths = [row["path"] for row in inventory]
    assert len(paths) == 6
    assert any(path.endswith("tests_execution_audit/test_audit.py") for path in paths)
    assert not any(".pytest-long" in path for path in paths)
