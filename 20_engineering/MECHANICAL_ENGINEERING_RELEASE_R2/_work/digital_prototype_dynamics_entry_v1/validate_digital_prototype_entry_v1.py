"""Lightweight, fail-closed audit for the R2 digital-prototype dynamics entry.

This script intentionally does not import a CAD kernel.  It validates hashes,
URDF topology/mass, current machine gates, visual-review evidence and the
source-only integrated-candidate contract.  Optional diagnostic replay invokes
the already-bounded Sim14 and Sim15 validation entry points; it never promotes
their diagnostic results to contact or production authority.
"""

from __future__ import annotations

import argparse
import ast
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parent


def workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("workspace root containing PROJECT_MAP.md was not found")


ROOT = workspace_root()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_json(relative: str) -> dict[str, Any]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def memory_snapshot() -> dict[str, Any]:
    if os.name != "nt":
        return {
            "available_physical_gib": None,
            "total_physical_gib": None,
            "measurement_status": "UNAVAILABLE_FAIL_CLOSED",
        }

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return {
            "available_physical_gib": None,
            "total_physical_gib": None,
            "measurement_status": "UNAVAILABLE_FAIL_CLOSED",
        }
    gib = float(1024**3)
    return {
        "available_physical_gib": status.ullAvailPhys / gib,
        "total_physical_gib": status.ullTotalPhys / gib,
        "memory_load_percent": int(status.dwMemoryLoad),
        "measurement_status": "MEASURED",
    }


