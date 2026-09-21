"""Deterministic fail-closed negative controls for the B601 gripper 2P proxy.

The controls mutate only in-memory records or files under a system temporary
directory.  They never edit the source STEP/PLY/URDF assets or the system M01
registry.  Each case is successful only when its intended contract violation is
actually raised and caught.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterable


PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = next(parent for parent in (PACKAGE, *PACKAGE.parents) if (parent / "PROJECT_MAP.md").is_file())
CONTRACT_PATH = PACKAGE / "00_contract" / "GRIPPER_2P_OPERATIONAL_PROXY_CONTRACT_V1.json"
SOURCE_LOCK_PATH = PACKAGE / "00_contract" / "SOURCE_AUTHORITY_LOCK_V1.json"
RUNNER_PATH = Path(__file__).resolve()
RESULT_PATH = PACKAGE / "05_results" / "NEGATIVE_CONTROLS_V1.json"
BUILDER_DIR = PACKAGE / "02_builder"

if str(BUILDER_DIR) not in sys.path:
    sys.path.insert(0, str(BUILDER_DIR))

import gripper_2p_geometry as geometry  # noqa: E402


WRAPPER_ID = "B51_REF_gripper_detail_LINKLOCAL057"
EXPECTED_CONTAINERS = (
    "B601_GRIPPER_PALM_GRIPPER_LINK_LOCAL_V1",
    "B601_GRIPPER_LEFT_FINGER_CHILD_LINK_LOCAL_V1",
    "B601_GRIPPER_RIGHT_FINGER_CHILD_LINK_LOCAL_V1",
)
EXPECTED_COUNTS = {"palm": 12, "left": 24, "right": 24, "total": 60}


class ContractViolation(RuntimeError):
    """An expected fail-closed rejection from a negative-control validator."""


def require_baseline(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(f"negative-control baseline invalid: {message}")


def enforce(condition: bool, code: str) -> None:
    if not condition:
        raise ContractViolation(code)


def stable_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(WORKSPACE).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_path(path),
    }


def strict_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            require_baseline(key not in result, f"duplicate JSON key {key!r} in {path.name}")
            result[key] = value
        return result

    require_baseline(path.is_file(), f"missing JSON {path}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def validate_file_pin(path: Path, pin: dict[str, Any]) -> None:
    enforce(path.is_file(), "SOURCE_PIN_FILE_MISSING")
    enforce(path.stat().st_size == int(pin["bytes"]), "SOURCE_PIN_BYTES_MISMATCH")
    enforce(sha256_path(path) == str(pin["sha256"]), "SOURCE_PIN_SHA256_MISMATCH")


def validate_container_set(container_ids: list[str]) -> None:
    enforce(len(container_ids) == 3, "CONTAINER_COUNT_NOT_THREE")
    enforce(len(set(container_ids)) == 3, "CONTAINER_IDS_NOT_UNIQUE")
    enforce(set(container_ids) == set(EXPECTED_CONTAINERS), "CONTAINER_SET_MISMATCH")


def validate_palm_source(candidate: dict[str, Any], contract: dict[str, Any]) -> None:
    expected = contract["candidate_set"]["authorized_candidates"][0]
    enforce(candidate.get("primary_step_source_id") == "gripper_r1_palm_step", "PALM_SOURCE_NOT_DIRECT_R1_STEP")
    enforce(
        candidate.get("primary_step_source_path") == expected["primary_step_source_path"],
        "PALM_SOURCE_PATH_MISMATCH",
    )


def validate_finger_membership(candidate_members: Iterable[str], expected_members: set[str]) -> None:
    values = list(candidate_members)
    enforce(len(values) == 24, "FINGER_MEMBER_COUNT_NOT_24")
    enforce(len(set(values)) == 24, "FINGER_MEMBERS_NOT_UNIQUE")
    enforce(set(values) == expected_members, "FROZEN_FINGER_MEMBERSHIP_MISMATCH")


def validate_no_wrapper(groups: dict[str, Iterable[str]]) -> None:
    for members in groups.values():
        enforce(WRAPPER_ID not in set(members), "AGGREGATE_WRAPPER_INCLUDED_AS_PHYSICAL_BODY")


def validate_solid_integrity(rows: list[dict[str, Any]]) -> None:
    enforce(bool(rows), "SOLID_LEDGER_EMPTY")
    for row in rows:
        enforce(row.get("brep_valid") is True, "SOLID_BREP_INVALID")
        enforce(row.get("closed") is True, "SOLID_NOT_CLOSED")
        volume = row.get("volume_mm3")
        enforce(
            not isinstance(volume, bool)
            and isinstance(volume, (int, float))
            and math.isfinite(float(volume))
            and float(volume) > 0.0,
            "SOLID_VOLUME_NOT_POSITIVE_FINITE",
        )


def validate_geometry_operations(operations: Iterable[str]) -> None:
    forbidden = {
        "BOOLEAN_FUSE",
        "OUTER_ENVELOPE",
        "CONVEX_HULL",
        "INVENTED_CONNECTOR",
        "BODY_DUPLICATION",
        "BODY_DELETION",
    }
    for operation in operations:
        enforce(operation not in forbidden, f"FORBIDDEN_GEOMETRY_OPERATION:{operation}")


def validate_count_ledger(ledger: dict[str, Any], *, require_independent_reopen: bool) -> None:
    reported = ledger.get("reported_counts", {})
    enforce(reported.get("palm") == 12, "PALM_SOLID_COUNT_NOT_12")
    enforce(reported.get("left") == 24, "LEFT_SOLID_COUNT_NOT_24")
    enforce(reported.get("right") == 24, "RIGHT_SOLID_COUNT_NOT_24")
    enforce(reported.get("total") == 60, "TOTAL_SOLID_COUNT_NOT_60")
    enforce(
        reported["total"] == reported["palm"] + reported["left"] + reported["right"],
        "TOTAL_SOLID_COUNT_ARITHMETIC_MISMATCH",
    )
    if require_independent_reopen:
        reopened = ledger.get("independent_reopen_counts")
        enforce(isinstance(reopened, dict), "INDEPENDENT_REOPEN_COUNTS_MISSING")
        enforce(reopened == EXPECTED_COUNTS, "INDEPENDENT_REOPEN_COUNTS_MISMATCH")


def validate_palm_frame(frame: str) -> None:
    enforce(frame == "gripper_link", "PALM_FRAME_MUST_BE_GRIPPER_LINK")


def validate_finger_reframe(metadata: dict[str, Any], expected_child: str) -> None:
    enforce(metadata.get("source_frame") == "gripper_link", "FINGER_SOURCE_FRAME_MUST_BE_GRIPPER_LINK")
    enforce(metadata.get("offline_inverse_q0_count") == 1, "FINGER_OFFLINE_REFRAME_COUNT_NOT_ONE")
    enforce(metadata.get("output_frame") == expected_child, "FINGER_OUTPUT_FRAME_NOT_CHILD_LINK")


def validate_runtime_metadata_via_builder(metadata: dict[str, Any], object_name: str) -> None:
    try:
        geometry.validate_runtime_metadata(metadata, object_name)
    except RuntimeError as exc:
        raise ContractViolation(f"BUILDER_RUNTIME_METADATA_REJECTED:{exc}") from None


def validate_scale(scale_factor: float, application_count: int) -> None:
    enforce(application_count == 1, "SCALE_APPLICATION_COUNT_NOT_ONE")
    enforce(scale_factor == 0.001, "STEP_MM_TO_RUNTIME_M_SCALE_NOT_0_001")


def validate_axis_binding(candidate_axis: list[float], expected_axis: list[float]) -> None:
    enforce(len(candidate_axis) == len(expected_axis) == 3, "AXIS_VECTOR_SHAPE_MISMATCH")
    enforce(candidate_axis == expected_axis, "LEFT_RIGHT_AXIS_BINDING_MISMATCH")


def validate_q0_reference_state(record: dict[str, Any]) -> None:
    enforce(record.get("q0_reference_only") is True, "Q0_NOT_DECLARED_REFERENCE_ONLY")
    enforce(record.get("owner_value_m") is None, "Q0_PROMOTED_TO_OWNER_STATE")
    enforce(record.get("named_state") is None, "Q0_PROMOTED_TO_NAMED_STATE")


def validate_conflicting_witness(record: dict[str, Any]) -> None:
    enforce(record.get("configuration_travel_authority") is None, "CONFLICTING_WITNESS_PROMOTED_TO_AUTHORITY")
    enforce(record.get("owner_state_written") is False, "CONFLICTING_WITNESS_WRITTEN_TO_OWNER_STATE")


def validate_locked_2p_diagnostic(record: dict[str, Any]) -> None:
    enforce(record.get("authority") == "DIAGNOSTIC_ONLY", "LOCKED_2P_DIAGNOSTIC_PROMOTED")
    enforce(record.get("owner_state_written") is False, "LOCKED_2P_DIAGNOSTIC_WRITTEN_TO_OWNER_STATE")


def validate_swept_volume_claim(claim: str) -> None:
    enforce(claim == "BROADPHASE_ONLY", "SWEPT_VOLUME_EXCEEDED_BROADPHASE_AUTHORITY")


def validate_local_claim_boundary(flags: dict[str, bool]) -> None:
    required_false = (
        "system_safe",
        "system_pair_evaluation_authorized",
        "path_search_authorized",
        "parent_gate_credit",
        "release_credit",
    )
    for key in required_false:
        enforce(flags.get(key) is False, f"LOCAL_GEOMETRY_PROMOTED_TO_SYSTEM:{key}")


def validate_system_invariants(candidate: dict[str, Any], expected: dict[str, Any]) -> None:
    enforce(set(candidate) == set(expected), "SYSTEM_INVARIANT_KEY_SET_MISMATCH")
    for key in sorted(expected):
        enforce(candidate[key] == expected[key], f"SYSTEM_AUTHORITY_COUNTER_OR_FLAG_CHANGED:{key}")


def caught_case(
    case_id: str,
    mutation: dict[str, Any],
    expected_code: str,
    action: Callable[[], None],
) -> dict[str, Any]:
    try:
        action()
    except ContractViolation as exc:
        message = str(exc)
        require_baseline(expected_code in message, f"{case_id} caught wrong rule: {message}")
        return {
            "case_id": case_id,
            "mutation": mutation,
            "expected_rejection_code": expected_code,
            "caught_exception_type": type(exc).__name__,
            "caught_message": message,
            "status": "CAUGHT",
        }
    except Exception as exc:  # pragma: no cover - defensive; never counts as caught
        raise RuntimeError(f"{case_id} raised unexpected {type(exc).__name__}: {exc}") from exc
    raise RuntimeError(f"{case_id} was not rejected")


def control(control_id: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    caught = sum(case["status"] == "CAUGHT" for case in cases)
    require_baseline(caught == len(cases) and bool(cases), f"{control_id} did not catch every subcase")
    return {
        "control_id": control_id,
        "case_count": len(cases),
        "caught_count": caught,
        "status": "CAUGHT",
        "cases": cases,
    }


def assignment_groups() -> dict[str, set[str]]:
    path = WORKSPACE / geometry.ASSIGNMENT_REL
    groups = {"gripper_link": set(), "gripper_left": set(), "gripper_right": set()}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            group = row["assigned_body"]
            require_baseline(group in groups, f"unknown assignment group {group!r}")
            if row["solid"] != WRAPPER_ID:
                groups[group].add(row["solid"])
    require_baseline(len(groups["gripper_link"]) == 9, "native palm lineage is not 9")
    require_baseline(len(groups["gripper_left"]) == 24, "left frozen group is not 24")
    require_baseline(len(groups["gripper_right"]) == 24, "right frozen group is not 24")
    return groups


def build_evidence() -> dict[str, Any]:
    contract = strict_json(CONTRACT_PATH)
    strict_json(SOURCE_LOCK_PATH)
    contract_ids = list(contract["minimum_negative_controls"])
    require_baseline(len(contract_ids) >= 20, "contract has fewer than 20 minimum negative controls")
    require_baseline(len(contract_ids) == len(set(contract_ids)), "contract negative-control ids are not unique")

    groups = assignment_groups()
    urdf = geometry.parse_urdf_contract()
    left_axis = list(urdf["joints"]["gripper_joint1"]["axis_parent"])
    right_axis = list(urdf["joints"]["gripper_joint2"]["axis_parent"])
    require_baseline(left_axis[1] < -0.999999 and right_axis[1] > 0.999999, "accepted URDF axis signs drifted")

    controls: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="b601_gripper_negative_controls_") as temporary:
        pin_file = Path(temporary) / "pinned_source.bin"
        payload = b"B601_NEGATIVE_CONTROL_PIN_PAYLOAD_V1"
        pin_file.write_bytes(payload)
        valid_pin = {"bytes": len(payload), "sha256": sha256_bytes(payload)}
        controls.append(
            control(
                "REJECT_SOURCE_HASH_OR_BYTE_MISMATCH",
                [
                    caught_case(
                        "NC01A_BAD_BYTES",
                        {"bytes": len(payload) + 1, "sha256": valid_pin["sha256"]},
                        "SOURCE_PIN_BYTES_MISMATCH",
                        lambda: validate_file_pin(
                            pin_file,
                            {"bytes": len(payload) + 1, "sha256": valid_pin["sha256"]},
                        ),
                    ),
                    caught_case(
                        "NC01B_BAD_SHA256",
                        {"bytes": len(payload), "sha256": "0" * 64},
                        "SOURCE_PIN_SHA256_MISMATCH",
                        lambda: validate_file_pin(pin_file, {"bytes": len(payload), "sha256": "0" * 64}),
                    ),
                ],
            )
        )

    controls.append(
        control(
            "REJECT_A_FOURTH_OR_MISSING_CONTAINER",
            [
                caught_case(
                    "NC02A_MISSING_CONTAINER",
                    {"container_count": 2},
                    "CONTAINER_COUNT_NOT_THREE",
                    lambda: validate_container_set(list(EXPECTED_CONTAINERS[:2])),
                ),
                caught_case(
                    "NC02B_FOURTH_CONTAINER",
                    {"container_count": 4, "extra": "UNAUTHORIZED_AGGREGATE"},
                    "CONTAINER_COUNT_NOT_THREE",
                    lambda: validate_container_set([*EXPECTED_CONTAINERS, "UNAUTHORIZED_AGGREGATE"]),
                ),
            ],
        )
    )

    bad_palm = copy.deepcopy(contract["candidate_set"]["authorized_candidates"][0])
    bad_palm["primary_step_source_id"] = "neutral_gripper_donor_step"
    controls.append(
        control(
            "REJECT_PALM_SOURCE_OTHER_THAN_DIRECT_R1_STEP",
            [
                caught_case(
                    "NC03_PALM_FROM_NEUTRAL_DONOR",
                    {"primary_step_source_id": bad_palm["primary_step_source_id"]},
                    "PALM_SOURCE_NOT_DIRECT_R1_STEP",
                    lambda: validate_palm_source(bad_palm, contract),
                )
            ],
        )
    )

    bad_left = sorted(groups["gripper_left"])
    bad_left[-1] = "OUTSIDE_FROZEN_LEFT_GROUP"
    bad_right = sorted(groups["gripper_right"])
    bad_right[-1] = "OUTSIDE_FROZEN_RIGHT_GROUP"
    controls.append(
        control(
            "REJECT_LEFT_OR_RIGHT_BODY_OUTSIDE_FROZEN_24_MEMBER_GROUP",
            [
                caught_case(
                    "NC04A_LEFT_OUTSIDE_FROZEN_GROUP",
                    {"replacement_member": "OUTSIDE_FROZEN_LEFT_GROUP", "reported_count": 24},
                    "FROZEN_FINGER_MEMBERSHIP_MISMATCH",
                    lambda: validate_finger_membership(bad_left, groups["gripper_left"]),
                ),
                caught_case(
                    "NC04B_RIGHT_OUTSIDE_FROZEN_GROUP",
                    {"replacement_member": "OUTSIDE_FROZEN_RIGHT_GROUP", "reported_count": 24},
                    "FROZEN_FINGER_MEMBERSHIP_MISMATCH",
                    lambda: validate_finger_membership(bad_right, groups["gripper_right"]),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_AGGREGATE_WRAPPER_AS_PHYSICAL_BODY",
            [
                caught_case(
                    "NC05_WRAPPER_INCLUDED",
                    {"included_member": WRAPPER_ID},
                    "AGGREGATE_WRAPPER_INCLUDED_AS_PHYSICAL_BODY",
                    lambda: validate_no_wrapper({"gripper_link": [WRAPPER_ID]}),
                )
            ],
        )
    )

    valid_solid = {"brep_valid": True, "closed": True, "volume_mm3": 1.0}
    controls.append(
        control(
            "REJECT_ANY_OPEN_INVALID_ZERO_OR_NEGATIVE_VOLUME_SOLID",
            [
                caught_case(
                    "NC06A_OPEN_SOLID",
                    {"closed": False},
                    "SOLID_NOT_CLOSED",
                    lambda: validate_solid_integrity([{**valid_solid, "closed": False}]),
                ),
                caught_case(
                    "NC06B_INVALID_BREP",
                    {"brep_valid": False},
                    "SOLID_BREP_INVALID",
                    lambda: validate_solid_integrity([{**valid_solid, "brep_valid": False}]),
                ),
                caught_case(
                    "NC06C_ZERO_VOLUME",
                    {"volume_mm3": 0.0},
                    "SOLID_VOLUME_NOT_POSITIVE_FINITE",
                    lambda: validate_solid_integrity([{**valid_solid, "volume_mm3": 0.0}]),
                ),
                caught_case(
                    "NC06D_NEGATIVE_VOLUME",
                    {"volume_mm3": -1.0},
                    "SOLID_VOLUME_NOT_POSITIVE_FINITE",
                    lambda: validate_solid_integrity([{**valid_solid, "volume_mm3": -1.0}]),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_ANY_INVENTED_CONNECTOR_FUSE_OR_ENVELOPE",
            [
                caught_case(
                    "NC07A_BOOLEAN_FUSE",
                    {"operation": "BOOLEAN_FUSE"},
                    "FORBIDDEN_GEOMETRY_OPERATION",
                    lambda: validate_geometry_operations(["SELECT", "BOOLEAN_FUSE", "COMPOUND_EMIT"]),
                ),
                caught_case(
                    "NC07B_OUTER_ENVELOPE",
                    {"operation": "OUTER_ENVELOPE"},
                    "FORBIDDEN_GEOMETRY_OPERATION",
                    lambda: validate_geometry_operations(["SELECT", "OUTER_ENVELOPE", "COMPOUND_EMIT"]),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_REPORTING_NATIVE_57_AS_NEW_OUTPUT_COUNT",
            [
                caught_case(
                    "NC08A_NATIVE_9_24_24_REPORTED_AS_OUTPUT",
                    {"reported_counts": {"palm": 9, "left": 24, "right": 24, "total": 57}},
                    "PALM_SOLID_COUNT_NOT_12",
                    lambda: validate_count_ledger(
                        {"reported_counts": {"palm": 9, "left": 24, "right": 24, "total": 57}},
                        require_independent_reopen=False,
                    ),
                ),
                caught_case(
                    "NC08B_LEFT_COUNT_23",
                    {"reported_counts": {"palm": 12, "left": 23, "right": 24, "total": 59}},
                    "LEFT_SOLID_COUNT_NOT_24",
                    lambda: validate_count_ledger(
                        {"reported_counts": {"palm": 12, "left": 23, "right": 24, "total": 59}},
                        require_independent_reopen=False,
                    ),
                ),
                caught_case(
                    "NC08C_RIGHT_COUNT_23",
                    {"reported_counts": {"palm": 12, "left": 24, "right": 23, "total": 59}},
                    "RIGHT_SOLID_COUNT_NOT_24",
                    lambda: validate_count_ledger(
                        {"reported_counts": {"palm": 12, "left": 24, "right": 23, "total": 59}},
                        require_independent_reopen=False,
                    ),
                ),
                caught_case(
                    "NC08D_TOTAL_NOT_60",
                    {"reported_counts": {"palm": 12, "left": 24, "right": 24, "total": 59}},
                    "TOTAL_SOLID_COUNT_NOT_60",
                    lambda: validate_count_ledger(
                        {"reported_counts": {"palm": 12, "left": 24, "right": 24, "total": 59}},
                        require_independent_reopen=False,
                    ),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_REPORTING_60_WITHOUT_INDEPENDENT_PER_CONTAINER_RECOUNT",
            [
                caught_case(
                    "NC09_TOTAL_60_WITHOUT_REOPEN_LEDGER",
                    {"reported_counts": EXPECTED_COUNTS, "independent_reopen_counts": None},
                    "INDEPENDENT_REOPEN_COUNTS_MISSING",
                    lambda: validate_count_ledger(
                        {"reported_counts": dict(EXPECTED_COUNTS), "independent_reopen_counts": None},
                        require_independent_reopen=True,
                    ),
                )
            ],
        )
    )

    controls.append(
        control(
            "REJECT_PALM_LINK6_BINDING",
            [
                caught_case(
                    "NC10_PALM_BOUND_TO_LINK6",
                    {"palm_frame": "link6"},
                    "PALM_FRAME_MUST_BE_GRIPPER_LINK",
                    lambda: validate_palm_frame("link6"),
                )
            ],
        )
    )

    controls.append(
        control(
            "REJECT_GRIPPER_LINK_LOCAL_FINGER_AS_CHILD_LOCAL_WITHOUT_OFFLINE_INVERSE_Q0_REFRAME",
            [
                caught_case(
                    "NC11_UNREFRAMED_LEFT_FINGER",
                    {
                        "source_frame": "gripper_link",
                        "output_frame": "gripper_link",
                        "offline_inverse_q0_count": 0,
                    },
                    "FINGER_OFFLINE_REFRAME_COUNT_NOT_ONE",
                    lambda: validate_finger_reframe(
                        {
                            "source_frame": "gripper_link",
                            "output_frame": "gripper_link",
                            "offline_inverse_q0_count": 0,
                        },
                        "gripper_left",
                    ),
                )
            ],
        )
    )

    controls.append(
        control(
            "REJECT_SECOND_OFFLINE_OR_RUNTIME_Q0_TRANSFORM",
            [
                caught_case(
                    "NC12A_DOUBLE_OFFLINE_REFRAME",
                    {"offline_inverse_q0_count": 2},
                    "FINGER_OFFLINE_REFRAME_COUNT_NOT_ONE",
                    lambda: validate_finger_reframe(
                        {
                            "source_frame": "gripper_link",
                            "output_frame": "gripper_left",
                            "offline_inverse_q0_count": 2,
                        },
                        "gripper_left",
                    ),
                ),
                caught_case(
                    "NC12B_DOUBLE_RUNTIME_TRANSFORM",
                    {"transform_application_count": 2},
                    "BUILDER_RUNTIME_METADATA_REJECTED",
                    lambda: validate_runtime_metadata_via_builder(
                        {
                            "units": "m",
                            "frame": "gripper_left",
                            "object_id": "A::gripper_left",
                            "transform_application_count": 2,
                        },
                        "gripper_left",
                    ),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_MM_TO_M_SCALE_ZERO_OR_TWO_TIMES",
            [
                caught_case(
                    "NC13A_ZERO_SCALE_APPLICATIONS",
                    {"scale_factor": 0.001, "application_count": 0},
                    "SCALE_APPLICATION_COUNT_NOT_ONE",
                    lambda: validate_scale(0.001, 0),
                ),
                caught_case(
                    "NC13B_TWO_SCALE_APPLICATIONS",
                    {"scale_factor": 0.001, "application_count": 2},
                    "SCALE_APPLICATION_COUNT_NOT_ONE",
                    lambda: validate_scale(0.001, 2),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_LEFT_RIGHT_FRAME_OR_AXIS_SWAP",
            [
                caught_case(
                    "NC14A_LEFT_FRAME_SWAPPED_TO_RIGHT",
                    {"object_name": "gripper_left", "frame": "gripper_right"},
                    "BUILDER_RUNTIME_METADATA_REJECTED",
                    lambda: validate_runtime_metadata_via_builder(
                        {
                            "units": "m",
                            "frame": "gripper_right",
                            "object_id": "A::gripper_left",
                            "transform_application_count": 1,
                        },
                        "gripper_left",
                    ),
                ),
                caught_case(
                    "NC14B_LEFT_AXIS_SWAPPED_TO_RIGHT",
                    {"candidate_axis": right_axis, "expected_axis": left_axis},
                    "LEFT_RIGHT_AXIS_BINDING_MISMATCH",
                    lambda: validate_axis_binding(right_axis, left_axis),
                ),
                caught_case(
                    "NC14C_RIGHT_AXIS_SWAPPED_TO_LEFT",
                    {"candidate_axis": left_axis, "expected_axis": right_axis},
                    "LEFT_RIGHT_AXIS_BINDING_MISMATCH",
                    lambda: validate_axis_binding(left_axis, right_axis),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_Q_ZERO_AS_OWNER_NAMED_STATE",
            [
                caught_case(
                    "NC15_Q0_WRITTEN_AS_OWNER_CLOSED",
                    {"q0_reference_only": True, "owner_value_m": 0.0, "named_state": "CLOSED"},
                    "Q0_PROMOTED_TO_OWNER_STATE",
                    lambda: validate_q0_reference_state(
                        {"q0_reference_only": True, "owner_value_m": 0.0, "named_state": "CLOSED"}
                    ),
                )
            ],
        )
    )

    controls.append(
        control(
            "REJECT_R1_OR_EQUAL_INCREMENT_WITNESS_AS_OWNER_AUTHORITY",
            [
                caught_case(
                    "NC16A_R1_NAMED_WITNESS_PROMOTED",
                    {"witness": "R1_NAMED_TRAVEL", "configuration_travel_authority": "R1_NAMED_TRAVEL"},
                    "CONFLICTING_WITNESS_PROMOTED_TO_AUTHORITY",
                    lambda: validate_conflicting_witness(
                        {
                            "configuration_travel_authority": "R1_NAMED_TRAVEL",
                            "owner_state_written": False,
                        }
                    ),
                ),
                caught_case(
                    "NC16B_EQUAL_INCREMENT_WITNESS_PROMOTED",
                    {
                        "witness": "ALTERNATE_EQUAL_INCREMENT",
                        "configuration_travel_authority": "ALTERNATE_EQUAL_INCREMENT",
                    },
                    "CONFLICTING_WITNESS_PROMOTED_TO_AUTHORITY",
                    lambda: validate_conflicting_witness(
                        {
                            "configuration_travel_authority": "ALTERNATE_EQUAL_INCREMENT",
                            "owner_state_written": False,
                        }
                    ),
                ),
            ],
        )
    )

    controls.append(
        control(
            "REJECT_LOCKED_2P_DIAGNOSTIC_QP_STAR_AS_MECHANICAL_STATE_AUTHORITY",
            [
                caught_case(
                    "NC17_LOCKED_2P_QP_STAR_PROMOTED",
                    {"qP_star_m": [0.03575, 0.03575], "authority": "OWNER_MECHANICAL_STATE"},
                    "LOCKED_2P_DIAGNOSTIC_PROMOTED",
                    lambda: validate_locked_2p_diagnostic(
                        {"authority": "OWNER_MECHANICAL_STATE", "owner_state_written": True}
                    ),
                )
            ],
        )
    )

    controls.append(
        control(
            "REJECT_SWEPT_VOLUME_AS_NARROWPHASE_OR_CONTACT_EVIDENCE",
            [
                caught_case(
                    "NC18A_SWEPT_VOLUME_AS_NARROWPHASE_SAFE",
                    {"claim": "NARROWPHASE_SAFE"},
                    "SWEPT_VOLUME_EXCEEDED_BROADPHASE_AUTHORITY",
                    lambda: validate_swept_volume_claim("NARROWPHASE_SAFE"),
                ),
                caught_case(
                    "NC18B_SWEPT_VOLUME_AS_CONTACT",
                    {"claim": "CONTACT"},
                    "SWEPT_VOLUME_EXCEEDED_BROADPHASE_AUTHORITY",
                    lambda: validate_swept_volume_claim("CONTACT"),
                ),
            ],
        )
    )

    base_flags = {
        "system_safe": False,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "parent_gate_credit": False,
        "release_credit": False,
    }
    local_promotion_cases: list[dict[str, Any]] = []
    for suffix, key in (
        ("A", "system_safe"),
        ("B", "system_pair_evaluation_authorized"),
        ("C", "path_search_authorized"),
        ("D", "parent_gate_credit"),
        ("E", "release_credit"),
    ):
        mutated = dict(base_flags)
        mutated[key] = True
        local_promotion_cases.append(
            caught_case(
                f"NC19{suffix}_LOCAL_PASS_PROMOTED_{key.upper()}",
                {key: True},
                "LOCAL_GEOMETRY_PROMOTED_TO_SYSTEM",
                lambda candidate=mutated: validate_local_claim_boundary(candidate),
            )
        )
    controls.append(
        control(
            "REJECT_LOCAL_GEOMETRY_PASS_AS_SYSTEM_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
            local_promotion_cases,
        )
    )

    invariants = copy.deepcopy(contract["current_system_authority_invariants"])
    counter_cases: list[dict[str, Any]] = []
    for suffix, key, value in (
        ("A", "asset_level_operational_authority_rows", 2),
        ("B", "system_pair_queries_executed", 1),
        ("C", "system_edges_certified", 1),
        ("D", "stage_instances_bound", 1),
        ("E", "system_safe_certificates", 1),
    ):
        mutated = copy.deepcopy(invariants)
        mutated[key] = value
        counter_cases.append(
            caught_case(
                f"NC20{suffix}_INCREMENT_{key.upper()}",
                {key: value},
                "SYSTEM_AUTHORITY_COUNTER_OR_FLAG_CHANGED",
                lambda candidate=mutated: validate_system_invariants(candidate, invariants),
            )
        )
    controls.append(
        control(
            "REJECT_ANY_INCREMENT_TO_CURRENT_SYSTEM_AUTHORITY_COUNTERS",
            counter_cases,
        )
    )

    actual_ids = [row["control_id"] for row in controls]
    require_baseline(actual_ids == contract_ids, "implemented control order/ids do not exactly cover the contract")
    control_count = len(controls)
    case_count = sum(row["case_count"] for row in controls)
    caught_control_count = sum(row["status"] == "CAUGHT" for row in controls)
    caught_case_count = sum(row["caught_count"] for row in controls)
    require_baseline(caught_control_count == control_count, "one or more controls were not caught")
    require_baseline(caught_case_count == case_count, "one or more subcases were not caught")

    invariant_bytes = stable_json_bytes(invariants)
    return {
        "schema": "B601_GRIPPER_2P_NEGATIVE_CONTROLS_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "as_of_date": "2026-08-28",
        "authority_scope": "LOCAL_FAIL_CLOSED_NEGATIVE_CONTROL_EVIDENCE_ONLY",
        "contract": relative_record(CONTRACT_PATH),
        "source_lock": relative_record(SOURCE_LOCK_PATH),
        "runner": relative_record(RUNNER_PATH),
        "execution_isolation": {
            "real_source_or_output_assets_modified": False,
            "mutations": "IN_MEMORY_OR_SYSTEM_TEMPORARY_DIRECTORY_ONLY",
            "temporary_directory_deleted_after_cases": True,
            "package_output_written_by_write_mode_only": RESULT_PATH.relative_to(WORKSPACE).as_posix(),
            "cad_or_brep_execution_called": False,
            "pair_query_called": False,
            "path_search_called": False,
        },
        "baseline_bindings": {
            "contract_minimum_control_count": len(contract_ids),
            "frozen_assignment_counts_excluding_wrapper": {
                "palm_native_lineage": len(groups["gripper_link"]),
                "left": len(groups["gripper_left"]),
                "right": len(groups["gripper_right"]),
            },
            "expected_new_container_reopen_counts": EXPECTED_COUNTS,
            "excluded_wrapper": WRAPPER_ID,
            "accepted_urdf_left_axis_in_parent": left_axis,
            "accepted_urdf_right_axis_in_parent": right_axis,
        },
        "summary": {
            "controls_required": len(contract_ids),
            "controls_executed": control_count,
            "controls_caught": caught_control_count,
            "subcases_executed": case_count,
            "subcases_caught": caught_case_count,
            "all_controls_caught": True,
        },
        "controls": controls,
        "current_system_authority_invariants": invariants,
        "system_invariant_snapshot": {
            "before_sha256": sha256_bytes(invariant_bytes),
            "after_sha256": sha256_bytes(stable_json_bytes(invariants)),
            "unchanged": True,
        },
        "authority_flags": {
            "system_safe": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "parent_gate_credit": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": f"PASS_{caught_control_count}_OF_{control_count}_CONTRACT_NEGATIVE_CONTROLS_AND_{caught_case_count}_OF_{case_count}_MUTATION_SUBCASES_CAUGHT__NO_SYSTEM_AUTHORITY_CHANGE",
        "review_status": "PENDING_INDEPENDENT_REVIEW",
        "next_stage_authorized": False,
        "parent_gate_credit": False,
        "release_credit": False,
    }


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="atomically write deterministic evidence")
    mode.add_argument("--check", action="store_true", help="recompute and require byte-identical existing evidence")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = build_evidence()
    payload = stable_json_bytes(evidence)
    if args.write:
        atomic_write(RESULT_PATH, payload)
        mode = "write"
    else:
        require_baseline(RESULT_PATH.is_file(), "negative-control evidence is missing")
        existing = RESULT_PATH.read_bytes()
        require_baseline(
            existing == payload,
            f"negative-control evidence drift: expected {sha256_bytes(payload)}, got {sha256_bytes(existing)}",
        )
        mode = "check"
    print(
        json.dumps(
            {
                "mode": mode,
                "output": RESULT_PATH.relative_to(WORKSPACE).as_posix(),
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "controls_caught": evidence["summary"]["controls_caught"],
                "controls_executed": evidence["summary"]["controls_executed"],
                "subcases_caught": evidence["summary"]["subcases_caught"],
                "subcases_executed": evidence["summary"]["subcases_executed"],
                "verdict": evidence["verdict"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
