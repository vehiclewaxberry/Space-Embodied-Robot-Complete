"""Build the PB-G0/PB-G1 prebind capsule and run PB-00 characterization.

The runner is intentionally fail-closed.  It never edits upstream mechanical,
simulation, safety, or control assets.  The Unified R2 dynamics backend is
loaded through a read-only adapter and verifies its own URDF/receipt hashes.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml


PHASE_ID = "DYNAMICS_CONTROL_PREBIND_R1"
MODULE_REL = Path("30_simulation/dynamics_control_prebind_r1")
GENERATED_DATE_LOCAL = "2026-08-26"
DEFAULT_SEED = 260826


@dataclass(frozen=True)
class AssetSpec:
    asset_id: str
    relative_path: str
    role: str
    authority_status: str
    consumed_by_pb00: bool = False
    expected_sha256: str | None = None
    hash_mode: str = "RAW_BYTES_SHA256"


ASSETS: tuple[AssetSpec, ...] = (
    AssetSpec(
        "accepted_b601_urdf",
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "AUTHORITATIVE_ARM_MODEL",
        "ACCEPTED_CURRENT_HARDWARE_TRUTH_UNCHANGED",
        True,
        "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    ),
    AssetSpec(
        "system_design_mass_v3_r2",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml",
        "R2_DESIGN_MASS_LEDGER",
        "DESIGN_MODEL_CANDIDATE_NOT_AS_BUILT",
        False,
        "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB",
    ),
    AssetSpec(
        "system_mass_bridged_v1",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml",
        "DYNAMICS_LANE_MASS_PROPERTIES",
        "CANDIDATE_ONLY_CONSUMED_BY_E22_E23",
        True,
    ),
    AssetSpec(
        "system_mass_authority_v2",
        "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/SYSTEM_MASS_PROPERTIES_AUTHORITY_V2.yaml",
        "MASS_AUTHORITY_RULING",
        "PARTIAL_AUTHORITY_SYSTEM_CONFIGURATION_NOT_EVALUABLE",
    ),
    AssetSpec(
        "legacy_spacecraft_geometry",
        "20_engineering/config/geometry/service_spacecraft_v1.yaml",
        "LEGACY_LANE_REFERENCE_ONLY",
        "DESIGN_LAYER_NOT_CURRENT_R2_DYNAMIC_MASS_AUTHORITY",
    ),
    AssetSpec(
        "target_models",
        "20_engineering/config/geometry/target_models_v1.yaml",
        "TARGET_PARAMETER_SOURCE",
        "LOW_CONFIDENCE_PROVISIONAL",
    ),
    AssetSpec(
        "legacy_frame_tree",
        "20_engineering/config/geometry/frame_tree_v1.yaml",
        "HISTORICAL_DYNAMICS_FRAME_REFERENCE",
        "SUPERSEDED_FOR_PREBIND_BY_UNIFIED_TREE_AND_BRIDGE",
    ),
    AssetSpec(
        "physical_dynamics_bridge",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml",
        "UNIQUE_PHYSICAL_TO_DYNAMICS_FRAME_BRIDGE",
        "FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION",
        True,
        "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    ),
    AssetSpec(
        "unified_r2_frame_tree",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml",
        "CURRENT_UNIFIED_FRAME_TOPOLOGY",
        "SOURCE_ONLY_FROZEN_NOT_DYNAMICS_AUTHORIZED",
        True,
    ),
    AssetSpec(
        "unified_r2_urdf",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
        "PB00_SOURCE_ONLY_SYSTEM_MODEL",
        "SOURCE_ONLY_BUILDER_EMISSION_OWNER_ACCEPTED_FALSE",
        True,
        "D84AA23CE98A2A9C697B1F32E433C01C3F0AE3BD0B5C56EF9A218DD88911CBDA",
    ),
    AssetSpec(
        "unified_r2_urdf_receipt",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json",
        "PB00_URDF_EXECUTION_RECEIPT",
        "SOURCE_ONLY_EXECUTION_RECEIPT_WITH_TMC_F01_DISCLOSURE",
        True,
        "957CA67D7BCC2CB591DF2442F24532CA3DAE24F358FC69BF390AC1A20F6F021E",
    ),
    AssetSpec(
        "unified_r2_backend",
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/sim13_v2_backends/dynamics_backend.py",
        "PB00_ZERO_MOMENTUM_BACKEND",
        "NONPRODUCTION_HASH_BOUND_BACKEND",
        True,
    ),
    AssetSpec(
        "unified_r2_dynamics_kernel",
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/free_floating_dynamics.py",
        "PB00_TREE_DYNAMICS_KERNEL",
        "NONPRODUCTION_DIAGNOSTIC_KERNEL",
        True,
    ),
    AssetSpec(
        "r2_hf_model_v3",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round4_hf_rom_v3/R2_HF_MODEL_V3.yaml",
        "FLEX_HIGH_FIDELITY_REFERENCE",
        "PROVISIONAL_DERIVED_OWNER_ACCEPTED_FALSE_EXCLUDED_FROM_PB00",
    ),
    AssetSpec(
        "r2_seven_mode_rom_v3",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round4_hf_rom_v3/R2_SEVEN_MODE_ROM_V3.json",
        "FLEX_ROM_REFERENCE",
        "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS_EXCLUDED_FROM_PB00",
    ),
    AssetSpec(
        "design_contact_model",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/DESIGN_CONTACT_MODEL_V1.yaml",
        "CONTACT_SENSITIVITY_CONTRACT",
        "BOUNDED_PROVISIONAL_AS_BUILT_NULL",
    ),
    AssetSpec(
        "gripper_actuation_interface",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml",
        "GRIPPER_CONTACT_VELOCITY_CONTRACT",
        "CANDIDATE_PHYSICAL_VALUES_PARTIAL",
    ),
    AssetSpec(
        "joint_control_config",
        "20_engineering/config/control_scene/control_01_v0.yaml",
        "JOINT_ACTUATOR_MODEL_REFERENCE",
        "PROVISIONAL_NOT_HARDWARE_AUTHORITY",
    ),
    AssetSpec(
        "attitude_control_config",
        "20_engineering/config/attitude_stab/attitude_stab_v0.yaml",
        "BASE_ACTUATOR_MODEL_REFERENCE",
        "PROVISIONAL_NOT_HARDWARE_AUTHORITY",
    ),
    AssetSpec(
        "mechanical_release_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json",
        "CURRENT_MECHANICAL_TERMINAL_GATE",
        "GATE_A_NOT_PASSED",
    ),
    AssetSpec(
        "mechanical_handoff_gate",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/17_MECH_TO_EMBODIED_HANDOFF_GATE.json",
        "MECH_TO_EMBODIED_HANDOFF_GATE",
        "FAIL_11_OF_12_HARNESS",
    ),
    AssetSpec(
        "route_c_completed_gate_v1",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_MISSION_COVERAGE_GATE_V1.json",
        "LATEST_COMPLETED_ROUTE_C_GATE_AT_PREBIND_EXECUTION",
        "FAIL_DOCUMENTED_LIVE_MECHANICAL_LINE",
    ),
    AssetSpec(
        "route_c_mass_delta_candidate_v2",
        "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/B601_ROUTE_C_MASS_DELTA_BY_LINK_CANDIDATES_V2.json",
        "ROUTE_C_CANDIDATE_CONTAMINATION_SENTINEL",
        "DESIGN_CANDIDATE_RC5_PROPAGATION_FORBIDDEN",
    ),
    AssetSpec(
        "sim13_20_of_20_gate",
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json",
        "LATEST_SIM13_NEGATIVE_CONTROL_GATE",
        "PASS_20_OF_20_MAXIMUM_ABORT_ONLY_NO_SYSTEM_BINDING",
    ),
    AssetSpec(
        "mech_rl_interface_v2",
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
        "CURRENT_MECH_RL_INTERFACE_INSTANCE",
        "SYSTEM_BINDING_FALSE",
    ),
    AssetSpec(
        "e23_gate",
        "30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json",
        "CURRENT_R2_FULL_FLEX_RECERT_GATE",
        "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS_NO_RELEASE_CREDIT",
    ),
    AssetSpec(
        "control_01_gate",
        "30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json",
        "END_EFFECTOR_CONTROL_GATE",
        "REPEAT",
    ),
    AssetSpec(
        "control_02_gate",
        "30_simulation/control_02_base_attitude/results/control_02_gate_check.json",
        "BASE_ATTITUDE_CONTROL_GATE",
        "PASS_WITH_PROVISIONAL_SCOPE_L0_NOT_EVALUATED",
    ),
    AssetSpec(
        "safe_00_gate",
        "30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json",
        "FAIL_CLOSED_RUNTIME_SAFETY_GATE",
        "PASS_PENDING_REVIEW_NEXT_STAGE_FALSE",
    ),
    AssetSpec(
        "sim12_gate",
        "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json",
        "HISTORICAL_STRATEGY_CONSERVATION_COMPARATOR",
        "FROZEN_HISTORICAL_GATE_NOT_INHERITED",
    ),
)


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "AGENTS.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise RuntimeError("PROJECT_ROOT_NOT_FOUND")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_digest(document: Any) -> str:
    encoded = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_yaml(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_json(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"JSON_SOURCE_UNREADABLE:{path}") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError(f"JSON_SOURCE_NOT_OBJECT:{path}")
    return value


def load_yaml(path: Path) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise RuntimeError(f"YAML_SOURCE_UNREADABLE:{path}") from exc
    if not isinstance(value, Mapping):
        raise RuntimeError(f"YAML_SOURCE_NOT_MAPPING:{path}")
    return value


def build_hash_manifest(repo: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for spec in ASSETS:
        path = repo / spec.relative_path
        if not path.is_file():
            raise RuntimeError(f"AUTHORITY_ASSET_MISSING:{spec.asset_id}:{spec.relative_path}")
        digest = sha256_file(path)
        expected_match: bool | str = "NOT_PINNED_IN_PREBIND_RUNNER"
        if spec.expected_sha256 is not None:
            expected_match = digest == spec.expected_sha256
            if not expected_match:
                raise RuntimeError(f"AUTHORITY_HASH_DRIFT:{spec.asset_id}")
        row = {
            "asset_id": spec.asset_id,
            "path": spec.relative_path.replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": digest,
            "hash_mode": spec.hash_mode,
            "role": spec.role,
            "authority_status": spec.authority_status,
            "consumed_by_pb00": str(spec.consumed_by_pb00).lower(),
            "expected_hash_match": str(expected_match).lower() if isinstance(expected_match, bool) else expected_match,
        }
        rows.append(row)
        by_id[spec.asset_id] = row
    return rows, by_id


def git_snapshot(repo: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        process = subprocess.run(
            ["git", *args], cwd=repo, check=False, capture_output=True, text=True, encoding="utf-8"
        )
        if process.returncode != 0:
            raise RuntimeError(f"GIT_QUERY_FAILED:{' '.join(args)}:{process.stderr.strip()}")
        return process.stdout.strip()

    status = run("status", "--porcelain=v1", "-uno").splitlines()
    return {
        "head": run("rev-parse", "HEAD"),
        "branch": run("branch", "--show-current"),
        "tracked_modification_count": len(status),
        "dirty": bool(status or run("ls-files", "--others", "--exclude-standard")),
        "retention_credit": False,
        "note": "Internal SHA locators are usable; dirty/untracked assets do not receive Git retention credit.",
    }


def source_ref(asset: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "path": asset["path"],
        "bytes": int(asset["bytes"]),
        "sha256": asset["sha256"],
        "hash_mode": asset["hash_mode"],
    }


def build_gate_snapshot(repo: Path, assets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    mech = load_json(repo / assets["mechanical_release_gate"]["path"])
    handoff = load_json(repo / assets["mechanical_handoff_gate"]["path"])
    route_c = load_json(repo / assets["route_c_completed_gate_v1"]["path"])
    sim13 = load_json(repo / assets["sim13_20_of_20_gate"]["path"])
    e23 = load_json(repo / assets["e23_gate"]["path"])
    ctrl1 = load_json(repo / assets["control_01_gate"]["path"])
    ctrl2 = load_json(repo / assets["control_02_gate"]["path"])
    safe = load_json(repo / assets["safe_00_gate"]["path"])
    sim12 = load_json(repo / assets["sim12_gate"]["path"])
    v2_gate = repo / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_MISSION_COVERAGE_GATE_V2.json"
    return {
        "schema": "PREBIND_CURRENT_GATE_SNAPSHOT_V1",
        "phase": PHASE_ID,
        "generated_date_local": GENERATED_DATE_LOCAL,
        "tests_are_not_gates": True,
        "gates": [
            {
                "id": "MECHANICAL_GATE_A",
                "state": "HOLD",
                "source_verdict": mech.get("verdict"),
                "gate_a_pass": mech.get("gate_a_pass"),
                "review_status": mech.get("review_status"),
                "next_stage_authorized": mech.get("next_stage_authorized"),
                "release_credit": mech.get("release_credit"),
                "source": source_ref(assets["mechanical_release_gate"]),
            },
            {
                "id": "MECH_TO_EMBODIED_HANDOFF",
                "state": "HOLD",
                "source_verdict": handoff.get("verdict"),
                "score": "11/12",
                "blocking_item": "G12_HARNESS",
                "next_stage_authorized": handoff.get("next_stage_authorized"),
                "release_credit": handoff.get("release_credit"),
                "source": source_ref(assets["mechanical_handoff_gate"]),
            },
            {
                "id": "ROUTE_C_LATEST_COMPLETED",
                "state": "REPEAT",
                "source_verdict": route_c.get("verdict"),
                "mandatory_key_states": {"total": 10, "unsafe": 1},
                "trajectory_segments": {"required": 8, "unsafe": 3},
                "key_metrics": {
                    "worst_clearance_mm_gated": route_c.get("predicates", {}).get("clearance", {}).get("worst_mm_gated"),
                    "worst_pinch_mm_gated": route_c.get("predicates", {}).get("pinch", {}).get("worst_mm_gated"),
                    "minimum_bend_radius_mm": route_c.get("predicates", {}).get("bend_radius", {}).get("min_mm"),
                },
                "route_c_v2_gate_present": v2_gate.is_file(),
                "v2_log_is_not_gate": True,
                "source": source_ref(assets["route_c_completed_gate_v1"]),
            },
            {
                "id": "SIM13_NEGATIVE_CONTROLS",
                "state": "LIMITED",
                "source_verdict": sim13.get("verdict"),
                "score": sim13.get("nc_score"),
                "maximum_operational_state": sim13.get("maximum_operational_state"),
                "next_stage_authorized": sim13.get("next_stage_authorized"),
                "release_credit": sim13.get("release_credit"),
                "source": source_ref(assets["sim13_20_of_20_gate"]),
            },
            {
                "id": "E23_FULL_FLEX_RECERT",
                "state": "PROVISIONAL",
                "source_verdict": e23.get("technical_verdict"),
                "summary": e23.get("summary"),
                "next_stage_authorized": e23.get("next_stage_authorized"),
                "release_credit": e23.get("release_credit"),
                "source": source_ref(assets["e23_gate"]),
            },
            {
                "id": "CTRL_01_END_EFFECTOR",
                "state": "REPEAT",
                "source_verdict": ctrl1.get("verdict"),
                "next_stage_authorized": ctrl1.get("next_stage_authorized"),
                "source": source_ref(assets["control_01_gate"]),
            },
            {
                "id": "CTRL_02_BASE_ATTITUDE",
                "state": "LIMITED",
                "source_verdict": ctrl2.get("verdict"),
                "scope": "PASS_WITH_PROVISIONAL_SCOPE; 7/16 stabilized under provisional actuator/time-window model; L0 NOT_EVALUATED",
                "review_status": ctrl2.get("review_status"),
                "source": source_ref(assets["control_02_gate"]),
            },
            {
                "id": "SAFE_00_RUNTIME_GATE",
                "state": "PENDING_REVIEW",
                "source_verdict": safe.get("verdict"),
                "review_status": safe.get("review_status"),
                "next_stage_authorized": safe.get("next_stage_authorized"),
                "source": source_ref(assets["safe_00_gate"]),
            },
            {
                "id": "SIM12_HISTORICAL_COMPARATOR",
                "state": "VERIFIED_HISTORICAL_ONLY",
                "source_verdict": sim12.get("verdict"),
                "max_eps_H": sim12.get("gates", {}).get("GS1_conservation", {}).get("max_eps_H"),
                "credit_inherited": False,
                "source": source_ref(assets["sim12_gate"]),
            },
        ],
        "aggregate": {
            "state": "HOLD",
            "next_stage_authorized": False,
            "formal_performance_credit": False,
        },
    }


def conflict_rows() -> list[dict[str, str]]:
    return [
        {"id":"PB-C01","domain":"mass","severity":"BLOCKING","conflict":"V3_R2 design ledger and bridged dynamics candidate are both non-production; bridged values differ from stated values.","selected_prebind_disposition":"Use bridged lane for diagnostic only; no production mass authority claim.","state":"HOLD"},
        {"id":"PB-C02","domain":"target","severity":"BLOCKING","conflict":"22 kg and 150 kg values exist, but formal target mass/inertia/capture-transform authority is absent.","selected_prebind_disposition":"Keep target plant disabled; values only in bounded sensitivity overlay.","state":"HOLD"},
        {"id":"PB-C03","domain":"frames","severity":"BLOCKING","conflict":"Legacy dynamics mount is 185.25 mm while physical installation is 208 mm with +25.000014 deg clocking.","selected_prebind_disposition":"Only consume hash-pinned physical-dynamics bridge; owner confirmation still required.","state":"HOLD"},
        {"id":"PB-C04","domain":"contact","severity":"BLOCKING","conflict":"Gripper first-contact maximum 0.005 m/s conflicts 10x with design-contact nominal 0.05 m/s (lower bound 0.01 m/s).","selected_prebind_disposition":"Contact disabled; UNKNOWN never ALLOW until owner ruling.","state":"HOLD"},
        {"id":"PB-C05","domain":"actuators","severity":"BLOCKING","conflict":"Joint/base/gripper actuator dynamics and hardware-qualified limits are provisional or null; URDF literals are not hardware qualification.","selected_prebind_disposition":"PB-00 generalized effort fixed at exact zero; no control performance credit.","state":"HOLD"},
        {"id":"PB-C06","domain":"gate_freshness","severity":"MAJOR","conflict":"Terminal release snapshots Sim13 at 15/20 while module-local latest gate is 20/20.","selected_prebind_disposition":"Record scope and generated source independently; no cross-file overwrite or inherited release credit.","state":"LIMITED"},
        {"id":"PB-C07","domain":"route_c","severity":"BLOCKING","conflict":"Route-C V2 mass delta is 1.5688 kg design candidate; RC5 propagation is forbidden and no V2 completed gate exists.","selected_prebind_disposition":"Exclude Route-C from all PB-00 matrices and assert contamination=false.","state":"HOLD"},
        {"id":"PB-C08","domain":"configuration_management","severity":"BLOCKING","conflict":"Repository is dirty and current Mechanical R2/E23/Sim13 authorities are not all retained by Git.","selected_prebind_disposition":"Use raw-byte SHA locators only; grant no configuration retention credit.","state":"HOLD"},
        {"id":"PB-C09","domain":"governance","severity":"MAJOR","conflict":"Historical project state says NO_NEW_SIMULATION while current owner instruction authorizes only PB-G0/PB-G1 prebind work.","selected_prebind_disposition":"Treat current authorization as narrow supersession only for isolated PB-G0/PB-00 diagnostic; all later stages remain HOLD.","state":"LIMITED"},
        {"id":"PB-C10","domain":"path_migration","severity":"MAJOR","conflict":"sim05/sim11 still resolve removed root cad/docs/config paths after REORG04.","selected_prebind_disposition":"Do not restore forbidden root directories or patch frozen modules; use current Unified R2 backend adapter.","state":"LIMITED"},
        {"id":"PB-C11","domain":"schema","severity":"MAJOR","conflict":"Sim13 backend state lacks target, wheel, flex covariance, and full capture topology handoff fields.","selected_prebind_disposition":"Freeze extended state schema now; do not claim runtime binding.","state":"HOLD"},
    ]


def negative_result_rows() -> list[dict[str, str]]:
    return [
        {"id":"NR-01","source":"mechanical_release_gate","negative_result":"Mechanical Gate A not passed; TMG-4/TMG-6 internal blockers remain.","preservation":"VERBATIM_ACTIVE","effect":"PB_G0_HOLD"},
        {"id":"NR-02","source":"mechanical_handoff_gate","negative_result":"Mechanical-to-embodied handoff 11/12; harness G12 fails.","preservation":"VERBATIM_ACTIVE","effect":"NO_FORMAL_HANDOFF"},
        {"id":"NR-03","source":"route_c_completed_gate_v1","negative_result":"FAIL_DOCUMENTED: 1/10 mandatory state unsafe and 3/8 trajectories unsafe.","preservation":"VERBATIM_ACTIVE","effect":"ROUTE_C_EXCLUDED"},
        {"id":"NR-04","source":"e15_legacy","negative_result":"Legacy ANCF certification remains REPEAT; E23 does not rewrite it.","preservation":"VERBATIM_ACTIVE","effect":"FULL_MODEL_CERTIFICATION_LIMITED"},
        {"id":"NR-05","source":"control_01_gate","negative_result":"CTRL-01 remains REPEAT under frozen gains and preregistered trajectories.","preservation":"VERBATIM_ACTIVE","effect":"NO_TRACKING_CREDIT"},
        {"id":"NR-06","source":"control_02_gate","negative_result":"L0 hardware-valid stabilization not evaluated; only 7/16 under provisional actuator/time-window scope.","preservation":"VERBATIM_ACTIVE","effect":"NO_HARDWARE_STABILITY_CREDIT"},
        {"id":"NR-07","source":"safe_00_gate","negative_result":"SAFE-00 is pending review with next_stage_authorized=false.","preservation":"VERBATIM_ACTIVE","effect":"NO_EXECUTION_AUTHORITY"},
        {"id":"NR-08","source":"sim13_20_of_20_gate","negative_result":"20/20 negative controls yield maximum operational state ABORT_ONLY; system binding false.","preservation":"VERBATIM_ACTIVE","effect":"NO_RL_OR_CAPTURE_CREDIT"},
        {"id":"NR-09","source":"mass_frame_contact_authority","negative_result":"System/target authority, frame owner confirmation, actuator dynamics and contact speed ruling remain unresolved.","preservation":"REGISTERED_NEW","effect":"PB_G0_AUTHORITY_SUFFICIENCY_HOLD"},
        {"id":"NR-10","source":"repository_state","negative_result":"Dirty/untracked authorities lack Git retention credit.","preservation":"REGISTERED_NEW","effect":"NO_RELEASE_CREDIT"},
    ]


def build_prebind_authority(assets: Mapping[str, Mapping[str, Any]], git: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "PREBIND_AUTHORITY_V1",
        "phase": PHASE_ID,
        "owner_authorization": {
            "source": "CURRENT_CODEX_TASK_OWNER_INSTRUCTION_2026_08_26",
            "authorized_scope": ["PB_G0_AUTHORITY_BINDING", "PB00_NONCREDIT_DIAGNOSTIC_CHARACTERIZATION", "PB_G1_FAIL_CLOSED_RULING"],
            "prohibited_scope": ["FORMAL_CONTROL_RELEASE", "CONTACT_OR_CAPTURE_CREDIT", "ROUTE_C_MASS_PROPAGATION", "NMPC", "RL", "VLA", "HIL"],
        },
        "baseline": {
            "mechanical_main_body": "FROZEN",
            "active_mechanical_work": "ROUTE_C_ONLY_EXTERNAL_READ_ONLY_LIVE_LINE",
            "authoritative_arm_model": "ACCEPTED_B601",
            "task_envelope": "MANDATORY_CAPTURE_STATES_ONLY",
            "formal_performance_credit": False,
            "rl_vla_training": "HOLD",
        },
        "bindings": {
            "accepted_b601": source_ref(assets["accepted_b601_urdf"]),
            "diagnostic_system_urdf": source_ref(assets["unified_r2_urdf"]),
            "dynamics_mass_lane": source_ref(assets["system_mass_bridged_v1"]),
            "physical_dynamics_bridge": source_ref(assets["physical_dynamics_bridge"]),
            "unified_frame_tree": source_ref(assets["unified_r2_frame_tree"]),
        },
        "authority_sufficiency": {
            "locator_and_hash": "VERIFIED",
            "accepted_arm": "VERIFIED",
            "system_mass_inertia": "PROVISIONAL",
            "target_mass_inertia": "PROVISIONAL",
            "frame_owner_confirmation": "PENDING_REVIEW",
            "contact": "HOLD",
            "actuator_hardware": "HOLD",
            "route_c_mass_consumption": False,
        },
        "repository": dict(git),
        "maximum_claim": "DIAGNOSTIC_PREBIND_PARAMETER_MAPPING_AND_PB00_CHARACTERIZATION",
        "pb_g0_locator_hash_pass": True,
        "pb_g0_authority_sufficiency_pass": False,
        "pb_g1_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }


def build_plants(assets: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    accepted = {
        "schema": "ACCEPTED_PLANT_PREBIND_VIEW_V1",
        "plant_id": "ACCEPTED_COMPONENTS_R2_DIAGNOSTIC_PLANT",
        "status": "LIMITED",
        "interpretation": "Accepted-component view; the assembled system plant is not production-authorized.",
        "configuration": "C01_NO_ROUTE_C_SOURCE_ONLY",
        "topology": {"links": 19, "joints": 18, "movable_dof": 8, "revolute": 6, "prismatic": 2},
        "mass": {"value": 31.022864807342987, "unit": "kg", "frame": "S", "reference_point": "system_com", "uncertainty": "see bridged design ledger", "authority": "CANDIDATE_ONLY", "status": "PROVISIONAL", "source_artifact": assets["system_mass_bridged_v1"]["path"], "source_field": "configurations.C01.bridged_candidate.mass_kg"},
        "arm": {"model": "ACCEPTED_B601", "mass_kg": 4.695555949342986, "urdf": source_ref(assets["accepted_b601_urdf"]), "hardware_limits_preserved": True, "urdf_effort_velocity_are_hardware_authority": False},
        "system_model": {"urdf": source_ref(assets["unified_r2_urdf"]), "classification": "SOURCE_ONLY_BUILDER_EMISSION", "owner_accepted": False, "production_dynamics_ready": False},
        "frames": {"tree": source_ref(assets["unified_r2_frame_tree"]), "bridge": source_ref(assets["physical_dynamics_bridge"]), "owner_confirmation": "PENDING_REVIEW"},
        "flex": {"enabled": False, "reason": "PB00_RIGID_ZERO_CONTACT_BASELINE", "future_reference": source_ref(assets["r2_seven_mode_rom_v3"])},
        "contact": {"enabled": False, "reason": "CONTACT_AUTHORITY_CONFLICT_AND_AS_BUILT_NULL"},
        "target": {"enabled": False, "reason": "NO_TARGET_IN_PB00"},
        "generalized_effort": {"values": [0.0] * 8, "units": ["N*m"] * 6 + ["N"] * 2, "status": "EXACT_ZERO_PB00_STIMULUS"},
        "route_c": {"included": False, "mass_delta_consumed": False, "contamination_check": "VERIFIED_EXCLUDED_FROM_SOURCE_URDF"},
        "formal_performance_credit": False,
    }
    sensitivity = {
        "schema": "PREBIND_SENSITIVITY_PLANT_V1",
        "base_plant": "ACCEPTED_PLANT.yaml",
        "status": "PLANNED",
        "not_executed_in_phase0": True,
        "overlays": [
            {"id":"TARGET_22KG","parameter":"mass","nominal":22.0,"unit":"kg","authority":"LOW_CONFIDENCE_PROVISIONAL","source":assets["target_models"]["path"]},
            {"id":"TARGET_150KG","parameter":"mass","nominal":150.0,"standard_uncertainty":45.0,"unit":"kg","distribution":"NOT_DECLARED","authority":"PROVISIONAL","source":assets["target_models"]["path"]},
            {"id":"CONTACT_STIFFNESS","parameter":"normal_stiffness","nominal":1.0e6,"lower":1.0e5,"upper":1.0e7,"unit":"N/m","distribution":"BOUNDED_NOT_PROBABILISTIC","authority":"BOUNDED_PROVISIONAL","source":assets["design_contact_model"]["path"]},
            {"id":"CONTACT_WINDOW","parameter":"contact_window","nominal":0.02,"lower":0.005,"upper":0.1,"unit":"s","distribution":"BOUNDED_NOT_PROBABILISTIC","authority":"PROVISIONAL_SIM11","source":assets["design_contact_model"]["path"]},
            {"id":"FLEX_ROM","parameter":"basis","value":"B1_B3_T1_T4_7D","unit":"dimensionless_basis_id","authority":"PASS_WITH_DECLARED_PROVISIONAL_PHYSICS","source":assets["r2_seven_mode_rom_v3"]["path"]},
        ],
        "correlation_policy": "NO_CORRELATION_INVENTED; absent covariance remains UNKNOWN",
        "zero_fill_forbidden": True,
        "formal_performance_credit": False,
    }
    unified = {
        "schema": "UNIFIED_R2_PLANT_PREBIND_VIEW_V1",
        "plant_id": "UNIFIED_R2_C01_NO_ROUTE_C",
        "status": "PROVISIONAL",
        "model": source_ref(assets["unified_r2_urdf"]),
        "execution_receipt": source_ref(assets["unified_r2_urdf_receipt"]),
        "backend": source_ref(assets["unified_r2_backend"]),
        "topology": {"link_count": 19, "joint_count": 18, "physical_link_count": 16, "frame_only_link_count": 3, "movable_dof": 8},
        "total_mass": {"value":31.022864807342987,"unit":"kg","authority":"DESIGN_CANDIDATE","status":"PROVISIONAL"},
        "scope": "ZERO_MOMENTUM_FREE_FLOATING_STATE_EVOLUTION_NOT_CONTACT_NOT_PRODUCTION_AUTHORIZED",
        "excluded": ["ROUTE_C", "CONTACT", "TARGET", "FLEX_DYNAMICS", "ACTUATOR_DYNAMICS", "SENSOR_DYNAMICS"],
        "owner_accepted": False,
        "production_dynamics_ready": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return accepted, sensitivity, unified


def parameter_rows(assets: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"parameter_id":"system_mass_C01","value":"31.022864807342987","unit":"kg","frame":"S","reference_point":"system_com","uncertainty":"member-level ledger","authority":"CANDIDATE_ONLY","status":"PROVISIONAL","source_artifact":assets["system_mass_bridged_v1"]["path"],"source_field":"configurations.C01.bridged_candidate.mass_kg","pb00_consumed":"true"},
        {"parameter_id":"accepted_b601_mass","value":"4.695555949342986","unit":"kg","frame":"URDF_LINK_TREE","reference_point":"aggregate_com","uncertainty":"0.09391111898685972 kg design policy","authority":"ACCEPTED_URDF","status":"VERIFIED","source_artifact":assets["accepted_b601_urdf"]["path"],"source_field":"sum(link.inertial.mass)","pb00_consumed":"true"},
        {"parameter_id":"physical_dynamic_clocking","value":"25.000014","unit":"deg","frame":"A0_dynamics_to_A0_physical","reference_point":"A0","uncertainty":"null deterministic bridge geometry","authority":"FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION","status":"PENDING_REVIEW","source_artifact":assets["physical_dynamics_bridge"]["path"],"source_field":"bridge_constant_ruling.unique_bridge_clocking_deg","pb00_consumed":"true"},
        {"parameter_id":"physical_dynamic_translation","value":"0.02275","unit":"m","frame":"A0_dynamics","reference_point":"A0","uncertainty":"null deterministic bridge geometry","authority":"FROZEN_CANDIDATE_PENDING_OWNER_CONFIRMATION","status":"PENDING_REVIEW","source_artifact":assets["physical_dynamics_bridge"]["path"],"source_field":"T_PHYSICAL_TO_DYNAMIC.translation_m[2]","pb00_consumed":"true"},
        {"parameter_id":"target_22kg_mass","value":"22","unit":"kg","frame":"T","reference_point":"target_com","uncertainty":"low confidence","authority":"PROVISIONAL","status":"HOLD","source_artifact":assets["target_models"]["path"],"source_field":"target_satellite_v0.mass_kg","pb00_consumed":"false"},
        {"parameter_id":"target_150kg_mass","value":"150","unit":"kg","frame":"D","reference_point":"target_com","uncertainty":"standard_uncertainty=45 kg; distribution not declared","authority":"PROVISIONAL","status":"HOLD","source_artifact":assets["target_models"]["path"],"source_field":"target_debris_v0.mass_kg","pb00_consumed":"false"},
        {"parameter_id":"contact_normal_stiffness","value":"1e6 [1e5,1e7]","unit":"N/m","frame":"UNRESOLVED_CONTACT_FRAME","reference_point":"contact_point","uncertainty":"bounded nonprobabilistic","authority":"BOUNDED_PROVISIONAL","status":"HOLD","source_artifact":assets["design_contact_model"]["path"],"source_field":"normal_stiffness","pb00_consumed":"false"},
        {"parameter_id":"contact_window","value":"0.02 [0.005,0.1]","unit":"s","frame":"N/A","reference_point":"contact_interval","uncertainty":"bounded nonprobabilistic","authority":"PROVISIONAL_SIM11","status":"HOLD","source_artifact":assets["design_contact_model"]["path"],"source_field":"contact_window","pb00_consumed":"false"},
        {"parameter_id":"route_c_mass_delta","value":"1.5688","unit":"kg","frame":"per_link_candidate","reference_point":"per_link_com","uncertainty":"design candidate","authority":"RC5_PROPAGATION_FORBIDDEN","status":"HOLD","source_artifact":assets["route_c_mass_delta_candidate_v2"]["path"],"source_field":"candidate_total_mass_kg","pb00_consumed":"false"},
    ]


def build_frame_contract(assets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema": "PREBIND_FRAME_CONTRACT_V1",
        "status": "PENDING_REVIEW",
        "matrix_convention": "row-major homogeneous T_parent_child; p_parent = T_parent_child @ p_child",
        "quaternion_convention": {"order":"wxyz","meaning":"active body-to-inertial rotation","from_frame":"body","to_frame":"I"},
        "units": {"translation":"m","rotation_matrix":"dimensionless","angle":"rad unless field suffix is _deg"},
        "source_tree": source_ref(assets["unified_r2_frame_tree"]),
        "source_bridge": source_ref(assets["physical_dynamics_bridge"]),
        "frames": [
            {"id":"I","parent":None,"role":"inertial_root","physical":False},
            {"id":"S","parent":"I","role":"spacecraft_bus_body_frame","physical":True},
            {"id":"D_BUS_MATE_PHYSICAL","parent":"S","role":"physical_mating_datum","physical":False},
            {"id":"D_BUS_M6_PATTERN","parent":"D_BUS_MATE_PHYSICAL","role":"physical_clocked_pattern_datum","physical":False},
            {"id":"M3R_ROOT","parent":"D_BUS_M6_PATTERN","role":"physical_load_path","physical":True},
            {"id":"B601_BASE_PHYSICAL","parent":"M3R_ROOT","role":"accepted_arm_physical_root","physical":True},
            {"id":"M_DYNAMICS_NONPHYSICAL","parent":"S","role":"nonphysical_dynamics_reference","physical":False},
            {"id":"E","parent":"B601_BASE_PHYSICAL","role":"end_effector_kinematic_frame","physical":False},
            {"id":"TARGET","parent":"I","role":"scenario_target_frame","physical":True,"status":"HOLD_UNBOUND_IN_PB00"},
        ],
        "unique_physical_to_dynamics_bridge": {
            "definition":"B = inv(T_S_A0_dynamics) @ T_S_A0_physical; p_A0dyn = B @ p_A0physical",
            "translation_m":[0.0,0.0,0.022749999999999992],
            "rotation_axis_in_A0_dynamics":[0.0,0.0,1.0],
            "rotation_angle_deg":25.000013999964253,
            "quaternion_wxyz":[0.9762959806769003,0.0,0.0,0.21643973321488344],
            "homogeneous_4x4":[[0.906307683772,-0.422618483193,0.0,0.0],[0.422618483193,0.906307683772,0.0,0.0],[0.0,0.0,1.0,0.022749999999999992],[0.0,0.0,0.0,1.0]],
            "owner_confirmation":"PENDING_REVIEW",
        },
        "configuration_mapping": {"system_configuration_id":"C01","urdf_configuration_id":"C01_NO_ROUTE_C","pb00_state_configuration":"C01_TO_FREE_MOTION_GENERALIZED_STATE","mapping_status":"LIMITED_DIAGNOSTIC"},
        "invariants": ["D and M may share selected numeric origins but are never semantic aliases", "physical load path must pass through D_BUS_MATE_PHYSICAL and never through M_DYNAMICS_NONPHYSICAL", "no frame averaging", "no per-module physical/dynamics frame mixing", "unknown target/contact frame never defaults to S"],
        "next_stage_authorized": False,
    }


def build_state_schema() -> dict[str, Any]:
    vector3 = {"type":"array","items":{"type":"number"},"minItems":3,"maxItems":3}
    quaternion = {"type":"array","items":{"type":"number"},"minItems":4,"maxItems":4}
    return {
        "$schema":"https://json-schema.org/draft/2020-12/schema",
        "$id":"STATE_HANDOFF_SCHEMA_V1",
        "title":"Dynamics Control Prebind State Handoff",
        "type":"object",
        "additionalProperties":False,
        "required":["schema","handoff_id","scenario_id","time","plant_binding","topology","servicer","joint_channels","safe00"],
        "properties":{
            "schema":{"const":"PREBIND_STATE_HANDOFF_V1"},
            "handoff_id":{"type":"string","minLength":1},
            "scenario_id":{"type":"string","minLength":1},
            "episode_id":{"type":"string"},
            "time":{"type":"object","additionalProperties":False,"required":["value","unit","valid_until"],"properties":{"value":{"type":"number"},"unit":{"const":"s"},"valid_until":{"type":"number"}}},
            "plant_binding":{"type":"object","additionalProperties":False,"required":["plant_sha256","frame_contract_sha256","schema_sha256","source_backend","destination_backend"],"properties":{"plant_sha256":{"type":"string","pattern":"^[A-F0-9]{64}$"},"frame_contract_sha256":{"type":"string","pattern":"^[A-F0-9]{64}$"},"schema_sha256":{"type":"string","pattern":"^[A-F0-9]{64}$"},"source_backend":{"type":"string"},"destination_backend":{"type":"string"}}},
            "topology":{"enum":["PRE_CAPTURE","COMPLIANT_CAPTURE","LOCKED_COMPOSITE"]},
            "servicer":{"type":"object","additionalProperties":False,"required":["position","quaternion","linear_velocity","angular_velocity"],"properties":{"position":{"type":"object","required":["values","unit","expressed_in","reference_point"],"properties":{"values":vector3,"unit":{"const":"m"},"expressed_in":{"const":"I"},"reference_point":{"type":"string"}}},"quaternion":{"type":"object","required":["values","order","from_frame","to_frame"],"properties":{"values":quaternion,"order":{"const":"wxyz"},"from_frame":{"type":"string"},"to_frame":{"const":"I"}}},"linear_velocity":{"type":"object","required":["values","unit","expressed_in","reference_point"],"properties":{"values":vector3,"unit":{"const":"m/s"},"expressed_in":{"type":"string"},"reference_point":{"type":"string"}}},"angular_velocity":{"type":"object","required":["values","unit","expressed_in"],"properties":{"values":vector3,"unit":{"const":"rad/s"},"expressed_in":{"type":"string"}}}}},
            "joint_channels":{"type":"array","minItems":8,"maxItems":8,"items":{"type":"object","additionalProperties":False,"required":["name","joint_type","q","q_unit","dq","dq_unit","effort","effort_unit"],"properties":{"name":{"enum":["joint1","joint2","joint3","joint4","joint5","joint6","gripper_joint1","gripper_joint2"]},"joint_type":{"enum":["REVOLUTE","PRISMATIC"]},"q":{"type":"number"},"q_unit":{"enum":["rad","m"]},"dq":{"type":"number"},"dq_unit":{"enum":["rad/s","m/s"]},"effort":{"type":["number","null"]},"effort_unit":{"enum":["N*m","N"]}}}},
            "wheel_momentum":{"type":["object","null"]},
            "flex_state":{"type":["object","null"],"properties":{"basis_id":{"type":"string"},"basis_sha256":{"type":"string"},"eta":{"type":"array","items":{"type":"number"}},"eta_dot":{"type":"array","items":{"type":"number"}}}},
            "target":{"type":["object","null"]},
            "attachment_transform":{"type":["object","null"]},
            "contact_state":{"type":["object","null"]},
            "safe00":{"type":"object","additionalProperties":False,"required":["physical_state","decision","request_sha256","response_sha256"],"properties":{"physical_state":{"enum":["SAFE","UNSAFE","UNKNOWN"]},"decision":{"enum":["ALLOW","MODIFY","WAIT","BACKOFF","ABORT"]},"request_sha256":{"type":"string"},"response_sha256":{"type":"string"}}},
            "continuity_ledger":{"type":["object","null"]},
        },
        "x_fail_closed_rules":["null is never converted to zero", "PREGRASP pose is not CAPTURE topology", "heterogeneous global norms are forbidden", "UNKNOWN physical state never maps to ALLOW", "before/after impulse and momentum quantities retain units, frames and reference points"],
    }


def build_solver_mapping(assets: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema":"PREBIND_SOLVER_MAPPING_V1",
        "mapping_id":"UNIFIED_R2_BACKEND_TO_PREBIND_STATE_V1",
        "status":"LIMITED",
        "backend":{"id":"SIM13_V2_UNIFIED_R2_FREE_FLOATING_DYNAMICS_BACKEND_V1","source":source_ref(assets["unified_r2_backend"]),"kernel":source_ref(assets["unified_r2_dynamics_kernel"]),"scope":"ZERO_MOMENTUM_FREE_FLOATING_STATE_EVOLUTION_NOT_CONTACT_NOT_PRODUCTION_AUTHORIZED"},
        "input":{"q":{"channels":["joint1","joint2","joint3","joint4","joint5","joint6","gripper_joint1","gripper_joint2"],"units":["rad"]*6+["m"]*2},"qdot":{"units":["rad/s"]*6+["m/s"]*2},"effort":{"units":["N*m"]*6+["N"]*2}},
        "output":{"base_position":{"unit":"m","frame":"I"},"base_quaternion":{"order":"wxyz","mapping":"body_to_inertial"},"base_twist":{"linear_unit":"m/s","angular_unit":"rad/s","expressed_in":"body/root"},"momentum":{"linear_unit":"N*s","angular_unit":"N*m*s","reference_point":"root"},"energy":{"unit":"J"}},
        "solver":{"method":"fixed_step_RK4_reduced_zero_momentum","coarse_step_s":0.002,"fine_step_s":0.001,"terminal_time_s":0.02,"random_seed":DEFAULT_SEED},
        "finite_difference":{"method":"centered_Richardson","revolute_step_rad":2.0e-5,"prismatic_step_m":2.0e-6},
        "unsupported_fields":["target state/covariance","wheel dynamics","flex eta/eta_dot","contact/compliance","actuator electrical dynamics","sensor/estimator covariance"],
        "approximation_class":"RIGID_SOURCE_ONLY_ZERO_CONTACT_DIAGNOSTIC",
        "classification_flip_policy":"Any missing source, hash drift, unsupported required field, unit/frame ambiguity, or Route-C contamination => HOLD/UNKNOWN; never ALLOW.",
        "next_stage_authorized":False,
    }


def build_capture_fsm() -> dict[str, Any]:
    return {
        "schema":"PREBIND_CAPTURE_FSM_V1",
        "status":"PLANNED",
        "states":[
            {"id":"RPO","topology":"PRE_CAPTURE"},
            {"id":"TASK_READY","topology":"PRE_CAPTURE"},
            {"id":"PREGRASP","topology":"PRE_CAPTURE"},
            {"id":"COMPLIANT_CAPTURE","topology":"COMPLIANT_CAPTURE"},
            {"id":"LOCKED_COMPOSITE","topology":"LOCKED_COMPOSITE"},
            {"id":"SAFE_RECOVERY","topology":"PRE_CAPTURE_OR_LOCKED_BY_SCENARIO"},
            {"id":"ABORT","topology":"FAIL_CLOSED"},
        ],
        "transitions":[
            {"from":"RPO","to":"TASK_READY","guard":"handoff schema+plant+frame hashes valid AND SAFE00 decision ALLOW","phase0":"NOT_EVALUATED"},
            {"from":"TASK_READY","to":"PREGRASP","guard":"mechanical Route-C mission state SAFE AND control authority valid","phase0":"HOLD"},
            {"from":"PREGRASP","to":"COMPLIANT_CAPTURE","guard":"contact authority resolved AND state continuity ledger open","phase0":"HOLD"},
            {"from":"COMPLIANT_CAPTURE","to":"LOCKED_COMPOSITE","guard":"attachment transform + impulse/momentum/energy ledger close","phase0":"HOLD"},
            {"from":"*","to":"ABORT","guard":"UNKNOWN/UNSAFE/hash drift/schema mismatch/physics veto","phase0":"ACTIVE_FAIL_CLOSED_RULE"},
        ],
        "invariants":["No pose snap", "Contact and locked constraint are mutually exclusive", "PREGRASP posture cannot stand in for CAPTURE topology", "150 kg/3 deg/s anchor remains physics veto/abort unless a later authorized Gate proves otherwise"],
    }


def scenario_rows() -> list[dict[str, str]]:
    return [
        {"scenario_id":"PB00_C0","name":"Unified R2 zero-effort free-floating conservation","plant":"UNIFIED_R2_C01_NO_ROUTE_C","target":"NONE","contact":"OFF","flex":"OFF","control":"ZERO_GENERALIZED_EFFORT","phase0_action":"EXECUTED_DIAGNOSTIC","gate_credit":"NONE","state":"LIMITED"},
        {"scenario_id":"PB01_RPO_TASK_READY","name":"RPO to TASK_READY state handoff","plant":"ACCEPTED_COMPONENTS_R2","target":"NONE","contact":"OFF","flex":"OFF","control":"NOT_BOUND","phase0_action":"SCHEMA_ONLY","gate_credit":"NONE","state":"HOLD"},
        {"scenario_id":"PB02_TASK_READY_PREGRASP","name":"TASK_READY to PREGRASP continuity","plant":"ACCEPTED_COMPONENTS_R2","target":"PRESENT_NOT_CAPTURED","contact":"OFF","flex":"PLANNED","control":"NOT_BOUND","phase0_action":"NOT_RUN","gate_credit":"NONE","state":"HOLD"},
        {"scenario_id":"PB03_CAPTURE_22KG","name":"PREGRASP to 22 kg compliant capture","plant":"SENSITIVITY_OVERLAY","target":"22KG_PROVISIONAL","contact":"PROVISIONAL_DISABLED","flex":"PLANNED","control":"NOT_BOUND","phase0_action":"NOT_RUN","gate_credit":"NONE","state":"HOLD"},
        {"scenario_id":"PB04_VETO_150KG","name":"150 kg at 3 deg/s physics veto anchor","plant":"SENSITIVITY_OVERLAY","target":"150KG_PROVISIONAL","contact":"DISABLED","flex":"UNKNOWN","control":"ABORT_ONLY","phase0_action":"PRESERVE_HISTORICAL_VETO","gate_credit":"NONE","state":"REPEAT"},
    ]


def negative_case_rows() -> list[dict[str, str]]:
    return [
        {"case_id":"NC-PB-01","stimulus":"accepted B601 hash drift","expected":"HOLD_AUTHORITY_HASH_DRIFT","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-02","stimulus":"Route-C mass appears in PB00 plant","expected":"HOLD_CANDIDATE_CONTAMINATION","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-03","stimulus":"UNKNOWN SAFE physical state requested as ALLOW","expected":"ABORT","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-04","stimulus":"PREGRASP pose relabeled as LOCKED_COMPOSITE","expected":"HOLD_TOPOLOGY_SNAP","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-05","stimulus":"mixed rad/m channel reduced with global norm","expected":"HOLD_DIMENSIONAL_MISMATCH","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-06","stimulus":"missing contact/target field silently zero-filled","expected":"HOLD_NULL_TO_ZERO_FORBIDDEN","phase0":"CONTRACTED"},
        {"case_id":"NC-PB-07","stimulus":"phase-only state change","expected":"DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY","phase0":"INHERITED_BACKEND_NEGATIVE_CONTROL_NOT_GATE_CREDIT"},
    ]


def load_backend(repo: Path):
    v2_root = repo / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    runtime_root = v2_root / "runtime_fail_closed_backends_v2"
    for entry in (str(runtime_root), str(v2_root)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from sim13_v2_backends.dynamics_backend import BackendState, UnifiedR2DynamicsBackend
    return UnifiedR2DynamicsBackend(project_root=repo), BackendState


def make_initial_state(backend: Any, backend_state: Any) -> Any:
    q = np.array((-1.570796, -1.047198, -2.094395, -0.523599, 0.0, 0.0, 0.03575, 0.03575))
    qdot = np.array((0.010, -0.008, 0.006, 0.004, -0.003, 0.002, 0.0005, -0.0004))
    position = np.zeros(3)
    quaternion = np.array((1.0, 0.0, 0.0, 0.0))
    twist = backend.mechanical_connection(q) @ qdot
    ee = backend.ee_centroid_inertial(q, position, quaternion)
    return backend_state(tuple(q), tuple(qdot), tuple(position), tuple(quaternion), tuple(twist), tuple(ee), "PB00_ZERO_EFFORT_FREE_MOTION")


def state_record(backend: Any, state: Any, time_s: float) -> dict[str, Any]:
    q = np.asarray(state.q_mixed_rad_m, dtype=float)
    qdot = np.asarray(state.qdot_mixed_rad_s_m_s, dtype=float)
    twist = backend.mechanical_connection(q) @ qdot
    momentum = backend.tree.momentum(q, twist, qdot)
    energy = backend.tree.kinetic_energy_j(q, twist, qdot)
    return {
        "time_s": float(time_s),
        "q_revolute_rad": q[:6].tolist(),
        "q_prismatic_m": q[6:].tolist(),
        "qdot_revolute_rad_s": qdot[:6].tolist(),
        "qdot_prismatic_m_s": qdot[6:].tolist(),
        "base_position_inertial_m": list(state.base_position_inertial_m),
        "base_quaternion_body_to_inertial_wxyz": list(state.base_quaternion_body_to_inertial_wxyz),
        "base_linear_velocity_body_m_s": twist[:3].tolist(),
        "base_angular_velocity_body_rad_s": twist[3:].tolist(),
        "linear_momentum_root_Ns": momentum.linear_root_kg_m_s.tolist(),
        "angular_momentum_about_root_Nms": momentum.angular_about_root_kg_m2_s.tolist(),
        "linear_momentum_residual_norm_Ns": float(np.linalg.norm(momentum.linear_root_kg_m_s)),
        "angular_momentum_residual_norm_Nms": float(np.linalg.norm(momentum.angular_about_root_kg_m2_s)),
        "kinetic_energy_J": float(energy),
    }


def propagate(backend: Any, state: Any, step_s: float, steps: int, keep_history: bool) -> tuple[Any, list[dict[str, Any]]]:
    current = state
    history = [state_record(backend, current, 0.0)] if keep_history else []
    if keep_history:
        for index in range(steps):
            current, assessment, audit = backend.advance(current, generalized_effort=np.zeros(8), step_s=step_s, steps=1)
            if not assessment.get("accepted") or not audit.get("momentum_conserved_within_limit"):
                raise RuntimeError("PB00_BACKEND_STEP_REJECTED")
            history.append(state_record(backend, current, (index + 1) * step_s))
    else:
        current, assessment, audit = backend.advance(current, generalized_effort=np.zeros(8), step_s=step_s, steps=steps)
        if not assessment.get("accepted") or not audit.get("momentum_conserved_within_limit"):
            raise RuntimeError("PB00_BACKEND_RUN_REJECTED")
    return current, history


def quaternion_distance(left: Sequence[float], right: Sequence[float]) -> float:
    alignment = abs(float(np.asarray(left, dtype=float) @ np.asarray(right, dtype=float)))
    return 2.0 * math.acos(float(np.clip(alignment, -1.0, 1.0)))


def run_pb00(repo: Path, seed: int, assets: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    np.random.seed(seed)
    backend, backend_state = load_backend(repo)
    initial = make_initial_state(backend, backend_state)
    coarse, _ = propagate(backend, initial, 0.002, 10, keep_history=False)
    fine, history = propagate(backend, initial, 0.001, 20, keep_history=True)
    replay, replay_history = propagate(backend, initial, 0.001, 20, keep_history=True)

    energies = np.array([row["kinetic_energy_J"] for row in history])
    linear = np.array([row["linear_momentum_residual_norm_Ns"] for row in history])
    angular = np.array([row["angular_momentum_residual_norm_Nms"] for row in history])
    energy_scale = float(energies[0])
    relative_energy_drift = float(np.max(np.abs(energies - energy_scale)) / energy_scale)
    coarse_q = np.asarray(coarse.q_mixed_rad_m)
    fine_q = np.asarray(fine.q_mixed_rad_m)
    coarse_qdot = np.asarray(coarse.qdot_mixed_rad_s_m_s)
    fine_qdot = np.asarray(fine.qdot_mixed_rad_s_m_s)
    convergence = {
        "revolute_q_max_abs_rad": float(np.max(np.abs(coarse_q[:6] - fine_q[:6]))),
        "prismatic_q_max_abs_m": float(np.max(np.abs(coarse_q[6:] - fine_q[6:]))),
        "revolute_qdot_max_abs_rad_s": float(np.max(np.abs(coarse_qdot[:6] - fine_qdot[:6]))),
        "prismatic_qdot_max_abs_m_s": float(np.max(np.abs(coarse_qdot[6:] - fine_qdot[6:]))),
        "base_position_norm_m": float(np.linalg.norm(np.asarray(coarse.base_position_inertial_m) - np.asarray(fine.base_position_inertial_m))),
        "base_quaternion_geodesic_rad": quaternion_distance(coarse.base_quaternion_body_to_inertial_wxyz, fine.base_quaternion_body_to_inertial_wxyz),
    }
    thresholds = {
        "relative_energy_drift_max": 2.0e-8,
        "linear_momentum_residual_max_Ns": 2.0e-13,
        "angular_momentum_residual_max_Nms": 2.0e-13,
        "revolute_q_convergence_max_rad": 2.0e-8,
        "prismatic_q_convergence_max_m": 2.0e-9,
        "revolute_qdot_convergence_max_rad_s": 2.0e-8,
        "prismatic_qdot_convergence_max_m_s": 2.0e-9,
        "base_position_convergence_max_m": 2.0e-9,
        "base_quaternion_convergence_max_rad": 2.0e-8,
    }
    replay_hash = canonical_digest(replay_history)
    history_hash = canonical_digest(history)
    checks = {
        "energy_conservation": relative_energy_drift < thresholds["relative_energy_drift_max"],
        "linear_momentum_conservation": float(np.max(linear)) < thresholds["linear_momentum_residual_max_Ns"],
        "angular_momentum_conservation": float(np.max(angular)) < thresholds["angular_momentum_residual_max_Nms"],
        "revolute_q_step_convergence": convergence["revolute_q_max_abs_rad"] < thresholds["revolute_q_convergence_max_rad"],
        "prismatic_q_step_convergence": convergence["prismatic_q_max_abs_m"] < thresholds["prismatic_q_convergence_max_m"],
        "revolute_qdot_step_convergence": convergence["revolute_qdot_max_abs_rad_s"] < thresholds["revolute_qdot_convergence_max_rad_s"],
        "prismatic_qdot_step_convergence": convergence["prismatic_qdot_max_abs_m_s"] < thresholds["prismatic_qdot_convergence_max_m_s"],
        "base_position_step_convergence": convergence["base_position_norm_m"] < thresholds["base_position_convergence_max_m"],
        "base_quaternion_step_convergence": convergence["base_quaternion_geodesic_rad"] < thresholds["base_quaternion_convergence_max_rad"],
        "deterministic_replay": history_hash == replay_hash and fine.as_dict() == replay.as_dict(),
        "route_c_excluded": "no_route_c" in assets["unified_r2_urdf"]["path"],
        "generalized_effort_exact_zero": True,
        "contact_disabled": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"PB00_DIAGNOSTIC_CHECK_FAILED:{checks}")
    sim12 = load_json(repo / assets["sim12_gate"]["path"])
    ledger = {
        "schema":"PREBIND_PB00_MOMENTUM_LEDGER_V1",
        "phase":PHASE_ID,
        "case_id":"PB00_C0",
        "classification":"LIMITED_DIAGNOSTIC_CHARACTERIZATION_NO_GATE_INHERITANCE",
        "plant":{"id":"UNIFIED_R2_C01_NO_ROUTE_C","total_mass":{"value":backend.tree.total_mass_kg,"unit":"kg"},"source_manifest":backend.source_manifest()},
        "stimulus":{"generalized_effort_values":[0.0]*8,"generalized_effort_units":["N*m"]*6+["N"]*2,"contact":"OFF","target":"NONE","flex":"OFF","initial_q_revolute_rad":list(initial.q_mixed_rad_m[:6]),"initial_q_prismatic_m":list(initial.q_mixed_rad_m[6:]),"initial_qdot_revolute_rad_s":list(initial.qdot_mixed_rad_s_m_s[:6]),"initial_qdot_prismatic_m_s":list(initial.qdot_mixed_rad_s_m_s[6:])},
        "integration":{"method":"fixed_step_RK4_reduced_zero_momentum","coarse":{"step_s":0.002,"steps":10},"fine":{"step_s":0.001,"steps":20},"terminal_time_s":0.02,"seed":seed},
        "metrics":{"initial_kinetic_energy_J":energy_scale,"relative_energy_drift_max":relative_energy_drift,"linear_momentum_residual_max_Ns":float(np.max(linear)),"angular_momentum_residual_max_Nms":float(np.max(angular)),"time_step_convergence":convergence,"fine_history_sha256":history_hash,"replay_history_sha256":replay_hash},
        "thresholds":thresholds,
        "checks":checks,
        "technical_characterization":"PASS",
        "historical_comparison":{"sim12_max_eps_H":sim12.get("gates",{}).get("GS1_conservation",{}).get("max_eps_H"),"comparison_semantics":"ORDER_OF_MAGNITUDE_CONTEXT_ONLY_DIFFERENT_PLANT_AND_METRIC_NO_PASS_INHERITANCE","sim05_historical_peak_base_attitude_deg":19.20,"sim05_historical_momentum_residual":7.3e-17,"sim05_current_head_replay":"BLOCKED_BY_REORG04_STALE_PATHS"},
        "limitations":["Source-only Unified R2 URDF excludes Route-C", "Rigid PB-00 excludes flex/contact/target/actuator/sensor dynamics", "Zero total momentum residual is audited about backend root", "System and frame owner authorities remain incomplete", "This diagnostic cannot unlock PB-G1 while PB-G0-A is HOLD"],
        "formal_performance_credit":False,
        "next_stage_authorized":False,
        "release_credit":False,
    }
    timeseries = {
        "schema":"PREBIND_PB00_TIMESERIES_V1",
        "case_id":"PB00_C0_FINE",
        "units":{"time":"s","revolute_q":"rad","prismatic_q":"m","revolute_qdot":"rad/s","prismatic_qdot":"m/s","base_position":"m","base_linear_velocity":"m/s","base_angular_velocity":"rad/s","linear_momentum":"N*s","angular_momentum":"N*m*s","kinetic_energy":"J"},
        "records":history,
        "canonical_records_sha256":history_hash,
    }
    return ledger, timeseries


def build_gates(assets: Mapping[str, Mapping[str, Any]], ledger: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    g0_criteria = [
        {"id":"G0-L1","criterion":"All declared authority assets locate and hash","status":"PASS"},
        {"id":"G0-L2","criterion":"Accepted B601 raw hash matches frozen value","status":"PASS","value":assets["accepted_b601_urdf"]["sha256"]},
        {"id":"G0-L3","criterion":"PB00 Unified R2 source excludes Route-C and Route-C mass is not consumed","status":"PASS"},
        {"id":"G0-A1","criterion":"Production-authoritative system configuration mass/inertia","status":"HOLD"},
        {"id":"G0-A2","criterion":"Formal target mass/inertia/capture-transform authority","status":"HOLD"},
        {"id":"G0-A3","criterion":"Physical-dynamics frame owner confirmation","status":"HOLD"},
        {"id":"G0-A4","criterion":"Hardware-valid joint/base/gripper actuator dynamics","status":"HOLD"},
        {"id":"G0-A5","criterion":"Contact velocity/stiffness/frame authority conflict resolved","status":"HOLD"},
        {"id":"G0-A6","criterion":"Configuration retention / clean frozen baseline","status":"HOLD"},
    ]
    g0 = {
        "schema":"PREBIND_PB_G0_GATE_V1","scope":"AUTHORITY_FRAME_UNIT_AND_BASELINE_PREBIND","criteria":g0_criteria,
        "summary":{"pass":3,"hold":6,"total":9},
        "key_metrics":{"locator_hash_layer":"PASS","authority_sufficiency_layer":"HOLD","route_c_mass_consumed":False},
        "authority_dispositions":["DIAGNOSTIC_PREBIND_ONLY","NO_CONTACT","NO_TARGET","ZERO_GENERALIZED_EFFORT_PB00_ONLY"],
        "risk_and_followup":["Owner-confirm system/target mass and frame bridge", "Resolve 0.005 vs 0.05 m/s contact-speed conflict", "Bind hardware actuator dynamics", "Freeze retained baseline in version control"],
        "evidence_hashes":{"accepted_b601":assets["accepted_b601_urdf"]["sha256"],"unified_r2":assets["unified_r2_urdf"]["sha256"],"frame_bridge":assets["physical_dynamics_bridge"]["sha256"]},
        "verdict":"PB_G0_HOLD_PARTIAL_AUTHORITY__DIAGNOSTIC_PREBIND_ONLY__NO_RELEASE_CREDIT",
        "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
    }
    pb00_gate = {
        "schema":"PREBIND_PB00_CHARACTERIZATION_GATE_V1",
        "scope":"NONCREDIT_UNIFIED_R2_ZERO_EFFORT_NUMERICAL_CHARACTERIZATION",
        "criteria":[{"id":key,"status":"PASS" if value else "FAIL"} for key,value in ledger["checks"].items()],
        "summary":{"passed":sum(bool(v) for v in ledger["checks"].values()),"total":len(ledger["checks"]),"failed":[k for k,v in ledger["checks"].items() if not v]},
        "key_metrics":ledger["metrics"],
        "technical_characterization":"PASS",
        "authority_disposition":"NONCREDIT_DIAGNOSTIC_ONLY_PB_G0_A_REMAINS_HOLD",
        "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
    }
    g1_criteria = [
        {"id":"G1-00","criterion":"PB-G0 aggregate PASS prerequisite","status":"HOLD","reason":"PB-G0-A authority sufficiency not passed"},
        {"id":"G1-01","criterion":"PB-00 linear/angular momentum and energy characterization","status":"PASS_DIAGNOSTIC_NO_CREDIT"},
        {"id":"G1-02","criterion":"PB-00 time-step convergence","status":"PASS_DIAGNOSTIC_NO_CREDIT"},
        {"id":"G1-03","criterion":"PB-00 deterministic replay","status":"PASS_DIAGNOSTIC_NO_CREDIT"},
        {"id":"G1-04","criterion":"RPO to TASK_READY state handoff continuity","status":"NOT_EVALUATED"},
        {"id":"G1-05","criterion":"PREGRASP to compliant/locked capture continuity","status":"NOT_EVALUATED"},
    ]
    g1 = {
        "schema":"PREBIND_PB_G1_GATE_V1","scope":"PB00_AND_STATE_HANDOFF_CONTINUITY",
        "criteria":g1_criteria,"summary":{"pass_diagnostic_no_credit":3,"hold_or_not_evaluated":3,"total":6},
        "key_metrics":ledger["metrics"],
        "authority_dispositions":["PB00 characterization retained", "PB-G1 not entered for credit", "State transitions remain schema-only"],
        "risk_and_followup":["Close PB-G0-A before any handoff or contact run", "Do not start NMPC/RL/VLA"],
        "verdict":"PB_G1_HOLD_NOT_AUTHORIZED_BY_PB_G0__PB00_DIAGNOSTIC_CHARACTERIZATION_AVAILABLE__NO_RELEASE_CREDIT",
        "review_status":"PENDING_OWNER_REVIEW","next_stage_authorized":False,"release_credit":False,
    }
    return g0, pb00_gate, g1


def classify_dirty_path(path: str, status: str) -> tuple[str, str, str]:
    lower = path.lower()
    name = Path(path).name.lower()
    if path.replace("\\", "/").startswith(MODULE_REL.as_posix() + "/"):
        return "CURRENT_PREBIND_WORK_PRODUCT", "KEEP", "Current authorized isolated work product"
    if status != "??":
        return "TRACKED_MODIFICATION", "KEEP_REVIEW", "Existing tracked user change; never auto-delete"
    if lower.startswith((".pytest-tmp/", ".pytest_tmp_")) or "__pycache__" in lower or name.endswith((".pyc", ".stackdump")):
        return "REGENERABLE_TEST_CACHE", "DELETE_SAFE", "Pure runtime/test cache"
    if "/quarantine/" in lower or "/authorization_package/" in lower or "/backup/" in lower or name.endswith((".fcbak", ".log")):
        return "MECHANICAL_MIDDLEWARE_CANDIDATE", "REVIEW_BEFORE_DELETE", "Likely intermediate/receipt material; may still carry negative evidence"
    if "/_work/" in lower or name.endswith("_attach_only.py") or name.endswith("_attach_only.ps1"):
        return "BUILD_MIDDLEWARE_CANDIDATE", "REVIEW_BEFORE_DELETE", "Build orchestration or work package; reproducibility dependency must be checked"
    if lower.startswith("20_engineering/"):
        return "MECHANICAL_RESEARCH_ASSET", "KEEP_PENDING_VERSION_CONTROL", "Mechanical source/evidence/release asset"
    if lower.startswith("30_simulation/"):
        return "SIMULATION_RESEARCH_ASSET", "KEEP_PENDING_VERSION_CONTROL", "Simulation source/evidence asset"
    if lower.startswith(("10_research/", "01_project/", "40_evidence/", "50_literature/")):
        return "RESEARCH_OR_EVIDENCE_ASSET", "KEEP_PENDING_VERSION_CONTROL", "Research, decision, or evidence asset"
    return "UNRESOLVED_UNTRACKED", "REVIEW_BEFORE_DELETE", "Untracked scope not proven regenerable"


def build_dirty_inventory(repo: Path, module: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    process = subprocess.run(["git","status","--porcelain=v1","-z","-uall"],cwd=repo,check=False,capture_output=True)
    if process.returncode != 0:
        raise RuntimeError("GIT_DIRTY_INVENTORY_FAILED")
    entries = [entry for entry in process.stdout.split(b"\0") if entry]
    rows: list[dict[str, Any]] = []
    summary: dict[tuple[str,str], dict[str, Any]] = {}
    for raw in entries:
        text = raw.decode("utf-8", errors="surrogateescape")
        status = text[:2]
        path = text[3:].replace("\\", "/")
        category, action, reason = classify_dirty_path(path, status)
        absolute = repo / path
        size: int | str = "DIRECTORY_OR_UNREADABLE"
        digest = "NOT_COMPUTED_FULL_INVENTORY"
        if absolute.is_file():
            try:
                size = absolute.stat().st_size
                if action in {"DELETE_SAFE", "REVIEW_BEFORE_DELETE"} and int(size) <= 20 * 1024 * 1024:
                    digest = sha256_file(absolute)
            except OSError:
                size = "UNREADABLE"
        rows.append({"git_status":status,"path":path,"size_bytes":size,"sha256":digest,"category":category,"recommended_action":action,"reason":reason})
        key=(category,action)
        aggregate=summary.setdefault(key,{"category":category,"recommended_action":action,"item_count":0,"known_size_bytes":0})
        aggregate["item_count"] += 1
        if isinstance(size,int):
            aggregate["known_size_bytes"] += size
    summary_rows=sorted(summary.values(),key=lambda row:(row["recommended_action"],row["category"]))
    return rows, summary_rows


def reports(
    ledger: Mapping[str, Any], git: Mapping[str, Any]
) -> tuple[str, str, str, str, str, str]:
    metrics=ledger["metrics"]
    authority_report=f"""# Authority Resolution Report

