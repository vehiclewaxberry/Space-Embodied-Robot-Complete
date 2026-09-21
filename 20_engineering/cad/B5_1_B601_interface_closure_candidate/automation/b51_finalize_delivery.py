from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CANDIDATE_ROOT = Path(__file__).resolve().parents[1]
AUDIT_ROOT = CANDIDATE_ROOT / "00_AUDIT"
ARTICULATION_EVIDENCE_ROOT = (
    CANDIDATE_ROOT / "07_VERIFICATION" / "articulation"
)

CANONICAL_INPUT_LOCK = (
    AUDIT_ROOT / "B51_INPUT_LOCK_V2_CANONICAL.json"
)
REFERENCE_CONTAINMENT = (
    AUDIT_ROOT / "B51_NATIVE_REFERENCE_CONTAINMENT.json"
)
H10_AUDIT = (
    CANDIDATE_ROOT
    / "07_VERIFICATION"
    / "interface"
    / "B51_CANONICAL_INTERFACE_BREP_AUDIT.json"
)
PHASE_BC_GATE = (
    CANDIDATE_ROOT / "07_VERIFICATION" / "B51_PHASE_BC_GATE.json"
)
PACKAGING_DECISION = (
    CANDIDATE_ROOT
    / "01_REQUIREMENTS"
    / "B51_PACKAGING_ENVELOPE_DECISION.md"
)
INTERFACE_CONTROL_DRAWING = (
    CANDIDATE_ROOT
    / "01_REQUIREMENTS"
    / "B51_INTERFACE_CONTROL_DRAWING.md"
)
CLEARANCE_GATE = (
    CANDIDATE_ROOT
    / "05_CLEARANCE"
    / "B51_STATE_TRANSITION_GATE.json"
)
CLEARANCE_CURVES = (
    CANDIDATE_ROOT
    / "05_CLEARANCE"
    / "B51_CONTINUOUS_CLEARANCE_CURVES.csv"
)
INTERFERENCE_LEDGER = (
    CANDIDATE_ROOT
    / "02_INTERFACE"
    / "B51_INTERFERENCE_DISPOSITION_LEDGER.csv"
)
ACCEPTED_JOINT_CONTRACT = (
    CANDIDATE_ROOT
    / "00_BASELINE_DONORS"
    / "B5_0_ACCEPTED_CANDIDATE_FULL_COPY"
    / "01_KINEMATICS"
    / "accepted_joint_contract.csv"
)

T005_REPORT = (
    ARTICULATION_EVIDENCE_ROOT
    / "B51_SEGMENT_CHAIN_6R_20260728T005.json"
)
T003_REPORT = (
    ARTICULATION_EVIDENCE_ROOT
    / "B51_SEGMENT_CHAIN_6R_20260728T003.json"
)
T004_ABORT_RECEIPT = (
    ARTICULATION_EVIDENCE_ROOT
    / "B51_SEGMENT_CHAIN_6R_20260728T004_ABORTED.json"
)
OFF_AXIS_DIAGNOSTIC = (
    ARTICULATION_EVIDENCE_ROOT
    / "B51_T003_OFF_AXIS_STATE_DIAGNOSTIC.json"
)

STOWAGE_EVIDENCE = (
    CANDIDATE_ROOT / "04_STOWAGE" / "B51_STOWAGE_LOAD_PATH.md",
    CANDIDATE_ROOT
    / "04_STOWAGE"
    / "B51_CONTACT_PAD_AND_PRELOAD_TRADE.md",
    CANDIDATE_ROOT
    / "04_STOWAGE"
    / "B51_HDRM_FUNCTIONAL_INTERFACE.md",
    CANDIDATE_ROOT
    / "04_STOWAGE"
    / "B51_SADDLE_PRELIMINARY_STRUCTURAL_REPORT.md",
)
STRUCTURAL_EVIDENCE = (
    CANDIDATE_ROOT
    / "06_ANALYSIS"
    / "B51_INTERFACE_LOAD_CASE_REGISTER.yaml",
    CANDIDATE_ROOT
    / "06_ANALYSIS"
    / "B51_ADAPTER_PRELIMINARY_FEA.md",
    CANDIDATE_ROOT
    / "06_ANALYSIS"
    / "B51_STOW_SUPPORT_PRELIMINARY_FEA.md",
    CANDIDATE_ROOT
    / "06_ANALYSIS"
    / "B51_STRUCTURAL_HOLDS.md",
)

KINEMATIC_OUTPUT = (
    CANDIDATE_ROOT
    / "03_ARTICULATION"
    / "B51_CAD_URDF_KINEMATIC_CONSISTENCY.json"
)
MATE_OUTPUT = (
    CANDIDATE_ROOT
    / "03_ARTICULATION"
    / "B51_JOINT_MATE_REGISTER.csv"
)
RANDOM_OUTPUT = (
    CANDIDATE_ROOT
    / "03_ARTICULATION"
    / "B51_RANDOM_POSE_VERIFICATION.csv"
)
GATE_OUTPUT = (
    CANDIDATE_ROOT / "07_VERIFICATION" / "B51_GATE.json"
)
DELIVERY_GAP_OUTPUT = (
    CANDIDATE_ROOT
    / "08_DELIVERY"
    / "B51_DELIVERY_GAP_REGISTER.md"
)
CURRENT_STATUS_OUTPUT = CANDIDATE_ROOT / "B51_CURRENT_STATUS.md"

