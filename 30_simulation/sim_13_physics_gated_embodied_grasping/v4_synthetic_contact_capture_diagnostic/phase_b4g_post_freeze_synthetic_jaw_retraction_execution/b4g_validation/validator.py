"""Independent fail-closed validator for the complete B4G execution bundle.

The validator is deliberately evidence-only: no solver, runner, mutation module,
or campaign test module is imported.  A contract-only mode is available before
execution; the default full mode requires every campaign and mutation artifact.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import stat
from typing import Any, Mapping

import numpy as np

from .artifact_derivation import (
    ArtifactDerivationResult,
    validate_nominal_payload_derivation,
)
from .core import (
    ValidationReport,
    array_payload_sha256,
    canonical_bytes,
    canonical_sha256,
    exact_key_set,
    finite_number,
    is_sha256,
    load_npz_strict,
    read_json_strict,
    resolve_declared,
    sha256_file,
    verify_file_record,
)
from .geometry_replay import (
    GeometryReplayError,
    centered_gap_jacobian,
    recompute_gap_rate,
    reconstruct_active_target_state_13,
    validate_frozen_source_bindings,
)
from .mutation_replay import (
    CLAIM_BOUNDARY as MUTATION_REPLAY_CLAIM_BOUNDARY,
    REPLAY_TYPE_BY_PARENT,
    apply_restricted_patch,
    certify_clearance_independent,
    evaluate_payload,
    independent_gate_record,
    load_artifact_record,
    validate_bundle,
    validate_patch_semantics,
)
from .supplemental_replay import (
    SupplementalReplayResult,
    validate_supplemental_trace,
)


PHASE_ROOT = Path(__file__).resolve().parent.parent


def _find_project_root() -> Path:
    for candidate in (PHASE_ROOT, *PHASE_ROOT.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate.resolve()
    raise RuntimeError("PROJECT_ROOT_NOT_FOUND")


PROJECT_ROOT = _find_project_root()
CONTRACT_ROOT = PHASE_ROOT / "contracts"
EVIDENCE_ROOT = PHASE_ROOT / "evidence"
RESULTS_ROOT = PHASE_ROOT / "results"
B4E_EVIDENCE_ROOT = (
    PHASE_ROOT.parent / "phase_b4_post_freeze_synthetic_6d_solver" / "evidence"
)

B4E_PROVENANCE_FILES: dict[str, tuple[Path, int, str]] = {
    "events": (
        B4E_EVIDENCE_ROOT / "SIM13_V4B4E_EVENT_INPUTS_V1.json", 25710,
        "FEAA39031CA73F4EC78174B53B63F9A993A7966FD26B1397C8BACD3076BDA224",
    ),
    "acquisitions": (
        B4E_EVIDENCE_ROOT / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json", 384551,
        "326DF1707D6B88310F441290D1D1DE34BBEB79B57453D3934CA4CF2826388B8A",
    ),
    "active_traces": (
        B4E_EVIDENCE_ROOT / "SIM13_V4B4E_ACTIVE_TRACES_V1.json", 1341400,
        "956BB62D1BED86738158A416B2EE6FDB6963F6D6B2E78F1ECA9D347430BC2CAD",
    ),
}

CLAIM_BOUNDARY = (
    "registered synthetic discrete-domain execution only; no physical, current-system, "
    "formal NC19, Owner, production or next-stage credit"
)

CONTRACT_FILES: dict[str, tuple[str, int, str]] = {
    "authorization": (
        "PHASE_B4G_POST_FREEZE_WORK_AUTHORIZATION_V1.json", 1528,
        "8430E2114FC0E873A86152B320539DD3531B57FDD3E1B5443374BBA33E9B7F4C",
    ),
    "bindings": (
        "PHASE_B4G_SOURCE_BINDINGS_V1.json", 4188,
        "EFEC89D34F206B3B8EB8ABF3D08FD798758FC9590EEA501F354A1CF484E4B142",
    ),
    "reference": (
        "PHASE_B4G_REFERENCE_FORCE_V1.json", 1474,
        "E31ABDAEBC03FC71C40EB6274304395850A8B2E8DCB293569DDF1A5850C45AD7",
    ),
    "schedule": (
        "PHASE_B4G_REGISTERED_SCHEDULE_V1.json", 57113,
        "C8D87B7DEFE69770C7A6C6D0B9BACB07CE7DC0F1E0C633393DE364C9DE8D563F",
    ),
    "run_spec": (
        "PHASE_B4G_RUN_SPEC_V1.json", 16556,
        "538920343D279AA352F8CEE3786985FCF7AE2E5C78CAC685EFBE458EA254F3E7",
    ),
    "mutations": (
        "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json", 10159,
        "9EB2FDB6489D653F1738C8B1E6D8CAE23D44BC9C8D350A1EEF42C4C40EA20E6D",
    ),
    "governance": (
        "PHASE_B4G_GOVERNANCE_V1.json", 3335,
        "3BDF4DFAFE5F686F569CCFF0E3870330E21596C1FEAFB6BC6EEB0AAE29D57C70",
    ),
    "evidence_schema": (
        "PHASE_B4G_EVIDENCE_SCHEMA_V1.json", 4934,
        "27183FBF3BF01ABA99BA7D0D15BDD181B335B4C4204DC9DA45353A6AECD3AFCB",
    ),
    "test_inventory": (
        "PHASE_B4G_PREREGISTRATION_TEST_INVENTORY_V1.json", 648,
        "618C7DB28177046D0E94C3D172773A61601EE65E82F62CEEC33C657EEF538AC6",
    ),
}

PREREGISTRATION_FILES: dict[str, tuple[Path, int, str]] = {
    "gate": (
        RESULTS_ROOT / "SIM13_V4B4G_PREREGISTRATION_GATE_V1.json", 6476,
        "288D12EA9120055C46CAE6EC18B397303DB38423DCF92A3FD30D32BBDD215A7E",
    ),
    "terminal": (
        RESULTS_ROOT / "SIM13_V4B4G_PREREGISTRATION_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json", 1404,
        "ED3FB03CAC4FA5C8A0758E1D97766D55D576B34870E43D0EBBF8991C6603553B",
    ),
    "source_manifest": (
        RESULTS_ROOT / "SIM13_V4B4G_PREREGISTRATION_SOURCE_MANIFEST_V1.json", 7410,
        "04E559FC4F846DEC3429B5F37110EF128F8308A7B955C6BD1DD0BD3EC6F88FA4",
    ),
    "test_result": (
        EVIDENCE_ROOT / "SIM13_V4B4G_PREREGISTRATION_TEST_RESULT_V1.json", 554,
        "EA86ABA83C418F9C1681B4DBDD9D18BD018699A3A2865A3AA360BF5162AED168",
    ),
}

LANES = (
    "RK4_COARSE", "RK4_FINE", "RK4_REFERENCE",
    "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE",
)
REFERENCE_LANES = ("RK4_REFERENCE", "MIDPOINT_REFERENCE")
LANE_DEFINITIONS = {
    "RK4_COARSE": ("rk4", 0.001),
    "RK4_FINE": ("rk4", 0.0005),
    "RK4_REFERENCE": ("rk4", 0.00025),
    "MIDPOINT_COARSE": ("midpoint", 0.0005),
    "MIDPOINT_FINE": ("midpoint", 0.00025),
    "MIDPOINT_REFERENCE": ("midpoint", 0.000125),
}
ALPHAS = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)
DURATIONS = (0.005, 0.01, 0.02)
GATES = tuple(f"B4F-G{index:02d}-" for index in range(1, 18))
G02 = "B4F-G02-A0-EXACT-REPLAY"
G03 = "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE"
G04 = "B4F-G04-ACTUATOR-WORK-LEDGER"
G05 = "B4F-G05-P-H-CONSERVATION"
G06 = "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"
G07 = "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION"
G08 = "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL"
G09 = "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE"
G10 = "B4F-G10-EXACT-ZERO-JUMP-REMOVAL"
G11 = "B4F-G11-INDEPENDENT-POST-RELEASE-5MS"
G12 = "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE"
G13 = "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC"
G16 = "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN"
BASE_CASE_GATES = {G03, G04, G05, G06, G07, G08, G09, G10, G11, G16}

ACTIVE_ARRAYS = {
    "time_s", "service_state_29", "target_state_13", "command_Q_14",
    "signed_W_act_J", "left_gap_m", "right_gap_m", "left_gap_rate_m_s",
    "right_gap_rate_m_s", "total_linear_momentum_N_s",
    "total_angular_momentum_N_m_s", "total_kinetic_energy_J",
    "energy_minus_work_residual_J", "ideal_constraint_power_W",
    "contact_force_N", "contact_torque_N_m", "stage_time_s", "stage_code",
    "stage_service_state_29", "stage_command_Q_14", "stage_power_W",
    "stage_P_coordinates_m", "stage_gap_jacobian_P",
    "stage_mass_cholesky_min_diagonal", "stage_domain_and_sign_pass",
}
POST_ARRAYS = {
    "post_time_s", "post_service_state_29", "post_target_state_13",
    "post_left_gap_m", "post_right_gap_m", "post_left_gap_rate_m_s",
    "post_right_gap_rate_m_s", "post_total_linear_momentum_N_s",
    "post_total_angular_momentum_N_m_s", "post_total_kinetic_energy_J",
    "post_contact_force_N", "post_contact_torque_N_m", "post_stage_time_s",
    "post_stage_code", "post_stage_service_state_29", "post_stage_target_state_13",
    "post_stage_P_coordinates_m", "post_stage_gap_jacobian_P",
    "post_stage_domain_and_sign_pass",
}
A0_PARENT_ARRAYS = {
    "time_s", "service_position_m", "service_quaternion_wxyz",
    "R_joint_coordinates_rad", "P_joint_coordinates_m", "base_linear_m_s",
    "base_angular_rad_s", "R_joint_rad_s", "P_joint_m_s", "left_gap_m",
    "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
}
CASE_REQUIRED_FIELDS = {
    "schema", "slot_index", "case_id", "lane_id", "arm", "execution_status",
    "terminal_status", "source_hashes", "acquisition", "event_provenance",
    "command_parameters", "geometry_domain", "opening_sign", "responses",
    "gate_records", "registered_slot", "npz_path", "npz_bytes", "npz_sha256", "claim_boundary",
}
EVENT_REQUIRED_FIELDS = {
    "lane_id", "fresh_b3_reconstruction", "first_qualifying_event_index",
    "acquisition_time_s", "acquisition_certificate_payload",
    "acquisition_certificate_sha256",
    "clearance_certificate_sha256", "removal_time_s",
}

_MUTATION_INCOMPLETE_MARKER_RELATIVE = Path(
    "b4g_mutation_execution/SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
)
_INACTIVE_ATTEMPT_MARKERS = (
    (
        Path("results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"),
        "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
        "EXECUTION_INVALIDATED_MARKER",
    ),
    (
        Path("results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json"),
        "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
        "PRIOR_FINAL_CREDIT_SUPERSEDED_MARKER",
    ),
)


def _load_strict(report: ValidationReport, path: Path, code: str) -> dict[str, Any] | None:
    if not report.require(path.is_file(), f"{code}_MISSING", path.as_posix()):
        return None
    return report.guard(f"{code}_INVALID_JSON", lambda: read_json_strict(path))


def _require_canonical_json(report: ValidationReport, path: Path, value: Mapping[str, Any], code: str) -> None:
    expected = canonical_bytes(value) + b"\n"
    report.require(path.read_bytes() == expected, f"{code}_NOT_CANONICAL_SORTED_COMPACT_LF")


def _validate_attempt_state_markers(
    report: ValidationReport,
    phase_root: Path,
) -> None:
    """Reject incomplete attempts and require any retained receipts inactive.

    The checks are independent of campaign, mutation, runner, publisher and
    audit modules.  They run even in contract-only mode so an incomplete or
    invalidated execution can never hide behind otherwise clean contracts.
    """

    root = Path(phase_root).resolve()
    incomplete = root / _MUTATION_INCOMPLETE_MARKER_RELATIVE
    report.require(
        not os.path.lexists(incomplete),
        "MUTATION_EXECUTION_INCOMPLETE_MARKER_PRESENT",
        incomplete.as_posix(),
    )
    for relative, expected_schema, code in _INACTIVE_ATTEMPT_MARKERS:
        path = root / relative
        if not os.path.lexists(path):
            report.require(True, f"{code}_ABSENT_OR_VALID_INACTIVE")
            continue
        path_lstat = report.guard(
            f"{code}_LSTAT_FAILED", lambda path=path: path.lstat(),
        )
        if path_lstat is None:
            continue
        if not report.require(
            not path.is_symlink() and stat.S_ISREG(path_lstat.st_mode),
            f"{code}_NOT_NON_SYMLINK_REGULAR_FILE",
            {
                "path": path.as_posix(),
                "is_symlink": path.is_symlink(),
                "lstat_mode": path_lstat.st_mode,
            },
        ):
            continue
        value = report.guard(
            f"{code}_INVALID_STRICT_JSON",
            lambda path=path: read_json_strict(path),
        )
        if not report.require(
            isinstance(value, Mapping), f"{code}_NOT_OBJECT",
        ):
            continue
        assert isinstance(value, Mapping)
        _require_canonical_json(report, path, value, code)
        report.require(
            value.get("schema") == expected_schema,
            f"{code}_SCHEMA_MISMATCH",
            value.get("schema"),
        )
        report.require(
            value.get("active") is False,
            f"{code}_ACTIVE_NOT_FALSE",
            value.get("active"),
        )


def _record_path(record: Mapping[str, Any]) -> Path:
    return resolve_declared(PROJECT_ROOT, PHASE_ROOT, record.get("path"))


def _inside_project(path: Path) -> bool:
    try:
        path.resolve().relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def _validate_schedule(report: ValidationReport, schedule: Mapping[str, Any]) -> None:
    slots = schedule.get("slots")
    report.require(schedule.get("seed") == 20260824, "SCHEDULE_SEED")
    report.require(schedule.get("slot_count") == 144, "SCHEDULE_SLOT_COUNT", schedule.get("slot_count"))
    report.require(schedule.get("a0_slot_count") == 12, "SCHEDULE_A0_COUNT")
    report.require(schedule.get("a1_slot_count") == 108, "SCHEDULE_A1_COUNT")
    report.require(schedule.get("a2_slot_count") == 24, "SCHEDULE_A2_COUNT")
    report.require(schedule.get("lane_order") == list(LANES), "SCHEDULE_LANE_ORDER")
    if not report.require(isinstance(slots, list) and len(slots) == 144, "SCHEDULE_SLOTS_NOT_144"):
        return
    report.require(canonical_sha256(slots) == schedule.get("slots_sha256"), "SCHEDULE_SLOT_PAYLOAD_HASH")
    report.require(schedule.get("slots_sha256") == "21642ED06620E589ABB854CCFE936EC2C84D9571ACACA86F690ACC5DB2D78137", "SCHEDULE_FROZEN_SLOT_HASH")
    report.require([slot.get("slot_index") for slot in slots] == list(range(144)), "SCHEDULE_SLOT_INDICES")
    report.require(len({slot.get("case_id") for slot in slots}) == 144, "SCHEDULE_CASE_IDS_NOT_UNIQUE")
    for lane_index, lane in enumerate(LANES):
        lane_slots = slots[lane_index * 24:(lane_index + 1) * 24]
        expected_method, expected_step = LANE_DEFINITIONS[lane]
        report.require(
            len(lane_slots) == 24
            and all(
                slot.get("lane_id") == lane
                and slot.get("method") == expected_method
                and slot.get("step_s") == expected_step
                for slot in lane_slots
            ),
            f"SCHEDULE_{lane}_BLOCK_METHOD_STEP",
        )
        report.require(lane_slots[0].get("arm") == "A0" and lane_slots[0].get("sentinel_position") == "PRE", f"SCHEDULE_{lane}_A0_PRE")
        report.require([slot.get("arm") for slot in lane_slots[1:19]] == ["A1"] * 18, f"SCHEDULE_{lane}_A1_18")
        report.require([slot.get("arm") for slot in lane_slots[19:23]] == ["A2"] * 4, f"SCHEDULE_{lane}_A2_4")
        report.require(lane_slots[23].get("arm") == "A0" and lane_slots[23].get("sentinel_position") == "POST", f"SCHEDULE_{lane}_A0_POST")
        for arm, segment in (("A1", lane_slots[1:19]), ("A2", lane_slots[19:23])):
            keys: list[str] = []
            for slot in segment:
                expected = hashlib.sha256(f"20260824|{lane}|{arm}|{slot.get('case_id')}".encode()).hexdigest().upper()
                report.require(slot.get("permutation_key_sha256") == expected, f"SCHEDULE_{lane}_{arm}_KEY", slot.get("case_id"))
                keys.append(expected)
            report.require(keys == sorted(keys), f"SCHEDULE_{lane}_{arm}_KEY_ORDER")
        levels = {(float(slot["alpha"]), float(slot["command_duration_s"])) for slot in lane_slots[1:19]}
        report.require(levels == {(a, d) for a in ALPHAS for d in DURATIONS}, f"SCHEDULE_{lane}_A1_GRID")


def _validate_contracts_and_preregistration(report: ValidationReport) -> dict[str, dict[str, Any]] | None:
    contracts: dict[str, dict[str, Any]] = {}
    for key, (name, size, digest) in CONTRACT_FILES.items():
        path = CONTRACT_ROOT / name
        if verify_file_record(report, path=path, expected_bytes=size, expected_sha256=digest, code=f"CONTRACT_{key.upper()}"):
            value = _load_strict(report, path, f"CONTRACT_{key.upper()}")
            if value is not None:
                contracts[key] = value
    for key, (path, size, digest) in PREREGISTRATION_FILES.items():
        verify_file_record(report, path=path, expected_bytes=size, expected_sha256=digest, code=f"PREREG_{key.upper()}")
    if len(contracts) != len(CONTRACT_FILES):
        return None
    _validate_schedule(report, contracts["schedule"])
    bindings = contracts["bindings"].get("sources", [])
    geometry_source_records: tuple[dict[str, Any], ...] = ()
    geometry_source_error: str | None = None
    try:
        geometry_source_records = validate_frozen_source_bindings(PROJECT_ROOT)
    except GeometryReplayError as error:
        geometry_source_error = str(error)
    report.require(
        len(bindings) == 11 and len(geometry_source_records) == 5,
        "DIRECT_PARENT_AND_GEOMETRY_BINDING_COUNT",
        {
            "direct_parent_count": len(bindings),
            "independent_geometry_source_count": len(geometry_source_records),
            "geometry_source_error": geometry_source_error,
        },
    )
    for row in bindings:
        verify_file_record(
            report, path=_record_path(row), expected_bytes=row.get("bytes"),
            expected_sha256=row.get("sha256"), code=f"BOUND_PARENT_{row.get('id', 'UNKNOWN')}",
        )
    source_manifest = _load_strict(report, PREREGISTRATION_FILES["source_manifest"][0], "PREREG_SOURCE_MANIFEST")
    if source_manifest is not None:
        report.require(source_manifest.get("self_excluded") is True, "PREREG_SOURCE_SELF_EXCLUDED")
        records = source_manifest.get("records", [])
        report.require(source_manifest.get("record_count") == 19 and len(records) == 19, "PREREG_SOURCE_RECORD_COUNT")
        for index, row in enumerate(records):
            verify_file_record(
                report, path=_record_path(row), expected_bytes=row.get("bytes"),
                expected_sha256=row.get("sha256"), code=f"PREREG_SOURCE_RECORD_{index:02d}",
            )
    gate = _load_strict(report, PREREGISTRATION_FILES["gate"][0], "PREREG_GATE")
    if gate is not None:
        report.require(gate.get("preregistration_final") is True and gate.get("campaign_final") is False, "PREREG_GATE_SCOPE")
        report.require(gate.get("capability_state", {}).get("b4g_full_campaign_executed") is False, "PREREG_GATE_CAMPAIGN_FALSE")
        report.require(gate.get("memory_record") == contracts["run_spec"].get("memory"), "PREREG_MEMORY")
    terminal = _load_strict(report, PREREGISTRATION_FILES["terminal"][0], "PREREG_TERMINAL")
    if terminal is not None:
        report.require(terminal.get("self_excluded") is True and terminal.get("acyclic") is True, "PREREG_TERMINAL_DAG")
        terminal_records = terminal.get("records", [])
        report.require(len(terminal_records) == 3, "PREREG_TERMINAL_RECORD_COUNT")
        for index, row in enumerate(terminal_records):
            verify_file_record(
                report, path=_record_path(row), expected_bytes=row.get("bytes"),
                expected_sha256=row.get("sha256"), code=f"PREREG_TERMINAL_RECORD_{index}",
            )
        terminal_names = {Path(str(row.get("path"))).name for row in terminal_records}
        report.require(PREREGISTRATION_FILES["terminal"][0].name not in terminal_names, "PREREG_TERMINAL_SELF_REFERENCE")
    governance = contracts["governance"]
    report.require(contracts["run_spec"].get("memory") == governance.get("memory_record_required"), "CONTRACT_MEMORY_ALIGNMENT")
    report.require(governance.get("formal_sim13_v2_state_unchanged") == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}, "FORMAL_STATE_DRIFT")
    report.observations["contract_and_preregistration"] = {
        "contract_files": len(contracts), "bound_parent_files": len(bindings),
        "registered_total_slots": 144, "lane_count": 6, "slots_per_lane": 24,
    }
    report.observations["independent_geometry_source_bindings"] = list(
        geometry_source_records
    )
    return contracts


def _validate_record_set(report: ValidationReport, rows: Any, code: str) -> None:
    if not report.require(isinstance(rows, list), f"{code}_NOT_LIST"):
        return
    for index, row in enumerate(rows):
        if not report.require(isinstance(row, dict), f"{code}_{index}_NOT_OBJECT"):
            continue
        declared_value = row.get("path", row.get("declared_path"))
        declared_text = str(declared_value).replace("\\", "/")
        declared_relative = Path(declared_text)
        declared_path = resolve_declared(PROJECT_ROOT, PHASE_ROOT, declared_value)
        resolved = row.get("resolved_path")
        path = Path(str(resolved)).resolve() if resolved is not None else declared_path
        expected_bytes = row.get("bytes", row.get("declared_bytes"))
        expected_sha = row.get("sha256", row.get("declared_sha256"))
        inside = report.require(
            _inside_project(path), f"{code}_{index:03d}_OUTSIDE_PROJECT",
            path.as_posix(),
        )
        if resolved is not None:
            if declared_relative.is_absolute():
                declared_matches = path == declared_relative.resolve()
            else:
                direct_candidates = {
                    (PROJECT_ROOT / declared_relative).resolve(),
                    (PHASE_ROOT / declared_relative).resolve(),
                }
                existing_candidates = {
                    candidate for candidate in direct_candidates if candidate.exists()
                }
                if existing_candidates:
                    declared_matches = path in existing_candidates
                else:
                    # Recursive parent manifests use paths relative to their own
                    # phase roots, which are intentionally not trusted fields in
                    # this record.  In that case bind every declared path segment
                    # to the resolved suffix; a same-name-only redirect is not
                    # sufficient.
                    declared_parts = tuple(declared_relative.parts)
                    declared_matches = (
                        bool(declared_parts)
                        and tuple(path.parts[-len(declared_parts):]) == declared_parts
                    )
            report.require(
                declared_matches,
                f"{code}_{index:03d}_DECLARED_RESOLVED_PATH_MISMATCH",
                {"declared": declared_path.as_posix(), "resolved": path.as_posix()},
            )
            report.require(row.get("actual_bytes") == expected_bytes and row.get("actual_sha256") == expected_sha and row.get("pass") is True, f"{code}_{index:03d}_SELF_REPORT_FIELDS")
        if not inside:
            continue
        verify_file_record(
            report, path=path, expected_bytes=expected_bytes,
            expected_sha256=expected_sha, code=f"{code}_{index:03d}",
        )


def _load_b4e_provenance_templates(
    report: ValidationReport,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, np.ndarray]],
]:
    """Load immutable parent event/acquisition truth without importing B4E code.

    B4G reruns B3 separately for every case, but the pre-command event and
    acquisition projection are deterministic for a frozen numerical lane.  The
    parent files therefore provide an external, hash-bound oracle.  Fresh
    certificates are later compared with the frozen five-pointer allowlist:
    two run IDs, the registered fresh-vs-reference source label, and the two
    bit-identical fresh dissipation values within two binary64 ULP.  The
    acquisition ledger contains matrices while B4G deliberately publishes its
    compact (no-matrix) form; this loader removes exactly that parent-only
    field before comparison.
    """

    values: dict[str, dict[str, Any]] = {}
    for name, (path, expected_bytes, expected_sha256) in B4E_PROVENANCE_FILES.items():
        verified = verify_file_record(
            report,
            path=path,
            expected_bytes=expected_bytes,
            expected_sha256=expected_sha256,
            code=f"B4E_PROVENANCE_{name.upper()}",
        )
        if not verified:
            continue
        value = _load_strict(report, path, f"B4E_PROVENANCE_{name.upper()}")
        if value is not None:
            values[name] = value
    if set(values) != set(B4E_PROVENANCE_FILES):
        return {}, {}, {}

    events = values["events"]
    acquisitions = values["acquisitions"]
    active_traces = values["active_traces"]
    report.require(events.get("schema") == "SIM13_V4B4E_EVENT_INPUTS_V1", "B4E_EVENT_TEMPLATE_SCHEMA")
    report.require(acquisitions.get("schema") == "SIM13_V4B4E_ACQUISITION_LEDGER_V1", "B4E_ACQUISITION_TEMPLATE_SCHEMA")
    report.require(active_traces.get("schema") == "SIM13_V4B4E_ACTIVE_TRACES_V1", "B4E_ACTIVE_TRACE_TEMPLATE_SCHEMA")
    event_rows = events.get("runs")
    acquisition_rows = acquisitions.get("runs")
    active_rows = active_traces.get("runs")
    expected_run_ids = [lane.lower() for lane in LANES]
    if not report.require(
        isinstance(event_rows, list)
        and [row.get("run_id") for row in event_rows if isinstance(row, dict)] == expected_run_ids,
        "B4E_EVENT_TEMPLATE_RUN_SET_ORDER",
    ):
        return {}, {}, {}
    if not report.require(
        isinstance(acquisition_rows, dict)
        and list(acquisition_rows) == expected_run_ids,
        "B4E_ACQUISITION_TEMPLATE_RUN_SET_ORDER",
    ):
        return {}, {}, {}
    if not report.require(
        isinstance(active_rows, dict)
        and list(active_rows) == expected_run_ids,
        "B4E_ACTIVE_TRACE_TEMPLATE_RUN_SET_ORDER",
    ):
        return {}, {}, {}

    event_by_lane: dict[str, dict[str, Any]] = {}
    acquisition_by_lane: dict[str, dict[str, Any]] = {}
    active_by_lane: dict[str, dict[str, np.ndarray]] = {}
    event_by_run = {str(row["run_id"]): row for row in event_rows}
    for lane in LANES:
        run_id = lane.lower()
        event = event_by_run[run_id]
        acquisition = acquisition_rows.get(run_id)
        active = active_rows.get(run_id)
        method, step_s = LANE_DEFINITIONS[lane]
        report.require(
            isinstance(event, dict)
            and event.get("method") == method
            and _same_float(event.get("step_s"), step_s),
            "B4E_EVENT_TEMPLATE_LANE_DEFINITION",
            lane,
        )
        if not report.require(isinstance(acquisition, dict), "B4E_ACQUISITION_TEMPLATE_OBJECT", lane):
            continue
        if not report.require(isinstance(active, dict), "B4E_ACTIVE_TRACE_TEMPLATE_OBJECT", lane):
            continue
        report.require(acquisition.get("run_id") == run_id, "B4E_ACQUISITION_TEMPLATE_RUN_ID", lane)
        report.require(
            _same_float(acquisition.get("acquisition_time_s"), event.get("time_s")),
            "B4E_EVENT_ACQUISITION_TEMPLATE_TIME",
            lane,
        )
        event_by_lane[lane] = dict(event)
        compact_acquisition = dict(acquisition)
        compact_acquisition.pop("matrices", None)
        acquisition_by_lane[lane] = compact_acquisition
        trace = active.get("trace")
        if not report.require(isinstance(trace, dict), "B4E_ACTIVE_TRACE_PAYLOAD_OBJECT", lane):
            continue
        report.require(
            active.get("run_id") == run_id
            and active.get("method") == method
            and _same_float(active.get("step_s"), step_s)
            and _same_float(active.get("acquisition_time_s"), event.get("time_s"))
            and _same_float(active.get("active_end_time_s"), 0.08)
            and active.get("synthetic_removal_executed") is False,
            "B4E_ACTIVE_TRACE_HEADER",
            lane,
        )
        joint = np.asarray(trace.get("service_joint_coordinates_mixed"), dtype="<f8")
        eta = np.asarray(trace.get("eta_mixed"), dtype="<f8")
        count = len(trace.get("time_s", [])) if isinstance(trace.get("time_s"), list) else -1
        if not report.require(
            count >= 2 and joint.shape == (count, 8) and eta.shape == (count, 14),
            "B4E_ACTIVE_TRACE_CORE_SHAPES",
            lane,
        ):
            continue
        mapped = {
            "time_s": np.asarray(trace["time_s"], dtype="<f8"),
            "service_position_m": np.asarray(trace["service_position_m"], dtype="<f8"),
            "service_quaternion_wxyz": np.asarray(trace["service_quaternion_wxyz"], dtype="<f8"),
            "R_joint_coordinates_rad": joint[:, :6],
            "P_joint_coordinates_m": joint[:, 6:8],
            "base_linear_m_s": eta[:, :3],
            "base_angular_rad_s": eta[:, 3:6],
            "R_joint_rad_s": eta[:, 6:12],
            "P_joint_m_s": eta[:, 12:14],
            "left_gap_m": np.asarray(trace["left_gap_m"], dtype="<f8"),
            "right_gap_m": np.asarray(trace["right_gap_m"], dtype="<f8"),
            "left_gap_rate_m_s": np.asarray(trace["left_gap_rate_m_s"], dtype="<f8"),
            "right_gap_rate_m_s": np.asarray(trace["right_gap_rate_m_s"], dtype="<f8"),
        }
        report.require(
            set(mapped) == A0_PARENT_ARRAYS
            and all(len(array) == count and np.all(np.isfinite(array)) for array in mapped.values()),
            "B4E_ACTIVE_TRACE_MAPPED_ARRAYS",
            lane,
        )
        active_by_lane[lane] = mapped
    report.require(set(event_by_lane) == set(LANES), "B4E_EVENT_TEMPLATE_LANE_COVERAGE")
    report.require(set(acquisition_by_lane) == set(LANES), "B4E_ACQUISITION_TEMPLATE_LANE_COVERAGE")
    report.require(set(active_by_lane) == set(LANES), "B4E_ACTIVE_TRACE_TEMPLATE_LANE_COVERAGE")
    return event_by_lane, acquisition_by_lane, active_by_lane


_SOURCE_INVENTORY_EXCLUDED_DIRECTORIES = frozenset({
    "evidence", "results", "__pycache__", ".pytest_cache", ".smoke",
    "raw_cases",
})
_VALIDATOR_INTERCHANGE_CONTRACTS = frozenset({
    "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json",
    "PHASE_B4G_MUTATION_ARTIFACT_INTERCHANGE_V1.json",
    "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json",
})


def _generated_directory_name(name: str) -> bool:
    """Identify generated test/smoke/cache trees before filesystem descent."""

    return bool(
        name in {"__pycache__", ".pytest_cache", ".smoke"}
        or name.startswith(".pytest")
        or name.startswith(".smoke")
    )


def _walk_phase_files_prepruned(
    phase_root: Path,
    *,
    exclude_source_derived_trees: bool,
) -> list[Path]:
    """Walk phase files without ever descending into generated long-path trees."""

    root = phase_root.resolve()
    if not root.is_dir():
        raise ValueError("PHASE_ROOT_NOT_DIRECTORY")

    def walk_error(error: OSError) -> None:
        raise error

    candidates: list[Path] = []
    for current, directory_names, file_names in os.walk(
        root, topdown=True, onerror=walk_error, followlinks=False,
    ):
        directory_names[:] = sorted(
            name for name in directory_names
            if not _generated_directory_name(name)
            and not (
                exclude_source_derived_trees
                and name in _SOURCE_INVENTORY_EXCLUDED_DIRECTORIES
            )
        )
        current_path = Path(current)
        candidates.extend(current_path / name for name in sorted(file_names))
    return candidates


def _independent_local_source_inventory(
    project_root: Path,
    phase_root: Path,
) -> list[dict[str, Any]]:
    """Independently enumerate the complete B4G source allowlist.

    This is an intentionally local transcription of the frozen inventory
    semantics.  It does not import the producer's source guard and therefore
    detects a coordinated omission from both the campaign identity and signed
    execution manifest.
    """

    project = project_root.resolve()
    phase = phase_root.resolve()
    try:
        phase.relative_to(project)
    except ValueError as error:
        raise ValueError("PHASE_ROOT_OUTSIDE_PROJECT") from error
    records: list[dict[str, Any]] = []
    candidates = _walk_phase_files_prepruned(
        phase, exclude_source_derived_trees=True,
    )
    for path in sorted(
        candidates, key=lambda item: item.relative_to(phase).as_posix(),
    ):
        relative = path.relative_to(phase)
        if not path.is_file() or any(
            part in _SOURCE_INVENTORY_EXCLUDED_DIRECTORIES
            or _generated_directory_name(part)
            for part in relative.parts
        ):
            continue
        is_python_source = path.suffix.lower() == ".py"
        is_frozen_contract = bool(
            len(relative.parts) >= 2
            and relative.parts[0] == "contracts"
            and path.suffix.lower() == ".json"
        )
        is_validator_interchange = bool(
            len(relative.parts) == 2
            and relative.parts[0] == "b4g_validation"
            and relative.name in _VALIDATOR_INTERCHANGE_CONTRACTS
        )
        is_test_configuration = relative.as_posix() == "pytest.ini"
        if not (
            is_python_source
            or is_frozen_contract
            or is_validator_interchange
            or is_test_configuration
        ):
            continue
        project_relative = path.resolve().relative_to(project).as_posix()
        phase_relative = relative.as_posix()
        records.append({
            "id": f"local::{phase_relative}",
            "path": project_relative,
            "role": "B4G_FROZEN_CONTRACT_SOURCE_TEST_OR_WORKFLOW",
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def _validate_independent_local_source_inventory(
    report: ValidationReport,
    local_sources: Any,
    frozen_tuples: set[tuple[Any, Any, Any]],
    *,
    project_root: Path,
    phase_root: Path,
) -> list[dict[str, Any]] | None:
    """Bind both self-reported inventories to an independent current walk."""

    independent_inventory = report.guard(
        "CAMPAIGN_INDEPENDENT_LOCAL_SOURCE_INVENTORY_ENUMERATION",
        lambda: _independent_local_source_inventory(project_root, phase_root),
    )
    if independent_inventory is None:
        return None
    report.require(
        local_sources == independent_inventory,
        "CAMPAIGN_LOCAL_SOURCE_NOT_EXACT_INDEPENDENT_ALLOWLIST_INVENTORY",
        {
            "reported_count": len(local_sources) if isinstance(local_sources, list) else None,
            "independent_count": len(independent_inventory),
        },
    )
    independently_current_tuples = {
        (row["path"], row["bytes"], row["sha256"])
        for row in independent_inventory
    }
    report.require(
        frozen_tuples == independently_current_tuples,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_NOT_EXACT_INDEPENDENT_ALLOWLIST_INVENTORY",
        {
            "frozen_count": len(frozen_tuples),
            "independent_count": len(independently_current_tuples),
        },
    )
    return independent_inventory


def _validate_execution_source_freeze(
    report: ValidationReport,
    identity: Mapping[str, Any],
    local_sources: Any,
) -> None:
    """Independently expand the signed execution terminal->gate->manifest chain."""

    freeze = identity.get("execution_source_freeze")
    expected_terminal = identity.get(
        "expected_execution_source_freeze_terminal_sha256",
    )
    if not report.require(
        isinstance(freeze, Mapping) and freeze.get("pass") is True,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_MISSING_OR_NOT_PASS",
    ):
        return
    assert isinstance(freeze, Mapping)
    report.require(
        is_sha256(expected_terminal)
        and freeze.get("expected_terminal_sha256") == expected_terminal,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_EXPECTED_TERMINAL",
    )
    terminal_path = Path(str(freeze.get("terminal_path"))).resolve()
    report.require(
        _inside_project(terminal_path),
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_OUTSIDE_PROJECT",
        terminal_path.as_posix(),
    )
    terminal_ok = verify_file_record(
        report, path=terminal_path,
        expected_bytes=freeze.get("terminal_bytes"),
        expected_sha256=expected_terminal,
        code="CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL",
    )
    terminal = (
        _load_strict(report, terminal_path, "CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL")
        if terminal_ok else None
    )
    if terminal is not None:
        report.require(
            terminal.get("self_excluded") is True
            and terminal.get("acyclic") is True,
            "CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_DAG",
        )
    terminal_records = freeze.get("terminal_records", [])
    report.require(
        isinstance(terminal_records, list) and bool(terminal_records),
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_RECORDS",
    )
    _validate_record_set(
        report, terminal_records,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_RECORD",
    )

    gate_path = Path(str(freeze.get("gate_path"))).resolve()
    report.require(
        _inside_project(gate_path),
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE_OUTSIDE_PROJECT",
        gate_path.as_posix(),
    )
    gate_sha = freeze.get("gate_sha256")
    gate_ok = report.require(
        gate_path.is_file() and is_sha256(gate_sha)
        and sha256_file(gate_path) == gate_sha,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE_HASH",
    )
    gate = (
        _load_strict(report, gate_path, "CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE")
        if gate_ok else None
    )
    if gate is not None:
        report.require(
            gate.get("final") is True,
            "CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE_NOT_FINAL",
        )

    manifest_path = Path(str(freeze.get("manifest_path"))).resolve()
    report.require(
        _inside_project(manifest_path),
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_MANIFEST_OUTSIDE_PROJECT",
        manifest_path.as_posix(),
    )
    manifest_sha = freeze.get("manifest_sha256")
    manifest_ok = report.require(
        manifest_path.is_file() and is_sha256(manifest_sha)
        and sha256_file(manifest_path) == manifest_sha,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_MANIFEST_HASH",
    )
    manifest = (
        _load_strict(report, manifest_path, "CAMPAIGN_EXECUTION_SOURCE_FREEZE_MANIFEST")
        if manifest_ok else None
    )
    if manifest is not None:
        report.require(
            manifest.get("self_excluded") is True,
            "CAMPAIGN_EXECUTION_SOURCE_FREEZE_MANIFEST_NOT_SELF_EXCLUDED",
        )
    sources = freeze.get("sources", [])
    report.require(
        isinstance(sources, list) and bool(sources)
        and freeze.get("source_count") == len(sources),
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_SOURCE_COUNT",
    )
    _validate_record_set(
        report, sources, "CAMPAIGN_EXECUTION_SOURCE_FREEZE_SOURCE",
    )
    sources_hash = report.guard(
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_SOURCE_HASH_RECOMPUTATION",
        lambda: canonical_sha256(sources),
    )
    report.require(
        sources_hash is not None
        and freeze.get("sources_canonical_sha256") == sources_hash,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_SOURCE_HASH",
    )
    frozen_tuples = {
        (
            row.get("declared_path"), row.get("actual_bytes"),
            row.get("actual_sha256"),
        )
        for row in sources if isinstance(row, Mapping)
    }
    current_tuples = {
        (row.get("path"), row.get("bytes"), row.get("sha256"))
        for row in local_sources if isinstance(row, Mapping)
    }
    report.require(
        frozen_tuples == current_tuples,
        "CAMPAIGN_EXECUTION_SOURCE_FREEZE_NOT_CURRENT_LOCAL_INVENTORY",
    )
    _validate_independent_local_source_inventory(
        report,
        local_sources,
        frozen_tuples,
        project_root=PROJECT_ROOT,
        phase_root=PHASE_ROOT,
    )


def _load_campaign_bundle(
    report: ValidationReport,
    contracts: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    paths = {
        "pre": EVIDENCE_ROOT / "SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
        "source": EVIDENCE_ROOT / "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json",
        "reference": EVIDENCE_ROOT / "SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1.json",
        "schedule": EVIDENCE_ROOT / "SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json",
        "a0_parent": EVIDENCE_ROOT / "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1.json",
        "post": EVIDENCE_ROOT / "SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
        "summary": RESULTS_ROOT / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
    }
    values: dict[str, dict[str, Any]] = {}
    for key, path in paths.items():
        value = _load_strict(report, path, f"CAMPAIGN_{key.upper()}")
        if value is not None:
            values[key] = value
            _require_canonical_json(report, path, value, f"CAMPAIGN_{key.upper()}")
    if len(values) != len(paths):
        return None
    report.require(values["schedule"] == contracts["schedule"], "PUBLISHED_SCHEDULE_NOT_FROZEN_SCHEDULE")
    for side in ("pre", "post"):
        snapshot = values[side]
        report.require(snapshot.get("pass") is True, f"{side.upper()}_SNAPSHOT_NOT_PASS")
        report.require(snapshot.get("bound_parent_count") == 11, f"{side.upper()}_SNAPSHOT_PARENT_COUNT")
        report.require(snapshot.get("local_forbidden_artifacts") == [], f"{side.upper()}_FORBIDDEN_ARTIFACT")
        rows = snapshot.get("bound_parents", [])
        report.require(len(rows) == 11 and all(row.get("pass") is True for row in rows), f"{side.upper()}_BOUND_PARENTS")
    report.require(
        values["pre"].get("snapshot_payload_sha256") == values["post"].get("snapshot_payload_sha256"),
        "PRE_POST_PROTECTED_SNAPSHOT_DRIFT",
    )
    source = values["source"]
    report.require(source.get("self_excluded") is True and source.get("acyclic") is True, "CAMPAIGN_SOURCE_DAG")
    identity = source.get("identity", {})
    local_sources = identity.get("local_sources", [])
    _validate_record_set(report, local_sources, "CAMPAIGN_LOCAL_SOURCE")
    report.require(identity.get("local_source_count") == len(local_sources), "CAMPAIGN_LOCAL_SOURCE_COUNT")
    report.require(canonical_sha256(local_sources) == identity.get("local_source_inventory_sha256"), "CAMPAIGN_LOCAL_SOURCE_INVENTORY_HASH")
    required_independent_validator_sources = (
        PHASE_ROOT / "validate_phase_b4g_evidence.py",
        PHASE_ROOT / "b4g_validation" / "core.py",
        PHASE_ROOT / "b4g_validation" / "validator.py",
        PHASE_ROOT / "b4g_validation" / "mutation_replay.py",
        PHASE_ROOT / "b4g_validation" / "artifact_derivation.py",
        PHASE_ROOT / "b4g_validation" / "geometry_replay.py",
        PHASE_ROOT / "b4g_validation" / "forced_propagation_replay.py",
        PHASE_ROOT / "b4g_validation" / "supplemental_replay.py",
        PHASE_ROOT / "b4g_validation" / "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json",
        PHASE_ROOT / "b4g_validation" / "PHASE_B4G_MUTATION_ARTIFACT_INTERCHANGE_V1.json",
        PHASE_ROOT / "b4g_validation" / "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json",
    )
    local_source_by_path = {
        str(row.get("path")): row
        for row in local_sources if isinstance(row, Mapping)
    }
    for required_path in required_independent_validator_sources:
        relative = required_path.resolve().relative_to(PROJECT_ROOT).as_posix()
        row = local_source_by_path.get(relative)
        report.require(
            isinstance(row, Mapping)
            and row.get("bytes") == required_path.stat().st_size
            and row.get("sha256") == sha256_file(required_path),
            "CAMPAIGN_INDEPENDENT_VALIDATOR_SOURCE_NOT_HASH_BOUND",
            relative,
        )
    forced_solver_relative = (
        "30_simulation/sim_13_physics_gated_embodied_grasping/"
        "v4_synthetic_contact_capture_diagnostic/"
        "phase_b4g_post_freeze_synthetic_jaw_retraction_execution/"
        "b4g_solver/forced_retraction.py"
    )
    forced_solver_rows = [
        row for row in local_sources
        if isinstance(row, Mapping) and row.get("path") == forced_solver_relative
    ]
    report.require(
        len(forced_solver_rows) == 1
        and forced_solver_rows[0].get("bytes") == 53722
        and forced_solver_rows[0].get("sha256")
        == "E337E79F7F5D5095080ABDE93DF9982F80A0AD925E0F21FDA90D527AA075F239",
        "CAMPAIGN_FROZEN_POST_RELEASE_FUNCTION_SOURCE_BINDING",
    )
    contract_sources = [
        row for row in local_sources
        if isinstance(row, Mapping) and "/contracts/" in f"/{row.get('path', '')}"
    ]
    report.require(
        canonical_sha256(contract_sources) == identity.get("contract_bundle_sha256"),
        "CAMPAIGN_CONTRACT_BUNDLE_HASH_NOT_RECOMPUTED",
    )
    anchors = identity.get("signed_preregistration_anchors", [])
    report.require(len(anchors) == 3 and all(row.get("pass") is True for row in anchors), "CAMPAIGN_SIGNED_PREREG_ANCHORS")
    expected_anchor_hashes = {value[2] for key, value in PREREGISTRATION_FILES.items() if key != "test_result"}
    report.require({row.get("actual_sha256") for row in anchors} == expected_anchor_hashes, "CAMPAIGN_SIGNED_PREREG_ANCHOR_HASH_SET")
    report.require(
        canonical_sha256(anchors)
        == identity.get("signed_preregistration_anchor_set_sha256"),
        "CAMPAIGN_SIGNED_PREREGISTRATION_ANCHOR_SET_HASH_NOT_RECOMPUTED",
    )
    prereg_sources = identity.get("preregistration_source_verification", {})
    prereg_records = (
        prereg_sources.get("records", [])
        if isinstance(prereg_sources, Mapping) else []
    )
    report.require(
        isinstance(prereg_sources, Mapping)
        and prereg_sources.get("pass") is True
        and prereg_sources.get("schema")
        == "SIM13_V4B4G_PREREGISTRATION_SOURCE_MANIFEST_V1"
        and prereg_sources.get("self_excluded") is True
        and prereg_sources.get("record_count") == 19
        and len(prereg_records) == 19,
        "CAMPAIGN_PREREGISTRATION_SOURCE_VERIFICATION_HEADER",
    )
    _validate_record_set(
        report, prereg_records, "CAMPAIGN_PREREGISTRATION_SOURCE_RECORD",
    )
    prereg_records_hash = report.guard(
        "CAMPAIGN_PREREGISTRATION_SOURCE_RECORD_HASH_RECOMPUTATION",
        lambda: canonical_sha256(prereg_records),
    )
    report.require(
        prereg_records_hash is not None
        and prereg_sources.get("records_canonical_sha256") == prereg_records_hash
        and identity.get("preregistration_source_records_sha256")
        == prereg_records_hash,
        "CAMPAIGN_PREREGISTRATION_SOURCE_RECORD_HASH",
    )
    prereg_manifest_path, prereg_manifest_bytes, prereg_manifest_sha = (
        PREREGISTRATION_FILES["source_manifest"]
    )
    report.require(
        prereg_sources.get("manifest_bytes") == prereg_manifest_bytes
        and prereg_sources.get("manifest_sha256") == prereg_manifest_sha,
        "CAMPAIGN_PREREGISTRATION_SOURCE_MANIFEST_IDENTITY",
    )
    _validate_execution_source_freeze(report, identity, local_sources)
    recursive = source.get("recursive_parent_verification", {})
    report.require(recursive.get("pass") is True and recursive.get("direct_binding_count") == 11, "CAMPAIGN_RECURSIVE_PARENT_VERIFICATION")
    for field in (
        "direct_bindings", "b4f_terminal_records", "b4f_evidence_records",
        "b4e_terminal_records", "b4e_evidence_records", "b4e_source_records",
        "b4_terminal_records",
    ):
        rows = recursive.get(field, [])
        report.require(isinstance(rows, list) and rows and all(row.get("pass") is True for row in rows), f"RECURSIVE_{field.upper()}")
        _validate_record_set(report, rows, f"RECURSIVE_{field.upper()}_BYTES")
    report.require(recursive.get("frozen_b4_gate_sha256") == "55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92", "RECURSIVE_B4_GATE_HASH")
    report.require(recursive.get("frozen_b4_terminal_sha256") == "09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E", "RECURSIVE_B4_TERMINAL_HASH")
    event_templates, acquisition_templates, active_trace_templates = _load_b4e_provenance_templates(report)
    reference = values["reference"]
    native = reference.get("native_recomputation", {})
    frozen_reference = contracts["reference"]
    report.require(reference.get("one_common_Q_ref_per_finger_N") == frozen_reference.get("individual_finger_reference_force_N"), "REFERENCE_QREF_EXACT")
    report.require(native.get("passed") is True, "REFERENCE_NATIVE_RECOMPUTATION")
    report.require(reference.get("per_lane_or_treatment_rescaling_used") is False, "REFERENCE_PER_LANE_RESCALING")
    report.require(reference.get("explicit_matrix_inverse_used") is False, "REFERENCE_EXPLICIT_INVERSE")
    report.require(reference.get("claim_boundary") == CLAIM_BOUNDARY, "REFERENCE_CLAIM_BOUNDARY")
    a0_parent = values["a0_parent"]
    report.require(
        set(a0_parent) == {
            "schema", "fresh_generation", "source_bindings",
            "b4e_active_traces_binding", "interchange_contract",
            "trace_count", "traces", "claim_boundary",
        },
        "A0_PARENT_MANIFEST_FIELDS",
    )
    report.require(a0_parent.get("schema") == "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1", "A0_PARENT_MANIFEST_SCHEMA")
    report.require(a0_parent.get("fresh_generation") is True, "A0_PARENT_NOT_FRESH")
    report.require(a0_parent.get("trace_count") == 6 and len(a0_parent.get("traces", [])) == 6, "A0_PARENT_TRACE_COUNT")
    report.require(a0_parent.get("source_bindings") == {
        "b4e_solver_sha256": "7AAF83E067019B3CA69FF78E61CADBC25BF9FAEC94699E7EA388859D8144295D",
        "b4e_run_spec_sha256": "4C4A6708A0784DCAD5004CF657D22D372DE2C5269EE33401B55A3441A7F9E76B",
        "b4e_audited_gate_sha256": "8F644E69F626793989488C8D8FF3803F9F1354C6D637E1E237044A55421C896E",
        "b4e_terminal_sha256": "09047EF1B605BBE288545564EC1BF71D0184A330FAABDA11D8A1B123584D60A6",
    }, "A0_PARENT_SOURCE_BINDINGS")
    interchange_path = (
        PHASE_ROOT / "b4g_validation"
        / "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json"
    ).resolve()
    interchange_binding = a0_parent.get("interchange_contract", {})
    report.require(
        isinstance(interchange_binding, Mapping)
        and set(interchange_binding) == {"path", "bytes", "sha256"},
        "A0_PARENT_INTERCHANGE_BINDING_FIELDS",
    )
    if isinstance(interchange_binding, Mapping):
        declared_interchange = resolve_declared(
            PROJECT_ROOT, PHASE_ROOT, interchange_binding.get("path"),
        )
        report.require(
            declared_interchange == interchange_path,
            "A0_PARENT_INTERCHANGE_BINDING_PATH",
        )
        verify_file_record(
            report, path=declared_interchange,
            expected_bytes=interchange_binding.get("bytes"),
            expected_sha256=interchange_binding.get("sha256"),
            code="A0_PARENT_INTERCHANGE_BINDING",
        )
    active_path, active_bytes, active_sha256 = B4E_PROVENANCE_FILES["active_traces"]
    active_binding = a0_parent.get("b4e_active_traces_binding", {})
    report.require(
        isinstance(active_binding, dict)
        and set(active_binding) == {"path", "bytes", "sha256"},
        "A0_PARENT_ACTIVE_TRACE_BINDING_FIELDS",
    )
    if isinstance(active_binding, dict):
        declared_active = resolve_declared(
            PROJECT_ROOT, PHASE_ROOT, active_binding.get("path"),
        )
        report.require(declared_active == active_path.resolve(), "A0_PARENT_ACTIVE_TRACE_BINDING_PATH")
        verify_file_record(
            report,
            path=declared_active,
            expected_bytes=active_binding.get("bytes"),
            expected_sha256=active_binding.get("sha256"),
            code="A0_PARENT_ACTIVE_TRACE_BINDING",
        )
        report.require(
            active_binding.get("bytes") == active_bytes
            and active_binding.get("sha256") == active_sha256,
            "A0_PARENT_ACTIVE_TRACE_BINDING_FROZEN_IDENTITY",
        )
    report.require(a0_parent.get("claim_boundary") == "fresh hash-bound parent reference for independent A0 replay only; no new release or physical credit", "A0_PARENT_CLAIM_BOUNDARY")
    summary = values["summary"]
    report.require(summary.get("schema") == "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1", "SUMMARY_SCHEMA")
    report.require(summary.get("status") == "CAMPAIGN_EXECUTION_COMPLETE_PENDING_NEGATIVE_CONTROLS_VALIDATOR_AND_INDEPENDENT_AUDIT", "SUMMARY_STATUS")
    report.require(summary.get("final") is False, "SUMMARY_MUST_NOT_BE_FINAL")
    report.require(summary.get("logical_slot_count") == 144, "SUMMARY_LOGICAL_SLOT_COUNT")
    report.require(summary.get("one_common_Q_ref_per_finger_N") == frozen_reference.get("individual_finger_reference_force_N"), "SUMMARY_QREF")
    report.require(summary.get("claim_boundary") == CLAIM_BOUNDARY, "SUMMARY_CLAIM_BOUNDARY")
    orchestration = summary.get("orchestration", {})
    report.require(orchestration.get("discovery_wave_count") == 114, "SUMMARY_DISCOVERY_COUNT")
    report.require(orchestration.get("conditional_a2_and_post_wave_count") == 30, "SUMMARY_CONDITIONAL_COUNT")
    report.require(orchestration.get("slot_index_semantics_unchanged") is True, "SUMMARY_SLOT_SEMANTICS")
    report.require(orchestration.get("hidden_mutable_state_or_event_cache_between_cases") is False, "SUMMARY_HIDDEN_STATE")
    report.require(summary.get("signed_preregistration_anchors") == anchors, "SUMMARY_PREREG_ANCHORS")
    report.observations["campaign_source_bundle"] = {
        "local_source_count": len(local_sources),
        "recursive_parent_direct_count": recursive.get("direct_binding_count"),
        "protected_snapshot_sha256": values["pre"].get("snapshot_payload_sha256"),
    }
    return summary, {
        **identity,
        "_a0_parent_manifest": a0_parent,
        "_b4e_event_templates": event_templates,
        "_b4e_acquisition_templates": acquisition_templates,
        "_b4e_active_trace_templates": active_trace_templates,
    }


def _gate_by_id(report: ValidationReport, metadata: Mapping[str, Any], case_id: str) -> dict[str, dict[str, Any]]:
    records = metadata.get("gate_records", [])
    if not report.require(isinstance(records, list), "CASE_GATE_RECORDS_NOT_LIST", case_id):
        return {}
    result: dict[str, dict[str, Any]] = {}
    allowed_na = {
        "A2_NOT_EVALUATED_NO_A1_PARENT", "NO_FINITE_REMOVAL_EVENT",
        "CASE_TERMINATED_GEOMETRY_BEFORE_EVENT", "CASE_TERMINATED_GEOMETRY_BEFORE_OUTCOME",
    }
    for record in records:
        if not report.require(
            isinstance(record, Mapping), "CASE_GATE_RECORD_NOT_OBJECT", case_id,
        ):
            continue
        exact_key_set(report, record, ("gate_id", "evaluation_status", "scientific_predicate", "applicability_reason", "detail"), "CASE_GATE_FIELDS")
        gate_id = record.get("gate_id")
        report.require(isinstance(gate_id, str) and any(gate_id.startswith(prefix) for prefix in GATES), "CASE_GATE_ID_INVALID", {"case_id": case_id, "gate_id": gate_id})
        report.require(gate_id not in result, "CASE_GATE_DUPLICATE", {"case_id": case_id, "gate_id": gate_id})
        status = record.get("evaluation_status")
        report.require(status in {"PASS", "FAIL", "NOT_APPLICABLE"}, "CASE_GATE_STATUS", {"case_id": case_id, "gate_id": gate_id})
        if status == "NOT_APPLICABLE":
            report.require(record.get("scientific_predicate") is None, "CASE_GATE_NA_PREDICATE", {"case_id": case_id, "gate_id": gate_id})
            report.require(record.get("applicability_reason") in allowed_na, "CASE_GATE_NA_REASON", {"case_id": case_id, "gate_id": gate_id, "reason": record.get("applicability_reason")})
        else:
            report.require(isinstance(record.get("scientific_predicate"), bool), "CASE_GATE_PREDICATE_TYPE", {"case_id": case_id, "gate_id": gate_id})
        result[str(gate_id)] = record
    return result


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    implementation = getattr(np, "trapezoid", None)
    return float(implementation(y, x)) if implementation is not None else float(np.trapz(y, x))


def _max_vector_drift(array: np.ndarray) -> float:
    if len(array) == 0:
        return math.inf
    return float(np.max(np.linalg.norm(array - array[0], axis=1)))


def _profile(times: np.ndarray, *, acquisition: float, alpha: float, delay: float, duration: float, qref: float) -> np.ndarray:
    start = acquisition + delay
    end = start + duration
    values = np.zeros_like(times, dtype=float)
    if duration <= 0.0 or alpha == 0.0:
        return values
    interior = (times > start) & (times < end)
    values[interior] = alpha * qref * np.sin(np.pi * (times[interior] - start) / duration) ** 2
    return values


def _require_shape(report: ValidationReport, array: np.ndarray, shape: tuple[Any, ...], code: str) -> None:
    matches = len(array.shape) == len(shape) and all(expected is None or actual == expected for actual, expected in zip(array.shape, shape))
    report.require(matches, code, {"expected": shape, "actual": array.shape})


def _same_float(left: Any, right: Any, *, atol: float = 1.0e-15) -> bool:
    """Compare registered scalar fields without accepting coercion or NaN."""

    return bool(finite_number(left) and finite_number(right) and abs(float(left) - float(right)) <= atol)


def _reject_displaced_governance_claims(
    report: ValidationReport,
    value: Any,
    *,
    required_false: Mapping[str, Any],
    required_null_names: Any,
    code: str,
    path: str = "$",
) -> None:
    """Reject governance-credit fields smuggled outside their canonical map."""

    null_names = set(required_null_names)
    if isinstance(value, Mapping):
        for key, item in value.items():
            item_path = f"{path}/{key}"
            if key in required_false:
                report.require(
                    item is False,
                    f"{code}_REQUIRED_FALSE_DISPLACED",
                    {"path": item_path, "value": item},
                )
            if key in null_names:
                report.require(
                    item is None,
                    f"{code}_REQUIRED_NULL_DISPLACED",
                    {"path": item_path, "value": item},
                )
            if key in {"final", "audited", "validator_pass_claimed"}:
                report.require(
                    item is False,
                    f"{code}_TERMINAL_CREDIT_DISPLACED",
                    {"path": item_path, "value": item},
                )
            if key == "owner_override_used":
                report.require(
                    item is False,
                    f"{code}_OWNER_OVERRIDE_DISPLACED",
                    {"path": item_path, "value": item},
                )
            _reject_displaced_governance_claims(
                report, item, required_false=required_false,
                required_null_names=null_names, code=code, path=item_path,
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_displaced_governance_claims(
                report, item, required_false=required_false,
                required_null_names=null_names, code=code,
                path=f"{path}/{index}",
            )


def _expected_command_sides(
    slot: Mapping[str, Any],
    selected_parent: Mapping[str, Any] | None,
) -> tuple[dict[str, float], dict[str, float]] | None:
    arm = slot.get("arm")
    zero = {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0}
    if arm == "A0":
        return dict(zero), dict(zero)
    if arm == "A1":
        side = {
            "alpha": float(slot["alpha"]),
            "delay_s": 0.0,
            "duration_s": float(slot["command_duration_s"]),
        }
        return dict(side), dict(side)
    if arm != "A2" or not isinstance(selected_parent, Mapping):
        return None
    alpha = float(selected_parent["alpha"])
    duration = float(selected_parent["command_duration_s"])
    full = {"alpha": alpha, "delay_s": 0.0, "duration_s": duration}
    off = {"alpha": 0.0, "delay_s": 0.0, "duration_s": duration}
    half = {"alpha": 0.5 * alpha, "delay_s": 0.005, "duration_s": duration}
    variant = slot.get("variant_id")
    if variant == "RIGHT_HALF_DELAY":
        return dict(full), dict(half)
    if variant == "LEFT_HALF_DELAY_MIRROR":
        return dict(half), dict(full)
    if variant == "RIGHT_COMMAND_OFF":
        return dict(full), dict(off)
    if variant == "LEFT_COMMAND_OFF_MIRROR":
        return dict(off), dict(full)
    return None


def _validate_registered_command(
    report: ValidationReport,
    metadata: Mapping[str, Any],
    slot: Mapping[str, Any],
) -> bool:
    """Bind every command degree of freedom to the frozen registered slot."""

    command = metadata.get("command_parameters", {})
    parent = command.get("selected_parent_level")
    if slot.get("arm") == "A2":
        parent_ok = report.require(isinstance(parent, dict), "CASE_A2_SELECTED_PARENT_MISSING", metadata.get("case_id"))
    else:
        parent_ok = report.require(parent is None, "CASE_NON_A2_SELECTED_PARENT_PRESENT", metadata.get("case_id"))
    try:
        expected = _expected_command_sides(slot, parent if isinstance(parent, Mapping) else None)
    except (KeyError, TypeError, ValueError):
        expected = None
    command_ok = report.require(expected is not None, "CASE_REGISTERED_COMMAND_UNRESOLVED", metadata.get("case_id"))
    if expected is None:
        return False
    for side_name, expected_side in zip(("left", "right"), expected):
        actual_side = command.get(side_name, {})
        for field, expected_value in expected_side.items():
            command_ok &= report.require(
                _same_float(actual_side.get(field), expected_value),
                "CASE_REGISTERED_COMMAND_MISMATCH",
                {
                    "case_id": metadata.get("case_id"), "side": side_name,
                    "field": field, "expected": expected_value,
                    "actual": actual_side.get(field),
                },
            )
    return bool(parent_ok and command_ok)


def _expected_stage_rows(
    time: np.ndarray,
    *,
    method: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Reconstruct the exact stored/stage sequence for an accepted trace."""

    codes: list[int] = [0]
    times: list[float] = [float(time[0])]
    cycle = (1, 2, 3, 4, 0) if method == "rk4" else (1, 5, 0)
    for left, right in zip(time[:-1], time[1:]):
        left_value = float(left); right_value = float(right)
        middle = left_value + 0.5 * (right_value - left_value)
        if method == "rk4":
            times.extend((left_value, middle, middle, right_value, right_value))
        else:
            times.extend((left_value, middle, right_value))
        codes.extend(cycle)
    return np.asarray(codes, dtype=np.int64), np.asarray(times, dtype=np.float64)


