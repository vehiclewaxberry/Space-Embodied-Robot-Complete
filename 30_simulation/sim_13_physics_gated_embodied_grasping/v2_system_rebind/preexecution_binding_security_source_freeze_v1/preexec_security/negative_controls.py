"""Exact single-fault source-only probes for NC15, NC16 and NC20."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from .receipts import (
    ReceiptError,
    ReplayStore,
    SHIELD_CAPABILITY,
    admit_backend_request,
    evaluate_receipt_bound_join,
    issue_synthetic_receipt,
    verify_receipt,
)
from .strict_json import canonical_digest, loads_strict


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[5]
PIN_PATH = PACKAGE_ROOT / "contracts/PARENT_BASELINE_HASH_PINS_V1.json"
SYNTHETIC_KEY = b"SIM13_SOURCE_FREEZE_SYNTHETIC_KEY_ONLY_20260825"
NOW = 1_787_600_000.0
ACTION_S1 = {
    "grasp_candidate_id": "GC_SYNTHETIC",
    "capture_timing_id": "T_SYNTHETIC",
    "strategy_id": "S1",
}
ACTION_ABORT = {
    "grasp_candidate_id": "__ABORT__",
    "capture_timing_id": "__ABORT__",
    "strategy_id": "ABORT",
}
CONTEXT = {
    "episode_id": "SYNTHETIC_SOURCE_FREEZE_EPISODE",
    "configuration_id": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
    "authority_epoch": 1,
    "target_class": "DEBRIS_150KG_3DPS",
}


@dataclass(frozen=True)
class ProbeRecord:
    control_id: str
    repeat_id: str
    baseline_valid: bool
    single_fault: str
    expected_reason: str
    observed_reason: str
    observed_outcome: str
    non_abort_execution_count: int
    exact_reason_match: bool
    baseline_hash_unchanged: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def parent_baseline_hashes() -> tuple[dict[str, str], bool]:
    pin_document = loads_strict(PIN_PATH.read_bytes())
    actual: dict[str, str] = {}
    unchanged = True
    for relative, expected in pin_document["pins"].items():
        path = PROJECT_ROOT / relative
        digest = _sha256(path) if path.is_file() else "ABSENT"
        actual[relative] = digest
        unchanged = unchanged and digest == expected
    return actual, unchanged


def _receipt(kind: str, payload: dict[str, Any], nonce: str, *, action: dict[str, Any] = ACTION_S1) -> bytes:
    return issue_synthetic_receipt(
        kind=kind,
        action=action,
        context=CONTEXT,
        payload=payload,
        issued_at_unix_s=NOW - 1.0,
        expires_at_unix_s=NOW + 30.0,
        nonce=nonce,
        evidence_sha256="A" * 64,
        key=SYNTHETIC_KEY,
    )


def _probe_nc15(repeat_id: str, baseline_unchanged: bool) -> ProbeRecord:
    receipt = _receipt(
        "SYSTEM_BINDING_V2",
        {"status": "PASS", "system_urdf_sha256": "B" * 64},
        f"NC15_{repeat_id}_NONCE_0001",
    )
    store = ReplayStore()
    first = verify_receipt(
        receipt,
        expected_kind="SYSTEM_BINDING_V2",
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=store,
        key=SYNTHETIC_KEY,
    )
    # Seed an already-consumed global nonce as the single NC15 fault.  Public
    # verification itself is read-only; only this synthetic replay precondition
    # uses the future atomic-commit primitive.
    store.consume_many((first.nonce,))
    observed = "NO_REJECTION"
    try:
        verify_receipt(
            receipt,
            expected_kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=store,
            key=SYNTHETIC_KEY,
        )
    except ReceiptError as exc:
        observed = str(exc)
    expected = "REPLAY_NONCE"
    return ProbeRecord(
        "NC15",
        repeat_id,
        first.status == "PASS",
        "REPLAY_IDENTICAL_FRESH_GATE_RECEIPT_BYTES",
        expected,
        observed,
        "MASK_TO_ABORT_ONLY" if observed == expected else "NON_ABORT_ESCAPED",
        0,
        observed == expected,
        baseline_unchanged,
    )


def _probe_nc16(repeat_id: str, baseline_unchanged: bool) -> ProbeRecord:
    shield = _receipt(
        "SHIELD_ATTESTATION_V2",
        {"status": "PASS", "capability": SHIELD_CAPABILITY, "shielded": True},
        f"NC16_{repeat_id}_NONCE_0001",
    )
    verified = verify_receipt(
        shield,
        expected_kind="SHIELD_ATTESTATION_V2",
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=ReplayStore(),
        key=SYNTHETIC_KEY,
    )
    baseline_store = ReplayStore()
    baseline = admit_backend_request(
        "S1",
        shield_receipt_bytes=shield,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=baseline_store,
        key=SYNTHETIC_KEY,
    )
    baseline_repeat = admit_backend_request(
        "S1",
        shield_receipt_bytes=shield,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=baseline_store,
        key=SYNTHETIC_KEY,
    )
    mutation = admit_backend_request(
        "S1",
        shield_receipt_bytes=None,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=ReplayStore(),
        key=SYNTHETIC_KEY,
    )
    observed = mutation.reason_codes[0]
    expected = "SHIELD_ATTESTATION_REQUIRED"
    return ProbeRecord(
        "NC16",
        repeat_id,
        verified.status == "PASS"
        and baseline.allowed is False
        and baseline.executed_strategy == "ABORT"
        and baseline.reason_codes == ("SOURCE_FREEZE_SCOPE_LOCK",)
        and baseline.attestation_verified is True
        and baseline_repeat.reason_codes == ("SOURCE_FREEZE_SCOPE_LOCK",)
        and baseline_store.seen_count == 0,
        "REMOVE_ONLY_SHIELD_ATTESTATION_RECEIPT",
        expected,
        observed,
        "MASK_TO_ABORT_ONLY" if mutation.executed_strategy == "ABORT" else "NON_ABORT_ESCAPED",
        0 if mutation.executed_strategy == "ABORT" else 1,
        observed == expected,
        baseline_unchanged,
    )


def _probe_nc20(repeat_id: str, baseline_unchanged: bool) -> ProbeRecord:
    gate_states = {
        name: "PASS"
        for name in (
            "ik_reachable", "external_collision_clear", "keep_out_clear", "sim10_gate",
            "safe00_state", "post_grasp_stability_gate", "gripper_configuration_accepted",
            "target_surface_normal_valid", "mechanical_system_binding",
            "harness_rated_envelope", "contact_physics_ready", "route_c_scope_disposition",
        )
    }
    complete = {
        "SYSTEM_BINDING_V2": _receipt("SYSTEM_BINDING_V2", {"status": "PASS", "system_urdf_sha256": "B" * 64}, f"NC20_{repeat_id}_SYS_NONCE", action=ACTION_S1),
        "RUNTIME_GATE_SNAPSHOT_V2": _receipt("RUNTIME_GATE_SNAPSHOT_V2", {"status": "PASS", "gate_count": 12, "gate_digest": canonical_digest(gate_states), "gate_states": gate_states}, f"NC20_{repeat_id}_RUN_NONCE", action=ACTION_S1),
        "DYNAMICS_GATE_V2": _receipt("DYNAMICS_GATE_V2", {"status": "PASS", "backend_receipt_sha256": "C" * 64}, f"NC20_{repeat_id}_DYN_NONCE", action=ACTION_S1),
        "CONTACT_PREFLIGHT_V2": _receipt("CONTACT_PREFLIGHT_V2", {"status": "PASS", "contact_receipt_sha256": "D" * 64}, f"NC20_{repeat_id}_CON_NONCE", action=ACTION_S1),
        "SHIELD_ATTESTATION_V2": _receipt("SHIELD_ATTESTATION_V2", {"status": "PASS", "capability": SHIELD_CAPABILITY, "shielded": True}, f"NC20_{repeat_id}_SHD_NONCE", action=ACTION_S1),
        "FEASIBILITY_150KG_V2": _receipt(
            "FEASIBILITY_150KG_V2",
            {
                "status": "FAIL",
                "target_mass_kg": 150.0,
                "target_rate_deg_s": 3.0,
                "post_capture_rate_deg_s": 3.0633,
                "verdict": "INFEASIBLE_RATE",
                "sim10_source_sha256": "E" * 64,
            },
            f"NC20_{repeat_id}_FEA_NONCE",
            action=ACTION_S1,
        ),
        "POST_GRASP_V2": _receipt(
            "POST_GRASP_V2",
            {"status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0, "stability_receipt_sha256": "F" * 64},
            f"NC20_{repeat_id}_PGR_NONCE",
            action=ACTION_S1,
        ),
    }
    # Establish that the baseline really contains seven independently valid,
    # action/context-bound records.  FAIL is a valid authenticated semantic
    # verdict for the feasibility and post-grasp records, not malformed bytes.
    preflight_store = ReplayStore()
    preflight = {
        kind: verify_receipt(
            receipt,
            expected_kind=kind,
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=preflight_store,
            key=SYNTHETIC_KEY,
        )
        for kind, receipt in complete.items()
    }
    preflight_valid = (
        set(preflight) == set(complete)
        and all(
            receipt.status == ("FAIL" if kind in {"FEASIBILITY_150KG_V2", "POST_GRASP_V2"} else "PASS")
            for kind, receipt in preflight.items()
        )
        and preflight_store.seen_count == 0
    )
    baseline_store = ReplayStore()
    baseline = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind=complete,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=baseline_store,
        key=SYNTHETIC_KEY,
    )
    baseline_repeat = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind=complete,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=baseline_store,
        key=SYNTHETIC_KEY,
    )
    without_feasibility = dict(complete)
    without_feasibility.pop("FEASIBILITY_150KG_V2")
    missing_feasibility = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind=without_feasibility,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=ReplayStore(),
        key=SYNTHETIC_KEY,
    )
    without_post_grasp = dict(complete)
    without_post_grasp.pop("POST_GRASP_V2")
    missing_post_grasp = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind=without_post_grasp,
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=ReplayStore(),
        key=SYNTHETIC_KEY,
    )
    observed_reasons = missing_feasibility.reason_codes + missing_post_grasp.reason_codes
    observed = "|".join(observed_reasons)
    expected = "MISSING_RECEIPT_KIND:FEASIBILITY_150KG_V2|MISSING_RECEIPT_KIND:POST_GRASP_V2"
    return ProbeRecord(
        "NC20",
        repeat_id,
        preflight_valid
        and baseline.allowed is False
        and baseline.executed_strategy == "ABORT"
        and baseline.reason_codes == ("FEASIBILITY_150KG_V2_FAIL",)
        and baseline_repeat.reason_codes == baseline.reason_codes
        and baseline_store.seen_count == 0,
        "TWO_ISOLATED_SUBPROBES_REMOVE_FEASIBILITY_THEN_POST_GRASP_FROM_OTHERWISE_COMPLETE_RECEIPT_SET",
        expected,
        observed,
        "MASK_TO_ABORT_ONLY" if missing_feasibility.executed_strategy == missing_post_grasp.executed_strategy == "ABORT" else "NON_ABORT_ESCAPED",
        int(missing_feasibility.executed_strategy != "ABORT") + int(missing_post_grasp.executed_strategy != "ABORT"),
        observed == expected,
        baseline_unchanged,
    )


PROBES: tuple[tuple[str, Callable[[str, bool], ProbeRecord]], ...] = (
    ("NC15", _probe_nc15),
    ("NC16", _probe_nc16),
    ("NC20", _probe_nc20),
)


def run_security_negative_controls() -> dict[str, Any]:
    hashes_before, pins_before = parent_baseline_hashes()
    records: list[ProbeRecord] = []
    for _, probe in PROBES:
        records.append(probe("R1", pins_before))
        records.append(probe("R2", pins_before))
    hashes_after, pins_after = parent_baseline_hashes()
    baseline_unchanged = pins_before and pins_after and hashes_before == hashes_after
    groups: list[dict[str, Any]] = []
    for control_id, _ in PROBES:
        selected = [record for record in records if record.control_id == control_id]
        invariant_views = [
            {
                key: value
                for key, value in asdict(record).items()
                if key not in ("repeat_id",)
            }
            for record in selected
        ]
        deterministic = invariant_views[0] == invariant_views[1]
        passed = all(
            record.baseline_valid
            and record.observed_outcome == "MASK_TO_ABORT_ONLY"
            and record.non_abort_execution_count == 0
            and record.exact_reason_match
            and record.baseline_hash_unchanged
            for record in selected
        ) and deterministic and baseline_unchanged
        groups.append(
            {
                "control_id": control_id,
                "status": "PASS_NEGATIVE_CONTROL_DETECTED" if passed else "FAIL_NEGATIVE_CONTROL_ESCAPED",
                "deterministic_repeat": deterministic,
                "records": [asdict(record) for record in selected],
            }
        )
    all_pass = all(group["status"] == "PASS_NEGATIVE_CONTROL_DETECTED" for group in groups)
    return {
        "schema": "SIM13_PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1",
        "scope": "SOURCE_ONLY_SYNTHETIC_KERNEL_NO_PRODUCTION_CREDIT",
        "controls_requested": [item[0] for item in PROBES],
        "controls_passed": [group["control_id"] for group in groups if group["status"].startswith("PASS")],
        "all_requested_controls_passed": all_pass,
        "groups": groups,
        "parent_baseline_hashes_before": hashes_before,
        "parent_baseline_hashes_after": hashes_after,
        "parent_baseline_hashes_unchanged": baseline_unchanged,
        "parent_formal_nc_passed": 15,
        "parent_formal_nc_total": 20,
        "formal_nc_promotion": 0,
        "additive_effective_source_only_frontier_passed": 18 if all_pass else 15,
        "additive_effective_source_only_frontier_total": 20,
        "remaining_dependency_holds": ["NC18", "NC19"],
        "contact_release_eligible": False,
        "next_stage_authorized": False,
    }


__all__ = [
    "ACTION_ABORT",
    "ACTION_S1",
    "CONTEXT",
    "NOW",
    "ProbeRecord",
    "SYNTHETIC_KEY",
    "parent_baseline_hashes",
    "run_security_negative_controls",
]
