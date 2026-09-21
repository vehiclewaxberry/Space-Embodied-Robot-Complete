"""Fail-closed post-generation validation for the integrated R2 CAD candidate.

This module never generates CAD.  ``--preflight`` checks that the future
inspection and snapshot chain targets the integrated 399-solid candidate.
``--postgenerate`` is legal only after the guarded generator has emitted a STEP,
GLB/topology sidecar and matching execution receipt.  It then invokes the
standard CAD ``inspect refs`` entry and checks assembly cardinality and bounds.

Neither mode grants M01, collision, contact, dynamics, manufacturing or release
authority.  CAD imports live in the external inspection process and are never
performed during source-only preflight.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parent
WORKSPACE = next(
    candidate
    for candidate in (PACKAGE, *PACKAGE.parents)
    if (candidate / "PROJECT_MAP.md").is_file()
)
INPUTS = PACKAGE / "INTEGRATED_CANDIDATE_INPUTS_V1.json"
GENERATOR = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.py"
WRAPPER = PACKAGE / "execute_integrated_candidate_v1.py"
WRAPPER_V2 = PACKAGE / "execute_integrated_candidate_v2.py"
OUTPUT_STEP = PACKAGE / "R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step"
OUTPUT_GLB = PACKAGE / ".R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step.glb"
ACTIVE_LOCK = PACKAGE / ".r2_integrated_candidate_active_run.lock"
SNAPSHOT_JOB = PACKAGE / "CAD_CANDIDATE_SNAPSHOT_JOB_V2.json"
EXECUTION_RECEIPTS = PACKAGE / "candidate_execution_receipts"
CHAIN_RECEIPTS = PACKAGE / "candidate_execution_chain_receipts"
FAILURE_RECEIPTS = PACKAGE / "candidate_failure_receipts"
PREFLIGHT_RECEIPT = PACKAGE / "CAD_POSTGENERATION_VALIDATOR_PREFLIGHT_V1.json"
POSTGEN_RECEIPT = PACKAGE / "CAD_POSTGENERATION_VALIDATION_V1.json"
INSPECT_RECEIPT = PACKAGE / "CAD_POSTGENERATION_INSPECT_REFS_V1.json"
EXPECTED_GROUP_LABELS = {
    "o1.1": "R2_SERVICER_WITHOUT_AXIS_WITNESS",
    "o1.2": "B601_FULL_ARM_FIXED_Q0_INSTALLED",
}
EXPECTED_MOUNT_DATUM_X_MM = 210.405
MOUNT_DATUM_TOLERANCE_MM = 0.01


class PostValidationError(RuntimeError):
    """A fail-closed post-generation validation error."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PostValidationError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, value: object) -> None:
    path.write_bytes(canonical_bytes(value))


