#!/usr/bin/env python3
"""Additive G33A mesh-binding repair using the fail-closed path resolver.

The historical G33 evidence and M2-migrated files remain immutable.  This
wrapper reuses the reviewed containment computation from r3f, redirects every
write to new M3R addendum files, and resolves every mesh through
``f3r2_path_resolver`` before trimesh opens it.

Passing this addendum proves only offline mesh grouping and three-state
clearance.  It does not create separate native finger parts, mates,
configurations, motion results, or a SolidWorks manufacturing baseline.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import trimesh

from f3r2_path_resolver import resolve_asset


TOOLS = Path(__file__).resolve().parent
F3R2 = TOOLS.parent
SOURCE_BINDING = (
    F3R2 / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING.json"
)
ADDENDUM = (
    F3R2 / "08_camera_harness/F3R2_GRIPPER_FINGER_BINDING_ADDENDUM_M3R_V2.json"
)
ADDENDUM_STATES = (
    F3R2 / "08_camera_harness/F3R2_GRIPPER_STATE_REGISTER_ADDENDUM_M3R_V2.csv"
)
LEGACY_SCRIPT = TOOLS / "r3f_g33_gripper_close.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_legacy_module():
    spec = importlib.util.spec_from_file_location("m3r_r3f_reviewed", LEGACY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load reviewed G33A computation")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    if ADDENDUM.exists() or ADDENDUM_STATES.exists():
        raise RuntimeError("refusing to overwrite an existing M3R G33A addendum")

    source_sha = sha256(SOURCE_BINDING)
    legacy_sha = sha256(LEGACY_SCRIPT)
    seed = json.loads(SOURCE_BINDING.read_text(encoding="utf-8"))
    seed["m3r_addendum"] = {
        "historical_source_path": str(SOURCE_BINDING).replace("\\", "/"),
        "historical_source_sha256": source_sha,
        "reviewed_computation_script": str(LEGACY_SCRIPT).replace("\\", "/"),
        "reviewed_computation_script_sha256": legacy_sha,
        "historical_evidence_modified": False,
        "top_level_error_and_traceback_scope": (
            "HISTORICAL_SOURCE_FAILURE_RETAINED_FOR_FORENSICS_"
            "NOT_CURRENT_ADDENDUM_ERROR"
        ),
    }
    ADDENDUM.write_text(
        json.dumps(seed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    module = load_legacy_module()
    module.BIND = ADDENDUM
    module.OUTS = ADDENDUM_STATES

    mesh_cache = {}
    resolutions = {}

    def resolve_one(stored_path):
        key = str(stored_path)
        if key not in resolutions:
            resolved = resolve_asset(key)
            resolutions[key] = {
                "stored_path": key.replace("\\", "/"),
                "resolved_path": resolved.resolved_path.replace("\\", "/"),
                "sha256": resolved.sha256,
                "resolution_method": resolved.resolution_method,
            }
        return resolutions[key]

    def resolved_mesh(stored_path):
        key = str(stored_path)
        if key not in mesh_cache:
            resolved = resolve_one(key)
            mesh_cache[key] = trimesh.load_mesh(
                resolved["resolved_path"], process=False
            )
        return mesh_cache[key]

    module.mesh = resolved_mesh
    solid_manifest = json.loads(module.SOLIDS.read_text(encoding="utf-8"))["solids"]
    for solid in solid_manifest.values():
        resolve_one(solid["path"])
    exit_code = 1
    try:
        module.main()
    except SystemExit as exc:
        exit_code = int(exc.code or 0)

    result = json.loads(ADDENDUM.read_text(encoding="utf-8"))
    computation_verdict = result.get("verdict")
    result["m3r_addendum"].update(
        {
            "resolver": "99_tools/f3r2_path_resolver.py",
            "resolved_mesh_count": len(resolutions),
            "mesh_files_loaded_for_finger_interpenetration": len(mesh_cache),
            "all_meshes_resolved": bool(resolutions) and len(resolutions) == 58,
            "resolution_records": list(resolutions.values()),
            "upstream_computation_verdict": computation_verdict,
            "native_component_gate": False,
            "limitations": [
                "offline STL grouping is not separate SLDPRT finger hardware",
                "no prismatic mates or native OPEN/PREGRASP/CLOSED configurations",
                "no SolidWorks native motion or interference result",
                "formal grip force remains not evaluated"
            ],
        }
    )
    passed = (
        exit_code == 0
        and computation_verdict == "G33A_GRIPPER_FINGERS_BOUND"
        and result["m3r_addendum"]["all_meshes_resolved"]
    )
    result["verdict"] = (
        "G33A_OFFLINE_MESH_BINDING_ADDENDUM_PASS"
        if passed
        else "G33A_OFFLINE_MESH_BINDING_ADDENDUM_FAIL"
    )
    result["native_gate_verdict"] = "G33A_NATIVE_COMPONENT_CONFIGURATION_HOLD"
    ADDENDUM.write_text(
        json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "verdict": result["verdict"],
        "native_gate_verdict": result["native_gate_verdict"],
        "resolved_mesh_count": len(resolutions),
        "historical_source_sha256": source_sha,
    }, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