FINAL_VERDICT = "B51_REVISE_INTERFACE_COLLISION"
URDF_MASS_DECIMAL = "4.6955559493429862"
FK_ELEMENT_TOLERANCE = 2.0e-7
EXPECTED_CONFIGURATIONS = {
    "FREE_6R_ENGINEERING",
    "Q0_ACCEPTED",
    "STOW_V2_CANDIDATE_HOLD",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise RuntimeError(f"required source is missing: {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    require_file(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON root must be an object: {path}")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    require_file(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def relative(path: Path) -> str:
    return path.resolve().relative_to(CANDIDATE_ROOT.resolve()).as_posix()


def file_record(path: Path) -> dict[str, Any]:
    require_file(path)
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def csv_text(
    fieldnames: list[str], rows: list[dict[str, Any]]
) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_outputs_once(contents: dict[Path, str]) -> None:
    existing = [str(path) for path in contents if path.exists()]
    if existing:
        raise RuntimeError(
            "delivery outputs already exist; overwrite is forbidden: "
            + ", ".join(existing)
        )
    for path in contents:
        path.parent.mkdir(parents=True, exist_ok=True)
    for path, text in contents.items():
        with path.open(
            "x", encoding="utf-8", newline=""
        ) as handle:
            handle.write(text)


def readback_from(value: Any) -> dict[str, Any]:
    record = as_dict(value)
    nested = record.get("readback")
    if isinstance(nested, dict):
        return nested
    return record


def pose_summary(value: Any) -> dict[str, Any]:
    readback = readback_from(value)

    def frame_errors(key: str) -> dict[str, float | None]:
        frames = as_dict(readback.get(key))
        result: dict[str, float | None] = {}
        for name, item in frames.items():
            result[str(name)] = numeric(
                as_dict(item).get("max_abs_error")
            )
        return result

    return {
        "max_homogeneous_transform_element_abs": numeric(
            readback.get("max_abs_error")
        ),
        "segment_frame_max_abs_errors": frame_errors("segments"),
        "vendor_visual_frame_max_abs_errors": frame_errors(
            "vendor_visuals"
        ),
        "position_error_m": "UNKNOWN_NOT_SEPARATELY_REPORTED",
        "orientation_error_rad": "UNKNOWN_NOT_SEPARATELY_REPORTED",
        "reporting_limit": (
            "The source run reports maximum absolute homogeneous-transform "
            "element error, not separately decomposed position and "
            "orientation errors."
        ),
    }


def pose_passes(value: Any) -> bool:
    error = pose_summary(value)[
        "max_homogeneous_transform_element_abs"
    ]
    return (
        isinstance(error, float)
        and error <= FK_ELEMENT_TOLERANCE
    )


def choose_articulation_evidence() -> tuple[
    dict[str, Any], Path, list[Path], bool
]:
    diagnostic_paths = [
        path
        for path in (T003_REPORT, T004_ABORT_RECEIPT, OFF_AXIS_DIAGNOSTIC)
        if path.is_file()
    ]
    if T005_REPORT.is_file():
        return (
            load_json(T005_REPORT),
            T005_REPORT,
            [T005_REPORT, *diagnostic_paths],
            True,
        )
    fallback = [
        require_file(T003_REPORT),
        require_file(T004_ABORT_RECEIPT),
    ]
    return load_json(T003_REPORT), T003_REPORT, fallback, False


def evaluate_six_r(
    report: dict[str, Any], source_is_t005: bool
) -> dict[str, Any]:
    build = as_dict(report.get("build"))
    random_checks = [
        as_dict(item)
        for item in as_list(build.get("random_legal_pose_checks"))
    ]
    q0 = build.get("q0_readback")
    stow = build.get("stow_v2_pose_check")
    direction_summary = as_dict(
        build.get("joint_direction_summary")
    )
    off_axis = [
        as_dict(item)
        for item in as_list(build.get("off_axis_rejection_checks"))
    ]
    configuration = as_dict(build.get("configurations"))
    configuration_names = {
        str(item) for item in as_list(configuration.get("names"))
    }
    mates = [
        as_dict(item) for item in as_list(build.get("mates"))
    ]
    cold = as_dict(
        report.get("cold_process_reopen_verification")
    )
    same_process = as_dict(
        report.get("same_process_document_reopen")
    )

    checks: list[tuple[str, bool]] = [
        (
            "SOURCE_IS_IMMUTABLE_T005",
            source_is_t005,
        ),
        (
            "DECLARED_6R_PASS_STATUS",
            str(report.get("status", "")).startswith(
                "B51_NATIVE_6R_SEGMENT_CHAIN_PASS_"
            ),
        ),
        (
            "NO_SOURCE_EXCEPTION",
            not isinstance(report.get("exception"), dict),
        ),
        (
            "MAX_JOINTS_IS_6",
            report.get("max_joints") == 6,
        ),
        (
            "TWELVE_NATIVE_REVOLUTE_MATE_RECORDS",
            build.get("mate_count") == 12
            and len(mates) == 12
            and all(
                item.get("mate_object_returned") is True
                for item in mates
            ),
        ),
        (
            "Q0_TRANSFORM_READBACK_WITHIN_TOLERANCE",
            pose_passes(q0),
        ),
        (
            "STOW_V2_TRANSFORM_READBACK_WITHIN_TOLERANCE",
            pose_passes(stow),
        ),
        (
            "JOINT_DIRECTION_COVERAGE_PASS",
            direction_summary.get("coverage_pass") is True,
        ),
        (
            "SIX_OFF_AXIS_REJECTIONS_WITHIN_TOLERANCE",
            len(off_axis) == 6
            and all(
                pose_passes(item.get("readback_after_rejection"))
                for item in off_axis
            ),
        ),
        (
            "TWENTY_RANDOM_LEGAL_POSES_WITHIN_TOLERANCE",
            len(random_checks) == 20
            and all(
                len(as_list(item.get("q_rad"))) == 6
                and as_dict(item.get("limit_validation")).get(
                    "all_legal"
                )
                is True
                and pose_passes(item)
                for item in random_checks
            ),
        ),
        (
            "REQUIRED_CONFIGURATION_SET_PERSISTED",
            configuration_names == EXPECTED_CONFIGURATIONS
            and configuration.get("status")
            == "CONFIGURATION_POSE_PERSISTENCE_PASS_PRE_SAVE",
        ),
        (
            "SAME_PROCESS_REOPEN_PASS",
            "REOPEN_REPRODUCIBILITY_PASS"
            in str(same_process.get("status", "")),
        ),
        (
            "COLD_PROCESS_REOPEN_PASS",
            cold.get("cold_process_reopen") is True,
        ),
    ]
    failed = [name for name, passed in checks if not passed]
    random_errors = [
        pose_summary(item)[
            "max_homogeneous_transform_element_abs"
        ]
        for item in random_checks
    ]
    numeric_random_errors = [
        value for value in random_errors if isinstance(value, float)
    ]
    run_credit = not failed
    return {
        "source_run_id": report.get("run_id"),
        "source_status": report.get("status"),
        "source_is_t005": source_is_t005,
        "acceptance_tolerance": {
            "metric": "MAX_ABS_HOMOGENEOUS_TRANSFORM_ELEMENT",
            "value": FK_ELEMENT_TOLERANCE,
            "units": (
                "MIXED_ROTATION_MATRIX_COEFFICIENT_AND_TRANSLATION_METRES"
            ),
        },
        "checks": {
            name: "PASS" if passed else "HOLD"
            for name, passed in checks
        },
        "failed_checks": failed,
        "random_pose_requested": report.get(
            "random_samples_requested"
        ),
        "random_pose_records_available": len(random_checks),
        "random_pose_max_transform_element_error": (
            max(numeric_random_errors)
            if numeric_random_errors
            else None
        ),
        "native_6r_run_credit": (
            "PASS_WITH_SEPARATE_2P_AND_NATIVE_LIMIT_MATE_HOLDS"
            if run_credit
            else "NONE"
        ),
        "native_6r_evidence_pass": run_credit,
    }


def accepted_topology(
    joints: list[dict[str, str]]
) -> dict[str, int]:
    result = {"revolute": 0, "fixed": 0, "prismatic": 0}
    for row in joints:
        joint_type = row.get("type", "")
        if joint_type not in result:
            raise RuntimeError(
                f"unsupported accepted joint type: {joint_type}"
            )
        result[joint_type] += 1
    if result != {"revolute": 6, "fixed": 1, "prismatic": 2}:
        raise RuntimeError(
            f"accepted joint topology drifted: {result}"
        )
    if len(joints) != 9:
        raise RuntimeError(
            f"accepted joint contract row count {len(joints)} != 9"
        )
    return result


def aggregate_random_frame_errors(
    random_checks: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {
        "segments": {},
        "vendor_visuals": {},
    }
    for check in random_checks:
        readback = readback_from(check)
        for group in ("segments", "vendor_visuals"):
            for name, item in as_dict(
                readback.get(group)
            ).items():
                value = numeric(
                    as_dict(item).get("max_abs_error")
                )
                if value is not None:
                    current = result[group].get(str(name), 0.0)
                    result[group][str(name)] = max(current, value)
    return result


def build_mate_rows(
    joints: list[dict[str, str]],
    report: dict[str, Any],
    evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    build = as_dict(report.get("build"))
    native_mates = [
        as_dict(item) for item in as_list(build.get("mates"))
    ]
    native_limit_present = (
        as_dict(report.get("joint_limit_enforcement")).get(
            "native_limit_mates_present"
        )
        is True
    )
    six_r_pass = (
        evaluation["native_6r_evidence_pass"] is True
    )
    rows: list[dict[str, Any]] = []
    revolute_index = 0
    for joint in joints:
        joint_type = joint["type"]
        labels = ""
        if joint_type == "revolute":
            revolute_index += 1
            labels = "+".join(
                str(item.get("label", ""))
                for item in native_mates
                if str(item.get("label", "")).startswith(
                    f"J{revolute_index}_"
                )
            )
            implementation = (
                "NATIVE_REVOLUTE_MATE_EVIDENCE_PASS"
                if six_r_pass and labels
                else "HOLD_NO_ACCEPTED_NATIVE_6R_EVIDENCE"
            )
            gate_effect = (
                "6R_CREDIT_ONLY_G3_REMAINS_HOLD"
                if six_r_pass
                else "G3_HOLD"
            )
        elif joint_type == "fixed":
            implementation = (
                "URDF_FIXED_TOPOLOGY_RECORDED_NO_SEPARATE_"
                "B51_MATE_CREDIT"
            )
            gate_effect = "G7_TRACEABILITY_ONLY"
        else:
            implementation = (
                "NOT_IMPLEMENTED_G08_PARTITION_AND_ZERO_"
                "CALIBRATION_HOLD"
            )
            gate_effect = "G3_HOLD"
        rows.append(
            {
                "joint_name": joint["name"],
                "urdf_type": joint_type,
                "parent_link": joint["parent"],
                "child_link": joint["child"],
                "origin_xyz_m_source": joint[
                    "origin_xyz_m_source"
                ],
                "origin_rpy_rad_source": joint[
                    "origin_rpy_rad_source"
                ],
                "axis_source": joint["axis_source"],
                "limit_lower_source": joint[
                    "limit_lower_source"
                ],
                "limit_upper_source": joint[
                    "limit_upper_source"
                ],
                "native_mate_labels": labels,
                "native_implementation_status": implementation,
                "native_limit_mate_present": str(
                    native_limit_present
                ).lower(),
                "limit_enforcement_method": (
                    "PRE_SOLVER_Q_VECTOR_GATE"
                    if joint_type in ("revolute", "prismatic")
                    else "NOT_APPLICABLE"
                ),
                "evidence_run_id": report.get("run_id", ""),
                "gate_effect": gate_effect,
            }
        )
    return rows


def build_random_rows(
    report: dict[str, Any],
    evaluation: dict[str, Any],
) -> list[dict[str, Any]]:
    checks = [
        as_dict(item)
        for item in as_list(
            as_dict(report.get("build")).get(
                "random_legal_pose_checks"
            )
        )
    ]
    if not checks:
        return [
            {
                "source_run_id": report.get("run_id", ""),
                "sample_id": "NO_ACCEPTED_RANDOM_POSE_SET",
                "within_accepted_limits": "UNKNOWN_NOT_REPORTED",
                "transform_max_abs_error": "",
                "position_error_m": "UNKNOWN_NOT_SEPARATELY_REPORTED",
                "orientation_error_rad": (
                    "UNKNOWN_NOT_SEPARATELY_REPORTED"
                ),
                "status": "HOLD_NO_ACCEPTED_RANDOM_POSE_SET",
                "evidence_note": (
                    "No random-pose list is admitted from the selected "
                    "source report."
                ),
            }
        ]
    rows: list[dict[str, Any]] = []
    source_accepted = (
        evaluation["native_6r_evidence_pass"] is True
    )
    for index, item in enumerate(checks, start=1):
        q = as_list(item.get("q_rad"))
        summary = pose_summary(item)
        limits_ok = (
            as_dict(item.get("limit_validation")).get("all_legal")
            is True
        )
        row: dict[str, Any] = {
            "source_run_id": report.get("run_id", ""),
            "sample_id": item.get(
                "label", f"RANDOM_LEGAL_{index:02d}"
            ),
            "within_accepted_limits": str(limits_ok).lower(),
            "transform_max_abs_error": summary[
                "max_homogeneous_transform_element_abs"
            ],
            "position_error_m": "UNKNOWN_NOT_SEPARATELY_REPORTED",
            "orientation_error_rad": (
                "UNKNOWN_NOT_SEPARATELY_REPORTED"
            ),
            "status": (
                "PASS_NATIVE_6R_TRANSFORM_READBACK"
                if source_accepted
                else "HOLD_SOURCE_RUN_NOT_ACCEPTED"
            ),
            "evidence_note": (
                "Transform-element metric only; position and orientation "
                "were not separately reported by the source run."
            ),
        }
        for joint_index in range(6):
            row[f"q{joint_index + 1}_rad"] = (
                q[joint_index] if joint_index < len(q) else ""
            )
        rows.append(row)
    return rows


def validate_controlling_truth(
    canonical_lock: dict[str, Any],
    containment: dict[str, Any],
    h10: dict[str, Any],
    phase_bc: dict[str, Any],
    ledger_rows: list[dict[str, str]],
) -> dict[str, Any]:
    if (
        containment.get("status")
        != "B51_PHASE_A_NATIVE_REFERENCE_CONTAINMENT_PASS"
        or containment.get("g0")
        != "PASS_REFERENCE_CONTAINMENT_ONLY"
    ):
        raise RuntimeError(
            "canonical reference containment is not a G0 pass"
        )
    post = as_dict(containment.get("post_audit"))
    if (
        post.get("verdict") != "ISOLATED"
        or post.get("resolved_inside_b51_copy") != 56
        or as_list(post.get("resolved_outside_b51_copy"))
        or as_list(post.get("unresolved_components"))
        or as_list(post.get("missing_resolved_paths"))
    ):
        raise RuntimeError(
            "canonical cold-reopen reference containment drifted"
        )
    if (
        as_dict(h10.get("h10")).get("status")
        != "FAIL_GEOMETRY_REDESIGN_REQUIRED"
    ):
        raise RuntimeError(
            "H10 is not the expected fail-closed redesign state"
        )
    if phase_bc.get("h9") != "HUMAN_DECISION_REQUIRED":
        raise RuntimeError("H9 human decision state drifted")
    if len(ledger_rows) != 28:
        raise RuntimeError(
            f"interference ledger row count {len(ledger_rows)} != 28"
        )
    open_rows = sum(
        row.get("closure_status", "").startswith("OPEN_")
        for row in ledger_rows
    )
    unacceptable_rows = sum(
        row.get("b51_proposed_class")
        == "UNACCEPTABLE_COLLISION"
        for row in ledger_rows
    )
    if open_rows != 28 or unacceptable_rows != 8:
        raise RuntimeError(
            "expected H10 ledger state drifted: "
            f"open={open_rows}, unacceptable={unacceptable_rows}"
        )
    if (
        canonical_lock.get(
            "accepted_urdf_mass_kg_source_decimal"
        )
        != URDF_MASS_DECIMAL
    ):
        raise RuntimeError("accepted URDF mass authority drifted")
    return {
        "ledger_rows": len(ledger_rows),
        "open_rows": open_rows,
        "unacceptable_collision_rows": unacceptable_rows,
    }


def main() -> int:
    generated_utc = utc_now()
    canonical_lock = load_json(CANONICAL_INPUT_LOCK)
    containment = load_json(REFERENCE_CONTAINMENT)
    h10 = load_json(H10_AUDIT)
    phase_bc = load_json(PHASE_BC_GATE)
    clearance = load_json(CLEARANCE_GATE)
    ledger_rows = load_csv(INTERFERENCE_LEDGER)
    joints = load_csv(ACCEPTED_JOINT_CONTRACT)
    topology = accepted_topology(joints)
    h10_counts = validate_controlling_truth(
        canonical_lock,
        containment,
        h10,
        phase_bc,
        ledger_rows,
    )
    (
        articulation_report,
        selected_articulation_path,
        articulation_paths,
        source_is_t005,
    ) = choose_articulation_evidence()
    off_axis_diagnostic = load_json(OFF_AXIS_DIAGNOSTIC)
    if (
        off_axis_diagnostic.get("status")
        != "SOLVER_STATE_RECOVERY_CANDIDATE_FOUND"
        or as_list(off_axis_diagnostic.get("passing_variants"))
        != ["DOCUMENT_REOPEN_AFTER_OFF_AXIS"]
    ):
        raise RuntimeError("off-axis recovery diagnostic state drifted")
    evaluation = evaluate_six_r(
        articulation_report, source_is_t005
    )
    build = as_dict(articulation_report.get("build"))
    random_checks = [
        as_dict(item)
        for item in as_list(build.get("random_legal_pose_checks"))
    ]
    six_r_pass = (
        evaluation["native_6r_evidence_pass"] is True
    )
    g3_status = (
        "HOLD_6R_COORDINATED_PASS_2P_AND_NATIVE_LIMIT_MATES_MISSING"
        if six_r_pass
        else "HOLD_NO_ACCEPTED_6R_RUN_2P_AND_NATIVE_LIMIT_MATES_MISSING"
    )

    evidence_records = [
        file_record(path) for path in articulation_paths
    ]
    kinematic = {
        "schema": "SER_B51_CAD_URDF_KINEMATIC_CONSISTENCY_V1",
        "generated_utc": generated_utc,
        "status": (
            "B51_CAD_URDF_6R_PASS_WITH_2P_AND_NATIVE_LIMIT_MATE_HOLDS"
            if six_r_pass
            else "B51_CAD_URDF_KINEMATIC_CONSISTENCY_HOLD"
        ),
        "accepted_urdf_authority": {
            "path": canonical_lock["accepted_urdf"]["path"],
            "sha256": canonical_lock["accepted_urdf"]["sha256"],
            "mass_kg_source_decimal": URDF_MASS_DECIMAL,
            "topology": topology,
            "cad_mass_override_authorized": False,
        },
        "accepted_joint_contract": file_record(
            ACCEPTED_JOINT_CONTRACT
        ),
        "selected_articulation_evidence": file_record(
            selected_articulation_path
        ),
        "all_articulation_evidence": evidence_records,
        "source_run_evaluation": evaluation,
        "q0_transform_readback": pose_summary(
            build.get("q0_readback")
        ),
        "stow_v2_transform_readback": pose_summary(
            build.get("stow_v2_pose_check")
        ),
        "random_legal_pose_summary": {
            "required": 20,
            "available": len(random_checks),
            "accepted": 20 if six_r_pass else 0,
            "maximum_transform_element_error": evaluation[
                "random_pose_max_transform_element_error"
            ],
            "per_link_max_transform_element_errors": (
                aggregate_random_frame_errors(random_checks)
            ),
        },
        "error_metric_limit": {
            "position_error_m": "UNKNOWN_NOT_SEPARATELY_REPORTED",
            "orientation_error_rad": (
                "UNKNOWN_NOT_SEPARATELY_REPORTED"
            ),
            "reason": (
                "The native source reports homogeneous-transform element "
                "errors. This closeout does not invent a position/orientation "
                "decomposition."
            ),
        },
        "registration_holds": {
            "G05": "CHAIN_DERIVED_HOLD",
            "G08": "CHAIN_DERIVED_HOLD",
            "silent_upgrade_to_direct": False,
        },
        "g3": {
            "status": g3_status,
            "native_6r_evidence": (
                "PASS" if six_r_pass else "HOLD"
            ),
            "native_2p_evidence": (
                "NOT_IMPLEMENTED_G08_PARTITION_AND_ZERO_CALIBRATION_HOLD"
            ),
            "native_limit_mates_present": False,
            "limit_control_credit": (
                "PRE_SOLVER_Q_VECTOR_GATE_ONLY"
            ),
        },
        "claim_limit": (
            "A T005 6R pass, when present, is coordinated-pose native "
            "revolute evidence only. It does not close 2P, native limit "
            "mates, H10, continuous clearance, manufacturing, launch, or "
            "flight qualification."
        ),
    }

    mate_fields = [
        "joint_name",
        "urdf_type",
        "parent_link",
        "child_link",
        "origin_xyz_m_source",
        "origin_rpy_rad_source",
        "axis_source",
        "limit_lower_source",
        "limit_upper_source",
        "native_mate_labels",
        "native_implementation_status",
        "native_limit_mate_present",
        "limit_enforcement_method",
        "evidence_run_id",
        "gate_effect",
    ]
    random_fields = [
        "source_run_id",
        "sample_id",
        "q1_rad",
        "q2_rad",
        "q3_rad",
        "q4_rad",
        "q5_rad",
        "q6_rad",
        "within_accepted_limits",
        "transform_max_abs_error",
        "position_error_m",
        "orientation_error_rad",
        "status",
        "evidence_note",
    ]
    mate_content = csv_text(
        mate_fields,
        build_mate_rows(joints, articulation_report, evaluation),
    )
    random_content = csv_text(
        random_fields,
        build_random_rows(articulation_report, evaluation),
    )
    kinematic_content = json_text(kinematic)

    phase_d_artifacts = {
        relative(KINEMATIC_OUTPUT): {
            "sha256": sha256_bytes(
                kinematic_content.encode("utf-8")
            )
        },
        relative(MATE_OUTPUT): {
            "sha256": sha256_bytes(
                mate_content.encode("utf-8")
            )
        },
        relative(RANDOM_OUTPUT): {
            "sha256": sha256_bytes(
                random_content.encode("utf-8")
            )
        },
    }
    datum_conflict = as_dict(
        h10.get("canonical_datum_conflict")
    )
    gate = {
        "schema": "SER_B51_GATE_V1",
        "generated_utc": generated_utc,
        "task_id": (
            "COMP-PROT-03-A4-B5.1-B601-INTERFACE-CLOSURE-"
            "ARTICULATION-STOWAGE"
        ),
        "status": FINAL_VERDICT,
        "final_verdict": FINAL_VERDICT,
        "clocking_25_deg": (
            "RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY"
        ),
        "mass_authority": {
            "source": "ACCEPTED_URDF",
            "kg_source_decimal": URDF_MASS_DECIMAL,
            "cad_mass_override_authorized": False,
        },
        "gates": {
            "G0": {
                "status": "PASS",
                "evidence": [
                    file_record(CANONICAL_INPUT_LOCK),
                    file_record(REFERENCE_CONTAINMENT),
                ],
                "reference_containment": "56_OF_56_INSIDE_B51_COPY",
                "claim_limit": (
                    "REFERENCE_CONTAINMENT_AND_SOURCE_HASH_"
                    "PRESERVATION_ONLY"
                ),
            },
            "G1": {
                "status": "HOLD_HUMAN_DECISION_REQUIRED",
                "mode_a": phase_bc.get("mode_a"),
                "mode_b": phase_bc.get("mode_b"),
                "launcher_or_deployer_icd_bound": False,
                "evidence": [
                    file_record(PHASE_BC_GATE),
                    file_record(PACKAGING_DECISION),
                    file_record(INTERFACE_CONTROL_DRAWING),
                ],
            },
            "G2": {
                "status": "FAIL_GEOMETRY_REDESIGN_REQUIRED",
                **h10_counts,
                "canonical_longeron_center_abs_yz_mm": (
                    datum_conflict.get(
                        "canonical_longeron_center_abs_yz_mm"
                    )
                ),
                "b51_longeron_center_abs_yz_mm": (
                    datum_conflict.get(
                        "b51_longeron_center_abs_yz_mm"
                    )
                ),
                "longeron_center_offset_mm": (
                    datum_conflict.get(
                        "longeron_center_offset_mm"
                    )
                ),
                "saddle_to_primary_gap_mm": (
                    datum_conflict.get(
                        "saddle_to_primary_gap_mm"
                    )
                ),
                "evidence": [file_record(H10_AUDIT)],
            },
            "G3": {
                "status": g3_status,
                "accepted_topology": topology,
                "native_6r_evidence": (
                    "PASS" if six_r_pass else "HOLD"
                ),
                "native_2p_evidence": "NOT_IMPLEMENTED",
                "native_limit_mates_present": False,
                "source_run": articulation_report.get("run_id"),
                "evidence": evidence_records,
                "solver_state_diagnostic": {
                    "status": off_axis_diagnostic.get("status"),
                    "source_open_mode": off_axis_diagnostic.get(
                        "source_open_mode"
                    ),
                    "passing_variants": as_list(
                        off_axis_diagnostic.get("passing_variants")
                    ),
                    "engineering_credit": "NONE_DIAGNOSTIC_ONLY",
                    "next_run_requirement": (
                        "NEW_IMMUTABLE_20_POSE_BUILD_AND_"
                        "INDEPENDENT_PROCESS_REOPEN"
                    ),
                },
            },
            "G4": {
                "status": (
                    "HOLD_PHYSICAL_RESTRAINT_AND_RELEASE_INTERFACE"
                ),
                "reason": (
                    "Concept documents exist, but the saddle load path "
                    "does not connect directly to canonical primary "
                    "structure and structural response is not run."
                ),
                "evidence": [
                    file_record(path) for path in STOWAGE_EVIDENCE
                ],
            },
            "G5": {
                "status": "HOLD_NOT_RUN",
                "source_status": clearance.get("status"),
                "nominal": clearance.get("nominal"),
                "L_FAIL": clearance.get("L_FAIL"),
                "R_FAIL": clearance.get("R_FAIL"),
                "DEPLOY_FAILED_BOTH": clearance.get(
                    "DEPLOY_FAILED_BOTH"
                ),
                "evidence": [
                    file_record(CLEARANCE_GATE),
                    file_record(CLEARANCE_CURVES),
                ],
            },
            "G6": {
                "status": "HOLD_NOT_RUN",
                "reason": (
                    "Unit-load, modal, slenderness, local-buckling and "
                    "connection-stiffness evidence is not available."
                ),
                "evidence": [
                    file_record(path) for path in STRUCTURAL_EVIDENCE
                ],
            },
            "G7": {
                "status": "HOLD_PARTIAL_DIGITAL_THREAD",
                "accepted_urdf_mass_preserved": True,
                "cad_urdf_full_topology_verified": False,
                "visual_collision_handoff_complete": False,
                "phase_d_artifacts": phase_d_artifacts,
            },
        },
        "verdict_logic": [
            "G0_PASS_RULES_OUT_BASELINE_CONTAMINATION",
            "G2_FAIL_REQUIRES_INTERFACE_COLLISION_REVISION",
            "G1_HOLD_DOES_NOT_OVERRIDE_G2_FAIL",
            "ANY_FUTURE_ACCEPTED_6R_EVIDENCE_DOES_NOT_OVERRIDE_G2_FAIL",
            "CURRENT_DIAGNOSTIC_RECOVERY_DOES_NOT_CLOSE_6R_2P_OR_NATIVE_LIMIT_MATES",
        ],
        "missing_required_deliverables": [
            "CANONICAL_DATUM_DRIVEN_B51_MASTER_SKELETON_NATIVE_PART",
            "TWENTY_EIGHT_ROW_H10_LOCAL_EVIDENCE_AND_CLOSURE",
            "CANONICAL_NATIVE_BRIDGE_ADAPTER_AND_TWO_SADDLE_ASSEMBLIES",
            "ACCEPTED_2P_GRIPPER_PARTITION_ZERO_AND_NATIVE_PRISMATIC_MATES",
            "NATIVE_JOINT_LIMIT_MATES",
            "CONTINUOUS_NOMINAL_AND_FAILURE_STATE_CLEARANCE",
            "UNIT_LOAD_MODAL_SLENDERNESS_AND_CONNECTION_STIFFNESS_EVIDENCE",
            "COMPLETE_PHASE_H_NATIVE_DRAWING_BOM_AND_MESH_HANDOFF",
        ],
        "claim_limits": [
            "NOT_COMPLETE",
            "NOT_FLIGHT_READY",
            "NOT_MANUFACTURING_READY",
            "NO_LAUNCH_QUALIFICATION",
        ],
    }
    gate_content = json_text(gate)

    six_r_sentence = (
        "T005 provides accepted 6R coordinated-pose evidence, but 2P and "
        "native limit mates remain HOLD."
        if six_r_pass
        else (
            "T005 reached its first random pose but failed after mate "
            "rebuild. The separate T003 read-only state diagnostic records "
            "10/10 legal directions, 2/2 illegal-limit rejections and 6/6 "
            "off-axis rejections; only document reopen recovered post-"
            "rebuild FK, and that result is diagnostic only. No accepted "
            "full 6R run is available, and 2P/native limit mates also "
            "remain HOLD."
            if source_is_t005
            else "No accepted full 6R run is available; 2P and native limit "
            "mates also remain HOLD."
        )
    )
    articulation_sources = ", ".join(
        f"`{relative(path)}`" for path in articulation_paths
    )
    delivery_gap_content = f"""# B5.1 delivery gap register

Generated UTC: `{generated_utc}`

Final verdict: `{FINAL_VERDICT}`

This register is fail-closed. File presence, a native 6R run, or a rendered
STEP does not create interface, 2P, structural, manufacturing, launch, or
flight authority.

## Controlling evidence

- Canonical input lock: `{relative(CANONICAL_INPUT_LOCK)}`
- Native reference containment: `{relative(REFERENCE_CONTAINMENT)}`
- H10 exact-BREP audit: `{relative(H10_AUDIT)}`
- Accepted joint contract: `{relative(ACCEPTED_JOINT_CONTRACT)}`
- Articulation evidence: {articulation_sources}

## Phase and Gate gaps

| Scope | Current result | Remaining gap |
|---|---|---|
| Phase A / G0 | PASS | Claim is limited to source preservation and isolated reference containment. |
| Phase B / G1 | HOLD | Human selection of Mode A or Mode B and a bound launcher/deployer ICD are missing. |
| Phase C / G2 | FAIL | 28/28 rows remain open, including 8 unacceptable collisions; the current saddle datum is offset from the canonical longeron datum. |
| Phase D / G3 | HOLD | {six_r_sentence} |
| Phase E / G4 | HOLD | Native physical saddle/HDRM assemblies, direct primary-structure load path, preload and response evidence are missing. |
| Phase F / G5 | HOLD | Continuous nominal and asymmetric failure-state clearance was not run. |
| Phase G / G6 | HOLD | Unit-load, mode, slenderness and connection-stiffness evidence was not run. |
| Phase H / G7 | HOLD | Full native integration, drawings, provisional BOM, Parasolid and visual/collision handoff remain incomplete. |

## Generated closeout artifacts

- `{relative(KINEMATIC_OUTPUT)}`
- `{relative(MATE_OUTPUT)}`
- `{relative(RANDOM_OUTPUT)}`
- `{relative(GATE_OUTPUT)}`

These artifacts report the available evidence; they do not upgrade any HOLD.

## Required next sequence

1. Correct the installation skeleton to the canonical longeron datum and
   rebuild the bridge adapter and both saddles as native candidate assets.
2. Attach exact common-volume, minimum-distance, local-image and replacement
   evidence to every one of the 28 H10 rows; close all unacceptable and
   unadjudicated collisions.
3. Complete a traceable G08 fixed-body/left-finger/right-finger partition,
   implement both accepted prismatic joints and native joint limit mates.
4. After G2/G3/G4 entry conditions are satisfied, run continuous clearance
   and then unit-load/modal preliminary analysis.

Claim level:
`ENGINEERING_DEFINITION_NOT_MANUFACTURING_RELEASE`.
"""

    gate_lines = "\n".join(
        f"- {name}: `{record['status']}`"
        for name, record in gate["gates"].items()
    )
    current_status_content = f"""# B5.1 current status

Generated UTC: `{generated_utc}`

Final verdict: `{FINAL_VERDICT}`

## 已读取真值

- canonical V2.2/B5.0 input lock and native cold-reopen containment;
- accepted URDF mass `{URDF_MASS_DECIMAL} kg` and 6R+1 fixed+2P joint contract;
- canonical H10 exact-BREP audit and the 28-row disposition ledger;
- articulation evidence selected from {articulation_sources}.

## 创建资产

- `{relative(KINEMATIC_OUTPUT)}`
- `{relative(MATE_OUTPUT)}`
- `{relative(RANDOM_OUTPUT)}`
- `{relative(GATE_OUTPUT)}`
- `{relative(DELIVERY_GAP_OUTPUT)}`
- `{relative(CURRENT_STATUS_OUTPUT)}`

## 发现问题

- G2 remains a controlling failure: all 28 H10 rows are open and 8 are
  classified `UNACCEPTABLE_COLLISION`.
- The B5.1 longeron datum differs from the canonical datum by
  `{datum_conflict.get("longeron_center_offset_mm")} mm`; both saddle
  candidates remain `{datum_conflict.get("saddle_to_primary_gap_mm")} mm`
  from canonical primary structure.
- {six_r_sentence}
- Continuous clearance and structural preliminary analyses remain not run.

## Gate

{gate_lines}

No `COMPLETE`, `FLIGHT_READY`, or `MANUFACTURING_READY` claim is authorized.

## 下一动作

Correct the canonical installation datum, rebuild the native adapter and
double-saddle interfaces, and close all 28 H10 records before continuous
clearance or structural analysis is admitted.
"""

    contents = {
        KINEMATIC_OUTPUT: kinematic_content,
        MATE_OUTPUT: mate_content,
        RANDOM_OUTPUT: random_content,
        GATE_OUTPUT: gate_content,
        DELIVERY_GAP_OUTPUT: delivery_gap_content,
        CURRENT_STATUS_OUTPUT: current_status_content,
    }
    write_outputs_once(contents)
    print(
        json.dumps(
            {
                "status": FINAL_VERDICT,
                "source_run": articulation_report.get("run_id"),
                "native_6r_evidence_pass": six_r_pass,
                "g3": g3_status,
                "outputs": [relative(path) for path in contents],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