def check(checks: list[dict[str, Any]], check_id: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": check_id, "passed": bool(passed), "evidence": evidence})


def cad_skill_root() -> Path:
    explicit = os.environ.get("CAD_SKILL_ROOT", "").strip()
    candidates = [
        Path(explicit) if explicit else None,
        Path("F:/codex_skill/AgentSkills/agents-skills/cad"),
        Path("F:/codex_skill/AgentSkills/codex-skills/cad"),
    ]
    for candidate in candidates:
        if candidate is not None and (candidate / "scripts" / "inspect" / "__main__.py").is_file():
            return candidate.resolve()
    raise PostValidationError("CAD_SKILL_ROOT_NOT_FOUND")


def build_preflight() -> dict[str, Any]:
    inputs = load_json(INPUTS)
    job = load_json(SNAPSHOT_JOB)
    expected = inputs["expected_candidate"]
    checks: list[dict[str, Any]] = []

    expected_output = (WORKSPACE / Path(expected["output_path"])).resolve()
    check(checks, "PF01_EXPLICIT_CANDIDATE_OUTPUT", expected_output == OUTPUT_STEP.resolve(), str(expected_output))
    check(checks, "PF02_EXPECTED_SOLIDS_399", int(expected["expected_solid_count"]) == 399, expected["expected_solid_count"])
    check(checks, "PF03_EXPECTED_GROUPS_2", int(expected["expected_group_count"]) == 2, expected["expected_group_count"])

    snapshot_input = Path(str(job.get("input", ""))).resolve()
    check(checks, "PF04_SNAPSHOT_TARGETS_CANDIDATE", snapshot_input == OUTPUT_STEP.resolve(), str(snapshot_input))
    outputs = job.get("outputs") if isinstance(job.get("outputs"), list) else []
    output_paths = [str(row.get("path", "")) for row in outputs if isinstance(row, dict)]
    check(checks, "PF05_FOUR_UNIQUE_SNAPSHOT_OUTPUTS", len(outputs) == 4 and len(set(output_paths)) == 4, output_paths)
    cameras = [row.get("camera") for row in outputs if isinstance(row, dict)]
    check(
        checks,
        "PF06_REQUIRED_VIEW_PACKET",
        len(cameras) == 4 and cameras[0] == "iso" and isinstance(cameras[1], dict) and cameras[2:] == ["top", "front"],
        cameras,
    )
    check(
        checks,
        "PF07_NO_OLD_MASTER_SNAPSHOT_NAMES",
        all("r2_master_" not in Path(path).name.lower() for path in output_paths),
        output_paths,
    )
    check(checks, "PF08_GENERATOR_PRESENT", GENERATOR.is_file(), str(GENERATOR))
    check(checks, "PF09_GUARDED_WRAPPER_PRESENT", WRAPPER.is_file(), str(WRAPPER))
    skill_root = cad_skill_root()
    check(checks, "PF10_STANDARD_INSPECT_PRESENT", (skill_root / "scripts" / "inspect" / "__main__.py").is_file(), str(skill_root))
    check(checks, "PF11_STANDARD_SNAPSHOT_PRESENT", (skill_root / "scripts" / "snapshot" / "__main__.py").is_file(), str(skill_root))

    failed = [row["id"] for row in checks if not row["passed"]]
    source_paths = {
        "inputs": INPUTS,
        "cad_brief": PACKAGE / "CAD_BRIEF_R2_INTEGRATED_C01_V1.md",
        "generator": GENERATOR,
        "v1_wrapper": WRAPPER,
        "v2_wrapper": PACKAGE / "execute_integrated_candidate_v2.py",
        "postvalidator": Path(__file__).resolve(),
        "candidate_snapshot_job": SNAPSHOT_JOB,
        "postvalidator_tests": PACKAGE / "tests" / "test_postvalidate_integrated_candidate_v1.py",
        "v2_wrapper_tests": PACKAGE / "tests" / "test_execute_integrated_candidate_v2.py",
    }
    return {
        "schema": "CAD_POSTGENERATION_VALIDATOR_PREFLIGHT_V1",
        "generated_utc": "DETERMINISTIC_SOURCE_ONLY_PREFLIGHT_NO_WALLCLOCK",
        "authority": "POSTGENERATION_VALIDATION_PREPARATION_ONLY__NO_CAD_GENERATION_OR_GEOMETRY_CREDIT",
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "source_pins": {
            key: {"path": path.relative_to(PACKAGE).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for key, path in source_paths.items()
        },
        "candidate_artifact_present": OUTPUT_STEP.is_file(),
        "geometry_validated": False,
        "snapshot_executed": False,
        "memory_gate_applicable": False,
        "memory_gate_passed": False,
        "owner_override_used": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "POSTGENERATION_VALIDATOR_READY__CANDIDATE_ARTIFACT_ABSENT_OR_UNVALIDATED__NO_GEOMETRY_CREDIT"
            if not failed
            else "POSTGENERATION_VALIDATOR_PREFLIGHT_FAIL__NO_GEOMETRY_CREDIT"
        ),
    }


def validate_chain_payload(
    chain: dict[str, Any],
    *,
    run_digest: str,
    execution_receipt_bytes: int,
    execution_receipt_sha256: str,
    authority_receipt_bytes: int,
    authority_receipt_sha256: str,
    memory_gate_passed: bool,
    owner_override_used: bool,
    available_physical_memory_gib: float | None,
    step_bytes: int,
    step_sha256: str,
    glb_bytes: int,
    glb_sha256: str,
) -> bool:
    try:
        return (
            chain["schema"] == "R2_INTEGRATED_CANDIDATE_EXECUTION_CHAIN_RECEIPT_V2"
            and str(chain["run_id_sha256"]).upper() == run_digest
            and chain["v1_execution_receipt"]["path"] == f"{run_digest}.json"
            and int(chain["v1_execution_receipt"]["bytes"]) == execution_receipt_bytes
            and str(chain["v1_execution_receipt"]["sha256"]).upper() == execution_receipt_sha256
            and chain["authority_receipt"]["path"] == f"{run_digest}.json"
            and int(chain["authority_receipt"]["bytes"]) == authority_receipt_bytes
            and str(chain["authority_receipt"]["sha256"]).upper() == authority_receipt_sha256
            and chain["wrappers"]["v1"]["path"] == WRAPPER.name
            and int(chain["wrappers"]["v1"]["bytes"]) == WRAPPER.stat().st_size
            and str(chain["wrappers"]["v1"]["sha256"]).upper() == sha256(WRAPPER)
            and chain["wrappers"]["v2"]["path"] == WRAPPER_V2.name
            and int(chain["wrappers"]["v2"]["bytes"]) == WRAPPER_V2.stat().st_size
            and str(chain["wrappers"]["v2"]["sha256"]).upper() == sha256(WRAPPER_V2)
            and chain["outputs"]["step"]["path"] == OUTPUT_STEP.name
            and int(chain["outputs"]["step"]["bytes"]) == step_bytes
            and str(chain["outputs"]["step"]["sha256"]).upper() == step_sha256
            and chain["outputs"]["glb_topology"]["path"] == OUTPUT_GLB.name
            and int(chain["outputs"]["glb_topology"]["bytes"]) == glb_bytes
            and str(chain["outputs"]["glb_topology"]["sha256"]).upper() == glb_sha256
            and chain["authority_summary"]["memory_gate_passed"] is memory_gate_passed
            and chain["authority_summary"]["owner_override_used"] is owner_override_used
            and chain["authority_summary"]["available_physical_memory_gib"] == available_physical_memory_gib
            and chain["postgeneration_validation_required"] is True
            and chain["snapshot_review_required"] is True
            and chain["next_stage_authorized"] is False
            and chain["release_credit"] is False
            and chain["claim_limit"]
            == "CHAIN_OF_CUSTODY_ONLY__NO_GEOMETRY_M01_CONTACT_DYNAMICS_OR_RELEASE_CREDIT"
            and chain["verdict"]
            == "INTEGRATED_CANDIDATE_EXECUTION_CHAIN_BOUND__POSTGEN_VALIDATION_AND_SNAPSHOT_HOLD"
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def validate_authority_payload(
    authority: dict[str, Any], *, run_digest: str, inputs: dict[str, Any]
) -> bool:
    try:
        run_id = str(authority["run_id"])
        if hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper() != run_digest:
            return False
        if (
            authority["schema"] != "R2_INTEGRATED_CANDIDATE_PREIMPORT_AUTHORITY_V1"
            or str(authority["run_id_sha256"]).upper() != run_digest
            or authority["input_contract"]["path"] != INPUTS.name
            or str(authority["input_contract"]["sha256"]).upper() != sha256(INPUTS)
            or authority["claim_limit"] != inputs["scope"]
            or float(authority["memory_gate_gib"]) != 6.0
        ):
            return False

        source_pins = authority["pinned_sources"]
        if set(source_pins) != set(inputs["sources"]):
            return False
        for key, declared in inputs["sources"].items():
            source_path = (WORKSPACE / Path(declared["path"])).resolve()
            pinned = source_pins[key]
            if (
                not source_path.is_file()
                or pinned["path"] != declared["path"]
                or int(pinned["bytes"]) != int(declared["bytes"])
                or int(pinned["bytes"]) != source_path.stat().st_size
                or str(pinned["sha256"]).upper() != str(declared["sha256"]).upper()
                or str(pinned["sha256"]).upper() != sha256(source_path)
            ):
                return False

        available = authority["available_physical_memory_gib"]
        passed = authority["memory_gate_passed"] is True
        override_used = authority["owner_override_used"] is True
        if passed:
            return (
                isinstance(available, (int, float))
                and math.isfinite(float(available))
                and float(available) >= 6.0
                and not override_used
                and authority["owner_override"] is None
            )

        override = authority["owner_override"]
        if not override_used or not isinstance(override, dict):
            return False
        override_id = str(override["owner_override_id"])
        validity = float(override["validity_seconds"])
        issued_text = str(override["issued_utc"])
        expires_text = str(override["expires_utc"])
        authorized_text = str(authority["authorized_utc"])
        issued = datetime.fromisoformat(issued_text[:-1] + "+00:00" if issued_text.endswith("Z") else issued_text)
        expires = datetime.fromisoformat(expires_text[:-1] + "+00:00" if expires_text.endswith("Z") else expires_text)
        authorized = datetime.fromisoformat(authorized_text[:-1] + "+00:00" if authorized_text.endswith("Z") else authorized_text)
        explicit_utc = all(
            value.tzinfo is not None and value.utcoffset() == timezone.utc.utcoffset(value)
            for value in (issued, expires, authorized)
        )
        return (
            (available is None or (math.isfinite(float(available)) and float(available) < 6.0))
            and explicit_utc
            and 0.0 < validity <= 7200.0
            and abs((expires - issued).total_seconds() - validity) <= 1.0e-9
            and issued <= authorized < expires
            and override["risk_ack"] == "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK"
            and str(override["owner_override_id_sha256"]).upper()
            == hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper()
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def validate_execution_payload(
    execution: dict[str, Any], *, run_digest: str
) -> bool:
    try:
        run_id = str(execution["run_id"])
        return (
            execution["schema"] == "R2_INTEGRATED_CANDIDATE_EXECUTION_RECEIPT_V1"
            and hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper() == run_digest
            and str(execution["run_id_sha256"]).upper() == run_digest
            and execution["standard_cad_tool"] == "cad/scripts/step"
            and execution["generator"]["path"] == GENERATOR.name
            and str(execution["generator"]["sha256"]).upper() == sha256(GENERATOR)
            and execution["outputs"]["step"]["path"] == OUTPUT_STEP.name
            and int(execution["outputs"]["step"]["bytes"]) == OUTPUT_STEP.stat().st_size
            and str(execution["outputs"]["step"]["sha256"]).upper() == sha256(OUTPUT_STEP)
            and execution["outputs"]["glb_topology"]["path"] == OUTPUT_GLB.name
            and int(execution["outputs"]["glb_topology"]["bytes"]) == OUTPUT_GLB.stat().st_size
            and str(execution["outputs"]["glb_topology"]["sha256"]).upper() == sha256(OUTPUT_GLB)
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _matching_execution_receipt() -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    if not OUTPUT_STEP.is_file():
        raise PostValidationError("CANDIDATE_STEP_MISSING")
    if not OUTPUT_GLB.is_file():
        raise PostValidationError("CANDIDATE_GLB_TOPOLOGY_MISSING")
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(EXECUTION_RECEIPTS.glob("*.json")) if EXECUTION_RECEIPTS.is_dir() else []:
        try:
            receipt = load_json(path)
            step = receipt["outputs"]["step"]
            glb = receipt["outputs"]["glb_topology"]
            if (
                str(step.get("sha256", "")).upper() == sha256(OUTPUT_STEP)
                and int(step.get("bytes", -1)) == OUTPUT_STEP.stat().st_size
                and str(glb.get("sha256", "")).upper() == sha256(OUTPUT_GLB)
                and int(glb.get("bytes", -1)) == OUTPUT_GLB.stat().st_size
            ):
                matches.append((path, receipt))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError, PostValidationError):
            continue
    if len(matches) != 1:
        raise PostValidationError(f"MATCHING_EXECUTION_RECEIPT_COUNT_{len(matches)}_EXPECTED_1")
    execution_path, execution = matches[0]
    run_digest = str(execution.get("run_id_sha256", "")).upper()
    failure_path = FAILURE_RECEIPTS / f"{run_digest}.json"
    authority_path = PACKAGE / "candidate_authority_receipts" / f"{run_digest}.json"
    chain_path = CHAIN_RECEIPTS / f"{run_digest}.json"
    if failure_path.is_file():
        raise PostValidationError("V2_EXECUTION_FAILURE_RECEIPT_PRESENT__OWNER_DISPOSITION_REQUIRED")
    if not authority_path.is_file():
        raise PostValidationError("MATCHING_AUTHORITY_RECEIPT_MISSING")
    if not chain_path.is_file():
        raise PostValidationError("V2_EXECUTION_CHAIN_RECEIPT_MISSING")
    authority = load_json(authority_path)
    chain = load_json(chain_path)
    inputs = load_json(INPUTS)
    if ACTIVE_LOCK.is_file():
        raise PostValidationError("ACTIVE_WRITER_LOCK_STILL_PRESENT")
    if not validate_execution_payload(execution, run_digest=run_digest):
        raise PostValidationError("V1_EXECUTION_RECEIPT_MISMATCH")
    if not validate_authority_payload(authority, run_digest=run_digest, inputs=inputs):
        raise PostValidationError("PREIMPORT_AUTHORITY_RECEIPT_MISMATCH")
    if not validate_chain_payload(
        chain,
        run_digest=run_digest,
        execution_receipt_bytes=execution_path.stat().st_size,
        execution_receipt_sha256=sha256(execution_path),
        authority_receipt_bytes=authority_path.stat().st_size,
        authority_receipt_sha256=sha256(authority_path),
        memory_gate_passed=authority["memory_gate_passed"],
        owner_override_used=authority["owner_override_used"],
        available_physical_memory_gib=authority["available_physical_memory_gib"],
        step_bytes=OUTPUT_STEP.stat().st_size,
        step_sha256=sha256(OUTPUT_STEP),
        glb_bytes=OUTPUT_GLB.stat().st_size,
        glb_sha256=sha256(OUTPUT_GLB),
    ):
        raise PostValidationError("V2_EXECUTION_CHAIN_RECEIPT_MISMATCH")
    return execution_path, execution, chain_path, chain


def _run_inspect_command(extra_arguments: list[str]) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "scripts.inspect",
        "refs",
        OUTPUT_STEP.as_posix(),
        *extra_arguments,
        "--format",
        "json",
    ]
    completed = subprocess.run(
        command,
        cwd=cad_skill_root(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise PostValidationError(f"CAD_INSPECT_FAILED_CODE_{completed.returncode}:{completed.stderr[-1000:]}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PostValidationError("CAD_INSPECT_STDOUT_NOT_JSON") from exc
    if not isinstance(payload, dict):
        raise PostValidationError("CAD_INSPECT_ROOT_NOT_OBJECT")
    return payload


def _run_inspect() -> dict[str, Any]:
    topology = _run_inspect_command(["--topology"])
    tokens = topology.get("tokens") if isinstance(topology.get("tokens"), list) else []
    topology_row = tokens[0].get("topology", {}) if len(tokens) == 1 and isinstance(tokens[0], dict) else {}
    shape_selectors = topology_row.get("shapes") if isinstance(topology_row, dict) else None
    if not isinstance(shape_selectors, list) or not all(isinstance(row, str) for row in shape_selectors):
        raise PostValidationError("CAD_INSPECT_TOPOLOGY_SHAPE_LIST_MISSING")
    selector_lines = ["#o1.1", "#o1.2", *(f"#{selector}" for selector in shape_selectors)]
    with tempfile.TemporaryDirectory(prefix="r2_cad_inspect_") as temporary_directory:
        selector_path = Path(temporary_directory) / "selectors.txt"
        selector_path.write_text("\n".join(selector_lines) + "\n", encoding="utf-8")
        selections = _run_inspect_command(
            [
                "--input-file",
                selector_path.as_posix(),
                "--detail",
                "--facts",
                "--positioning",
            ]
        )
    return {
        "schema": "CAD_POSTGENERATION_INSPECT_BUNDLE_V2",
        "topology_inspect": topology,
        "selector_inspect": selections,
    }


def validate_inspect_payload(payload: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    topology_payload = payload.get("topology_inspect") if isinstance(payload.get("topology_inspect"), dict) else {}
    selector_payload = payload.get("selector_inspect") if isinstance(payload.get("selector_inspect"), dict) else {}
    topology_tokens = topology_payload.get("tokens") if isinstance(topology_payload.get("tokens"), list) else []
    tokens = selector_payload.get("tokens") if isinstance(selector_payload.get("tokens"), list) else []
    root = topology_tokens[0] if len(topology_tokens) == 1 and isinstance(topology_tokens[0], dict) else {}
    summary = root.get("summary") if isinstance(root.get("summary"), dict) else {}
    topology_errors = topology_payload.get("errors") if isinstance(topology_payload.get("errors"), list) else ["INVALID_TOPOLOGY_ERRORS_FIELD"]
    selector_errors = selector_payload.get("errors") if isinstance(selector_payload.get("errors"), list) else ["INVALID_SELECTOR_ERRORS_FIELD"]
    expected_solids = int(expected["expected_solid_count"])
    expected_groups = int(expected["expected_group_count"])
    occurrence_count = int(summary.get("occurrenceCount", -1))
    leaf_count = int(summary.get("leafOccurrenceCount", -1))
    shape_count = int(summary.get("shapeCount", -1))
    derived_groups = occurrence_count - leaf_count - 1

    check(
        checks,
        "PG01_INSPECT_OK",
        topology_payload.get("ok") is True
        and selector_payload.get("ok") is True
        and not topology_errors
        and not selector_errors,
        {
            "topology_ok": topology_payload.get("ok"),
            "selector_ok": selector_payload.get("ok"),
            "topology_errors": topology_errors,
            "selector_errors": selector_errors,
        },
    )
    check(checks, "PG02_ASSEMBLY_KIND", summary.get("kind") == "assembly", summary.get("kind"))
    check(checks, "PG03_SHAPE_COUNT", shape_count == expected_solids, shape_count)
    check(checks, "PG04_LEAF_OCCURRENCE_COUNT", leaf_count == expected_solids, leaf_count)
    check(checks, "PG05_DERIVED_GROUP_COUNT", derived_groups == expected_groups, {"derived": derived_groups, "occurrences": occurrence_count})

    bounds = summary.get("bounds") if isinstance(summary.get("bounds"), dict) else {}
    actual_min = bounds.get("min") if isinstance(bounds.get("min"), list) else []
    actual_max = bounds.get("max") if isinstance(bounds.get("max"), list) else []
    target = expected["expected_bounds_mm"]
    tolerance = float(target["absolute_tolerance_mm"])
    bounds_ok = len(actual_min) == 3 and len(actual_max) == 3
    if bounds_ok:
        bounds_ok = all(
            abs(float(actual) - float(wanted)) <= tolerance
            for actual_row, wanted_row in ((actual_min, target["min"]), (actual_max, target["max"]))
            for actual, wanted in zip(actual_row, wanted_row, strict=True)
        )
    check(
        checks,
        "PG06_BOUNDS_MM",
        bounds_ok,
        {"actual": {"min": actual_min, "max": actual_max}, "expected": target, "unit": "mm"},
    )
    selections = [
        selection
        for token in tokens
        if isinstance(token, dict) and isinstance(token.get("selections"), list)
        for selection in token["selections"]
        if isinstance(selection, dict)
    ]
    selection_errors = [row for row in selections if row.get("error") or row.get("status") != "resolved"]
    group_selections = [row for row in selections if row.get("selectorType") == "occurrence"]
    shape_selections = [row for row in selections if row.get("selectorType") == "shape"]
    selector_to_selection = {str(row.get("normalizedSelector", "")): row for row in group_selections}
    labels_ok = set(selector_to_selection) == set(EXPECTED_GROUP_LABELS) and all(
        selector_to_selection[selector].get("summary") == label
        for selector, label in EXPECTED_GROUP_LABELS.items()
    )
    check(
        checks,
        "PG07_TWO_NAMED_GROUP_SELECTORS_RESOLVE",
        len(group_selections) == 2 and not selection_errors and labels_ok,
        group_selections,
    )
    spacecraft_bbox = selector_to_selection.get("o1.1", {}).get("positioning", {}).get("bbox", {})
    arm_bbox = selector_to_selection.get("o1.2", {}).get("positioning", {}).get("bbox", {})
    spacecraft_max = spacecraft_bbox.get("max") if isinstance(spacecraft_bbox, dict) else None
    arm_min = arm_bbox.get("min") if isinstance(arm_bbox, dict) else None
    datum_ok = (
        isinstance(spacecraft_max, list)
        and isinstance(arm_min, list)
        and len(spacecraft_max) == 3
        and len(arm_min) == 3
        and abs(float(spacecraft_max[0]) - EXPECTED_MOUNT_DATUM_X_MM) <= MOUNT_DATUM_TOLERANCE_MM
        and abs(float(arm_min[0]) - EXPECTED_MOUNT_DATUM_X_MM) <= MOUNT_DATUM_TOLERANCE_MM
        and abs(float(spacecraft_max[0]) - float(arm_min[0])) <= MOUNT_DATUM_TOLERANCE_MM
    )
    check(
        checks,
        "PG08_M3R_TO_B601_MOUNT_DATUM_X_MM",
        datum_ok,
        {
            "spacecraft_group_max_x_mm": spacecraft_max[0] if isinstance(spacecraft_max, list) and spacecraft_max else None,
            "arm_group_min_x_mm": arm_min[0] if isinstance(arm_min, list) and arm_min else None,
            "expected_x_mm": EXPECTED_MOUNT_DATUM_X_MM,
            "absolute_tolerance_mm": MOUNT_DATUM_TOLERANCE_MM,
        },
    )

    topology = root.get("topology") if isinstance(root.get("topology"), dict) else {}
    topology_occurrences = topology.get("occurrences") if isinstance(topology.get("occurrences"), list) else []
    topology_shapes = topology.get("shapes") if isinstance(topology.get("shapes"), list) else []
    display_shape_selectors = [str(row.get("displaySelector", "")) for row in shape_selections]
    shape_details = [row.get("detail") if isinstance(row.get("detail"), dict) else {} for row in shape_selections]
    positive_solids = all(
        detail.get("kind") == "solid"
        and isinstance(detail.get("volume"), (int, float))
        and math.isfinite(float(detail["volume"]))
        and float(detail["volume"]) > 0.0
        for detail in shape_details
    )
    check(
        checks,
        "PG09_ALL_399_SHAPES_ARE_POSITIVE_VOLUME_SOLIDS",
        len(shape_selections) == expected_solids
        and len(set(display_shape_selectors)) == expected_solids
        and set(display_shape_selectors) == set(str(row) for row in topology_shapes)
        and positive_solids,
        {
            "shape_selections": len(shape_selections),
            "unique_shape_selectors": len(set(display_shape_selectors)),
            "topology_shape_selectors": len(topology_shapes),
            "all_kind_solid_and_positive_volume": positive_solids,
        },
    )

    group_details = {
        selector: row.get("detail") if isinstance(row.get("detail"), dict) else {}
        for selector, row in selector_to_selection.items()
    }
    expected_group_leaf_counts = expected.get("expected_group_leaf_counts", {})
    group_parent_ids = [str(detail.get("parentId", "")) for detail in group_details.values()]
    group_descendants = {
        selector: [str(value) for value in detail.get("descendantOccurrenceIds", [])]
        if isinstance(detail.get("descendantOccurrenceIds"), list)
        else []
        for selector, detail in group_details.items()
    }
    flattened_descendants = [value for rows in group_descendants.values() for value in rows]
    shape_occurrence_ids = [str(detail.get("occurrenceId", "")) for detail in shape_details]
    topology_occurrence_ids = [str(value) for value in topology_occurrences]
    common_parent = group_parent_ids[0] if group_parent_ids else ""
    expected_occurrence_ids = {
        common_parent,
        *EXPECTED_GROUP_LABELS,
        *flattened_descendants,
    }
    group_structure_ok = (
        set(group_details) == set(EXPECTED_GROUP_LABELS)
        and len(set(group_parent_ids)) == 1
        and bool(group_parent_ids[0])
        and all(
            int(group_details[selector].get("childCount", -1)) == int(expected_group_leaf_counts.get(selector, -2))
            and len(group_descendants[selector]) == int(expected_group_leaf_counts.get(selector, -2))
            for selector in EXPECTED_GROUP_LABELS
        )
        and len(flattened_descendants) == expected_solids
        and len(set(flattened_descendants)) == expected_solids
        and len(shape_occurrence_ids) == expected_solids
        and len(set(shape_occurrence_ids)) == expected_solids
        and set(shape_occurrence_ids) == set(flattened_descendants)
        and len(topology_occurrences) == occurrence_count
        and len(set(topology_occurrence_ids)) == occurrence_count
        and set(topology_occurrence_ids) == expected_occurrence_ids
        and len([value for value in topology_occurrence_ids if "." not in value]) == 1
        and common_parent in topology_occurrence_ids
    )
    check(
        checks,
        "PG10_SINGLE_ROOT_TWO_DIRECT_GROUPS_ONE_SOLID_PER_LEAF",
        group_structure_ok,
        {
            "group_parent_ids": group_parent_ids,
            "group_child_counts": {key: value.get("childCount") for key, value in group_details.items()},
            "group_descendant_counts": {key: len(value) for key, value in group_descendants.items()},
            "unique_shape_occurrences": len(set(shape_occurrence_ids)),
            "topology_occurrences": len(topology_occurrences),
        },
    )
    return checks


def build_postgeneration() -> dict[str, Any]:
    preflight = build_preflight()
    if preflight["summary"]["failed"]:
        raise PostValidationError("POSTGENERATION_PREFLIGHT_NOT_PASS")
    receipt_path, execution, chain_path, chain = _matching_execution_receipt()
    inspect = _run_inspect()
    write_json(INSPECT_RECEIPT, inspect)
    inputs = load_json(INPUTS)
    expected = dict(inputs["expected_candidate"])
    expected["expected_group_leaf_counts"] = {
        "o1.1": len(inputs["r2_master_filter_contract"]["retained_solid_indices"]),
        "o1.2": int(inputs["sources"]["b601_fixed_q0_reference"]["expected_solid_count"]),
    }
    checks = validate_inspect_payload(inspect, expected)
    check(checks, "PG11_STEP_HASH_MATCHES_EXECUTION_RECEIPT", execution["outputs"]["step"]["sha256"] == sha256(OUTPUT_STEP), sha256(OUTPUT_STEP))
    check(checks, "PG12_GLB_HASH_MATCHES_EXECUTION_RECEIPT", execution["outputs"]["glb_topology"]["sha256"] == sha256(OUTPUT_GLB), sha256(OUTPUT_GLB))
    check(checks, "PG13_GENERATOR_PINNED", execution.get("generator", {}).get("sha256") == sha256(GENERATOR), sha256(GENERATOR))
    check(checks, "PG14_INPUT_CONTRACT_AND_PREIMPORT_AUTHORITY_PINNED", validate_authority_payload(load_json(PACKAGE / "candidate_authority_receipts" / f"{execution['run_id_sha256']}.json"), run_digest=str(execution["run_id_sha256"]).upper(), inputs=inputs), sha256(INPUTS))
    check(checks, "PG15_V2_CHAIN_REQUIRES_POSTVALIDATION_AND_SNAPSHOT", chain["postgeneration_validation_required"] is True and chain["snapshot_review_required"] is True, chain_path.name)
    failed = [row["id"] for row in checks if not row["passed"]]
    return {
        "schema": "CAD_POSTGENERATION_VALIDATION_V1",
        "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority": "RESEARCH_CANDIDATE_GEOMETRY_VALIDATION_ONLY",
        "execution_receipt": {"path": receipt_path.name, "sha256": sha256(receipt_path)},
        "execution_chain_receipt": {"path": chain_path.name, "sha256": sha256(chain_path)},
        "artifacts": {
            "step": {"path": OUTPUT_STEP.name, "bytes": OUTPUT_STEP.stat().st_size, "sha256": sha256(OUTPUT_STEP)},
            "glb_topology": {"path": OUTPUT_GLB.name, "bytes": OUTPUT_GLB.stat().st_size, "sha256": sha256(OUTPUT_GLB)},
            "inspect_refs": {"path": INSPECT_RECEIPT.name, "sha256": sha256(INSPECT_RECEIPT)},
            "snapshot_job": {"path": SNAPSHOT_JOB.name, "sha256": sha256(SNAPSHOT_JOB)},
        },
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "geometry_validated": not failed,
        "snapshot_executed": False,
        "snapshot_review_required": True,
        "m01_authorized": False,
        "collision_authority": False,
        "contact_authority": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": (
            "INTEGRATED_399_SOLID_CANDIDATE_POSTGEN_GEOMETRY_PASS__SNAPSHOT_REVIEW_M01_AND_RELEASE_HOLD"
            if not failed
            else "INTEGRATED_CANDIDATE_POSTGEN_GEOMETRY_FAIL__NO_DOWNSTREAM_CREDIT"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--check-preflight", action="store_true")
    mode.add_argument("--postgenerate", action="store_true")
    args = parser.parse_args()

    if args.preflight:
        payload = build_preflight()
        write_json(PREFLIGHT_RECEIPT, payload)
        print(payload["verdict"])
        print(f"checks={payload['summary']['passed']}/{payload['summary']['total']}")
        return 0 if not payload["summary"]["failed"] else 1
    if args.check_preflight:
        expected = canonical_bytes(build_preflight())
        if not PREFLIGHT_RECEIPT.is_file() or PREFLIGHT_RECEIPT.read_bytes() != expected:
            print("FAIL_PREFLIGHT_RECEIPT_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 1
        print("PASS_PREFLIGHT_BYTE_IDENTICAL")
        return 0

    try:
        payload = build_postgeneration()
    except PostValidationError as exc:
        print(f"POSTGENERATION_VALIDATION_BLOCKED:{exc}")
        return 2
    write_json(POSTGEN_RECEIPT, payload)
    print(payload["verdict"])
    print(f"checks={payload['summary']['passed']}/{payload['summary']['total']}")
    return 0 if not payload["summary"]["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
