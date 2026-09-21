"""Independent fail-closed validation for the M4 digital-prototype package.

This validates artifact integrity and the honesty of expected HOLD states.  A
zero exit code does not issue structural, production-dynamics, manufacturing,
qualification, or flight authority.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import yaml


M4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = M4_ROOT.parents[1]
SIM14_ROOT = PROJECT_ROOT / "30_simulation" / "sim_14_m4_digital_prototype_grasping"
RECEIPT = M4_ROOT / "11_validation" / "M4_INDEPENDENT_VALIDATION_RECEIPT_V1.json"

CONFIGURATION_IDS = (
    "DEPLOYED_NOMINAL",
    "LEFT_PANEL_FAIL",
    "RIGHT_PANEL_FAIL",
    "BOTH_PANEL_FAIL",
    "ARM_STOWED_ONORBIT",
    "ARM_TASK_READY",
    "PREGRASP",
    "TARGET_CAPTURE_22KG",
    "TARGET_CAPTURE_150KG",
)
CONFIGURATION_FIELDS = (
    "mass",
    "cg",
    "inertia",
    "bbox",
    "frames",
    "collision",
    "confidence",
    "status",
)

CORE_FILES = (
    "README.md",
    "00_authority/M4_PHASE_AUTHORITY_AND_BOUNDARY.yaml",
    "00_authority/M4_LOOP_ENGINEERING_CONTROL_V1.yaml",
    "00_authority/M4_COMPOSITION_AND_MASS_BOUNDARY_DECISION.yaml",
    "00_authority/M4_ENGINEERING_RESEARCH_AND_VERIFICATION_METHOD.md",
    "00_authority/M4_ECR_REGISTER_V1.csv",
    "00_authority/M4_INPUT_SOURCE_REGISTER.csv",
    "00_authority/M4_EXTERNAL_REFERENCE_REGISTER.csv",
    "00_authority/M4_FROZEN_INPUT_MANIFEST_V1.json",
    "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
    "02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.FCStd",
    "02_parameterized_cad/SEI_DIGITAL_PROTOTYPE_V1.step",
    "02_parameterized_cad/DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json",
    "02_parameterized_cad/DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1.json",
    "02_parameterized_cad/DIGITAL_PROTOTYPE_COLLISION_ASSET_REGISTER_V1.yaml",
    "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
    "03_mass_properties/M4_MASS_MATERIAL_TOLERANCE_MECHANISM_AUDIT_V1.json",
    "04_material_database/PROTOTYPE_MATERIAL_LIBRARY_V1.yaml",
    "04_material_database/MATERIAL_PROCESS_CLOSURE_STATUS_V2.yaml",
    "05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml",
    "05_tolerance/HINGE_DEPLOYMENT_TOLERANCE_CHAIN_V1.yaml",
    "05_tolerance/GRIPPER_FUNCTIONAL_TOLERANCE_MAP_V1.yaml",
    "05_tolerance/TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml",
    "06_mechanism/MECHANISM_STATUS_REGISTER_V1.yaml",
    "06_mechanism/GRIPPER_R1_MECHANISM_RELEASE_STATUS_V2.yaml",
    "06_mechanism/HDRM_PROTOTYPE_CLOSURE_PLAN_V1.yaml",
    "06_mechanism/MECHANISM_VERIFICATION_REQUIREMENTS_V1.csv",
    "07_structural_model/STRUCTURAL_ANALYSIS_ENTRY_GATE.json",
    "07_structural_model/STRUCTURAL_MODEL_PLAN_V1.yaml",
    "08_simulation_assets/MECH_RL_INTERFACE_V2.yaml",
    "08_simulation_assets/SIM14_ASSET_HANDOFF_REGISTER_V1.csv",
    "11_validation/B601_NAMED_POSE_REVALIDATION_V1.json",
    "11_validation/M4_ROOT_FREECAD_COLD_REOPEN_RECEIPT_V1.json",
    "11_validation/URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json",
    "12_release/M4_REQUIREMENTS_VERIFICATION_MATRIX_V1.csv",
    "12_release/M4_NEXT_LOOP_ACTION_REGISTER_V1.yaml",
    "12_release/M4_RELEASE_SUMMARY.md",
    "12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json",
)


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_unique_mapping(
    loader: UniqueKeyLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    output: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in output:
            raise ValueError(f"duplicate YAML key: {key!r}")
        output[key] = loader.construct_object(value_node, deep=deep)
    return output


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_yaml(path: Path) -> Mapping[str, Any]:
    value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    if not isinstance(value, Mapping):
        raise ValueError("root is not a mapping")
    return value


def load_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("root is not a mapping")
    return value


def close(left: float, right: float, tolerance: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=tolerance)


def main() -> int:
    checks: list[dict[str, Any]] = []

    def add(
        check_id: str,
        passed: bool,
        detail: str,
        evidence: str | None = None,
    ) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
                "evidence": evidence,
            }
        )

    # Required artifacts and structured-file parseability.
    missing = [relative for relative in CORE_FILES if not (M4_ROOT / relative).is_file()]
    empty = [
        relative
        for relative in CORE_FILES
        if (M4_ROOT / relative).is_file() and (M4_ROOT / relative).stat().st_size <= 0
    ]
    add(
        "M4-V-001-CORE-ARTIFACTS",
        not missing and not empty,
        f"missing={missing}; empty={empty}",
        str(M4_ROOT),
    )

    parse_failures: list[str] = []
    structured_count = 0
    for path in sorted(M4_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                load_yaml(path)
                structured_count += 1
            elif path.suffix.lower() == ".json":
                load_json(path)
                structured_count += 1
            elif path.suffix.lower() == ".csv":
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    rows = list(csv.reader(stream))
                if not rows:
                    raise ValueError("empty CSV")
                structured_count += 1
        except Exception as exc:  # evidence receipt must retain every parse defect
            parse_failures.append(f"{path.relative_to(M4_ROOT).as_posix()}: {exc}")
    add(
        "M4-V-002-STRUCTURED-PARSE",
        not parse_failures,
        f"parsed={structured_count}; failures={parse_failures}",
        str(M4_ROOT),
    )

    # Generation timestamps are evidence, not decorative metadata.  Reject
    # timezone-free or future-dated records instead of silently accepting a
    # chronology that cannot have occurred on the validating host.
    future_timestamps: list[str] = []
    invalid_timestamps: list[str] = []
    validation_now = datetime.now().astimezone()
    for path in sorted(M4_ROOT.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        try:
            record = load_yaml(path) if path.suffix.lower() in {".yaml", ".yml"} else load_json(path)
            raw_timestamp = record.get("generated_local")
            if raw_timestamp is None:
                continue
            parsed_timestamp = datetime.fromisoformat(str(raw_timestamp))
            if parsed_timestamp.tzinfo is None:
                invalid_timestamps.append(
                    f"{path.relative_to(M4_ROOT).as_posix()}: timezone missing"
                )
            elif parsed_timestamp > validation_now + timedelta(minutes=5):
                future_timestamps.append(
                    f"{path.relative_to(M4_ROOT).as_posix()}: {raw_timestamp}"
                )
        except Exception as exc:
            invalid_timestamps.append(
                f"{path.relative_to(M4_ROOT).as_posix()}: {exc}"
            )
    add(
        "M4-V-007-EVIDENCE-CHRONOLOGY",
        not future_timestamps and not invalid_timestamps,
        f"future={future_timestamps}; invalid={invalid_timestamps}",
        str(M4_ROOT),
    )

    # Frozen source integrity, including predecessor M3 and Sim13 trees.
    frozen_path = M4_ROOT / "00_authority" / "M4_FROZEN_INPUT_MANIFEST_V1.json"
    frozen = load_json(frozen_path) if frozen_path.is_file() else {}
    source_mismatches: list[dict[str, str]] = []
    for record in frozen.get("files", []):
        raw = str(record.get("path", ""))
        candidate = Path(raw)
        source = candidate if candidate.is_absolute() else PROJECT_ROOT / candidate
        actual = sha256_file(source) if source.is_file() else "MISSING"
        expected = str(record.get("sha256", "")).upper()
        if actual != expected:
            source_mismatches.append(
                {"path": raw, "expected": expected, "actual": actual}
            )
    frozen_pass = (
        frozen.get("status") == "PASS"
        and frozen.get("missing_count") == 0
        and frozen.get("duplicate_path_count") == 0
        and not source_mismatches
    )
    add(
        "M4-V-003-FROZEN-INPUT-INTEGRITY",
        frozen_pass,
        f"records={len(frozen.get('files', []))}; mismatches={source_mismatches}",
        str(frozen_path),
    )
    frozen_paths = {str(record.get("path", "")) for record in frozen.get("files", [])}
    local_reference_pattern = re.compile(
        r"(?:path|source|source_validation|local_candidate_matrix):\s+"
        r"((?:20_engineering|30_simulation)/[^,\]\}]+)"
    )
    external_references: set[str] = set()
    for path in sorted(M4_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {
            ".yaml", ".yml", ".json", ".md", ".csv"
        }:
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            match = local_reference_pattern.search(line)
            if not match:
                continue
            reference = match.group(1).strip(" '\"")
            if reference.startswith(
                "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/"
            ) or reference.startswith(
                "30_simulation/sim_14_m4_digital_prototype_grasping/"
            ):
                continue
            external_references.add(reference)
    uncovered_references = sorted(external_references - frozen_paths)
    add(
        "M4-V-005-INPUT-REFERENCE-COVERAGE",
        not uncovered_references,
        f"external_references={len(external_references)}; uncovered={uncovered_references}",
        str(frozen_path),
    )
    source_register_path = M4_ROOT / "00_authority" / "M4_INPUT_SOURCE_REGISTER.csv"
    with source_register_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as source_stream:
        source_rows = list(csv.DictReader(source_stream))
    source_register_pass = bool(source_rows) and all(
        row.get("mutation_allowed") == "false"
        and row.get("status") == "HASH_FROZEN_PASS"
        and row.get("coverage_evidence")
        == "00_authority/M4_FROZEN_INPUT_MANIFEST_V1.json"
        for row in source_rows
    )
    add(
        "M4-V-006-INPUT-SOURCE-REGISTER-STATE",
        source_register_pass,
        f"rows={len(source_rows)}; statuses={[row.get('status') for row in source_rows]}",
        str(source_register_path),
    )
    ecr_path = M4_ROOT / "00_authority" / "M4_ECR_REGISTER_V1.csv"
    with ecr_path.open("r", encoding="utf-8-sig", newline="") as ecr_stream:
        ecr_rows = list(csv.DictReader(ecr_stream))
    correction_ecr = next(
        (row for row in ecr_rows if row.get("ecr_id") == "M4-ECR-011"), {}
    )
    ecr_correction_pass = (
        correction_ecr.get("status") == "ACCEPTED_FAIL_CLOSED_CORRECTION"
        and "11.7 mm to 6.7 mm" in str(correction_ecr.get("decision", ""))
        and "No master solid change" in str(correction_ecr.get("geometry_effect", ""))
        and "no production-physics promotion" in str(
            correction_ecr.get("simulation_effect", "")
        )
    )
    add(
        "M4-V-008-CORRECTION-CHANGE-CONTROL",
        ecr_correction_pass,
        f"M4-ECR-011={correction_ecr}",
        str(ecr_path),
    )

    authority = load_yaml(M4_ROOT / "00_authority" / "M4_PHASE_AUTHORITY_AND_BOUNDARY.yaml")
    memory = authority.get("memory_execution_authority", {})
    memory_truth = (
        memory.get("memory_gate_passed") is False
        and memory.get("owner_override_used") is True
        and memory.get("status") == "OWNER_OVERRIDE_LOW_MEMORY"
    )
    add(
        "M4-V-004-MEMORY-OVERRIDE-TRUTH",
        memory_truth,
        "6 GiB gate remains false; M4-OVR-001 must remain explicit",
        "00_authority/M4_PHASE_AUTHORITY_AND_BOUNDARY.yaml",
    )

    # Master assembly truth and composition boundary.
    build = load_json(M4_ROOT / "02_parameterized_cad" / "DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json")
    build_pass = (
        build.get("all_geometry_checks_pass") is True
        and build.get("formal_fea_performed") is False
        and build.get("memory_gate", {}).get("memory_gate_passed") is False
        and build.get("memory_gate", {}).get("owner_override_used") is True
        and build.get("fcstd_cold_reopen", {}).get("all_links_internal") is True
        and build.get("fcstd_cold_reopen", {}).get("all_source_shapes_valid") is True
        and build.get("step_cold_reopen", {}).get("valid") is True
    )
    add(
        "M4-V-010-MASTER-COLD-REOPEN",
        build_pass,
        f"verdict={build.get('verdict')}",
        "02_parameterized_cad/DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json",
    )
    unresolved_slots = set(build.get("unresolved_component_slots", []))
    load_bridge_explicit = any("LOAD_BRIDGE" in value for value in unresolved_slots)
    add(
        "M4-V-011-LOAD-BRIDGE-DISCONTINUITY",
        load_bridge_explicit,
        f"unresolved_slots={sorted(unresolved_slots)}",
        "02_parameterized_cad/DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json",
    )
    geometry = load_json(M4_ROOT / "02_parameterized_cad" / "DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1.json")
    geometry_truth = (
        str(geometry.get("verdict", "")).startswith("PASS_DIGITAL_PROTOTYPE_GEOMETRY")
        and geometry.get("system_interference_verdict")
        == "NOT_EVALUATED_NO_CONTINUOUS_OR_CONFIGURATION_COMPLETE_MODEL"
        and geometry.get("formal_fea_performed") is False
    )
    add(
        "M4-V-012-GEOMETRY-SCOPE",
        geometry_truth,
        f"verdict={geometry.get('verdict')}; system={geometry.get('system_interference_verdict')}",
        "02_parameterized_cad/DIGITAL_PROTOTYPE_GEOMETRY_AUDIT_V1.json",
    )

    frame_tree = load_yaml(
        M4_ROOT / "01_system_architecture" / "DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml"
    )
    assembly_alias = frame_tree.get("frame_aliases", {}).get(
        "spacecraft_assembly_frame", {}
    )
    identity_4 = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    frame_alias_pass = (
        frame_tree.get("root_frame") == "S"
        and assembly_alias.get("canonical_frame") == "S"
        and assembly_alias.get("relation") == "IDENTITY_EQUIVALENCE"
        and assembly_alias.get("T_S_spacecraft_assembly_frame_rows") == identity_4
        and str(assembly_alias.get("status", "")).startswith("FROZEN_")
    )
    add(
        "M4-V-013-ASSEMBLY-FRAME-ALIAS",
        frame_alias_pass,
        f"root={frame_tree.get('root_frame')}; alias={assembly_alias}",
        "01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
    )
    root_cold_receipt = load_json(
        M4_ROOT
        / "11_validation"
        / "M4_ROOT_FREECAD_COLD_REOPEN_RECEIPT_V1.json"
    )
    root_cold_pass = (
        root_cold_receipt.get("status") == "PASS_READ_ONLY_COLD_REOPEN"
        and root_cold_receipt.get("execution_mode")
        == "READ_ONLY_SINGLE_PROCESS_OWNER_OVERRIDE"
        and root_cold_receipt.get("memory_gate_passed") is False
        and root_cold_receipt.get("owner_override_used") is True
        and root_cold_receipt.get("formal_fea_performed") is False
        and root_cold_receipt.get("fcstd", {}).get("object_count") == 68
        and root_cold_receipt.get("fcstd", {}).get("app_link_count") == 6
        and root_cold_receipt.get("fcstd", {}).get("all_links_internal") is True
        and root_cold_receipt.get("fcstd", {}).get("all_source_shapes_valid") is True
        and root_cold_receipt.get("step", {}).get("solid_count") == 40
        and root_cold_receipt.get("step", {}).get("valid") is True
    )
    add(
        "M4-V-014-ROOT-FREECAD-READONLY-SMOKE",
        root_cold_pass,
        (
            f"fcstd={root_cold_receipt.get('fcstd')}; "
            f"step={root_cold_receipt.get('step')}"
        ),
        "11_validation/M4_ROOT_FREECAD_COLD_REOPEN_RECEIPT_V1.json",
    )

    # Exact nine-configuration schema and fail-closed release properties.
    config = load_yaml(M4_ROOT / "03_mass_properties" / "CONFIGURATION_LIBRARY_V1.yaml")
    configurations = list(config.get("configurations", []))
    names = tuple(item.get("name") for item in configurations)
    fields_complete = all(
        all(field in item for field in CONFIGURATION_FIELDS) for item in configurations
    )
    add(
        "M4-V-020-NINE-CONFIGURATIONS",
        names == CONFIGURATION_IDS and fields_complete,
        f"names={names}; required_fields_complete={fields_complete}",
        "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    )
    release_leaks: list[str] = []
    for item in configurations:
        name = str(item.get("name"))
        fields = (
            ("mass.released_value_kg", item.get("mass", {}).get("released_value_kg")),
            ("cg.released_xyz_m", item.get("cg", {}).get("released_xyz_m")),
            ("inertia.released_matrix_kg_m2", item.get("inertia", {}).get("released_matrix_kg_m2")),
            ("bbox.released_min_xyz_m", item.get("bbox", {}).get("released_min_xyz_m")),
            ("bbox.released_max_xyz_m", item.get("bbox", {}).get("released_max_xyz_m")),
            ("bbox.released_extent_xyz_m", item.get("bbox", {}).get("released_extent_xyz_m")),
        )
        for label, value in fields:
            if value is not None:
                release_leaks.append(f"{name}.{label}={value!r}")
        if item.get("collision", {}).get("whole_assembly_evaluated") is not False:
            release_leaks.append(f"{name}.collision.whole_assembly_evaluated")
        if "HOLD" not in str(item.get("status", "")):
            release_leaks.append(f"{name}.status={item.get('status')!r}")
    add(
        "M4-V-021-CONFIGURATION-FAIL-CLOSED",
        not release_leaks,
        f"release_leaks={release_leaks}",
        "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    )
    branch_b_values = [
        item.get("mass", {}).get("diagnostic_branches", {}).get("m3r_B_value_kg")
        for item in configurations
    ]
    expected_branch_b = [29.081436764691] * 7 + [51.081436764691, 179.081436764691]
    branch_b_pass = len(branch_b_values) == 9 and all(
        value is not None and close(value, expected)
        for value, expected in zip(branch_b_values, expected_branch_b)
    )
    add(
        "M4-V-022-DIAGNOSTIC-MASS-BRANCH",
        branch_b_pass,
        f"values={branch_b_values}; non-authoritative diagnostic values only",
        "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    )
    inertia_reference_count = sum(
        item.get("inertia", {}).get("reference_point")
        == "configuration_system_CG"
        for item in configurations
    )
    configuration_frame_count = sum(
        item.get("frames", {}).get("root") == "spacecraft_assembly_frame"
        for item in configurations
    )
    readiness_summary = config.get("summary", {})
    add(
        "M4-V-025-CONFIGURATION-FRAME-AND-INERTIA-CONTRACT",
        inertia_reference_count == 9
        and configuration_frame_count == 9
        and readiness_summary.get("numeric_mass_diagnostic_available_count") == 9
        and readiness_summary.get(
            "ready_for_full_mass_properties_diagnostic_loader_count"
        )
        == 0
        and readiness_summary.get("ready_for_production_dynamics_count") == 0,
        (
            f"inertia_reference_count={inertia_reference_count}; "
            f"configuration_frame_count={configuration_frame_count}; "
            f"summary={readiness_summary}"
        ),
        "03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    )

    mass = load_yaml(M4_ROOT / "03_mass_properties" / "SYSTEM_MASS_PROPERTIES_V3.yaml")
    mass_text = (M4_ROOT / "03_mass_properties" / "SYSTEM_MASS_PROPERTIES_V3.yaml").read_text(encoding="utf-8")
    obsolete_mass_claims = [
        token for token in ("DOUBLE_COUNT_RISK", "POSITIVE_OVERLAP") if token in mass_text
    ]
    add(
        "M4-V-023-MASS-BOUNDARY-REV2",
        not obsolete_mass_claims
        and (
            "legacy flange ownership" in mass_text.lower()
            or "legacy_flange_ownership" in mass_text.lower()
        )
        and (
            "load bridge" in mass_text.lower()
            or "load_bridge" in mass_text.lower()
        ),
        f"obsolete_claims={obsolete_mass_claims}",
        "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
    )
    adr_text = (
        M4_ROOT
        / "00_authority"
        / "M4_COMPOSITION_AND_MASS_BOUNDARY_DECISION.yaml"
    ).read_text(encoding="utf-8")
    add(
        "M4-V-024-LEGACY-FLANGE-DISPOSITION",
        "confirmation that the legacy flange is replaced by M3R" not in adr_text
        and "controlled legacy flange ownership and mass allocation" in adr_text
        and "controlled spacecraft load bridge geometry and mating datums" in adr_text,
        "No replacement semantics; architecture disposition and ownership remain explicit closure items",
        "00_authority/M4_COMPOSITION_AND_MASS_BOUNDARY_DECISION.yaml",
    )

    uncertainty_records: list[tuple[str, Mapping[str, Any]]] = []
    component_records = mass.get("component_records", {})
    for component_id, component in component_records.items():
        for quantity_id in ("center_of_mass", "inertia_about_own_com"):
            if quantity_id in component:
                uncertainty_records.append(
                    (f"{component_id}.{quantity_id}", component[quantity_id])
                )
    b601_record = component_records.get(
        "b601_complete_arm_including_gripper_urdf_links", {}
    )
    for quantity_id in (
        "zero_joint_diagnostic_properties",
        "named_pose_digital_properties",
    ):
        if quantity_id in b601_record:
            uncertainty_records.append((f"b601.{quantity_id}", b601_record[quantity_id]))
    bad_uncertainty_records = [
        name
        for name, record in uncertainty_records
        if record.get("distribution") is not None
        or record.get("degrees_of_freedom") is not None
        or record.get("source") != "component_source_ref"
    ]
    add(
        "M4-V-026-MASS-UNCERTAINTY-SCHEMA",
        len(uncertainty_records) == 14 and not bad_uncertainty_records,
        f"record_count={len(uncertainty_records)}; bad={bad_uncertainty_records}",
        "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml",
    )

    diagnostic_branches = mass.get("diagnostic_nonrelease_branches", {})
    declared_members = set(component_records) | set(
        mass.get("diagnostic_derived_components", {})
    )
    unresolved_branch_members = sorted(
        {
            member
            for branch in diagnostic_branches.values()
            if isinstance(branch, Mapping)
            for member in branch.get("members", [])
            if member not in declared_members
        }
    )
    branch_contract = diagnostic_branches.get("member_resolution_contract", {})
    pose_receipt = load_json(
        M4_ROOT / "11_validation" / "B601_NAMED_POSE_REVALIDATION_V1.json"
    )
    pose_status = pose_receipt.get("status")
    config_pose_status = config.get("diagnostic_pose_sources", {}).get(
        "M4_named_pose_revalidation", {}
    ).get("status")
    b601_pose_status = b601_record.get("named_pose_digital_properties", {}).get(
        "receipt_status"
    )
    add(
        "M4-V-027-MASS-BRANCH-AND-POSE-BINDING",
        not unresolved_branch_members
        and branch_contract.get("unresolved_member_count") == 0
        and pose_status == config_pose_status == b601_pose_status,
        (
            f"unresolved_members={unresolved_branch_members}; "
            f"pose_statuses={[pose_status, config_pose_status, b601_pose_status]}"
        ),
        "03_mass_properties/SYSTEM_MASS_PROPERTIES_V3.yaml;03_mass_properties/CONFIGURATION_LIBRARY_V1.yaml",
    )

    mass_audit_path = (
        M4_ROOT
        / "03_mass_properties"
        / "M4_MASS_MATERIAL_TOLERANCE_MECHANISM_AUDIT_V1.json"
    )
    mass_audit = load_json(mass_audit_path)
    audit_hash_mismatches: list[str] = []
    for record in mass_audit.get("audited_artifacts", []):
        artifact_path = M4_ROOT / str(record.get("path", ""))
        actual_hash = sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
        if actual_hash != str(record.get("sha256", "")).upper():
            audit_hash_mismatches.append(str(record.get("path", "")))
    add(
        "M4-V-028-CROSS-DOMAIN-AUDIT-HASHES",
        mass_audit.get("status")
        == "PASS_FAIL_CLOSED_PACKAGE_INTEGRITY_M4_RELEASE_STILL_HOLD"
        and len(mass_audit.get("audited_artifacts", [])) == 13
        and not audit_hash_mismatches,
        (
            f"artifacts={len(mass_audit.get('audited_artifacts', []))}; "
            f"mismatches={audit_hash_mismatches}"
        ),
        str(mass_audit_path),
    )

    # Materials, mechanisms, and structural entry must remain honest HOLDs.
    material = load_yaml(M4_ROOT / "04_material_database" / "PROTOTYPE_MATERIAL_LIBRARY_V1.yaml")
    counts = material.get("selection_and_release_counts", {})
    material_pass = (
        counts.get("flight_approved_records") == 0
        and counts.get("formal_fea_authorized_records") == 0
        and material.get("governing_rules", {}).get("formal_fea_use_authorized") is False
        and material.get("governing_rules", {}).get("flight_material_approval_claimed") is False
    )
    add(
        "M4-V-030-MATERIAL-CANDIDATE-BOUNDARY",
        material_pass,
        f"counts={counts}",
        "04_material_database/PROTOTYPE_MATERIAL_LIBRARY_V1.yaml",
    )
    material_sources = [
        source
        for candidate in material.get("materials", [])
        for source in candidate.get("sources", [])
    ]
    material_provenance_pass = (
        material.get("purpose")
        == "PUBLIC_URL_AND_RETRIEVAL_DATE_REFERENCED_PROTOTYPE_CANDIDATE_SCREENING"
        and bool(material_sources)
        and all(source.get("url") and source.get("retrieved_on") for source in material_sources)
        and all(source.get("source_sha256") is None for source in material_sources)
        and all("NOT_LOCALLY_HASH_ARCHIVED" in str(source.get("source_status", ""))
                or "CONTEXT_REFERENCE_NOT_ALLOWABLES" in str(source.get("source_status", ""))
                for source in material_sources)
    )
    add(
        "M4-V-034-MATERIAL-PROVENANCE-SCOPE",
        material_provenance_pass,
        f"source_count={len(material_sources)}; purpose={material.get('purpose')}",
        "04_material_database/PROTOTYPE_MATERIAL_LIBRARY_V1.yaml",
    )
    mechanism = load_yaml(M4_ROOT / "06_mechanism" / "MECHANISM_STATUS_REGISTER_V1.yaml")
    mechanism_metrics = mechanism.get("gate_metrics", {})
    mechanism_pass = (
        mechanism_metrics.get("prototype_physical_release_count") == 0
        and mechanism_metrics.get("flight_release_count") == 0
        and mechanism_metrics.get("formal_contact_load_authority_count") == 0
        and mechanism_metrics.get("verdict") == "HOLD"
    )
    add(
        "M4-V-031-MECHANISM-PHYSICAL-HOLD",
        mechanism_pass,
        f"metrics={mechanism_metrics}",
        "06_mechanism/MECHANISM_STATUS_REGISTER_V1.yaml",
    )
    structural = load_json(M4_ROOT / "07_structural_model" / "STRUCTURAL_ANALYSIS_ENTRY_GATE.json")
    structural_pass = (
        structural.get("gate_status") == "HOLD"
        and structural.get("pass_token_issued") is False
        and structural.get("formal_fea_authorized") is False
        and structural.get("formal_fea_run_count") == 0
    )
    add(
        "M4-V-032-STRUCTURAL-ENTRY-HOLD",
        structural_pass,
        f"gate={structural.get('gate_status')}; run_count={structural.get('formal_fea_run_count')}",
        "07_structural_model/STRUCTURAL_ANALYSIS_ENTRY_GATE.json",
    )
    structural_plan = load_yaml(
        M4_ROOT / "07_structural_model" / "STRUCTURAL_MODEL_PLAN_V1.yaml"
    )
    tolerance_stack = load_yaml(
        M4_ROOT / "05_tolerance" / "INTERFACE_STACKUP_B601_M3R_V1.yaml"
    )
    spacecraft_chain = next(
        (
            item
            for item in tolerance_stack.get("chains", [])
            if item.get("chain_id") == "STAGE_B_SPACECRAFT_M6_PATTERN"
        ),
        {},
    )
    physical_path_pass = structural_plan.get("load_path") == [
        "B601",
        "STAGE_A_INTERFACE_RING",
        "STAGE_B_LOAD_DIFFUSION_PLATE",
        "SPACECRAFT_LOAD_BRIDGE",
        "SPACECRAFT_BUS_PRIMARY_STRUCTURE",
    ] and tolerance_stack.get("assembly_path") == (
        "B601 -> M3R_STAGE_A -> M3R_STAGE_B -> SPACECRAFT_LOAD_BRIDGE"
    )
    datum_pass = (
        spacecraft_chain.get("datum_frame")
        == "SPACECRAFT_LOAD_BRIDGE_MATING_DATUM"
        and spacecraft_chain.get("unknown_inputs", {}).get(
            "spacecraft_load_bridge_mating_datum_definition"
        )
        is None
        and spacecraft_chain.get("unknown_inputs", {}).get(
            "physical_mating_datum_to_M_DYNAMICS_transform"
        )
        is None
    )
    add(
        "M4-V-033-PHYSICAL-LOAD-PATH-AND-DATUM",
        physical_path_pass and datum_pass,
        f"load_path={structural_plan.get('load_path')}; datum={spacecraft_chain.get('datum_frame')}",
        "07_structural_model/STRUCTURAL_MODEL_PLAN_V1.yaml;05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml",
    )
    nominal_geometry = spacecraft_chain.get("nominal_geometry", {})
    stack_contract = tolerance_stack.get("physical_stack_station_contract", {})
    station_records = stack_contract.get("stations", {})
    station_values = {
        name: record.get("station_x_mm") for name, record in station_records.items()
    }
    expected_stations = {
        "M_FRAME_DYNAMICS_ORIGIN": 185.25,
        "ADAPTER_PLATE_EXTERNAL_FACE": 198.0,
        "CENTRAL_BOSS_PHYSICAL_INSTALLATION_FACE": 208.0,
        "B601_AS_BUILT_FASTENER_END_PLANE": 210.405,
    }
    physical_stack_source = tolerance_stack.get("sources", {}).get(
        "physical_stack", {}
    )
    physical_stack_path = PROJECT_ROOT / str(physical_stack_source.get("path", ""))
    physical_stack_hash_pass = (
        physical_stack_path.is_file()
        and sha256_file(physical_stack_path)
        == str(physical_stack_source.get("sha256", "")).upper()
    )
    nominal_ligament = nominal_geometry.get(
        "Stage_B_nominal_net_hole_edge_ligament_mm"
    )
    ligament_pass = nominal_ligament is not None and close(
        nominal_ligament, 160.0 / 2.0 - 70.0 - 6.6 / 2.0
    )
    tolerance_plan = load_yaml(
        M4_ROOT / "05_tolerance" / "TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml"
    )
    tolerance_metrics = tolerance_plan.get("current_metrics", {})
    counting_basis = tolerance_metrics.get("functional_chain_counting_basis", {})
    chain_count_pass = (
        counting_basis.get("B601_M3R_spacecraft_interface_chains") == 6
        and counting_basis.get("gripper_guarded_clearance_models") == 1
        and counting_basis.get("solar_hinge_tolerance_chains") == 3
        and tolerance_metrics.get("open_functional_chains") == 10
    )
    add(
        "M4-V-035-TOLERANCE-NUMERIC-AND-COUNTING-CONSISTENCY",
        station_values == expected_stations
        and physical_stack_hash_pass
        and ligament_pass
        and chain_count_pass,
        (
            f"stations={station_values}; ligament_mm={nominal_ligament}; "
            f"physical_stack_hash_pass={physical_stack_hash_pass}; "
            f"open_chains={tolerance_metrics.get('open_functional_chains')}"
        ),
        "05_tolerance/INTERFACE_STACKUP_B601_M3R_V1.yaml;05_tolerance/TOLERANCE_CLOSURE_EXECUTION_PLAN_V1.yaml",
    )

    mechanism_requirements_path = (
        M4_ROOT / "06_mechanism" / "MECHANISM_VERIFICATION_REQUIREMENTS_V1.csv"
    )
    with mechanism_requirements_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as mechanism_stream:
        mechanism_rows = list(csv.DictReader(mechanism_stream))
    bad_mechanism_rows: list[str] = []
    for row in mechanism_rows:
        try:
            output_contract = json.loads(row.get("output_schema_json", ""))
            contract_valid = isinstance(output_contract, list) and bool(output_contract) and all(
                isinstance(output, Mapping)
                and output.get("name")
                and ("unit" in output)
                for output in output_contract
            )
        except Exception:
            contract_valid = False
        if (
            not contract_valid
            or row.get("status") != "HOLD"
            or row.get("acceptance_value") not in {None, ""}
            or row.get("standard_uncertainty") not in {None, ""}
            or (
                row.get("measurement_structure") == "MULTI_OUTPUT"
                and row.get("unit") not in {None, ""}
            )
        ):
            bad_mechanism_rows.append(str(row.get("verification_id", "")))
    add(
        "M4-V-036-MECHANISM-MEASURAND-CONTRACT",
        len(mechanism_rows) == 20 and not bad_mechanism_rows,
        f"rows={len(mechanism_rows)}; bad={bad_mechanism_rows}",
        "06_mechanism/MECHANISM_VERIFICATION_REQUIREMENTS_V1.csv",
    )

    # Drawings and BOM must exist, but remain prototype/non-procurement artifacts.
    drawing_files = [path for path in (M4_ROOT / "09_drawings").glob("*") if path.is_file()]
    bom_files = [path for path in (M4_ROOT / "10_BOM").glob("*") if path.is_file()]
    drawings_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in drawing_files + bom_files
        if path.suffix.lower() in {".md", ".csv", ".yaml", ".yml", ".json"}
    )
    add(
        "M4-V-040-DRAWING-BOM-PACKAGE",
        bool(drawing_files)
        and bool(bom_files)
        and ("NOT" in drawings_text.upper() or "HOLD" in drawings_text.upper()),
        f"drawing_files={len(drawing_files)}; bom_files={len(bom_files)}",
        "09_drawings;10_BOM",
    )

    # Re-run Sim14 rather than trusting previously written evidence.
    sim_test = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=SIM14_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    sim_output = (sim_test.stdout + sim_test.stderr).strip()
    add(
        "M4-V-050-SIM14-INDEPENDENT-PYTEST",
        sim_test.returncode == 0,
        f"exit_code={sim_test.returncode}; output={sim_output[-4000:]}",
        str(SIM14_ROOT / "tests"),
    )
    sim_gate_path = SIM14_ROOT / "evidence" / "SIM14_DYNAMICS_GRASPING_GATE.json"
    sim_gate = load_json(sim_gate_path) if sim_gate_path.is_file() else {}
    sim_scope_pass = (
        sim_gate.get("overall_status") == "PASS_DIAGNOSTIC_KERNEL_HOLD_PRODUCTION_DYNAMICS"
        and sim_gate.get("production_dynamics_gate") == "HOLD"
        and str(sim_gate.get("test_gate", "")).startswith("PASS_")
        and sim_gate.get("contact_physics_gate") == "HOLD_NOT_IMPLEMENTED_NO_AUTHORITY"
        and sim_gate.get("next_stage_authorized") is False
    )
    add(
        "M4-V-051-SIM14-SCOPE",
        sim_scope_pass,
        f"overall={sim_gate.get('overall_status')}; production={sim_gate.get('production_dynamics_gate')}",
        str(sim_gate_path),
    )
    sim_binding_path = (
        SIM14_ROOT / "evidence" / "SIM14_PRODUCTION_BINDING_RECEIPT.json"
    )
    sim_binding = load_json(sim_binding_path)
    resolved_sim_assets = sim_binding.get("resolved_hash_bound_artifacts", [])
    closure_audit = sim_binding.get("closure_audit", {})
    sim_nested_binding_pass = (
        sim_binding.get("required_artifact_count") == 14
        and sim_binding.get("resolved_required_artifact_count") == 14
        and len(resolved_sim_assets) == 14
        and sim_binding.get("unresolved_required_artifacts") == []
        and "mass_material_tolerance_mechanism_audit" in resolved_sim_assets
        and closure_audit.get("nested_artifact_hashes_verified") == 13
        and closure_audit.get("nested_artifact_hashes_expected") == 13
        and closure_audit.get("status") == "PASS_FAIL_CLOSED_NOT_RUNTIME_UNLOCK"
        and sim_binding.get("configuration_inertia_reference_point_verified_count")
        == 9
        and sim_binding.get("uncertainty_subrecord_verified_count") == 14
        and sim_binding.get("full_mass_properties_loader_ready_count") == 0
        and sim_binding.get("production_dynamics_ready") is False
    )
    add(
        "M4-V-052-SIM14-NESTED-MECHANICAL-AUDIT",
        sim_nested_binding_pass,
        (
            f"resolved={len(resolved_sim_assets)}; closure_audit={closure_audit}; "
            f"production_ready={sim_binding.get('production_dynamics_ready')}"
        ),
        str(sim_binding_path),
    )

    # A prior gate generation is required for this final consistency check.
    # The gate is regenerated after validation so its quantitative receipt
    # carries the final validator count without creating a hash cycle.
    release_gate_path = (
        M4_ROOT
        / "12_release"
        / "MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json"
    )
    release_gate = load_json(release_gate_path)
    release_tokens = release_gate.get("release_tokens", {})
    vcd_path = M4_ROOT / "12_release" / "M4_REQUIREMENTS_VERIFICATION_MATRIX_V1.csv"
    with vcd_path.open("r", encoding="utf-8-sig", newline="") as vcd_stream:
        vcd_rows = list(csv.DictReader(vcd_stream))
    vcd_070 = next(
        (row for row in vcd_rows if row.get("requirement_id") == "M4-REQ-070"),
        {},
    )
    ecr_010 = next(
        (row for row in ecr_rows if row.get("ecr_id") == "M4-ECR-010"), {}
    )
    final_control_pass = (
        release_tokens.get("digital_prototype", {}).get("issued") is True
        and release_tokens.get("bounded_diagnostic_dynamics", {}).get("issued")
        is True
        and release_tokens.get("structural_entry", {}).get("issued") is False
        and release_tokens.get("production_contact_rl", {}).get("issued") is False
        and release_gate.get("memory_execution_record", {}).get(
            "memory_gate_passed"
        )
        is False
        and release_gate.get("memory_execution_record", {}).get(
            "owner_override_used"
        )
        is True
        and vcd_070.get("current_status")
        == "PASS_34_OF_34_SCOPED_TOKENS_ISSUED"
        and ecr_010.get("status") == "ACCEPTED_SCOPED_GATE_ISSUED"
    )
    add(
        "M4-V-070-FINAL-SCOPED-RELEASE-CONTROL",
        final_control_pass,
        (
            f"tokens={release_tokens}; VCD={vcd_070.get('current_status')}; "
            f"ECR={ecr_010.get('status')}"
        ),
        "12_release/MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json;12_release/M4_REQUIREMENTS_VERIFICATION_MATRIX_V1.csv;00_authority/M4_ECR_REGISTER_V1.csv",
    )

    failed = [item for item in checks if item["status"] == "FAIL"]
    receipt = {
        "schema": "M4_INDEPENDENT_VALIDATION_RECEIPT_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "validator": "99_tools/validate_m4_release.py",
        "check_count": len(checks),
        "pass_count": len(checks) - len(failed),
        "fail_count": len(failed),
        "checks": checks,
        "release_tokens": {
            "artifact_integrity": "PASS" if not failed else "FAIL",
            "digital_prototype": (
                "ELIGIBLE_FOR_SCOPED_WORKING_RELEASE" if not failed else "HOLD"
            ),
            "structural_entry": "HOLD",
            "bounded_diagnostic_dynamics": (
                "ELIGIBLE" if not failed else "HOLD"
            ),
            "production_contact_rl": "HOLD",
            "manufacturing_qualification_flight": "HOLD",
        },
        "status": (
            "PASS_EXPECTED_HOLDS_PRESERVED" if not failed else "FAIL_INTEGRITY_OR_SCOPE"
        ),
    }
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "check_count": receipt["check_count"],
                "pass_count": receipt["pass_count"],
                "fail_count": receipt["fail_count"],
                "status": receipt["status"],
                "failed_check_ids": [item["check_id"] for item in failed],
            },
            indent=2,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
