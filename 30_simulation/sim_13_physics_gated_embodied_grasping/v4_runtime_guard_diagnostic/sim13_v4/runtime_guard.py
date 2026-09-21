"""Action/context/snapshot-bound diagnostic capabilities.

The key, clock, issuer and nonce store in this module are explicitly diagnostic
fixtures.  They demonstrate fail-closed semantics; they are not suitable for a
production trust boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import math
import threading
from typing import Any, Mapping

from .canonical import canonical_digest, canonical_json_bytes


DIAGNOSTIC_KEY_CLASS = "PUBLIC_TEST_KEY_NON_SECRET_NON_PRODUCTION"
DIAGNOSTIC_CLOCK_CLASS = "INJECTED_DETERMINISTIC_CLOCK_NOT_TRUSTED_PRODUCTION"
DIAGNOSTIC_ISSUER = "SIM13_V4_SYNTHETIC_SHIELD_V1"
DIAGNOSTIC_CAPABILITY_SCOPE = "SYNTHETIC_NON_ABORT_NUMERICAL_STEP_ONLY"
DIAGNOSTIC_HMAC_KEY = b"SIM13_V4_PUBLIC_DIAGNOSTIC_KEY_NOT_SECRET_NOT_PRODUCTION_V1"
MAX_VALIDITY_WINDOW_S = 5.0
NONCE_PERSISTENCE_BOUNDARY = (
    "SINGLE_CANONICAL_MODULE_INSTANCE_LIFETIME_SHARED_THREAD_SAFE_ONLY__"
    "NO_IMPORTLIB_RELOAD_DUPLICATE_MODULE_INSTANCE_CROSS_PROCESS_OR_RESTART_"
    "PERSISTENCE_CLAIM"
)
REQUIRED_SYNTHETIC_GATES = (
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


@dataclass(frozen=True)
class DiagnosticAction:
    grasp_candidate_id: str
    capture_timing_id: str
    strategy_id: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value
            for value in (
                self.grasp_candidate_id,
                self.capture_timing_id,
                self.strategy_id,
            )
        ):
            raise ValueError("action identifiers must be non-empty strings")
        if self.strategy_id not in {"S1", "S3a", "ABORT"}:
            raise ValueError("unsupported strategy_id")
        canonical_abort = (
            self.grasp_candidate_id == "__ABORT__"
            and self.capture_timing_id == "__ABORT__"
        )
        if (self.strategy_id == "ABORT") != canonical_abort:
            raise ValueError("ABORT must use canonical identifiers")

    @property
    def is_abort(self) -> bool:
        return self.strategy_id == "ABORT"

    def as_dict(self) -> dict[str, str]:
        return {
            "grasp_candidate_id": self.grasp_candidate_id,
            "capture_timing_id": self.capture_timing_id,
            "strategy_id": self.strategy_id,
        }

    @classmethod
    def abort(cls) -> "DiagnosticAction":
        return cls("__ABORT__", "__ABORT__", "ABORT")


def synthetic_gate_snapshot(
    *, overrides: Mapping[str, str] | None = None
) -> dict[str, object]:
    gates = {name: "PASS" for name in REQUIRED_SYNTHETIC_GATES}
    gates.update(dict(overrides or {}))
    if set(gates) != set(REQUIRED_SYNTHETIC_GATES):
        raise ValueError("synthetic snapshot must contain exactly twelve gates")
    if any(value not in {"PASS", "FAIL", "UNKNOWN"} for value in gates.values()):
        raise ValueError("invalid gate state")
    return {
        "snapshot_class": "SYNTHETIC_ALL_PASS_KERNEL_FIXTURE_NOT_CURRENT_SYSTEM",
        "gates": gates,
        "current_system_binding_passed": False,
        "runtime_production_gate_passed": False,
        "contact_grasp_gate_passed": False,
    }


@dataclass
class DiagnosticClock:
    now_s: float
    clock_class: str = DIAGNOSTIC_CLOCK_CLASS

    def __post_init__(self) -> None:
        if not math.isfinite(self.now_s):
            raise ValueError("diagnostic clock must be finite")
        if self.clock_class != DIAGNOSTIC_CLOCK_CLASS:
            raise ValueError("only the explicit non-production clock is admitted")

    def read(self) -> float:
        return float(self.now_s)

    def advance(self, delta_s: float) -> None:
        if not math.isfinite(delta_s) or delta_s < 0.0:
            raise ValueError("clock advance must be finite and nonnegative")
        self.now_s += float(delta_s)


def _make_canonical_module_nonce_api():
    """Keep mutable nonce state closure-private and expose no clearing hook."""

    lock = threading.Lock()
    consumed: set[str] = set()

    def consume_once(nonce: str) -> bool:
        with lock:
            if nonce in consumed:
                return False
            consumed.add(nonce)
            return True

    def is_consumed(nonce: str) -> bool:
        with lock:
            return nonce in consumed

    def count() -> int:
        with lock:
            return len(consumed)

    return consume_once, is_consumed, count


(
    _consume_canonical_module_nonce_once,
    _canonical_module_nonce_is_consumed,
    _canonical_module_nonce_count,
) = (
    _make_canonical_module_nonce_api()
)


class NonceLedger:
    """View of one canonical module instance's shared, locked nonce store.

    Constructing another view does not create an isolated replay domain.  There
    is deliberately no reset/clear method.  Persistence across ``importlib``
    reload, duplicate module instances, processes, or interpreter restart is
    not claimed.
    """

    __slots__ = ()

    def consume_once(self, nonce: str) -> bool:
        if not isinstance(nonce, str) or not nonce:
            return False
        return _consume_canonical_module_nonce_once(nonce)

    def is_consumed(self, nonce: str) -> bool:
        return _canonical_module_nonce_is_consumed(nonce)

    @property
    def consumed_count(self) -> int:
        return _canonical_module_nonce_count()


@dataclass(frozen=True)
class DiagnosticCapability:
    payload: Mapping[str, object]
    signature_hmac_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "payload": dict(self.payload),
            "signature_hmac_sha256": self.signature_hmac_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "DiagnosticCapability":
        payload = value.get("payload")
        signature = value.get("signature_hmac_sha256")
        if not isinstance(payload, Mapping) or not isinstance(signature, str):
            raise ValueError("malformed diagnostic capability")
        return cls(dict(payload), signature)


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    executed_action: DiagnosticAction
    reason_code: str
    consumed_nonce: str | None


def _signature(payload: Mapping[str, object]) -> str:
    return hmac.new(
        DIAGNOSTIC_HMAC_KEY,
        canonical_json_bytes(payload),
        hashlib.sha256,
    ).hexdigest().upper()


def diagnostic_resign_capability(
    payload: Mapping[str, object]
) -> DiagnosticCapability:
    """Re-sign a mutated payload solely for deterministic negative controls."""

    copied = dict(payload)
    return DiagnosticCapability(copied, _signature(copied))


def _snapshot_is_admissible(snapshot: Mapping[str, object]) -> bool:
    gates = snapshot.get("gates")
    return (
        snapshot.get("snapshot_class")
        == "SYNTHETIC_ALL_PASS_KERNEL_FIXTURE_NOT_CURRENT_SYSTEM"
        and isinstance(gates, Mapping)
        and set(gates) == set(REQUIRED_SYNTHETIC_GATES)
        and all(gates[name] == "PASS" for name in REQUIRED_SYNTHETIC_GATES)
        and snapshot.get("current_system_binding_passed") is False
        and snapshot.get("runtime_production_gate_passed") is False
        and snapshot.get("contact_grasp_gate_passed") is False
    )


class DiagnosticShield:
    def __init__(
        self,
        *,
        clock: DiagnosticClock,
    ) -> None:
        self.clock = clock
        self.nonce_ledger = NonceLedger()

    def issue_capability(
        self,
        *,
        action: DiagnosticAction,
        context: Mapping[str, object],
        gate_snapshot: Mapping[str, object],
        nonce: str,
        validity_window_s: float,
    ) -> DiagnosticCapability:
        if action.is_abort:
            raise ValueError("ABORT does not require a non-ABORT capability")
        if not isinstance(nonce, str) or not nonce:
            raise ValueError("nonce must be a non-empty string")
        if (
            not math.isfinite(validity_window_s)
            or validity_window_s <= 0.0
            or validity_window_s > MAX_VALIDITY_WINDOW_S
        ):
            raise ValueError("capability validity window is outside diagnostic bound")
        if not _snapshot_is_admissible(gate_snapshot):
            raise ValueError("synthetic snapshot is not admissible for capability issue")
        now = self.clock.read()
        backend_id = context.get("backend_id")
        if not isinstance(backend_id, str) or not backend_id:
            raise ValueError("context must bind a backend_id")
        payload: dict[str, object] = {
            "schema": "SIM13_V4_DIAGNOSTIC_CAPABILITY_V1",
            "scope": DIAGNOSTIC_CAPABILITY_SCOPE,
            "issuer": DIAGNOSTIC_ISSUER,
            "key_class": DIAGNOSTIC_KEY_CLASS,
            "clock_class": DIAGNOSTIC_CLOCK_CLASS,
            "issued_at_s": now,
            "not_before_s": now,
            "expires_at_s": now + float(validity_window_s),
            "validity_window_s": float(validity_window_s),
            "nonce": nonce,
            "backend_id": backend_id,
            "action_sha256": canonical_digest(action.as_dict()),
            "context_sha256": canonical_digest(context),
            "gate_snapshot_sha256": canonical_digest(gate_snapshot),
            "current_system_binding_passed": False,
            "runtime_production_gate_passed": False,
            "release_credit": False,
        }
        return DiagnosticCapability(payload, _signature(payload))

    def authorize_and_consume(
        self,
        *,
        action: DiagnosticAction,
        context: Mapping[str, object],
        gate_snapshot: Mapping[str, object],
        capability: DiagnosticCapability | None,
    ) -> AdmissionDecision:
        if action.is_abort:
            return AdmissionDecision(True, action, "ABORT_ALWAYS_AVAILABLE", None)

        def deny(reason: str) -> AdmissionDecision:
            return AdmissionDecision(False, DiagnosticAction.abort(), reason, None)

        if capability is None:
            return deny("CAPABILITY_MISSING")
        payload = capability.payload
        if not hmac.compare_digest(capability.signature_hmac_sha256, _signature(payload)):
            return deny("CAPABILITY_SIGNATURE_INVALID")
        exact_constants = {
            "schema": "SIM13_V4_DIAGNOSTIC_CAPABILITY_V1",
            "scope": DIAGNOSTIC_CAPABILITY_SCOPE,
            "issuer": DIAGNOSTIC_ISSUER,
            "key_class": DIAGNOSTIC_KEY_CLASS,
            "clock_class": DIAGNOSTIC_CLOCK_CLASS,
            "current_system_binding_passed": False,
            "runtime_production_gate_passed": False,
            "release_credit": False,
        }
        if any(payload.get(key) != value for key, value in exact_constants.items()):
            return deny("CAPABILITY_SCOPE_OR_AUTHORITY_INVALID")
        numeric_names = (
            "issued_at_s",
            "not_before_s",
            "expires_at_s",
            "validity_window_s",
        )
        if any(
            isinstance(payload.get(name), bool)
            or not isinstance(payload.get(name), (int, float))
            or not math.isfinite(float(payload[name]))
            for name in numeric_names
        ):
            return deny("CAPABILITY_TIME_FIELDS_INVALID")
        issued = float(payload["issued_at_s"])
        not_before = float(payload["not_before_s"])
        expires = float(payload["expires_at_s"])
        window = float(payload["validity_window_s"])
        if (
            window <= 0.0
            or window > MAX_VALIDITY_WINDOW_S
            or not_before != issued
            or expires != issued + window
        ):
            return deny("CAPABILITY_VALIDITY_WINDOW_INVALID")
        now = self.clock.read()
        if now < not_before:
            return deny("CAPABILITY_NOT_YET_VALID")
        if now > expires:
            return deny("CAPABILITY_STALE")
        if payload.get("action_sha256") != canonical_digest(action.as_dict()):
            return deny("CAPABILITY_ACTION_MISMATCH")
        if payload.get("context_sha256") != canonical_digest(context):
            return deny("CAPABILITY_CONTEXT_MISMATCH")
        if payload.get("gate_snapshot_sha256") != canonical_digest(gate_snapshot):
            return deny("CAPABILITY_GATE_SNAPSHOT_MISMATCH")
        if not _snapshot_is_admissible(gate_snapshot):
            return deny("CAPABILITY_GATE_SNAPSHOT_NOT_ADMISSIBLE")
        backend_id = context.get("backend_id")
        if payload.get("backend_id") != backend_id:
            return deny("CAPABILITY_BACKEND_MISMATCH")
        nonce = payload.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            return deny("CAPABILITY_NONCE_INVALID")
        if not self.nonce_ledger.consume_once(nonce):
            return deny("CAPABILITY_NONCE_REPLAY")
        return AdmissionDecision(True, action, "CAPABILITY_ACCEPTED_ONCE", nonce)


__all__ = (
    "AdmissionDecision",
    "DIAGNOSTIC_CAPABILITY_SCOPE",
    "DIAGNOSTIC_CLOCK_CLASS",
    "DIAGNOSTIC_HMAC_KEY",
    "DIAGNOSTIC_ISSUER",
    "DIAGNOSTIC_KEY_CLASS",
    "DiagnosticAction",
    "DiagnosticCapability",
    "DiagnosticClock",
    "DiagnosticShield",
    "MAX_VALIDITY_WINDOW_S",
    "NONCE_PERSISTENCE_BOUNDARY",
    "NonceLedger",
    "REQUIRED_SYNTHETIC_GATES",
    "diagnostic_resign_capability",
    "synthetic_gate_snapshot",
)