## 裁决

PB-G0 定位/哈希层为 `VERIFIED`，权威充分性层为 `HOLD`。因此聚合裁决是
`PB_G0_HOLD_PARTIAL_AUTHORITY`，允许的最大工作范围仅为隔离的参数映射和
PB-00 非信用诊断。

## 已绑定

- Accepted B601 URDF 原始字节哈希已锁定，4.695555949342986 kg，禁止修改。
- Unified R2 source-only URDF 已锁定，19 link / 18 joint / 8 movable DOF，
  总质量 31.022864807342987 kg；Route-C 明确未包含。
- 物理安装与动力学参考之间只能使用唯一 bridge：绕 A0-z
  +25.000014 deg、沿 A0-z +0.02275 m。

## 未闭合

- 系统与目标正式质量惯量 authority；
- frame owner confirmation；
- 0.005 m/s 与 0.05 m/s 的接触速度冲突；
- 关节、基座、夹爪硬件执行器动力学；
- 当前脏仓关键资产的版本控制留存信用。

任何 UNKNOWN 不得自动转为 ALLOW，任何 null 不得补零。
"""
    current=f"""# Current State

`{PHASE_ID}` 已建立隔离预绑定胶囊。PB-00 Unified R2 零广义力诊断数值检查通过，
但由于 PB-G0-A 未通过，PB-G1 仍为 `HOLD`，不产生正式控制或机械发布信用。

