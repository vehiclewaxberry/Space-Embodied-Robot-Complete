"""Adversarial controls for the source-only current-system intake boundary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable
from unittest.mock import patch

from .evaluator import evaluate_snapshot
from .freeze_support import (
    FROZEN_PACKAGE_FILE_ALLOWLIST,
    canonical_json_bytes,
    validate_frozen_package_file_set,
)
from .schema import (
    PROMOTION_RECEIPT_ARTIFACT_ID,
    route_c_auto_accept,
    validate_intake_document,
    validate_mass_mode,
    validate_promotion_receipt,
    validate_promotion_sequence,
)
from .strict_io import (
    IntakeError,
    SourceSnapshot,
    deep_freeze,
    load_default_snapshot,
    resolve_bound_path,
    sha256_bytes,
    strict_json_bytes,
    thaw,
    validate_project_relative_path,
    verify_payload,
)


def _rejected(action: Callable[[], Any], classification: str | None = None) -> bool:
    try:
        action()
    except IntakeError as exc:
        return classification is None or exc.classification == classification
    except (KeyError, TypeError, ValueError, AttributeError):
        return classification is None
    return False


def _receipt(issued: str, expires: str, nonce: str = "NONCE_CURRENT_SYS_0001") -> dict[str, Any]:
    return {
        "schema": "CURRENT_SYSTEM_PROMOTION_AUTHORITY_RECEIPT_V1",
        "artifact_id": PROMOTION_RECEIPT_ARTIFACT_ID,
        "action_digest": "A" * 64,
        "context_digest": "B" * 64,
        "issued_at_utc": issued,
        "expires_at_utc": expires,
        "nonce": nonce,
        "generation": 1,
        "authority": "OWNER_EXTERNAL_AUTHORITY",
        "decision": "ALLOW_SINGLE_USE",
    }


def _source_lineage_mutation(snapshot: SourceSnapshot) -> SourceSnapshot:
    """Mutate the Route-C source lineage itself, not a derived intake field."""

    artifact_id = "route_c_checkpoint_b"
    original = snapshot.artifacts[artifact_id]
    parsed = thaw(original.parsed)
    parsed["authority_guards"]["route_b_seed_inheritance_allowed"] = True
    mutated_payload = canonical_json_bytes(parsed)
    artifacts = dict(snapshot.artifacts)
    artifacts[artifact_id] = replace(
        original,
        parsed=deep_freeze(parsed),
        payload=mutated_payload,
        byte_count=len(mutated_payload),
        sha256=sha256_bytes(mutated_payload),
    )
    return replace(snapshot, artifacts=MappingProxyType(artifacts))


def run_negative_controls(snapshot: SourceSnapshot | None = None) -> dict[str, Any]:
    snapshot = load_default_snapshot() if snapshot is None else snapshot
    baseline = evaluate_snapshot(snapshot)
    baseline_bytes = canonical_json_bytes(baseline)
    baseline_hash = sha256_bytes(baseline_bytes)
    controls: list[dict[str, Any]] = []

    def add(control_id: str, stimulus: str, passed: bool) -> None:
        controls.append({"id": control_id, "stimulus": stimulus, "passed": passed})

    missing_uncertainty = deepcopy(baseline)
    del missing_uncertainty["physical_quantities"]["c01_design_mass"]["uncertainty"]["correlation"]
    add("NC01", "MISSING_UNCERTAINTY_FIELD", _rejected(lambda: validate_intake_document(missing_uncertainty), "MALFORMED"))

    zero_filled = deepcopy(baseline)
    zero_filled["physical_quantities"]["contact_normal_stiffness"]["value"] = 0.0
    add("NC02", "NULL_PHYSICAL_VALUE_ZERO_FILLED", _rejected(lambda: validate_intake_document(zero_filled), "TEST_REQUIRED"))

    wrong_unit = deepcopy(baseline)
    wrong_unit["physical_quantities"]["c01_design_mass"]["unit"] = "lb"
    add("NC03", "WRONG_PHYSICAL_UNIT", _rejected(lambda: validate_intake_document(wrong_unit), "MALFORMED"))

    add(
        "NC04",
        "GHOST_DESKTOP_MESH_PATH",
        _rejected(lambda: validate_project_relative_path("C:/Users/operator/Desktop/ghost_mesh.STL"), "MALFORMED"),
    )

    physical_speed = deepcopy(baseline)
    physical_speed["physical_quantities"]["gripper_urdf_model_velocity_literal"]["authority"] = "HARDWARE_RATED_SPEED"
    add("NC05", "URDF_SPEED_PROMOTED_TO_HARDWARE_RATING", _rejected(lambda: validate_intake_document(physical_speed), "TEST_REQUIRED"))

    now = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
    stale = _receipt("2026-08-25T10:00:00Z", "2026-08-25T10:10:00Z")
    add(
        "NC06",
        "STALE_OWNER_RECEIPT",
        _rejected(
            lambda: validate_promotion_receipt(
                stale,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=set(),
            ),
            "OWNER_REQUIRED",
        ),
    )

    fresh = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z")
    replay_ledger: set[str] = set()
    validate_promotion_receipt(
        fresh,
        now=now,
        expected_action_digest="A" * 64,
        expected_context_digest="B" * 64,
        replay_ledger=replay_ledger,
    )
    add(
        "NC07",
        "REPLAYED_OWNER_RECEIPT",
        _rejected(
            lambda: validate_promotion_receipt(
                fresh,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=replay_ledger,
            ),
            "OWNER_REQUIRED",
        ),
    )

    add(
        "NC08",
        "DUAL_OR_AGGREGATE_MASS_MODE",
        _rejected(lambda: validate_mass_mode(["EXPLICIT_STRUCTURE_PLUS_RESIDUAL", "AGGREGATE_BUS"]), "MALFORMED")
        and _rejected(lambda: validate_mass_mode("AGGREGATE_BUS"), "MALFORMED"),
    )

    route_b_snapshot = _source_lineage_mutation(snapshot)
    route_b_polluted = route_b_snapshot.artifacts["route_c_checkpoint_b"].parsed["authority_guards"]["route_b_seed_inheritance_allowed"] is True
    add(
        "NC09",
        "ROUTE_B_SEED_INHERITANCE_IN_SOURCE_LINEAGE",
        route_b_polluted and _rejected(lambda: evaluate_snapshot(route_b_snapshot)),
    )

    candidate_release = deepcopy(baseline)
    candidate_release["domains"]["material"]["classification"] = "PASS"
    candidate_release["domains"]["material"]["eligible"] = True
    add("NC10", "CANDIDATE_PROMOTED_TO_RELEASED", _rejected(lambda: validate_intake_document(candidate_release), "OWNER_REQUIRED"))

    add("NC11", "ABSOLUTE_REPOSITORY_PATH", _rejected(lambda: validate_project_relative_path("/outside/source.json"), "MALFORMED"))
    add("NC12", "TRAVERSAL_REPOSITORY_PATH", _rejected(lambda: validate_project_relative_path("../outside/source.json"), "MALFORMED"))

    with patch("current_handoff.strict_io._is_link_or_reparse", return_value=True):
        symlink_rejected = _rejected(
            lambda: resolve_bound_path(snapshot.project_root, snapshot.artifacts["topology_frame_tree"].relative_path),
            "MALFORMED",
        )
    add("NC13", "SYMLINK_OR_REPARSE_SOURCE", symlink_rejected)

    add("NC14", "DUPLICATE_JSON_KEY", _rejected(lambda: strict_json_bytes(b'{"schema":"A","schema":"B"}'), "MALFORMED"))
    add(
        "NC15",
        "NAN_OR_INFINITY_JSON",
        _rejected(lambda: strict_json_bytes(b'{"x":NaN}'), "MALFORMED")
        and _rejected(lambda: strict_json_bytes(b'{"x":Infinity}'), "MALFORMED"),
    )

    extra = deepcopy(baseline)
    extra["unexpected"] = False
    add("NC16", "EXTRA_JSON_FIELD", _rejected(lambda: validate_intake_document(extra), "MALFORMED"))
    add("NC17", "SOURCE_HASH_DRIFT", _rejected(lambda: verify_payload(b"drift", 5, "0" * 64), "HASH_DRIFT"))
    add(
        "NC18",
        "MISSING_BOUND_SOURCE",
        _rejected(lambda: resolve_bound_path(snapshot.project_root, "20_engineering/definitely_absent_source.json"), "MISSING"),
    )

    route_c_included = {
        "schema": "ROUTE_C_DISPOSITION_V1",
        "disposition": "INCLUDED",
        "owner_receipt_digest": None,
        "auto_accepted": False,
    }
    route_c_excluded = {
        "schema": "ROUTE_C_DISPOSITION_V1",
        "disposition": "EXCLUDED_RESEARCH_CANDIDATE",
        "owner_receipt_digest": None,
        "auto_accepted": False,
    }
    add("NC19", "ROUTE_C_INCLUDED_AUTO_ACCEPT", _rejected(lambda: route_c_auto_accept(route_c_included), "OWNER_REQUIRED"))
    add("NC20", "ROUTE_C_EXCLUDED_AUTO_ACCEPT", _rejected(lambda: route_c_auto_accept(route_c_excluded), "OWNER_REQUIRED"))

    bypass = deepcopy(baseline["promotion_sequence"])
    bypass[0]["state"] = "PASS"
    add("NC21", "PROMOTION_SEQUENCE_BYPASS", _rejected(lambda: validate_promotion_sequence(bypass), "OWNER_REQUIRED"))

    replay = evaluate_snapshot(snapshot)
    mutation_source = snapshot.artifacts["e15_gate"]
    tampered_payload = bytearray(mutation_source.payload)
    mutation_index = len(tampered_payload) // 2
    tampered_payload[mutation_index] ^= 0x01
    tampered_bytes = bytes(tampered_payload)
    add(
        "NC22",
        "SOURCE_PAYLOAD_BYTE_AND_HASH_MUTATION",
        canonical_json_bytes(replay) == baseline_bytes
        and sha256_bytes(canonical_json_bytes(replay)) == baseline_hash
        and len(tampered_bytes) == mutation_source.byte_count
        and sha256_bytes(tampered_bytes) != mutation_source.sha256
        and _rejected(
            lambda: verify_payload(tampered_bytes, mutation_source.byte_count, mutation_source.sha256),
            "HASH_DRIFT",
        ),
    )

    false_complete = deepcopy(baseline)
    false_complete["current_intake_status"] = "INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION"
    add("NC23", "CURRENT_STATUS_FALSELY_COMPLETED", _rejected(lambda: validate_intake_document(false_complete), "OWNER_REQUIRED"))

    promoted_flag = deepcopy(baseline)
    promoted_flag["flags"]["current_system_bound"] = True
    add("NC24", "MANDATORY_FALSE_FLIPPED_TRUE", _rejected(lambda: validate_intake_document(promoted_flag), "OWNER_REQUIRED"))

    syntactic_ledger: set[str] = set()
    schema_preflight_ok = True
    try:
        validate_promotion_receipt(
            _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", "NONCE_CURRENT_SYS_0025"),
            now=now,
            expected_action_digest="A" * 64,
            expected_context_digest="B" * 64,
            replay_ledger=syntactic_ledger,
        )
    except IntakeError:
        schema_preflight_ok = False
    forged_after_preflight = deepcopy(baseline)
    forged_after_preflight["flags"]["current_system_bound"] = True
    add(
        "NC25",
        "SCHEMA_VALID_RECEIPT_MISUSED_AS_CRYPTOGRAPHIC_AUTHORITY",
        schema_preflight_ok and _rejected(lambda: validate_intake_document(forged_after_preflight), "OWNER_REQUIRED"),
    )

    alias_cases = (
        "20_engineering//source.json",
        "20_engineering/./source.json",
        "20_engineering/NUL.json",
        "20_engineering/control\x00source.json",
    )
    add(
        "NC26",
        "PATH_ALIAS_CONTROL_OR_WINDOWS_RESERVED_SEGMENT",
        all(_rejected(lambda candidate=candidate: validate_project_relative_path(candidate), "MALFORMED") for candidate in alias_cases),
    )

    wrong_artifact = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", "NONCE_CURRENT_SYS_0027")
    wrong_artifact["artifact_id"] = "FORGED_PROMOTION_RECEIPT"
    add(
        "NC27",
        "PROMOTION_RECEIPT_ARTIFACT_ID_MISMATCH",
        _rejected(
            lambda: validate_promotion_receipt(
                wrong_artifact,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=set(),
            ),
            "OWNER_REQUIRED",
        ),
    )

    action_ledger: set[str] = set()
    wrong_action = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", "NONCE_CURRENT_SYS_0028")
    wrong_action["action_digest"] = "C" * 64
    add(
        "NC28",
        "PROMOTION_RECEIPT_ACTION_DIGEST_MISMATCH",
        _rejected(
            lambda: validate_promotion_receipt(
                wrong_action,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=action_ledger,
            ),
            "OWNER_REQUIRED",
        )
        and not action_ledger,
    )

    context_ledger: set[str] = set()
    wrong_context = _receipt("2026-08-25T11:55:00Z", "2026-08-25T12:05:00Z", "NONCE_CURRENT_SYS_0029")
    wrong_context["context_digest"] = "D" * 64
    add(
        "NC29",
        "PROMOTION_RECEIPT_CONTEXT_DIGEST_MISMATCH",
        _rejected(
            lambda: validate_promotion_receipt(
                wrong_context,
                now=now,
                expected_action_digest="A" * 64,
                expected_context_digest="B" * 64,
                replay_ledger=context_ledger,
            ),
            "OWNER_REQUIRED",
        )
        and not context_ledger,
    )

    extra_evidence_or_result = (
        "evidence/ROGUE_GENERATED_ASSET.json",
        "results/ROGUE_UNRECEIPTED_RESULT.json",
    )
    add(
        "NC30",
        "EXTRA_EVIDENCE_OR_RESULT_FILE_OUTSIDE_FROZEN_ALLOWLIST",
        all(
            _rejected(
                lambda extra=extra: validate_frozen_package_file_set((*FROZEN_PACKAGE_FILE_ALLOWLIST, extra)),
                "MALFORMED",
            )
            for extra in extra_evidence_or_result
        ),
    )

    physics_robot_extensions = (".sdf", ".xacro", ".mjcf", ".msh", ".vtk", ".npy", ".h5")
    add(
        "NC31",
        "EXTRA_PHYSICS_OR_ROBOT_FORMAT_OUTSIDE_FROZEN_ALLOWLIST",
        all(
            _rejected(
                lambda suffix=suffix: validate_frozen_package_file_set(
                    (*FROZEN_PACKAGE_FILE_ALLOWLIST, f"evidence/ROGUE_PHYSICS_ROBOT_ASSET{suffix}")
                ),
                "MALFORMED",
            )
            for suffix in physics_robot_extensions
        ),
    )

    return {
        "schema": "CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROLS_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "baseline_sha256": baseline_hash,
        "baseline_status": baseline["current_intake_status"],
        "controls": controls,
        "controls_passed": sum(item["passed"] for item in controls),
        "controls_total": len(controls),
        "all_passed": bool(controls) and all(item["passed"] for item in controls),
        "receipt_validation_scope": "SCHEMA_FRESHNESS_BINDING_IN_MEMORY_REPLAY_PREFLIGHT_ONLY__NO_PERSISTENT_OR_CROSS_PROCESS_CREDIT__NO_SIGNATURE_OR_TRUST_ROOT",
        "urdf_generator_invoked": False,
        "generated_cad_step_mesh_urdf_or_physics_assets": False,
    }
