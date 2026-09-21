"""Hash-, action-, context-, time- and nonce-bound admission receipts.

The HMAC key is supplied by the caller and is never embedded in this source
freeze.  Tests use an explicitly synthetic key.  A future production adapter
must obtain its key and trusted clock from separately qualified authority.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
from dataclasses import dataclass
from typing import Any, Mapping

from .strict_json import (
    StrictJSONError,
    canonical_digest,
    canonical_json_bytes,
    deep_freeze,
    loads_strict,
    require_exact_keys,
    validate_json_domain,
)


RECEIPT_SCHEMA = "SIM13_PREEXECUTION_RECEIPT_V1"
MAX_VALIDITY_SECONDS = 300.0
MAX_FUTURE_SKEW_SECONDS = 2.0
SHIELD_CAPABILITY = "SIM13_NON_ABORT_ONLY_THROUGH_FAIL_CLOSED_SHIELD_V2"
KINDS = (
    "SYSTEM_BINDING_V2",
    "RUNTIME_GATE_SNAPSHOT_V2",
    "DYNAMICS_GATE_V2",
    "CONTACT_PREFLIGHT_V2",
    "SHIELD_ATTESTATION_V2",
    "FEASIBILITY_150KG_V2",
    "POST_GRASP_V2",
)
ACTION_FIELDS = (
    "grasp_candidate_id",
    "capture_timing_id",
    "strategy_id",
)
CONTEXT_FIELDS = (
    "episode_id",
    "configuration_id",
    "authority_epoch",
    "target_class",
)
CANONICAL_ABORT_ACTION = {
    "grasp_candidate_id": "__ABORT__",
    "capture_timing_id": "__ABORT__",
    "strategy_id": "ABORT",
}
_SHA256 = re.compile(r"^[0-9A-F]{64}$")
_NONCE = re.compile(r"^[A-Za-z0-9._-]{16,128}$")
_RUNTIME_GATE_NAMES = (
    "ik_reachable",
    "external_collision_clear",
    "keep_out_clear",
    "sim10_gate",
    "safe00_state",
    "post_grasp_stability_gate",
    "gripper_configuration_accepted",
    "target_surface_normal_valid",
    "mechanical_system_binding",
    "harness_rated_envelope",
    "contact_physics_ready",
    "route_c_scope_disposition",
)


class ReceiptError(ValueError):
    """A receipt failed syntax, binding, freshness, replay or policy checks."""


@dataclass(frozen=True)
class VerifiedReceipt:
    kind: str
    nonce: str
    status: str
    action_digest: str
    context_digest: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AdmissionDecision:
    requested_strategy: str
    executed_strategy: str
    allowed: bool
    reason_codes: tuple[str, ...]
    attestation_verified: bool


class ReplayStore:
    """In-process synthetic nonce state with no persistent production credit.

    The store exists only to exercise replay and atomic-commit semantics in this
    source-freeze.  Restarting the process loses state; a future production
    adapter must replace it with a qualified durable store.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def assert_unseen(self, nonces: tuple[str, ...] | list[str]) -> None:
        """Read-only global nonce check; no state is changed."""

        with self._lock:
            if len(nonces) != len(set(nonces)):
                raise ReceiptError("DUPLICATE_NONCE_IN_BUNDLE")
            if any(nonce in self._seen for nonce in nonces):
                raise ReceiptError("REPLAY_NONCE")

    def consume_many(self, nonces: tuple[str, ...] | list[str]) -> None:
        """Future atomic allow-commit primitive; unused by this ABORT-only API."""

        with self._lock:
            if len(nonces) != len(set(nonces)):
                raise ReceiptError("DUPLICATE_NONCE_IN_BUNDLE")
            if any(nonce in self._seen for nonce in nonces):
                raise ReceiptError("REPLAY_NONCE")
            self._seen.update(nonces)

    @property
    def seen_count(self) -> int:
        with self._lock:
            return len(self._seen)


