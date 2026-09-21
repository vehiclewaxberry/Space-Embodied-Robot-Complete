"""Read-only, hash-bound sim10 150 kg / 3 deg/s veto diagnostic."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Mapping

import yaml

from .canonical import canonical_digest, canonical_json_bytes, file_record
from .runtime_guard import (
    DIAGNOSTIC_HMAC_KEY,
    DiagnosticAction,
)


V4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = V4_ROOT.parents[2]
SIM10_GATE_PATH = (
    PROJECT_ROOT
    / "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json"
)
SIM10_SUMMARY_PATH = (
    PROJECT_ROOT
    / "30_simulation/sim_10_mission_feasibility/results/sim_10_scan_summary.json"
)
SIM10_PARAMETER_CARD_PATH = (
    PROJECT_ROOT / "20_engineering/config/mission_feasibility/scan_v0.yaml"
)
SIM10_ANCHOR_SOURCE_PATH = (
    PROJECT_ROOT / "30_simulation/sim_10_mission_feasibility/src/scan_grid.py"
)
EXPECTED_SIM10_GATE_SHA256 = (
    "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67"
)
EXPECTED_SIM10_SUMMARY_SHA256 = (
    "63D84CE5CA84E9B9DE8C2833577C9645FF2060874B8AB5E081EE7672D0046FC5"
)
EXPECTED_SIM10_PARAMETER_CARD_SHA256 = (
    "856F1E30DE47CA5B3F505F9FE5BD5CD22A75E448EC916B42D9C330F7A62E28EA"
)
EXPECTED_SIM10_ANCHOR_SOURCE_SHA256 = (
    "FBEA1EB8AC459ABA364683AF9C6BE668154FF036ADEDCCC441B5D32CFFF4D5C4"
)
ANCHOR_ID = "debris_sim06"
ANCHOR_TARGET_MASS_KG = 150.0
ANCHOR_TUMBLE_DPS = 3.0
ANCHOR_REGION = "INFEASIBLE_RATE"
ANCHOR_W_PLUS_DPS = 3.0633304945807067
VETO_RECEIPT_SCOPE = (
    "HISTORICAL_SIM10_HASH_BOUND_ACTION_VETO_DIAGNOSTIC_NOT_CURRENT_R2_PASS"
)


@dataclass(frozen=True)
class TargetRequest:
    target_id: str
    target_mass_kg: float
    tumble_rate_dps: float

    def __post_init__(self) -> None:
        if not self.target_id:
            raise ValueError("target_id must be non-empty")
        if isinstance(self.target_mass_kg, bool) or not isinstance(
            self.target_mass_kg, (int, float)
        ):
            raise TypeError("target mass must be numeric")
        if isinstance(self.tumble_rate_dps, bool) or not isinstance(
            self.tumble_rate_dps, (int, float)
        ):
            raise TypeError("tumble rate must be numeric")
        if not math.isfinite(self.target_mass_kg) or self.target_mass_kg <= 0.0:
            raise ValueError("target mass must be positive and finite")
        if not math.isfinite(self.tumble_rate_dps) or self.tumble_rate_dps < 0.0:
            raise ValueError("tumble rate must be finite and nonnegative")

    def as_dict(self) -> dict[str, object]:
        return {
            "target_id": self.target_id,
            "target_mass_kg": float(self.target_mass_kg),
            "tumble_rate_dps": float(self.tumble_rate_dps),
        }


def debris_150kg_3dps_request() -> TargetRequest:
    return TargetRequest("target_debris_v0", 150.0, 3.0)


@dataclass(frozen=True)
class VetoReceipt:
    payload: Mapping[str, object]
    signature_hmac_sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "payload": dict(self.payload),
            "signature_hmac_sha256": self.signature_hmac_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "VetoReceipt":
        payload = value.get("payload")
        signature = value.get("signature_hmac_sha256")
        if not isinstance(payload, Mapping) or not isinstance(signature, str):
            raise ValueError("malformed veto receipt")
        return cls(dict(payload), signature)


@dataclass(frozen=True)
class VetoDecision:
    allowed: bool
    executed_action: DiagnosticAction
    reason_code: str
    receipt_verified: bool
    historical_sim10_pass_inherited_to_current_system: bool = False


def _signature(payload: Mapping[str, object]) -> str:
    return hmac.new(
        DIAGNOSTIC_HMAC_KEY,
        canonical_json_bytes(payload),
        hashlib.sha256,
    ).hexdigest().upper()


def diagnostic_resign_veto_payload(payload: Mapping[str, object]) -> VetoReceipt:
    """Re-sign a mutated receipt only to exercise semantic drift controls."""

    copied = dict(payload)
    return VetoReceipt(copied, _signature(copied))


def _anchor_source_literals() -> dict[str, float]:
    tree = ast.parse(
        SIM10_ANCHOR_SOURCE_PATH.read_text(encoding="utf-8"),
        filename=str(SIM10_ANCHOR_SOURCE_PATH),
    )
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        entries: dict[str, ast.AST] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                entries[key.value] = value
        anchor_node = entries.get("anchor")
        if not (
            isinstance(anchor_node, ast.Constant)
            and anchor_node.value == ANCHOR_ID
        ):
            continue
        mass_node = entries.get("m_t")
        speed_node = entries.get("omega_dps")
        if not (
            isinstance(mass_node, ast.Constant)
            and isinstance(mass_node.value, (int, float))
            and not isinstance(mass_node.value, bool)
            and isinstance(speed_node, ast.Constant)
            and isinstance(speed_node.value, (int, float))
            and not isinstance(speed_node.value, bool)
        ):
            raise ValueError("SIM10_ANCHOR_SOURCE_TYPES_UNKNOWN")
        return {
            "target_mass_kg": float(mass_node.value),
            "tumble_rate_dps": float(speed_node.value),
        }
    raise ValueError("SIM10_ANCHOR_SOURCE_DEBRIS_ROW_UNKNOWN")


def _load_hash_bound_anchor() -> dict[str, object]:
    gate_record = file_record(SIM10_GATE_PATH, PROJECT_ROOT)
    summary_record = file_record(SIM10_SUMMARY_PATH, PROJECT_ROOT)
    parameter_card_record = file_record(SIM10_PARAMETER_CARD_PATH, PROJECT_ROOT)
    anchor_source_record = file_record(SIM10_ANCHOR_SOURCE_PATH, PROJECT_ROOT)
    if gate_record["sha256"] != EXPECTED_SIM10_GATE_SHA256:
        raise ValueError("SIM10_GATE_HASH_DRIFT")
    if summary_record["sha256"] != EXPECTED_SIM10_SUMMARY_SHA256:
        raise ValueError("SIM10_SUMMARY_HASH_DRIFT")
    if parameter_card_record["sha256"] != EXPECTED_SIM10_PARAMETER_CARD_SHA256:
        raise ValueError("SIM10_PARAMETER_CARD_HASH_DRIFT")
    if anchor_source_record["sha256"] != EXPECTED_SIM10_ANCHOR_SOURCE_SHA256:
        raise ValueError("SIM10_ANCHOR_SOURCE_HASH_DRIFT")
    gate = json.loads(SIM10_GATE_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SIM10_SUMMARY_PATH.read_text(encoding="utf-8"))
    parameter_card = yaml.safe_load(
        SIM10_PARAMETER_CARD_PATH.read_text(encoding="utf-8")
    )
    source_literals = _anchor_source_literals()
    if gate.get("schema_version") != "sim10-gate-v1":
        raise ValueError("SIM10_GATE_SCHEMA_UNKNOWN")
    if gate.get("verdict") != "SIM10_GATES_PASS":
        raise ValueError("SIM10_GATE_VERDICT_UNKNOWN")
    x1 = gate.get("gates", {}).get("X1_anchors_vs_sim06", {})
    if x1.get("pass") is not True:
        raise ValueError("SIM10_X1_UNKNOWN_OR_FAIL")
    matches = [
        item
        for item in x1.get("checks", [])
        if item.get("anchor") == ANCHOR_ID
    ]
    if len(matches) != 1:
        raise ValueError("SIM10_GATE_ANCHOR_UNKNOWN")
    gate_anchor = matches[0]
    summary_anchor = summary.get("anchors", {}).get(ANCHOR_ID)
    if not isinstance(summary_anchor, Mapping):
        raise ValueError("SIM10_SUMMARY_ANCHOR_UNKNOWN")
    if not (
        gate_anchor.get("ok") is True
        and gate_anchor.get("region") == ANCHOR_REGION
        and gate_anchor.get("region_expected") == ANCHOR_REGION
        and summary_anchor.get("region_default_tier") == ANCHOR_REGION
        and abs(float(gate_anchor.get("w_plus_dps")) - ANCHOR_W_PLUS_DPS) <= 1.0e-15
        and abs(float(summary_anchor.get("w_plus_dps")) - ANCHOR_W_PLUS_DPS)
        <= 1.0e-15
    ):
        raise ValueError("SIM10_ANCHOR_CONTENT_DRIFT")
    g1 = parameter_card.get("scan", {}).get("geometry_classes", {}).get(
        "G1_slender", {}
    )
    if not (
        parameter_card.get("version") == "v0"
        and g1.get("calibration_target") == "target_debris_v0"
        and isinstance(g1.get("calibration_mass_kg"), (int, float))
        and not isinstance(g1.get("calibration_mass_kg"), bool)
        and float(g1["calibration_mass_kg"]) == ANCHOR_TARGET_MASS_KG
        and source_literals == {
            "target_mass_kg": ANCHOR_TARGET_MASS_KG,
            "tumble_rate_dps": ANCHOR_TUMBLE_DPS,
        }
    ):
        raise ValueError("SIM10_PARAMETER_OR_SOURCE_ANCHOR_DRIFT")
    return {
        "anchor_id": ANCHOR_ID,
        "target_mass_kg": ANCHOR_TARGET_MASS_KG,
        "tumble_rate_dps": ANCHOR_TUMBLE_DPS,
        "w_plus_dps": ANCHOR_W_PLUS_DPS,
        "region": ANCHOR_REGION,
        "gate": gate_record,
        "summary": summary_record,
        "parameter_card": parameter_card_record,
        "anchor_source": anchor_source_record,
        "mass_speed_proof": {
            "parameter_card_calibration_mass_kg": float(
                g1["calibration_mass_kg"]
            ),
            "anchor_source_target_mass_kg": source_literals["target_mass_kg"],
            "anchor_source_tumble_rate_dps": source_literals["tumble_rate_dps"],
        },
    }


class Sim10MissionVeto:
    def issue_veto_receipt(
        self,
        *,
        action: DiagnosticAction,
        gate_snapshot: Mapping[str, object],
        target: TargetRequest,
    ) -> VetoReceipt:
        if action.is_abort:
            raise ValueError("ABORT does not need a mission veto receipt")
        if target != debris_150kg_3dps_request():
            raise ValueError("ONLY_150KG_3DPS_ANCHOR_IS_DEFINED")
        anchor = _load_hash_bound_anchor()
        payload: dict[str, object] = {
            "schema": "SIM13_V4_SIM10_VETO_RECEIPT_V1",
            "scope": VETO_RECEIPT_SCOPE,
            "action_sha256": canonical_digest(action.as_dict()),
            "gate_snapshot_sha256": canonical_digest(gate_snapshot),
            "target_sha256": canonical_digest(target.as_dict()),
            "target": target.as_dict(),
            "anchor_id": anchor["anchor_id"],
            "anchor_region": anchor["region"],
            "anchor_w_plus_dps": anchor["w_plus_dps"],
            "sim10_gate_sha256": anchor["gate"]["sha256"],
            "sim10_summary_sha256": anchor["summary"]["sha256"],
            "sim10_parameter_card_sha256": anchor["parameter_card"]["sha256"],
            "sim10_anchor_source_sha256": anchor["anchor_source"]["sha256"],
            "mass_speed_source_proof": anchor["mass_speed_proof"],
            "veto": True,
            "canonical_outcome": "MASK_TO_ABORT_ONLY",
            "reason_code": "MISSION_VETO_INFEASIBLE_RATE",
            "historical_sim10_gate_pass_inherited_to_current_system": False,
            "current_r2_feasibility_passed": False,
            "contact_grasp_gate_passed": False,
            "release_credit": False,
        }
        return VetoReceipt(payload, _signature(payload))

    def decide(
        self,
        *,
        action: DiagnosticAction,
        gate_snapshot: Mapping[str, object],
        target: TargetRequest,
        receipt: VetoReceipt | None,
    ) -> VetoDecision:
        def abort(reason: str, verified: bool = False) -> VetoDecision:
            return VetoDecision(False, DiagnosticAction.abort(), reason, verified)

        if action.is_abort:
            return VetoDecision(True, action, "ABORT_ALWAYS_AVAILABLE", False)
        if receipt is None:
            return abort("SIM10_VETO_RECEIPT_UNKNOWN")
        if not isinstance(receipt, VetoReceipt):
            return abort("SIM10_VETO_RECEIPT_MALFORMED_TYPE")
        payload = receipt.payload
        if not isinstance(payload, Mapping) or not isinstance(
            receipt.signature_hmac_sha256, str
        ):
            return abort("SIM10_VETO_RECEIPT_MALFORMED_TYPE")
        try:
            expected_signature = _signature(payload)
        except (TypeError, ValueError, OverflowError):
            return abort("SIM10_VETO_RECEIPT_MALFORMED_TYPE")
        if not hmac.compare_digest(receipt.signature_hmac_sha256, expected_signature):
            return abort("SIM10_VETO_RECEIPT_SIGNATURE_INVALID")
        if payload.get("schema") != "SIM13_V4_SIM10_VETO_RECEIPT_V1" or payload.get(
            "scope"
        ) != VETO_RECEIPT_SCOPE:
            return abort("SIM10_VETO_RECEIPT_SCOPE_UNKNOWN")
        if payload.get("action_sha256") != canonical_digest(action.as_dict()):
            return abort("SIM10_VETO_RECEIPT_ACTION_MISMATCH")
        if payload.get("gate_snapshot_sha256") != canonical_digest(gate_snapshot):
            return abort("SIM10_VETO_RECEIPT_SNAPSHOT_MISMATCH")
        if payload.get("target_sha256") != canonical_digest(target.as_dict()):
            return abort("SIM10_VETO_RECEIPT_TARGET_MISMATCH")
        if payload.get("target") != target.as_dict():
            return abort("SIM10_VETO_RECEIPT_TARGET_CONTENT_MISMATCH")
        if payload.get("anchor_id") != ANCHOR_ID:
            return abort("SIM10_VETO_RECEIPT_ANCHOR_DRIFT")
        if (
            payload.get("sim10_gate_sha256") != EXPECTED_SIM10_GATE_SHA256
            or payload.get("sim10_summary_sha256")
            != EXPECTED_SIM10_SUMMARY_SHA256
            or payload.get("sim10_parameter_card_sha256")
            != EXPECTED_SIM10_PARAMETER_CARD_SHA256
            or payload.get("sim10_anchor_source_sha256")
            != EXPECTED_SIM10_ANCHOR_SOURCE_SHA256
        ):
            return abort("SIM10_VETO_RECEIPT_HASH_DRIFT")
        try:
            anchor = _load_hash_bound_anchor()
        except (
            OSError,
            ValueError,
            TypeError,
            AttributeError,
            json.JSONDecodeError,
            yaml.YAMLError,
        ):
            return abort("SIM10_ANCHOR_UNKNOWN_FAIL_CLOSED")
        try:
            w_plus = payload.get("anchor_w_plus_dps")
            if isinstance(w_plus, bool) or not isinstance(w_plus, (int, float)):
                raise TypeError("anchor_w_plus_dps must be numeric")
            if not math.isfinite(float(w_plus)):
                raise ValueError("anchor_w_plus_dps must be finite")
            source_proof = payload.get("mass_speed_source_proof")
            if not isinstance(source_proof, Mapping):
                raise TypeError("mass_speed_source_proof must be a mapping")
            numeric_proof = {
                key: source_proof.get(key)
                for key in (
                    "parameter_card_calibration_mass_kg",
                    "anchor_source_target_mass_kg",
                    "anchor_source_tumble_rate_dps",
                )
            }
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in numeric_proof.values()
            ):
                raise TypeError("mass/speed proof fields must be numeric")
            if any(not math.isfinite(float(value)) for value in numeric_proof.values()):
                raise ValueError("mass/speed proof fields must be finite")
        except (TypeError, ValueError, OverflowError):
            return abort("SIM10_VETO_RECEIPT_MALFORMED_TYPE")
        if (
            payload.get("anchor_region") != anchor["region"]
            or abs(float(w_plus) - ANCHOR_W_PLUS_DPS) > 1.0e-15
            or dict(numeric_proof) != anchor["mass_speed_proof"]
        ):
            return abort("SIM10_VETO_RECEIPT_ANCHOR_CONTENT_DRIFT")
        if not (
            payload.get("veto") is True
            and payload.get("canonical_outcome") == "MASK_TO_ABORT_ONLY"
            and payload.get("reason_code") == "MISSION_VETO_INFEASIBLE_RATE"
            and payload.get("historical_sim10_gate_pass_inherited_to_current_system")
            is False
            and payload.get("current_r2_feasibility_passed") is False
            and payload.get("contact_grasp_gate_passed") is False
            and payload.get("release_credit") is False
        ):
            return abort("SIM10_VETO_RECEIPT_SEMANTIC_DRIFT")
        return abort("MISSION_VETO_INFEASIBLE_RATE", True)


def sim10_artifact_records() -> dict[str, dict[str, object]]:
    return {
        "gate": file_record(SIM10_GATE_PATH, PROJECT_ROOT),
        "summary": file_record(SIM10_SUMMARY_PATH, PROJECT_ROOT),
        "parameter_card": file_record(SIM10_PARAMETER_CARD_PATH, PROJECT_ROOT),
        "anchor_source": file_record(SIM10_ANCHOR_SOURCE_PATH, PROJECT_ROOT),
    }


__all__ = (
    "ANCHOR_ID",
    "ANCHOR_REGION",
    "ANCHOR_TARGET_MASS_KG",
    "ANCHOR_TUMBLE_DPS",
    "ANCHOR_W_PLUS_DPS",
    "EXPECTED_SIM10_GATE_SHA256",
    "EXPECTED_SIM10_PARAMETER_CARD_SHA256",
    "EXPECTED_SIM10_ANCHOR_SOURCE_SHA256",
    "EXPECTED_SIM10_SUMMARY_SHA256",
    "Sim10MissionVeto",
    "TargetRequest",
    "VetoDecision",
    "VetoReceipt",
    "debris_150kg_3dps_request",
    "diagnostic_resign_veto_payload",
    "sim10_artifact_records",
)
