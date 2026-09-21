"""Deterministically build the ODR-60 query-infrastructure audit and gate.

This builder executes only static source inspection and synthetic tests.  It
never calls the current V9F geometry kernel and never starts a path search.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent


def workspace_root() -> Path:
    for candidate in (HERE, *HERE.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root not found")


ROOT = workspace_root()
PACKAGE_REL = HERE.relative_to(ROOT).as_posix()

REL = {
    "adapter": f"{PACKAGE_REL}/exact_q_trace_adapter.py",
    "continuous_edge": f"{PACKAGE_REL}/continuous_edge_certificate.py",
    "tests": f"{PACKAGE_REL}/test_query_infrastructure.py",
    "builder": f"{PACKAGE_REL}/build_query_infrastructure_gate.py",
    "readme": f"{PACKAGE_REL}/README.md",
    "v9f_source": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
        "ROUTE_C_EXACT_SWEEP_V9F.py"
    ),
    "v9f_mesh_manifest": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
        "ROUTE_C_SWEEP_MESH_PACK_V9F/MANIFEST.json"
    ),
    "v9f_golden": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/_work/"
        "v9f_p1_candidate/REFERENCE_VS_P0_SINGLE_POSE_BENCHMARK_V2.json"
    ),
    "system_registry": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
        "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
        "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
    ),
    "collision_authority_gate": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
        "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/"
        "ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1.json"
    ),
    "base_link_proxy_v2_validation": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
        "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/"
        "BASE_LINK_OPERATIONAL_COLLISION_VALIDATION_V2.json"
    ),
    "base_link_proxy_v2_stl": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
        "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/"
        "BASE_LINK_OPERATIONAL_COLLISION_V2.stl"
    ),
    "preflight_gate": (
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
        "ODR60_OPTION_A_PREFLIGHT_V1/ODR60_OPTION_A_PREFLIGHT_GATE_V1.json"
    ),
}

AUDIT_NAME = "FROZEN_V9F_STATIC_ADAPTER_AUDIT_V1.json"
GATE_NAME = "QUERY_INFRASTRUCTURE_GATE_V1.json"
MANIFEST_NAME = "QUERY_INFRASTRUCTURE_SHA256_V1.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def pin(rel_path: str) -> dict[str, Any]:
    path = ROOT / rel_path
    if not path.is_file():
        raise RuntimeError(f"required input absent: {rel_path}")
    return {
        "path": rel_path,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def pin_bytes(rel_path: str, payload: bytes) -> dict[str, Any]:
    return {
        "path": rel_path,
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
        "bytes": len(payload),
    }


def iter_mappings(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from iter_mappings(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_mappings(item)


def load_adapter():
    path = ROOT / REL["adapter"]
    spec = importlib.util.spec_from_file_location("odr60_query_adapter_build", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load adapter module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


def run_synthetic_tests() -> tuple[int, bool]:
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / REL["tests"])],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    combined = completed.stdout + "\n" + completed.stderr
    match = re.search(r"(\d+) passed", combined)
    count = int(match.group(1)) if match else 0
    return count, completed.returncode == 0 and count > 0


def main() -> int:
    adapter = load_adapter()
    audit = adapter.static_audit_frozen_v9f()
    audit_bytes = json_bytes(audit)

    test_count, tests_pass = run_synthetic_tests()
    mesh_manifest = json.loads((ROOT / REL["v9f_mesh_manifest"]).read_text("utf-8"))
    registry = json.loads((ROOT / REL["system_registry"]).read_text("utf-8"))
    collision_gate = json.loads(
        (ROOT / REL["collision_authority_gate"]).read_text("utf-8")
    )

    base_entries = [
        item
        for item in iter_mappings(mesh_manifest)
        if item.get("file") == "vendor_base_link_tris.npy"
    ]
    if len(base_entries) != 1:
        raise RuntimeError("V9F vendor_base_link manifest entry is not unique")
    v9f_base = base_entries[0]
    cable_objects = [
        item
        for item in registry.get("objects", [])
        if str(item.get("object_id", "")).startswith("C::")
    ]
    missing_capsules = [
        item
        for item in cable_objects
        if item.get("geometry", {}).get("runtime_representation")
        == "CAPSULE_CHAIN_REQUIRED_NOT_PREEMITTED"
    ]

    source_pins = {name: pin(path) for name, path in REL.items()}
    source_pins["static_audit"] = pin_bytes(
        f"{PACKAGE_REL}/{AUDIT_NAME}", audit_bytes
    )

    checks = {
        "frozen_v9f_static_audit_pass": audit.get("pass") is True,
        "static_audit_loaded_no_current_geometry": (
            audit.get("current_geometry_loaded") is False
        ),
        "static_audit_executed_no_exact_q_query": (
            audit.get("exact_q_query_executed") is False
        ),
        "synthetic_tests_pass": tests_pass and test_count == 17,
        "adapter_scope_is_harness_pointwise_only": (
            audit.get("scope")
            == "ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY"
        ),
        "v9f_manifest_hash_matches_adapter_pin": (
            source_pins["v9f_mesh_manifest"]["sha256"]
            == adapter.V9F_MESH_MANIFEST_SHA256
        ),
        "v9f_base_uses_declared_legacy_raw_source": (
            v9f_base.get("source_sha256")
            == adapter.V9F_LEGACY_RAW_BASE_LINK_SOURCE_SHA256
        ),
        "v9f_base_does_not_bind_v2_proxy": (
            v9f_base.get("source_sha256")
            != source_pins["base_link_proxy_v2_stl"]["sha256"]
        ),
        "nine_cable_objects_require_unemitted_capsules": (
            len(cable_objects) == 9 and len(missing_capsules) == 9
        ),
        "system_registry_remains_150_objects": len(registry.get("objects", [])) == 150,
        "collision_gate_registry_hash_cross_binding_matches": (
            collision_gate.get("system_registry", {})
            .get("artifacts", {})
            .get("registry", {})
            .get("sha256")
            == source_pins["system_registry"]["sha256"]
        ),
        "system_pair_universe_remains_11175": (
            collision_gate.get("system_registry", {}).get("pair_count") == 11175
        ),
        "system_unassessed_pairs_remain_11166": (
            collision_gate.get("system_registry", {}).get(
                "unassessed_fail_closed_pair_count"
            )
            == 11166
        ),
        "complete_system_collision_pass_remains_false": (
            collision_gate.get("complete_system_collision_pass") is False
        ),
        "path_search_executed_remains_false": (
            collision_gate.get("path_search_executed") is False
        ),
    }
    if not all(checks.values()):
        failures = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"query infrastructure gate checks failed: {failures}")

    gate = {
        "schema": "ODR60_OPTION_A_QUERY_INFRASTRUCTURE_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": (
            "STATIC_AND_SYNTHETIC_METHOD_EVIDENCE_ONLY__"
            "NO_CURRENT_GEOMETRY_PAIR_EDGE_OR_PATH_AUTHORITY"
        ),
        "review_status": "PENDING_OWNER_REVIEW",
        "source_pins": source_pins,
        "validation": {
            "pytest": f"{test_count}/{test_count} PASS",
            "static_audit": "PASS",
            "current_geometry_loaded": False,
            "current_exact_q_query_executed": False,
            "binary64_golden_parity_executed": False,
            "accepted_run_authority_pin_present": False,
        },
        "checks": checks,
        "exact_q_adapter": {
            "implementation_status": (
                "STATIC_FIXTURES_PASS_ONLY__CURRENT_EXECUTION_AUTHORITY_PIN_ABSENT"
            ),
            "scope": "ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY",
            "v9f_source_sha256": source_pins["v9f_source"]["sha256"],
            "mesh_manifest_sha256": source_pins["v9f_mesh_manifest"]["sha256"],
            "mesh_base_link_source_sha256": v9f_base.get("source_sha256"),
            "v2_base_link_operational_proxy_bound": False,
            "centerline_sample_spacing_mm": 1.5,
            "centerline_spatial_discretization_allowance_bound": None,
            "system_pair_ids_returned": False,
            "caller_supplied_memory_gate_boolean_accepted": False,
            "single_run_consumption_receipt_required": True,
            "system_pair_evaluation_authorized": False,
        },
        "continuous_edge_method": {
            "implementation_status": "STATIC_FIXTURES_PASS_ONLY__SYSTEM_BINDING_HOLD",
            "method": (
                "RECURSIVE_LINEAR_Q_EDGE_MIDPOINT_SUBDIVISION_WITH_"
                "CERTIFIED_RELATIVE_CLEARANCE_LIPSCHITZ_BOUND"
            ),
            "relative_bound_requires_sum_of_both_object_contributions": True,
            "threshold_contact_is_never_safe": True,
            "unknown_is_never_safe": True,
            "oracle_fail_can_never_certify_safe": True,
            "negative_required_clearance_rejected": True,
            "nonnumeric_oracle_or_bound_fails_closed": True,
            "system_bound_requires_pair_geometry_scene_acm_oracle_domain_binding": True,
            "current_system_pair_oracle_bound": False,
            "current_hash_bound_per_object_motion_coefficients": False,
            "system_edge_evaluated": False,
        },
        "system_collision_state": {
            "known_active_object_count": 150,
            "pair_count": 11175,
            "excepted_pair_count": 9,
            "unassessed_fail_closed_pair_count": 11166,
            "cable_object_count": len(cable_objects),
            "cable_capsule_chain_preemitted_count": 0,
            "complete_system_collision_pass": False,
        },
        "remaining_binding_blockers": [
            "CURRENT_V9F_HARNESS_QUERY_USES_LEGACY_RAW_BASE_LINK_NOT_V2_PROXY",
            "NINE_HARNESS_OBJECT_CAPSULE_CHAINS_OR_SPATIAL_DISCRETIZATION_BOUND_ABSENT",
            "PER_PAIR_EXACT_OR_CONSERVATIVE_LOWER_BOUND_API_ABSENT",
            "HASH_BOUND_PER_OBJECT_PER_JOINT_GLOBAL_MOTION_COEFFICIENTS_ABSENT",
            "M01_DISCRETE_SCENE_STATE_AND_COMPLETE_ACM_BINDING_ABSENT",
            "11166_NON_EXCEPTED_SYSTEM_COLLISION_PAIRS_UNASSESSED_FAIL_CLOSED",
            "CURRENT_V9F_BINARY64_GOLDEN_PARITY_NOT_EXECUTED",
            "OWNER_OPTION_A_AND_RUN_SPECIFIC_EXECUTION_AUTHORITY_ABSENT",
            "RUNTIME_MEMORY_NOT_NOMINALLY_ADMITTED",
        ],
        "legal_current_operation": "STATIC_AUDIT_AND_SYNTHETIC_FIXTURES_ONLY",
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "QUERY_INFRASTRUCTURE_STATIC_FIXTURES_PASS_ONLY__METHOD_SYSTEM_BINDING_HOLD__"
            "FROZEN_V9F_HARNESS_BINARY64_PARITY_NOT_EXECUTED__"
            "SYSTEM_PAIR_ORACLE_AND_MOTION_BOUNDS_ABSENT__"
            "NO_PAIR_EDGE_PATH_OR_RELEASE_AUTHORITY"
        ),
    }
    gate_bytes = json_bytes(gate)

    manifest_rows = []
    virtual_artifacts = {
        f"{PACKAGE_REL}/{AUDIT_NAME}": audit_bytes,
        f"{PACKAGE_REL}/{GATE_NAME}": gate_bytes,
    }
    manifest_inputs = [*REL.values(), *virtual_artifacts]
    for rel_path in manifest_inputs:
        artifact = (
            pin_bytes(rel_path, virtual_artifacts[rel_path])
            if rel_path in virtual_artifacts
            else pin(rel_path)
        )
        manifest_rows.append(
            {
                "path": rel_path,
                "sha256": artifact["sha256"],
                "bytes": artifact["bytes"],
            }
        )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["path", "sha256", "bytes"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(manifest_rows)
    manifest_bytes = buffer.getvalue().encode("utf-8")

    outputs = {
        HERE / AUDIT_NAME: audit_bytes,
        HERE / GATE_NAME: gate_bytes,
        HERE / MANIFEST_NAME: manifest_bytes,
    }
    temporary_paths: list[Path] = []
    try:
        for target, payload in outputs.items():
            temporary = target.with_name(f".{target.name}.tmp")
            temporary.write_bytes(payload)
            temporary_paths.append(temporary)
        for target in outputs:
            os.replace(target.with_name(f".{target.name}.tmp"), target)
    finally:
        for temporary in temporary_paths:
            if temporary.exists():
                temporary.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