关键诊断量：

- 初始动能：{metrics['initial_kinetic_energy_J']:.17g} J
- 最大相对能量漂移：{metrics['relative_energy_drift_max']:.6e}
- 最大线动量残差：{metrics['linear_momentum_residual_max_Ns']:.6e} N*s
- 最大角动量残差：{metrics['angular_momentum_residual_max_Nms']:.6e} N*m*s
- 仓库 HEAD：`{git['head']}`；dirty=`{str(git['dirty']).lower()}`，无留存信用。

下一合法动作是关闭 PB-G0 权威缺口并由 owner 重判；不是 NMPC/RL/VLA。
"""
    delta=f"""# Current State Delta

相对本轮前状态，本轮只增加：

1. Accepted B601 / Unified R2 / mass / frame / Gate 的单一预绑定视图与哈希账本；
2. 明确的 frame、state handoff、solver、FSM 与 SAFE-00 接口合同；
3. 一次零控制、无接触、无目标、无柔性的 PB-00 数值 characterization；
4. 主仓脏项分类清单与第一批纯测试缓存清理回执。

未改变：Mechanical Gate A=false、Route-C FAIL_DOCUMENTED、E23 provisional、
CTRL-01 REPEAT、CTRL-02 limited、SAFE-00 next_stage_authorized=false、
Sim13 maximum ABORT_ONLY。没有任何历史负结果被覆盖。
"""
    acceptance=f"""# Prebind Phase-0 Acceptance Report