def _validate_stage_contract(
    report: ValidationReport,
    *,
    prefix: str,
    lane: str,
    sample_time: np.ndarray,
    sample_service: np.ndarray,
    stage_time: np.ndarray,
    stage_code: np.ndarray,
    stage_service: np.ndarray,
    stage_flags: np.ndarray,
    domain_exit: bool,
    sample_target: np.ndarray | None = None,
    stage_target: np.ndarray | None = None,
) -> bool:
    """Verify method, step grid, stage code pattern and stored-row identity."""

    method, frozen_step = LANE_DEFINITIONS[lane]
    ok = True
    if len(sample_time) >= 2:
        differences = np.diff(sample_time)
        ok &= report.require(bool(np.all(differences > 0.0)), f"{prefix}_SAMPLE_TIME_ORDER", lane)
        ok &= report.require(bool(np.all(differences <= frozen_step + 1.0e-14)), f"{prefix}_SAMPLE_STEP_MAX", lane)
        if len(differences) > 1:
            ok &= report.require(bool(np.all(np.abs(differences[:-1] - frozen_step) <= 1.0e-14)), f"{prefix}_SAMPLE_NONTERMINAL_STEP", lane)
    expected_codes, expected_times = _expected_stage_rows(sample_time, method=method)
    accepted = np.asarray(stage_flags, dtype=bool)
    accepted_count = len(expected_codes)
    ok &= report.require(len(stage_code) >= accepted_count, f"{prefix}_STAGE_COUNT_TOO_SMALL", {"lane": lane, "expected_min": accepted_count, "actual": len(stage_code)})
    if len(stage_code) >= accepted_count:
        ok &= report.require(bool(np.array_equal(stage_code[:accepted_count], expected_codes)), f"{prefix}_STAGE_CODE_PATTERN", lane)
        ok &= report.require(bool(np.allclose(stage_time[:accepted_count], expected_times, rtol=0.0, atol=1.0e-14)), f"{prefix}_STAGE_TIME_PATTERN", lane)
        ok &= report.require(bool(np.all(accepted[:accepted_count])), f"{prefix}_ACCEPTED_STAGE_FLAG_FALSE", lane)
    if domain_exit:
        suffix_codes = stage_code[accepted_count:]
        suffix_flags = accepted[accepted_count:]
        # The frozen solver's failed DomainExit probe need not contain a full
        # state/mass/power row.  NPZ therefore preserves only successful raw
        # pre-failure stages: a possibly empty prefix before the next stored row.
        cycle = np.asarray((1, 2, 3, 4) if method == "rk4" else (1, 5), dtype=np.int64)
        ok &= report.require(0 <= len(suffix_codes) <= len(cycle), f"{prefix}_DOMAIN_EXIT_PREFailure_STAGE_COUNT", lane)
        if len(suffix_codes):
            ok &= report.require(bool(np.array_equal(suffix_codes, cycle[:len(suffix_codes)])), f"{prefix}_DOMAIN_EXIT_STAGE_SUFFIX_PATTERN", lane)
            ok &= report.require(bool(np.all(suffix_flags)), f"{prefix}_DOMAIN_EXIT_PREFailure_STAGE_FLAG", lane)
            ok &= report.require(float(stage_time[-1]) >= float(sample_time[-1]) - 1.0e-14 and float(stage_time[-1]) <= float(sample_time[-1]) + frozen_step + 1.0e-14, f"{prefix}_DOMAIN_EXIT_STAGE_TIME_RANGE", lane)
            start = float(sample_time[-1])
            expected_suffix_times = (
                (start, start + 0.5 * frozen_step, start + 0.5 * frozen_step, start + frozen_step)
                if method == "rk4" else (start, start + 0.5 * frozen_step)
            )
            ok &= report.require(
                bool(np.allclose(stage_time[accepted_count:], np.asarray(expected_suffix_times[:len(suffix_codes)]), rtol=0.0, atol=1.0e-14)),
                f"{prefix}_DOMAIN_EXIT_PREFailure_STAGE_TIME_PATTERN", lane,
            )
    else:
        ok &= report.require(len(stage_code) == accepted_count, f"{prefix}_STAGE_COUNT", {"lane": lane, "expected": accepted_count, "actual": len(stage_code)})
        ok &= report.require(bool(np.all(accepted)), f"{prefix}_STAGE_FLAG_FALSE", lane)
    accepted_stored = np.flatnonzero((stage_code == 0) & accepted)
    ok &= report.require(len(accepted_stored) == len(sample_time), f"{prefix}_STORED_STAGE_COUNT", lane)
    if len(accepted_stored) == len(sample_time):
        ok &= report.require(bool(np.array_equal(stage_time[accepted_stored], sample_time)), f"{prefix}_STORED_TIME_ALIGNMENT", lane)
        ok &= report.require(bool(np.array_equal(stage_service[accepted_stored], sample_service)), f"{prefix}_STORED_SERVICE_ALIGNMENT", lane)
        if sample_target is not None and stage_target is not None:
            ok &= report.require(bool(np.array_equal(stage_target[accepted_stored], sample_target)), f"{prefix}_STORED_TARGET_ALIGNMENT", lane)
    if len(stage_time):
        ok &= report.require(bool(np.all(np.diff(stage_time) >= -1.0e-14)), f"{prefix}_STAGE_TIME_ORDER", lane)
    return bool(ok)


