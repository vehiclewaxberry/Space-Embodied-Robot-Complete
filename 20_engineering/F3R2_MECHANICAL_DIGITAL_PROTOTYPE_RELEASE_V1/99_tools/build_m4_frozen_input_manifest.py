"""Build the immutable-input manifest for the M4 digital-prototype loop.

The script intentionally hashes source artifacts in streaming mode.  It does
not modify any predecessor baseline and does not load CAD documents.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[3]
M4 = Path(__file__).resolve().parents[1]
OUTPUT = M4 / "00_authority" / "M4_FROZEN_INPUT_MANIFEST_V1.json"

INPUTS = [
    "20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1",
    "30_simulation/sim_13_physics_gated_embodied_grasping",
    "30_simulation/sim_05_free_floating_arm/b601_model.py",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/MECH_RL_INTERFACE_V1.yaml",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/SYSTEM_FRAME_TREE.yaml",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/02_interfaces/CONFIGURATION_MATRIX.csv",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.stl",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/SEI_MECH_B601_V5R_NEUTRAL_OPERATIONAL_BASELINE.step",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/01_native_cad/SEI_MECH_B601_V5R_COLLISION_MESH.stl",
    "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/hdrm/V4_ARM_HDRM_60MM_FLANGE_SKELETON.step",
    "20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/02_neutral_cad/hdrm/V4_ARM_HDRM_RELEASE_SWEEP_KEEP_OUT.step",
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
    "20_engineering/cad/freecad_authoritative/B601_KINEMATIC_ASSEMBLY_Q0_WITNESS.step",
    "20_engineering/cad/spacecraft_layout/servicer_12U_v0/servicer_12U_v0.step",
    "20_engineering/cad/spacecraft_layout/servicer_12U_v0/servicer_12U_v0.json",
    "20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.step",
    "20_engineering/cad/spacecraft_layout/target_satellite_v0/target_satellite_v0.json",
    "20_engineering/cad/spacecraft_layout/target_debris_v0/target_debris_v0.step",
    "20_engineering/cad/spacecraft_layout/target_debris_v0/target_debris_v0.json",
    "20_engineering/cad/spacecraft_layout/model_specs_v0.json",
    "20_engineering/config/geometry/frame_tree_v1.yaml",
    "20_engineering/config/geometry/service_spacecraft_v1.yaml",
    "20_engineering/config/geometry/flexible_appendage_v1.yaml",
    "20_engineering/config/visualization/scene_manifest_v1.yaml",
    "20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv",
    "20_engineering/design_inputs/v2_system_mechanical/05_mass_budget/V2_mass_ownership_table.csv",
    "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/B601_EQUIVALENT_INERTIA_RECOMPUTED.yaml",
    "20_engineering/F3R2_MECHANICAL_CDR_QUALIFICATION_CLOSURE_20260821/03_wp2_mass_interface/M3R_MASS_RULING.json",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_INITIAL_POSE.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/F3R2_ARM_POSE_REGISTER.csv",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_TSM_PHYSICAL_FRAME_DIAGRAM.md",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_PHYSICAL_STACK.yaml",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_TSM_FRAME_TO_FLANGE_TRANSFORM.json",
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/M3R_ADAPTER_INTERFACE_SSOT.yaml",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json",
    "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/06_pack_and_go/V5R_NEUTRAL_OPERATIONAL_PACKAGE/addenda/v4_delta/hdrm/V4_ARM_HDRM_60MM_FLANGE_SKELETON.step",
    "20_engineering/cad/Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/design/b601_stow_joint_vector_v3.json",
    "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/110_Layout_and_Deployment_01/solar/solar_deployment_contract.json",
    "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/110_Layout_and_Deployment_01/solar/solar_deployment_pose_000deg.step",
    "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/110_Layout_and_Deployment_01/solar/solar_deployment_pose_090deg.step",
]

EXTERNAL_INPUTS = [
    Path(r"C:\Users\stude\.codex\attachments\3f8a1338-bb5c-4b2b-bd2a-bb1e10a8df7f\pasted-text-1.txt"),
    Path(r"C:\Users\stude\.codex\attachments\787a450f-adfb-47ad-9d57-3e8faf59455a\pasted-text.txt"),
    Path(r"C:\Users\stude\.codex\attachments\038d9781-5921-4858-9fea-c070890a71b8\pasted-text.txt"),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def record(path: Path, display_path: str, source_group: str) -> dict[str, object]:
    stat = path.stat()
    return {
        "path": display_path.replace("\\", "/"),
        "source_group": source_group,
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
    }


def main() -> int:
    records: list[dict[str, object]] = []
    missing: list[str] = []
    for relative in INPUTS:
        source = WORKSPACE / relative
        if not source.exists():
            missing.append(relative)
            continue
        if source.is_dir():
            for path in sorted(item for item in source.rglob("*") if item.is_file()):
                if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".fcbak"}:
                    continue
                display = path.relative_to(WORKSPACE).as_posix()
                records.append(record(path, display, relative))
        else:
            records.append(record(source, relative, relative))
    for source in EXTERNAL_INPUTS:
        display = source.as_posix()
        if not source.is_file():
            missing.append(display)
            continue
        records.append(record(source, display, "owner_evidence"))

    unique: dict[str, dict[str, object]] = {}
    duplicate_paths: list[str] = []
    for item in records:
        key = str(item["path"])
        if key in unique:
            duplicate_paths.append(key)
        unique[key] = item

    manifest = {
        "schema": "M4_FROZEN_INPUT_MANIFEST_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "workspace": str(WORKSPACE).replace("\\", "/"),
        "hash_algorithm": "SHA-256",
        "file_count": len(unique),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in unique.values()),
        "missing_count": len(missing),
        "missing": missing,
        "duplicate_path_count": len(duplicate_paths),
        "duplicate_paths": duplicate_paths,
        "source_mutation_allowed": False,
        "status": "PASS" if not missing and not duplicate_paths else "HOLD",
        "files": [unique[key] for key in sorted(unique)],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in (
        "file_count", "total_size_bytes", "missing_count", "duplicate_path_count", "status"
    )}, indent=2))
    return 0 if manifest["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