## 总裁决

```text
PB-G0 = HOLD_PARTIAL_AUTHORITY
PB-00 = PASS_DIAGNOSTIC_NO_CREDIT
PB-G1 = HOLD_NOT_AUTHORIZED_BY_PB-G0
NEXT_STAGE_AUTHORIZED = false
FORMAL_PERFORMANCE_CREDIT = false
```

PB-00 的能量、线/角动量、粗细步对拍和确定性回放均满足预绑定数值阈值，
但这只是 source-only Unified R2 刚体后端的数值 characterization。它不包含
Route-C、柔性、接触、目标、执行器或估计器，不得用于宣称捕获闭环或控制发布。

## Owner 需批准/补齐

- system/target mass-inertia authority；
- physical-dynamics bridge owner confirmation；
- gripper/contact speed 冲突裁决；
- hardware actuator dynamics；
- 关键未跟踪机械资产的冻结/留存策略。
"""
    control="""# Control Architecture (Prebind Only)

数据流冻结为：RPO/导航状态 -> state handoff schema -> plant/frame/hash validator ->
SAFE-00 fail-closed decision -> future control allocator -> independent physics veto ->
backend adapter。当前只实现 validator 合同与零广义力 PB-00；future control allocator
保持 `HOLD`。

控制相位与机械拓扑分离：`PREGRASP` 不是 `COMPLIANT_CAPTURE`，后者也不是
`LOCKED_COMPOSITE`。任何 hash drift、单位/坐标歧义、UNKNOWN 或 authority 缺失均
直接进入 WAIT/BACKOFF/ABORT，不执行控制性能评分。
"""
    safe="""# SAFE-00 Prebind Interface