def _validate_action_context(
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    requested_strategy: str | None = None,
) -> tuple[str, str]:
    """Enforce the parent high-level action and exact contextual envelope."""

    try:
        validate_json_domain(action, path="/action")
        validate_json_domain(context, path="/context")
        require_exact_keys(action, ACTION_FIELDS, path="/action")
        require_exact_keys(context, CONTEXT_FIELDS, path="/context")
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc
    for field in ACTION_FIELDS:
        value = action[field]
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ReceiptError(f"INVALID_ACTION_FIELD:/action/{field}")
    for field in ("episode_id", "configuration_id", "target_class"):
        value = context[field]
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ReceiptError(f"INVALID_CONTEXT_FIELD:/context/{field}")
    epoch = context["authority_epoch"]
    if type(epoch) is not int or epoch < 1:
        raise ReceiptError("INVALID_CONTEXT_FIELD:/context/authority_epoch")
    abort_token_present = (
        action["grasp_candidate_id"] == "__ABORT__"
        or action["capture_timing_id"] == "__ABORT__"
        or action["strategy_id"] == "ABORT"
    )
    if abort_token_present and dict(action) != CANONICAL_ABORT_ACTION:
        raise ReceiptError("NONCANONICAL_ABORT_ACTION")
    if requested_strategy is not None:
        if not isinstance(requested_strategy, str) or requested_strategy != action["strategy_id"]:
            raise ReceiptError("REQUESTED_STRATEGY_ACTION_MISMATCH")
    try:
        return canonical_digest(dict(action)), canonical_digest(dict(context))
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc


def _require_sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ReceiptError(f"INVALID_SHA256:{path}")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReceiptError(f"INVALID_NUMBER:{path}")
    try:
        result = float(value)
    except OverflowError as exc:
        # Strict JSON intentionally accepts arbitrary-precision integers.  A
        # hostile but syntactically valid integer can still overflow binary64;
        # translate only that expected boundary failure into a policy error.
        raise ReceiptError(f"INVALID_NUMBER:{path}") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ReceiptError(f"INVALID_NUMBER:{path}")
    return result


def _status(value: Any, path: str) -> str:
    if value not in ("PASS", "FAIL", "UNKNOWN", "HOLD"):
        raise ReceiptError(f"INVALID_STATUS:{path}")
    return str(value)


def _validate_payload(kind: str, value: Any) -> str:
    path = f"/body/payload/{kind}"
    if kind == "SYSTEM_BINDING_V2":
        require_exact_keys(value, ("status", "system_urdf_sha256"), path=path)
        _require_sha(value["system_urdf_sha256"], f"{path}/system_urdf_sha256")
        return _status(value["status"], f"{path}/status")
    if kind == "RUNTIME_GATE_SNAPSHOT_V2":
        require_exact_keys(value, ("status", "gate_count", "gate_digest", "gate_states"), path=path)
        if value["gate_count"] != 12:
            raise ReceiptError("RUNTIME_GATE_COUNT_MISMATCH")
        _require_sha(value["gate_digest"], f"{path}/gate_digest")
        require_exact_keys(value["gate_states"], _RUNTIME_GATE_NAMES, path=f"{path}/gate_states")
        states = {
            name: _status(value["gate_states"][name], f"{path}/gate_states/{name}")
            for name in _RUNTIME_GATE_NAMES
        }
        if value["gate_digest"] != canonical_digest(states):
            raise ReceiptError("RUNTIME_GATE_DIGEST_MISMATCH")
        status = _status(value["status"], f"{path}/status")
        aggregate = "PASS" if all(state == "PASS" for state in states.values()) else "FAIL"
        if status != aggregate:
            raise ReceiptError("RUNTIME_GATE_AGGREGATE_MISMATCH")
        return status
    if kind == "DYNAMICS_GATE_V2":
        require_exact_keys(value, ("status", "backend_receipt_sha256"), path=path)
        _require_sha(value["backend_receipt_sha256"], f"{path}/backend_receipt_sha256")
        return _status(value["status"], f"{path}/status")
    if kind == "CONTACT_PREFLIGHT_V2":
        require_exact_keys(value, ("status", "contact_receipt_sha256"), path=path)
        _require_sha(value["contact_receipt_sha256"], f"{path}/contact_receipt_sha256")
        return _status(value["status"], f"{path}/status")
    if kind == "SHIELD_ATTESTATION_V2":
        require_exact_keys(value, ("status", "capability", "shielded"), path=path)
        if value["capability"] != SHIELD_CAPABILITY or value["shielded"] is not True:
            raise ReceiptError("SHIELD_CAPABILITY_OR_ATTESTATION_INVALID")
        return _status(value["status"], f"{path}/status")
    if kind == "FEASIBILITY_150KG_V2":
        require_exact_keys(
            value,
            (
                "status",
                "target_mass_kg",
                "target_rate_deg_s",
                "post_capture_rate_deg_s",
                "verdict",
                "sim10_source_sha256",
            ),
            path=path,
        )
        mass = _number(value["target_mass_kg"], f"{path}/target_mass_kg")
        rate = _number(value["target_rate_deg_s"], f"{path}/target_rate_deg_s")
        post = _number(value["post_capture_rate_deg_s"], f"{path}/post_capture_rate_deg_s")
        _require_sha(value["sim10_source_sha256"], f"{path}/sim10_source_sha256")
        status = _status(value["status"], f"{path}/status")
        if abs(mass - 150.0) > 1.0e-12 or abs(rate - 3.0) > 1.0e-12:
            raise ReceiptError("FEASIBILITY_ANCHOR_MISMATCH")
        if abs(post - 3.0633) > 1.0e-12:
            raise ReceiptError("FEASIBILITY_POST_CAPTURE_ANCHOR_MISMATCH")
        if value["verdict"] != "INFEASIBLE_RATE" or status != "FAIL":
            raise ReceiptError("150KG_3DPS_PASS_FORGERY")
        return status
    if kind == "POST_GRASP_V2":
        require_exact_keys(
            value,
            ("status", "target_mass_kg", "target_rate_deg_s", "stability_receipt_sha256"),
            path=path,
        )
        mass = _number(value["target_mass_kg"], f"{path}/target_mass_kg")
        rate = _number(value["target_rate_deg_s"], f"{path}/target_rate_deg_s")
        _require_sha(value["stability_receipt_sha256"], f"{path}/stability_receipt_sha256")
        status = _status(value["status"], f"{path}/status")
        if abs(mass - 150.0) > 1.0e-12 or abs(rate - 3.0) > 1.0e-12:
            raise ReceiptError("POST_GRASP_ANCHOR_MISMATCH")
        if status == "PASS":
            raise ReceiptError("150KG_3DPS_POST_GRASP_PASS_FORGERY")
        return status
    raise ReceiptError(f"UNKNOWN_RECEIPT_KIND:{kind}")


