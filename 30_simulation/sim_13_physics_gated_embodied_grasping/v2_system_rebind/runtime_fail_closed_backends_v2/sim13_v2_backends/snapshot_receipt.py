"""Fresh action/context-bound gate-snapshot receipts (WO-NC15 backend).

A snapshot receipt binds four digests -- requested action, execution context,
and the 12-gate authority snapshot -- to a single-use nonce and a finite
validity window read from an injected trusted clock.  Verification is
fail-closed: any malformed field, stale timestamp, replayed nonce, or binding
drift rejects the snapshot with an exact ``snapshot_rejected`` reason and the
runtime shield masks the non-ABORT request to the canonical ABORT action.

Trust-boundary honesty notes:

- The HMAC key is a declared public, non-secret package constant.  It provides
  tamper-evidence inside this cooperative in-process fail-closed boundary, not
  cryptographic security against a hostile same-process attacker.
- ``SystemUtcClock`` is the host wall clock; it is *not* a hardware root of
  trust.  ``InjectedClock`` is the deterministic clock used by tests and by
  the deterministic evidence runners.  Both classes are declared on every
  receipt so a clock-class substitution is detectable.
- The replay store persists one marker file per consumed nonce, following the
  unified_r2 run-consumption marker pattern: creation is atomic (``xb``), so a
  nonce can be consumed exactly once per store root.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import math
from pathlib import Path
import time
from typing import Any, Mapping

from .canonical import canonical_digest, canonical_json_bytes, sha256_bytes


RECEIPT_SCHEMA = "SIM13_V2_GATE_SNAPSHOT_RECEIPT_V1"
CONSUMPTION_SCHEMA = "SIM13_V2_SNAPSHOT_NONCE_CONSUMPTION_V1"
RECEIPT_ISSUER = "SIM13_V2_RUNTIME_FAIL_CLOSED_RECEIPT_AUTHORITY_V1"
KEY_CLASS = "PUBLIC_NON_SECRET_COOPERATIVE_FAIL_CLOSED_BOUNDARY_NOT_CRYPTO_ROOT"
RECEIPT_HMAC_KEY = (
    b"SIM13_V2_SNAPSHOT_RECEIPT_PUBLIC_NON_SECRET_KEY_COOPERATIVE_BOUNDARY_V1"
)
MAX_VALIDITY_WINDOW_S = 5.0
SYSTEM_CLOCK_CLASS = "HOST_WALL_CLOCK_UTC_NOT_HARDWARE_ROOT_OF_TRUST"
INJECTED_CLOCK_CLASS = "INJECTED_DETERMINISTIC_CLOCK_FOR_TESTS_AND_EVIDENCE"


class ClockError(ValueError):
    """Raised when a clock cannot supply a finite monotonically read time."""


class SystemUtcClock:
    """Host wall clock; explicitly not a hardware root of trust."""

    clock_class = SYSTEM_CLOCK_CLASS

    def read(self) -> float:
        return float(time.time())


class InjectedClock:
    """Deterministic clock for tests/evidence; never claimed as production."""

    clock_class = INJECTED_CLOCK_CLASS

    def __init__(self, now_s: float) -> None:
        if not math.isfinite(now_s):
            raise ClockError("injected clock start must be finite")
        self._now = float(now_s)

    def read(self) -> float:
        return float(self._now)

    def advance(self, delta_s: float) -> None:
        if not math.isfinite(delta_s) or delta_s < 0.0:
            raise ClockError("clock advance must be finite and nonnegative")
        self._now += float(delta_s)


@dataclass(frozen=True)
class SnapshotReceipt:
    """One fresh, single-use, action/context/snapshot-bound receipt."""

    payload: Mapping[str, Any]
    signature_hmac_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "signature_hmac_sha256": self.signature_hmac_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SnapshotReceipt":
        if not isinstance(value, Mapping):
            raise ValueError("receipt must be a mapping")
        payload = value.get("payload")
        signature = value.get("signature_hmac_sha256")
        if not isinstance(payload, Mapping) or not isinstance(signature, str):
            raise ValueError("malformed snapshot receipt")
        return cls(dict(payload), signature)


@dataclass(frozen=True)
class ReceiptAdmission:
    allowed: bool
    reason_code: str
    consumed_nonce: str | None = None


def _signature(payload: Mapping[str, Any]) -> str:
    return hmac.new(
        RECEIPT_HMAC_KEY, canonical_json_bytes(payload), hashlib.sha256
    ).hexdigest().upper()


def resign_receipt_for_negative_control(
    payload: Mapping[str, Any]
) -> SnapshotReceipt:
    """Re-sign a mutated payload solely so negative controls stay deterministic."""

    copied = dict(payload)
    return SnapshotReceipt(copied, _signature(copied))


class FileReplayStore:
    """Persistent single-use nonce store using atomic marker files.

    One marker file per consumed nonce digest under ``store_root``; the marker
    content is itself canonical JSON so replay evidence stays reproducible.
    """

    def __init__(self, store_root: str | Path) -> None:
        self.store_root = Path(store_root)
        self.store_root.mkdir(parents=True, exist_ok=True)

    def _marker_path(self, nonce: str) -> Path:
        digest = sha256_bytes(nonce.encode("utf-8"))
        return self.store_root / f"{digest}.json"

    def is_consumed(self, nonce: str) -> bool:
        return self._marker_path(nonce).is_file()

    def consume_once(self, nonce: str, *, consumed_at_s: float) -> bool:
        """Atomically consume ``nonce`` exactly once; False means replay."""

        if not isinstance(nonce, str) or not nonce:
            return False
        if not math.isfinite(consumed_at_s):
            raise ClockError("consumption time must be finite")
        marker = self._marker_path(nonce)
        record = {
            "schema": CONSUMPTION_SCHEMA,
            "nonce_sha256": sha256_bytes(nonce.encode("utf-8")),
            "consumed_at_s": float(consumed_at_s),
            "consumption_pattern": "UNIFIED_R2_RUN_CONSUMPTION_SINGLE_USE_MARKER",
        }
        try:
            with marker.open("xb") as handle:
                handle.write(canonical_json_bytes(record) + b"\n")
        except FileExistsError:
            return False
        return True

    @property
    def consumed_count(self) -> int:
        return sum(1 for item in self.store_root.glob("*.json") if item.is_file())


class SnapshotReceiptAuthority:
    """Issues and verifies fresh gate-snapshot receipts."""

    def __init__(self, *, clock: SystemUtcClock | InjectedClock) -> None:
        self.clock = clock

    def issue_receipt(
        self,
        *,
        action: Mapping[str, Any],
        context: Mapping[str, Any],
        gate_snapshot: Mapping[str, Any],
        nonce: str,
        validity_window_s: float,
    ) -> SnapshotReceipt:
        if not isinstance(nonce, str) or not nonce:
            raise ValueError("nonce must be a non-empty string")
        if (
            not math.isfinite(validity_window_s)
            or validity_window_s <= 0.0
            or validity_window_s > MAX_VALIDITY_WINDOW_S
        ):
            raise ValueError("receipt validity window is outside the bounded maximum")
        now = self.clock.read()
        payload: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "issuer": RECEIPT_ISSUER,
            "key_class": KEY_CLASS,
            "clock_class": self.clock.clock_class,
            "issued_at_s": now,
            "not_before_s": now,
            "expires_at_s": now + float(validity_window_s),
            "validity_window_s": float(validity_window_s),
            "nonce": nonce,
            "action_sha256": canonical_digest(action),
            "context_sha256": canonical_digest(context),
            "gate_snapshot_sha256": canonical_digest(gate_snapshot),
            "release_credit": False,
            "next_stage_authorized": False,
        }
        return SnapshotReceipt(payload, _signature(payload))

    def verify_and_consume(
        self,
        *,
        receipt: SnapshotReceipt | None,
        action: Mapping[str, Any],
        context: Mapping[str, Any],
        gate_snapshot: Mapping[str, Any],
        replay_store: FileReplayStore,
    ) -> ReceiptAdmission:
        """Verify freshness/binding and consume the nonce, fail-closed."""

        def reject(reason: str) -> ReceiptAdmission:
            return ReceiptAdmission(False, reason, None)

        if receipt is None:
            return reject("SNAPSHOT_REJECTED_RECEIPT_MISSING")
        if not isinstance(receipt, SnapshotReceipt):
            return reject("SNAPSHOT_REJECTED_MALFORMED")
        payload = receipt.payload
        if not isinstance(payload, Mapping) or not isinstance(
            receipt.signature_hmac_sha256, str
        ):
            return reject("SNAPSHOT_REJECTED_MALFORMED")
        try:
            expected_signature = _signature(payload)
        except (TypeError, ValueError, OverflowError):
            return reject("SNAPSHOT_REJECTED_MALFORMED")
        if not hmac.compare_digest(
            receipt.signature_hmac_sha256, expected_signature
        ):
            return reject("SNAPSHOT_REJECTED_SIGNATURE_INVALID")
        exact_constants = {
            "schema": RECEIPT_SCHEMA,
            "issuer": RECEIPT_ISSUER,
            "key_class": KEY_CLASS,
            "clock_class": self.clock.clock_class,
            "release_credit": False,
            "next_stage_authorized": False,
        }
        if any(payload.get(key) != value for key, value in exact_constants.items()):
            return reject("SNAPSHOT_REJECTED_SCOPE_INVALID")
        time_fields = ("issued_at_s", "not_before_s", "expires_at_s", "validity_window_s")
        if any(
            isinstance(payload.get(name), bool)
            or not isinstance(payload.get(name), (int, float))
            or not math.isfinite(float(payload[name]))
            for name in time_fields
        ):
            return reject("SNAPSHOT_REJECTED_TIME_FIELDS_INVALID")
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
            return reject("SNAPSHOT_REJECTED_VALIDITY_WINDOW_INVALID")
        now = self.clock.read()
        if now < not_before:
            return reject("SNAPSHOT_REJECTED_NOT_YET_VALID")
        if now > expires:
            return reject("SNAPSHOT_REJECTED_STALE")
        if payload.get("action_sha256") != canonical_digest(action):
            return reject("SNAPSHOT_REJECTED_ACTION_MISMATCH")
        if payload.get("context_sha256") != canonical_digest(context):
            return reject("SNAPSHOT_REJECTED_CONTEXT_MISMATCH")
        if payload.get("gate_snapshot_sha256") != canonical_digest(gate_snapshot):
            return reject("SNAPSHOT_REJECTED_GATE_SNAPSHOT_MISMATCH")
        nonce = payload.get("nonce")
        if not isinstance(nonce, str) or not nonce:
            return reject("SNAPSHOT_REJECTED_NONCE_INVALID")
        if not replay_store.consume_once(nonce, consumed_at_s=now):
            return reject("SNAPSHOT_REJECTED_NONCE_REPLAY")
        return ReceiptAdmission(True, "SNAPSHOT_RECEIPT_ACCEPTED_ONCE", nonce)


__all__ = [
    "CONSUMPTION_SCHEMA",
    "FileReplayStore",
    "InjectedClock",
    "INJECTED_CLOCK_CLASS",
    "KEY_CLASS",
    "MAX_VALIDITY_WINDOW_S",
    "RECEIPT_HMAC_KEY",
    "RECEIPT_ISSUER",
    "RECEIPT_SCHEMA",
    "ReceiptAdmission",
    "SnapshotReceipt",
    "SnapshotReceiptAuthority",
    "SYSTEM_CLOCK_CLASS",
    "SystemUtcClock",
    "resign_receipt_for_negative_control",
]
