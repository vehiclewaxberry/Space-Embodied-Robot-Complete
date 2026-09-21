"""Finalize the evidence-gated B5.0 fixed-q0 native CAD milestone.

This verifier is intentionally narrower than the full B5.0 program.  It
accepts only the fixed-q0 native reference baseline and records every later
mechanical, integration, simulation, and retained-DOF claim as partial or HOLD.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil
import trimesh
from PIL import Image


CANDIDATE = Path(__file__).resolve().parents[1]
RUN_ID = "B50_NATIVE_20260727T2214Z"
RUN = CANDIDATE / "03_CAD/native_runs" / RUN_ID
EVIDENCE = RUN / "evidence"
REVIEWS = RUN / "reviews"
EXPORTS = RUN / "30_exports"
VERIFY = CANDIDATE / "07_VERIFICATION"

EXPECTED_URDF_SHA256 = (
    "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
)
EXPECTED_STEP_SHA256 = (
    "70B3F05A674CB38D39E5DE3B51817DFF5BDE0D9A79639331009670E63AACCFA0"
)
EXPECTED_ASSEMBLY_SHA256 = (
    "7622969F4D8F49B295A82D28E720EF62DAEEA78A96B5D2BAB55AF67FC7955B99"
)
EXPECTED_DRAWING_SHA256 = (
    "5AC5A232ED483B957DAEC478A4D34142877AC3BD89EF9D007DA6395ABF825A4C"
)


def fail(message: str) -> None:
    raise SystemExit(f"B5.0 finalization HOLD: {message}")


def require(condition: object, message: str) -> None:
    if not condition:
        fail(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    return path.relative_to(CANDIDATE).as_posix()


def artifact(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing artifact: {path}")
    require(path.stat().st_size > 0, f"empty artifact: {path}")
    return {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def receipt_run_artifact(value: dict[str, object]) -> dict[str, object]:
    """Normalize a run-relative build receipt artifact to candidate-relative."""
    normalized = dict(value)
    receipt_path = Path(str(normalized.get("path") or ""))
    require(not receipt_path.is_absolute(), "receipt artifact unexpectedly uses an absolute path")
    normalized["path"] = rel(RUN / receipt_path)
    return normalized


def read_json(path: Path) -> dict[str, object]:
    require(path.is_file(), f"missing JSON receipt: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - fail-closed evidence path
        fail(f"cannot parse {path}: {exc}")
    require(isinstance(value, dict), f"JSON receipt is not an object: {path}")
    return value


def write_new_json(path: Path, payload: dict[str, object]) -> None:
    require(not path.exists(), f"overwrite forbidden: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    require(not temporary.exists(), f"temporary path already exists: {temporary}")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def mesh_facts(path: Path) -> dict[str, object]:
    scene = trimesh.load(path, force="scene", process=False)
    geometries = list(scene.geometry.values())
    require(geometries, f"mesh has no geometry: {path}")
    bounds = np.asarray(scene.bounds, dtype=float)
    require(bounds.shape == (2, 3), f"mesh bounds invalid: {path}")
    return {
        **artifact(path),
        "loader": f"trimesh_{trimesh.__version__}",
        "geometry_count": len(geometries),
        "vertices": int(sum(len(item.vertices) for item in geometries)),
        "faces": int(sum(len(item.faces) for item in geometries)),
        "bounds": bounds.tolist(),
    }


def foreground_ratio(path: Path) -> float:
    image = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    require(image.ndim == 3 and image.shape[2] == 3, f"invalid image: {path}")
    edge = 8
    left = image[:, :edge, :].mean(axis=1, keepdims=True)
    right = image[:, -edge:, :].mean(axis=1, keepdims=True)
    background = 0.5 * (left + right)
    foreground = np.abs(image - background).sum(axis=2) > 24.0
    return float(foreground.mean())


def assert_artifact_hash(path: Path, expected: str, label: str) -> None:
    actual = sha256(path)
    require(actual == expected, f"{label} hash mismatch: {actual} != {expected}")


def main() -> int:
    generated_utc = datetime.now(timezone.utc).isoformat()
    sidecar_path = EVIDENCE / "step_sidecar_generation.json"
    visual_path = EVIDENCE / "visual_review_adjudication.json"
    gate_path = VERIFY / "GATE_STATUS.json"
    for output in (sidecar_path, visual_path, gate_path):
        require(not output.exists(), f"output already exists: {output}")

    cold = read_json(EVIDENCE / "native_q0_cold_verify.json")
    build = read_json(EVIDENCE / "q0_assembly_build_attempt3.json")
    protected = read_json(VERIFY / "protected_hash_verification.json")
    cad_cli = read_json(EVIDENCE / "cad_cli_inspect_refs.json")
    attempt1 = read_json(EVIDENCE / "visual_review_vtk.json")
    attempt2 = read_json(EVIDENCE / "visual_review_vtk_attempt2.json")

    require(
        cold.get("status")
        == "B5_0_NATIVE_Q0_COLD_VERIFY_PASS_WITH_G05_G08_HOLD",
        "cold verifier status is not accepted",
    )
    require(cold.get("build_attempt_id") == "attempt3", "cold verifier not bound to attempt3")
    require(
        cold.get("mass_authority") == "EXCLUDED_ACCEPTED_URDF_ONLY",
        "CAD mass authority was elevated",
    )
    require(
        cold.get("mechanism_dof_authority") == "NONE_FIXED_Q0_REFERENCE",
        "fixed-q0 mechanism authority changed",
    )
    source_contract = cold["checks"]["source_contract"]
    require(
        source_contract["accepted_urdf"]["sha256"] == EXPECTED_URDF_SHA256,
        "accepted URDF hash does not match the frozen value",
    )
    require(
        source_contract["accepted_mass_source_decimal_kg"] == "4.6955559493429862",
        "accepted mass source decimal changed",
    )
    require(source_contract["hold_groups"] == ["G05", "G08"], "G05/G08 HOLD not preserved")
    require(
        source_contract["b106"] == "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
        "B106 bounded-search status changed",
    )
    require(build.get("status") == "B5_0_NATIVE_BUILD_PASS", "attempt3 build is not PASS")
    require(build.get("attempt_id") == "attempt3", "wrong assembly build attempt")
    require(
        build["result"]["verdict"] == "B5_0_NATIVE_Q0_ASSEMBLY_BUILD_PASS",
        "assembly result is not PASS",
    )
    require(build["result"]["component_count"] == 9, "assembly component count is not 9")
    require(
        build["result"]["fixed_geometry_component_count"] == 9,
        "not all q0 components are fixed",
    )
    require(
        build["result"]["retained_mechanism_dof_claimed"] is False,
        "build incorrectly claims retained mechanism DOF",
    )
    require(
        protected.get("verdict") == "B5_0_PROTECTED_BASELINE_HASH_PASS"
        and protected.get("checked") == 79
        and protected.get("passed") == 79
        and protected.get("failed") == 0,
        "protected baseline is not 79/79 PASS",
    )
    require(
        cad_cli.get("verdict") == "B5_0_CAD_CLI_INSPECT_REFS_PASS"
        and cad_cli.get("ok") is True
        and cad_cli.get("exit_code") == 0
        and cad_cli["summary"]["occurrence_count"] == 9
        and cad_cli["summary"]["leaf_occurrence_count"] == 8
        and cad_cli["summary"]["shape_count"] == 388
        and cad_cli["summary"]["face_count"] == 24667
        and cad_cli["summary"]["edge_count"] == 64405
        and not cad_cli.get("errors")
        and not cad_cli.get("warnings"),
        "CAD CLI inspect receipt is incomplete or failed",
    )

    assembly = RUN / "20_assembly/B50_B601_ENGINEERING_ARM_Q0.SLDASM"
    drawing = RUN / "40_drawings/B50_B601_ENGINEERING_ARM_Q0.SLDDRW"
    step = EXPORTS / "B50_B601_ENGINEERING_ARM_Q0.step"
    assert_artifact_hash(assembly, EXPECTED_ASSEMBLY_SHA256, "assembly")
    assert_artifact_hash(drawing, EXPECTED_DRAWING_SHA256, "drawing")
    assert_artifact_hash(step, EXPECTED_STEP_SHA256, "STEP")

    stl = EXPORTS / "B50_B601_ENGINEERING_ARM_Q0.stl"
    glb = EXPORTS / "B50_B601_ENGINEERING_ARM_Q0.glb"
    topology_glb = EXPORTS / ".B50_B601_ENGINEERING_ARM_Q0.step.glb"
    sidecar = {
        "schema": "SER_B50_STEP_SIDECAR_GENERATION_V1",
        "generated_utc": generated_utc,
        "run_id": RUN_ID,
        "status": "B5_0_STEP_SIDECARS_PASS_AS_NON_AUTHORITATIVE_PREVIEWS",
        "source_step": artifact(step),
        "source_step_hash_before": EXPECTED_STEP_SHA256,
        "source_step_hash_after": sha256(step),
        "generation": {
            "requested_tool": "cadpy_0.3.9",
            "direct_step_branch": "TOOL_DEVIATION_EXIT_0_WITHOUT_REQUESTED_SIDECARS",
            "fallback": "cadpy_internal_generate_part_outputs",
            "step_writer_called": False,
            "primary_step_modified": False,
            "mesh_tolerance": 0.08,
            "mesh_angular_tolerance": 1.20,
            "mesh_tolerance_semantics": "relative_deflection_not_mm",
        },
        "sidecars": {
            "stl": mesh_facts(stl),
            "native_glb": mesh_facts(glb),
            "step_topology_glb": mesh_facts(topology_glb),
        },
        "known_mesh_warning": "4 faces skipped due to null triangulation",
        "claim_limit": (
            "STL and GLB are visualization/collision-preview derivatives only; "
            "they omit four null-triangulation faces and do not supersede the "
            "cold-verified 388-solid STEP."
        ),
    }
    require(
        sidecar["source_step_hash_before"] == sidecar["source_step_hash_after"],
        "STEP changed during sidecar generation",
    )
    write_new_json(sidecar_path, sidecar)

    image1 = REVIEWS / "B50_B601_ENGINEERING_ARM_Q0_vtk_review.png"
    image2 = REVIEWS / "B50_B601_ENGINEERING_ARM_Q0_vtk_review_attempt2.png"
    ratio1 = foreground_ratio(image1)
    ratio2 = foreground_ratio(image2)
    require(ratio1 < 0.002, "first visual attempt is not the recorded blank render")
    require(ratio2 >= 0.002, "second visual attempt has insufficient foreground")
    require(
        attempt2["image_validation"]["foreground_ratio"] >= 0.002,
        "attempt2 receipt did not pass its foreground gate",
    )
    require(
        attempt2["source_stl"]["sha256"] == sidecar["sidecars"]["stl"]["sha256"],
        "visual review source STL does not match sidecar evidence",
    )
    visual = {
        "schema": "SER_B50_VISUAL_REVIEW_ADJUDICATION_V1",
        "generated_utc": generated_utc,
        "run_id": RUN_ID,
        "status": "B5_0_VISUAL_REVIEW_PASS_WITH_INVALIDATED_ATTEMPT_AND_TOOL_DEVIATION",
        "standard_cad_snapshot": {
            "attempts": 3,
            "result": "TOOL_DEVIATION_BROWSER_RESOURCE_FAILURE",
            "png_generated": False,
        },
        "fallback_attempts": [
            {
                "attempt": 1,
                "receipt": artifact(EVIDENCE / "visual_review_vtk.json"),
                "image": artifact(image1),
                "foreground_ratio_recomputed": ratio1,
                "adjudication": "INVALIDATED_EMPTY_FOREGROUND",
                "note": (
                    "The receipt self-reported PASS before foreground validation "
                    "was added; it is explicitly excluded from accepted evidence."
                ),
            },
            {
                "attempt": 2,
                "receipt": artifact(EVIDENCE / "visual_review_vtk_attempt2.json"),
                "image": artifact(image2),
                "foreground_ratio_recomputed": ratio2,
                "adjudication": "ACCEPTED_VISUAL_EVIDENCE",
            },
        ],
        "qualitative_review": {
            "reviewer": "CODEX_VISUAL_INSPECTION",
            "geometry_visible": True,
            "folded_multijoint_arm_readable": True,
            "all_components_collapsed_at_origin": False,
            "giant_coordinate_spikes": False,
            "bounds_consistent_with_step_mm": True,
        },
        "source_limit": (
            "The accepted visual image is rendered from the STEP-derived STL. "
            "It is not a replacement for the cold STEP verification."
        ),
    }
    write_new_json(visual_path, visual)

    sldworks = sorted(
        {
            process.pid
            for process in psutil.process_iter(["pid", "name"])
            if str(process.info.get("name") or "").lower() == "sldworks.exe"
        }
    )
    locks = [
        rel(path)
        for path in RUN.rglob("~$*")
        if path.is_file()
    ]
    require(not sldworks, f"SolidWorks processes remain: {sldworks}")
    require(not locks, f"SolidWorks lock files remain: {locks}")

    step_check = cold["checks"]["step"]
    require(step_check["ocp_read"] == "PASS", "STEP OCP cold read is not PASS")
    require(step_check["solid_count"] == 388, "STEP solid count is not 388")
    require(
        step_check["max_bbox_abs_error_mm"] <= 0.1,
        "STEP bbox error exceeds the 0.1 mm gate",
    )
    require(cold["artifact_hashes_unchanged_at_exit"] is True, "cold verification altered artifacts")

    gate = {
        "schema": "SER_B50_GATE_STATUS_V1",
        "gate_id": "COMP-PROT-03-A4-B5.0-B601-SPACE-MANIPULATOR-ENGINEERING-CAD",
        "generated_utc": generated_utc,
        "run_id": RUN_ID,
        "verdict": (
            "B5_0_PHASE1_NATIVE_Q0_REFERENCE_PASS_WITH_G05_G08_HOLD_"
            "AND_RECORDED_TOOL_DEVIATIONS"
        ),
        "scope": (
            "Native SolidWorks fixed-q0 engineering geometry reference only; "
            "not the complete B5.0 spacecraft-integrated mechanism."
        ),
        "truth_authority": {
            "accepted_urdf": {
                **source_contract["accepted_urdf"],
                "mass_kg_source_decimal": "4.6955559493429862",
                "editable": False,
            },
            "cad_mass_authority": "EXCLUDED_ACCEPTED_URDF_ONLY",
            "cad_mechanism_dof_authority": "NONE_FIXED_Q0_REFERENCE",
            "vendor_geometry_role": "GEOMETRY_REFERENCE_ONLY",
        },
        "artifacts": {
            "master_skeleton": receipt_run_artifact(
                cold["checks"]["build_receipts"]["master_skeleton"]
            ),
            "native_parts": {
                group: receipt_run_artifact(value)
                for group, value in cold["checks"]["build_receipts"][
                    "native_parts"
                ].items()
            },
            "assembly": artifact(assembly),
            "drawing": artifact(drawing),
            "step": artifact(step),
            "stl_preview": artifact(stl),
            "glb_preview": artifact(glb),
            "visual_review": artifact(image2),
        },
        "native_cad_checks": {
            "native_parts": 8,
            "assembly_components": 9,
            "component_model": (
                "8_LINKLOCAL_GEOMETRY_PARTS_PLUS_1_ZERO_SOLID_MASTER_SKELETON"
            ),
            "all_components_fixed": True,
            "retained_mechanism_dof": False,
            "drawing_model_backed_views": 1,
            "step_solid_count": 388,
            "step_bbox_mm": step_check["bbox_mm"],
            "max_bbox_error_vs_registered_q0_mm": step_check[
                "max_bbox_abs_error_mm"
            ],
            "solidworks_processes_after_gate": sldworks,
            "solidworks_lock_files_after_gate": locks,
            "cad_cli_inspect_refs": cad_cli["summary"],
        },
        "source_status": {
            "direct_geometry_groups": ["G01", "G02", "G03", "G04", "G06", "G07"],
            "hold_groups": ["G05", "G08"],
            "b106": "NOT_FOUND_IN_PHASE0_BOUNDED_SEARCH",
            "protected_baseline": "79_OF_79_PASS",
        },
        "mechanical_design_gates": {
            "G0_BASELINE_PROTECTION": "PASS",
            "G1_KINEMATIC_CONSISTENCY": "PASS_FOR_FIXED_Q0_REFERENCE_ONLY",
            "G2_ENGINEERING_FORM_COMPLETENESS": (
                "PARTIAL_HOLD_ENGINEERED_INTERNAL_LOAD_PATHS_BASE_ADAPTER_"
                "STOWAGE_EE_SENSORS_HARNESS_NOT_COMPLETE"
            ),
            "G3_ASSEMBLY_AND_CLEARANCE": (
                "HOLD_NO_SPACECRAFT_TOP_LEVEL_OR_CONTINUOUS_CLEARANCE_EVIDENCE"
            ),
            "G4_DIGITAL_THREAD": (
                "PARTIAL_CAD_STEP_TRACE_PASS_CANDIDATE_URDF_MJCF_USD_PENDING"
            ),
            "G5_SIMULATION_RUNNABLE": "HOLD_NOT_EXECUTED",
            "G6_CLAIM_COMPLIANCE": "PASS_WITH_EXPLICIT_LIMITS",
        },
        "evidence": {
            "build_attempt": rel(EVIDENCE / "q0_assembly_build_attempt3.json"),
            "cold_verification": rel(EVIDENCE / "native_q0_cold_verify.json"),
            "sidecar_generation": rel(sidecar_path),
            "visual_adjudication": rel(visual_path),
            "cad_cli_inspect_refs": rel(EVIDENCE / "cad_cli_inspect_refs.json"),
            "protected_hashes": rel(VERIFY / "protected_hash_verification.json"),
        },
        "tool_deviations": [
            {
                "id": "B50-NATIVE-DEV-001",
                "condition": (
                    "Early-bound pywin32 IMathUtility.CreateTransform(list) "
                    "silently produced an identity transform."
                ),
                "resolution": (
                    "Typed VT_ARRAY|VT_R8 SAFEARRAY marshalling was used; "
                    "input, post-set, post-fix, and cold-reopen transforms passed."
                ),
            },
            {
                "id": "B50-NATIVE-DEV-002",
                "condition": (
                    "cadpy 0.3.9 direct STEP sidecar branch exited 0 without "
                    "creating the requested STL/native GLB."
                ),
                "resolution": (
                    "Internal part-output path generated sidecars without a "
                    "STEP writer; source STEP hash remained unchanged."
                ),
            },
            {
                "id": "B50-NATIVE-DEV-003",
                "condition": (
                    "Three standard CAD snapshot attempts closed the browser "
                    "context under the topology payload."
                ),
                "resolution": (
                    "VTK offscreen review used the same-STEP derived STL. "
                    "Attempt 1 was blank and invalidated; attempt 2 passed an "
                    "explicit foreground-pixel gate and visual inspection."
                ),
            },
            {
                "id": "B50-NATIVE-DEV-004",
                "condition": (
                    "STL/GLB meshing skipped four faces with null triangulation."
                ),
                "resolution": (
                    "Sidecars are preview-only; 388-solid OCP-cold-read STEP "
                    "remains the geometry exchange authority."
                ),
            },
        ],
        "remaining_holds": [
            "G05 and G08 vendor registration remain CHAIN_DERIVED_HOLD.",
            "B106 is bounded-not-found, not proven absent globally.",
            "The SolidWorks assembly is a fixed q0 reference with no retained joint DOF; neither the accepted 6R arm motion nor the two prismatic gripper motions are implemented as movable components/mates.",
            "Phase 2 engineered joint/load-path decomposition is not complete.",
            "Base adapter, front saddle, rear wrist support, HDRM envelope, end effector, sensors, and harness are not complete.",
            "No spacecraft top-level integration or continuous solar-wing/arm clearance has been accepted.",
            "Candidate URDF, collision meshes, MJCF, USD, and free-floating simulation remain pending.",
            "No manufacturing, strength, launch, flight, capture-generalization, or autonomous-VLA claim is authorized.",
        ],
        "next_gate": (
            "PHASE2_ENGINEERING_DECOMPOSITION_AND_PHASE3_INTERFACE_EVIDENCE_GATE"
        ),
    }
    write_new_json(gate_path, gate)

    print(
        json.dumps(
            {
                "verdict": gate["verdict"],
                "protected_baseline": "79/79 PASS",
                "step_solids": step_check["solid_count"],
                "visual_foreground_ratio": ratio2,
                "solidworks_processes": len(sldworks),
                "outputs": [rel(sidecar_path), rel(visual_path), rel(gate_path)],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