def _sign(body: Mapping[str, Any], key: bytes) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ReceiptError("ATTESTATION_KEY_TOO_SHORT")
    return hmac.new(key, canonical_json_bytes(body), hashlib.sha256).hexdigest().upper()


def issue_synthetic_receipt(
    *,
    kind: str,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    payload: Mapping[str, Any],
    issued_at_unix_s: float,
    expires_at_unix_s: float,
    nonce: str,
    evidence_sha256: str,
    key: bytes,
) -> bytes:
    """Issue bytes for a synthetic test receipt; this is not production authority."""

    try:
        validate_json_domain(action, path="/action")
        validate_json_domain(context, path="/context")
        validate_json_domain(payload, path="/payload")
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc
    if kind not in KINDS:
        raise ReceiptError(f"UNKNOWN_RECEIPT_KIND:{kind}")
    action_digest, context_digest = _validate_action_context(action, context)
    if not isinstance(payload, Mapping):
        raise ReceiptError("PAYLOAD_NOT_OBJECT")
    if not isinstance(nonce, str) or not _NONCE.fullmatch(nonce):
        raise ReceiptError("INVALID_NONCE")
    _require_sha(evidence_sha256, "/body/evidence_sha256")
    issued = _number(issued_at_unix_s, "/body/issued_at_unix_s")
    expires = _number(expires_at_unix_s, "/body/expires_at_unix_s")
    if expires <= issued or expires - issued > MAX_VALIDITY_SECONDS:
        raise ReceiptError("INVALID_VALIDITY_WINDOW")
    body = {
        "schema": RECEIPT_SCHEMA,
        "kind": kind,
        "issuer": "SYNTHETIC_SOURCE_FREEZE_FIXTURE_ONLY",
        "action_digest": action_digest,
        "context_digest": context_digest,
        "issued_at_unix_s": issued,
        "expires_at_unix_s": expires,
        "nonce": nonce,
        "evidence_sha256": evidence_sha256,
        "payload": dict(payload),
    }
    try:
        _validate_payload(kind, body["payload"])
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc
    try:
        outer = {"body": body, "signature_hmac_sha256": _sign(body, key)}
        return canonical_json_bytes(outer)
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc


def _verify_receipt_no_consume(
    receipt_bytes: bytes,
    *,
    expected_kind: str,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    replay_store: ReplayStore,
    key: bytes,
) -> VerifiedReceipt:
    """Private complete verifier; it checks replay state but never mutates it."""

    action_digest, context_digest = _validate_action_context(action, context)
    if not isinstance(receipt_bytes, bytes):
        raise ReceiptError("RECEIPT_BYTES_REQUIRED")
    try:
        outer = loads_strict(receipt_bytes)
        require_exact_keys(outer, ("body", "signature_hmac_sha256"), path="/")
        body = outer["body"]
        require_exact_keys(
            body,
            (
                "schema",
                "kind",
                "issuer",
                "action_digest",
                "context_digest",
                "issued_at_unix_s",
                "expires_at_unix_s",
                "nonce",
                "evidence_sha256",
                "payload",
            ),
            path="/body",
        )
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc
    if body["schema"] != RECEIPT_SCHEMA:
        raise ReceiptError("RECEIPT_SCHEMA_MISMATCH")
    if body["kind"] != expected_kind or expected_kind not in KINDS:
        raise ReceiptError("RECEIPT_KIND_MISMATCH")
    if body["issuer"] != "SYNTHETIC_SOURCE_FREEZE_FIXTURE_ONLY":
        raise ReceiptError("UNTRUSTED_SYNTHETIC_ISSUER")
    _require_sha(body["action_digest"], "/body/action_digest")
    _require_sha(body["context_digest"], "/body/context_digest")
    _require_sha(body["evidence_sha256"], "/body/evidence_sha256")
    if body["action_digest"] != action_digest:
        raise ReceiptError("ACTION_DIGEST_MISMATCH")
    if body["context_digest"] != context_digest:
        raise ReceiptError("CONTEXT_DIGEST_MISMATCH")
    if not isinstance(body["nonce"], str) or not _NONCE.fullmatch(body["nonce"]):
        raise ReceiptError("INVALID_NONCE")
    issued = _number(body["issued_at_unix_s"], "/body/issued_at_unix_s")
    expires = _number(body["expires_at_unix_s"], "/body/expires_at_unix_s")
    now = _number(trusted_now_unix_s, "/trusted_now_unix_s")
    if expires <= issued or expires - issued > MAX_VALIDITY_SECONDS:
        raise ReceiptError("INVALID_VALIDITY_WINDOW")
    if issued - now > MAX_FUTURE_SKEW_SECONDS:
        raise ReceiptError("RECEIPT_NOT_YET_VALID")
    if now > expires:
        raise ReceiptError("STALE_RECEIPT")
    expected_signature = _sign(body, key)
    signature = outer["signature_hmac_sha256"]
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        raise ReceiptError("ATTESTATION_SIGNATURE_INVALID")
    try:
        status = _validate_payload(expected_kind, body["payload"])
    except StrictJSONError as exc:
        raise ReceiptError(str(exc)) from exc
    replay_store.assert_unseen((body["nonce"],))
    return VerifiedReceipt(
        kind=expected_kind,
        nonce=body["nonce"],
        status=status,
        action_digest=body["action_digest"],
        context_digest=body["context_digest"],
        payload=deep_freeze(body["payload"]),
    )


def verify_receipt(
    receipt_bytes: bytes,
    *,
    expected_kind: str,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    replay_store: ReplayStore,
    key: bytes,
) -> VerifiedReceipt:
    """Public read-only receipt verification; never consumes a nonce.

    Nonce commit belongs to a future atomically allowed action.  This package
    cannot produce such an action because every non-ABORT path is scope-locked.
    """

    return _verify_receipt_no_consume(
        receipt_bytes,
        expected_kind=expected_kind,
        action=action,
        context=context,
        trusted_now_unix_s=trusted_now_unix_s,
        replay_store=replay_store,
        key=key,
    )


def admit_backend_request(
    requested_strategy: str,
    *,
    shield_receipt_bytes: bytes | None,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    replay_store: ReplayStore,
    key: bytes,
) -> AdmissionDecision:
    """A direct backend call cannot execute non-ABORT without attestation."""

    try:
        _validate_action_context(action, context, requested_strategy=requested_strategy)
    except ReceiptError as exc:
        return AdmissionDecision(str(requested_strategy), "ABORT", False, (str(exc),), False)
    if requested_strategy == "ABORT":
        return AdmissionDecision("ABORT", "ABORT", True, ("ABORT_ALWAYS_AVAILABLE",), False)
    if shield_receipt_bytes is None:
        return AdmissionDecision(
            requested_strategy,
            "ABORT",
            False,
            ("SHIELD_ATTESTATION_REQUIRED",),
            False,
        )
    try:
        receipt = _verify_receipt_no_consume(
            shield_receipt_bytes,
            expected_kind="SHIELD_ATTESTATION_V2",
            action=action,
            context=context,
            trusted_now_unix_s=trusted_now_unix_s,
            replay_store=replay_store,
            key=key,
        )
    except ReceiptError as exc:
        return AdmissionDecision(requested_strategy, "ABORT", False, (str(exc),), False)
    if receipt.status != "PASS":
        return AdmissionDecision(
            requested_strategy,
            "ABORT",
            False,
            (f"SHIELD_ATTESTATION_{receipt.status}",),
            True,
        )
    return AdmissionDecision(
        requested_strategy,
        "ABORT",
        False,
        ("SOURCE_FREEZE_SCOPE_LOCK",),
        True,
    )