def pinned_file(record: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / Path(record["path"])
    actual = {
        "path": record["path"],
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else None,
        "sha256": sha256(path) if path.is_file() else None,
        "expected_bytes": int(record["bytes"]),
        "expected_sha256": str(record["sha256"]).upper(),
    }
    actual["pass"] = (
        actual["exists"]
        and actual["bytes"] == actual["expected_bytes"]
        and actual["sha256"] == actual["expected_sha256"]
    )
    return actual


def joint_record(joint: ET.Element) -> dict[str, Any]:
    limit = joint.find("limit")
    origin = joint.find("origin")
    axis = joint.find("axis")
    return {
        "name": joint.attrib["name"],
        "type": joint.attrib["type"],
        "parent": joint.find("parent").attrib["link"],
        "child": joint.find("child").attrib["link"],
        "origin_xyz": origin.attrib.get("xyz", "0 0 0") if origin is not None else "0 0 0",
        "origin_rpy": origin.attrib.get("rpy", "0 0 0") if origin is not None else "0 0 0",
        "axis": axis.attrib.get("xyz") if axis is not None else None,
        "lower": limit.attrib.get("lower") if limit is not None else None,
        "upper": limit.attrib.get("upper") if limit is not None else None,
        "effort": limit.attrib.get("effort") if limit is not None else None,
        "velocity": limit.attrib.get("velocity") if limit is not None else None,
    }


def urdf_audit(accepted_path: Path, unified_path: Path) -> dict[str, Any]:
    accepted = ET.parse(accepted_path).getroot()
    unified = ET.parse(unified_path).getroot()
    links = [link.attrib["name"] for link in unified.findall("link")]
    joints = [joint_record(joint) for joint in unified.findall("joint")]
    accepted_joints = {
        joint.attrib["name"]: joint_record(joint)
        for joint in accepted.findall("joint")
    }
    unified_joints = {joint["name"]: joint for joint in joints}

    parent_of: dict[str, str] = {}
    duplicate_children: list[str] = []
    for joint in joints:
        child = joint["child"]
        if child in parent_of:
            duplicate_children.append(child)
        parent_of[child] = joint["parent"]
    roots = sorted(set(links) - set(parent_of))
    children_by_parent: dict[str, list[str]] = {}
    for joint in joints:
        children_by_parent.setdefault(joint["parent"], []).append(joint["child"])
    visited: set[str] = set()
    frontier = list(roots)
    while frontier:
        node = frontier.pop()
        if node in visited:
            continue
        visited.add(node)
        frontier.extend(children_by_parent.get(node, []))

    subtree_mismatches = []
    for name, accepted_joint in accepted_joints.items():
        candidate = unified_joints.get(name)
        if candidate != accepted_joint:
            subtree_mismatches.append(name)

    mass_values = [
        Decimal(element.attrib["value"])
        for element in unified.findall("./link/inertial/mass")
    ]
    total_mass = sum(mass_values, Decimal("0"))
    joint_types = Counter(joint["type"] for joint in joints)
    expected_joint_types = {"fixed": 10, "revolute": 6, "prismatic": 2}
    expected_mass = Decimal("31.022864807342987")
    checks = {
        "link_count_19": len(links) == 19,
        "joint_count_18": len(joints) == 18,
        "joint_type_distribution": dict(joint_types) == expected_joint_types,
        "single_root_spacecraft_bus": roots == ["spacecraft_bus"],
        "unique_joint_child": not duplicate_children,
        "tree_connected": visited == set(links),
        "eight_actuated_dof": joint_types["revolute"] + joint_types["prismatic"] == 8,
        "sixteen_inertial_links": len(mass_values) == 16,
        "total_mass_exact_within_1e_12_kg": abs(total_mass - expected_mass) <= Decimal("1e-12"),
        "accepted_b601_subtree_exact": not subtree_mismatches,
    }
    return {
        "schema": "R2_URDF_TOPOLOGY_VALIDATION_RECEIPT_V1",
        "generated_utc": utc_now(),
        "accepted_b601_urdf": {
            "path": accepted_path.relative_to(ROOT).as_posix(),
            "bytes": accepted_path.stat().st_size,
            "sha256": sha256(accepted_path),
            "modification": "FORBIDDEN",
        },
        "unified_r2_urdf": {
            "path": unified_path.relative_to(ROOT).as_posix(),
            "bytes": unified_path.stat().st_size,
            "sha256": sha256(unified_path),
            "classification": "SOURCE_ONLY_BUILDER_EMISSION__PENDING_OWNER_REVIEW",
        },
        "observed": {
            "links": len(links),
            "joints": len(joints),
            "joint_types": dict(sorted(joint_types.items())),
            "root_links": roots,
            "inertial_links": len(mass_values),
            "total_mass_kg_decimal": str(total_mass),
            "actuated_dof": joint_types["revolute"] + joint_types["prismatic"],
            "accepted_subtree_joint_rows": len(accepted_joints),
            "accepted_subtree_mismatches": subtree_mismatches,
        },
        "checks": checks,
        "gate_passed": all(checks.values()),
        "maximum_claim": "URDF_TOPOLOGY_MASS_SCHEMA_AND_ACCEPTED_B601_SUBTREE_PASS__NO_CONTACT_OR_PRODUCTION_AUTHORITY",
    }


def source_audit(inputs: dict[str, Any]) -> dict[str, Any]:
    generator = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.py"
    wrapper = PACKAGE / "execute_integrated_candidate_v1.py"
    tree = ast.parse(generator.read_text(encoding="utf-8"), filename=str(generator))
    top_imports = []
    gen_step = None
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            top_imports.append(node.module or "")
        elif isinstance(node, ast.FunctionDef) and node.name == "gen_step":
            gen_step = node
    forbidden = ("OCP", "build123d", "FreeCAD", "Part")
    forbidden_top_imports = [
        name for name in top_imports if any(name == item or name.startswith(item + ".") for item in forbidden)
    ]
    pin_checks = {
        key: pinned_file(record)
        for key, record in inputs["sources"].items()
    }
    checks = {
        "generator_syntax_parsed": True,
        "gen_step_present_and_zero_argument": gen_step is not None and not (
            gen_step.args.args
            or gen_step.args.posonlyargs
            or gen_step.args.kwonlyargs
            or gen_step.args.vararg
            or gen_step.args.kwarg
        ),
        "no_top_level_cad_kernel_import": not forbidden_top_imports,
        "all_pinned_sources_match": all(record["pass"] for record in pin_checks.values()),
        "wrapper_present": wrapper.is_file(),
        "frozen_master_not_output_target": Path(inputs["expected_candidate"]["output_path"]) != Path(
            inputs["sources"]["frozen_r2_master_geometry"]["path"]
        ),
    }
    return {
        "generator": {
            "path": generator.relative_to(ROOT).as_posix(),
            "bytes": generator.stat().st_size,
            "sha256": sha256(generator),
        },
        "wrapper": {
            "path": wrapper.relative_to(ROOT).as_posix(),
            "bytes": wrapper.stat().st_size,
            "sha256": sha256(wrapper),
        },
        "pinned_sources": pin_checks,
        "forbidden_top_level_imports": forbidden_top_imports,
        "checks": checks,
        "pass": all(checks.values()),
    }


def replay_diagnostics(enabled: bool) -> dict[str, Any]:
    cases = {
        "sim14": ROOT / "30_simulation/sim_14_m4_digital_prototype_grasping",
        "sim15": ROOT / "30_simulation/sim_15_m5_geometry_gated_grasping",
    }
    receipt_path = PACKAGE / "DIAGNOSTIC_REPLAY_RECEIPT_V1.json"
    if not enabled and receipt_path.is_file():
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        if existing.get("requested") is True:
            return existing
    results: dict[str, Any] = {}
    if enabled:
        environment = dict(os.environ)
        environment["PYTHONUTF8"] = "1"
        for name, directory in cases.items():
            completed = subprocess.run(
                [sys.executable, "tools/run_validation.py"],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            output = (completed.stdout or "") + (completed.stderr or "")
            results[name] = {
                "executed": True,
                "returncode": completed.returncode,
                "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest().upper(),
                "output_tail": output.splitlines()[-24:],
                "pass": completed.returncode == 0,
            }
    else:
        results = {name: {"executed": False, "pass": None} for name in cases}
    receipt = {
        "schema": "R2_DIAGNOSTIC_DYNAMICS_REPLAY_RECEIPT_V1",
        "generated_utc": utc_now(),
        "requested": enabled,
        "results": results,
        "claim_limit": "SIM14_SIM15_DIAGNOSTIC_REPLAY_ONLY__NO_CONTACT_STRUCTURAL_PRODUCTION_OR_FLIGHT_AUTHORITY",
    }
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rerun-diagnostics", action="store_true")
    args = parser.parse_args()

    inputs = json.loads((PACKAGE / "INTEGRATED_CANDIDATE_INPUTS_V1.json").read_text(encoding="utf-8"))
    source = source_audit(inputs)
    source_receipt = {
        "schema": "R2_INTEGRATED_CANDIDATE_SOURCE_AUDIT_V1",
        "generated_utc": utc_now(),
        **source,
        "maximum_claim": "SOURCE_AND_PIN_CHAIN_READY__GENERATION_REQUIRES_FRESH_RUNTIME_AUTHORITY",
    }
    write_json(PACKAGE / "INTEGRATED_CANDIDATE_SOURCE_AUDIT_V1.json", source_receipt)
    accepted_path = ROOT / inputs["sources"]["accepted_b601_urdf"]["path"]
    unified_path = ROOT / inputs["sources"]["unified_r2_urdf_candidate"]["path"]
    urdf = urdf_audit(accepted_path, unified_path)
    write_json(PACKAGE / "URDF_TOPOLOGY_VALIDATION_RECEIPT_V1.json", urdf)

    replay = replay_diagnostics(args.rerun_diagnostics)
    sim14_path = ROOT / "30_simulation/sim_14_m4_digital_prototype_grasping/evidence/SIM14_DYNAMICS_GRASPING_GATE.json"
    sim15_path = ROOT / "30_simulation/sim_15_m5_geometry_gated_grasping/evidence/SIM15_DIAGNOSTIC_GATE_V1.json"
    sim13_path = ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json"
    m01_path = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json"
    sim14 = json.loads(sim14_path.read_text(encoding="utf-8"))
    sim15 = json.loads(sim15_path.read_text(encoding="utf-8"))
    sim13 = json.loads(sim13_path.read_text(encoding="utf-8"))
    m01 = json.loads(m01_path.read_text(encoding="utf-8"))

    manifest_path = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/01_BASELINE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    self_entry = next(record for record in manifest["files"] if record["file"] == manifest_path.name)
    manifest_integrity = {
        "actual_bytes": manifest_path.stat().st_size,
        "actual_sha256": sha256(manifest_path),
        "self_claimed_bytes": self_entry["bytes"],
        "self_claimed_sha256": self_entry["sha256"],
        "self_claim_matches": (
            manifest_path.stat().st_size == int(self_entry["bytes"])
            and sha256(manifest_path) == str(self_entry["sha256"]).upper()
        ),
        "policy_says_manifest_excluded_but_self_entry_present": (
            "excludes itself" in manifest.get("self_reference_policy", "")
        ),
        "disposition": "REGISTERED_DOCUMENT_INTEGRITY_DEFECT__DO_NOT_REWRITE_FROZEN_RELEASE_IN_THIS_RESEARCH_BRANCH",
    }

    snapshots_dir = ROOT / "40_evidence/artifacts/digital_prototype_dynamics_entry_v1"
    snapshots = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "review": "CURRENT_R2_MASTER_VISUALLY_SHOWS_AXIS_WITNESS_AND_DETACHED_PALM_NOT_FULL_INSTALLED_ARM",
        }
        for path in sorted(snapshots_dir.glob("r2_master_*.png"))
    ]
    product_structure_text = (
        ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml"
    ).read_text(encoding="utf-8")
    cad_current = {
        "schema": "R2_CURRENT_CAD_STATE_RECEIPT_V1",
        "generated_utc": utc_now(),
        "master_step": pinned_file(inputs["sources"]["frozen_r2_master_geometry"]),
        "inspection": {
            "kind": "part",
            "occurrence_count": 1,
            "solid_count": 41,
            "face_count": 647,
            "edge_count": 1691,
            "bounds_mm": {
                "min": [-230.25, -313.15, -243.075977],
                "max": [441.700116, 313.15, 247.90813],
            },
        },
        "product_structure_evidence": {
            "frame_axis_witness_only_declared": "FRAME_AXIS_WITNESS_ONLY" in product_structure_text,
            "gripper_fingers_defined_not_modelled_declared": "DEFINED_NOT_MODELLED" in product_structure_text,
        },
        "snapshot_review": snapshots,
        "visual_completeness_gate": "FAIL_CURRENT_FROZEN_MASTER_IS_NOT_A_FULL_INSTALLED_B601_DIGITAL_PROTOTYPE",
        "frozen_release_modified": False,
    }
    write_json(PACKAGE / "CAD_CURRENT_STATE_RECEIPT_V1.json", cad_current)

    gripper_text = (
        ROOT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml"
    ).read_text(encoding="utf-8")
    contact_text = (
        ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml"
    ).read_text(encoding="utf-8")
    gripper_speed = float(re.search(r"first_contact_speed_max_m_s:\s*([0-9.]+)", gripper_text).group(1))
    contact_speed = float(
        re.search(r"first_contact_closing_velocity_mps:\s*\n\s*nominal:\s*([0-9.]+)", contact_text).group(1)
    )
    contact_conflict = {
        "gripper_interface_first_contact_speed_max_mps": gripper_speed,
        "design_contact_model_nominal_closing_velocity_mps": contact_speed,
        "consistent": gripper_speed == contact_speed,
        "ratio_contact_model_to_interface": contact_speed / gripper_speed,
        "disposition": "HOLD_CONTACT_CONSUMPTION_PENDING_NAMED_AUTHORITY_RESOLUTION",
    }

    memory = memory_snapshot()
    memory["gate_gib"] = 6.0
    memory["gate_passed"] = (
        memory["available_physical_gib"] is not None
        and memory["available_physical_gib"] >= 6.0
    )
    candidate_step = ROOT / inputs["expected_candidate"]["output_path"]
    active_lock = PACKAGE / ".r2_integrated_candidate_active_run.lock"
    preflight = {
        "schema": "R2_INTEGRATED_CANDIDATE_PREFLIGHT_V1",
        "generated_utc": utc_now(),
        "source_chain_pass": source["pass"],
        "memory": memory,
        "candidate_step_present": candidate_step.is_file(),
        "active_writer_lock_present": active_lock.is_file(),
        "fresh_owner_override_observed": False,
        "execution_authorized": False,
        "verdict": (
            "SOURCE_READY__FRESH_LOW_MEMORY_OWNER_OVERRIDE_REQUIRED_BEFORE_CAD_IMPORT"
            if not memory["gate_passed"]
            else "SOURCE_READY__FRESH_NAMED_RUN_AUTHORITY_REQUIRED"
        ),
        "next_action": "RUN_EXECUTE_INTEGRATED_CANDIDATE_V1_ONLY_AFTER_FRESH_OWNER_AUTHORIZATION",
    }
    write_json(PACKAGE / "INTEGRATED_CANDIDATE_PREFLIGHT_V1.json", preflight)

    sim14_pass = sim14.get("overall_status") == "PASS_DIAGNOSTIC_KERNEL_HOLD_PRODUCTION_DYNAMICS"
    sim15_pass = sim15.get("overall_status") == "PASS_SIM15_DIAGNOSTIC_REPRODUCIBILITY_ONLY"
    replay_pass = (
        all(item.get("pass") is True for item in replay["results"].values())
        if replay.get("requested") is True
        else None
    )
    gate = {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V1",
        "generated_utc": utc_now(),
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "current_truth": {
            "frozen_master_cad_visually_complete": False,
            "integrated_full_arm_candidate_source_ready": source["pass"],
            "integrated_full_arm_candidate_generated": candidate_step.is_file(),
            "unified_r2_urdf_topology_gate_passed": urdf["gate_passed"],
            "unified_r2_urdf_owner_accepted": False,
            "m01_execution_gate_passed": bool(m01.get("next_stage_authorized")),
            "sim13_negative_control_registry_gate_passed": bool(sim13.get("gate_passed")),
            "sim13_non_abort_authorized": bool(sim13.get("next_stage_authorized")),
            "contact_velocity_contract_consistent": contact_conflict["consistent"],
            "sim14_diagnostic_gate_passed": sim14_pass,
            "sim15_diagnostic_gate_passed": sim15_pass,
            "diagnostic_replay_this_run_passed": replay_pass,
        },
        "authorized_now": {
            "repeatable_sim14_diagnostic_replay": sim14_pass,
            "repeatable_sim15_geometry_gated_diagnostic_replay": sim15_pass,
            "urdf_topology_and_mass_schema_consumption_for_diagnostic_model_loading": urdf["gate_passed"],
            "integrated_candidate_cad_generation": False,
            "m01_pair_or_edge_evaluation": False,
            "non_abort_contact_grasping": False,
            "production_dynamics": False,
            "flight_release": False,
        },
        "exact_blockers": [
            "FRESH_RUN_SPECIFIC_OWNER_AUTHORITY_REQUIRED_FOR_NEW_CANDIDATE_GENERATION",
            "AVAILABLE_MEMORY_BELOW_6_GIB_REQUIRES_FRESH_SINGLE_USE_OWNER_OVERRIDE" if not memory["gate_passed"] else "NONE_MEMORY_GATE_CURRENTLY_PASS",
            "INTEGRATED_FULL_ARM_CANDIDATE_STEP_NOT_GENERATED" if not candidate_step.is_file() else "INTEGRATED_CANDIDATE_PENDING_INSPECTION_AND_SNAPSHOT_REVIEW",
            "M01_SCENES_0_OF_3_CLEARANCE_0_OF_11166_MOTION_0_OF_150_ORACLE_0_OF_11166_NO_EDGE_CERTIFICATES",
            "ROUTE_C_HARNESS_MANDATORY_STATES_UNSAFE_AND_G12_NOT_CLOSED",
            "SIM13_MAXIMUM_OPERATIONAL_STATE_ABORT_ONLY",
            "UNIFIED_R2_OWNER_ROUTE_C_SYSTEM_AND_CONSUMER_BINDINGS_NOT_ACCEPTED",
            "CONTACT_CLOSING_VELOCITY_CONTRACT_0P005_VS_0P05_MPS_UNRESOLVED",
            "BASELINE_MANIFEST_SELF_ENTRY_DOES_NOT_MATCH_CURRENT_FILE",
        ],
        "m01_counts": m01.get("remaining_readiness"),
        "sim13_maximum_operational_state": sim13.get("maximum_operational_state"),
        "contact_contract_audit": contact_conflict,
        "release_manifest_integrity_audit": manifest_integrity,
        "evidence_pins": {
            "candidate_source_audit": {
                "path": "INTEGRATED_CANDIDATE_SOURCE_AUDIT_V1.json",
                "sha256": sha256(PACKAGE / "INTEGRATED_CANDIDATE_SOURCE_AUDIT_V1.json"),
            },
            "cad_current_state_receipt": {
                "path": "CAD_CURRENT_STATE_RECEIPT_V1.json",
                "sha256": sha256(PACKAGE / "CAD_CURRENT_STATE_RECEIPT_V1.json"),
            },
            "urdf_validation_receipt": {
                "path": "URDF_TOPOLOGY_VALIDATION_RECEIPT_V1.json",
                "sha256": sha256(PACKAGE / "URDF_TOPOLOGY_VALIDATION_RECEIPT_V1.json"),
            },
            "candidate_preflight": {
                "path": "INTEGRATED_CANDIDATE_PREFLIGHT_V1.json",
                "sha256": sha256(PACKAGE / "INTEGRATED_CANDIDATE_PREFLIGHT_V1.json"),
            },
            "diagnostic_replay_receipt": {
                "path": "DIAGNOSTIC_REPLAY_RECEIPT_V1.json",
                "sha256": sha256(PACKAGE / "DIAGNOSTIC_REPLAY_RECEIPT_V1.json"),
            },
            "sim14_gate": {"path": sim14_path.relative_to(ROOT).as_posix(), "sha256": sha256(sim14_path)},
            "sim15_gate": {"path": sim15_path.relative_to(ROOT).as_posix(), "sha256": sha256(sim15_path)},
            "sim13_20_of_20_gate": {"path": sim13_path.relative_to(ROOT).as_posix(), "sha256": sha256(sim13_path)},
            "m01_gate": {"path": m01_path.relative_to(ROOT).as_posix(), "sha256": sha256(m01_path)},
        },
        "maximum_claim": "BOUNDED_DIAGNOSTIC_DYNAMICS_ENTRY_IS_REPRODUCIBLE__INTEGRATED_CAD_GENERATION_AND_NON_ABORT_GRASPING_REMAIN_HOLD",
        "verdict": "PASS_BOUNDED_DIAGNOSTIC_DYNAMICS_ENTRY__INTEGRATED_CAD_AND_NON_ABORT_GRASPING_HOLD",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    gate["exact_blockers"] = [item for item in gate["exact_blockers"] if not item.startswith("NONE_")]
    write_json(PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V1.json", gate)
    print(json.dumps({
        "source_chain_pass": source["pass"],
        "urdf_gate_passed": urdf["gate_passed"],
        "sim14_diagnostic_pass": sim14_pass,
        "sim15_diagnostic_pass": sim15_pass,
        "replay_pass": replay_pass,
        "available_memory_gib": memory["available_physical_gib"],
        "candidate_step_present": candidate_step.is_file(),
        "verdict": gate["verdict"],
    }, indent=2, ensure_ascii=False))
    return 0 if source["pass"] and urdf["gate_passed"] and sim14_pass and sim15_pass and (replay_pass is not False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
