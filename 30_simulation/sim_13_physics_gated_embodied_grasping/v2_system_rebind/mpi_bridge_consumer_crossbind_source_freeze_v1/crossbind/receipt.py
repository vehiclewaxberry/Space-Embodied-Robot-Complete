"""Signed source-only V3 composition over seven verified preexecution receipts.

There is deliberately no production composite producer in this package. The
only issuable object is a ``SYNTHETIC_SIGNED_COMPOSITION_FIXTURE``. Its seven
preexecution inputs are raw receipt bytes and are verified by the final pinned
preexecution strict parser and HMAC verifier. Successful fixture verification
consumes an independent in-process V3 nonce, but can never authorize execution.
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import re
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .bridge import CrossbindRecord
from .constants import SOURCE_PIN_BY_ID
from .strict_io import sha256_bytes


class ReceiptError(ValueError):
    """A signed V3 composition or one of its source receipts is invalid."""


SYNTHETIC_RECEIPT_KIND = "SYNTHETIC_SIGNED_COMPOSITION_FIXTURE"
PRODUCTION_RECEIPT_KIND = "PRODUCTION_AUTHENTICATED_COMPOSITE_AUTHORIZATION"
PRODUCTION_PRODUCER_STATUS = "NOT_IMPLEMENTED_NO_PRODUCER"
V3_SCHEMA = "SYSTEM_BINDING_V3_SIGNED_COMPOSITION_FIXTURE_V1"
V3_ISSUER = "SYNTHETIC_SOURCE_FREEZE_COMPOSITION_FIXTURE_ONLY"
MAX_VALIDITY_SECONDS = 300.0
ACTION_FIELDS = ("grasp_candidate_id", "capture_timing_id", "strategy_id")
PREEXEC_CONTEXT_FIELDS = ("episode_id", "configuration_id", "authority_epoch", "target_class")
V3_CONTEXT_FIELDS = PREEXEC_CONTEXT_FIELDS + ("mission_phase_id", "reference_frame_id")
CONFIGURATION_MAPPING = {
    "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT"
}
PREEXEC_KINDS = (
    "SYSTEM_BINDING_V2",
    "RUNTIME_GATE_SNAPSHOT_V2",
    "DYNAMICS_GATE_V2",
    "CONTACT_PREFLIGHT_V2",
    "SHIELD_ATTESTATION_V2",
    "FEASIBILITY_150KG_V2",
    "POST_GRASP_V2",
)
_HASH_RE = re.compile(r"^[0-9A-F]{64}$")
_NONCE_RE = re.compile(r"^[A-Za-z0-9._-]{16,128}$")
_SYNTHETIC_PREEXEC_KEY = b"MPI-CROSSBIND-PREEXEC-SYNTHETIC-KEY-ONLY-0001"
_SYNTHETIC_V3_KEY = b"MPI-CROSSBIND-V3-SYNTHETIC-KEY-ONLY-00000001"

PREEXEC_RECEIPT_ENTRY_FIELDS = (
    "kind", "sha256", "nonce", "status", "action_digest", "context_digest",
    "issued_at_unix_s", "expires_at_unix_s", "evidence_sha256",
)
V3_BODY_FIELDS = (
    "schema", "receipt_kind", "issuer", "production_composite_producer_status",
    "urdf_sha256", "interface_sha256", "frame_tree_sha256", "bridge_sha256",
    "bridge_semantic_digest", "crossbind_record_digest", "mass_inertia_binding_sha256",
    "owner_authority_sha256", "intake_gate_sha256", "intake_terminal_sha256",
    "preexec_gate_sha256", "preexec_terminal_sha256",
    "preexec_receipt_verifier_source_sha256", "preexec_strict_json_source_sha256",
    "action", "context", "configuration_mapping", "preexec_action_digest",
    "preexec_context_digest", "preexec_receipt_set_digest", "preexec_receipts",
    "decision", "trusted_clock_scale", "issued_at_unix_s", "expires_at_unix_s", "nonce",
)


@dataclass(frozen=True, slots=True)
class PreexecComposition:
    action_digest: str
    context_digest: str
    ordered_receipts: tuple[Mapping[str, Any], ...]
    receipt_set_digest: str
    common_issued_at_unix_s: float
    common_expires_at_unix_s: float
    decision: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class SyntheticV3Fixture:
    receipt_bytes: bytes
    preexec_receipt_bytes_by_kind: Mapping[str, bytes]
    action: Mapping[str, Any]
    context: Mapping[str, Any]
    trusted_now_unix_s: float
    preexec_key: bytes
    v3_key: bytes


class V3ReplayStore:
    """Independent in-process fixture replay state; never production durable."""

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def consume(self, nonce: str) -> None:
        with self._lock:
            if nonce in self._seen:
                raise ReceiptError("V3_REPLAY_NONCE")
            self._seen.add(nonce)

    @property
    def seen_count(self) -> int:
        with self._lock:
            return len(self._seen)


def _actual_preexec_modules() -> tuple[Any, Any]:
    """Load the final sibling verifier only after exact source pins match."""

    v2_root = Path(__file__).resolve().parents[2]
    for source_id, relative in (
        ("PREEXEC_RECEIPT_VERIFIER_SOURCE", "preexec_security/receipts.py"),
        ("PREEXEC_STRICT_JSON_SOURCE", "preexec_security/strict_json.py"),
    ):
        path = v2_root / "preexecution_binding_security_source_freeze_v1" / relative
        if not path.is_file() or path.is_symlink():
            raise ReceiptError(f"PINNED_PREEXEC_SOURCE_UNAVAILABLE:{source_id}")
        if sha256_bytes(path.read_bytes()) != SOURCE_PIN_BY_ID[source_id]["sha256"]:
            raise ReceiptError(f"PINNED_PREEXEC_SOURCE_DRIFT:{source_id}")
    root_text = str(v2_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    receipts = importlib.import_module(
        "preexecution_binding_security_source_freeze_v1.preexec_security.receipts"
    )
    strict = importlib.import_module(
        "preexecution_binding_security_source_freeze_v1.preexec_security.strict_json"
    )
    return receipts, strict


def _exact_keys(value: Any, expected: tuple[str, ...], code: str) -> None:
    if not isinstance(value, Mapping):
        raise ReceiptError(f"NOT_OBJECT:{code}")
    actual = set(value)
    required = set(expected)
    if actual != required:
        raise ReceiptError(
            f"KEY_SET_MISMATCH:{code}:extra={sorted(actual-required)}:missing={sorted(required-actual)}"
        )


def _require_hash(value: Any, field: str) -> str:
    if not isinstance(value, str) or _HASH_RE.fullmatch(value) is None:
        raise ReceiptError(f"INVALID_SHA256:{field}")
    return value


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReceiptError(f"INVALID_NUMBER:{field}")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ReceiptError(f"INVALID_NUMBER:{field}") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise ReceiptError(f"INVALID_NUMBER:{field}")
    return result


def _validate_action_context(action: Any, context: Any, strict: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        strict.validate_json_domain(action, path="/body/action")
        strict.validate_json_domain(context, path="/body/context")
        strict.require_exact_keys(action, ACTION_FIELDS, path="/body/action")
        strict.require_exact_keys(context, V3_CONTEXT_FIELDS, path="/body/context")
    except Exception as exc:
        raise ReceiptError(str(exc)) from exc
    action_dict = dict(action)
    context_dict = dict(context)
    if any(not isinstance(action_dict[key], str) or not action_dict[key] or len(action_dict[key]) > 128 for key in ACTION_FIELDS):
        raise ReceiptError("INVALID_ACTION_FIELD")
    for key in ("episode_id", "configuration_id", "target_class", "mission_phase_id", "reference_frame_id"):
        if not isinstance(context_dict[key], str) or not context_dict[key] or len(context_dict[key]) > 128:
            raise ReceiptError(f"INVALID_CONTEXT_FIELD:{key}")
    if type(context_dict["authority_epoch"]) is not int or context_dict["authority_epoch"] < 1:
        raise ReceiptError("INVALID_CONTEXT_FIELD:authority_epoch")
    mapped = CONFIGURATION_MAPPING.get(context_dict["configuration_id"])
    if mapped != context_dict["configuration_id"]:
        raise ReceiptError("CONFIGURATION_MAPPING_MISMATCH")
    if context_dict["reference_frame_id"] != "ODR01_DYNAMICS":
        raise ReceiptError("REFERENCE_FRAME_NOT_ODR01_DYNAMICS")
    return action_dict, context_dict


def _preexec_context(v3_context: Mapping[str, Any]) -> dict[str, Any]:
    return {key: v3_context[key] for key in PREEXEC_CONTEXT_FIELDS}


def _preexec_payload(kind: str, strict: Any) -> dict[str, Any]:
    if kind == "SYSTEM_BINDING_V2":
        return {"status": "HOLD", "system_urdf_sha256": "A" * 64}
    if kind == "RUNTIME_GATE_SNAPSHOT_V2":
        names = (
            "ik_reachable", "external_collision_clear", "keep_out_clear", "sim10_gate",
            "safe00_state", "post_grasp_stability_gate", "gripper_configuration_accepted",
            "target_surface_normal_valid", "mechanical_system_binding", "harness_rated_envelope",
            "contact_physics_ready", "route_c_scope_disposition",
        )
        states = {name: "PASS" for name in names}
        return {"status": "PASS", "gate_count": 12, "gate_digest": strict.canonical_digest(states), "gate_states": states}
    if kind == "DYNAMICS_GATE_V2":
        return {"status": "HOLD", "backend_receipt_sha256": "B" * 64}
    if kind == "CONTACT_PREFLIGHT_V2":
        return {"status": "HOLD", "contact_receipt_sha256": "C" * 64}
    if kind == "SHIELD_ATTESTATION_V2":
        return {"status": "PASS", "capability": "SIM13_NON_ABORT_ONLY_THROUGH_FAIL_CLOSED_SHIELD_V2", "shielded": True}
    if kind == "FEASIBILITY_150KG_V2":
        return {
            "status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0,
            "post_capture_rate_deg_s": 3.0633, "verdict": "INFEASIBLE_RATE",
            "sim10_source_sha256": "D" * 64,
        }
    if kind == "POST_GRASP_V2":
        return {
            "status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0,
            "stability_receipt_sha256": "E" * 64,
        }
    raise ReceiptError(f"UNKNOWN_PREEXEC_KIND:{kind}")


def issue_synthetic_preexec_receipt_set(
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    issued_at_unix_s: float = 1000.0,
    expires_at_unix_s: float = 1300.0,
    key: bytes = _SYNTHETIC_PREEXEC_KEY,
) -> dict[str, bytes]:
    preexec, strict = _actual_preexec_modules()
    output: dict[str, bytes] = {}
    for index, kind in enumerate(PREEXEC_KINDS, start=1):
        output[kind] = preexec.issue_synthetic_receipt(
            kind=kind,
            action=dict(action),
            context=dict(context),
            payload=_preexec_payload(kind, strict),
            issued_at_unix_s=issued_at_unix_s,
            expires_at_unix_s=expires_at_unix_s,
            nonce=f"PREEXEC_COMPOSITION_FIXTURE_{index:02d}",
            evidence_sha256=f"{index:X}" * 64,
            key=key,
        )
    return output


def verify_preexec_composition(
    receipt_bytes_by_kind: Mapping[str, bytes],
    *,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    key: bytes,
) -> PreexecComposition:
    """Verify all seven raw preexec receipt bytes using the pinned verifier."""

    preexec, strict = _actual_preexec_modules()
    if not isinstance(receipt_bytes_by_kind, Mapping):
        raise ReceiptError("PREEXEC_RECEIPT_SET_NOT_OBJECT")
    if set(receipt_bytes_by_kind) != set(PREEXEC_KINDS):
        raise ReceiptError(
            f"PREEXEC_RECEIPT_KIND_SET_MISMATCH:extra={sorted(set(receipt_bytes_by_kind)-set(PREEXEC_KINDS))}:missing={sorted(set(PREEXEC_KINDS)-set(receipt_bytes_by_kind))}"
        )
    now = _require_number(trusted_now_unix_s, "trusted_now_unix_s")
    replay_store = preexec.ReplayStore()
    ordered: list[dict[str, Any]] = []
    for kind in PREEXEC_KINDS:
        raw = receipt_bytes_by_kind[kind]
        if not isinstance(raw, bytes):
            raise ReceiptError(f"PREEXEC_RECEIPT_BYTES_REQUIRED:{kind}")
        try:
            verified = preexec.verify_receipt(
                raw,
                expected_kind=kind,
                action=dict(action),
                context=dict(context),
                trusted_now_unix_s=now,
                replay_store=replay_store,
                key=key,
            )
            outer = strict.loads_strict(raw)
        except Exception as exc:
            raise ReceiptError(f"PREEXEC_VERIFICATION_FAILED:{kind}:{exc}") from exc
        body = outer["body"]
        ordered.append(
            {
                "kind": kind,
                "sha256": sha256_bytes(raw),
                "nonce": verified.nonce,
                "status": verified.status,
                "action_digest": verified.action_digest,
                "context_digest": verified.context_digest,
                "issued_at_unix_s": body["issued_at_unix_s"],
                "expires_at_unix_s": body["expires_at_unix_s"],
                "evidence_sha256": body["evidence_sha256"],
            }
        )
    nonces = [item["nonce"] for item in ordered]
    if len(nonces) != len(set(nonces)):
        raise ReceiptError("DUPLICATE_PREEXEC_NONCE_IN_SET")
    action_digests = {item["action_digest"] for item in ordered}
    context_digests = {item["context_digest"] for item in ordered}
    if len(action_digests) != 1:
        raise ReceiptError("MIXED_PREEXEC_ACTION_DIGEST")
    if len(context_digests) != 1:
        raise ReceiptError("MIXED_PREEXEC_CONTEXT_DIGEST")
    common_issued = max(float(item["issued_at_unix_s"]) for item in ordered)
    common_expires = min(float(item["expires_at_unix_s"]) for item in ordered)
    if common_expires <= common_issued or not (common_issued <= now <= common_expires):
        raise ReceiptError("PREEXEC_COMMON_VALIDITY_WINDOW_EMPTY_OR_STALE")
    frozen_ordered = tuple(dict(item) for item in ordered)
    decision = {
        "executed_strategy": "ABORT",
        "allowed": False,
        "reason": "SOURCE_FREEZE_SCOPE_LOCK",
        "composite_authorization": False,
        "release_credit": False,
    }
    return PreexecComposition(
        action_digest=next(iter(action_digests)),
        context_digest=next(iter(context_digests)),
        ordered_receipts=frozen_ordered,
        receipt_set_digest=strict.canonical_digest(list(frozen_ordered)),
        common_issued_at_unix_s=common_issued,
        common_expires_at_unix_s=common_expires,
        decision=decision,
    )


def _fixed_hashes(record: CrossbindRecord) -> dict[str, str]:
    return {
        "frame_tree_sha256": SOURCE_PIN_BY_ID["UNIFIED_R2_FRAME_TREE"]["sha256"],
        "bridge_sha256": SOURCE_PIN_BY_ID["PHYSICAL_DYNAMICS_BRIDGE"]["sha256"],
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "mass_inertia_binding_sha256": SOURCE_PIN_BY_ID["BRIDGED_MASS_INERTIA"]["sha256"],
        "owner_authority_sha256": SOURCE_PIN_BY_ID["OWNER_ODR45"]["sha256"],
        "intake_gate_sha256": SOURCE_PIN_BY_ID["INTAKE_GATE"]["sha256"],
        "intake_terminal_sha256": SOURCE_PIN_BY_ID["INTAKE_TERMINAL"]["sha256"],
        "preexec_gate_sha256": SOURCE_PIN_BY_ID["PREEXEC_GATE"]["sha256"],
        "preexec_terminal_sha256": SOURCE_PIN_BY_ID["PREEXEC_TERMINAL"]["sha256"],
        "preexec_receipt_verifier_source_sha256": SOURCE_PIN_BY_ID["PREEXEC_RECEIPT_VERIFIER_SOURCE"]["sha256"],
        "preexec_strict_json_source_sha256": SOURCE_PIN_BY_ID["PREEXEC_STRICT_JSON_SOURCE"]["sha256"],
    }


def _signature(body: Mapping[str, Any], key: bytes, strict: Any) -> str:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ReceiptError("V3_KEY_TOO_SHORT")
    return hmac.new(key, strict.canonical_json_bytes(dict(body)), hashlib.sha256).hexdigest().upper()


def issue_synthetic_v3_fixture(
    record: CrossbindRecord,
    *,
    preexec_receipt_bytes_by_kind: Mapping[str, bytes],
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    trusted_now_unix_s: float,
    preexec_key: bytes = _SYNTHETIC_PREEXEC_KEY,
    v3_key: bytes = _SYNTHETIC_V3_KEY,
    issued_at_unix_s: float = 1020.0,
    expires_at_unix_s: float = 1280.0,
    nonce: str = "V3_COMPOSITION_FIXTURE_NONCE_0001",
) -> bytes:
    _, strict = _actual_preexec_modules()
    action_dict, context_dict = _validate_action_context(action, context, strict)
    composition = verify_preexec_composition(
        preexec_receipt_bytes_by_kind,
        action=action_dict,
        context=_preexec_context(context_dict),
        trusted_now_unix_s=trusted_now_unix_s,
        key=preexec_key,
    )
    issued = _require_number(issued_at_unix_s, "issued_at_unix_s")
    expires = _require_number(expires_at_unix_s, "expires_at_unix_s")
    if expires <= issued or expires - issued > MAX_VALIDITY_SECONDS:
        raise ReceiptError("INVALID_V3_VALIDITY_WINDOW")
    if issued < composition.common_issued_at_unix_s or expires > composition.common_expires_at_unix_s:
        raise ReceiptError("V3_WINDOW_NOT_CONTAINED_IN_PREEXEC_COMMON_WINDOW")
    if not (issued <= trusted_now_unix_s <= expires):
        raise ReceiptError("V3_RECEIPT_NOT_CURRENT")
    if not isinstance(nonce, str) or _NONCE_RE.fullmatch(nonce) is None:
        raise ReceiptError("INVALID_V3_NONCE")
    body: dict[str, Any] = {
        "schema": V3_SCHEMA,
        "receipt_kind": SYNTHETIC_RECEIPT_KIND,
        "issuer": V3_ISSUER,
        "production_composite_producer_status": PRODUCTION_PRODUCER_STATUS,
        "urdf_sha256": "A" * 64,
        "interface_sha256": "B" * 64,
        **_fixed_hashes(record),
        "action": action_dict,
        "context": context_dict,
        "configuration_mapping": {
            "preexec_configuration_id": context_dict["configuration_id"],
            "v3_configuration_id": CONFIGURATION_MAPPING[context_dict["configuration_id"]],
        },
        "preexec_action_digest": composition.action_digest,
        "preexec_context_digest": composition.context_digest,
        "preexec_receipt_set_digest": composition.receipt_set_digest,
        "preexec_receipts": [dict(item) for item in composition.ordered_receipts],
        "decision": dict(composition.decision),
        "trusted_clock_scale": "UTC_UNIX_SECONDS",
        "issued_at_unix_s": issued,
        "expires_at_unix_s": expires,
        "nonce": nonce,
    }
    return strict.canonical_json_bytes(
        {"body": body, "signature_hmac_sha256": _signature(body, v3_key, strict)}
    )


def validate_system_binding_v3(
    receipt_bytes: bytes,
    record: CrossbindRecord,
    *,
    preexec_receipt_bytes_by_kind: Mapping[str, bytes],
    expected_action: Mapping[str, Any],
    expected_context: Mapping[str, Any],
    trusted_now_unix_s: float,
    replay_store: V3ReplayStore,
    preexec_key: bytes,
    v3_key: bytes,
    expected_urdf_sha256: str = "A" * 64,
    expected_interface_sha256: str = "B" * 64,
) -> dict[str, Any]:
    """Verify, cross-bind and atomically commit one signed synthetic V3 nonce."""

    if not isinstance(receipt_bytes, bytes):
        raise ReceiptError("SERIALIZED_SIGNED_ENVELOPE_BYTES_REQUIRED")
    _, strict = _actual_preexec_modules()
    try:
        outer = strict.loads_strict(receipt_bytes)
        strict.require_exact_keys(outer, ("body", "signature_hmac_sha256"), path="/")
        body = outer["body"]
        strict.require_exact_keys(body, V3_BODY_FIELDS, path="/body")
    except Exception as exc:
        raise ReceiptError(str(exc)) from exc
    if body["schema"] != V3_SCHEMA:
        raise ReceiptError("V3_SCHEMA_MISMATCH")
    kind = body["receipt_kind"]
    if kind == PRODUCTION_RECEIPT_KIND:
        raise ReceiptError(PRODUCTION_PRODUCER_STATUS)
    if kind != SYNTHETIC_RECEIPT_KIND:
        raise ReceiptError(f"V3_RECEIPT_KIND_NOT_PERMITTED:{kind}")
    if body["issuer"] != V3_ISSUER:
        raise ReceiptError("UNTRUSTED_V3_FIXTURE_ISSUER")
    if body["production_composite_producer_status"] != PRODUCTION_PRODUCER_STATUS:
        raise ReceiptError("PRODUCTION_PRODUCER_STATUS_DRIFT")
    signature = outer["signature_hmac_sha256"]
    expected_signature = _signature(body, v3_key, strict)
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected_signature):
        raise ReceiptError("V3_SIGNATURE_INVALID")

    action_dict, context_dict = _validate_action_context(body["action"], body["context"], strict)
    expected_action_dict, expected_context_dict = _validate_action_context(expected_action, expected_context, strict)
    if action_dict != expected_action_dict:
        raise ReceiptError("V3_ACTION_REBIND")
    if context_dict != expected_context_dict:
        raise ReceiptError("V3_CONTEXT_REBIND")
    mapping = body["configuration_mapping"]
    _exact_keys(mapping, ("preexec_configuration_id", "v3_configuration_id"), "configuration_mapping")
    if mapping != {
        "preexec_configuration_id": context_dict["configuration_id"],
        "v3_configuration_id": CONFIGURATION_MAPPING[context_dict["configuration_id"]],
    }:
        raise ReceiptError("CONFIGURATION_MAPPING_MISMATCH")

    composition = verify_preexec_composition(
        preexec_receipt_bytes_by_kind,
        action=action_dict,
        context=_preexec_context(context_dict),
        trusted_now_unix_s=trusted_now_unix_s,
        key=preexec_key,
    )
    fixed = _fixed_hashes(record)
    fixed["urdf_sha256"] = _require_hash(expected_urdf_sha256, "expected_urdf_sha256")
    fixed["interface_sha256"] = _require_hash(expected_interface_sha256, "expected_interface_sha256")
    for field, expected in fixed.items():
        _require_hash(body[field], field)
        if body[field] != expected:
            raise ReceiptError(f"HASH_BINDING_MISMATCH:{field}")
    for field in ("preexec_action_digest", "preexec_context_digest", "preexec_receipt_set_digest"):
        _require_hash(body[field], field)
    if body["preexec_action_digest"] != composition.action_digest:
        raise ReceiptError("PREEXEC_ACTION_DIGEST_MISMATCH")
    if body["preexec_context_digest"] != composition.context_digest:
        raise ReceiptError("PREEXEC_CONTEXT_DIGEST_MISMATCH")
    if body["preexec_receipt_set_digest"] != composition.receipt_set_digest:
        raise ReceiptError("PREEXEC_RECEIPT_SET_DIGEST_MISMATCH")
    if body["preexec_receipts"] != [dict(item) for item in composition.ordered_receipts]:
        raise ReceiptError("PREEXEC_ORDERED_RECEIPT_SET_MISMATCH")
    for index, item in enumerate(body["preexec_receipts"]):
        _exact_keys(item, PREEXEC_RECEIPT_ENTRY_FIELDS, f"preexec_receipts/{index}")
    if body["decision"] != dict(composition.decision):
        raise ReceiptError("V3_DECISION_NOT_ABORT_SOURCE_LOCK")
    if body["trusted_clock_scale"] != "UTC_UNIX_SECONDS":
        raise ReceiptError("TRUSTED_CLOCK_SCALE_MISMATCH")
    issued = _require_number(body["issued_at_unix_s"], "issued_at_unix_s")
    expires = _require_number(body["expires_at_unix_s"], "expires_at_unix_s")
    now = _require_number(trusted_now_unix_s, "trusted_now_unix_s")
    if expires <= issued or expires - issued > MAX_VALIDITY_SECONDS:
        raise ReceiptError("INVALID_V3_VALIDITY_WINDOW")
    if issued < composition.common_issued_at_unix_s or expires > composition.common_expires_at_unix_s:
        raise ReceiptError("V3_WINDOW_NOT_CONTAINED_IN_PREEXEC_COMMON_WINDOW")
    if not (issued <= now <= expires):
        raise ReceiptError("V3_RECEIPT_NOT_CURRENT")
    nonce = body["nonce"]
    if not isinstance(nonce, str) or _NONCE_RE.fullmatch(nonce) is None:
        raise ReceiptError("INVALID_V3_NONCE")

    # Only this final commit mutates state. Every failed path above consumes 0.
    replay_store.consume(nonce)
    return {
        "schema_valid": True,
        "receipt_kind": SYNTHETIC_RECEIPT_KIND,
        "preexec_receipts_verified": len(PREEXEC_KINDS),
        "preexec_receipt_set_digest": composition.receipt_set_digest,
        "action_context_bound": True,
        "time_window_contained": True,
        "v3_nonce_consumed": True,
        "v3_replay_store_scope": "IN_PROCESS_SYNTHETIC_ONLY_NOT_DURABLE",
        "decision": dict(composition.decision),
        "production_composite_producer_status": PRODUCTION_PRODUCER_STATUS,
        "production_authenticated_receipt_present": False,
        "source_lock": True,
        "authorization_credit": False,
    }


def make_synthetic_v3_fixture(record: CrossbindRecord) -> SyntheticV3Fixture:
    action = {
        "grasp_candidate_id": "SYNTHETIC_G0",
        "capture_timing_id": "SYNTHETIC_T0",
        "strategy_id": "S1",
    }
    context = {
        "episode_id": "SYNTHETIC_EPISODE_0001",
        "configuration_id": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
        "authority_epoch": 1,
        "target_class": "NONCOOPERATIVE_DEBRIS_150KG_3DPS",
        "mission_phase_id": "SOURCE_FREEZE_VALIDATOR",
        "reference_frame_id": "ODR01_DYNAMICS",
    }
    preexec_set = issue_synthetic_preexec_receipt_set(action, _preexec_context(context))
    now = 1100.0
    receipt_bytes = issue_synthetic_v3_fixture(
        record,
        preexec_receipt_bytes_by_kind=preexec_set,
        action=action,
        context=context,
        trusted_now_unix_s=now,
    )
    return SyntheticV3Fixture(
        receipt_bytes=receipt_bytes,
        preexec_receipt_bytes_by_kind=preexec_set,
        action=action,
        context=context,
        trusted_now_unix_s=now,
        preexec_key=_SYNTHETIC_PREEXEC_KEY,
        v3_key=_SYNTHETIC_V3_KEY,
    )


__all__ = [
    "ACTION_FIELDS", "CONFIGURATION_MAPPING", "PREEXEC_CONTEXT_FIELDS", "PREEXEC_KINDS",
    "PRODUCTION_PRODUCER_STATUS", "PRODUCTION_RECEIPT_KIND", "ReceiptError",
    "SYNTHETIC_RECEIPT_KIND", "SyntheticV3Fixture", "V3ReplayStore",
    "issue_synthetic_preexec_receipt_set", "issue_synthetic_v3_fixture",
    "make_synthetic_v3_fixture", "validate_system_binding_v3", "verify_preexec_composition",
]
