"""Run reproducible CAD CLI validation for the isolated solar Gate 1-3 rig.

All outputs stay beside this script.  The checks deliberately separate:
- baseline refs/facts/planes/positioning for every generated STEP;
- scalar geometry measurements;
- face/occurrence frame checks for hinge and cell-face orientation.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
SOLAR_DIR = THIS_DIR.parent
WORKSPACE = THIS_DIR.parents[5]
INSPECT = Path(
    r"C:\Users\stude\.codex\plugins\cache\text-to-cad\cad\0.3.9"
    r"\skills\cad\scripts\inspect"
)

POSE_TAGS = ("000", "005", "015", "030", "060", "090")


def _target(name: str) -> str:
    return (SOLAR_DIR / name).relative_to(WORKSPACE).as_posix()


def _run(case: dict) -> dict:
    args = ["python", str(INSPECT), *case["args"], "--format", "json"]
    output = THIS_DIR / f"{case['id']}.json"
    # Always regenerate selector evidence.  Command equality is not a valid
    # cache key because the STEP at the same path can change after an
    # adversarial repair; reusing the prior payload would mix current artifact
    # hashes with stale geometry observations.
    completed = subprocess.run(
        args,
        cwd=WORKSPACE,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    record = {
        "id": case["id"],
        "command": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode == 0:
        record["payload"] = json.loads(completed.stdout)
    output.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return record


def _close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(float(a) - float(b)) <= tol


def _vector_close(actual, expected, tol: float = 1e-6) -> bool:
    return len(actual) == len(expected) and all(
        _close(a, b, tol) for a, b in zip(actual, expected)
    )


def _evaluate(record: dict, case: dict) -> dict:
    result = {
        "id": case["id"],
        "category": case["category"],
        "status": "FAIL",
        "expected": case.get("expected"),
    }
    if record["returncode"] != 0:
        result["reason"] = "CLI_RETURN_CODE_NONZERO"
        return result

    payload = record["payload"]
    if not payload.get("ok"):
        result["reason"] = "CAD_CLI_PAYLOAD_NOT_OK"
        return result

    if case["category"] == "refs":
        summary = payload["tokens"][0]["summary"]
        result["observed"] = summary
        result["status"] = "PASS"
        return result

    if case["category"] == "measure":
        observed = payload["measurement"]["absoluteDistance"]
        result["observed"] = observed
        result["status"] = (
            "PASS" if _close(observed, case["expected"]["absoluteDistance"]) else "FAIL"
        )
        return result

    selection = payload.get("selectionPositioning") or payload["frame"]
    result["observed"] = {
        "kind": selection.get("kind"),
        "center": selection.get("center"),
        "normal": selection.get("normal"),
        "bbox_size": selection.get("bboxFacts", {}).get("size"),
        "extent_axis": selection.get("bboxFacts", {}).get("extentAxis"),
    }
    expected = case["expected"]
    checks = []
    if "normal" in expected:
        checks.append(_vector_close(selection.get("normal", []), expected["normal"]))
    if "center" in expected:
        checks.append(_vector_close(selection.get("center", []), expected["center"]))
    if "center_axis" in expected:
        axis_index = {"x": 0, "y": 1, "z": 2}[expected["center_axis"]]
        checks.append(
            _close(selection["center"][axis_index], expected["center_coordinate"])
        )
    if "bbox_size" in expected:
        checks.append(
            _vector_close(selection["bboxFacts"]["size"], expected["bbox_size"])
        )
    if "extent_axis" in expected:
        checks.append(selection["bboxFacts"]["extentAxis"] == expected["extent_axis"])
    result["status"] = "PASS" if checks and all(checks) else "FAIL"
    return result


def main() -> int:
    cases = []
    for tag in POSE_TAGS:
        cases.append(
            {
                "id": f"refs_pose_{tag}deg",
                "category": "refs",
                "args": [
                    "refs",
                    _target(f"solar_deployment_pose_{tag}deg.step"),
                    "--facts",
                    "--planes",
                    "--positioning",
                ],
            }
        )
    cases.append(
        {
            "id": "refs_sweep_samples",
            "category": "refs",
            "args": [
                "refs",
                _target("solar_deployment_sweep_samples.step"),
                "--facts",
                "--planes",
                "--positioning",
            ],
        }
    )

    pose0 = _target("solar_deployment_pose_000deg.step")
    pose90 = _target("solar_deployment_pose_090deg.step")
    cases.extend(
        [
            {
                "id": "measure_pose_000_panel_x_span",
                "category": "measure",
                "args": [
                    "measure",
                    pose0,
                    "--from",
                    "#o1.4.1.f1",
                    "--to",
                    "#o1.4.1.f2",
                    "--axis",
                    "x",
                ],
                "expected": {"absoluteDistance": 227.0},
            },
            {
                "id": "measure_pose_000_panel_thickness",
                "category": "measure",
                "args": [
                    "measure",
                    pose0,
                    "--from",
                    "#o1.4.1.f3",
                    "--to",
                    "#o1.4.1.f4",
                    "--axis",
                    "y",
                ],
                "expected": {"absoluteDistance": 6.0},
            },
            {
                "id": "measure_pose_000_panel_height",
                "category": "measure",
                "args": [
                    "measure",
                    pose0,
                    "--from",
                    "#o1.4.1.f5",
                    "--to",
                    "#o1.4.1.f6",
                    "--axis",
                    "z",
                ],
                "expected": {"absoluteDistance": 200.0},
            },
            {
                "id": "measure_pose_000_hinge_station_separation",
                "category": "measure",
                "args": [
                    "measure",
                    pose0,
                    "--from",
                    "#o1.2.9",
                    "--to",
                    "#o1.2.13",
                    "--axis",
                    "x",
                ],
                "expected": {"absoluteDistance": 149.82},
            },
            {
                "id": "measure_pose_090_left_panel_radial_length",
                "category": "measure",
                "args": [
                    "measure",
                    pose90,
                    "--from",
                    "#o1.4.1.f5",
                    "--to",
                    "#o1.4.1.f6",
                    "--axis",
                    "y",
                ],
                "expected": {"absoluteDistance": 200.0},
            },
            {
                "id": "measure_pose_090_panel_x_span",
                "category": "measure",
                "args": [
                    "measure",
                    pose90,
                    "--from",
                    "#o1.4.1.f1",
                    "--to",
                    "#o1.4.1.f2",
                    "--axis",
                    "x",
                ],
                "expected": {"absoluteDistance": 227.0},
            },
            {
                "id": "frame_pose_000_left_outer_surface",
                "category": "frame",
                "args": ["frame", pose0, "#o1.4.1.f4"],
                "expected": {
                    "normal": [0.0, 1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": 113.0,
                },
            },
            {
                "id": "frame_pose_000_right_outer_surface",
                "category": "frame",
                "args": ["frame", pose0, "#o1.5.1.f3"],
                "expected": {
                    "normal": [0.0, -1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": -113.0,
                },
            },
            {
                "id": "frame_pose_000_left_cell_inward",
                "category": "frame",
                "args": ["frame", pose0, "#o1.4.2.f3"],
                "expected": {
                    "normal": [0.0, -1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": 106.6,
                },
            },
            {
                "id": "frame_pose_000_right_cell_inward",
                "category": "frame",
                "args": ["frame", pose0, "#o1.5.2.f4"],
                "expected": {
                    "normal": [0.0, 1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": -106.6,
                },
            },
            {
                "id": "frame_pose_000_left_hinge_pin_x",
                "category": "frame",
                "args": ["frame", pose0, "#o1.2.9"],
                "expected": {
                    "bbox_size": [26.0, 6.0, 6.0],
                    "extent_axis": "x",
                    "center_axis": "y",
                    "center_coordinate": 110.0,
                },
            },
            {
                "id": "frame_pose_000_left_panel_root_on_hinge",
                "category": "frame",
                "args": ["frame", pose0, "#o1.4.1.f5"],
                "expected": {
                    "center": [-61.0, 110.0, -105.65],
                    "normal": [0.0, 0.0, -1.0],
                },
            },
            {
                "id": "frame_pose_030_left_panel_root_on_hinge",
                "category": "frame",
                "args": [
                    "frame",
                    _target("solar_deployment_pose_030deg.step"),
                    "#o1.4.1.f5",
                ],
                "expected": {
                    "center": [-61.0, 110.0, -105.65],
                },
            },
            {
                "id": "frame_pose_090_left_tip",
                "category": "frame",
                "args": ["frame", pose90, "#o1.4.1.f6"],
                "expected": {
                    "normal": [0.0, 1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": 310.0,
                },
            },
            {
                "id": "frame_pose_090_left_panel_root_on_hinge",
                "category": "frame",
                "args": ["frame", pose90, "#o1.4.1.f5"],
                "expected": {
                    "center": [-61.0, 110.0, -105.65],
                    "normal": [0.0, -1.0, 0.0],
                },
            },
            {
                "id": "frame_pose_090_right_panel_root_on_hinge",
                "category": "frame",
                "args": ["frame", pose90, "#o1.5.1.f5"],
                "expected": {
                    "center": [-61.0, -110.0, -105.65],
                    "normal": [0.0, 1.0, 0.0],
                },
            },
            {
                "id": "frame_pose_090_right_tip",
                "category": "frame",
                "args": ["frame", pose90, "#o1.5.1.f6"],
                "expected": {
                    "normal": [0.0, -1.0, 0.0],
                    "center_axis": "y",
                    "center_coordinate": -310.0,
                },
            },
            {
                "id": "frame_pose_090_left_cell_plus_z",
                "category": "frame",
                "args": ["frame", pose90, "#o1.4.2.f3"],
                "expected": {
                    "normal": [0.0, 0.0, 1.0],
                    "center_axis": "z",
                    "center_coordinate": -102.25,
                },
            },
            {
                "id": "frame_pose_090_right_cell_plus_z",
                "category": "frame",
                "args": ["frame", pose90, "#o1.5.2.f4"],
                "expected": {
                    "normal": [0.0, 0.0, 1.0],
                    "center_axis": "z",
                    "center_coordinate": -102.25,
                },
            },
        ]
    )

    records = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(_run, case): case for case in cases}
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            records[record["id"]] = record

    evaluations = [
        _evaluate(records[case["id"]], case)
        for case in cases
    ]
    pass_count = sum(item["status"] == "PASS" for item in evaluations)
    fail_count = sum(item["status"] == "FAIL" for item in evaluations)

    artifacts = {}
    for tag in POSE_TAGS:
        path = SOLAR_DIR / f"solar_deployment_pose_{tag}deg.step"
        artifacts[path.name] = {
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    sweep_path = SOLAR_DIR / "solar_deployment_sweep_samples.step"
    artifacts[sweep_path.name] = {
        "bytes": sweep_path.stat().st_size,
        "sha256": hashlib.sha256(sweep_path.read_bytes()).hexdigest(),
    }

    summary = {
        "decision_id": "V22-LAYOUT-AND-DEPLOYMENT-01",
        "scope": "SOLAR_GATE_1_TO_3_ONLY",
        "gate_verdict": (
            "PASS_GEOMETRY_AND_DISCRETE_KINEMATIC_DIAGNOSTIC_WITH_HOLDS"
            if fail_count == 0
            else "HOLD_VALIDATION_FAILURE"
        ),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "partial_state_angle": None,
        "samples_define_partial": False,
        "actual_deployed_tip_abs_y_mm": 310.0,
        "legacy_tip_abs_y_mm": 313.15,
        "legacy_tip_status": "HOLD_INTERFACE_RATIFICATION",
        "checks": evaluations,
        "artifacts": artifacts,
        "claim_limits": [
            "NO_STRENGTH_CLAIM",
            "NO_STIFFNESS_CLAIM",
            "NO_RELEASE_RELIABILITY_CLAIM",
            "NO_MANUFACTURING_CLAIM",
            "NO_PURCHASED_PART_REPRESENTATION",
            "NO_NATIVE_SOLIDWORKS_CLAIM",
        ],
    }
    (THIS_DIR / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
