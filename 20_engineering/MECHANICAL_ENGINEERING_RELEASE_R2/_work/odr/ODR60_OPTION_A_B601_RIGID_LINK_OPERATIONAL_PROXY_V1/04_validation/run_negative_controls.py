"""Fail-closed mutation campaign for the six B601 rigid-link proxies.

The campaign never edits a source, STEP, runtime mesh, parent Gate, registry,
or scene.  It builds an in-memory authority snapshot from the frozen contract
and source lock, mutates one protected invariant per case, and requires the
same validator used for the baseline to reject every mutation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Callable


PACKAGE_DIR = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    PACKAGE_DIR / "00_contract" / "B601_RIGID_LINK_OPERATIONAL_COLLISION_CONTRACT_V1.json"
)
SOURCE_LOCK_PATH = PACKAGE_DIR / "01_sources" / "SOURCE_AUTHORITY_LOCK_V1.json"
OUTPUT_PATH = PACKAGE_DIR / "05_results" / "NEGATIVE_CONTROLS_V1.json"

EXPECTED_LINKS = tuple(f"link{index}" for index in range(1, 7))
EXPECTED_OBJECT_IDS = tuple(f"A::{link_id}" for link_id in EXPECTED_LINKS)
EXPECTED_EXCLUDED_IDS = (
    "A::base_link",
    "A::gripper_link",
    "A::gripper_left",
    "A::gripper_right",
)
EXPECTED_LOCAL_CANDIDATE_COUNT = 6
EXPECTED_SYSTEM_REGISTRY_OPERATIONAL_COUNT = 1


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _workspace_root() -> Path:
    for candidate in (PACKAGE_DIR, *PACKAGE_DIR.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


def build_authority_state() -> dict:
    """Return the immutable baseline consumed by every mutation case."""

    contract = _read_json(CONTRACT_PATH)
    lock = _read_json(SOURCE_LOCK_PATH)
    rows = []
    for link_id in EXPECTED_LINKS:
        record = lock["link_sources"][link_id]
        rows.append(
            {
                "link_id": link_id,
                "object_id": record["object_id"],
                "frame": record["frame"],
                "source_path": record["path"],
                "source_bytes": record["bytes"],
                "source_sha256": record["sha256"],
                "runtime_unit": contract["geometry_method"]["runtime_unit"],
                "step_unit": contract["geometry_method"]["step_unit"],
                "asset_level_operational_candidate": True,
            }
        )

    urdf = lock["immutable_sources"]["accepted_b601_urdf"]
    return {
        "schema": "B601_RIGID_LINK_OPERATIONAL_PROXY_MUTATION_STATE_V1",
        "contract_object_ids": list(contract["object_ids"]),
        "contract_excluded_objects": list(contract["excluded_objects"]),
        "accepted_b601_urdf": {
            "path": urdf["path"],
            "bytes": urdf["bytes"],
            "sha256": urdf["sha256"],
        },
        "geometry_method": copy.deepcopy(contract["geometry_method"]),
        "objects": rows,
        "counts": {
            "local_pending_owner_review_candidate_count": EXPECTED_LOCAL_CANDIDATE_COUNT,
            "system_registry_operational_asset_count_unchanged": EXPECTED_SYSTEM_REGISTRY_OPERATIONAL_COUNT,
            "system_active_object_count": 150,
        },
        "authority_flags": copy.deepcopy(contract["authority_flags"]),
        "source_mutation_authorized": lock["source_mutation_authorized"],
        "accepted_urdf_mutation_authorized": lock["accepted_urdf_mutation_authorized"],
        "parent_gate_mutation_authorized": lock["parent_gate_mutation_authorized"],
    }


def validate_authority_state(state: dict, *, verify_disk: bool = True) -> list[str]:
    """Return stable fail-closed issue codes; an empty list is a valid state."""

    contract = _read_json(CONTRACT_PATH)
    lock = _read_json(SOURCE_LOCK_PATH)
    issues: list[str] = []

    if tuple(state.get("contract_object_ids", ())) != EXPECTED_OBJECT_IDS:
        issues.append("CONTRACT_OBJECT_SET_OR_ORDER_DRIFT")
    if tuple(state.get("contract_excluded_objects", ())) != EXPECTED_EXCLUDED_IDS:
        issues.append("CONTRACT_EXCLUDED_OBJECT_SET_DRIFT")

    rows = state.get("objects")
    if not isinstance(rows, list):
        issues.append("OBJECT_ROWS_NOT_A_LIST")
        rows = []
    object_ids = [row.get("object_id") for row in rows if isinstance(row, dict)]
    if len(rows) != EXPECTED_LOCAL_CANDIDATE_COUNT:
        issues.append("LOCAL_CANDIDATE_OBJECT_COUNT_DRIFT")
    if len(object_ids) != len(set(object_ids)):
        issues.append("DUPLICATE_OBJECT_ID")
    if set(object_ids) != set(EXPECTED_OBJECT_IDS):
        issues.append("LOCAL_OPERATIONAL_OBJECT_SET_DRIFT")
    if any(object_id in EXPECTED_EXCLUDED_IDS for object_id in object_ids):
        issues.append("BASE_OR_GRIPPER_UNAUTHORIZED_PROMOTION")

    row_by_link = {
        row.get("link_id"): row for row in rows if isinstance(row, dict) and row.get("link_id")
    }
    root = _workspace_root()
    for link_id in EXPECTED_LINKS:
        row = row_by_link.get(link_id)
        expected = lock["link_sources"][link_id]
        if row is None:
            issues.append(f"MISSING_OBJECT_ROW_{link_id.upper()}")
            continue
        if row.get("object_id") != expected["object_id"]:
            issues.append(f"OBJECT_ID_DRIFT_{link_id.upper()}")
        if row.get("frame") != expected["frame"]:
            issues.append(f"FRAME_SWAP_OR_DRIFT_{link_id.upper()}")
        if row.get("source_path") != expected["path"]:
            issues.append(f"SOURCE_PATH_DRIFT_{link_id.upper()}")
        if row.get("source_bytes") != expected["bytes"]:
            issues.append(f"SOURCE_BYTES_DRIFT_{link_id.upper()}")
        if row.get("source_sha256") != expected["sha256"]:
            issues.append(f"SOURCE_HASH_DRIFT_{link_id.upper()}")
        if row.get("runtime_unit") != "m" or row.get("step_unit") != "mm":
            issues.append(f"M_MM_UNIT_DRIFT_{link_id.upper()}")
        if row.get("asset_level_operational_candidate") is not True:
            issues.append(f"LOCAL_CANDIDATE_FLAG_DRIFT_{link_id.upper()}")
        if verify_disk:
            source_path = root / expected["path"]
            if not source_path.is_file():
                issues.append(f"SOURCE_FILE_MISSING_{link_id.upper()}")
            else:
                if source_path.stat().st_size != expected["bytes"]:
                    issues.append(f"SOURCE_DISK_BYTES_DRIFT_{link_id.upper()}")
                if _sha256_path(source_path) != expected["sha256"]:
                    issues.append(f"SOURCE_DISK_HASH_DRIFT_{link_id.upper()}")

    urdf = state.get("accepted_b601_urdf", {})
    expected_urdf = lock["immutable_sources"]["accepted_b601_urdf"]
    for field in ("path", "bytes", "sha256"):
        if urdf.get(field) != expected_urdf[field]:
            issues.append(f"ACCEPTED_URDF_{field.upper()}_DRIFT")
    if verify_disk:
        urdf_path = root / expected_urdf["path"]
        if not urdf_path.is_file():
            issues.append("ACCEPTED_URDF_FILE_MISSING")
        else:
            if urdf_path.stat().st_size != expected_urdf["bytes"]:
                issues.append("ACCEPTED_URDF_DISK_BYTES_DRIFT")
            if _sha256_path(urdf_path) != expected_urdf["sha256"]:
                issues.append("ACCEPTED_URDF_DISK_HASH_DRIFT")

    method = state.get("geometry_method", {})
    expected_method = contract["geometry_method"]
    for field in ("source_unit", "step_unit", "runtime_unit"):
        if method.get(field) != expected_method[field]:
            issues.append(f"GEOMETRY_METHOD_{field.upper()}_DRIFT")
    if method.get("slab_count") != expected_method["slab_count"]:
        issues.append("SLAB_COUNT_DRIFT")
    if method.get("transverse_guard_mm") != expected_method["transverse_guard_mm"]:
        issues.append("TRANSVERSE_GUARD_EXCEEDED_OR_DRIFTED")
    if method.get("longitudinal_guard_mm") != expected_method["longitudinal_guard_mm"]:
        issues.append("LONGITUDINAL_GUARD_DRIFT")

    counts = state.get("counts", {})
    expected_counts = {
        "local_pending_owner_review_candidate_count": EXPECTED_LOCAL_CANDIDATE_COUNT,
        "system_registry_operational_asset_count_unchanged": EXPECTED_SYSTEM_REGISTRY_OPERATIONAL_COUNT,
        "system_active_object_count": 150,
    }
    for field, expected_value in expected_counts.items():
        if counts.get(field) != expected_value:
            issues.append(f"OPERATIONAL_COUNT_INFLATION_OR_DRIFT_{field.upper()}")

    expected_flags = contract["authority_flags"]
    flags = state.get("authority_flags", {})
    for field, expected_value in expected_flags.items():
        if flags.get(field) is not expected_value:
            issues.append(f"FORBIDDEN_AUTHORITY_FLIP_{field.upper()}")
    for field in (
        "source_mutation_authorized",
        "accepted_urdf_mutation_authorized",
        "parent_gate_mutation_authorized",
    ):
        if state.get(field) is not False:
            issues.append(f"FORBIDDEN_MUTATION_AUTHORITY_FLIP_{field.upper()}")

    return sorted(set(issues))


def _set(path: tuple[object, ...], value: object) -> Callable[[dict], None]:
    def mutate(state: dict) -> None:
        cursor: object = state
        for key in path[:-1]:
            cursor = cursor[key]  # type: ignore[index]
        cursor[path[-1]] = value  # type: ignore[index]

    return mutate


def _swap_frames(state: dict) -> None:
    state["objects"][0]["frame"], state["objects"][1]["frame"] = (
        state["objects"][1]["frame"],
        state["objects"][0]["frame"],
    )


def _duplicate_object(state: dict) -> None:
    state["objects"].append(copy.deepcopy(state["objects"][0]))


def _promote_excluded(object_id: str, link_id: str) -> Callable[[dict], None]:
    def mutate(state: dict) -> None:
        row = copy.deepcopy(state["objects"][0])
        row["object_id"] = object_id
        row["link_id"] = link_id
        row["frame"] = link_id.replace("gripper_left", "gripper_link").replace(
            "gripper_right", "gripper_link"
        )
        state["objects"].append(row)

    return mutate


def mutation_cases() -> list[tuple[str, str, Callable[[dict], None]]]:
    return [
        (
            "NC01_SOURCE_HASH_DRIFT",
            "SOURCE_HASH_DRIFT_LINK1",
            _set(("objects", 0, "source_sha256"), "0" * 64),
        ),
        (
            "NC02_SOURCE_BYTES_DRIFT",
            "SOURCE_BYTES_DRIFT_LINK2",
            _set(("objects", 1, "source_bytes"), 1),
        ),
        (
            "NC03_RUNTIME_M_AS_MM",
            "M_MM_UNIT_DRIFT_LINK3",
            _set(("objects", 2, "runtime_unit"), "mm"),
        ),
        (
            "NC04_STEP_MM_AS_M",
            "M_MM_UNIT_DRIFT_LINK4",
            _set(("objects", 3, "step_unit"), "m"),
        ),
        ("NC05_FRAME_SWAP", "FRAME_SWAP_OR_DRIFT_LINK1", _swap_frames),
        (
            "NC06_ACCEPTED_URDF_HASH_DRIFT",
            "ACCEPTED_URDF_SHA256_DRIFT",
            _set(("accepted_b601_urdf", "sha256"), "F" * 64),
        ),
        ("NC07_DUPLICATE_OBJECT", "DUPLICATE_OBJECT_ID", _duplicate_object),
        (
            "NC08_UNAUTHORIZED_BASE_PROMOTION",
            "BASE_OR_GRIPPER_UNAUTHORIZED_PROMOTION",
            _promote_excluded("A::base_link", "base_link"),
        ),
        (
            "NC09_UNAUTHORIZED_GRIPPER_PROMOTION",
            "BASE_OR_GRIPPER_UNAUTHORIZED_PROMOTION",
            _promote_excluded("A::gripper_link", "gripper_link"),
        ),
        (
            "NC10_LOCAL_CANDIDATE_COUNT_INFLATION",
            "OPERATIONAL_COUNT_INFLATION_OR_DRIFT_LOCAL_PENDING_OWNER_REVIEW_CANDIDATE_COUNT",
            _set(("counts", "local_pending_owner_review_candidate_count"), 7),
        ),
        (
            "NC11_SYSTEM_REGISTRY_OPERATIONAL_COUNT_INFLATION",
            "OPERATIONAL_COUNT_INFLATION_OR_DRIFT_SYSTEM_REGISTRY_OPERATIONAL_ASSET_COUNT_UNCHANGED",
            _set(("counts", "system_registry_operational_asset_count_unchanged"), 7),
        ),
        (
            "NC12_SYSTEM_PAIR_AUTHORITY_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_SYSTEM_PAIR_EVALUATION_AUTHORIZED",
            _set(("authority_flags", "system_pair_evaluation_authorized"), True),
        ),
        (
            "NC13_PATH_SEARCH_AUTHORITY_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_PATH_SEARCH_AUTHORIZED",
            _set(("authority_flags", "path_search_authorized"), True),
        ),
        (
            "NC14_NEXT_STAGE_AUTHORITY_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_NEXT_STAGE_AUTHORIZED",
            _set(("authority_flags", "next_stage_authorized"), True),
        ),
        (
            "NC15_RELEASE_CREDIT_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_RELEASE_CREDIT",
            _set(("authority_flags", "release_credit"), True),
        ),
        (
            "NC16_PARENT_GATE_REISSUE_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_PARENT_MECHANICAL_GATE_REISSUED",
            _set(("authority_flags", "parent_mechanical_gate_reissued"), True),
        ),
        (
            "NC17_SYSTEM_REGISTRY_REISSUE_FLIP",
            "FORBIDDEN_AUTHORITY_FLIP_SYSTEM_REGISTRY_REISSUED",
            _set(("authority_flags", "system_registry_reissued"), True),
        ),
        (
            "NC18_TRANSVERSE_GUARD_EXCEEDED",
            "TRANSVERSE_GUARD_EXCEEDED_OR_DRIFTED",
            _set(("geometry_method", "transverse_guard_mm"), 0.006),
        ),
    ]


def run_campaign() -> dict:
    baseline = build_authority_state()
    baseline_issues = validate_authority_state(baseline)
    results = []
    for case_id, expected_issue, mutate in mutation_cases():
        candidate = copy.deepcopy(baseline)
        mutate(candidate)
        issues = validate_authority_state(candidate)
        detected = expected_issue in issues
        results.append(
            {
                "case_id": case_id,
                "expected_issue": expected_issue,
                "detected": detected,
                "issue_count": len(issues),
                "issues": issues,
            }
        )

    all_detected = not baseline_issues and all(row["detected"] for row in results)
    state_sha256 = hashlib.sha256(_json_bytes(baseline)).hexdigest().upper()
    return {
        "schema": "B601_RIGID_LINK_OPERATIONAL_PROXY_NEGATIVE_CONTROLS_V1",
        "authority": "IN_MEMORY_MUTATION_CAMPAIGN_ONLY__NO_SOURCE_OR_PARENT_MUTATION",
        "baseline_state_sha256": state_sha256,
        "baseline_counts": copy.deepcopy(baseline["counts"]),
        "baseline_valid": not baseline_issues,
        "baseline_issues": baseline_issues,
        "case_count": len(results),
        "cases_detected": sum(1 for row in results if row["detected"]),
        "all_negative_controls_detected": all_detected,
        "cases": results,
        "authority_flags": {
            "parent_mechanical_gate_reissued": False,
            "system_registry_reissued": False,
            "system_pair_evaluation_authorized": False,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "verdict": (
            "B601_RIGID_LINK_OPERATIONAL_PROXY_NEGATIVE_CONTROLS_ALL_CAUGHT"
            if all_detected
            else "B601_RIGID_LINK_OPERATIONAL_PROXY_NEGATIVE_CONTROLS_FAILED"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the deterministic result")
    args = parser.parse_args()
    report = run_campaign()
    payload = _json_bytes(report)
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_bytes(payload)
    else:
        print(payload.decode("utf-8"), end="")
    return 0 if report["all_negative_controls_detected"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