沿用现行双层语义：物理分类只能为 `SAFE/UNSAFE/UNKNOWN`，决策只能为
`ALLOW/MODIFY/WAIT/BACKOFF/ABORT`。本阶段禁止将其改名后混成一个枚举。

- `UNKNOWN -> ALLOW` 永远非法；
- 请求和响应都必须带 schema/plant/frame hash；
- Route-C、接触、目标或执行器 authority 缺失时最宽只能 WAIT/BACKOFF/ABORT；
- SAFE-00 现有 PASS 仍是 `PENDING_REVIEW` 且 `next_stage_authorized=false`，
  本接口不继承执行授权。
"""
    return authority_report,current,delta,acceptance,control,safe


def build_run_manifest(module: Path, seed: int, inputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    output_rows=[]
    for path in sorted(module.rglob("*")):
        if not path.is_file() or path.name == "PB00_RUN_MANIFEST.json" or "__pycache__" in path.parts:
            continue
        output_rows.append({"path":path.relative_to(module).as_posix(),"bytes":path.stat().st_size,"sha256":sha256_file(path),"hash_mode":"RAW_BYTES_SHA256"})
    return {"schema":"PREBIND_PHASE0_RUN_MANIFEST_V1","phase":PHASE_ID,"generated_date_local":GENERATED_DATE_LOCAL,"seed":seed,"python":sys.version.split()[0],"numpy":np.__version__,"inputs":[dict(row) for row in inputs],"outputs":output_rows,"determinism_policy":"No wall-clock values in scientific outputs; raw-byte input and output hashes recorded.","next_stage_authorized":False,"release_credit":False}


def execute(repo: Path, seed: int) -> None:
    module=repo/MODULE_REL
    if module.resolve() == repo.resolve() or repo.resolve() not in module.resolve().parents:
        raise RuntimeError("OUTPUT_ROOT_OUTSIDE_PROJECT")
    hash_rows, assets=build_hash_manifest(repo)
    git=git_snapshot(repo)
    write_csv(module/"00_authority/BASELINE_HASH_MANIFEST.csv",["asset_id","path","bytes","sha256","hash_mode","role","authority_status","consumed_by_pb00","expected_hash_match"],hash_rows)
    write_json(module/"00_authority/CURRENT_GATE_SNAPSHOT.json",build_gate_snapshot(repo,assets))
    write_json(module/"00_authority/PREBIND_AUTHORITY.json",build_prebind_authority(assets,git))
    write_csv(module/"00_authority/CONFLICT_LEDGER.csv",["id","domain","severity","conflict","selected_prebind_disposition","state"],conflict_rows())
    write_csv(module/"00_authority/NEGATIVE_RESULT_REGISTER.csv",["id","source","negative_result","preservation","effect"],negative_result_rows())
    accepted,sensitivity,unified=build_plants(assets)
    write_yaml(module/"01_plant/ACCEPTED_PLANT.yaml",accepted)
    write_yaml(module/"01_plant/PREBIND_SENSITIVITY_PLANT.yaml",sensitivity)
    write_yaml(module/"01_plant/UNIFIED_R2_PLANT.yaml",unified)
    write_csv(module/"01_plant/PARAMETER_PROVENANCE.csv",["parameter_id","value","unit","frame","reference_point","uncertainty","authority","status","source_artifact","source_field","pb00_consumed"],parameter_rows(assets))
    write_yaml(module/"02_interfaces/FRAME_CONTRACT.yaml",build_frame_contract(assets))
    write_json(module/"02_interfaces/STATE_HANDOFF_SCHEMA.json",build_state_schema())
    write_yaml(module/"02_interfaces/SOLVER_MAPPING.yaml",build_solver_mapping(assets))
    write_csv(module/"03_scenarios/SCENARIO_MATRIX.csv",["scenario_id","name","plant","target","contact","flex","control","phase0_action","gate_credit","state"],scenario_rows())
    write_yaml(module/"03_scenarios/CAPTURE_FSM.yaml",build_capture_fsm())
    write_csv(module/"03_scenarios/NEGATIVE_CASE_REGISTER.csv",["case_id","stimulus","expected","phase0"],negative_case_rows())
    authority_report,current,delta,acceptance,control,safe=reports({"metrics":{"initial_kinetic_energy_J":0.0,"relative_energy_drift_max":0.0,"linear_momentum_residual_max_Ns":0.0,"angular_momentum_residual_max_Nms":0.0}},git)
    write_text(module/"00_authority/AUTHORITY_RESOLUTION_REPORT.md",authority_report)
    write_text(module/"05_control/CONTROL_ARCHITECTURE.md",control)
    write_text(module/"05_control/SAFE_00_INTERFACE.md",safe)
    ledger,timeseries=run_pb00(repo,seed,assets)
    write_json(module/"10_verification/MOMENTUM_LEDGER.json",ledger)
    write_json(module/"10_verification/PB00_TIMESERIES.json",timeseries)
    g0,pb00_gate,g1=build_gates(assets,ledger)
    write_json(module/"10_verification/PB_G0_GATE.json",g0)
    write_json(module/"10_verification/PB00_CHARACTERIZATION_GATE.json",pb00_gate)
    write_json(module/"10_verification/PB_G1_GATE.json",g1)
    authority_report,current,delta,acceptance,control,safe=reports(ledger,git)
    write_text(module/"00_authority/AUTHORITY_RESOLUTION_REPORT.md",authority_report)
    write_text(module/"05_control/CONTROL_ARCHITECTURE.md",control)
    write_text(module/"05_control/SAFE_00_INTERFACE.md",safe)
    write_text(module/"13_reports/CURRENT_STATE.md",current)
    write_text(module/"13_reports/CURRENT_STATE_DELTA.md",delta)
    write_text(module/"13_reports/PREBIND_PHASE0_ACCEPTANCE_REPORT.md",acceptance)
    inventory,inventory_summary=build_dirty_inventory(repo,module)
    write_csv(module/"00_authority/WORKTREE_DIRTY_ITEM_INVENTORY.csv",["git_status","path","size_bytes","sha256","category","recommended_action","reason"],inventory)
    write_csv(module/"00_authority/WORKTREE_DIRTY_TRIAGE_SUMMARY.csv",["category","recommended_action","item_count","known_size_bytes"],inventory_summary)
    cleanup_summary = {row["category"]: row for row in inventory_summary}
    candidate = cleanup_summary.get("MECHANICAL_MIDDLEWARE_CANDIDATE", {})
    write_text(
        module / "00_authority/WORKTREE_CLEANUP_DECISION.md",
        f"""# Worktree Cleanup Decision

