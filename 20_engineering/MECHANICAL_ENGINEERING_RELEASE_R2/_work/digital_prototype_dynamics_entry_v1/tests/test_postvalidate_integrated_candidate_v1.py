from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE = PACKAGE / "postvalidate_integrated_candidate_v1.py"
SPEC = importlib.util.spec_from_file_location("postvalidator", SOURCE)
assert SPEC and SPEC.loader
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def expected_contract() -> dict:
    return {
        "expected_solid_count": 399,
        "expected_group_count": 2,
        "expected_group_leaf_counts": {"o1.1": 11, "o1.2": 388},
        "expected_bounds_mm": {
            "min": [-230.25, -313.15, -274.86072587989787],
            "max": [488.533214, 313.15, 285.63229786565915],
            "absolute_tolerance_mm": 0.1,
        },
    }


def inspect_payload(
    *,
    shapes: int = 399,
    leaves: int = 399,
    occurrences: int = 402,
    shape_kind: str = "solid",
    shape_volume: float = 1.0,
) -> dict:
    summary = {
        "kind": "assembly",
        "occurrenceCount": occurrences,
        "leafOccurrenceCount": leaves,
        "shapeCount": shapes,
        "bounds": {
            "min": [-230.25, -313.15, -274.86072587989787],
            "max": [488.533214, 313.15, 285.63229786565915],
        },
    }
    group_1_leaves = [f"o1.1.{index}" for index in range(1, min(shapes, 11) + 1)]
    group_2_count = max(0, shapes - len(group_1_leaves))
    group_2_leaves = [f"o1.2.{index}" for index in range(1, group_2_count + 1)]
    leaf_occurrences = group_1_leaves + group_2_leaves
    shape_selectors = [f"{occurrence}.s1" for occurrence in leaf_occurrences]
    group_tokens = [
        {
            "summary": summary,
            "selections": [{
                "status": "resolved",
                "selectorType": "occurrence",
                "normalizedSelector": "o1.1",
                "displaySelector": "o1.1",
                "summary": "R2_SERVICER_WITHOUT_AXIS_WITNESS",
                "detail": {
                    "parentId": "o1",
                    "childCount": len(group_1_leaves),
                    "descendantOccurrenceIds": group_1_leaves,
                },
                "positioning": {"bbox": {"min": [-230.25, -313.15, -112.0], "max": [210.405, 313.15, 112.0]}},
            }],
        },
        {
            "summary": summary,
            "selections": [{
                "status": "resolved",
                "selectorType": "occurrence",
                "normalizedSelector": "o1.2",
                "displaySelector": "o1.2",
                "summary": "B601_FULL_ARM_FIXED_Q0_INSTALLED",
                "detail": {
                    "parentId": "o1",
                    "childCount": len(group_2_leaves),
                    "descendantOccurrenceIds": group_2_leaves,
                },
                "positioning": {"bbox": {"min": [210.405, -200.0, -274.86072587989787], "max": [488.533214, 200.0, 285.63229786565915]}},
            }],
        },
    ]
    shape_tokens = [
        {
            "summary": summary,
            "selections": [{
                "status": "resolved",
                "selectorType": "shape",
                "normalizedSelector": selector,
                "displaySelector": selector,
                "summary": f"{shape_kind} volume={shape_volume}",
                "detail": {
                    "occurrenceId": occurrence,
                    "kind": shape_kind,
                    "volume": shape_volume,
                },
            }],
        }
        for selector, occurrence in zip(shape_selectors, leaf_occurrences, strict=True)
    ]
    return {
        "schema": "CAD_POSTGENERATION_INSPECT_BUNDLE_V2",
        "topology_inspect": {
            "ok": True,
            "errors": [],
            "tokens": [{
                "summary": summary,
                "topology": {
                    "occurrences": ["o1", "o1.1", "o1.2", *leaf_occurrences],
                    "shapes": shape_selectors,
                },
            }],
        },
        "selector_inspect": {
            "ok": True,
            "errors": [],
            "tokens": [*group_tokens, *shape_tokens],
        },
    }


