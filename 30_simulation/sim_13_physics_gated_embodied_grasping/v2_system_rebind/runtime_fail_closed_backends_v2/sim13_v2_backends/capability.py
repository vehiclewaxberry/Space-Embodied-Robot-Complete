"""Backend capability tokens and shield-attestation admission (WO-NC16).

A capability token binds one backend -- identified by the SHA-256 of its
source file -- to one action, one execution context, one nonce, and a finite
validity window.  The token is minted only by the runtime shield after the
fail-closed gate evaluation, and the backend admission interface refuses every
call that arrives without a valid shield attestation.  A direct, unshielded
non-ABORT backend call is rejected with the exact reason
``BACKEND_REJECTS_UNSHIELDED_NON_ABORT`` and masked to the canonical ABORT.

Trust-boundary honesty notes:

- The HMAC key is a declared public, non-secret package constant.  The token
  is tamper-evident inside this cooperative in-process boundary; it is not a
  cryptographic capability against a hostile same-process attacker.
- The capability token is *not* the backend invocation itself: admission is
  re-verified on every call, and the nonce is single-use.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import math
from typing import Any, Mapping

from .canonical import canonical_digest, canonical_json_bytes
from .snapshot_receipt import FileReplayStore


CAPABILITY_SCHEMA = "SIM13_V2_BACKEND_CAPABILITY_TOKEN_V1"
CAPABILITY_ISSUER = "SIM13_V2_RUNTIME_SHIELD_ATTESTATION_V1"
CAPABILITY_KEY_CLASS = (
    "PUBLIC_NON_SECRET_COOPERATIVE_FAIL_CLOSED_BOUNDARY_NOT_CRYPTO_ROOT"
)
CAPABILITY_HMAC_KEY = (
    b"SIM13_V2_CAPABILITY_TOKEN_PUBLIC_NON_SECRET_KEY_COOPERATIVE_BOUNDARY_V1"
)
MAX_CAPABILITY_WINDOW_S = 5.0


class UnshieldedBackendCallError(PermissionError):
    """Raised when a backend is invoked without a valid shield attestation."""


@dataclass(frozen=True)
class CapabilityToken:
    payload: Mapping[str, Any]
    signature_hmac_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "signature_hmac_sha256": self.signature_hmac_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CapabilityToken":
        if not isinstance(value, Mapping):
            raise ValueError("capability token must be a mapping")
        payload = value.get("payload")
        signature = value.get("signature_hmac_sha256")
        if not isinstance(payload, Mapping) or not isinstance(signature, str):
            raise ValueError("malformed capability token")
        return cls(dict(payload), signature)


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason_code: str
    consumed_nonce: str | None = None


def _signature(payload: Mapping[str, Any]) -> str:
    return hmac.new(
        CAPABILITY_HMAC_KEY, canonical_json_bytes(payload), hashlib.sha256
    ).hexdigest().upper()


def resign_capability_for_negative_control(
    payload: Mapping[str, Any]
) -> CapabilityToken:
    """Re-sign a mutated payload solely so negative controls stay deterministic."""

    copied = dict(payload)
    return CapabilityToken(copied, _signature(copied))


class ShieldAttestationAuthority:
    """Mints backend capability tokens; the only attestation issuer."""

    def __init__(self, *, shield_id: str = CAPABILITY_ISSUER) -> None:
        if shield_id != CAPABILITY_ISSUER:
            raise ValueError("the shield attestation identity is fixed")
        self._shield_id = shield_id

    def issue_capability(
        self,
        *,
        backend_id: str,
        backend_source_sha256: str,
        action: Mapping[str, Any],
        context: Mapping[str, Any],
        nonce: str,
        issued_at_s: float,
        validity_window_s: float,
    ) -> CapabilityToken:
        if not isinstance(backend_id, str) or not backend_id:
            raise ValueError("backend_id must be a non-empty string")
        if (
            not isinstance(backend_source_sha256, str)
            or len(backend_source_sha256) != 64
            or any(c not in "0123456789ABCDEF" for c in backend_source_sha256)
        ):
            raise ValueError("backend_source_sha256 must be a 64-hex uppercase digest")
        if not isinstance(nonce, str) or not nonce:
            raise ValueError("nonce must be a non-empty string")
        if not math.isfinite(issued_at_s):
            raise ValueError("issued_at_s must be finite")
        if (
            not math.isfinite(validity_window_s)
            or validity_window_s <= 0.0
            or validity_window_s > MAX_CAPABILITY_WINDOW_S
        ):
            raise ValueError("capability validity window is outside the bounded maximum")
        payload: dict[str, Any] = {
            "schema": CAPABILITY_SCHEMA,
            "issuer": self._shield_id,
            "key_class": CAPABILITY_KEY_CLASS,
            "backend_id": backend_id,
            "backend_source_sha256": backend_source_sha256,
            "issued_at_s": float(issued_at_s),
            "not_before_s": float(issued_at_s),
            "expires_at_s": float(issued_at_s) + float(validity_window_s),
            "validity_window_s": float(validity_window_s),
            "nonce": nonce,
            "action_sha256": canonical_digest(action),
            "context_sha256": canonical_digest(context),
            "release_credit": False,
            "next_stage_authorized": False,
        }
        return CapabilityToken(payload, _signature(payload))


def verify_capability(
    *,
    token: CapabilityToken | None,
    backend_id: str,
    backend_source_sha256: str,
    action: Mapping[str, Any],
    context: Mapping[str, Any],
    now_s: float,
    replay_store: FileReplayStore,
) -> AdmissionDecision:
    """Fail-closed verification of one capability token for one call."""

    def reject(reason: str) -> AdmissionDecision:
        return AdmissionDecision(False, reason, None)

    if token is None:
        return reject("BACKEND_REJECTS_UNSHIELDED_NON_ABORT")
    if not isinstance(token, CapabilityToken):
        return reject("CAPABILITY_TOKEN_MALFORMED")
    payload = token.payload
    if not isinstance(payload, Mapping) or not isinstance(
        token.signature_hmac_sha256, str
    ):
        return reject("CAPABILITY_TOKEN_MALFORMED")
    try:
        expected_signature = _signature(payload)
    except (TypeError, ValueError, OverflowError):
        return reject("CAPABILITY_TOKEN_MALFORMED")
    if not hmac.compare_digest(token.signature_hmac_sha256, expected_signature):
        return reject("CAPABILITY_TOKEN_SIGNATURE_INVALID")
    exact_constants = {
        "schema": CAPABILITY_SCHEMA,
        "issuer": CAPABILITY_ISSUER,
        "key_class": CAPABILITY_KEY_CLASS,
        "release_credit": False,
        "next_stage_authorized": False,
    }
    if any(payload.get(key) != value for key, value in exact_constants.items()):
        return reject("CAPABILITY_TOKEN_SCOPE_INVALID")
    if payload.get("backend_id") != backend_id:
        return reject("CAPABILITY_TOKEN_BACKEND_MISMATCH")
    if payload.get("backend_source_sha256") != backend_source_sha256:
        return reject("CAPABILITY_TOKEN_BACKEND_SOURCE_MISMATCH")
    time_fields = ("issued_at_s", "not_before_s", "expires_at_s", "validity_window_s")
    if any(
        isinstance(payload.get(name), bool)
        or not isinstance(payload.get(name), (int, float))
        or not math.isfinite(float(payload[name]))
        for name in time_fields
    ):
        return reject("CAPABILITY_TOKEN_TIME_FIELDS_INVALID")
    issued = float(payload["issued_at_s"])
    not_before = float(payload["not_before_s"])
    expires = float(payload["expires_at_s"])
    window = float(payload["validity_window_s"])
    if (
        window <= 0.0
        or window > MAX_CAPABILITY_WINDOW_S
        or not_before != issued
        or expires != issued + window
    ):
        return reject("CAPABILITY_TOKEN_VALIDITY_WINDOW_INVALID")
    if not math.isfinite(now_s):
        return reject("CAPABILITY_TOKEN_CLOCK_INVALID")
    if now_s < not_before:
        return reject("CAPABILITY_TOKEN_NOT_YET_VALID")
    if now_s > expires:
        return reject("CAPABILITY_TOKEN_STALE")
    if payload.get("action_sha256") != canonical_digest(action):
        return reject("CAPABILITY_TOKEN_ACTION_MISMATCH")
    if payload.get("context_sha256") != canonical_digest(context):
        return reject("CAPABILITY_TOKEN_CONTEXT_MISMATCH")
    nonce = payload.get("nonce")
    if not isinstance(nonce, str) or not nonce:
        return reject("CAPABILITY_TOKEN_NONCE_INVALID")
    if not replay_store.consume_once(nonce, consumed_at_s=now_s):
        return reject("CAPABILITY_TOKEN_NONCE_REPLAY")
    return AdmissionDecision(True, "CAPABILITY_TOKEN_ACCEPTED_ONCE", nonce)


class ShieldedBackendAdmission:
    """Mandatory shield-attestation admission interface for one backend.

    ``admit`` is the only path through which the wrapped backend callable may
    run.  ``backend_source_sha256`` is computed once from the backend source
    file at construction; a token bound to any other source digest is rejected.
    """

    def __init__(
        self,
        *,
        backend_id: str,
        backend_source_sha256: str,
    ) -> None:
        if not isinstance(backend_id, str) or not backend_id:
            raise ValueError("backend_id must be a non-empty string")
        if (
            not isinstance(backend_source_sha256, str)
            or len(backend_source_sha256) != 64
        ):
            raise ValueError("backend_source_sha256 must be a 64-hex digest")
        self.backend_id = backend_id
        self.backend_source_sha256 = backend_source_sha256.upper()

    def admit(
        self,
        *,
        token: CapabilityToken | None,
        action: Mapping[str, Any],
        context: Mapping[str, Any],
        now_s: float,
        replay_store: FileReplayStore,
    ) -> AdmissionDecision:
        return verify_capability(
            token=token,
            backend_id=self.backend_id,
            backend_source_sha256=self.backend_source_sha256,
            action=action,
            context=context,
            now_s=now_s,
            replay_store=replay_store,
        )


__all__ = [
    "AdmissionDecision",
    "CAPABILITY_HMAC_KEY",
    "CAPABILITY_ISSUER",
    "CAPABILITY_KEY_CLASS",
    "CAPABILITY_SCHEMA",
    "CapabilityToken",
    "MAX_CAPABILITY_WINDOW_S",
    "ShieldAttestationAuthority",
    "ShieldedBackendAdmission",
    "UnshieldedBackendCallError",
    "resign_capability_for_negative_control",
    "verify_capability",
]