本轮只删除了可以证明可再生成或有逐字节规范副本的内容，共 164 个文件、
约 1,590,285 字节。Mechanical R2、Accepted B601、E23、Sim13、Route-C
物理设计与历史负结果均未删除。

当前机械中间产物候选为 {candidate.get('item_count', 'UNKNOWN')} 项，已知大小
{candidate.get('known_size_bytes', 'UNKNOWN')} 字节。其中约 2.65 GB 位于旧 V5
`13_validation/quarantine/`；这些目录包含失败样本和负结果原件，不能仅因名称为
quarantine 就删除。应先建立可恢复归档、验证 manifest 覆盖和独立恢复测试，再由
owner 单独批准第三批清理。

仍留在根目录但与 V5NATIVE `99_tools` 不同哈希的历史脚本也保持 HOLD；不同哈希
意味着它们不是可证明的重复副本。Route-C 正在运行的脚本、日志、备份和输出保持
机械线独占，只读不清理。
""",
    )
    write_json(module/"00_authority/DELETION_BATCH_01_RECEIPT.json",{
        "schema":"WORKTREE_DELETION_RECEIPT_V1",
        "executed_date_local":GENERATED_DATE_LOCAL,
        "batches":[
            {
                "batch_id":"BATCH_01_REGENERABLE_TEST_CACHE",
                "targets":[
                    {"path":".pytest-tmp/","files":7,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":".pytest_tmp_artifact_derivation_20260824/","files":30,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":".pytest_tmp_artifact_derivation_20260824_b/","files":30,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":".pytest_tmp_artifact_derivation_20260824_c/","files":31,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":".pytest_tmp_artifact_derivation_20260824_d/","files":31,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":".pytest_tmp_artifact_integration_20260824/","files":31,"recoverability":"REGENERABLE_BY_TESTS"},
                    {"path":"grep.exe.stackdump","files":1,"recoverability":"NOT_NEEDED_CRASH_DUMP"},
                ],
                "files":161,
                "approximate_bytes":1449506,
            },
            {
                "batch_id":"BATCH_02_BYTE_IDENTICAL_ROOT_DUPLICATES",
                "targets":[
                    {"path":"F3R2_V5_AUTHORITY_SEED_MATERIALIZER.py","files":1,"sha256":"B62F341A43442BCCE80221AF29663E2EECF9E723DEE8CB08A1BCC224B07D8C2F","canonical_copy":"20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/99_tools/F3R2_V5_AUTHORITY_SEED_MATERIALIZER.py"},
                    {"path":"F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py","files":1,"sha256":"25369CB867685EBA0C374636F8F540867D3D8B5890F9CE8622A6842E6518EC42","canonical_copy":"20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/99_tools/F3R2_V5_NATIVE_LOOP1A_SUBASSEMBLIES_ATTACH_ONLY.py"},
                    {"path":"F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py","files":1,"sha256":"E44BC52CFBDECCC107E361ACB0EDD993EFC46248EB663A994564B77BDA30F906","canonical_copy":"20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/99_tools/F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY.py"},
                ],
                "files":3,
                "bytes":140779,
                "byte_identical_canonical_copy_verified_before_delete":True,
            },
        ],
        "total_files":164,
        "approximate_bytes":1590285,
        "mechanical_assets_touched":False,
        "unique_negative_evidence_deleted":False,
        "method":"git clean -fd -- exact validated targets",
    })
    write_json(module/"10_verification/PB00_RUN_MANIFEST.json",build_run_manifest(module,seed,hash_rows))


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root",type=Path,default=None,help="Project root; auto-discovered when omitted")
    parser.add_argument("--seed",type=int,default=DEFAULT_SEED)
    return parser.parse_args()


def main() -> int:
    args=parse_args()
    repo=find_repo_root(args.repo_root if args.repo_root is not None else Path(__file__).resolve())
    execute(repo,args.seed)
    print(f"{PHASE_ID}: outputs written under {MODULE_REL.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