def test_preflight_targets_integrated_candidate_and_four_views() -> None:
    payload = mod.build_preflight()
    assert payload["summary"]["failed"] == []
    assert payload["summary"]["passed"] == payload["summary"]["total"] == 11
    assert len(payload["source_pins"]) == 9
    assert all(len(record["sha256"]) == 64 and record["bytes"] > 0 for record in payload["source_pins"].values())
    assert payload["geometry_validated"] is False
    assert payload["next_stage_authorized"] is False


def test_valid_inspect_payload_passes_all_checks() -> None:
    checks = mod.validate_inspect_payload(inspect_payload(), expected_contract())
    assert len(checks) == 10
    assert all(row["passed"] for row in checks)


def test_solid_count_mismatch_fails_closed() -> None:
    checks = mod.validate_inspect_payload(inspect_payload(shapes=398), expected_contract())
    assert next(row for row in checks if row["id"] == "PG03_SHAPE_COUNT")["passed"] is False


def test_group_count_mismatch_fails_closed() -> None:
    checks = mod.validate_inspect_payload(inspect_payload(occurrences=401), expected_contract())
    assert next(row for row in checks if row["id"] == "PG05_DERIVED_GROUP_COUNT")["passed"] is False


def test_bounds_mismatch_fails_closed() -> None:
    payload = inspect_payload()
    payload["topology_inspect"]["tokens"][0]["summary"]["bounds"]["max"][0] += 0.101
    checks = mod.validate_inspect_payload(payload, expected_contract())
    assert next(row for row in checks if row["id"] == "PG06_BOUNDS_MM")["passed"] is False


def test_group_label_mismatch_fails_closed() -> None:
    payload = inspect_payload()
    payload["selector_inspect"]["tokens"][1]["selections"][0]["summary"] = "WRONG_ARM_GROUP"
    checks = mod.validate_inspect_payload(payload, expected_contract())
    assert next(row for row in checks if row["id"] == "PG07_TWO_NAMED_GROUP_SELECTORS_RESOLVE")["passed"] is False


def test_mount_datum_mismatch_fails_closed() -> None:
    payload = inspect_payload()
    payload["selector_inspect"]["tokens"][1]["selections"][0]["positioning"]["bbox"]["min"][0] = 210.416
    checks = mod.validate_inspect_payload(payload, expected_contract())
    assert next(row for row in checks if row["id"] == "PG08_M3R_TO_B601_MOUNT_DATUM_X_MM")["passed"] is False


def test_non_solid_or_zero_volume_shape_fails_closed() -> None:
    payload = inspect_payload(shape_kind="shell", shape_volume=0.0)
    checks = mod.validate_inspect_payload(payload, expected_contract())
    assert next(row for row in checks if row["id"] == "PG09_ALL_399_SHAPES_ARE_POSITIVE_VOLUME_SOLIDS")["passed"] is False


def test_group_parent_or_one_shape_per_leaf_mismatch_fails_closed() -> None:
    payload = inspect_payload()
    payload["selector_inspect"]["tokens"][1]["selections"][0]["detail"]["parentId"] = "o9"
    checks = mod.validate_inspect_payload(payload, expected_contract())
    assert next(row for row in checks if row["id"] == "PG10_SINGLE_ROOT_TWO_DIRECT_GROUPS_ONE_SOLID_PER_LEAF")["passed"] is False
    duplicate_topology = inspect_payload()
    occurrences = duplicate_topology["topology_inspect"]["tokens"][0]["topology"]["occurrences"]
    occurrences[0] = occurrences[-1]
    checks = mod.validate_inspect_payload(duplicate_topology, expected_contract())
    assert next(row for row in checks if row["id"] == "PG10_SINGLE_ROOT_TWO_DIRECT_GROUPS_ONE_SOLID_PER_LEAF")["passed"] is False