def _validate_domain_exit_record(
    report: ValidationReport,
    *,
    geometry: Mapping[str, Any],
    case_id: str,
    accepted_end_time_s: float | None,
    frozen_step_s: float,
) -> bool:
    """Validate the original, variably shaped frozen-solver DomainExit probe."""

    failure = geometry.get("failure")
    ok = report.require(
        geometry.get("failure_probe_source") == "FROZEN_SOLVER_DOMAINEXIT_RECORD",
        "CASE_DOMAIN_EXIT_PROBE_SOURCE", case_id,
    )
    ok &= report.require(isinstance(failure, dict), "CASE_DOMAIN_EXIT_RAW_FAILURE_MISSING", case_id)
    if not isinstance(failure, dict):
        return False
    reason = failure.get("reason")
    allowed = {
        "P_COORDINATE_OUTSIDE_CLOSED_DOMAIN",
        "CENTERED_GAP_DERIVATIVE_OUTSIDE_DOMAIN",
        "OPENING_SIGN_CHANGED_OR_NONPOSITIVE",
        "CONSUMED_OPENING_SIGN_MISMATCH",
    }
    ok &= report.require(reason in allowed, "CASE_DOMAIN_EXIT_REASON", {"case_id": case_id, "reason": reason})
    time_value = failure.get("time_s")
    ok &= report.require(finite_number(time_value), "CASE_DOMAIN_EXIT_TIME", case_id)
    if finite_number(time_value) and accepted_end_time_s is not None:
        ok &= report.require(
            float(time_value) >= accepted_end_time_s - 1.0e-14
            and float(time_value) <= accepted_end_time_s + frozen_step_s + 1.0e-14,
            "CASE_DOMAIN_EXIT_TIME_RANGE", case_id,
        )
    ok &= report.require(isinstance(failure.get("stage_label"), str) and bool(failure.get("stage_label")), "CASE_DOMAIN_EXIT_STAGE_LABEL", case_id)
    try:
        p = np.asarray(failure.get("P_coordinates_m_left_right"), dtype=float)
    except (TypeError, ValueError):
        p = np.empty(0)
    ok &= report.require(p.shape == (2,) and bool(np.all(np.isfinite(p))), "CASE_DOMAIN_EXIT_P_COORDINATES", case_id)

    # A raw centred-difference DomainExit and a consumed-sign DomainExit have
    # deliberately different frozen record shapes.  The former carries the
    # centred perturbation; the latter is raised by ``_stage_audit`` after a
    # successful opening audit and therefore carries the full audit, Q and
    # consumed-sign record, but no ``centered_step_m``.  Do not invent a
    # fixed-shape failure row or require a field the frozen solver never wrote.
    step = math.nan
    if reason != "CONSUMED_OPENING_SIGN_MISMATCH":
        try:
            step = float(failure.get("centered_step_m"))
        except (TypeError, ValueError):
            step = math.nan
        ok &= report.require(
            math.isfinite(step) and abs(step - 1.0e-7) <= 1.0e-18,
            "CASE_DOMAIN_EXIT_CENTERED_STEP", case_id,
        )

    def validate_opening_audit(*, require_registered_signs: bool) -> tuple[bool, list[int]]:
        audit_ok = True
        try:
            jacobian = np.asarray(failure.get("raw_gap_jacobian_dimensionless"), dtype=float)
            diagonal = np.asarray(failure.get("diagonal_gap_derivatives_dimensionless"), dtype=float)
            signs = list(failure.get("opening_sign_left_right"))
            nominal_gap = np.asarray(failure.get("nominal_gap_m_left_right"), dtype=float)
            nominal_rate = np.asarray(failure.get("nominal_gap_rate_m_s_left_right"), dtype=float)
            contact_force = float(failure.get("contact_force_max_N"))
            contact_torque = float(failure.get("contact_torque_max_N_m"))
        except (TypeError, ValueError):
            jacobian = np.empty(0); diagonal = np.empty(0); signs = []
            nominal_gap = np.empty(0); nominal_rate = np.empty(0)
            contact_force = contact_torque = math.nan
        audit_ok &= report.require(
            jacobian.shape == (2, 2) and bool(np.all(np.isfinite(jacobian))),
            "CASE_DOMAIN_EXIT_RAW_GAP_JACOBIAN", case_id,
        )
        audit_ok &= report.require(
            diagonal.shape == (2,) and bool(np.all(np.isfinite(diagonal)))
            and jacobian.shape == (2, 2) and bool(np.array_equal(diagonal, np.diag(jacobian))),
            "CASE_DOMAIN_EXIT_DIAGONAL_JACOBIAN_BINDING", case_id,
        )
        expected_signs = (
            [int(np.sign(value)) for value in diagonal]
            if diagonal.shape == (2,) and np.all(np.isfinite(diagonal)) else []
        )
        audit_ok &= report.require(
            len(signs) == 2 and signs == expected_signs
            and all(isinstance(value, int) and not isinstance(value, bool) and value in {-1, 0, 1} for value in signs),
            "CASE_DOMAIN_EXIT_OPENING_SIGN_JACOBIAN_BINDING", case_id,
        )
        if require_registered_signs:
            audit_ok &= report.require(signs == [1, 1], "CASE_DOMAIN_EXIT_RAW_SIGNS_NOT_REGISTERED", case_id)
        audit_ok &= report.require(
            nominal_gap.shape == (2,) and nominal_rate.shape == (2,)
            and bool(np.all(np.isfinite(nominal_gap))) and bool(np.all(np.isfinite(nominal_rate))),
            "CASE_DOMAIN_EXIT_NOMINAL_GAP_AUDIT", case_id,
        )
        audit_ok &= report.require(
            math.isfinite(contact_force) and math.isfinite(contact_torque)
            and abs(contact_force) <= 1.0e-12 and abs(contact_torque) <= 1.0e-12,
            "CASE_DOMAIN_EXIT_CONTACT_MUTUAL_EXCLUSION", case_id,
        )
        return bool(audit_ok), signs

    if reason in {"P_COORDINATE_OUTSIDE_CLOSED_DOMAIN", "CENTERED_GAP_DERIVATIVE_OUTSIDE_DOMAIN"}:
        side = failure.get("failed_side")
        valid_side = isinstance(side, int) and not isinstance(side, bool) and side in {0, 1}
        ok &= report.require(valid_side, "CASE_DOMAIN_EXIT_FAILED_SIDE", case_id)
        if p.shape == (2,) and valid_side:
            coordinate = float(p[int(side)])
            if reason == "P_COORDINATE_OUTSIDE_CLOSED_DOMAIN":
                detected = coordinate < 0.0 or coordinate > 0.0715
            else:
                detected = 0.0 <= coordinate <= 0.0715 and (coordinate - step < 0.0 or coordinate + step > 0.0715)
            ok &= report.require(detected, "CASE_DOMAIN_EXIT_PREDICATE_NOT_REPRODUCED", case_id)
    elif reason == "OPENING_SIGN_CHANGED_OR_NONPOSITIVE":
        audit_ok, signs = validate_opening_audit(require_registered_signs=False)
        ok &= audit_ok
        try:
            diagonal = np.asarray(failure.get("diagonal_gap_derivatives_dimensionless"), dtype=float)
        except (TypeError, ValueError):
            diagonal = np.empty(0)
        detected = bool(
            diagonal.shape == (2,) and np.all(np.isfinite(diagonal))
            and (diagonal[0] <= 0.0 or diagonal[1] <= 0.0 or signs != [1, 1])
        )
        ok &= report.require(detected, "CASE_DOMAIN_EXIT_OPENING_SIGN_NOT_REPRODUCED", case_id)
    elif reason == "CONSUMED_OPENING_SIGN_MISMATCH":
        audit_ok, raw_signs = validate_opening_audit(require_registered_signs=True)
        ok &= audit_ok
        consumed = failure.get("consumed_opening_sign_left_right")
        ok &= report.require(
            isinstance(consumed, list) and len(consumed) == 2
            and all(isinstance(value, int) and not isinstance(value, bool) and value in {-1, 1} for value in consumed)
            and (consumed != [1, 1] or consumed != raw_signs)
            and failure.get("consumed_sigma_equals_raw_and_registered") is False,
            "CASE_DOMAIN_EXIT_CONSUMED_SIGN_NOT_REPRODUCED", case_id,
        )
        q = failure.get("generalized_force_14")
        try:
            q_array = np.asarray(q, dtype=float)
        except (TypeError, ValueError):
            q_array = np.empty(0)
        ok &= report.require(
            q_array.shape == (14,) and bool(np.all(np.isfinite(q_array)))
            and bool(np.all(q_array[:12] == 0.0)),
            "CASE_DOMAIN_EXIT_COMMAND_PROBE", case_id,
        )
        ok &= report.require(
            failure.get("Q_base_and_R_exact_zero") is True
            and failure.get("contact_kernel_enabled") is False
            and failure.get("accepted") is False,
            "CASE_DOMAIN_EXIT_CONSUMED_SIGN_FLAGS", case_id,
        )
    return bool(ok)


