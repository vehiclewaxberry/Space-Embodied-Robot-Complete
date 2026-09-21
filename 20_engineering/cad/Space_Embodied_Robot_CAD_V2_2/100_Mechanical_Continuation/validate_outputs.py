"""Run deterministic local validation for the isolated V2.2 STEP assembly.

All generated reports stay under ./validation.  The script does not inspect or
write the canonical V2.2 SolidWorks assembly.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VALIDATION = ROOT / "validation"
SOURCE = ROOT / "v22_mechanical_continuation.py"
STEP = ROOT / "v22_mechanical_continuation.step"
GLB = ROOT / ".v22_mechanical_continuation.step.glb"
INSPECT = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9"
    r"\skills\cad\scripts\inspect"
)
TOL = 1.0e-6


def _hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_source():
    spec = importlib.util.spec_from_file_location("v22mc_validate", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_inspect(report_name: str, args: list[str]) -> dict:
    command = [sys.executable, str(INSPECT), *args, "--format", "json"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=120,
        check=False,
    )
    record = {
        "command": command,
        "cwd": str(ROOT),
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    (VALIDATION / f"{report_name}.raw.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{report_name} failed rc={result.returncode}: {result.stderr}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{report_name} did not return JSON: {result.stdout[:500]}"
        ) from exc
    (VALIDATION / f"{report_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _close(actual: float, expected: float) -> bool:
    return abs(float(actual) - float(expected)) <= TOL


def _measurement(payload: dict) -> float:
    return float(payload["measurement"]["absoluteDistance"])


def _selection(payload: dict) -> dict:
    return payload["tokens"][0]["selections"][0]


def _labels(shape) -> list[str]:
    labels: list[str] = []

    def visit(node):
        label = str(getattr(node, "label", "") or "")
        if label:
            labels.append(label)
        for child in tuple(getattr(node, "children", ()) or ()):
            visit(child)

    visit(shape)
    return labels


def main() -> int:
    VALIDATION.mkdir(parents=True, exist_ok=True)
    module = _load_source()
    shape = module.gen_step()
    solids = list(shape.solids())
    labels = _labels(shape)
    from build123d import import_step

    reopened_shape = import_step(STEP)
    reopened_solids = list(reopened_shape.solids())
    reopened_bbox = reopened_shape.bounding_box()

    baseline = _run_inspect(
        "baseline_refs_facts_planes_positioning",
        [
            "refs",
            STEP.name,
            "--facts",
            "--planes",
            "--positioning",
        ],
    )
    interface_refs = _run_inspect(
        "targeted_interface_refs",
        [
            "refs",
            STEP.name,
            "#o1.2.1",
            "#o1.2.1.f6",
            "#o1.2.1.f7",
            "#o1.2.2",
            "#o1.2.2.f1",
            "#o1.2.2.f2",
            "#o1.2.2.f4",
            "#o1.2.2.f5",
            "--detail",
            "--facts",
            "--positioning",
        ],
    )
    module_refs = _run_inspect(
        "module_refs",
        [
            "refs",
            STEP.name,
            "#o1",
            "#o1.1",
            "#o1.2",
            "#o1.3",
            "#o1.4",
            "#o1.5",
            "--facts",
            "--positioning",
        ],
    )
    mount_thickness = _run_inspect(
        "measure_mount_thickness",
        [
            "measure",
            STEP.name,
            "--from",
            "#o1.2.1.f1",
            "--to",
            "#o1.2.1.f8",
            "--axis",
            "x",
        ],
    )
    mount_width = _run_inspect(
        "measure_mount_width",
        [
            "measure",
            STEP.name,
            "--from",
            "#o1.2.1.f2",
            "--to",
            "#o1.2.1.f5",
            "--axis",
            "y",
        ],
    )
    mount_height = _run_inspect(
        "measure_mount_height",
        [
            "measure",
            STEP.name,
            "--from",
            "#o1.2.1.f4",
            "--to",
            "#o1.2.1.f3",
            "--axis",
            "z",
        ],
    )
    bus_width = _run_inspect(
        "measure_bus_width",
        [
            "measure",
            STEP.name,
            "--from",
            "#o1.1.2.f3",
            "--to",
            "#o1.1.4.f4",
            "--axis",
            "y",
        ],
    )
    c5_width = _run_inspect(
        "measure_c5_stowed_package_width",
        [
            "measure",
            STEP.name,
            "--from",
            "#o1.4.2.15.f3",
            "--to",
            "#o1.4.1.15.f4",
            "--axis",
            "y",
        ],
    )
    adapter_flush = _run_inspect(
        "align_mount_plate_to_adapter",
        [
            "align",
            STEP.name,
            "--moving",
            "#o1.2.2.f3",
            "--target",
            "#o1.2.1.f8",
            "--mode",
            "flush",
            "--axis",
            "x",
        ],
    )
    mount_frame = _run_inspect(
        "frame_mount_plate",
        ["frame", STEP.name, "#o1.2.1"],
    )

    baseline_token = baseline["tokens"][0]
    baseline_summary = baseline_token["summary"]
    contract = module.design_contract()
    interface_by_selector = {
        item["token"]: item["selections"][0]
        for item in interface_refs["tokens"]
    }

    checks = {
        "step_exists_nonempty": STEP.is_file() and STEP.stat().st_size > 0,
        "glb_exists_nonempty": GLB.is_file() and GLB.stat().st_size > 0,
        "shape_valid": bool(shape.is_valid),
        "all_122_solids_valid": (
            len(solids) == 122 and all(bool(solid.is_valid) for solid in solids)
        ),
        "all_solids_positive_volume": all(
            float(solid.volume) > 0.0 for solid in solids
        ),
        "step_reopen_122_solids_valid": (
            len(reopened_solids) == 122
            and all(bool(solid.is_valid) for solid in reopened_solids)
        ),
        "step_reopen_all_solids_positive_volume": all(
            float(solid.volume) > 0.0 for solid in reopened_solids
        ),
        "step_reopen_bbox_persistent": all(
            _close(actual, expected)
            for actual, expected in zip(
                (
                    reopened_bbox.min.X,
                    reopened_bbox.min.Y,
                    reopened_bbox.min.Z,
                    reopened_bbox.max.X,
                    reopened_bbox.max.Y,
                    reopened_bbox.max.Z,
                ),
                (
                    -213.0,
                    -151.15,
                    -200.0,
                    580.0,
                    151.15,
                    140.0,
                ),
            )
        ),
        "baseline_refs_ok": bool(baseline.get("ok")),
        "baseline_zero_warnings": not baseline_token.get("warnings"),
        "assembly_occurrence_count_132": (
            baseline_summary["occurrenceCount"] == 132
        ),
        "leaf_occurrence_count_122": (
            baseline_summary["leafOccurrenceCount"] == 122
        ),
        "shape_count_122": baseline_summary["shapeCount"] == 122,
        "mount_plate_thickness_12_mm": _close(
            _measurement(mount_thickness),
            module.MOUNT_PLATE_THICKNESS_MM,
        ),
        "mount_plate_width_160_mm": _close(
            _measurement(mount_width),
            module.MOUNT_PLATE_WIDTH_MM,
        ),
        "mount_plate_height_160_mm": _close(
            _measurement(mount_height),
            module.MOUNT_PLATE_HEIGHT_MM,
        ),
        "central_interface_radius_50_mm": _close(
            interface_by_selector["#o1.2.1.f6"]["positioning"]["radius"],
            module.CENTRAL_INTERFACE_DIAMETER_MM / 2,
        ),
        "harness_passage_radius_15_mm": _close(
            interface_by_selector["#o1.2.1.f7"]["positioning"]["radius"],
            module.SOURCE_B5_DISPLAY_HARNESS_PASSAGE_DIAMETER / 2,
        ),
        "adapter_outer_radius_90_mm": _close(
            interface_by_selector["#o1.2.2.f1"]["positioning"]["radius"],
            module.SOURCE_B5_DISPLAY_ADAPTER_OD / 2,
        ),
        "adapter_inner_radius_50_mm": _close(
            interface_by_selector["#o1.2.2.f4"]["positioning"]["radius"],
            module.SOURCE_B5_DISPLAY_ADAPTER_ID / 2,
        ),
        "connector_reservation_radius_9_mm": _close(
            interface_by_selector["#o1.2.2.f5"]["positioning"]["radius"],
            module.SOURCE_B5_DISPLAY_CONNECTOR_WINDOW_DIAMETER / 2,
        ),
        "adapter_outer_face_x_198_mm": _close(
            interface_by_selector["#o1.2.2.f2"]["positioning"]["coordinate"],
            198.0,
        ),
        "adapter_plate_flush_delta_zero": all(
            _close(value, 0.0)
            for value in adapter_flush["alignment"][
                "translationVector"
            ]
        ),
        "bus_width_226_3_mm": _close(
            _measurement(bus_width),
            module.C5_AVAILABLE_MM,
        ),
        "stowed_package_width_238_3_mm": _close(
            _measurement(c5_width),
            module.C5_REQUIRED_MM,
        ),
        "c5_negative_relation_preserved": (
            _measurement(c5_width) > _measurement(bus_width)
            and _close(
                _measurement(c5_width) - _measurement(bus_width),
                12.0,
            )
        ),
        "solar_root_mechanism_bbox_width_302_3_mm": _close(
            baseline_summary["bounds"]["max"][1]
            - baseline_summary["bounds"]["min"][1],
            302.3,
        ),
        "mount_frame_axes_identity": (
            mount_frame["frame"]["localAxes"]
            == {
                "x": [1.0, 0.0, 0.0],
                "y": [0.0, 1.0, 0.0],
                "z": [0.0, 0.0, 1.0],
            }
        ),
        "required_occurrence_labels_present": all(
            any(required in label for label in labels)
            for required in (
                "B601_MOUNT_PLATE",
                "B601_CENTRAL_INTERFACE",
                "ARM_STOW",
                "SOLAR_ROOT",
                "PLATFORM",
            )
        ),
        "service_pending_ratification": (
            module.SERVICE_STATUS == "PENDING_RATIFICATION"
        ),
        "capture_safe_not_upgraded": (
            module.CAPTURE_SAFE_STATUS
            == "UNKNOWN_CANDIDATE_NOT_UPGRADED"
        ),
        "visual_mass_authority_excluded": (
            contract["authority"]["mass"] == "EXCLUDED"
        ),
    }

    report = {
        "validation_id": "V22_MECHANICAL_CONTINUATION_VALIDATION_01",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "source_sha256": _hash(SOURCE),
        "step_sha256": _hash(STEP),
        "glb_sha256": _hash(GLB),
        "step_bytes": STEP.stat().st_size,
        "glb_bytes": GLB.stat().st_size,
        "shape": {
            "root_label": shape.label,
            "root_child_count": len(tuple(shape.children)),
            "solid_count": len(solids),
            "positive_volume_sum_mm3": sum(
                float(solid.volume) for solid in solids
            ),
            "bbox_mm": baseline_summary["bounds"],
            "occurrence_count": baseline_summary["occurrenceCount"],
            "leaf_occurrence_count": baseline_summary["leafOccurrenceCount"],
            "face_count": baseline_summary["faceCount"],
            "edge_count": baseline_summary["edgeCount"],
            "reopened_step_solid_count": len(reopened_solids),
            "reopened_step_bbox_mm": {
                "min": [
                    reopened_bbox.min.X,
                    reopened_bbox.min.Y,
                    reopened_bbox.min.Z,
                ],
                "max": [
                    reopened_bbox.max.X,
                    reopened_bbox.max.Y,
                    reopened_bbox.max.Z,
                ],
            },
        },
        "measurements_mm": {
            "mount_plate_thickness": _measurement(mount_thickness),
            "mount_plate_width": _measurement(mount_width),
            "mount_plate_height": _measurement(mount_height),
            "central_interface_diameter": (
                2
                * interface_by_selector["#o1.2.1.f6"]["positioning"][
                    "radius"
                ]
            ),
            "harness_passage_diameter": (
                2
                * interface_by_selector["#o1.2.1.f7"]["positioning"][
                    "radius"
                ]
            ),
            "adapter_od": (
                2
                * interface_by_selector["#o1.2.2.f1"]["positioning"][
                    "radius"
                ]
            ),
            "adapter_id": (
                2
                * interface_by_selector["#o1.2.2.f4"]["positioning"][
                    "radius"
                ]
            ),
            "connector_reservation_diameter": (
                2
                * interface_by_selector["#o1.2.2.f5"]["positioning"][
                    "radius"
                ]
            ),
            "adapter_outer_face_x": interface_by_selector[
                "#o1.2.2.f2"
            ]["positioning"]["coordinate"],
            "bus_available_width": _measurement(bus_width),
            "c5_stowed_package_width": _measurement(c5_width),
            "c5_overage": _measurement(c5_width)
            - _measurement(bus_width),
            "solar_root_mechanism_lower_bound_width": (
                baseline_summary["bounds"]["max"][1]
                - baseline_summary["bounds"]["min"][1]
            ),
        },
        "selectors": {
            "mount_plate": "#o1.2.1",
            "central_interface_cylinder": "#o1.2.1.f6",
            "harness_passage_cylinder": "#o1.2.1.f7",
            "adapter": "#o1.2.2",
            "adapter_outer_face": "#o1.2.2.f2",
            "adapter_inner_cylinder": "#o1.2.2.f4",
            "connector_reservation_cylinder": "#o1.2.2.f5",
            "arm_stow_main": "#o1.3.1",
            "arm_stow_wrist": "#o1.3.2",
            "solar_module": "#o1.4",
            "c5_right_outer_face": "#o1.4.2.15.f3",
            "c5_left_outer_face": "#o1.4.1.15.f4",
        },
        "adapter_plate_alignment": adapter_flush["alignment"],
        "design_contract": contract,
        "checks": checks,
        "failed_checks": [
            name for name, passed in checks.items() if not passed
        ],
        "claim_limits": [
            "No structural strength or stiffness qualification.",
            "No launch-load or release-shock qualification.",
            "No SolidWorks configuration/BOM/mass-exclusion semantics in STEP.",
            "No B601 vendor LOD1 geometry or contact-face qualification.",
            "C5 remains HOLD; the negative 238.3 mm > 226.3 mm is preserved.",
        ],
    }
    (VALIDATION / "design_contract_validation.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