def test_missing_generated_step_blocks_before_cad_inspection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "OUTPUT_STEP", tmp_path / "missing.step")
    monkeypatch.setattr(
        mod,
        "build_preflight",
        lambda: {"summary": {"failed": []}},
    )
    inspect_called = False

    def forbidden_inspect() -> dict:
        nonlocal inspect_called
        inspect_called = True
        raise AssertionError("CAD inspect must not run when the candidate is missing")

    monkeypatch.setattr(mod, "_run_inspect", forbidden_inspect)
    with pytest.raises(mod.PostValidationError, match="CANDIDATE_STEP_MISSING"):
        mod.build_postgeneration()
    assert inspect_called is False


def test_same_run_failure_receipt_blocks_even_when_outputs_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = tmp_path / "candidate.step"
    glb = tmp_path / ".candidate.step.glb"
    execution_dir = tmp_path / "execution"
    failure_dir = tmp_path / "failure"
    execution_dir.mkdir()
    failure_dir.mkdir()
    step.write_bytes(b"STEP")
    glb.write_bytes(b"GLB")
    run_digest = "A" * 64
    execution = {
        "run_id_sha256": run_digest,
        "outputs": {
            "step": {"bytes": step.stat().st_size, "sha256": mod.sha256(step)},
            "glb_topology": {"bytes": glb.stat().st_size, "sha256": mod.sha256(glb)},
        },
    }
    (execution_dir / f"{run_digest}.json").write_text(
        mod.json.dumps(execution), encoding="utf-8"
    )
    (failure_dir / f"{run_digest}.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(mod, "OUTPUT_STEP", step)
    monkeypatch.setattr(mod, "OUTPUT_GLB", glb)
    monkeypatch.setattr(mod, "EXECUTION_RECEIPTS", execution_dir)
    monkeypatch.setattr(mod, "FAILURE_RECEIPTS", failure_dir)
    with pytest.raises(
        mod.PostValidationError,
        match="V2_EXECUTION_FAILURE_RECEIPT_PRESENT__OWNER_DISPOSITION_REQUIRED",
    ):
        mod._matching_execution_receipt()


def valid_chain() -> dict:
    return {
        "schema": "R2_INTEGRATED_CANDIDATE_EXECUTION_CHAIN_RECEIPT_V2",
        "run_id_sha256": "A" * 64,
        "v1_execution_receipt": {"path": f"{'A' * 64}.json", "bytes": 101, "sha256": "B" * 64},
        "authority_receipt": {"path": f"{'A' * 64}.json", "bytes": 202, "sha256": "C" * 64},
        "wrappers": {
            "v1": {"path": mod.WRAPPER.name, "bytes": mod.WRAPPER.stat().st_size, "sha256": mod.sha256(mod.WRAPPER)},
            "v2": {"path": mod.WRAPPER_V2.name, "bytes": mod.WRAPPER_V2.stat().st_size, "sha256": mod.sha256(mod.WRAPPER_V2)},
        },
        "outputs": {
            "step": {"path": mod.OUTPUT_STEP.name, "bytes": 303, "sha256": "D" * 64},
            "glb_topology": {"path": mod.OUTPUT_GLB.name, "bytes": 404, "sha256": "E" * 64},
        },
        "authority_summary": {
            "memory_gate_passed": True,
            "owner_override_used": False,
            "available_physical_memory_gib": 6.5,
        },
        "postgeneration_validation_required": True,
        "snapshot_review_required": True,
        "next_stage_authorized": False,
        "release_credit": False,
        "claim_limit": "CHAIN_OF_CUSTODY_ONLY__NO_GEOMETRY_M01_CONTACT_DYNAMICS_OR_RELEASE_CREDIT",
        "verdict": "INTEGRATED_CANDIDATE_EXECUTION_CHAIN_BOUND__POSTGEN_VALIDATION_AND_SNAPSHOT_HOLD",
    }


def test_v2_chain_contract_accepts_exact_binding() -> None:
    assert mod.validate_chain_payload(
        valid_chain(),
        run_digest="A" * 64,
        execution_receipt_bytes=101,
        execution_receipt_sha256="B" * 64,
        authority_receipt_bytes=202,
        authority_receipt_sha256="C" * 64,
        memory_gate_passed=True,
        owner_override_used=False,
        available_physical_memory_gib=6.5,
        step_bytes=303,
        step_sha256="D" * 64,
        glb_bytes=404,
        glb_sha256="E" * 64,
    )


def test_v2_chain_authority_or_release_tamper_fails_closed() -> None:
    chain = valid_chain()
    chain["release_credit"] = True
    assert not mod.validate_chain_payload(
        chain,
        run_digest="A" * 64,
        execution_receipt_bytes=101,
        execution_receipt_sha256="B" * 64,
        authority_receipt_bytes=202,
        authority_receipt_sha256="C" * 64,
        memory_gate_passed=True,
        owner_override_used=False,
        available_physical_memory_gib=6.5,
        step_bytes=303,
        step_sha256="D" * 64,
        glb_bytes=404,
        glb_sha256="E" * 64,
    )
    chain = valid_chain()
    chain["authority_summary"]["memory_gate_passed"] = False
    assert not mod.validate_chain_payload(
        chain,
        run_digest="A" * 64,
        execution_receipt_bytes=101,
        execution_receipt_sha256="B" * 64,
        authority_receipt_bytes=202,
        authority_receipt_sha256="C" * 64,
        memory_gate_passed=True,
        owner_override_used=False,
        available_physical_memory_gib=6.5,
        step_bytes=303,
        step_sha256="D" * 64,
        glb_bytes=404,
        glb_sha256="E" * 64,
    )


def valid_authority(run_id: str) -> tuple[dict, dict]:
    inputs = mod.load_json(mod.INPUTS)
    pins = {
        key: {
            "path": record["path"],
            "bytes": record["bytes"],
            "sha256": record["sha256"],
        }
        for key, record in inputs["sources"].items()
    }
    return inputs, {
        "schema": "R2_INTEGRATED_CANDIDATE_PREIMPORT_AUTHORITY_V1",
        "run_id": run_id,
        "run_id_sha256": mod.hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper(),
        "authorized_utc": "2026-08-27T00:30:00Z",
        "available_physical_memory_gib": 6.5,
        "memory_gate_gib": 6.0,
        "memory_gate_passed": True,
        "owner_override_used": False,
        "owner_override": None,
        "input_contract": {"path": mod.INPUTS.name, "sha256": mod.sha256(mod.INPUTS)},
        "pinned_sources": pins,
        "claim_limit": inputs["scope"],
    }


def test_preimport_authority_binds_input_contract_and_all_current_sources() -> None:
    run_id = "unit-authority-run-0001"
    inputs, authority = valid_authority(run_id)
    digest = mod.hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    assert mod.validate_authority_payload(authority, run_digest=digest, inputs=inputs)
    authority["input_contract"]["sha256"] = "0" * 64
    assert not mod.validate_authority_payload(authority, run_digest=digest, inputs=inputs)


def test_low_memory_authority_requires_exact_single_run_override_window() -> None:
    run_id = "unit-authority-run-0002"
    inputs, authority = valid_authority(run_id)
    digest = mod.hashlib.sha256(run_id.encode("utf-8")).hexdigest().upper()
    override_id = "unit-owner-override-0002"
    authority.update(
        {
            "authorized_utc": "2026-08-27T00:30:00Z",
            "available_physical_memory_gib": 2.5,
            "memory_gate_passed": False,
            "owner_override_used": True,
            "owner_override": {
                "owner_override_id": override_id,
                "owner_override_id_sha256": mod.hashlib.sha256(override_id.encode("utf-8")).hexdigest().upper(),
                "issued_utc": "2026-08-27T00:00:00Z",
                "expires_utc": "2026-08-27T01:00:00Z",
                "validity_seconds": 3600.0,
                "risk_ack": "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK",
            },
        }
    )
    assert mod.validate_authority_payload(authority, run_digest=digest, inputs=inputs)
    authority["owner_override"]["validity_seconds"] = 7200.1
    assert not mod.validate_authority_payload(authority, run_digest=digest, inputs=inputs)