def evaluate_receipt_bound_join(
    requested_strategy: str,
    *,
    receipt_bytes_by_kind: Mapping[str, bytes],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    replay_store: ReplayStore,
    key: bytes,
) -> AdmissionDecision:
    """Replace naked booleans with an ALL_OF receipt join, then retain scope lock."""

    try:
        _validate_action_context(action, context, requested_strategy=requested_strategy)
    except ReceiptError as exc:
        return AdmissionDecision(str(requested_strategy), "ABORT", False, (str(exc),), False)
    if requested_strategy == "ABORT":
        return AdmissionDecision("ABORT", "ABORT", True, ("ABORT_ALWAYS_AVAILABLE",), False)
    if not isinstance(receipt_bytes_by_kind, Mapping):
        return AdmissionDecision(requested_strategy, "ABORT", False, ("RECEIPT_BUNDLE_NOT_OBJECT",), False)
    provided_kinds = tuple(receipt_bytes_by_kind)
    if any(not isinstance(kind, str) for kind in provided_kinds):
        return AdmissionDecision(requested_strategy, "ABORT", False, ("RECEIPT_KIND_KEY_NOT_STRING",), False)
    extra = sorted(set(provided_kinds) - set(KINDS))
    verified: list[VerifiedReceipt] = []
    # Verify every known record that was actually supplied before reasoning
    # about absence.  A corrupt "otherwise complete" bundle must not hide
    # behind a higher-priority missing-kind result.
    for kind in KINDS:
        if kind not in receipt_bytes_by_kind:
            continue
        try:
            verified.append(
                _verify_receipt_no_consume(
                    receipt_bytes_by_kind[kind],
                    expected_kind=kind,
                    action=action,
                    context=context,
                    trusted_now_unix_s=trusted_now_unix_s,
                    replay_store=replay_store,
                    key=key,
                )
            )
        except ReceiptError as exc:
            return AdmissionDecision(requested_strategy, "ABORT", False, (str(exc),), False)
    try:
        replay_store.assert_unseen([receipt.nonce for receipt in verified])
    except ReceiptError as exc:
        return AdmissionDecision(requested_strategy, "ABORT", False, (str(exc),), False)
    if extra:
        return AdmissionDecision(requested_strategy, "ABORT", False, (f"EXTRA_RECEIPT_KIND:{extra}",), False)
    missing = [kind for kind in KINDS if kind not in receipt_bytes_by_kind]
    if missing:
        safety_priority = (
            "FEASIBILITY_150KG_V2",
            "POST_GRASP_V2",
            "SHIELD_ATTESTATION_V2",
            "SYSTEM_BINDING_V2",
            "RUNTIME_GATE_SNAPSHOT_V2",
            "DYNAMICS_GATE_V2",
            "CONTACT_PREFLIGHT_V2",
        )
        first = next(kind for kind in safety_priority if kind in missing)
        return AdmissionDecision(requested_strategy, "ABORT", False, (f"MISSING_RECEIPT_KIND:{first}",), kind_has_attestation(verified))
    non_pass = next((receipt for receipt in verified if receipt.status != "PASS"), None)
    if non_pass is not None:
        return AdmissionDecision(
            requested_strategy,
            "ABORT",
            False,
            (f"{non_pass.kind}_{non_pass.status}",),
            kind_has_attestation(verified),
        )
    return AdmissionDecision(
        requested_strategy,
        "ABORT",
        False,
        ("SOURCE_FREEZE_SCOPE_LOCK",),
        kind_has_attestation(verified),
    )


def kind_has_attestation(receipts: list[VerifiedReceipt]) -> bool:
    return any(
        receipt.kind == "SHIELD_ATTESTATION_V2"
        and receipt.status == "PASS"
        and receipt.payload["capability"] == SHIELD_CAPABILITY
        for receipt in receipts
    )


__all__ = [
    "ACTION_FIELDS",
    "AdmissionDecision",
    "CANONICAL_ABORT_ACTION",
    "CONTEXT_FIELDS",
    "KINDS",
    "MAX_VALIDITY_SECONDS",
    "RECEIPT_SCHEMA",
    "ReceiptError",
    "ReplayStore",
    "SHIELD_CAPABILITY",
    "VerifiedReceipt",
    "admit_backend_request",
    "evaluate_receipt_bound_join",
    "issue_synthetic_receipt",
    "verify_receipt",
]
