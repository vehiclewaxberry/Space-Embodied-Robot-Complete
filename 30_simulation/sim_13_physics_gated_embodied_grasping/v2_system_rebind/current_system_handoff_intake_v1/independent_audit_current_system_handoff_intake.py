"""Independent stdlib audit; intentionally does not import current_handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[3]
CROSSWALK_PATH = PACKAGE_ROOT / "contracts" / "FIELD_SOURCE_CROSSWALK_V1.json"
OUTPUT_PATH = PACKAGE_ROOT / "evidence" / "CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1.json"
REPARSE_POINT = 0x400
YAML_SCHEMA_RE = re.compile(r"(?m)^schema:[ \t]*([^#\r\n]+?)[ \t]*\r?$")
EXPECTED_CLASSIFICATIONS = {
    "topology": "OWNER_REQUIRED",
    "mass": "CANDIDATE_ONLY",
    "limits": "TEST_REQUIRED",
    "collision": "TEST_REQUIRED",
    "contact": "TEST_REQUIRED",
    "material": "CANDIDATE_ONLY",
    "flex": "TEST_REQUIRED",
    "harness": "MISSING",
    "targets": "MISSING",
}
MANDATORY_FALSE = (
    "intake_complete",
    "current_system_bound",
    "urdf_emitted",
    "system_urdf_available",
    "interface_instantiated",
    "runtime_ready",
    "dynamics_ready",
    "contact_ready",
    "full_flex_ready",
    "sim13_ready",
    "next_stage_authorized",
    "release",
)
FROZEN_BINDING_DIGEST = "D6CC48E6EEF2112AC9CA4E1C2F0D97D59D9FF2B64880DC44DF95109CD6A01F33"
REQUIRED_ABSENT_PATHS = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
)
EXPECTED_ARTIFACT_BINDINGS = (
    ("topology_frame_tree", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml", 11828, "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756"),
    ("mass_model", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml", 223714, "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB"),
    ("limits_interface", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml", 2126, "364D7F2C54B6A77CC80B105EC24F3B7DDEA5FD5648FD7F01E7A2F96BE21A5F51"),
    ("collision_gate", "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json", 17130, "DB9029C8626B135F531E5467F1293CA65EDFED7BCB5BAB469CBDAA717AE71BF8"),
    ("contact_contract", "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml", 5199, "1BF741A508AA6F263D81458184840F2AD6608652250256CE84D7F2656BD04B6B"),
    ("material_selection", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml", 25619, "B2973F2A0A95CAF21FE551C5E82388FEEEDCAACE79140A5339DACD5884723220"),
    ("full_flex_checkpoint", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/R2_FULL_FLEX_GATE_V1.json", 24848, "FC8C9D7BEABF58D19B25CF4A238F12AC255F664F756E7950A942E7E6D3FC1C13"),
    ("e22_gate", "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", 9374, "472ADA4A7ABF98BBD5F72B0459400704A86FAF2B13DACCD562025C0CC356AA5E"),
    ("e15_gate", "30_simulation/e15_ancf_certification/results/gate_summary.json", 1585, "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80"),
    ("harness_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json", 7324, "F3B444222E87509B66F712E623A4903748C7309C6396708EC02A0C1A54CDAA5C"),
    ("handoff_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json", 54345, "13722965D5C558D3439A7CB1E77ABBF3C2094B88E9D62F80D664D0C4C90D4E21"),
    ("route_c_checkpoint_b", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json", 14887, "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1"),
    ("route_c_cad_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_CAD_ENTRY_GATE_V1.json", 2624, "5524EFB209C792DCFECA022C613030E35EAB86ADFFDB8F3CA4D244D6C73E98AE"),
    ("current_binding_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json", 6345, "7FD3C63AF46BE4BA3055CCF87EFD1A71C13517EC872B1F3EDC52304B070D9153"),
    ("target_feasibility_gate", "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json", 5951, "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67"),
)
EXPECTED_DOMAIN_SOURCES = {
    "topology": ("topology_frame_tree", "current_binding_gate"),
    "mass": ("mass_model", "topology_frame_tree"),
    "limits": ("limits_interface",),
    "collision": ("collision_gate",),
    "contact": ("contact_contract", "limits_interface"),
    "material": ("material_selection",),
    "flex": ("full_flex_checkpoint", "e22_gate", "e15_gate"),
    "harness": ("harness_gate", "handoff_gate", "route_c_checkpoint_b", "route_c_cad_gate"),
    "targets": ("target_feasibility_gate", "contact_contract"),
}
FORBIDDEN_ASSET_EXTENSIONS = {
    ".urdf", ".step", ".stp", ".fcstd", ".stl", ".obj", ".dae", ".ply", ".gltf", ".glb",
    ".inp", ".odb", ".traj", ".npz", ".xacro", ".sdf", ".mjcf", ".msh", ".vtk", ".npy", ".h5",
}
FORBIDDEN_CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis", ".cache", ".coverage"}
ARTIFACT_PATHS = {
    "intake": "evidence/CURRENT_SYSTEM_HANDOFF_INTAKE_V1.json",
    "negative_controls": "evidence/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROLS_V1.json",
    "independent_audit": "evidence/CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1.json",
    "source_manifest": "evidence/CURRENT_SYSTEM_HANDOFF_SOURCE_MANIFEST_V1.json",
    "gate": "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json",
    "terminal": "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json",
}
CONTRACT_NAMES = (
    "CURRENT_SYSTEM_HANDOFF_INTAKE_SCHEMA_V1.json",
    "FIELD_SOURCE_CROSSWALK_V1.json",
    "ROUTE_C_DISPOSITION_CONTRACT_V1.json",
    "PROMOTION_SEQUENCE_CONTRACT_V1.json",
    "CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROL_CONTRACT_V1.json",
)
FROZEN_PACKAGE_FILE_ALLOWLIST = tuple(
    sorted(
        {
            "README.md",
            "contracts/CURRENT_SYSTEM_HANDOFF_INTAKE_SCHEMA_V1.json",
            "contracts/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROL_CONTRACT_V1.json",
            "contracts/FIELD_SOURCE_CROSSWALK_V1.json",
            "contracts/PROMOTION_SEQUENCE_CONTRACT_V1.json",
            "contracts/ROUTE_C_DISPOSITION_CONTRACT_V1.json",
            "current_handoff/__init__.py",
            "current_handoff/evaluator.py",
            "current_handoff/freeze_support.py",
            "current_handoff/negative_controls.py",
            "current_handoff/schema.py",
            "current_handoff/strict_io.py",
            "evidence/CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_INTAKE_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROLS_V1.json",
            "evidence/CURRENT_SYSTEM_HANDOFF_SOURCE_MANIFEST_V1.json",
            "freeze_current_system_handoff_intake.py",
            "independent_audit_current_system_handoff_intake.py",
            "pytest.ini",
            "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json",
            "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json",
            "tests/conftest.py",
            "tests/test_evaluator.py",
            "tests/test_frozen_bundle.py",
            "tests/test_independent_audit.py",
            "tests/test_negative_controls.py",
            "tests/test_schema.py",
            "tests/test_strict_io.py",
            "validate_current_system_handoff_intake_source_freeze.py",
            "verify_current_system_handoff_intake_read_only_replay.py",
        }
    )
)
PACKAGE_PROJECT_RELATIVE = PACKAGE_ROOT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(token):
    raise ValueError(f"nonfinite JSON: {token}")


def _strict_json(payload: bytes):
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )

    def walk(child):
        if isinstance(child, float) and not math.isfinite(child):
            raise ValueError("nonfinite JSON")
        if isinstance(child, dict):
            for nested in child.values():
                walk(nested)
        elif isinstance(child, list):
            for nested in child:
                walk(nested)

    walk(value)
    return value


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _canonical_json(document) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _canonical_path(relative: str, *, must_exist: bool = True) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("invalid project-relative path")
    if any(ord(character) < 32 or ord(character) == 127 for character in relative):
        raise ValueError("path control character")
    pure = PurePosixPath(relative)
    if pure.is_absolute() or pure.as_posix() != relative or "//" in relative or "/./" in relative:
        raise ValueError("path alias")
    if any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError("path traversal")
    root = PROJECT_ROOT.resolve(strict=True)
    cursor = root
    for part in pure.parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            stat = cursor.lstat()
            if cursor.is_symlink() or bool(getattr(stat, "st_file_attributes", 0) & REPARSE_POINT):
                raise ValueError("symlink/reparse source")
        elif must_exist:
            raise ValueError("missing source")
        else:
            break
    path = root.joinpath(*pure.parts)
    if must_exist:
        resolved = path.resolve(strict=True)
        if resolved.relative_to(root).as_posix() != relative or not resolved.is_file():
            raise ValueError("path canonicality/file failure")
        return resolved
    path.resolve(strict=False).relative_to(root)
    return path


def _load_sources():
    crosswalk_payload = CROSSWALK_PATH.read_bytes()
    crosswalk = _strict_json(crosswalk_payload)
    declared_bindings = tuple(
        (spec.get("id"), spec.get("path"), spec.get("bytes"), spec.get("sha256"))
        for spec in crosswalk.get("artifacts", ())
        if isinstance(spec, dict)
    )
    if declared_bindings != EXPECTED_ARTIFACT_BINDINGS:
        raise ValueError("crosswalk ID/path/bytes/SHA differs from independent source constants")
    declared_domains = {
        item.get("domain"): tuple(item.get("artifact_ids", ()))
        for item in crosswalk.get("domain_bindings", ())
        if isinstance(item, dict)
    }
    if declared_domains != EXPECTED_DOMAIN_SOURCES:
        raise ValueError("crosswalk domain source lineage differs from independent constants")
    if tuple(crosswalk.get("required_absent_paths", ())) != REQUIRED_ABSENT_PATHS:
        raise ValueError("required absent paths are not the exact system URDF/interface pair")
    sources = {}
    receipts = []
    for spec in crosswalk["artifacts"]:
        path = _canonical_path(spec["path"])
        payload = path.read_bytes()
        digest = _sha(payload)
        if len(payload) != spec["bytes"] or digest != spec["sha256"]:
            raise ValueError(f"hash drift: {spec['id']}")
        if spec["format"] == "JSON":
            parsed = _strict_json(payload)
            if parsed.get(spec["schema_field"]) != spec["expected_schema"]:
                raise ValueError(f"schema mismatch: {spec['id']}")
        elif spec["format"] == "YAML_PINNED":
            text = payload.decode("utf-8")
            schemas = [match.strip().strip("'\"") for match in YAML_SCHEMA_RE.findall(text)]
            if schemas != [spec["expected_schema"]]:
                raise ValueError(f"opaque YAML schema marker mismatch: {spec['id']}")
            parsed = {"schema": schemas[0], "text": text}
        else:
            raise ValueError("unsupported source format")
        sources[spec["id"]] = parsed
        receipts.append({"artifact_id": spec["id"], "path": spec["path"], "bytes": len(payload), "sha256": digest, "read_count": 1})
    for relative in crosswalk["required_absent_paths"]:
        candidate = _canonical_path(relative, must_exist=False)
        if candidate.exists() or candidate.is_symlink():
            raise ValueError(f"unadmitted artifact exists: {relative}")
    return crosswalk, sources, receipts


def build_audit() -> dict:
    crosswalk, source, receipts = _load_sources()
    frame_text = source["topology_frame_tree"]["text"]
    mass_text = source["mass_model"]["text"]
    limits_text = source["limits_interface"]["text"]
    contact_text = source["contact_contract"]["text"]
    material_text = source["material_selection"]["text"]
    collision = source["collision_gate"]
    flex = source["full_flex_checkpoint"]
    e22 = source["e22_gate"]
    e15 = source["e15_gate"]
    harness = source["harness_gate"]
    handoff = source["handoff_gate"]
    checkpoint_b = source["route_c_checkpoint_b"]
    cad_gate = source["route_c_cad_gate"]
    binding = source["current_binding_gate"]
    target = source["target_feasibility_gate"]
    domain_map = {item["domain"]: item["classification"] for item in crosswalk["domain_bindings"]}
    checks = {
        "crosswalk_id_path_bytes_sha_matches_independent_constants": tuple(
            (item["id"], item["path"], item["bytes"], item["sha256"])
            for item in crosswalk["artifacts"]
        ) == EXPECTED_ARTIFACT_BINDINGS,
        "domain_source_lineage_matches_independent_constants": {
            item["domain"]: tuple(item["artifact_ids"])
            for item in crosswalk["domain_bindings"]
        } == EXPECTED_DOMAIN_SOURCES,
        "fifteen_sources_path_bytes_sha_schema_bound": len(receipts) == 15 and all(item["read_count"] == 1 for item in receipts),
        "domain_classifications_exact_and_never_pass": domain_map == EXPECTED_CLASSIFICATIONS and "PASS" not in domain_map.values(),
        "topology_static_only_19_18": "urdf_emitted: false" in frame_text and "total_links: 19" in frame_text and "joints: 18" in frame_text,
        "mass_candidate_not_as_built": "m7_design_ledger_c01_kg: 31.022864807342987" in mass_text and "authority: DESIGN_MODEL_R2" in mass_text,
        "model_velocity_not_hardware": "urdf_velocity_limit_literal_m_s: 15.0" in limits_text and "rated_speed_m_s: null" in limits_text,
        "collision_not_released": collision["narrow_phase_available"] is False and collision["system_collision_release"] is False,
        "contact_null_and_unauthorized": "estimate: null" in contact_text and "physical_contact_kernel_authorized: false" in contact_text,
        "materials_zero_flight_allowables": "ZERO_FLIGHT_ALLOWABLES_ZERO_QUALIFICATION_CLAIMS" in material_text,
        "full_flex_checkpoint_6_12_hold": flex["checkpoint_outcome"] == "HOLD" and flex["summary"]["passed"] == 6 and flex["summary"]["total"] == 12,
        "e22_16_18_g11_g17_fail": e22["summary"] == {"passed": 16, "total": 18, "failed": ["G11", "G17"]},
        "e15_repeat_and_5p64_gt_5": e15["overall"] == "REPEAT_ANCF_CERTIFICATION" and e15["cross_solver_diagnostic"]["max_relative_difference"] == 0.05637349419858036 and e15["cross_solver_diagnostic"]["all_lt_5pct"] is False,
        "harness_zero_safe_zero_released": sum(item["pass"] is True for item in harness["key_state_checks"]) == 0 and harness["trajectory_segments_with_released_authority"] == 0,
        "handoff_g12_fail": handoff["checks_passed"] == 11 and handoff["checks_total"] == 12 and handoff["failing_checks"] == ["G12"],
        "route_c_0_of_13_and_no_seed": checkpoint_b["physical_registry"]["entries_total"] == 13 and checkpoint_b["physical_registry"]["status_AVAILABLE"] == 0 and checkpoint_b["authority_guards"]["route_b_seed_inheritance_allowed"] is False,
        "route_c_cad_not_authorized": cad_gate["gate"] == "HOLD" and cad_gate["cad_artifacts_created_by_this_package"] == 0,
        "current_binding_invalidated": binding["current_authority"]["mechanical_release"] is False and binding["current_authority"]["production_dynamics_ready"] is False,
        "target_lane_rigid_only": target["verdict"] == "SIM10_GATES_PASS" and target["flex_status"] == "UNKNOWN_NOT_IN_CRITERIA",
        "system_urdf_and_interface_exact_paths_absent": (
            tuple(crosswalk["required_absent_paths"]) == REQUIRED_ABSENT_PATHS
            and all(not _canonical_path(relative, must_exist=False).exists() for relative in REQUIRED_ABSENT_PATHS)
        ),
        "complete_package_file_allowlist_exact": _package_file_paths() == FROZEN_PACKAGE_FILE_ALLOWLIST,
    }
    passed = all(checks.values())
    return {
        "schema": "CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "audit_status": "PASS_INDEPENDENT_SOURCE_ONLY_AUDIT" if passed else "FAIL_INDEPENDENT_SOURCE_ONLY_AUDIT",
        "independent_audit_pass": passed,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "source_receipts": receipts,
        "imports_production_evaluator": False,
        "yaml_source_handling": "OPAQUE_LENGTH_SHA256_PIN_PLUS_SINGLE_SCHEMA_MARKER__NOT_INTAKE_YAML",
        "current_intake_status": "HOLD_INCOMPLETE",
        "gate_ceiling": "PASS_SOURCE_FREEZE_ONLY",
        "flags": {name: False for name in MANDATORY_FALSE},
    }


def _receipt_matches(record, expected_path=None):
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        return False
    relative = record.get("path")
    if not isinstance(relative, str) or (expected_path is not None and relative != expected_path):
        return False
    try:
        path = _canonical_path(relative)
    except (OSError, ValueError):
        return False
    payload = path.read_bytes()
    return record.get("bytes") == len(payload) and record.get("sha256") == _sha(payload)


def _source_inventory():
    excluded = {"evidence", "results"} | FORBIDDEN_CACHE_NAMES
    records = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(PACKAGE_ROOT)
        if any(part.lower() in excluded for part in relative.parts) or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        payload = path.read_bytes()
        records.append(
            {
                "path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
                "bytes": len(payload),
                "sha256": _sha(payload),
            }
        )
    return records


def _package_file_paths():
    return tuple(
        sorted(
            path.relative_to(PACKAGE_ROOT).as_posix()
            for path in PACKAGE_ROOT.rglob("*")
            if path.is_file()
        )
    )


def _forbidden_entries():
    findings = []
    for path in sorted(PACKAGE_ROOT.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(PACKAGE_ROOT)
        lowered = {part.lower() for part in relative.parts}
        cache = bool(lowered & FORBIDDEN_CACHE_NAMES) or any(part.lower().startswith(".coverage.") for part in relative.parts)
        bytecode = path.is_file() and path.suffix.lower() in {".pyc", ".pyo"}
        geometry = path.is_file() and path.suffix.lower() in FORBIDDEN_ASSET_EXTENSIONS
        if cache or bytecode or geometry:
            findings.append(relative.as_posix())
    return findings


def audit_committed_bundle() -> dict:
    """Independently recompute the complete manifest -> evidence -> Gate -> terminal DAG."""

    documents = {
        name: _strict_json((PACKAGE_ROOT / relative).read_bytes())
        for name, relative in ARTIFACT_PATHS.items()
    }
    intake = documents["intake"]
    negative = documents["negative_controls"]
    stored_audit = documents["independent_audit"]
    manifest = documents["source_manifest"]
    gate = documents["gate"]
    terminal = documents["terminal"]
    expected_audit = build_audit()
    evidence_names = ("intake", "negative_controls", "independent_audit", "source_manifest")
    evidence_paths = [f"{PACKAGE_PROJECT_RELATIVE}/{ARTIFACT_PATHS[name]}" for name in evidence_names]
    gate_path = f"{PACKAGE_PROJECT_RELATIVE}/{ARTIFACT_PATHS['gate']}"
    exact_source_receipts = tuple(
        (item.get("artifact_id"), item.get("path"), item.get("bytes"), item.get("sha256"), item.get("read_count"), item.get("transport_classification"))
        for item in intake.get("source_receipts", ())
        if isinstance(item, dict)
    )
    expected_source_receipts = tuple((*binding, 1, "PASS") for binding in EXPECTED_ARTIFACT_BINDINGS)
    exact_false = lambda document: (
        isinstance(document.get("flags"), dict)
        and set(document["flags"]) == set(MANDATORY_FALSE)
        and all(document["flags"][name] is False for name in MANDATORY_FALSE)
    )
    expected_key_sets = {
        "intake": {"schema", "artifact_id", "scope", "current_intake_status", "theoretical_ceiling", "gate_ceiling", "classification_enum", "mass_mode", "required_absent_paths", "source_receipts", "domains", "physical_quantities", "route_c_disposition", "promotion_sequence", "preserved_hard_negatives", "checks", "flags", "source_only_validation_pass", "frozen_binding_digest"},
        "negative_controls": {"schema", "artifact_id", "baseline_sha256", "baseline_status", "controls", "controls_passed", "controls_total", "all_passed", "receipt_validation_scope", "urdf_generator_invoked", "generated_cad_step_mesh_urdf_or_physics_assets"},
        "independent_audit": set(expected_audit),
        "source_manifest": {"schema", "artifact_id", "inventory_scope", "files", "file_count", "frozen_package_file_allowlist", "package_file_count", "complete_package_file_allowlist_exact", "forbidden_package_entries", "forbidden_package_entry_count", "urdf_generator_source_imported", "generated_cad_step_mesh_urdf_or_physics_assets"},
        "gate": {"schema", "artifact_id", "overall_status", "current_intake_status", "highest_theoretical_status", "source_freeze_tooling_pass", "source_artifacts_bound", "source_validation_checks_passed", "source_validation_checks_total", "negative_controls_passed", "negative_controls_total", "independent_audit_checks_passed", "independent_audit_checks_total", "domain_classification_counts", "frozen_binding_digest", "contracts", "evidence", "receipt_validation_scope", "evidence_dag_complete", "complete_package_file_allowlist_exact", "package_files_frozen", "preserved_hard_negatives", "flags", "generated_cad_step_mesh_urdf_or_physics_assets", "urdf_generator_invoked", "legacy_unified_r2_validator_invoked", "release_credit", "ceiling_note"},
        "terminal": {"schema", "artifact_id", "terminal_status", "current_intake_status", "gate", "evidence_dag_terminal_commit", "flags", "release_credit", "next_required_external_closure"},
    }
    checks = {
        "all_six_documents_strict_and_exact_key_sets": all(set(documents[name]) == expected_key_sets[name] for name in ARTIFACT_PATHS),
        "artifact_identity_exact_across_complete_dag": all(document.get("artifact_id") == "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1" for document in documents.values()),
        "stored_independent_source_audit_exact_replay": stored_audit == expected_audit,
        "source_manifest_exact_inventory_and_hashes": manifest.get("files") == _source_inventory() and manifest.get("file_count") == len(manifest.get("files", ())) and all(_receipt_matches(record) for record in manifest.get("files", ())),
        "source_manifest_forbidden_inventory_zero": manifest.get("forbidden_package_entries") == [] and manifest.get("forbidden_package_entry_count") == 0,
        "complete_package_file_allowlist_exact": (
            manifest.get("frozen_package_file_allowlist") == list(FROZEN_PACKAGE_FILE_ALLOWLIST)
            and manifest.get("package_file_count") == len(FROZEN_PACKAGE_FILE_ALLOWLIST)
            and manifest.get("complete_package_file_allowlist_exact") is True
            and gate.get("complete_package_file_allowlist_exact") is True
            and gate.get("package_files_frozen") == len(FROZEN_PACKAGE_FILE_ALLOWLIST)
            and _package_file_paths() == FROZEN_PACKAGE_FILE_ALLOWLIST
        ),
        "intake_source_receipt_bindings_exact": exact_source_receipts == expected_source_receipts,
        "intake_required_absent_paths_exact_and_absent": intake.get("required_absent_paths") == list(REQUIRED_ABSENT_PATHS) and all(not _canonical_path(path, must_exist=False).exists() for path in REQUIRED_ABSENT_PATHS),
        "frozen_binding_digest_source_constant_exact": intake.get("frozen_binding_digest") == gate.get("frozen_binding_digest") == FROZEN_BINDING_DIGEST,
        "negative_controls_exact_31_of_31": negative.get("controls_passed") == negative.get("controls_total") == 31 and negative.get("all_passed") is True and [item.get("id") for item in negative.get("controls", ())] == [f"NC{i:02d}" for i in range(1, 32)] and all(item.get("passed") is True for item in negative.get("controls", ())),
        "gate_evidence_receipts_complete_exact_and_current": gate.get("evidence_dag_complete") is True and [item.get("path") for item in gate.get("evidence", ())] == evidence_paths and all(_receipt_matches(record, path) for record, path in zip(gate.get("evidence", ()), evidence_paths)),
        "gate_contract_receipts_complete_exact_and_current": len(gate.get("contracts", ())) == len(CONTRACT_NAMES) and [item.get("path") for item in gate.get("contracts", ())] == [f"{PACKAGE_PROJECT_RELATIVE}/contracts/{name}" for name in CONTRACT_NAMES] and all(_receipt_matches(record) for record in gate.get("contracts", ())),
        "terminal_exactly_commits_current_gate": terminal.get("evidence_dag_terminal_commit") is True and _receipt_matches(terminal.get("gate"), gate_path),
        "gate_terminal_hold_and_source_only_ceiling": gate.get("overall_status") == terminal.get("terminal_status") == "PASS_SOURCE_FREEZE_ONLY" and gate.get("current_intake_status") == terminal.get("current_intake_status") == "HOLD_INCOMPLETE" and gate.get("release_credit") is False and terminal.get("release_credit") is False,
        "all_twelve_flags_false_in_intake_audit_gate_terminal": all(exact_false(document) for document in (intake, stored_audit, gate, terminal)),
        "promotion_receipt_scope_has_no_persistent_or_authority_credit": "NO_PERSISTENT_OR_CROSS_PROCESS_CREDIT" in gate.get("receipt_validation_scope", "") and "NO_OWNER_AUTHORITY" in gate.get("receipt_validation_scope", ""),
        "forbidden_generated_assets_and_cache_entries_absent": _forbidden_entries() == [],
    }
    passed = all(checks.values())
    return {
        "schema": "CURRENT_SYSTEM_HANDOFF_COMPLETE_DAG_INDEPENDENT_AUDIT_V1",
        "status": "PASS_COMPLETE_DAG_INDEPENDENT_AUDIT" if passed else "FAIL_COMPLETE_DAG_INDEPENDENT_AUDIT",
        "pass": passed,
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        document = build_audit()
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        print(f"independent_audit=FAIL error={exc}")
        return 1
    if args.print:
        print(_canonical_json(document).decode("utf-8"), end="")
    if args.check:
        if not OUTPUT_PATH.is_file() or OUTPUT_PATH.read_bytes() != _canonical_json(document):
            print("independent_audit=FAIL frozen evidence differs")
            return 1
        dag = audit_committed_bundle()
        if not dag["pass"]:
            print(
                "independent_audit=FAIL complete_dag={}/{} failed={}".format(
                    dag["checks_passed"],
                    dag["checks_total"],
                    ",".join(name for name, passed in dag["checks"].items() if not passed),
                )
            )
            return 1
    print(f"independent_audit={document['audit_status']} checks={document['checks_passed']}/{document['checks_total']}")
    if args.check:
        print(f"complete_dag={dag['status']} checks={dag['checks_passed']}/{dag['checks_total']}")
    return 0 if document["independent_audit_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
