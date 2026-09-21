from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest


SIM13_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SIM13_ROOT.parents[1]
ACCEPTED_URDF_RELATIVE = Path(
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
)
VISUAL_MESH_RELATIVE = Path(
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/"
    "meshes_b601_gripper/base_link.STL"
)
COLLISION_MESH_RELATIVE = Path(
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/"
    "meshes_b601_gripper/gripper_link.STL"
)
FRAME_TREE_RELATIVE = Path(
    "30_simulation/sim_13_physics_gated_embodied_grasping/"
    "assets/BOOTSTRAP_TEST_FRAME_TREE.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def mechanical_interface_factory(
    tmp_path: Path,
) -> Callable[..., Path]:
    """Build a hash-bound, test-scope manifest around repository assets.

    This deliberately does not claim to be the production whole-system
    mechanical package.  It is sufficient to prove strict loading, accepted
    URDF topology/mass authority, deterministic anchors, and fail-closed masks.
    """

    def factory(
        *,
        artifact_hash_overrides: dict[str, str] | None = None,
        manifest_overrides: dict[str, Any] | None = None,
        directory_name: str = "interface",
    ) -> Path:
        manifest_directory = tmp_path / directory_name
        manifest_directory.mkdir(parents=True, exist_ok=True)
        paths = {
            "accepted_urdf": ACCEPTED_URDF_RELATIVE,
            "visual_mesh": VISUAL_MESH_RELATIVE,
            "collision_mesh": COLLISION_MESH_RELATIVE,
            "frame_tree": FRAME_TREE_RELATIVE,
        }
        hashes = {
            name: _sha256(PROJECT_ROOT / relative)
            for name, relative in paths.items()
        }
        hashes.update(artifact_hash_overrides or {})
        asset_root = os.path.relpath(PROJECT_ROOT, manifest_directory).replace(
            os.sep, "/"
        )
        document: dict[str, Any] = {
            "schema_version": "MECH_RL_INTERFACE_V1",
            "scope": "SIM13_TEST_FIXTURE_B601_ONLY_NOT_PRODUCTION_PACKAGE",
            "gate_eligible": False,
            "asset_root": asset_root,
            "artifacts": {
                name: {
                    "path": relative.as_posix(),
                    "sha256": hashes[name],
                }
                for name, relative in paths.items()
            },
            "accepted_configurations": [
                "DEPLOYED_NOMINAL",
                "LEFT_PANEL_FAIL",
                "RIGHT_PANEL_FAIL",
                "BOTH_PANEL_FAIL",
                "ARM_STOWED_ONORBIT",
                "ARM_TASK_READY",
                "GRIPPER_CLOSED",
                "GRIPPER_PARTIAL",
                "GRIPPER_PREGRASP",
                "GRIPPER_OPEN",
            ],
            "gripper_contact_frames": [
                {
                    "id": "GC_PRIMARY",
                    "frame_id": "GRIPPER_CONTACT_PRIMARY",
                    "surface_normal": [0.0, 0.0, 1.0],
                }
            ],
            "capture_timing_ids": ["T_EARLY", "T_NOMINAL", "T_LATE"],
            "m3r_mount_transform": {
                "parent_frame": "SERVICE_SPACECRAFT",
                "child_frame": "M3R_STAGE_A_RING",
                "translation_m": [0.0, 0.0, 0.0],
                "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
                "status": "TEST_IDENTITY_ONLY_NOT_PRODUCTION_T_SM",
            },
            "camera_reserve_frames": ["CAMERA_RESERVE_PRIMARY"],
            "keep_out": [
                {"id": "CAMERA_KEEP_OUT", "frame_id": "CAMERA_KEEP_OUT"},
                {"id": "CABLE_KEEP_OUT", "frame_id": "CABLE_KEEP_OUT"},
            ],
            "mass_and_inertia": {
                "authority": "accepted_urdf",
                "b601_total_mass_kg": 4.695555949,
                "mesh_mass_inference_forbidden": True,
            },
        }
        if manifest_overrides:
            document.update(manifest_overrides)
        manifest = manifest_directory / "MECH_RL_INTERFACE_V1.yaml"
        manifest.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return manifest

    return factory


@pytest.fixture
def mechanical_interface_path(mechanical_interface_factory: Callable[..., Path]) -> Path:
    production_path = os.environ.get("SIM13_PRODUCTION_INTERFACE")
    if production_path:
        path = Path(production_path).resolve()
        if not path.is_file():
            pytest.fail(
                "SIM13_PRODUCTION_INTERFACE does not name an existing file: "
                f"{path}"
            )
        return path
    return mechanical_interface_factory()