def _geometry_snapshot_from_metadata(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the immutable acquisition snapshot or fail closed.

    The surrounding acquisition validator byte-compares the complete payload
    against the hash-bound B4E parent.  Geometry replay consumes that payload
    directly and never imports a solver/runtime module.
    """

    provenance = metadata.get("event_provenance")
    if not isinstance(provenance, Mapping):
        raise GeometryReplayError("EVENT_PROVENANCE_NOT_OBJECT")
    payload = provenance.get("acquisition_certificate_payload")
    if not isinstance(payload, Mapping):
        raise GeometryReplayError("ACQUISITION_CERTIFICATE_PAYLOAD_NOT_OBJECT")
    acquisition = payload.get("acquisition")
    if not isinstance(acquisition, Mapping):
        raise GeometryReplayError("ACQUISITION_PAYLOAD_NOT_OBJECT")
    snapshot = acquisition.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise GeometryReplayError("ACQUISITION_SNAPSHOT_NOT_OBJECT")
    return snapshot


def _replay_active_geometry_arrays(
    arrays: Mapping[str, np.ndarray],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Independently reconstruct all accepted active geometry observations."""

    target_error = 0.0
    gap_error = 0.0
    rate_error = 0.0
    for index, service in enumerate(arrays["service_state_29"]):
        try:
            target = reconstruct_active_target_state_13(service, snapshot)
            observation = recompute_gap_rate(service, target)
        except GeometryReplayError as error:
            raise GeometryReplayError(
                f"ACTIVE_SAMPLE_GEOMETRY_REPLAY:{index}:{error}"
            ) from error
        target_error = max(
            target_error,
            float(np.max(np.abs(target - arrays["target_state_13"][index]))),
        )
        stored_gaps = np.asarray(
            (arrays["left_gap_m"][index], arrays["right_gap_m"][index]),
            dtype=float,
        )
        stored_rates = np.asarray(
            (
                arrays["left_gap_rate_m_s"][index],
                arrays["right_gap_rate_m_s"][index],
            ),
            dtype=float,
        )
        gap_error = max(
            gap_error,
            float(np.max(np.abs(observation.gaps_m - stored_gaps))),
        )
        rate_error = max(
            rate_error,
            float(np.max(np.abs(observation.gap_rates_m_s - stored_rates))),
        )

    stage_p_error = 0.0
    stage_jacobian_error = 0.0
    all_stage_signs_registered = True
    for index, service in enumerate(arrays["stage_service_state_29"]):
        try:
            replay = centered_gap_jacobian(service, snapshot=snapshot)
        except GeometryReplayError as error:
            raise GeometryReplayError(
                f"ACTIVE_STAGE_GEOMETRY_REPLAY:{index}:{error}"
            ) from error
        stage_p_error = max(
            stage_p_error,
            float(np.max(np.abs(
                replay.p_coordinates_m - arrays["stage_P_coordinates_m"][index]
            ))),
        )
        stage_jacobian_error = max(
            stage_jacobian_error,
            float(np.max(np.abs(
                replay.raw_gap_jacobian_p
                - arrays["stage_gap_jacobian_P"][index]
            ))),
        )
        all_stage_signs_registered &= replay.opening_signs == (1, 1)
    return {
        "active_target_state_max_abs_error": target_error,
        "active_gap_max_abs_error_m": gap_error,
        "active_gap_rate_max_abs_error_m_s": rate_error,
        "active_stage_P_max_abs_error_m": stage_p_error,
        "active_stage_gap_jacobian_max_abs_error": stage_jacobian_error,
        "active_stage_opening_signs_all_registered": bool(
            all_stage_signs_registered
        ),
    }


def _replay_post_geometry_arrays(
    arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    """Independently reconstruct post-release gaps/rates and raw Jacobians."""

    gap_error = 0.0
    rate_error = 0.0
    for index, (service, target) in enumerate(zip(
        arrays["post_service_state_29"], arrays["post_target_state_13"],
    )):
        try:
            observation = recompute_gap_rate(service, target)
        except GeometryReplayError as error:
            raise GeometryReplayError(
                f"POST_SAMPLE_GEOMETRY_REPLAY:{index}:{error}"
            ) from error
        stored_gaps = np.asarray(
            (
                arrays["post_left_gap_m"][index],
                arrays["post_right_gap_m"][index],
            ),
            dtype=float,
        )
        stored_rates = np.asarray(
            (
                arrays["post_left_gap_rate_m_s"][index],
                arrays["post_right_gap_rate_m_s"][index],
            ),
            dtype=float,
        )
        gap_error = max(
            gap_error,
            float(np.max(np.abs(observation.gaps_m - stored_gaps))),
        )
        rate_error = max(
            rate_error,
            float(np.max(np.abs(observation.gap_rates_m_s - stored_rates))),
        )

    stage_p_error = 0.0
    stage_jacobian_error = 0.0
    all_stage_signs_registered = True
    for index, (service, target) in enumerate(zip(
        arrays["post_stage_service_state_29"],
        arrays["post_stage_target_state_13"],
    )):
        try:
            replay = centered_gap_jacobian(
                service,
                independent_target_state_13=target,
            )
        except GeometryReplayError as error:
            raise GeometryReplayError(
                f"POST_STAGE_GEOMETRY_REPLAY:{index}:{error}"
            ) from error
        stage_p_error = max(
            stage_p_error,
            float(np.max(np.abs(
                replay.p_coordinates_m
                - arrays["post_stage_P_coordinates_m"][index]
            ))),
        )
        stage_jacobian_error = max(
            stage_jacobian_error,
            float(np.max(np.abs(
                replay.raw_gap_jacobian_p
                - arrays["post_stage_gap_jacobian_P"][index]
            ))),
        )
        all_stage_signs_registered &= replay.opening_signs == (1, 1)
    return {
        "post_gap_max_abs_error_m": gap_error,
        "post_gap_rate_max_abs_error_m_s": rate_error,
        "post_stage_P_max_abs_error_m": stage_p_error,
        "post_stage_gap_jacobian_max_abs_error": stage_jacobian_error,
        "post_stage_opening_signs_all_registered": bool(
            all_stage_signs_registered
        ),
    }


def _validate_active_geometry_replay(
    report: ValidationReport,
    *,
    metadata: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    case_id: str,
) -> tuple[bool, dict[str, Any]]:
    result = report.guard(
        "CASE_INDEPENDENT_ACTIVE_GEOMETRY_REPLAY_EXCEPTION",
        lambda: _replay_active_geometry_arrays(
            arrays, _geometry_snapshot_from_metadata(metadata),
        ),
    )
    if not isinstance(result, dict):
        return False, {}
    checks = (
        result["active_target_state_max_abs_error"] <= 1.0e-12,
        result["active_gap_max_abs_error_m"] <= 1.0e-12,
        result["active_gap_rate_max_abs_error_m_s"] <= 1.0e-12,
        result["active_stage_P_max_abs_error_m"] <= 1.0e-15,
        result["active_stage_gap_jacobian_max_abs_error"] <= 1.0e-12,
        result["active_stage_opening_signs_all_registered"] is True,
    )
    passed = all(checks)
    report.require(
        passed,
        "CASE_INDEPENDENT_ACTIVE_GEOMETRY_REPLAY",
        {"case_id": case_id, **result},
    )
    return passed, result


def _validate_post_geometry_replay(
    report: ValidationReport,
    *,
    arrays: Mapping[str, np.ndarray],
    case_id: str,
) -> tuple[bool, dict[str, Any]]:
    result = report.guard(
        "CASE_INDEPENDENT_POST_GEOMETRY_REPLAY_EXCEPTION",
        lambda: _replay_post_geometry_arrays(arrays),
    )
    if not isinstance(result, dict):
        return False, {}
    checks = (
        result["post_gap_max_abs_error_m"] <= 1.0e-12,
        result["post_gap_rate_max_abs_error_m_s"] <= 1.0e-12,
        result["post_stage_P_max_abs_error_m"] <= 1.0e-15,
        result["post_stage_gap_jacobian_max_abs_error"] <= 1.0e-12,
        result["post_stage_opening_signs_all_registered"] is True,
    )
    passed = all(checks)
    report.require(
        passed,
        "CASE_INDEPENDENT_POST_GEOMETRY_REPLAY",
        {"case_id": case_id, **result},
    )
    return passed, result


def _validate_npz_arrays(
    report: ValidationReport,
    *,
    metadata: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    case_id: str,
    slot: Mapping[str, Any],
) -> dict[str, Any]:
    responses = metadata.get("responses", {})
    finite_event = responses.get("finite_removal_event") is True
    expected_inventory = ACTIVE_ARRAYS | (POST_ARRAYS if finite_event else set())
    report.require(set(arrays) == expected_inventory, "CASE_NPZ_ARRAY_INVENTORY", {"case_id": case_id, "missing": sorted(expected_inventory - set(arrays)), "extra": sorted(set(arrays) - expected_inventory)})
    if not ACTIVE_ARRAYS.issubset(arrays):
        return {}
    float_names = expected_inventory - {"stage_code", "stage_domain_and_sign_pass", "post_stage_code", "post_stage_domain_and_sign_pass"}
    for name in float_names:
        if name in arrays:
            report.require(arrays[name].dtype.str == "<f8", "CASE_NPZ_LITTLE_ENDIAN_FLOAT64_DTYPE", {"case_id": case_id, "array": name, "dtype": arrays[name].dtype.str})
    for name in {"stage_code", "post_stage_code"} & set(arrays):
        report.require(arrays[name].dtype.str == "<i8", "CASE_NPZ_LITTLE_ENDIAN_INT64_DTYPE", {"case_id": case_id, "array": name, "dtype": arrays[name].dtype.str})
    for name in {"stage_domain_and_sign_pass", "post_stage_domain_and_sign_pass"} & set(arrays):
        report.require(arrays[name].dtype.str == "|b1", "CASE_NPZ_BOOL_DTYPE", {"case_id": case_id, "array": name, "dtype": arrays[name].dtype.str})
    time = arrays["time_s"]
    _require_shape(report, time, (None,), "CASE_TIME_SHAPE")
    n = len(time)
    geometry = metadata.get("geometry_domain", {})
    geometry_pass = geometry.get("passed") is True
    report.require(n >= 1 or not geometry_pass, "CASE_EMPTY_ACTIVE_TRACE", case_id)
    if n:
        report.require(bool(np.all(np.diff(time) > 0.0)), "CASE_ACTIVE_TIME_NOT_STRICTLY_INCREASING", case_id)
    lane = str(metadata.get("lane_id"))
    if not report.require(lane in LANE_DEFINITIONS, "CASE_LANE_UNKNOWN", lane):
        return {}
    expected_method, expected_step = LANE_DEFINITIONS[lane]
    report.require(slot.get("method") == expected_method and slot.get("step_s") == expected_step, "CASE_LANE_METHOD_STEP_CONTRACT", case_id)
    for name, width in (
        ("service_state_29", 29), ("target_state_13", 13), ("command_Q_14", 14),
        ("total_linear_momentum_N_s", 3), ("total_angular_momentum_N_m_s", 3),
    ):
        _require_shape(report, arrays[name], (n, width), f"CASE_{name.upper()}_SHAPE")
    for name in (
        "signed_W_act_J", "left_gap_m", "right_gap_m", "left_gap_rate_m_s",
        "right_gap_rate_m_s", "total_kinetic_energy_J", "energy_minus_work_residual_J",
        "ideal_constraint_power_W", "contact_force_N", "contact_torque_N_m",
    ):
        _require_shape(report, arrays[name], (n,), f"CASE_{name.upper()}_SHAPE")
    stage_time = arrays["stage_time_s"]
    s = len(stage_time)
    report.require(s >= 1 or not geometry_pass, "CASE_NO_ACTIVE_STAGE_AUDIT", case_id)
    for name, shape in (
        ("stage_code", (s,)), ("stage_service_state_29", (s, 29)),
        ("stage_command_Q_14", (s, 14)), ("stage_power_W", (s,)),
        ("stage_P_coordinates_m", (s, 2)), ("stage_gap_jacobian_P", (s, 2, 2)),
        ("stage_mass_cholesky_min_diagonal", (s,)), ("stage_domain_and_sign_pass", (s,)),
    ):
        _require_shape(report, arrays[name], shape, f"CASE_{name.upper()}_SHAPE")
    report.require(bool(np.all(np.isin(arrays["stage_code"], [0, 1, 2, 3, 4, 5]))), "CASE_STAGE_CODE_DOMAIN", case_id)
    stage_flags = arrays["stage_domain_and_sign_pass"]
    if n == 0:
        report.require(s == 0, "CASE_INITIAL_DOMAIN_EXIT_HAS_PREFailure_STAGE_ROWS", case_id)
        report.require(metadata.get("terminal_status") == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN", "CASE_DOMAIN_EXIT_TERMINAL_STATUS", case_id)
        _validate_domain_exit_record(
            report, geometry=geometry, case_id=case_id,
            accepted_end_time_s=None, frozen_step_s=expected_step,
        )
        empty_clearance = {
            "finite_event": False, "tau_c_s": None, "removal_time_s": None,
            "certified_good_intervals_s": [],
            "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
            "endpoint_only": False,
        }
        reported_clearance = responses.get("clearance_certificate_payload")
        report.require(reported_clearance == empty_clearance, "CASE_INITIAL_DOMAIN_EXIT_CLEARANCE_PAYLOAD", case_id)
        report.require(
            metadata.get("event_provenance", {}).get("clearance_certificate_sha256")
            == canonical_sha256({"lane_id": lane, "case_id": case_id, "clearance": reported_clearance}),
            "CASE_CLEARANCE_CERTIFICATE_HASH", case_id,
        )
        report.require(metadata.get("event_provenance", {}).get("removal_time_s") is None, "CASE_DOMAIN_EXIT_REMOVAL_TIME_NOT_NULL", case_id)
        return {
            "work_delta_J": 0.0, "fine_work_J": 0.0, "coarse_work_J": 0.0,
            "fine_work_error_J": 0.0, "coarse_work_error_J": 0.0,
            "linear_momentum_drift": 0.0, "angular_momentum_drift": 0.0,
            "energy_minus_work_residual": 0.0, "post": {},
            "registered_command_pass": True,
            "clearance": empty_clearance,
            "g03_pass": True, "g04_pass": True, "g05_pass": True,
            "g06_pass": True, "g07_pass": True, "g08_pass": True,
            "g09_predicate": False, "g10_pass": True, "g11_pass": True,
            "g16_predicate": False, "independent_integrity_pass": False,
        }
    if geometry_pass:
        report.require(bool(np.all(stage_flags)), "CASE_STAGE_DOMAIN_OR_SIGN_FALSE", case_id)
    else:
        report.require(bool(np.all(stage_flags)), "CASE_DOMAIN_EXIT_PREFailure_STAGE_FALSE", case_id)
        report.require(metadata.get("terminal_status") == "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN", "CASE_DOMAIN_EXIT_TERMINAL_STATUS", case_id)
        _validate_domain_exit_record(
            report, geometry=geometry, case_id=case_id,
            accepted_end_time_s=float(time[-1]) if n else None,
            frozen_step_s=expected_step,
        )
    _validate_stage_contract(
        report, prefix="CASE_ACTIVE", lane=lane, sample_time=time,
        sample_service=arrays["service_state_29"], stage_time=stage_time,
        stage_code=arrays["stage_code"], stage_service=arrays["stage_service_state_29"],
        stage_flags=stage_flags, domain_exit=not geometry_pass,
    )
    accepted_stage = stage_flags.astype(bool)
    report.require(bool(np.all(arrays["stage_mass_cholesky_min_diagonal"][accepted_stage] > 0.0)), "CASE_STAGE_MASS_NOT_SPD", case_id)
    p = arrays["service_state_29"][:, 13:15]
    stage_p = arrays["stage_P_coordinates_m"]
    report.require(
        bool(np.array_equal(stage_p, arrays["stage_service_state_29"][:, 13:15])),
        "CASE_STAGE_P_NOT_BOUND_TO_STAGE_STATE", case_id,
    )
    report.require(bool(np.all((p >= 0.0) & (p <= 0.0715))), "CASE_SAMPLE_P_DOMAIN", case_id)
    report.require(bool(np.all((stage_p[accepted_stage] - 1.0e-7 >= 0.0) & (stage_p[accepted_stage] + 1.0e-7 <= 0.0715))), "CASE_STAGE_CENTERED_P_DOMAIN", case_id)
    jac = arrays["stage_gap_jacobian_P"]
    report.require(bool(np.all(jac[accepted_stage, 0, 0] > 0.0) and np.all(jac[accepted_stage, 1, 1] > 0.0)), "CASE_STAGE_OPENING_SIGN_NOT_POSITIVE", case_id)
    report.require(bool(np.all(arrays["command_Q_14"][:, :12] == 0.0)), "CASE_NON_P_SAMPLE_COMMAND", case_id)
    report.require(bool(np.all(arrays["stage_command_Q_14"][:, :12] == 0.0)), "CASE_NON_P_STAGE_COMMAND", case_id)
    computed_stage_power = np.sum(arrays["stage_command_Q_14"][:, 12:14] * arrays["stage_service_state_29"][:, 27:29], axis=1)
    report.require(bool(np.allclose(computed_stage_power, arrays["stage_power_W"], rtol=0.0, atol=1.0e-14)), "CASE_STAGE_POWER_MISMATCH", case_id)
    sample_service_quaternion_norm = np.linalg.norm(arrays["service_state_29"][:, 3:7], axis=1)
    sample_target_quaternion_norm = np.linalg.norm(arrays["target_state_13"][:, 3:7], axis=1)
    stage_service_quaternion_norm = np.linalg.norm(arrays["stage_service_state_29"][:, 3:7], axis=1)
    report.require(
        bool(np.all(np.abs(sample_service_quaternion_norm - 1.0) <= 1.0e-12))
        and bool(np.all(np.abs(sample_target_quaternion_norm - 1.0) <= 1.0e-12))
        and bool(np.all(np.abs(stage_service_quaternion_norm - 1.0) <= 1.0e-12)),
        "CASE_ACTIVE_QUATERNION_NORM", case_id,
    )
    active_geometry_replay_pass, active_geometry_replay = (
        _validate_active_geometry_replay(
            report,
            metadata=metadata,
            arrays=arrays,
            case_id=case_id,
        )
    )
    event = metadata["event_provenance"]
    acquisition = float(event["acquisition_time_s"])
    report.require(abs(float(time[0]) - acquisition) <= 1.0e-15, "CASE_ACTIVE_START_NOT_ACQUISITION", case_id)
    command = metadata["command_parameters"]
    qref = float(command["Q_ref_per_finger_N"])
    expected_left = _profile(time, acquisition=acquisition, alpha=float(command["left"]["alpha"]), delay=float(command["left"]["delay_s"]), duration=float(command["left"]["duration_s"]), qref=qref)
    expected_right = _profile(time, acquisition=acquisition, alpha=float(command["right"]["alpha"]), delay=float(command["right"]["delay_s"]), duration=float(command["right"]["duration_s"]), qref=qref)
    report.require(bool(np.allclose(arrays["command_Q_14"][:, 12], expected_left, rtol=0.0, atol=2.0e-15)), "CASE_LEFT_COMMAND_PROFILE", case_id)
    report.require(bool(np.allclose(arrays["command_Q_14"][:, 13], expected_right, rtol=0.0, atol=2.0e-15)), "CASE_RIGHT_COMMAND_PROFILE", case_id)
    for expected, side in ((expected_left, 12), (expected_right, 13)):
        report.require(bool(np.all(arrays["command_Q_14"][expected == 0.0, side] == 0.0)), "CASE_COMMAND_ENDPOINT_OR_OUTSIDE_NOT_EXACT_ZERO", {"case_id": case_id, "side": side})
    stage_left = _profile(stage_time, acquisition=acquisition, alpha=float(command["left"]["alpha"]), delay=float(command["left"]["delay_s"]), duration=float(command["left"]["duration_s"]), qref=qref)
    stage_right = _profile(stage_time, acquisition=acquisition, alpha=float(command["right"]["alpha"]), delay=float(command["right"]["delay_s"]), duration=float(command["right"]["duration_s"]), qref=qref)
    report.require(bool(np.allclose(arrays["stage_command_Q_14"][:, 12], stage_left, rtol=0.0, atol=2.0e-15)), "CASE_LEFT_STAGE_COMMAND_PROFILE", case_id)
    report.require(bool(np.allclose(arrays["stage_command_Q_14"][:, 13], stage_right, rtol=0.0, atol=2.0e-15)), "CASE_RIGHT_STAGE_COMMAND_PROFILE", case_id)
    stored_stage = np.flatnonzero((arrays["stage_code"] == 0) & accepted_stage)
    if len(stored_stage) == n:
        report.require(bool(np.array_equal(arrays["stage_command_Q_14"][stored_stage], arrays["command_Q_14"])), "CASE_STORED_COMMAND_ALIGNMENT", case_id)
    report.require(bool(np.max(np.abs(arrays["contact_force_N"])) <= 1.0e-12), "CASE_ACTIVE_CONTACT_FORCE", case_id)
    report.require(bool(np.max(np.abs(arrays["contact_torque_N_m"])) <= 1.0e-12), "CASE_ACTIVE_CONTACT_TORQUE", case_id)
    report.require(bool(np.max(np.abs(arrays["ideal_constraint_power_W"])) <= 1.0e-10), "CASE_IDEAL_CONSTRAINT_POWER", case_id)
    linear_drift = _max_vector_drift(arrays["total_linear_momentum_N_s"])
    angular_drift = _max_vector_drift(arrays["total_angular_momentum_N_m_s"])
    report.require(linear_drift <= 1.0e-9, "CASE_LINEAR_MOMENTUM_DRIFT", {"case_id": case_id, "value": linear_drift})
    report.require(angular_drift <= 1.0e-9, "CASE_ANGULAR_MOMENTUM_DRIFT", {"case_id": case_id, "value": angular_drift})
    work = arrays["signed_W_act_J"]
    work_initial_zero = bool(work[0] == 0.0)
    report.require(work_initial_zero, "CASE_WORK_LEDGER_INITIAL_NOT_EXACT_ZERO", case_id)
    independent_energy_residual = np.abs(
        (arrays["total_kinetic_energy_J"] - work)
        - (arrays["total_kinetic_energy_J"][0] - work[0])
    )
    report.require(
        bool(np.allclose(
            arrays["energy_minus_work_residual_J"],
            independent_energy_residual,
            rtol=0.0, atol=1.0e-12,
        )),
        "CASE_ENERGY_MINUS_WORK_RESIDUAL_NOT_RAW_RECOMPUTATION", case_id,
    )
    energy_residual = float(np.max(independent_energy_residual))
    report.require(energy_residual <= 1.0e-7, "CASE_ENERGY_MINUS_WORK_RESIDUAL", {"case_id": case_id, "value": energy_residual})
    work_delta = float(arrays["signed_W_act_J"][-1] - arrays["signed_W_act_J"][0])
    work_pass = n == 1 and work_initial_zero and abs(work_delta) <= 1.0e-15
    cumulative_work_error = 0.0
    if n >= 2:
        power = np.sum(arrays["command_Q_14"][:, 12:14] * arrays["service_state_29"][:, 27:29], axis=1)
        fine = _trapz(power, time)
        cumulative_work = np.concatenate((
            np.asarray([0.0]),
            np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time)),
        ))
        cumulative_work_error = float(np.max(np.abs(cumulative_work - work)))
        indices = list(range(0, n, 2))
        if indices[-1] != n - 1:
            indices.append(n - 1)
        coarse = _trapz(power[np.asarray(indices)], time[np.asarray(indices)])
        fine_error = abs(fine - work_delta)
        coarse_error = abs(coarse - work_delta)
        work_pass = bool(
            work_initial_zero and fine_error <= 1.0e-7
            and cumulative_work_error <= 1.0e-7
            and (fine_error <= coarse_error + 1.0e-15 or coarse_error <= 1.0e-7)
        )
        report.require(work_pass, "CASE_INDEPENDENT_WORK_QUADRATURE", {"case_id": case_id, "fine_error_J": fine_error, "coarse_error_J": coarse_error, "cumulative_work_error_J": cumulative_work_error})
    else:
        fine = coarse = work_delta
        fine_error = coarse_error = 0.0
    command_profile_pass = bool(
        np.all(arrays["command_Q_14"][:, :12] == 0.0)
        and np.allclose(arrays["command_Q_14"][:, 12], expected_left, rtol=0.0, atol=2.0e-15)
        and np.allclose(arrays["command_Q_14"][:, 13], expected_right, rtol=0.0, atol=2.0e-15)
    )
    sample_p_pass = np.all((p >= 0.0) & (p <= 0.0715), axis=1)
    sample_linear_pass = np.linalg.norm(arrays["total_linear_momentum_N_s"] - arrays["total_linear_momentum_N_s"][0], axis=1) <= 1.0e-9
    sample_angular_pass = np.linalg.norm(arrays["total_angular_momentum_N_m_s"] - arrays["total_angular_momentum_N_m_s"][0], axis=1) <= 1.0e-9
    sample_good = (
        sample_p_pass & sample_linear_pass & sample_angular_pass
        & (independent_energy_residual <= 1.0e-7)
        & (np.abs(arrays["ideal_constraint_power_W"]) <= 1.0e-10)
        & (np.abs(arrays["contact_force_N"]) <= 1.0e-12)
        & (np.abs(arrays["contact_torque_N_m"]) <= 1.0e-12)
    )
    command_end = max(
        acquisition + float(command["left"]["delay_s"]) + float(command["left"]["duration_s"]),
        acquisition + float(command["right"]["delay_s"]) + float(command["right"]["duration_s"]),
    )
    clearance: dict[str, Any]
    if n >= 2:
        command_zero = np.all(arrays["command_Q_14"] == 0.0, axis=1)
        ledger_intervals = sample_good[:-1] & sample_good[1:] & command_zero[:-1] & command_zero[1:] & (time[:-1] >= command_end - 1.0e-12)
        clearance = certify_clearance_independent(
            time, arrays["left_gap_m"], arrays["right_gap_m"],
            arrays["left_gap_rate_m_s"], arrays["right_gap_rate_m_s"],
            acquisition_time_s=max(acquisition, command_end - 0.001),
            ledger_interval_certified=ledger_intervals,
        )
    else:
        clearance = {
            "finite_event": False, "tau_c_s": None, "removal_time_s": None,
            "certified_good_intervals_s": [],
            "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
            "endpoint_only": False,
        }
    independently_finite = clearance.get("finite_event") is True
    report.require(independently_finite is finite_event, "CASE_CLEARANCE_FINITE_EVENT_RAW_MISMATCH", {"case_id": case_id, "computed": independently_finite, "reported": finite_event})
    reported_clearance = responses.get("clearance_certificate_payload")
    report.require(isinstance(reported_clearance, dict), "CASE_CLEARANCE_CERTIFICATE_PAYLOAD_MISSING", case_id)
    if isinstance(reported_clearance, dict):
        certificate = canonical_sha256({"lane_id": lane, "case_id": case_id, "clearance": reported_clearance})
        report.require(event.get("clearance_certificate_sha256") == certificate, "CASE_CLEARANCE_CERTIFICATE_HASH", case_id)
        report.require(reported_clearance.get("algorithm") == clearance.get("algorithm"), "CASE_CLEARANCE_ALGORITHM", case_id)
        report.require(reported_clearance.get("endpoint_only") is False, "CASE_CLEARANCE_ENDPOINT_ONLY_FORBIDDEN", case_id)
        report.require(reported_clearance.get("finite_event") is independently_finite, "CASE_CLEARANCE_PAYLOAD_OUTCOME", case_id)
        reported_removal = reported_clearance.get("removal_time_s")
        computed_removal = clearance.get("removal_time_s")
        report.require(
            (reported_removal is None and computed_removal is None)
            or (_same_float(reported_removal, computed_removal, atol=1.0e-12)),
            "CASE_CLEARANCE_EARLIEST_REMOVAL", case_id,
        )
        reported_intervals = reported_clearance.get("certified_good_intervals_s")
        computed_intervals = clearance.get("certified_good_intervals_s")
        intervals_match = False
        try:
            reported_array = np.asarray(reported_intervals, dtype=float)
            computed_array = np.asarray(computed_intervals, dtype=float)
            intervals_match = bool(
                reported_array.shape == computed_array.shape
                and np.allclose(reported_array, computed_array, rtol=0.0, atol=1.0e-12)
            )
        except (TypeError, ValueError):
            intervals_match = False
        report.require(intervals_match, "CASE_CLEARANCE_ALL_ROOT_INTERVALS", case_id)
    removal_time = event.get("removal_time_s")
    if finite_event:
        report.require(finite_number(removal_time) and abs(float(time[-1]) - float(removal_time)) <= 1.0e-12, "CASE_ACTIVE_END_NOT_EXACT_REMOVAL", case_id)
        report.require(arrays["left_gap_m"][-1] >= 1.0e-6 and arrays["right_gap_m"][-1] >= 1.0e-6, "CASE_REMOVAL_BILATERAL_GAP", case_id)
        report.require(arrays["left_gap_rate_m_s"][-1] >= -1.0e-6 and arrays["right_gap_rate_m_s"][-1] >= -1.0e-6, "CASE_REMOVAL_BILATERAL_RATE", case_id)
        report.require(bool(np.all(arrays["command_Q_14"][-1] == 0.0)), "CASE_REMOVAL_COMMAND_NONZERO", case_id)
        report.require(float(removal_time) + 1.0e-12 >= command_end + 0.001, "CASE_DWELL_BEFORE_COMMAND_END", case_id)
    elif geometry_pass:
        report.require(abs(float(time[-1]) - (acquisition + 0.08)) <= 1.0e-12, "CASE_NO_EVENT_HORIZON_NOT_ACQ_PLUS_0P08", {"case_id": case_id, "end": float(time[-1]), "acquisition": acquisition})
    post_metrics: dict[str, Any] = {}
    post_pass = not finite_event
    post_contact_pass = not finite_event
    post_work_pass = not finite_event
    post_geometry_replay_pass = not finite_event
    post_geometry_replay: dict[str, Any] = {}
    if finite_event and POST_ARRAYS.issubset(arrays):
        post_time = arrays["post_time_s"]
        m = len(post_time)
        report.require(m >= 2 and bool(np.all(np.diff(post_time) > 0.0)), "CASE_POST_TIME", case_id)
        report.require(abs(float(post_time[0]) - float(removal_time)) <= 1.0e-12 and abs(float(post_time[-1]) - (float(removal_time) + 0.005)) <= 1.0e-12, "CASE_POST_5MS_HORIZON", case_id)
        for name, width in (("post_service_state_29", 29), ("post_target_state_13", 13), ("post_total_linear_momentum_N_s", 3), ("post_total_angular_momentum_N_m_s", 3)):
            _require_shape(report, arrays[name], (m, width), f"CASE_{name.upper()}_SHAPE")
        for name in (
            "post_left_gap_m", "post_right_gap_m", "post_left_gap_rate_m_s",
            "post_right_gap_rate_m_s", "post_total_kinetic_energy_J",
            "post_contact_force_N", "post_contact_torque_N_m",
        ):
            _require_shape(report, arrays[name], (m,), f"CASE_{name.upper()}_SHAPE")
        report.require(bool(np.array_equal(arrays["post_service_state_29"][0], arrays["service_state_29"][-1])), "CASE_POST_SERVICE_MAPPING_JUMP", case_id)
        report.require(bool(np.array_equal(arrays["post_target_state_13"][0], arrays["target_state_13"][-1])), "CASE_POST_TARGET_MAPPING_JUMP", case_id)
        report.require(float(np.max(np.abs(arrays["post_contact_force_N"]))) <= 1.0e-12, "CASE_POST_CONTACT_FORCE", case_id)
        report.require(float(np.max(np.abs(arrays["post_contact_torque_N_m"]))) <= 1.0e-12, "CASE_POST_CONTACT_TORQUE", case_id)
        post_linear = _max_vector_drift(arrays["post_total_linear_momentum_N_s"])
        post_angular = _max_vector_drift(arrays["post_total_angular_momentum_N_m_s"])
        post_energy = float(np.max(np.abs(arrays["post_total_kinetic_energy_J"] - arrays["post_total_kinetic_energy_J"][0])))
        report.require(post_linear <= 1.0e-9 and post_angular <= 1.0e-9, "CASE_POST_MOMENTUM_DRIFT", {"case_id": case_id, "linear": post_linear, "angular": post_angular})
        report.require(post_energy <= 1.0e-7, "CASE_POST_ENERGY_DRIFT", {"case_id": case_id, "value": post_energy})
        report.require(bool(np.all((arrays["post_service_state_29"][:, 13:15] >= 0.0) & (arrays["post_service_state_29"][:, 13:15] <= 0.0715))), "CASE_POST_SAMPLE_P_DOMAIN", case_id)
        post_clearance = certify_clearance_independent(
            post_time, arrays["post_left_gap_m"], arrays["post_right_gap_m"],
            arrays["post_left_gap_rate_m_s"], arrays["post_right_gap_rate_m_s"],
            acquisition_time_s=float(post_time[0]) - 0.001,
            ledger_interval_certified=np.ones(m - 1, dtype=bool),
        )
        intervals = post_clearance.get("certified_good_intervals_s", [])
        full_post_clearance = bool(
            len(intervals) == 1
            and abs(float(intervals[0][0]) - float(post_time[0])) <= 1.0e-12
            and abs(float(intervals[0][1]) - float(post_time[-1])) <= 1.0e-12
        )
        report.require(full_post_clearance, "CASE_POST_CLEARANCE_REENTRY", case_id)
        u = len(arrays["post_stage_time_s"])
        report.require(u >= 1, "CASE_NO_POST_STAGE_AUDIT", case_id)
        for name, shape in (
            ("post_stage_code", (u,)), ("post_stage_service_state_29", (u, 29)),
            ("post_stage_target_state_13", (u, 13)), ("post_stage_P_coordinates_m", (u, 2)),
            ("post_stage_gap_jacobian_P", (u, 2, 2)), ("post_stage_domain_and_sign_pass", (u,)),
        ):
            _require_shape(report, arrays[name], shape, f"CASE_{name.upper()}_SHAPE")
        report.require(bool(np.all(np.isin(arrays["post_stage_code"], [0, 1, 2, 3, 4, 5]))), "CASE_POST_STAGE_CODE_DOMAIN", case_id)
        report.require(bool(np.all(arrays["post_stage_domain_and_sign_pass"])), "CASE_POST_STAGE_DOMAIN_OR_SIGN_FALSE", case_id)
        _validate_stage_contract(
            report, prefix="CASE_POST", lane=lane, sample_time=post_time,
            sample_service=arrays["post_service_state_29"],
            stage_time=arrays["post_stage_time_s"], stage_code=arrays["post_stage_code"],
            stage_service=arrays["post_stage_service_state_29"],
            stage_flags=arrays["post_stage_domain_and_sign_pass"], domain_exit=False,
            sample_target=arrays["post_target_state_13"], stage_target=arrays["post_stage_target_state_13"],
        )
        post_p = arrays["post_stage_P_coordinates_m"]
        report.require(
            bool(np.array_equal(
                post_p, arrays["post_stage_service_state_29"][:, 13:15],
            )),
            "CASE_POST_STAGE_P_NOT_BOUND_TO_STAGE_STATE", case_id,
        )
        report.require(bool(np.all((post_p - 1.0e-7 >= 0.0) & (post_p + 1.0e-7 <= 0.0715))), "CASE_POST_STAGE_CENTERED_P_DOMAIN", case_id)
        post_jac = arrays["post_stage_gap_jacobian_P"]
        report.require(bool(np.all(post_jac[:, 0, 0] > 0.0) and np.all(post_jac[:, 1, 1] > 0.0)), "CASE_POST_OPENING_SIGN", case_id)
        post_quaternion_ok = bool(
            np.all(np.abs(np.linalg.norm(arrays["post_service_state_29"][:, 3:7], axis=1) - 1.0) <= 1.0e-12)
            and np.all(np.abs(np.linalg.norm(arrays["post_target_state_13"][:, 3:7], axis=1) - 1.0) <= 1.0e-12)
            and np.all(np.abs(np.linalg.norm(arrays["post_stage_service_state_29"][:, 3:7], axis=1) - 1.0) <= 1.0e-12)
            and np.all(np.abs(np.linalg.norm(arrays["post_stage_target_state_13"][:, 3:7], axis=1) - 1.0) <= 1.0e-12)
        )
        report.require(post_quaternion_ok, "CASE_POST_QUATERNION_NORM", case_id)
        post_geometry_replay_pass, post_geometry_replay = (
            _validate_post_geometry_replay(
                report,
                arrays=arrays,
                case_id=case_id,
            )
        )
        carried_work = responses.get("post_signed_W_act_carried_constant_J")
        report.require(_same_float(carried_work, arrays["signed_W_act_J"][-1]), "CASE_POST_WORK_NOT_CARRIED", case_id)
        report.require(responses.get("post_actuator_work_reset_on_removal") is False, "CASE_POST_WORK_RESET", case_id)
        report.require(responses.get("post_release_generalized_force_14") == [0.0] * 14, "CASE_POST_GENERALIZED_FORCE_NONZERO", case_id)
        post_contact_pass = bool(
            float(np.max(np.abs(arrays["post_contact_force_N"]))) <= 1.0e-12
            and float(np.max(np.abs(arrays["post_contact_torque_N_m"]))) <= 1.0e-12
        )
        post_work_pass = bool(
            _same_float(carried_work, arrays["signed_W_act_J"][-1])
            and responses.get("post_actuator_work_reset_on_removal") is False
            and responses.get("post_release_generalized_force_14") == [0.0] * 14
        )
        post_pass = bool(
            post_linear <= 1.0e-9 and post_angular <= 1.0e-9
            and post_energy <= 1.0e-7 and full_post_clearance
            and post_contact_pass and post_work_pass
            and post_geometry_replay_pass
        )
        post_metrics = {
            "linear_drift": post_linear, "angular_drift": post_angular,
            "energy_drift": post_energy, "full_clearance": full_post_clearance,
            "independent_geometry_replay": post_geometry_replay,
        }
    g03_pass = bool(np.all(arrays["command_Q_14"][:, :12] == 0.0) and np.all(arrays["stage_command_Q_14"][:, :12] == 0.0))
    g04_pass = bool(work_pass and (not finite_event or post_work_pass))
    g05_pass = bool(linear_drift <= 1.0e-9 and angular_drift <= 1.0e-9 and (not finite_event or (post_metrics.get("linear_drift", math.inf) <= 1.0e-9 and post_metrics.get("angular_drift", math.inf) <= 1.0e-9)))
    g06_pass = bool(energy_residual <= 1.0e-7 and (not finite_event or post_metrics.get("energy_drift", math.inf) <= 1.0e-7))
    g07_pass = bool(float(np.max(np.abs(arrays["contact_force_N"]))) <= 1.0e-12 and float(np.max(np.abs(arrays["contact_torque_N_m"]))) <= 1.0e-12 and (not finite_event or post_contact_pass))
    g08_pass = bool(command_profile_pass and (not finite_event or np.all(arrays["command_Q_14"][-1] == 0.0)))
    independent_integrity = bool(
        geometry_pass and g03_pass and g04_pass and g05_pass and g06_pass
        and g07_pass and g08_pass and np.all(sample_good)
        and active_geometry_replay_pass
        and (not finite_event or post_pass)
    )
    independently_reproduced_geometry_predicate = bool(
        geometry_pass and active_geometry_replay_pass
        and (not finite_event or post_geometry_replay_pass)
    )
    return {
        "work_delta_J": work_delta, "fine_work_J": fine, "coarse_work_J": coarse,
        "fine_work_error_J": fine_error, "coarse_work_error_J": coarse_error,
        "cumulative_work_error_J": cumulative_work_error,
        "linear_momentum_drift": linear_drift, "angular_momentum_drift": angular_drift,
        "energy_minus_work_residual": energy_residual, "post": post_metrics,
        "independent_active_geometry_replay": active_geometry_replay,
        "registered_command_pass": command_profile_pass,
        "clearance": clearance,
        "g03_pass": g03_pass, "g04_pass": g04_pass, "g05_pass": g05_pass,
        "g06_pass": g06_pass, "g07_pass": g07_pass, "g08_pass": g08_pass,
        "g09_predicate": independently_finite,
        "g10_pass": bool(not finite_event or np.array_equal(arrays["post_service_state_29"][0], arrays["service_state_29"][-1]) and np.array_equal(arrays["post_target_state_13"][0], arrays["target_state_13"][-1])),
        "g11_pass": bool(not finite_event or post_pass),
        "g16_predicate": independently_reproduced_geometry_predicate,
        "independent_integrity_pass": independent_integrity,
    }


def _expected_execution_ordinals(schedule: Mapping[str, Any]) -> dict[str, int]:
    slots = schedule["slots"]
    discovery: list[Mapping[str, Any]] = []
    conditional: list[Mapping[str, Any]] = []
    for lane in LANES:
        lane_slots = [slot for slot in slots if slot["lane_id"] == lane]
        discovery.extend(lane_slots[:19])
    for lane in LANES:
        lane_slots = [slot for slot in slots if slot["lane_id"] == lane]
        conditional.extend(lane_slots[19:24])
    return {str(slot["case_id"]): index for index, slot in enumerate(discovery + conditional)}


def _validate_na_a2(
    report: ValidationReport,
    metadata: Mapping[str, Any],
    gates: Mapping[str, Mapping[str, Any]],
    expected_npz: Path,
) -> None:
    case_id = str(metadata.get("case_id"))
    report.require(metadata.get("arm") == "A2", "NA_RECORD_NOT_A2", case_id)
    report.require(metadata.get("terminal_status") == "NOT_EVALUATED_NO_A1_SUCCESS", "NA_A2_TERMINAL_STATUS", case_id)
    report.require(set(gates) == BASE_CASE_GATES, "NA_A2_GATE_SET", {"case_id": case_id, "gates": sorted(gates)})
    for gate_id, gate in gates.items():
        report.require(gate.get("evaluation_status") == "NOT_APPLICABLE", "NA_A2_GATE_STATUS", {"case_id": case_id, "gate_id": gate_id})
        report.require(gate.get("scientific_predicate") is None, "NA_A2_GATE_PREDICATE", {"case_id": case_id, "gate_id": gate_id})
        report.require(gate.get("applicability_reason") == "A2_NOT_EVALUATED_NO_A1_PARENT", "NA_A2_GATE_REASON", {"case_id": case_id, "gate_id": gate_id})
    event = metadata.get("event_provenance", {})
    report.require(event.get("fresh_b3_reconstruction") is False, "NA_A2_FRESHNESS_MUST_BE_FALSE", case_id)
    report.require(all(event.get(key) is None for key in ("first_qualifying_event_index", "acquisition_time_s", "acquisition_certificate_payload", "acquisition_certificate_sha256", "clearance_certificate_sha256", "removal_time_s")), "NA_A2_EVENT_MUST_BE_NULL", case_id)
    report.require(
        metadata.get("acquisition") == {
            "status": "NOT_EVALUATED", "acquisition_time_s": None,
        },
        "NA_A2_TOP_LEVEL_ACQUISITION", case_id,
    )
    report.require(
        metadata.get("command_parameters") == {
            "selected_parent": None,
            "variant_id": metadata.get("registered_slot", {}).get("variant_id"),
        },
        "NA_A2_COMMAND_PARAMETERS", case_id,
    )
    report.require(
        metadata.get("geometry_domain") == {
            "status": "NOT_EVALUATED", "passed": None,
        },
        "NA_A2_GEOMETRY_DOMAIN", case_id,
    )
    report.require(
        metadata.get("opening_sign") == {
            "status": "NOT_EVALUATED", "registered_left_right": [1, 1],
        },
        "NA_A2_OPENING_SIGN", case_id,
    )
    report.require(
        metadata.get("responses") == {
            "synthetic_removal_executed": False,
            "finite_removal_event": False,
            "selector_case_integrity_pass": False,
        },
        "NA_A2_RESPONSES", case_id,
    )
    report.require(all(metadata.get(key) is None for key in ("npz_path", "npz_bytes", "npz_sha256", "numeric_payload_sha256")), "NA_A2_NPZ_FIELDS_NOT_NULL", case_id)
    report.require(metadata.get("npz_arrays") == [], "NA_A2_NPZ_ARRAYS_NOT_EMPTY", case_id)
    report.require(not expected_npz.exists(), "NA_A2_NPZ_FILE_EXISTS", expected_npz.as_posix())


FRESH_B3_EVENT_SOURCE = "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE"
HASH_BOUND_B3_EVENT_SOURCE = "HASH_BOUND_B3_REFERENCE_RECORD_205"
FRESH_CERTIFICATE_ALLOWED_POINTER_DIFFERENCES = (
    "/event/run_id",
    "/acquisition/run_id",
    "/event/source",
    "/event/b3_dissipation_J",
    "/acquisition/energy_audit/D_B3_minus_J",
)


def _float64_ordered_bits(value: Any) -> int | None:
    if not finite_number(value):
        return None
    scalar = np.asarray(float(value), dtype="<f8")
    bits = int(scalar.view("<u8").item())
    sign = 1 << 63
    mask = (1 << 64) - 1
    return ((~bits) & mask) if bits & sign else bits | sign


def _float64_ulp_distance(left: Any, right: Any) -> int | None:
    left_bits = _float64_ordered_bits(left)
    right_bits = _float64_ordered_bits(right)
    if left_bits is None or right_bits is None:
        return None
    return abs(left_bits - right_bits)


def _fixed_b4e_certificate_source_bindings() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for key in ("events", "acquisitions"):
        path, size, digest = B4E_PROVENANCE_FILES[key]
        result[key] = {
            "path": path.resolve().relative_to(PROJECT_ROOT).as_posix(),
            "bytes": size,
            "sha256": digest,
        }
    return result


def _validate_fresh_certificate_template_comparison(
    report: ValidationReport,
    *,
    payload: Mapping[str, Any],
    lane: str,
    case_id: str,
    event_templates: Mapping[str, Mapping[str, Any]],
    acquisition_templates: Mapping[str, Mapping[str, Any]],
    code_prefix: str,
) -> dict[str, Any] | None:
    """Compare fresh B3 evidence to fixed B4E with one frozen 2-ULP allowlist."""

    event = payload.get("event")
    acquisition = payload.get("acquisition")
    parent_event = event_templates.get(lane)
    parent_acquisition = acquisition_templates.get(lane)
    if not report.require(
        isinstance(event, Mapping) and isinstance(acquisition, Mapping),
        f"{code_prefix}_FRESH_CERTIFICATE_EVENT_ACQUISITION_OBJECT",
        case_id,
    ):
        return None
    if not report.require(
        isinstance(parent_event, Mapping)
        and isinstance(parent_acquisition, Mapping),
        f"{code_prefix}_FIXED_CERTIFICATE_TEMPLATE_MISSING",
        lane,
    ):
        return None
    assert isinstance(event, Mapping) and isinstance(acquisition, Mapping)
    assert isinstance(parent_event, Mapping) and isinstance(parent_acquisition, Mapping)

    parent_energy = parent_acquisition.get("energy_audit")
    fresh_energy = acquisition.get("energy_audit")
    event_fixed_d = parent_event.get("b3_dissipation_J")
    event_fresh_d = event.get("b3_dissipation_J")
    acquisition_fixed_d = (
        parent_energy.get("D_B3_minus_J")
        if isinstance(parent_energy, Mapping) else None
    )
    acquisition_fresh_d = (
        fresh_energy.get("D_B3_minus_J")
        if isinstance(fresh_energy, Mapping) else None
    )
    event_ulp = _float64_ulp_distance(event_fresh_d, event_fixed_d)
    acquisition_ulp = _float64_ulp_distance(
        acquisition_fresh_d, acquisition_fixed_d,
    )
    fresh_bits_equal = (
        _float64_ordered_bits(event_fresh_d) is not None
        and _float64_ordered_bits(event_fresh_d)
        == _float64_ordered_bits(acquisition_fresh_d)
    )
    event_ulp_pass = event_ulp is not None and event_ulp <= 2
    acquisition_ulp_pass = (
        acquisition_ulp is not None and acquisition_ulp <= 2
    )
    dissipation_nonnegative = bool(
        finite_number(event_fresh_d)
        and finite_number(acquisition_fresh_d)
        and float(event_fresh_d) >= 0.0
        and float(acquisition_fresh_d) >= 0.0
    )
    report.require(
        fresh_bits_equal,
        f"{code_prefix}_FRESH_DISSIPATION_INTERNAL_NOT_BIT_EXACT",
        case_id,
    )
    report.require(
        dissipation_nonnegative and event_ulp_pass and acquisition_ulp_pass,
        f"{code_prefix}_FRESH_DISSIPATION_EXCEEDS_2_ULP",
        {
            "case_id": case_id,
            "event_ulp": event_ulp,
            "acquisition_ulp": acquisition_ulp,
        },
    )

    fixed_source = parent_event.get("source")
    fresh_source = event.get("source")
    source_pass = bool(
        fixed_source in (HASH_BOUND_B3_EVENT_SOURCE, FRESH_B3_EVENT_SOURCE)
        and fresh_source == FRESH_B3_EVENT_SOURCE
    )
    report.require(
        source_pass,
        f"{code_prefix}_FRESH_EVENT_SOURCE_NOT_ALLOWED",
        {"case_id": case_id, "fixed": fixed_source, "fresh": fresh_source},
    )
    run_id_pass = bool(
        event.get("run_id") == case_id
        and acquisition.get("run_id") == case_id
    )
    report.require(
        run_id_pass,
        f"{code_prefix}_FRESH_CERTIFICATE_RUN_ID_BINDING",
        case_id,
    )

    normalized_event = deepcopy(dict(event))
    normalized_acquisition = deepcopy(dict(acquisition))
    expected_event = deepcopy(dict(parent_event))
    expected_acquisition = deepcopy(dict(parent_acquisition))
    expected_event["run_id"] = case_id
    expected_acquisition["run_id"] = case_id
    normalized_event["source"] = expected_event.get("source")
    normalized_event["b3_dissipation_J"] = event_fixed_d
    normalized_energy = normalized_acquisition.get("energy_audit")
    if isinstance(normalized_energy, dict):
        normalized_energy["D_B3_minus_J"] = acquisition_fixed_d
    all_other_exact = bool(
        canonical_bytes(normalized_event) == canonical_bytes(expected_event)
        and canonical_bytes(normalized_acquisition)
        == canonical_bytes(expected_acquisition)
    )
    report.require(
        all_other_exact,
        f"{code_prefix}_FRESH_CERTIFICATE_NONALLOWLIST_DRIFT",
        case_id,
    )
    passed = bool(
        run_id_pass and source_pass and fresh_bits_equal
        and dissipation_nonnegative and event_ulp_pass
        and acquisition_ulp_pass and all_other_exact
    )
    return {
        "fixed_source_bindings": _fixed_b4e_certificate_source_bindings(),
        "allowed_pointer_differences": list(
            FRESH_CERTIFICATE_ALLOWED_POINTER_DIFFERENCES
        ),
        "dissipation_comparisons": {
            "event": {
                "fixed": event_fixed_d,
                "fresh": event_fresh_d,
                "ulp_distance": event_ulp,
                "maximum_ulp": 2,
            },
            "acquisition": {
                "fixed": acquisition_fixed_d,
                "fresh": acquisition_fresh_d,
                "ulp_distance": acquisition_ulp,
                "maximum_ulp": 2,
            },
        },
        "all_other_pointers_exact": all_other_exact,
        "passed": passed,
    }


def _validate_acquisition_provenance(
    report: ValidationReport,
    *,
    metadata: Mapping[str, Any],
    event_templates: Mapping[str, Mapping[str, Any]],
    acquisition_templates: Mapping[str, Mapping[str, Any]],
) -> None:
    """Independently bind one fresh B3 event/acquisition to immutable B4E truth."""

    case_id = str(metadata.get("case_id"))
    lane = str(metadata.get("lane_id"))
    provenance = metadata.get("event_provenance", {})
    payload = provenance.get("acquisition_certificate_payload")
    if not report.require(isinstance(payload, dict), "CASE_ACQUISITION_CERTIFICATE_PAYLOAD_OBJECT", case_id):
        return
    report.require(
        set(payload) == {"lane_id", "case_id", "event", "acquisition"},
        "CASE_ACQUISITION_CERTIFICATE_PAYLOAD_FIELDS",
        case_id,
    )
    report.require(payload.get("lane_id") == lane, "CASE_ACQUISITION_PAYLOAD_LANE", case_id)
    report.require(payload.get("case_id") == case_id, "CASE_ACQUISITION_PAYLOAD_CASE", case_id)
    certificate = report.guard(
        "CASE_ACQUISITION_CERTIFICATE_PAYLOAD_NOT_CANONICAL_JSON",
        lambda: canonical_sha256(payload),
    )
    report.require(
        certificate is not None
        and certificate == provenance.get("acquisition_certificate_sha256"),
        "CASE_ACQUISITION_CERTIFICATE_RECOMPUTATION",
        case_id,
    )

    event = payload.get("event")
    acquisition = payload.get("acquisition")
    if not report.require(isinstance(event, dict), "CASE_ACQUISITION_PAYLOAD_EVENT_OBJECT", case_id):
        return
    if not report.require(isinstance(acquisition, dict), "CASE_ACQUISITION_PAYLOAD_ACQUISITION_OBJECT", case_id):
        return
    report.require(metadata.get("acquisition") == acquisition, "CASE_TOP_LEVEL_ACQUISITION_PAYLOAD_MISMATCH", case_id)
    report.require(event.get("run_id") == case_id, "CASE_EVENT_RUN_ID_NOT_CASE_ID", case_id)
    report.require(acquisition.get("run_id") == case_id, "CASE_ACQUISITION_RUN_ID_NOT_CASE_ID", case_id)
    method, step_s = LANE_DEFINITIONS.get(lane, (None, None))
    report.require(event.get("method") == method, "CASE_EVENT_METHOD_NOT_FROZEN_LANE", case_id)
    report.require(_same_float(event.get("step_s"), step_s), "CASE_EVENT_STEP_NOT_FROZEN_LANE", case_id)
    report.require(
        isinstance(event.get("index"), int)
        and not isinstance(event.get("index"), bool)
        and event.get("index") == provenance.get("first_qualifying_event_index"),
        "CASE_EVENT_INDEX_PAYLOAD_MISMATCH",
        case_id,
    )
    report.require(
        _same_float(event.get("time_s"), provenance.get("acquisition_time_s"))
        and _same_float(acquisition.get("acquisition_time_s"), provenance.get("acquisition_time_s")),
        "CASE_EVENT_ACQUISITION_TIME_PAYLOAD_MISMATCH",
        case_id,
    )

    parent_event = event_templates.get(lane)
    parent_acquisition = acquisition_templates.get(lane)
    if not report.require(isinstance(parent_event, dict), "CASE_B4E_EVENT_TEMPLATE_MISSING", lane):
        return
    if not report.require(isinstance(parent_acquisition, dict), "CASE_B4E_ACQUISITION_TEMPLATE_MISSING", lane):
        return
    _validate_fresh_certificate_template_comparison(
        report,
        payload=payload,
        lane=lane,
        case_id=case_id,
        event_templates=event_templates,
        acquisition_templates=acquisition_templates,
        code_prefix="CASE",
    )


def _expected_initial_states_from_acquisition_payload(
    report: ValidationReport,
    metadata: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray] | None:
    """Rebuild the attached active initial state from immutable B4E fields.

    The event configuration is pre-acquisition truth, while the active
    velocities must come from ``z_plus_reduced``.  In particular, event
    ``nu_s_mixed`` and target twist are z-minus quantities and are not valid
    substitutes for the post-acquisition attached initial velocity.
    """

    case_id = str(metadata.get("case_id"))
    payload = metadata.get("event_provenance", {}).get(
        "acquisition_certificate_payload", {},
    )
    if not isinstance(payload, Mapping):
        report.require(False, "CASE_INITIAL_STATE_ACQUISITION_PAYLOAD_MISSING", case_id)
        return None
    event = payload.get("event", {})
    acquisition = payload.get("acquisition", {})
    if not isinstance(event, Mapping) or not isinstance(acquisition, Mapping):
        report.require(False, "CASE_INITIAL_STATE_EVENT_OR_ACQUISITION_MISSING", case_id)
        return None
    service = event.get("service", {})
    target = event.get("target", {})
    try:
        position = np.asarray(service.get("base_position_inertial_m"), dtype=float)
        quaternion = np.asarray(
            service.get("base_quaternion_body_to_inertial_wxyz"), dtype=float,
        )
        joints = np.asarray(service.get("joint_coordinates_mixed"), dtype=float)
        target_position = np.asarray(target.get("position_inertial_m"), dtype=float)
        target_quaternion = np.asarray(
            target.get("quaternion_body_to_inertial_wxyz"), dtype=float,
        )
        z_plus = np.asarray(acquisition.get("z_plus_reduced"), dtype=float)
        eta_plus = np.asarray(acquisition.get("eta_plus"), dtype=float)
    except (TypeError, ValueError):
        report.require(False, "CASE_INITIAL_STATE_TEMPLATE_NUMERIC", case_id)
        return None
    valid = bool(
        position.shape == (3,) and quaternion.shape == (4,)
        and joints.shape == (8,) and target_position.shape == (3,)
        and target_quaternion.shape == (4,) and z_plus.shape == (20,)
        and eta_plus.shape == (14,)
        and all(np.all(np.isfinite(value)) for value in (
            position, quaternion, joints, target_position,
            target_quaternion, z_plus, eta_plus,
        ))
    )
    report.require(valid, "CASE_INITIAL_STATE_TEMPLATE_SHAPE_OR_FINITE", case_id)
    if not valid:
        return None
    report.require(
        bool(np.array_equal(eta_plus, z_plus[:14])),
        "CASE_ACQUISITION_ETA_PLUS_Z_PLUS_BINDING", case_id,
    )
    report.require(
        abs(float(np.linalg.norm(quaternion)) - 1.0) <= 1.0e-12
        and abs(float(np.linalg.norm(target_quaternion)) - 1.0) <= 1.0e-12,
        "CASE_INITIAL_TEMPLATE_QUATERNION_NORM", case_id,
    )
    expected_service = np.concatenate((position, quaternion, joints, z_plus[:14]))
    expected_target = np.concatenate((
        target_position, target_quaternion, z_plus[14:20],
    ))
    return expected_service, expected_target


def _validate_executed_case(
    report: ValidationReport,
    *,
    metadata: Mapping[str, Any],
    gates: Mapping[str, Mapping[str, Any]],
    npz_path: Path,
    contracts: Mapping[str, Mapping[str, Any]],
    slot: Mapping[str, Any],
    event_templates: Mapping[str, Mapping[str, Any]],
    acquisition_templates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    case_id = str(metadata.get("case_id"))
    arm = str(metadata.get("arm"))
    expected_gates = BASE_CASE_GATES | ({G02} if arm == "A0" else set())
    report.require(set(gates) == expected_gates, "CASE_GATE_SET", {"case_id": case_id, "expected": sorted(expected_gates), "actual": sorted(gates)})
    event = metadata.get("event_provenance", {})
    report.require(event.get("fresh_b3_reconstruction") is True, "CASE_NOT_FRESH_B3", case_id)
    report.require(event.get("lane_id") == metadata.get("lane_id"), "CASE_EVENT_LANE_MISMATCH", case_id)
    report.require(isinstance(event.get("first_qualifying_event_index"), int) and event.get("first_qualifying_event_index") >= 0, "CASE_EVENT_INDEX", case_id)
    report.require(finite_number(event.get("acquisition_time_s")), "CASE_ACQUISITION_TIME", case_id)
    report.require(is_sha256(event.get("acquisition_certificate_sha256")), "CASE_ACQUISITION_CERTIFICATE", case_id)
    report.require(is_sha256(event.get("clearance_certificate_sha256")), "CASE_CLEARANCE_CERTIFICATE", case_id)
    _validate_acquisition_provenance(
        report,
        metadata=metadata,
        event_templates=event_templates,
        acquisition_templates=acquisition_templates,
    )
    geometry = metadata.get("geometry_domain", {})
    geometry_pass = geometry.get("passed") is True
    failure = geometry.get("failure")
    opening = metadata.get("opening_sign", {})
    report.require(opening.get("registered_left_right") == [1, 1], "CASE_REGISTERED_OPENING_SIGN", case_id)
    if geometry_pass:
        report.require(opening.get("initial_recomputed_left_right") == [1, 1], "CASE_RECOMPUTED_OPENING_SIGN", case_id)
        report.require(opening.get("all_consumed_signs_bound_to_raw_and_registered") is True, "CASE_CONSUMED_OPENING_SIGN", case_id)
    else:
        # An initial P-domain or opening-sign exit has no successful initial
        # recomputation.  A later consumed-sign mismatch is the one legitimate
        # reason for the aggregate consumed-sign binding to be false.
        failure_at_initial = bool(
            isinstance(failure, Mapping)
            and failure.get("stage_label") == "ACCEPTED_SAMPLE_0"
            and _same_float(
                failure.get("time_s"),
                metadata.get("event_provenance", {}).get("acquisition_time_s"),
            )
        )
        if failure_at_initial:
            raw_initial = failure.get("opening_sign_left_right")
            expected_initial = raw_initial if isinstance(raw_initial, list) else None
        else:
            expected_initial = [1, 1]
        report.require(
            opening.get("initial_recomputed_left_right") == expected_initial,
            "CASE_DOMAIN_EXIT_INITIAL_OPENING_SIGN", case_id,
        )
        expected_consumed = not (
            isinstance(failure, Mapping)
            and failure.get("reason") == "CONSUMED_OPENING_SIGN_MISMATCH"
        )
        report.require(
            opening.get("all_consumed_signs_bound_to_raw_and_registered") is expected_consumed,
            "CASE_DOMAIN_EXIT_CONSUMED_OPENING_SIGN", case_id,
        )
    report.require(geometry.get("P_coordinate_m_closed_interval_left_right") == [[0.0, 0.0715], [0.0, 0.0715]], "CASE_GEOMETRY_INTERVAL", case_id)
    report.require(geometry.get("clipping_or_extrapolation_used") is False, "CASE_CLIPPING_OR_EXTRAPOLATION", case_id)
    report.require(
        geometry.get("failure_probe_published_in_fixed_shape_npz") is False,
        "CASE_DOMAIN_EXIT_FIXED_SHAPE_PROBE_FORBIDDEN", case_id,
    )
    report.require(
        geometry.get("published_stage_rows_are_raw_pre_failure_only") is (not geometry_pass),
        "CASE_DOMAIN_EXIT_RAW_PREFIX_DECLARATION", case_id,
    )
    if geometry_pass:
        report.require(
            failure is None and geometry.get("failure_probe_source") is None,
            "CASE_GEOMETRY_PASS_HAS_FAILURE_PROBE", case_id,
        )
    else:
        report.require(
            isinstance(failure, Mapping)
            and geometry.get("failure_probe_source") == "FROZEN_SOLVER_DOMAINEXIT_RECORD",
            "CASE_DOMAIN_EXIT_FAILURE_PROBE_BINDING", case_id,
        )
    command = metadata.get("command_parameters", {})
    report.require(command.get("Q_ref_per_finger_N") == contracts["reference"].get("individual_finger_reference_force_N"), "CASE_QREF_NOT_COMMON", case_id)
    report.require(command.get("only_nonzero_generalized_force_indices_zero_based") == [12, 13], "CASE_ALLOWED_COMMAND_INDICES", case_id)
    report.require(command.get("physical_actuator_force_capacity_N") is None, "CASE_PHYSICAL_FORCE_NOT_NULL", case_id)
    _validate_registered_command(report, metadata, slot)
    verify_file_record(
        report, path=npz_path, expected_bytes=metadata.get("npz_bytes"),
        expected_sha256=metadata.get("npz_sha256"), code=f"CASE_NPZ_{metadata.get('slot_index', 'UNKNOWN')}",
    )
    arrays = load_npz_strict(report, npz_path, code=f"CASE_NPZ_{metadata.get('slot_index', 'UNKNOWN')}")
    if arrays is None:
        return {}
    report.require(sorted(arrays) == metadata.get("npz_arrays"), "CASE_METADATA_NPZ_INVENTORY", case_id)
    report.require(array_payload_sha256(arrays) == metadata.get("numeric_payload_sha256"), "CASE_NUMERIC_PAYLOAD_HASH", case_id)
    metrics = _validate_npz_arrays(report, metadata=metadata, arrays=arrays, case_id=case_id, slot=slot)
    initial_truth = _expected_initial_states_from_acquisition_payload(report, metadata)
    if (
        initial_truth is not None
        and "time_s" in arrays and len(arrays["time_s"])
        and arrays.get("service_state_29", np.empty(0)).shape[1:] == (29,)
        and arrays.get("target_state_13", np.empty(0)).shape[1:] == (13,)
    ):
        expected_service, expected_target = initial_truth
        report.require(
            bool(np.max(np.abs(arrays["service_state_29"][0] - expected_service)) <= 1.0e-12),
            "CASE_INITIAL_SERVICE_STATE_NOT_IMMUTABLE_B4E", case_id,
        )
        report.require(
            bool(np.max(np.abs(arrays["target_state_13"][0] - expected_target)) <= 1.0e-12),
            "CASE_INITIAL_TARGET_STATE_NOT_IMMUTABLE_B4E", case_id,
        )
    responses = metadata.get("responses", {})
    finite_event = responses.get("finite_removal_event") is True
    removal_executed = responses.get("synthetic_removal_executed") is True
    post_reported = responses.get("post_release_passed") is True
    report.require(removal_executed is (finite_event and post_reported), "CASE_FINITE_EVENT_REMOVAL_POST_RELATION", case_id)
    if not geometry_pass:
        expected_terminal = "DIAGNOSTIC_FAIL_CLOSED_GEOMETRY_DOMAIN"
    elif not finite_event:
        expected_terminal = "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"
    elif post_reported:
        expected_terminal = "SYNTHETIC_CONSTRAINT_REMOVAL_AND_POST_RELEASE_OBSERVATION_COMPLETE"
    else:
        expected_terminal = None
    if expected_terminal is not None:
        report.require(
            metadata.get("terminal_status") == expected_terminal,
            "CASE_TERMINAL_STATUS_NOT_RAW_OUTCOME",
            {"case_id": case_id, "expected": expected_terminal, "actual": metadata.get("terminal_status")},
        )
    metric_by_gate = {
        G03: "g03_pass", G04: "g04_pass", G05: "g05_pass",
        G06: "g06_pass", G07: "g07_pass", G08: "g08_pass",
    }
    for gate_id, metric_name in metric_by_gate.items():
        gate = gates.get(gate_id, {})
        computed = metrics.get(metric_name) is True
        report.require(gate.get("evaluation_status") == "PASS" and gate.get("scientific_predicate") is True, "CASE_INTEGRITY_GATE_NOT_TRUE", {"case_id": case_id, "gate_id": gate_id})
        report.require(computed, "CASE_INTEGRITY_GATE_RAW_RECOMPUTATION", {"case_id": case_id, "gate_id": gate_id})
    report.require(gates.get(G16, {}).get("evaluation_status") == "PASS", "CASE_G16_DETECTOR_NOT_PASS", case_id)
    report.require(gates.get(G16, {}).get("scientific_predicate") is geometry_pass, "CASE_G16_PREDICATE", case_id)
    report.require(metrics.get("g16_predicate") is geometry_pass, "CASE_G16_RAW_RECOMPUTATION", case_id)
    if geometry_pass:
        report.require(gates.get(G09, {}).get("evaluation_status") == "PASS", "CASE_G09_NOT_EVALUATED", case_id)
        report.require(gates.get(G09, {}).get("scientific_predicate") is finite_event, "CASE_G09_OUTCOME", case_id)
        report.require(metrics.get("g09_predicate") is finite_event, "CASE_G09_RAW_RECOMPUTATION", case_id)
        detail_clearance = gates.get(G09, {}).get("detail", {}).get("clearance")
        report.require(detail_clearance == responses.get("clearance_certificate_payload"), "CASE_G09_CLEARANCE_CERTIFICATE_PAYLOAD_BINDING", case_id)
    else:
        report.require(gates.get(G09, {}).get("evaluation_status") == "NOT_APPLICABLE" and gates.get(G09, {}).get("applicability_reason") == "CASE_TERMINATED_GEOMETRY_BEFORE_OUTCOME", "CASE_G09_GEOMETRY_NA", case_id)
        report.require(finite_event is False and metrics.get("g09_predicate") is False, "CASE_DOMAIN_EXIT_EVENT_FORBIDDEN", case_id)
    if finite_event:
        report.require(gates.get(G10, {}).get("evaluation_status") == "PASS" and gates.get(G10, {}).get("scientific_predicate") is True, "CASE_G10_EVENT", case_id)
        report.require(gates.get(G11, {}).get("evaluation_status") == "PASS" and gates.get(G11, {}).get("scientific_predicate") is True, "CASE_G11_EVENT", case_id)
        report.require(metrics.get("g10_pass") is True, "CASE_G10_RAW_MAPPING", case_id)
        report.require(metrics.get("g11_pass") is True, "CASE_G11_RAW_POST_RELEASE", case_id)
        report.require(post_reported, "CASE_POST_RELEASE_NOT_PASS", case_id)
        mapping = gates.get(G10, {}).get("detail", {})
        maxima = mapping.get("native_velocity_jump_maxima", {})
        raw_jump_maxima = {
            "service_base_linear_m_s": float(np.max(np.abs(
                arrays["post_service_state_29"][0, 15:18]
                - arrays["service_state_29"][-1, 15:18]
            ))),
            "service_base_angular_rad_s": float(np.max(np.abs(
                arrays["post_service_state_29"][0, 18:21]
                - arrays["service_state_29"][-1, 18:21]
            ))),
            "service_R_joint_rad_s": float(np.max(np.abs(
                arrays["post_service_state_29"][0, 21:27]
                - arrays["service_state_29"][-1, 21:27]
            ))),
            "service_P_joint_m_s": float(np.max(np.abs(
                arrays["post_service_state_29"][0, 27:29]
                - arrays["service_state_29"][-1, 27:29]
            ))),
            "target_linear_m_s": float(np.max(np.abs(
                arrays["post_target_state_13"][0, 7:10]
                - arrays["target_state_13"][-1, 7:10]
            ))),
            "target_angular_rad_s": float(np.max(np.abs(
                arrays["post_target_state_13"][0, 10:13]
                - arrays["target_state_13"][-1, 10:13]
            ))),
        }
        report.require(
            maxima == raw_jump_maxima
            and all(value <= 1.0e-12 for value in raw_jump_maxima.values()),
            "CASE_G10_NATIVE_JUMP_MAXIMA", case_id,
        )
        raw_linear_impulse = (
            arrays["post_total_linear_momentum_N_s"][0]
            - arrays["total_linear_momentum_N_s"][-1]
        )
        raw_angular_impulse = (
            arrays["post_total_angular_momentum_N_m_s"][0]
            - arrays["total_angular_momentum_N_m_s"][-1]
        )
        raw_kinetic_jump = float(
            arrays["post_total_kinetic_energy_J"][0]
            - arrays["total_kinetic_energy_J"][-1]
        )
        report.require(
            mapping.get("linear_impulse_N_s") == [0.0, 0.0, 0.0]
            and float(np.max(np.abs(raw_linear_impulse))) <= 1.0e-12,
            "CASE_G10_LINEAR_IMPULSE", case_id,
        )
        report.require(
            mapping.get("angular_impulse_N_m_s") == [0.0, 0.0, 0.0]
            and float(np.max(np.abs(raw_angular_impulse))) <= 1.0e-12,
            "CASE_G10_ANGULAR_IMPULSE", case_id,
        )
        report.require(
            mapping.get("kinetic_energy_jump_J") == 0.0
            and abs(raw_kinetic_jump) <= 1.0e-12,
            "CASE_G10_KINETIC_JUMP", case_id,
        )
        report.require(mapping.get("ideal_constraint_stored_energy_J") == 0.0, "CASE_G10_STORED_ENERGY", case_id)
        g11_detail = gates.get(G11, {}).get("detail", {})
        raw_post_maxima = {
            "linear_momentum_drift_N_s": metrics.get("post", {}).get("linear_drift"),
            "angular_momentum_drift_N_m_s": metrics.get("post", {}).get("angular_drift"),
            "energy_drift_J": metrics.get("post", {}).get("energy_drift"),
            "contact_force_N": float(np.max(np.abs(arrays["post_contact_force_N"]))),
            "contact_torque_N_m": float(np.max(np.abs(arrays["post_contact_torque_N_m"]))),
        }
        report.require(
            g11_detail.get("maxima") == raw_post_maxima,
            "CASE_G11_MAXIMA_NOT_RAW_RECOMPUTATION", case_id,
        )
        crosscheck = g11_detail.get("parent_b4e_crosscheck", {})
        report.require(crosscheck.get("passed") is True and crosscheck.get("parent_post_release_passed") is True, "CASE_G11_B4E_PARENT_NOT_PASS", case_id)
        for field in ("mapping_z_before_max_error", "terminal_service_state_max_error", "terminal_target_state_max_error"):
            report.require(finite_number(crosscheck.get(field)) and float(crosscheck[field]) <= 1.0e-12, "CASE_G11_B4E_PARENT_ERROR", {"case_id": case_id, "field": field})
        report.require(g11_detail.get("terminal_status") == metadata.get("terminal_status"), "CASE_G11_TERMINAL_STATUS", case_id)
        report.require(crosscheck.get("parent_terminal_status") == metadata.get("terminal_status"), "CASE_G11_PARENT_TERMINAL_STATUS", case_id)
    else:
        reason = "NO_FINITE_REMOVAL_EVENT" if geometry_pass else "CASE_TERMINATED_GEOMETRY_BEFORE_EVENT"
        for gate_id in (G10, G11):
            report.require(gates.get(gate_id, {}).get("evaluation_status") == "NOT_APPLICABLE" and gates.get(gate_id, {}).get("applicability_reason") == reason, "CASE_EVENT_GATE_NA_REASON", {"case_id": case_id, "gate_id": gate_id})
    if arm == "A0":
        report.require(gates.get(G02, {}).get("evaluation_status") == "PASS" and gates.get(G02, {}).get("scientific_predicate") is True, "A0_G02_NOT_PASS", case_id)
        comparison = metadata.get("responses", {}).get("a0_replay_comparison", {})
        report.require(comparison.get("passed") is True and comparison.get("fresh_b4e_reference_propagation") is True, "A0_FRESH_PARENT_REPLAY", case_id)
        report.require(finite_event is False, "A0_FINITE_REMOVAL_FORBIDDEN", case_id)
        report.require(bool(np.all(arrays["command_Q_14"] == 0.0)), "A0_Q_NOT_EXACT_ZERO", case_id)
        report.require(bool(np.all(arrays["signed_W_act_J"] == 0.0)), "A0_W_NOT_EXACT_ZERO", case_id)
    reported_work = metadata.get("responses", {}).get("signed_work_terminal_J")
    if metrics:
        report.require(finite_number(reported_work) and abs(float(reported_work) - float(arrays["signed_W_act_J"][-1])) <= 1.0e-15, "CASE_REPORTED_TERMINAL_WORK", case_id)
        report.require(responses.get("selector_case_integrity_pass") is metrics.get("independent_integrity_pass"), "CASE_SELECTOR_INTEGRITY_SELF_REPORT_MISMATCH", case_id)
    return {"metadata": metadata, "arrays": arrays, "metrics": metrics, "gates": gates, "slot": slot, "npz_path": npz_path}


def _load_and_validate_cases(
    report: ValidationReport,
    *,
    summary: Mapping[str, Any],
    identity: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[int, dict[str, Any]]:
    schedule = contracts["schedule"]
    slots = schedule["slots"]
    index = summary.get("case_metadata_index", [])
    if not report.require(isinstance(index, list) and len(index) == 144, "SUMMARY_CASE_INDEX_NOT_144"):
        return {}
    report.require([row.get("slot_index") for row in index] == list(range(144)), "SUMMARY_CASE_INDEX_ORDER")
    ordinal_map = _expected_execution_ordinals(schedule)
    expected_source_base = {
        "local_source_inventory_sha256": identity.get("local_source_inventory_sha256"),
        "contract_bundle_sha256": identity.get("contract_bundle_sha256"),
        "signed_preregistration_anchor_set_sha256": identity.get("signed_preregistration_anchor_set_sha256"),
        "registered_slots_sha256": schedule.get("slots_sha256"),
    }
    records: dict[int, dict[str, Any]] = {}
    acquisition_certificates: list[str] = []
    clearance_certificates: list[str] = []
    expected_raw_filenames: set[str] = set()
    executed_count = 0
    na_count = 0
    for slot, row in zip(slots, index):
        slot_index = int(slot["slot_index"])
        if not report.require(
            isinstance(row, Mapping), "SUMMARY_CASE_INDEX_ROW_NOT_OBJECT", slot_index,
        ):
            continue
        exact_key_set(
            report,
            row,
            {
                "slot_index", "case_id", "execution_status",
                "metadata_path", "metadata_sha256",
            },
            "SUMMARY_CASE_INDEX_ROW_FIELDS",
        )
        report.require(row.get("case_id") == slot.get("case_id"), "SUMMARY_CASE_INDEX_ID", slot_index)
        stem = "".join(character if character.isalnum() else "_" for character in str(slot["case_id"]))
        expected_metadata = EVIDENCE_ROOT / "raw_cases" / f"{slot_index:03d}__{stem}.json"
        metadata_path = resolve_declared(PROJECT_ROOT, PHASE_ROOT, row.get("metadata_path"))
        report.require(
            metadata_path == expected_metadata.resolve(),
            "CASE_METADATA_PATH_NOT_REGISTERED_SLOT_PATH",
            {"slot_index": slot_index, "declared": metadata_path.as_posix(), "expected": expected_metadata.resolve().as_posix()},
        )
        expected_raw_filenames.add(expected_metadata.name)
        verify_file_record(report, path=metadata_path, expected_bytes=metadata_path.stat().st_size if metadata_path.is_file() else -1, expected_sha256=row.get("metadata_sha256"), code=f"CASE_METADATA_{slot_index:03d}")
        metadata = _load_strict(report, metadata_path, f"CASE_METADATA_{slot_index:03d}")
        if metadata is None:
            continue
        _require_canonical_json(report, metadata_path, metadata, f"CASE_METADATA_{slot_index:03d}")
        exact_key_set(report, metadata, CASE_REQUIRED_FIELDS | {"execution_ordinal", "numeric_payload_sha256", "npz_arrays"}, "CASE_METADATA_REQUIRED_FIELDS")
        _reject_displaced_governance_claims(
            report, metadata,
            required_false=contracts["governance"].get("required_false", {}),
            required_null_names=contracts["governance"].get(
                "required_null_physical_inputs", [],
            ),
            code="CASE_METADATA_GOVERNANCE_INJECTION",
        )
        report.require(metadata.get("schema") == "SIM13_V4B4G_CASE_METADATA_V1", "CASE_METADATA_SCHEMA", slot_index)
        report.require(
            row.get("execution_status") == metadata.get("execution_status"),
            "SUMMARY_CASE_INDEX_STATUS_MISMATCH",
            slot_index,
        )
        for key in ("slot_index", "case_id", "lane_id", "arm"):
            report.require(metadata.get(key) == slot.get(key), "CASE_METADATA_SLOT_MISMATCH", {"slot_index": slot_index, "field": key})
        report.require(metadata.get("registered_slot") == slot, "CASE_REGISTERED_SLOT_BYTES_MISMATCH", slot_index)
        report.require(metadata.get("execution_ordinal") == ordinal_map.get(str(slot["case_id"])), "CASE_EXECUTION_ORDINAL", slot_index)
        report.require(metadata.get("claim_boundary") == CLAIM_BOUNDARY, "CASE_CLAIM_BOUNDARY", slot_index)
        source_hashes = dict(expected_source_base)
        source_hashes["slot_canonical_sha256"] = canonical_sha256(slot)
        report.require(metadata.get("source_hashes") == source_hashes, "CASE_SOURCE_HASHES", slot_index)
        event = metadata.get("event_provenance", {})
        exact_key_set(report, event, EVENT_REQUIRED_FIELDS, "CASE_EVENT_REQUIRED_FIELDS")
        gates = _gate_by_id(report, metadata, str(slot["case_id"]))
        expected_npz = EVIDENCE_ROOT / "raw_cases" / f"{slot_index:03d}__{stem}.npz"
        status = metadata.get("execution_status")
        if status == "NOT_EVALUATED_NO_A1_SUCCESS":
            na_count += 1
            validated_na = report.guard(
                f"CASE_NA_VALIDATION_EXCEPTION_{slot_index:03d}",
                lambda: (
                    _validate_na_a2(report, metadata, gates, expected_npz), True,
                )[1],
            )
            if validated_na is not None:
                records[slot_index] = {"metadata": metadata, "arrays": None, "metrics": {}, "gates": gates, "slot": slot, "npz_path": None}
        elif status == "EXECUTED_FRESH_REGISTERED_SLOT":
            executed_count += 1
            expected_raw_filenames.add(expected_npz.name)
            declared_npz = resolve_declared(PROJECT_ROOT, PHASE_ROOT, metadata.get("npz_path"))
            report.require(declared_npz == expected_npz.resolve(), "CASE_NPZ_PATH", {"slot_index": slot_index, "declared": declared_npz.as_posix(), "expected": expected_npz.resolve().as_posix()})
            validated_case = report.guard(
                f"CASE_VALIDATION_EXCEPTION_{slot_index:03d}",
                lambda: _validate_executed_case(
                    report, metadata=metadata, gates=gates, npz_path=declared_npz,
                    contracts=contracts, slot=slot,
                    event_templates=identity.get("_b4e_event_templates", {}),
                    acquisition_templates=identity.get("_b4e_acquisition_templates", {}),
                ),
            )
            if isinstance(validated_case, dict):
                records[slot_index] = validated_case
            acquisition_certificates.append(str(event.get("acquisition_certificate_sha256")))
            clearance_certificates.append(str(event.get("clearance_certificate_sha256")))
        else:
            report.require(False, "CASE_EXECUTION_STATUS", {"slot_index": slot_index, "status": status})
    report.require(sorted(records) == list(range(144)), "CASE_RECORD_SET_INCOMPLETE")
    raw_root = EVIDENCE_ROOT / "raw_cases"
    actual_raw_filenames = (
        {path.name for path in raw_root.iterdir() if path.is_file()}
        if raw_root.is_dir() else set()
    )
    report.require(
        actual_raw_filenames == expected_raw_filenames,
        "CASE_RAW_DIRECTORY_EXACT_INVENTORY",
        {
            "missing": sorted(expected_raw_filenames - actual_raw_filenames),
            "extra": sorted(actual_raw_filenames - expected_raw_filenames),
        },
    )
    report.require(executed_count == summary.get("executed_slot_count"), "SUMMARY_EXECUTED_COUNT", {"computed": executed_count, "reported": summary.get("executed_slot_count")})
    report.require(na_count == summary.get("a2_not_evaluated_slot_count"), "SUMMARY_A2_NA_COUNT", {"computed": na_count, "reported": summary.get("a2_not_evaluated_slot_count")})
    report.require((executed_count, na_count) in {(144, 0), (120, 24)}, "CASE_EXECUTED_NA_PARTITION", {"executed": executed_count, "na": na_count})
    report.require(len(set(acquisition_certificates)) == executed_count, "CASE_ACQUISITION_CERTIFICATES_NOT_UNIQUE")
    report.require(len(set(clearance_certificates)) == executed_count, "CASE_CLEARANCE_CERTIFICATES_NOT_UNIQUE")
    report.observations["case_shards"] = {
        "logical_slot_count": 144, "executed_slot_count": executed_count,
        "a2_not_evaluated_slot_count": na_count,
        "fresh_unique_acquisition_certificates": len(set(acquisition_certificates)),
    }
    return records


def _stable_quaternion_geodesic_max(
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    """Return a fail-closed, sign-invariant maximum quaternion geodesic.

    The chord/``atan2`` form remains well conditioned near zero, unlike the
    mathematically equivalent dot/``acos`` form.  This is an independent
    validator implementation: it deliberately does not call the execution
    runner's quaternion routine.
    """

    try:
        left_array = np.asarray(left, dtype=float)
        right_array = np.asarray(right, dtype=float)
    except (TypeError, ValueError, OverflowError):
        return math.inf
    if (
        left_array.ndim != 2
        or right_array.ndim != 2
        or left_array.shape != right_array.shape
        or left_array.shape[1:] != (4,)
        or left_array.shape[0] == 0
        or not bool(np.all(np.isfinite(left_array)))
        or not bool(np.all(np.isfinite(right_array)))
    ):
        return math.inf
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        left_norm = np.linalg.norm(left_array, axis=1)
        right_norm = np.linalg.norm(right_array, axis=1)
        norms_valid = bool(
            np.all(np.isfinite(left_norm))
            and np.all(np.isfinite(right_norm))
            and np.all(np.abs(left_norm - 1.0) <= 1.0e-12)
            and np.all(np.abs(right_norm - 1.0) <= 1.0e-12)
        )
        if not norms_valid:
            return math.inf
        left_unit = left_array / left_norm[:, None]
        right_unit = right_array / right_norm[:, None]
        dots = np.sum(left_unit * right_unit, axis=1)
        right_aligned = np.where(dots[:, None] < 0.0, -right_unit, right_unit)
        difference_norm = np.linalg.norm(left_unit - right_aligned, axis=1)
        sum_norm = np.linalg.norm(left_unit + right_aligned, axis=1)
        theta = 4.0 * np.arctan2(difference_norm, sum_norm)
    if not bool(np.all(np.isfinite(theta))):
        return math.inf
    return float(np.max(theta))


def _a0_channel_maxima(
    raw: Mapping[str, np.ndarray],
    parent: Mapping[str, np.ndarray],
    mask: np.ndarray,
) -> dict[str, float]:
    """Independently compute the exact ten frozen A0 comparison channels."""

    state = raw["service_state_29"][mask]
    raw_quaternion = state[:, 3:7]
    parent_quaternion = parent["service_quaternion_wxyz"]
    quaternion_error = _stable_quaternion_geodesic_max(
        raw_quaternion, parent_quaternion,
    )
    return {
        "service_position_m": float(np.max(np.abs(state[:, 0:3] - parent["service_position_m"]))),
        "service_quaternion_geodesic_rad": quaternion_error,
        "R_joint_coordinates_rad": float(np.max(np.abs(state[:, 7:13] - parent["R_joint_coordinates_rad"]))),
        "P_joint_coordinates_m": float(np.max(np.abs(state[:, 13:15] - parent["P_joint_coordinates_m"]))),
        "base_linear_m_s": float(np.max(np.abs(state[:, 15:18] - parent["base_linear_m_s"]))),
        "base_angular_rad_s": float(np.max(np.abs(state[:, 18:21] - parent["base_angular_rad_s"]))),
        "R_joint_rad_s": float(np.max(np.abs(state[:, 21:27] - parent["R_joint_rad_s"]))),
        "P_joint_m_s": float(np.max(np.abs(state[:, 27:29] - parent["P_joint_m_s"]))),
        "left_right_gap_m": float(max(
            np.max(np.abs(raw["left_gap_m"][mask] - parent["left_gap_m"])),
            np.max(np.abs(raw["right_gap_m"][mask] - parent["right_gap_m"])),
        )),
        "left_right_gap_rate_m_s": float(max(
            np.max(np.abs(raw["left_gap_rate_m_s"][mask] - parent["left_gap_rate_m_s"])),
            np.max(np.abs(raw["right_gap_rate_m_s"][mask] - parent["right_gap_rate_m_s"])),
        )),
    }


def _validate_a0(
    report: ValidationReport,
    summary: Mapping[str, Any],
    records: Mapping[int, Mapping[str, Any]],
    schedule: Mapping[str, Any],
    parent_manifest: Mapping[str, Any],
    immutable_b4e_traces: Mapping[str, Mapping[str, np.ndarray]],
    event_templates: Mapping[str, Mapping[str, Any]],
    acquisition_templates: Mapping[str, Mapping[str, Any]],
) -> None:
    channel_names = (
        "service_position_m", "service_quaternion_geodesic_rad",
        "R_joint_coordinates_rad", "P_joint_coordinates_m",
        "base_linear_m_s", "base_angular_rad_s", "R_joint_rad_s",
        "P_joint_m_s", "left_right_gap_m", "left_right_gap_rate_m_s",
    )
    traces = parent_manifest.get("traces", [])
    by_lane = {
        str(row.get("lane_id")): row for row in traces if isinstance(row, dict)
    }
    report.require(set(by_lane) == set(LANES) and len(traces) == 6, "A0_PARENT_LANE_SET")
    parent_arrays: dict[str, dict[str, np.ndarray]] = {}
    parent_paths: set[Path] = set()
    parent_certificates: list[Any] = []
    for lane in LANES:
        row = by_lane.get(lane, {})
        method, step = LANE_DEFINITIONS[lane]
        required = {
            "lane_id", "method", "step_s", "fresh_b3_reconstruction",
            "fresh_b4e_reference_propagation", "acquisition_time_s",
            "common_absolute_end_time_s", "event_certificate_sha256",
            "acquisition_certificate_payload",
            "fixed_template_comparison_audit",
            "npz_path", "npz_bytes", "npz_sha256", "numeric_payload_sha256",
        }
        exact_key_set(report, row, required, "A0_PARENT_TRACE_FIELDS")
        report.require(row.get("method") == method and row.get("step_s") == step, "A0_PARENT_METHOD_STEP", lane)
        report.require(row.get("fresh_b3_reconstruction") is True and row.get("fresh_b4e_reference_propagation") is True, "A0_PARENT_FRESHNESS", lane)
        report.require(row.get("common_absolute_end_time_s") == 0.08, "A0_PARENT_COMMON_END", lane)
        parent_payload = row.get("acquisition_certificate_payload")
        report.require(
            isinstance(parent_payload, Mapping)
            and set(parent_payload) == {"lane_id", "case_id", "event", "acquisition"},
            "A0_PARENT_ACQUISITION_CERTIFICATE_PAYLOAD_FIELDS",
            lane,
        )
        parent_case_id = (
            str(parent_payload.get("case_id"))
            if isinstance(parent_payload, Mapping) else ""
        )
        report.require(
            isinstance(parent_payload, Mapping)
            and parent_payload.get("lane_id") == lane
            and bool(parent_case_id),
            "A0_PARENT_ACQUISITION_CERTIFICATE_ID_BINDING",
            lane,
        )
        parent_certificate = report.guard(
            "A0_PARENT_ACQUISITION_CERTIFICATE_CANONICALIZATION",
            lambda: canonical_sha256(parent_payload),
        ) if isinstance(parent_payload, Mapping) else None
        report.require(
            is_sha256(row.get("event_certificate_sha256"))
            and parent_certificate == row.get("event_certificate_sha256"),
            "A0_PARENT_EVENT_CERTIFICATE",
            lane,
        )
        expected_audit = (
            _validate_fresh_certificate_template_comparison(
                report,
                payload=parent_payload,
                lane=lane,
                case_id=parent_case_id,
                event_templates=event_templates,
                acquisition_templates=acquisition_templates,
                code_prefix="A0_PARENT",
            )
            if isinstance(parent_payload, Mapping) else None
        )
        report.require(
            expected_audit is not None
            and row.get("fixed_template_comparison_audit") == expected_audit,
            "A0_PARENT_FIXED_TEMPLATE_COMPARISON_AUDIT",
            lane,
        )
        parent_certificates.append(row.get("event_certificate_sha256"))
        path = resolve_declared(PROJECT_ROOT, PHASE_ROOT, row.get("npz_path"))
        report.require(path not in parent_paths, "A0_PARENT_TRACE_PATH_REUSED", lane)
        parent_paths.add(path)
        verify_file_record(report, path=path, expected_bytes=row.get("npz_bytes"), expected_sha256=row.get("npz_sha256"), code=f"A0_PARENT_{lane}")
        arrays = load_npz_strict(report, path, code=f"A0_PARENT_{lane}")
        if arrays is None:
            continue
        report.require(set(arrays) == A0_PARENT_ARRAYS, "A0_PARENT_ARRAY_INVENTORY", {"lane": lane, "actual": sorted(arrays)})
        for name, value in arrays.items():
            report.require(value.dtype.str == "<f8", "A0_PARENT_LITTLE_ENDIAN_FLOAT64", {"lane": lane, "array": name, "dtype": value.dtype.str})
        report.require(array_payload_sha256(arrays) == row.get("numeric_payload_sha256"), "A0_PARENT_NUMERIC_PAYLOAD_HASH", lane)
        if not A0_PARENT_ARRAYS.issubset(arrays):
            continue
        parent_time = arrays["time_s"]
        count = len(parent_time)
        _require_shape(report, parent_time, (None,), "A0_PARENT_TIME_SHAPE")
        report.require(count >= 2 and bool(np.all(np.diff(parent_time) > 0.0)), "A0_PARENT_TIME_ORDER", lane)
        report.require(_same_float(parent_time[0], row.get("acquisition_time_s")), "A0_PARENT_ACQUISITION_TIME", lane)
        report.require(_same_float(parent_time[-1], 0.08, atol=1.0e-14), "A0_PARENT_TERMINAL_TIME", lane)
        if count >= 2:
            report.require(bool(np.allclose(np.diff(parent_time), step, rtol=0.0, atol=1.0e-14)), "A0_PARENT_FROZEN_TIME_GRID", lane)
        for name, width in (
            ("service_position_m", 3), ("service_quaternion_wxyz", 4),
            ("R_joint_coordinates_rad", 6), ("P_joint_coordinates_m", 2),
            ("base_linear_m_s", 3), ("base_angular_rad_s", 3),
            ("R_joint_rad_s", 6), ("P_joint_m_s", 2),
        ):
            _require_shape(report, arrays[name], (count, width), f"A0_PARENT_{name.upper()}_SHAPE")
        for name in ("left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s"):
            _require_shape(report, arrays[name], (count,), f"A0_PARENT_{name.upper()}_SHAPE")
        quaternion_norm = np.linalg.norm(arrays["service_quaternion_wxyz"], axis=1)
        report.require(bool(np.all(np.abs(quaternion_norm - 1.0) <= 1.0e-12)), "A0_PARENT_QUATERNION_NORM", lane)
        immutable = immutable_b4e_traces.get(lane)
        if report.require(isinstance(immutable, Mapping), "A0_IMMUTABLE_B4E_TRACE_MISSING", lane):
            assert isinstance(immutable, Mapping)
            report.require(set(immutable) == A0_PARENT_ARRAYS, "A0_IMMUTABLE_B4E_TRACE_ARRAY_SET", lane)
            for name in A0_PARENT_ARRAYS:
                if name in immutable:
                    report.require(
                        bool(np.array_equal(arrays[name], immutable[name])),
                        "A0_PARENT_NOT_IMMUTABLE_B4E_ACTIVE_TRACE",
                        {"lane": lane, "array": name},
                    )
        parent_arrays[lane] = arrays
    report.require(len(set(parent_certificates)) == 6, "A0_PARENT_EVENT_CERTIFICATES_NOT_UNIQUE")
    aggregate = summary.get("a0", {})
    report.require(aggregate.get("a0_slot_count") == 12, "A0_AGGREGATE_COUNT")
    report.require(aggregate.get("all_exact_replay_and_pre_post_payload_pairs_pass") is True, "A0_AGGREGATE_NOT_PASS")
    lane_pairs = aggregate.get("lane_pairs", [])
    report.require(len(lane_pairs) == 6, "A0_LANE_PAIR_COUNT")
    for lane in LANES:
        slots = [slot for slot in schedule["slots"] if slot["lane_id"] == lane and slot["arm"] == "A0"]
        pre_slot = next(slot for slot in slots if slot["sentinel_position"] == "PRE")
        post_slot = next(slot for slot in slots if slot["sentinel_position"] == "POST")
        pre = records[int(pre_slot["slot_index"])]
        post = records[int(post_slot["slot_index"])]
        pre_meta = pre["metadata"]
        post_meta = post["metadata"]
        report.require(pre_meta.get("numeric_payload_sha256") == post_meta.get("numeric_payload_sha256"), "A0_PRE_POST_NUMERIC_HASH", lane)
        pre_arrays = pre.get("arrays")
        post_arrays = post.get("arrays")
        if pre_arrays is not None and post_arrays is not None:
            report.require(set(pre_arrays) == set(post_arrays), "A0_PRE_POST_ARRAY_SET", lane)
            for name in set(pre_arrays) & set(post_arrays):
                report.require(bool(np.array_equal(pre_arrays[name], post_arrays[name])), "A0_PRE_POST_ARRAY_BYTES", {"lane": lane, "array": name})
        independent_by_case: dict[str, dict[str, float]] = {}
        parent = parent_arrays.get(lane)
        for item in (pre, post):
            metadata = item["metadata"]
            raw = item.get("arrays")
            comparison = metadata.get("responses", {}).get("a0_replay_comparison", {})
            maxima = comparison.get("channel_maxima", {})
            tolerances = comparison.get("native_absolute_tolerances", {})
            report.require(comparison.get("common_end_time_s") == 0.08, "A0_COMMON_INTERVAL", metadata.get("case_id"))
            report.require(comparison.get("Q_and_W_exact_zero") is True, "A0_COMPARISON_Q_W", metadata.get("case_id"))
            report.require(set(maxima) == set(channel_names) and set(tolerances) == set(channel_names), "A0_FROZEN_TEN_CHANNEL_SET", metadata.get("case_id"))
            report.require(all(tolerances.get(name) == 1.0e-12 for name in channel_names), "A0_FROZEN_TOLERANCE_EACH_1E12", metadata.get("case_id"))
            if raw is None or parent is None:
                continue
            raw_time = raw["time_s"]
            mask = raw_time <= 0.08 + 1.0e-12
            common_time = raw_time[mask]
            report.require(bool(np.array_equal(common_time, parent["time_s"])), "A0_PARENT_TIME_GRID_MISMATCH", metadata.get("case_id"))
            if not np.array_equal(common_time, parent["time_s"]):
                continue
            computed = _a0_channel_maxima(raw, parent, mask)
            independent_by_case[str(metadata.get("case_id"))] = computed
            report.require(maxima == computed, "A0_METADATA_MAXIMA_NOT_RAW_RECOMPUTATION", metadata.get("case_id"))
            for name, value in computed.items():
                report.require(value <= 1.0e-12, "A0_RAW_PARENT_CHANNEL_EXCEEDS_1E12", {"case_id": metadata.get("case_id"), "channel": name, "value": value})
            report.require(bool(np.all(raw["command_Q_14"] == 0.0) and np.all(raw["signed_W_act_J"] == 0.0)), "A0_RAW_Q_W_NOT_EXACT_ZERO", metadata.get("case_id"))
        pair = next((item for item in lane_pairs if item.get("lane_id") == lane), None)
        report.require(pair is not None and pair.get("passed") is True, "A0_SUMMARY_PAIR", lane)
        if pair is not None:
            report.require(pair.get("pre_case_id") == pre_meta.get("case_id") and pair.get("post_case_id") == post_meta.get("case_id"), "A0_SUMMARY_PAIR_IDS", lane)
            report.require(pair.get("parent_trace_sha256") == by_lane.get(lane, {}).get("npz_sha256"), "A0_SUMMARY_PARENT_TRACE_BINDING", lane)


def _reference_records(records: Mapping[int, Mapping[str, Any]]) -> dict[tuple[str, float, float], Mapping[str, Any]]:
    result: dict[tuple[str, float, float], Mapping[str, Any]] = {}
    for item in records.values():
        metadata = item["metadata"]
        if metadata.get("arm") != "A1":
            continue
        slot = item.get("slot", {})
        result[(str(slot.get("lane_id")), float(slot.get("alpha")), float(slot.get("command_duration_s")))] = item
    return result


def _compute_reference_eligibility(
    report: ValidationReport,
    records: Mapping[int, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key = _reference_records(records)
    gates: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for alpha in ALPHAS:
        for duration in DURATIONS:
            rk = by_key.get(("RK4_REFERENCE", alpha, duration))
            mid = by_key.get(("MIDPOINT_REFERENCE", alpha, duration))
            if not report.require(rk is not None and mid is not None, "G12_REFERENCE_PAIR_MISSING", {"alpha": alpha, "duration": duration}):
                continue
            assert rk is not None and mid is not None
            rk_meta = rk["metadata"]; mid_meta = mid["metadata"]
            rk_metrics = rk.get("metrics", {}); mid_metrics = mid.get("metrics", {})
            level_id = f"ALPHA_{str(alpha).replace('.', 'P')}__TCMD_MS_{round(duration * 1000)}"
            geometry = bool(rk_metrics.get("g16_predicate") and mid_metrics.get("g16_predicate"))
            rk_finite = rk_metrics.get("g09_predicate") is True
            mid_finite = mid_metrics.get("g09_predicate") is True
            if not geometry:
                gates.append({"gate_id": G12, "evaluation_status": "NOT_APPLICABLE", "scientific_predicate": None, "applicability_reason": "REFERENCE_CASE_GEOMETRY_DOMAIN_EXIT", "detail": {"level_id": level_id, "alpha": alpha, "T_cmd_s": duration}})
                continue
            if not rk_finite and not mid_finite:
                gates.append({"gate_id": G12, "evaluation_status": "NOT_APPLICABLE", "scientific_predicate": None, "applicability_reason": "NO_PAIRED_FINITE_REFERENCE_EVENT", "detail": {"level_id": level_id, "alpha": alpha, "T_cmd_s": duration, "rk4_finite": rk_finite, "midpoint_finite": mid_finite}})
                continue
            if rk_finite is not mid_finite:
                gates.append({
                    "gate_id": G12,
                    "evaluation_status": "PASS",
                    "scientific_predicate": False,
                    "applicability_reason": "EXACTLY_ONE_REFERENCE_FINITE_EVENT_EVALUATED_NEGATIVE_OUTCOME",
                    "detail": {
                        "level_id": level_id, "alpha": alpha,
                        "T_cmd_s": duration,
                        "rk4_finite": rk_finite,
                        "midpoint_finite": mid_finite,
                        "eligible": False,
                        "one_reference_success_only_rule_applied": True,
                    },
                })
                continue
            acquisition_delta = abs(float(rk_meta["event_provenance"]["acquisition_time_s"]) - float(mid_meta["event_provenance"]["acquisition_time_s"]))
            removal_delta = abs(float(rk_metrics["clearance"]["removal_time_s"]) - float(mid_metrics["clearance"]["removal_time_s"]))
            rk_work = float(rk["arrays"]["signed_W_act_J"][-1])
            mid_work = float(mid["arrays"]["signed_W_act_J"][-1])
            work_tolerance = max(1.0e-10, 0.001 * max(abs(rk_work), abs(mid_work)))
            work_delta = abs(rk_work - mid_work)
            provenance = bool(
                rk_meta["event_provenance"]["fresh_b3_reconstruction"]
                and mid_meta["event_provenance"]["fresh_b3_reconstruction"]
                and rk_meta["event_provenance"]["lane_id"] == "RK4_REFERENCE"
                and mid_meta["event_provenance"]["lane_id"] == "MIDPOINT_REFERENCE"
                and rk_meta["event_provenance"]["acquisition_certificate_sha256"] != mid_meta["event_provenance"]["acquisition_certificate_sha256"]
                and rk_meta["event_provenance"]["clearance_certificate_sha256"] != mid_meta["event_provenance"]["clearance_certificate_sha256"]
            )
            predicate = bool(
                acquisition_delta <= 0.00025 and removal_delta <= 0.00025
                and work_delta <= work_tolerance and provenance
                and rk_metrics.get("g11_pass") is True
                and mid_metrics.get("g11_pass") is True
                and rk_metrics.get("independent_integrity_pass") is True
                and mid_metrics.get("independent_integrity_pass") is True
            )
            detail = {
                "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                "acquisition_time_difference_s": acquisition_delta,
                "removal_time_difference_s": removal_delta,
                "event_time_tolerance_s": 0.00025,
                "signed_work_difference_J": work_delta,
                "signed_work_tolerance_J": work_tolerance,
                "lane_specific_fresh_provenance_pass": provenance,
                "rk4_reference_case_id": rk_meta["case_id"],
                "midpoint_reference_case_id": mid_meta["case_id"],
            }
            gates.append({"gate_id": G12, "evaluation_status": "PASS", "scientific_predicate": predicate, "applicability_reason": "PAIRED_FINITE_REFERENCE_EVENTS_EVALUATED", "detail": detail})
            if predicate:
                eligible.append({
                    "level_id": level_id, "alpha": alpha, "command_duration_s": duration,
                    "case_abs_work_J": max(abs(rk_work), abs(mid_work)),
                    "rk4_reference_case_id": rk_meta["case_id"],
                    "midpoint_reference_case_id": mid_meta["case_id"],
                })
    eligible.sort(key=lambda row: (row["alpha"], row["command_duration_s"], row["case_abs_work_J"], row["level_id"]))
    return gates, eligible


def _validate_g12_and_selector(
    report: ValidationReport,
    summary: Mapping[str, Any],
    records: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any] | None:
    expected_gates, eligible = _compute_reference_eligibility(report, records)
    reported_gates = summary.get("cross_reference_gate_records_18", [])
    report.require(len(reported_gates) == 18, "G12_RECORD_COUNT")
    report.require(reported_gates == expected_gates, "G12_RECORDS_NOT_INDEPENDENT_RECOMPUTATION")
    report.require(summary.get("reference_eligible_levels") == eligible, "G12_ELIGIBLE_LEVEL_LIST")
    selected = eligible[0] if eligible else None
    selector = summary.get("selector", {})
    expected_status = "REACHABLE_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN" if selected else "NOT_OBSERVED_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
    report.require(selector.get("status") == expected_status, "SELECTOR_STATUS")
    report.require(selector.get("eligible_level_count") == len(eligible), "SELECTOR_ELIGIBLE_COUNT")
    report.require(selector.get("eligible_levels_in_frozen_sort_order") == eligible, "SELECTOR_ELIGIBLE_ORDER")
    report.require(selector.get("selected_parent_level") == selected, "SELECTOR_SELECTED_PARENT")
    report.require(selector.get("reported_label") == "lowest_tested_reachable_alpha_in_registered_discrete_grid", "SELECTOR_LABEL")
    report.require(selector.get("lowest_tested_reachable_alpha_in_registered_discrete_grid") == (None if selected is None else selected["alpha"]), "SELECTOR_LOWEST_TESTED_ALPHA")
    report.require(selector.get("selected_tested_duration_s") == (None if selected is None else selected["command_duration_s"]), "SELECTOR_TESTED_DURATION")
    for field in ("minimum_required_force_or_work_claimed", "continuous_threshold_or_interpolation_claimed", "global_unreachability_claimed"):
        report.require(selector.get(field) is False, f"SELECTOR_FORBIDDEN_CLAIM_{field}")
    report.observations["selector"] = {
        "eligible_level_count": len(eligible),
        "lowest_tested_reachable_alpha": None if selected is None else selected["alpha"],
        "selected_tested_duration_s": None if selected is None else selected["command_duration_s"],
        "minimum_force_claim": False,
    }
    return selected


def _mirror_metrics(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_arrays = left["arrays"]
    right_arrays = right["arrays"]
    left_meta = left["metadata"]
    right_meta = right["metadata"]
    left_relative = left_arrays["time_s"] - float(left_meta["event_provenance"]["acquisition_time_s"])
    right_relative = right_arrays["time_s"] - float(right_meta["event_provenance"]["acquisition_time_s"])
    grids_equal = bool(np.array_equal(left_relative, right_relative))
    common = left_relative if grids_equal else np.intersect1d(left_relative, right_relative, assume_unique=True)
    missing = not grids_equal
    if missing:
        gap = gap_rate = work = math.inf
    else:
        gap = float(max(
            np.max(np.abs(left_arrays["left_gap_m"] - right_arrays["right_gap_m"])),
            np.max(np.abs(left_arrays["right_gap_m"] - right_arrays["left_gap_m"])),
        ))
        gap_rate = float(max(
            np.max(np.abs(left_arrays["left_gap_rate_m_s"] - right_arrays["right_gap_rate_m_s"])),
            np.max(np.abs(left_arrays["right_gap_rate_m_s"] - right_arrays["left_gap_rate_m_s"])),
        ))
        work = abs(float(left_arrays["signed_W_act_J"][-1]) - float(right_arrays["signed_W_act_J"][-1]))
    parity = bool(
        left_meta["responses"]["finite_removal_event"]
        == right_meta["responses"]["finite_removal_event"]
        and left_meta["terminal_status"] == right_meta["terminal_status"]
    )
    predicate = bool(not missing and gap <= 1.0e-9 and gap_rate <= 1.0e-9 and work <= 1.0e-9 and parity)
    return {
        "scientific_predicate": predicate, "common_relative_sample_count": int(len(common)),
        "left_relative_sample_count": int(len(left_relative)),
        "right_relative_sample_count": int(len(right_relative)),
        "full_relative_grid_equal": grids_equal,
        "missing_exact_common_grid": missing,
        "direct_left_right_swapped_gap_residual_m": None if not math.isfinite(gap) else gap,
        "direct_left_right_swapped_gap_rate_residual_m_s": None if not math.isfinite(gap_rate) else gap_rate,
        "signed_work_terminal_common_interval_residual_J": None if not math.isfinite(work) else work,
        "outcome_parity": parity,
    }


def _validate_a2(
    report: ValidationReport,
    summary: Mapping[str, Any],
    records: Mapping[int, Mapping[str, Any]],
    selected: Mapping[str, Any] | None,
) -> None:
    pair_records = summary.get("a2_mirror_pair_gate_records_12", [])
    report.require(len(pair_records) == 12, "A2_PAIR_RECORD_COUNT")
    a2 = [item for item in records.values() if item["metadata"].get("arm") == "A2"]
    report.require(len(a2) == 24, "A2_SLOT_COUNT")
    report.require(all((item["metadata"].get("execution_status") == "EXECUTED_FRESH_REGISTERED_SLOT") == (selected is not None) for item in a2), "A2_CONDITIONAL_EXECUTION")
    pairs = (("RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR"), ("RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR"))
    offset = 0
    predicates: list[bool] = []
    for lane in LANES:
        lane_items = [item for item in a2 if item["metadata"]["lane_id"] == lane]
        report.require(len(lane_items) == 4, "A2_LANE_SLOT_COUNT", lane)
        for right_variant, left_variant in pairs:
            reported = pair_records[offset] if offset < len(pair_records) else {}
            offset += 1
            report.require(reported.get("gate_id") == G13, "A2_PAIR_GATE_ID", {"lane": lane, "pair": right_variant})
            if selected is None:
                report.require(reported.get("evaluation_status") == "NOT_APPLICABLE" and reported.get("scientific_predicate") is None and reported.get("applicability_reason") == "NO_REFERENCE_ELIGIBLE_A1_PARENT", "A2_PAIR_NO_PARENT_NA", {"lane": lane, "pair": right_variant})
                continue
            right = next(item for item in lane_items if right_variant in item["metadata"]["case_id"])
            left = next(item for item in lane_items if left_variant in item["metadata"]["case_id"])
            report.require(right["metadata"]["command_parameters"].get("selected_parent_level") == selected, "A2_RIGHT_PARENT", right["metadata"]["case_id"])
            report.require(left["metadata"]["command_parameters"].get("selected_parent_level") == selected, "A2_LEFT_PARENT", left["metadata"]["case_id"])
            metrics = _mirror_metrics(left, right)
            detail = reported.get("detail", {})
            report.require(reported.get("evaluation_status") == "PASS", "A2_PAIR_NOT_EVALUATED", {"lane": lane, "pair": right_variant})
            report.require(reported.get("scientific_predicate") is metrics["scientific_predicate"], "A2_PAIR_PREDICATE", {"lane": lane, "pair": right_variant})
            for field, value in metrics.items():
                report.require(detail.get(field) == value, "A2_PAIR_RAW_METRIC", {"lane": lane, "pair": right_variant, "field": field, "computed": value, "reported": detail.get(field)})
            report.require(detail.get("baseline_correction_or_fitted_transform_used") is False, "A2_BASELINE_CORRECTION_USED", {"lane": lane, "pair": right_variant})
            predicates.append(metrics["scientific_predicate"])
    global_records = {record.get("gate_id"): record for record in summary.get("global_gate_records", [])}
    global_g13 = global_records.get(G13, {})
    if selected is None:
        report.require(global_g13.get("evaluation_status") == "NOT_APPLICABLE" and global_g13.get("applicability_reason") == "NO_REFERENCE_ELIGIBLE_A1_PARENT", "A2_GLOBAL_NO_PARENT_NA")
    else:
        report.require(global_g13.get("evaluation_status") == "PASS" and global_g13.get("scientific_predicate") is all(predicates), "A2_GLOBAL_PREDICATE")


def _validate_global_and_governance(
    report: ValidationReport,
    summary: Mapping[str, Any],
    contracts: Mapping[str, Mapping[str, Any]],
) -> None:
    governance_contract = contracts["governance"]
    governance = summary.get("governance", {})
    required_false = governance_contract.get("required_false", {})
    required_null_names = governance_contract.get("required_null_physical_inputs", [])
    required_null = {name: None for name in required_null_names}
    _reject_displaced_governance_claims(
        report, summary, required_false=required_false,
        required_null_names=required_null_names,
        code="SUMMARY_GOVERNANCE_INJECTION",
    )
    report.require(governance.get("required_false") == required_false, "SUMMARY_REQUIRED_FALSE_MAP")
    report.require(governance.get("required_null_physical_inputs") == required_null, "SUMMARY_REQUIRED_NULL_MAP")
    report.require(governance.get("formal_sim13_v2_state_unchanged") == governance_contract.get("formal_sim13_v2_state_unchanged"), "SUMMARY_FORMAL_STATE")
    report.require(governance.get("memory") == {"memory_gate_applicable": False, "memory_gate_passed": False, "owner_override_used": False, "classification": "DIAGNOSTIC_ONLY"}, "SUMMARY_MEMORY_RECORD")
    report.require(all(value is False for value in governance.get("required_false", {}).values()), "SUMMARY_REQUIRED_FALSE_HAS_TRUE")
    report.require(all(value is None for value in governance.get("required_null_physical_inputs", {}).values()), "SUMMARY_REQUIRED_NULL_HAS_VALUE")
    report.require(summary.get("case_integrity_failures") == [], "SUMMARY_CASE_INTEGRITY_FAILURES")
    report.require(summary.get("registered_domain_execution_integrity_pass") is True, "SUMMARY_EXECUTION_INTEGRITY_NOT_PASS")
    hook = summary.get("negative_control_hook", {})
    report.require(hook.get("status") == "NOT_EXECUTED_BY_CAMPAIGN_ORCHESTRATOR", "SUMMARY_MUTATION_HOOK_STATUS")
    report.require(hook.get("registered_parent_count") == 22 and hook.get("registered_subvariant_count") == 65, "SUMMARY_MUTATION_HOOK_COUNTS")
    report.require(hook.get("campaign_execution_credit_from_this_hook") is False, "SUMMARY_MUTATION_HOOK_CREDIT")
    global_records = summary.get("global_gate_records", [])
    report.require(isinstance(global_records, list) and len(global_records) == 6, "GLOBAL_GATE_RECORD_COUNT")
    valid_global_records = [
        record for record in global_records if isinstance(record, Mapping)
    ] if isinstance(global_records, list) else []
    report.require(
        len(valid_global_records) == 6,
        "GLOBAL_GATE_RECORD_NOT_OBJECT",
    )
    by_id = {record.get("gate_id"): record for record in valid_global_records}
    expected_ids = {
        "B4F-G01-SOURCE-AND-PARENT-RECURSIVE", G02, G13,
        "B4F-G14-REGISTERED-DOMAIN-NO-POST-HOC-EXTENSION",
        "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
        "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY",
    }
    report.require(set(by_id) == expected_ids, "GLOBAL_GATE_ID_SET", sorted(by_id))
    for gate_id, record in by_id.items():
        exact_key_set(report, record, ("gate_id", "evaluation_status", "scientific_predicate", "applicability_reason", "detail"), "GLOBAL_GATE_FIELDS")
        report.require(record.get("evaluation_status") != "FAIL", "GLOBAL_GATE_FAIL", gate_id)
    for gate_id in expected_ids - {G13}:
        report.require(by_id.get(gate_id, {}).get("evaluation_status") == "PASS" and by_id.get(gate_id, {}).get("scientific_predicate") is True, "GLOBAL_GATE_REQUIRED_TRUE", gate_id)
    g15_detail = by_id.get("B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS", {}).get("detail", {})
    report.require(g15_detail.get("required_false") == required_false, "GLOBAL_G15_REQUIRED_FALSE")
    report.require(g15_detail.get("required_null_physical_inputs") == required_null, "GLOBAL_G15_REQUIRED_NULL")
    report.require(g15_detail.get("memory") == contracts["run_spec"].get("memory"), "GLOBAL_G15_MEMORY")
    report.require(by_id.get("B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY", {}).get("detail") == summary.get("selector"), "GLOBAL_G17_SELECTOR_BINDING")
    forbidden_names = set(governance_contract.get("forbidden_local_artifacts", [])[1:])
    forbidden_candidates = report.guard(
        "B4G_FORBIDDEN_LOCAL_ARTIFACT_PREPRUNED_ENUMERATION",
        lambda: _walk_phase_files_prepruned(
            PHASE_ROOT, exclude_source_derived_trees=False,
        ),
    )
    forbidden = [] if forbidden_candidates is None else [
        path.relative_to(PHASE_ROOT).as_posix()
        for path in forbidden_candidates
        if path.is_file()
        and (path.suffix.lower() == ".urdf" or path.name in forbidden_names)
    ]
    report.require(not forbidden, "B4G_FORBIDDEN_LOCAL_ARTIFACT", forbidden)


def _validate_mutations(
    report: ValidationReport,
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any] | None:
    path = PHASE_ROOT / "b4g_mutation_execution" / "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json"
    evidence = _load_strict(report, path, "NEGATIVE_CONTROL_EVIDENCE")
    if evidence is None:
        return None
    _require_canonical_json(report, path, evidence, "NEGATIVE_CONTROL_EVIDENCE")
    exact_key_set(
        report,
        evidence,
        {
            "schema", "scope", "required_parent_ids",
            "subvariant_counts_by_parent", "source_binding",
            "finite_event_harness_precondition", "counts",
            "parent_summaries", "receipts",
            "all_65_subvariants_unique_hit_and_killed", "final", "audited",
            "validator_pass_claimed", "dictionary_flag_only_mutation_used",
            "campaign_or_scientific_credit_from_mutations",
            "campaign_negative_control_hook_closed",
            "executor_bundle_generation_complete", "claim_boundary",
            "mutation_credit_boundary", "capabilities", "memory",
        },
        "NEGATIVE_CONTROL_EVIDENCE_FIELDS",
    )
    report.require(evidence.get("schema") == "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1", "NEGATIVE_CONTROL_SCHEMA")
    report.require(evidence.get("scope") == "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH_MUTATIONS_ONLY", "NEGATIVE_CONTROL_SCOPE")
    report.require(
        evidence.get("claim_boundary") == CLAIM_BOUNDARY,
        "NEGATIVE_CONTROL_CLAIM_BOUNDARY",
    )
    report.require(evidence.get("final") is False and evidence.get("audited") is False and evidence.get("validator_pass_claimed") is False, "NEGATIVE_CONTROL_PREVALIDATION_STATUS")
    report.require(evidence.get("dictionary_flag_only_mutation_used") is False, "NEGATIVE_CONTROL_DICTIONARY_FLAG_ONLY")
    report.require(evidence.get("campaign_or_scientific_credit_from_mutations") is False, "NEGATIVE_CONTROL_CREDIT_BOUNDARY")
    report.require(
        evidence.get("campaign_negative_control_hook_closed") is False
        and evidence.get("executor_bundle_generation_complete") is True,
        "NEGATIVE_CONTROL_EXECUTOR_NOT_AUDITED_FINAL",
    )
    report.require(
        evidence.get("mutation_credit_boundary") == MUTATION_REPLAY_CLAIM_BOUNDARY,
        "NEGATIVE_CONTROL_MUTATION_CREDIT_BOUNDARY",
    )
    report.require(evidence.get("memory") == {"memory_gate_applicable": False, "memory_gate_passed": False, "owner_override_used": False, "classification": "DIAGNOSTIC_ONLY"}, "NEGATIVE_CONTROL_MEMORY")
    report.require(
        evidence.get("capabilities") == {
            "registered_negative_controls_executed": True,
            "physical_release_implemented": False,
            "current_system_bound": False,
            "formal_nc19_credit": False,
            "owner_authorized": False,
            "production_ready": False,
            "release_authorized": False,
            "next_stage_authorized": False,
        },
        "NEGATIVE_CONTROL_CAPABILITIES",
    )
    spec = contracts["mutations"]
    _reject_displaced_governance_claims(
        report,
        evidence,
        required_false=contracts["governance"].get("required_false", {}),
        required_null_names=contracts["governance"].get(
            "required_null_physical_inputs", [],
        ),
        code="NEGATIVE_CONTROL_GOVERNANCE_INJECTION",
    )
    variants = spec.get("variants", [])
    expected_by_parent = {item["id"].split("_", 1)[0]: item for item in variants}
    expected_full_id = {item["id"].split("_", 1)[0]: item["id"] for item in variants}
    expected_gate = {item["id"].split("_", 1)[0]: item["expected_gate"] for item in variants}
    expected_count = {item["id"].split("_", 1)[0]: int(item["count"]) for item in variants}
    report.require(
        evidence.get("required_parent_ids") == spec.get("required_parent_ids"),
        "NEGATIVE_CONTROL_REQUIRED_PARENT_IDS",
    )
    report.require(
        evidence.get("subvariant_counts_by_parent")
        == spec.get("subvariant_counts_by_parent"),
        "NEGATIVE_CONTROL_SUBVARIANT_COUNTS_BY_PARENT",
    )
    counts = evidence.get("counts", {})
    report.require(
        isinstance(counts, Mapping)
        and set(counts) == {
            "required_parent_count", "total_subvariants",
            "executed_subvariants", "killed_subvariants",
            "unique_subvariants", "executed", "killed", "unique",
        },
        "NEGATIVE_CONTROL_COUNT_FIELDS",
    )
    report.require(counts.get("required_parent_count") == 22, "NEGATIVE_CONTROL_PARENT_COUNT")
    report.require(counts.get("total_subvariants") == 65, "NEGATIVE_CONTROL_TOTAL_COUNT")
    executed_value = counts.get("executed_subvariants", counts.get("executed"))
    killed_value = counts.get("killed_subvariants", counts.get("killed"))
    unique_value = counts.get("unique_subvariants", counts.get("unique"))
    report.require(executed_value == 65 and killed_value == 65 and unique_value == 65, "NEGATIVE_CONTROL_EXECUTED_KILLED_UNIQUE", counts)
    receipts = evidence.get("receipts", [])
    report.require(isinstance(receipts, list) and len(receipts) == 65, "NEGATIVE_CONTROL_RECEIPT_COUNT")
    validator_generated_fields = {
        "actual_failed_gate", "nominal_gate_sha256", "mutant_gate_sha256",
    }
    required_fields = (set(spec.get("each_receipt_requires", [])) - validator_generated_fields) | {
        "receipt_id", "parent_id", "subvariant_index", "mutation_id", "target",
        "execution_detail", "base_artifact", "mutant_artifact", "patch_artifact", "replay",
    }
    receipt_ids: list[Any] = []
    base_hashes: list[Any] = []
    mutant_hashes: list[Any] = []
    patch_hashes: list[Any] = []
    parent_counts: Counter[str] = Counter()
    parent_indices: dict[str, set[int]] = defaultdict(set)
    generated_replays: list[dict[str, Any]] = []
    finite_derivations: list[dict[str, Any]] = []
    finite_artifact_bindings: list[tuple[str, int, str]] = []
    supplemental_inventory_records: list[dict[str, Any]] = []
    nc07_derived_work: float | None = None
    campaign_source_path = EVIDENCE_ROOT / "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json"
    campaign_source_sha = sha256_file(campaign_source_path) if campaign_source_path.is_file() else None
    campaign_path = RESULTS_ROOT / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    campaign_summary = _load_strict(
        report, campaign_path, "NEGATIVE_CONTROL_CAMPAIGN_SUMMARY_BINDING",
    )
    official_metadata_bindings: set[tuple[Path, str]] = set()
    if isinstance(campaign_summary, Mapping):
        for row in campaign_summary.get("case_metadata_index", []):
            if isinstance(row, Mapping):
                official_metadata_bindings.add((
                    resolve_declared(
                        PROJECT_ROOT, PHASE_ROOT, row.get("metadata_path"),
                    ),
                    str(row.get("metadata_sha256")),
                ))
    mutation_executor_path = PHASE_ROOT / "run_phase_b4g_mutation_audit.py"
    validator_path = Path(__file__).resolve()
    required_false = contracts["governance"].get("required_false", {})
    required_null_names = contracts["governance"].get("required_null_physical_inputs", [])
    for index, receipt in enumerate(receipts if isinstance(receipts, list) else []):
        if not report.require(
            isinstance(receipt, Mapping),
            "NEGATIVE_CONTROL_RECEIPT_NOT_OBJECT", index,
        ):
            continue
        exact_key_set(report, receipt, required_fields, "NEGATIVE_CONTROL_RECEIPT_FIELDS")
        report.require(
            not (validator_generated_fields & set(receipt)),
            "NEGATIVE_CONTROL_EXECUTOR_FORGED_VALIDATOR_RESULT_FIELDS",
            {"index": index, "forbidden": sorted(validator_generated_fields & set(receipt))},
        )
        parent = str(receipt.get("parent_id"))
        normalized = parent
        receipt_id = str(receipt.get("receipt_id"))
        report.require(normalized in expected_by_parent, "NEGATIVE_CONTROL_PARENT_ID", {"index": index, "parent": parent})
        if normalized not in expected_by_parent:
            continue
        expected_variant_id = expected_full_id[normalized]
        gate_id = expected_gate[normalized]
        subvariant = receipt.get("subvariant_index")
        report.require(isinstance(subvariant, int) and not isinstance(subvariant, bool) and 1 <= subvariant <= expected_count[normalized], "NEGATIVE_CONTROL_SUBVARIANT_INDEX", receipt_id)
        report.require(receipt.get("mutation_id") == expected_variant_id, "NEGATIVE_CONTROL_MUTATION_ID", receipt_id)
        report.require(receipt_id.startswith(f"{normalized}__SV{int(subvariant) if isinstance(subvariant, int) else -1:02d}__"), "NEGATIVE_CONTROL_RECEIPT_ID_CANONICAL", receipt_id)
        report.require(receipt.get("expected_gate") == gate_id, "NEGATIVE_CONTROL_EXPECTED_GATE", receipt_id)

        artifacts: dict[str, tuple[Path, dict[str, Any]] | None] = {}
        for field, code in (("base_artifact", "BASE"), ("mutant_artifact", "MUTANT"), ("patch_artifact", "PATCH")):
            record = receipt.get(field, {})
            if isinstance(record, Mapping):
                report.require(record.get("media_type") == "application/json", f"NEGATIVE_CONTROL_{code}_MEDIA_TYPE", receipt_id)
                report.require(record.get("replay_type") == REPLAY_TYPE_BY_PARENT[normalized], f"NEGATIVE_CONTROL_{code}_REPLAY_TYPE", receipt_id)
                artifacts[field] = load_artifact_record(
                    report, record, project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
                    code=f"NEGATIVE_CONTROL_{code}_{index:02d}",
                )
            else:
                report.require(False, f"NEGATIVE_CONTROL_{code}_RECORD", receipt_id)
                artifacts[field] = None
        if any(value is None for value in artifacts.values()):
            continue
        base_path, base = artifacts["base_artifact"]  # type: ignore[misc]
        mutant_path, mutant = artifacts["mutant_artifact"]  # type: ignore[misc]
        patch_path, patch = artifacts["patch_artifact"]  # type: ignore[misc]
        replay_type = REPLAY_TYPE_BY_PARENT[normalized]
        report.require(base_path != mutant_path and base_path != patch_path and mutant_path != patch_path, "NEGATIVE_CONTROL_ARTIFACT_PATH_ALIAS", receipt_id)
        expected_receipt_root = (
            PHASE_ROOT / "b4g_mutation_execution" / "artifacts" / receipt_id
        ).resolve()
        report.require(
            base_path == expected_receipt_root / "base.json"
            and mutant_path == expected_receipt_root / "mutant.json"
            and patch_path == expected_receipt_root / "patch.json",
            "NEGATIVE_CONTROL_ARTIFACT_FORMAL_PATH_BINDING",
            receipt_id,
        )
        patch_binding_pass = True
        patch_binding_pass &= report.require(patch.get("schema") == "SIM13_V4B4G_MUTATION_PATCH_V1" and patch.get("format") == "RFC6902_JSON_V1_RESTRICTED", "NEGATIVE_CONTROL_PATCH_SCHEMA", receipt_id)
        patch_binding_pass &= report.require(patch.get("receipt_id") == receipt_id, "NEGATIVE_CONTROL_PATCH_RECEIPT", receipt_id)
        patch_binding_pass &= report.require(patch.get("target") == receipt.get("target"), "NEGATIVE_CONTROL_PATCH_TARGET", receipt_id)
        patch_binding_pass &= report.require(patch.get("base_sha256") == sha256_file(base_path), "NEGATIVE_CONTROL_PATCH_BASE_HASH", receipt_id)
        patch_binding_pass &= report.require(patch.get("mutant_sha256") == sha256_file(mutant_path), "NEGATIVE_CONTROL_PATCH_MUTANT_HASH", receipt_id)
        patched = report.guard(f"NEGATIVE_CONTROL_PATCH_APPLY_{index:02d}", lambda: apply_restricted_patch(base, patch))
        if patched is None:
            continue
        patch_replay_pass = report.require(patched == mutant and canonical_bytes(patched) + b"\n" == mutant_path.read_bytes(), "NEGATIVE_CONTROL_PATCH_REPLAY_NOT_MUTANT_BYTES", receipt_id)
        semantic_pass = report.guard(
            f"NEGATIVE_CONTROL_PATCH_SEMANTICS_REPLAY_{index:02d}",
            lambda: validate_patch_semantics(
                parent_id=normalized,
                subvariant_index=int(subvariant) if isinstance(subvariant, int) else -1,
                target=receipt.get("target"),
                patch=patch,
                base_payload=base.get("payload", {}),
                mutation_spec=spec,
                frozen_q_ref=float(contracts["reference"]["individual_finger_reference_force_N"]),
            ),
        )
        semantic_pass = report.require(
            semantic_pass is True,
            "NEGATIVE_CONTROL_PATCH_SEMANTICS_NOT_PREREGISTERED",
            receipt_id,
        )
        bundle_validity: list[bool] = []
        for bundle, bundle_path, suffix in ((base, base_path, "BASE"), (mutant, mutant_path, "MUTANT")):
            bundle_valid = validate_bundle(
                report, bundle, bundle_path=bundle_path, receipt_id=receipt_id,
                parent_id=normalized, gate_id=gate_id, replay_type=replay_type,
                project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            )
            bundle_valid &= report.require(bundle.get("mutation_id") == expected_variant_id, f"NEGATIVE_CONTROL_{suffix}_MUTATION_ID", receipt_id)
            provenance = bundle.get("execution_provenance", {})
            producer = resolve_declared(PROJECT_ROOT, PHASE_ROOT, provenance.get("producer_entrypoint_path")) if isinstance(provenance, Mapping) else Path()
            bundle_valid &= report.require(producer == mutation_executor_path.resolve(), f"NEGATIVE_CONTROL_{suffix}_PRODUCER_PATH", receipt_id)
            bundle_valid &= report.require(provenance.get("producer_entrypoint_sha256") == (sha256_file(mutation_executor_path) if mutation_executor_path.is_file() else None), f"NEGATIVE_CONTROL_{suffix}_PRODUCER_HASH", receipt_id)
            bundle_valid &= report.require(provenance.get("source_manifest_sha256") == campaign_source_sha, f"NEGATIVE_CONTROL_{suffix}_SOURCE_MANIFEST_HASH", receipt_id)
            bundle_validity.append(bool(bundle_valid))
        immutable_bundle_fields = set(base) - {"payload"}
        common_bundle_pass = report.require(
            immutable_bundle_fields == set(mutant) - {"payload"}
            and all(base.get(field) == mutant.get(field) for field in immutable_bundle_fields),
            "NEGATIVE_CONTROL_BASE_MUTANT_COMMON_FIELDS_DRIFT",
            receipt_id,
        )
        underlying_path_pass = True
        bound_parent_gate = next(
            (
                row for row in contracts["bindings"].get("sources", [])
                if isinstance(row, Mapping)
                and row.get("id") == "b4f_audited_gate"
            ),
            None,
        )
        exact_role_paths: dict[str, Path] = {
            "EXECUTION_SOURCE_MANIFEST": campaign_source_path,
            "FROZEN_CLASSIFIER_FIXTURE_CONTRACT": (
                CONTRACT_ROOT / CONTRACT_FILES["mutations"][0]
            ),
            "FROZEN_MUTATION_FALLBACK_CONTRACT": (
                CONTRACT_ROOT / CONTRACT_FILES["mutations"][0]
            ),
            "FROZEN_REGISTERED_SCHEDULE": (
                CONTRACT_ROOT / CONTRACT_FILES["schedule"][0]
            ),
            "FROZEN_GOVERNANCE_CONTRACT": (
                CONTRACT_ROOT / CONTRACT_FILES["governance"][0]
            ),
            "CAMPAIGN_SUMMARY": campaign_path,
            "EXECUTED_FINITE_HARNESS_RAW_OUTPUT": (
                PHASE_ROOT / "b4g_mutation_execution" / "underlying"
                / "B4G_MUTATION_FINITE_HARNESS__canonical_raw.json"
            ),
            "MUTANT_RAW_BYTES": (
                PHASE_ROOT / "b4g_mutation_execution" / "underlying"
                / "B4FNC01__mutated_bound_parent.bin"
            ),
        }
        if normalized == "B4FNC08" and isinstance(subvariant, int):
            side = "left" if subvariant == 1 else "right"
            exact_role_paths["MUTANT_DWELL_FORCE_TRACE"] = (
                PHASE_ROOT / "b4g_mutation_execution" / "underlying"
                / f"B4FNC08__{side}__mutant_dwell_force_trace.json"
            )
        if normalized == "B4FNC17":
            exact_role_paths["A2_DETECTOR_SIX_LANE_TRACE"] = (
                PHASE_ROOT / "b4g_mutation_execution" / "underlying"
                / "B4FNC17__a2_detector_six_lane_trace.json"
            )
        if normalized == "B4FNC21" and isinstance(subvariant, int):
            exact_role_paths["GEOMETRY_CLIP_EXTRAPOLATE_TRACE"] = (
                PHASE_ROOT / "b4g_mutation_execution" / "underlying"
                / f"B4FNC21__SV{subvariant:02d}__geometry_clip_extrapolate_trace.json"
            )
        if isinstance(bound_parent_gate, Mapping):
            exact_role_paths["BOUND_PARENT_SOURCE"] = _record_path(
                bound_parent_gate,
            )
        metadata_roles = {
            "REGISTERED_CASE_METADATA", "RK4_REFERENCE_CASE_METADATA",
            "MIDPOINT_REFERENCE_CASE_METADATA", "REGISTERED_A2_CASE_METADATA",
        }
        for row in base.get("artifact_records", []):
            if not isinstance(row, Mapping):
                underlying_path_pass = False
                continue
            role = str(row.get("role"))
            actual_path = resolve_declared(
                PROJECT_ROOT, PHASE_ROOT, row.get("path"),
            )
            if role in exact_role_paths:
                underlying_path_pass &= actual_path == exact_role_paths[role].resolve()
            elif role in metadata_roles:
                underlying_path_pass &= (
                    actual_path, str(row.get("sha256"))
                ) in official_metadata_bindings
            elif role == "REGISTERED_CASE_RAW_NPZ":
                # artifact_derivation independently binds this path to the
                # official metadata's npz_path/bytes/SHA and array inventory.
                pass
            else:
                underlying_path_pass = False
        underlying_path_pass &= report.require(
            underlying_path_pass,
            "NEGATIVE_CONTROL_UNDERLYING_ROLE_PATH_NOT_FORMAL",
            receipt_id,
        )
        artifact_derivation = report.guard(
            f"NEGATIVE_CONTROL_ARTIFACT_DERIVATION_{index:02d}",
            lambda: validate_nominal_payload_derivation(
                normalized,
                base.get("payload", {}),
                base.get("artifact_records", []),
                project_root=PROJECT_ROOT,
                phase_root=PHASE_ROOT,
                mutation_spec=spec,
                frozen_schedule=contracts["schedule"],
                governance=contracts["governance"],
                source_bindings=contracts["bindings"],
                frozen_q_ref=float(
                    contracts["reference"]["individual_finger_reference_force_N"]
                ),
                subvariant_index=(
                    int(subvariant) if isinstance(subvariant, int) else -1
                ),
            ),
        )
        artifact_derivation_pass = report.require(
            isinstance(artifact_derivation, ArtifactDerivationResult),
            "NEGATIVE_CONTROL_BASE_NOT_INDEPENDENTLY_ARTIFACT_DERIVED",
            receipt_id,
        )
        supplemental_replay = report.guard(
            f"NEGATIVE_CONTROL_SUPPLEMENTAL_REPLAY_{index:02d}",
            lambda: validate_supplemental_trace(
                normalized,
                int(subvariant) if isinstance(subvariant, int) else -1,
                base.get("artifact_records", []),
                project_root=PROJECT_ROOT,
                phase_root=PHASE_ROOT,
                mutation_spec=spec,
                frozen_schedule=contracts["schedule"],
                frozen_q_ref=float(
                    contracts["reference"]["individual_finger_reference_force_N"]
                ),
                base_payload=base.get("payload", {}),
            ),
        )
        supplemental_replay_pass = report.require(
            isinstance(supplemental_replay, SupplementalReplayResult),
            "NEGATIVE_CONTROL_REQUIRED_SUPPLEMENTAL_REPLAY_FAILED",
            receipt_id,
        )
        if (
            isinstance(supplemental_replay, SupplementalReplayResult)
            and supplemental_replay.role is not None
            and supplemental_replay.artifact_path is not None
        ):
            supplemental_path = Path(supplemental_replay.artifact_path).resolve()
            supplemental_inventory_records.append({
                "receipt_id": receipt_id,
                "role": supplemental_replay.role,
                "path": supplemental_path.relative_to(PROJECT_ROOT).as_posix(),
                "bytes": supplemental_path.stat().st_size,
                "sha256": supplemental_replay.artifact_sha256,
            })
        derived_mutant_pass = False
        derived_nominal_payload_sha: str | None = None
        derived_mutant_payload_sha: str | None = None
        artifact_derivation_diagnostics_sha: str | None = None
        if isinstance(artifact_derivation, ArtifactDerivationResult):
            derived_nominal_payload_sha = canonical_sha256(
                artifact_derivation.derived_payload,
            )
            derived_mutant_payload_sha = canonical_sha256(
                artifact_derivation.derived_mutant_payload,
            )
            artifact_derivation_diagnostics_sha = canonical_sha256(
                artifact_derivation.diagnostics,
            )
            # The patch/bundle replay alone only proves that *some* mutant was
            # produced from the submitted base.  Bind the submitted mutant to
            # the independently reconstructed, preregistered subvariant so a
            # coordinated base+patch+mutant forgery cannot choose an arbitrary
            # gate-killing amplitude or target.
            derived_mutant_pass = report.require(
                canonical_bytes(mutant.get("payload", {}))
                == canonical_bytes(artifact_derivation.derived_mutant_payload),
                "NEGATIVE_CONTROL_MUTANT_NOT_PREREGISTERED_ARTIFACT_DERIVED",
                receipt_id,
            )
            if normalized in {
                "B4FNC07", "B4FNC08", "B4FNC11", "B4FNC12",
                "B4FNC13", "B4FNC14",
            }:
                finite_derivations.append(dict(artifact_derivation.diagnostics))
                finite_rows = [
                    row for row in base.get("artifact_records", [])
                    if isinstance(row, Mapping)
                    and row.get("role") == "EXECUTED_FINITE_HARNESS_RAW_OUTPUT"
                ]
                if len(finite_rows) == 1:
                    finite_artifact_bindings.append((
                        str(finite_rows[0].get("path")),
                        int(finite_rows[0].get("bytes", -1)),
                        str(finite_rows[0].get("sha256")),
                    ))
                else:
                    report.require(
                        False,
                        "NEGATIVE_CONTROL_FINITE_ARTIFACT_ROLE_COUNT",
                        receipt_id,
                    )
            if normalized == "B4FNC07":
                derived_work = artifact_derivation.derived_payload.get(
                    "W_before_removal_J",
                )
                if finite_number(derived_work):
                    nc07_derived_work = float(derived_work)
        base_pass = evaluate_payload(
            replay_type, gate_id, base.get("payload", {}),
            parent_id=normalized,
            frozen_schedule=contracts["schedule"],
            frozen_q_ref=float(contracts["reference"]["individual_finger_reference_force_N"]),
            mutation_spec=spec,
            required_false=required_false,
            required_null_names=required_null_names, project_root=PROJECT_ROOT,
            phase_root=PHASE_ROOT,
        )
        mutant_pass = evaluate_payload(
            replay_type, gate_id, mutant.get("payload", {}),
            parent_id=normalized,
            frozen_schedule=contracts["schedule"],
            frozen_q_ref=float(contracts["reference"]["individual_finger_reference_force_N"]),
            mutation_spec=spec,
            required_false=required_false,
            required_null_names=required_null_names, project_root=PROJECT_ROOT,
            phase_root=PHASE_ROOT,
        )
        nominal_record = independent_gate_record(gate_id, replay_type, base_pass)
        mutant_record = independent_gate_record(gate_id, replay_type, mutant_pass)
        nominal_gate_sha = canonical_sha256(nominal_record)
        mutant_gate_sha = canonical_sha256(mutant_record)
        real_path_hit = bool(
            patch_binding_pass and patch_replay_pass and semantic_pass
            and len(bundle_validity) == 2 and all(bundle_validity)
            and common_bundle_pass and underlying_path_pass
            and artifact_derivation_pass and derived_mutant_pass
            and supplemental_replay_pass
        )
        independent_killed = bool(real_path_hit and base_pass and not mutant_pass and mutant_record["failed_gate_ids"] == [gate_id])
        replay = receipt.get("replay", {})
        report.require(isinstance(replay, dict) and replay.get("schema") == "SIM13_V4B4G_RECEIPT_INDEPENDENT_REPLAY_BINDING_V1", "NEGATIVE_CONTROL_REPLAY_SCHEMA", receipt_id)
        if isinstance(replay, dict):
            report.require(
                set(replay) == {
                    "schema", "evaluator_id", "independent_validator_path",
                    "independent_validator_sha256",
                },
                "NEGATIVE_CONTROL_REPLAY_BINDING_FIELDS",
                receipt_id,
            )
            report.require(replay.get("evaluator_id") == f"B4G_VALIDATION::{replay_type}", "NEGATIVE_CONTROL_REPLAY_EVALUATOR", receipt_id)
            report.require(replay.get("independent_validator_path") == validator_path.relative_to(PROJECT_ROOT).as_posix(), "NEGATIVE_CONTROL_REPLAY_VALIDATOR_PATH", receipt_id)
            report.require(replay.get("independent_validator_sha256") == sha256_file(validator_path), "NEGATIVE_CONTROL_REPLAY_VALIDATOR_HASH", receipt_id)
        report.require(receipt.get("nominal_input_sha256") == sha256_file(base_path), "NEGATIVE_CONTROL_NOMINAL_INPUT_HASH", receipt_id)
        report.require(receipt.get("mutant_input_sha256") == sha256_file(mutant_path), "NEGATIVE_CONTROL_MUTANT_INPUT_HASH", receipt_id)
        report.require(receipt.get("real_path_hit") is real_path_hit and real_path_hit, "NEGATIVE_CONTROL_REAL_PATH_NOT_HIT", receipt_id)
        report.require(receipt.get("killed") is independent_killed and independent_killed, "NEGATIVE_CONTROL_NOT_INDEPENDENTLY_KILLED", receipt_id)
        detail = receipt.get("execution_detail", {})
        operations = patch.get("operations", [])
        report.require(isinstance(detail, dict) and detail.get("artifact_interchange_schema") == "SIM13_V4B4G_MUTATION_ARTIFACT_INTERCHANGE_V1" and detail.get("patch_operation_count") == len(operations), "NEGATIVE_CONTROL_EXECUTION_DETAIL_BINDING", receipt_id)
        receipt_ids.append(receipt.get("receipt_id"))
        base_hashes.append(sha256_file(base_path))
        mutant_hashes.append(sha256_file(mutant_path))
        patch_hashes.append(sha256_file(patch_path))
        parent_counts[normalized] += 1
        if isinstance(subvariant, int):
            parent_indices[normalized].add(subvariant)
        generated_replays.append({
            "receipt_id": receipt_id,
            "parent_id": normalized,
            "subvariant_index": subvariant,
            "nominal_input_sha256": sha256_file(base_path),
            "mutant_input_sha256": sha256_file(mutant_path),
            "real_path_hit": real_path_hit,
            "expected_gate": gate_id,
            "actual_failed_gate": gate_id if independent_killed else None,
            "nominal_gate_sha256": nominal_gate_sha,
            "mutant_gate_sha256": mutant_gate_sha,
            "nominal_gate_record": nominal_record,
            "mutant_gate_record": mutant_record,
            "artifact_derived_nominal_payload_sha256": derived_nominal_payload_sha,
            "artifact_derived_mutant_payload_sha256": derived_mutant_payload_sha,
            "artifact_derivation_diagnostics_sha256": artifact_derivation_diagnostics_sha,
            "supplemental_role": (
                supplemental_replay.role
                if isinstance(supplemental_replay, SupplementalReplayResult)
                else None
            ),
            "supplemental_artifact_sha256": (
                supplemental_replay.artifact_sha256
                if isinstance(supplemental_replay, SupplementalReplayResult)
                else None
            ),
            "supplemental_diagnostics_sha256": (
                canonical_sha256(supplemental_replay.diagnostics)
                if isinstance(supplemental_replay, SupplementalReplayResult)
                else None
            ),
            "killed": independent_killed,
            "independently_killed": independent_killed,
        })
    report.require(len(set(receipt_ids)) == 65, "NEGATIVE_CONTROL_RECEIPT_IDS_NOT_UNIQUE")
    report.require(len(set(mutant_hashes)) == 65, "NEGATIVE_CONTROL_MUTANT_INPUTS_NOT_UNIQUE")
    report.require(len(set(patch_hashes)) == 65, "NEGATIVE_CONTROL_PATCHES_NOT_UNIQUE")
    report.require(parent_counts == Counter(expected_count), "NEGATIVE_CONTROL_PARENT_DISTRIBUTION", dict(parent_counts))
    report.require(all(parent_indices[parent] == set(range(1, count + 1)) for parent, count in expected_count.items()), "NEGATIVE_CONTROL_SUBVARIANT_INDEX_COVERAGE", {key: sorted(value) for key, value in parent_indices.items()})
    summaries = evidence.get("parent_summaries", [])
    report.require(isinstance(summaries, list) and len(summaries) == 22, "NEGATIVE_CONTROL_PARENT_SUMMARY_COUNT")
    summary_parents: list[str] = []
    for item in summaries if isinstance(summaries, list) else []:
        if isinstance(item, Mapping):
            exact_key_set(
                report,
                item,
                {
                    "parent_id", "expected_gate", "expected_count",
                    "executed_count", "killed_count", "passed",
                },
                "NEGATIVE_CONTROL_PARENT_SUMMARY_FIELDS",
            )
        parent = str(item.get("parent_id"))
        normalized = parent
        summary_parents.append(normalized)
        report.require(normalized in expected_by_parent, "NEGATIVE_CONTROL_SUMMARY_PARENT", parent)
        if normalized in expected_by_parent:
            count = expected_count[normalized]
            report.require(item.get("expected_gate") == expected_by_parent[normalized]["expected_gate"], "NEGATIVE_CONTROL_SUMMARY_GATE", parent)
            report.require(item.get("expected_count") == count and item.get("executed_count") == count and item.get("killed_count") == count, "NEGATIVE_CONTROL_SUMMARY_COUNTS", parent)
            report.require(item.get("passed") is True, "NEGATIVE_CONTROL_SUMMARY_NOT_PASS", parent)
    report.require(set(summary_parents) == set(expected_by_parent) and len(set(summary_parents)) == 22, "NEGATIVE_CONTROL_SUMMARY_PARENT_SET")
    report.require(
        len(finite_derivations) == 7,
        "MUTATION_FINITE_HARNESS_DERIVATION_COUNT",
        len(finite_derivations),
    )
    finite_diagnostic_hashes = {
        canonical_sha256(item) for item in finite_derivations
    }
    report.require(
        len(finite_diagnostic_hashes) == 1,
        "MUTATION_FINITE_HARNESS_DERIVATIONS_DISAGREE",
        sorted(finite_diagnostic_hashes),
    )
    report.require(
        len(finite_artifact_bindings) == 7
        and len(set(finite_artifact_bindings)) == 1,
        "MUTATION_FINITE_HARNESS_ARTIFACT_NOT_SINGLE_BYTE_IDENTITY",
        sorted(set(finite_artifact_bindings)),
    )
    finite_diagnostic = finite_derivations[0] if finite_derivations else {}
    abs_work = finite_diagnostic.get("abs_work_J")
    removal_time = finite_diagnostic.get("removal_time_s")
    expected_precondition = {
        "finite_event": True,
        "finite_removal_event": True,
        "synthetic_removal_executed": True,
        "removal_time_s": removal_time,
        "W_act_at_removal_J": nc07_derived_work,
        "abs_W_act_at_removal_J": abs_work,
        "abs_W_act_gt_1e_12_J": True,
        "post_release_passed": True,
        "passed": True,
        "a1_or_b3_main_trigger_credit": False,
        "physical_current_or_formal_credit": False,
    }
    precondition = evidence.get("finite_event_harness_precondition", {})
    report.require(
        precondition == expected_precondition,
        "MUTATION_FINITE_HARNESS_PRECONDITION_NOT_INDEPENDENTLY_DERIVED",
        {"expected": expected_precondition, "actual": precondition},
    )
    report.require(
        finite_number(abs_work) and float(abs_work) > 1.0e-12
        and finite_number(nc07_derived_work)
        and abs(float(nc07_derived_work)) == float(abs_work)
        and finite_number(removal_time),
        "MUTATION_FINITE_HARNESS_WORK_PRECONDITION",
        {"abs_work_J": abs_work, "signed_work_J": nc07_derived_work},
    )
    report.require(evidence.get("all_65_subvariants_unique_hit_and_killed") is True, "NEGATIVE_CONTROL_GLOBAL_NOT_PASS")
    binding = evidence.get("source_binding", {})
    report.require(isinstance(binding, dict), "NEGATIVE_CONTROL_SOURCE_BINDING_OBJECT")
    source_freeze = (
        campaign_summary.get("execution_source_freeze", {})
        if isinstance(campaign_summary, Mapping) else {}
    )
    freeze_terminal_path = Path(
        str(source_freeze.get("terminal_path", ""))
    ).resolve()
    expected_binding_paths = {
        "mutation_spec": CONTRACT_ROOT / CONTRACT_FILES["mutations"][0],
        "preregistration_gate": PREREGISTRATION_FILES["gate"][0],
        "preregistration_terminal": PREREGISTRATION_FILES["terminal"][0],
        "preregistration_source_manifest": PREREGISTRATION_FILES["source_manifest"][0],
        "campaign_summary": campaign_path,
        "execution_source_manifest": campaign_source_path,
        "execution_source_freeze_terminal": freeze_terminal_path,
        "mutation_executor": mutation_executor_path,
        "independent_validator": validator_path,
    }
    if isinstance(binding, dict):
        expected_binding_fields = set(expected_binding_paths) | {
            "execution_source_freeze_expected_terminal_sha256",
            "artifact_inventory", "all_required_files_byte_bound",
        }
        report.require(
            set(binding) == expected_binding_fields,
            "NEGATIVE_CONTROL_SOURCE_BINDING_KEYS",
            {
                "missing": sorted(expected_binding_fields - set(binding)),
                "extra": sorted(set(binding) - expected_binding_fields),
            },
        )
        for key, expected_path in expected_binding_paths.items():
            row = binding.get(key, {})
            if not isinstance(row, dict):
                report.require(False, f"NEGATIVE_CONTROL_SOURCE_BINDING_{key.upper()}_RECORD")
                continue
            exact_key_set(
                report, row, {"path", "bytes", "sha256"},
                f"NEGATIVE_CONTROL_SOURCE_BINDING_{key.upper()}_FIELDS",
            )
            actual_path = resolve_declared(PROJECT_ROOT, PHASE_ROOT, row.get("path"))
            report.require(actual_path == expected_path.resolve(), f"NEGATIVE_CONTROL_SOURCE_BINDING_{key.upper()}_PATH")
            verify_file_record(report, path=actual_path, expected_bytes=row.get("bytes"), expected_sha256=row.get("sha256"), code=f"NEGATIVE_CONTROL_SOURCE_BINDING_{key.upper()}")
        expected_freeze_terminal_sha = source_freeze.get(
            "expected_terminal_sha256",
            campaign_summary.get(
                "expected_execution_source_freeze_terminal_sha256",
            ) if isinstance(campaign_summary, Mapping) else None,
        )
        report.require(
            is_sha256(expected_freeze_terminal_sha)
            and binding.get("execution_source_freeze_expected_terminal_sha256")
            == expected_freeze_terminal_sha
            and isinstance(binding.get("execution_source_freeze_terminal"), Mapping)
            and binding["execution_source_freeze_terminal"].get("sha256")
            == expected_freeze_terminal_sha,
            "NEGATIVE_CONTROL_EXECUTION_SOURCE_FREEZE_TERMINAL_BINDING",
        )
        report.require(
            binding.get("all_required_files_byte_bound") is True,
            "NEGATIVE_CONTROL_ALL_REQUIRED_FILES_BOUND",
        )
        inventory = binding.get("artifact_inventory", {})
        expected_inventory = {
            "receipt_count": 65,
            "base_sha256s": sorted(base_hashes),
            "mutant_sha256s": sorted(mutant_hashes),
            "patch_sha256s": sorted(patch_hashes),
            "supplemental_role_records": sorted(
                supplemental_inventory_records,
                key=lambda item: (item["receipt_id"], item["role"]),
            ),
        }
        report.require(inventory == {**expected_inventory, "inventory_sha256": canonical_sha256(expected_inventory)}, "NEGATIVE_CONTROL_ARTIFACT_INVENTORY")
    report.observations["negative_controls"] = {
        "parent_count": 22, "subvariant_count": 65,
        "executed": executed_value, "killed": killed_value, "unique": unique_value,
        "finite_event_harness_abs_work_J": abs_work,
        "validator_generated_replay_count": len(generated_replays),
        "validator_generated_replays_sha256": canonical_sha256(generated_replays),
        "validator_generated_replays": generated_replays,
    }
    return evidence


def validate_b4g(*, mode: str = "full") -> ValidationReport:
    """Validate contracts, campaign, and optionally all negative controls.

    Modes:
      ``contracts`` validates frozen contracts, parent bindings and preregistration.
      ``campaign`` additionally validates all 144 logical slots and campaign summary.
      ``full`` additionally requires and validates all 65 mutation receipts.
    """

    report = ValidationReport(mode=mode)
    if mode not in {"contracts", "campaign", "full"}:
        report.require(False, "VALIDATION_MODE_INVALID", mode)
        return report
    _validate_attempt_state_markers(report, PHASE_ROOT)
    contracts = _validate_contracts_and_preregistration(report)
    if contracts is None or mode == "contracts":
        report.observations["final_or_audited_credit"] = False
        return report
    bundle = _load_campaign_bundle(report, contracts)
    if bundle is None:
        report.observations["final_or_audited_credit"] = False
        return report
    summary, identity = bundle
    records = _load_and_validate_cases(report, summary=summary, identity=identity, contracts=contracts)
    if len(records) == 144:
        _validate_a0(
            report, summary, records, contracts["schedule"],
            identity["_a0_parent_manifest"],
            identity.get("_b4e_active_trace_templates", {}),
            identity.get("_b4e_event_templates", {}),
            identity.get("_b4e_acquisition_templates", {}),
        )
        selected = _validate_g12_and_selector(report, summary, records)
        _validate_a2(report, summary, records, selected)
    _validate_global_and_governance(report, summary, contracts)
    if mode == "full":
        _validate_mutations(report, contracts)
    report.observations["final_or_audited_credit"] = False
    report.observations["physical_current_formal_owner_production_credit"] = False
    return report
