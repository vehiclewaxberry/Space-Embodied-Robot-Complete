"""Action-bound 150 kg feasibility / post-grasp evaluator (WO-NC20).

The evaluator binds six hash-pinned anchors:

- sim10 gate, scan summary, mission parameter card, and anchor source, which
  together prove the ``debris_sim06`` anchor: 150 kg at 3 deg/s tumbles to
  omega+ = 3.0633304945807067 deg/s and lands in ``INFEASIBLE_RATE``;
- sim12 gate check and strategy results, which prove the ``B_anchor`` case
  (the same 150 kg / 3 deg/s target) is INFEASIBLE for all four binding-gate
  strategies with a negative wheel momentum margin -- the post-grasp state is
  not wheels-only stabilizable.

For every non-ABORT request against this anchor the evaluator therefore can
only issue a ``FEASIBILITY_FAIL`` receipt; a request presented without a
``FEASIBILITY_PASS`` receipt is masked by the runtime shield to the canonical
ABORT with reason ``MISSION_VETO_INFEASIBLE_RATE``.  Historical sim10/sim12
PASS verdicts are hash anchors only; nothing here inherits them as current-R2,
contact, or production PASS.
"""

from __future__ import annotations

import ast
import csv
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
from pathlib import Path
from typing import Any, Mapping

import yaml

from .canonical import canonical_digest, canonical_json_bytes, sha256_file


EVALUATOR_ID = "SIM13_V2_ACTION_BOUND_FEASIBILITY_EVALUATOR_V1"
RECEIPT_SCHEMA = "SIM13_V2_ACTION_BOUND_FEASIBILITY_RECEIPT_V1"
KEY_CLASS = "PUBLIC_NON_SECRET_COOPERATIVE_FAIL_CLOSED_BOUNDARY_NOT_CRYPTO_ROOT"
RECEIPT_HMAC_KEY = (
    b"SIM13_V2_FEASIBILITY_RECEIPT_PUBLIC_NON_SECRET_KEY_COOPERATIVE_BOUNDARY_V1"
)

SIM10_GATE_REL = "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json"
SIM10_SUMMARY_REL = "30_simulation/sim_10_mission_feasibility/results/sim_10_scan_summary.json"
SIM10_CARD_REL = "20_engineering/config/mission_feasibility/scan_v0.yaml"
SIM10_SOURCE_REL = "30_simulation/sim_10_mission_feasibility/src/scan_grid.py"
SIM12_GATE_REL = "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json"
SIM12_CSV_REL = "30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv"

EXPECTED_ANCHOR_SHA256 = {
    SIM10_GATE_REL: "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67",
    SIM10_SUMMARY_REL: "63D84CE5CA84E9B9DE8C2833577C9645FF2060874B8AB5E081EE7672D0046FC5",
    SIM10_CARD_REL: "856F1E30DE47CA5B3F505F9FE5BD5CD22A75E448EC916B42D9C330F7A62E28EA",
    SIM10_SOURCE_REL: "FBEA1EB8AC459ABA364683AF9C6BE668154FF036ADEDCCC441B5D32CFFF4D5C4",
    SIM12_GATE_REL: "A416C13481119BBDC61764D518A1ABEBC159A78BBD78FAC132803069713DACD8",
    SIM12_CSV_REL: "F538676005CE8CE899BEB8956B33EE75458B18A207AD06FCACAA8B59AEC42DE6",
}
ANCHOR_ID = "debris_sim06"
ANCHOR_TARGET_MASS_KG = 150.0
ANCHOR_TUMBLE_DPS = 3.0
ANCHOR_REGION = "INFEASIBLE_RATE"
ANCHOR_W_PLUS_DPS = 3.0633304945807067
SIM12_ANCHOR_CASE = "B_anchor"


class AnchorSourceError(RuntimeError):
    """Raised when a hash-pinned sim10/sim12 anchor is absent or drifted."""


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "target_mass_kg": float(self.target_mass_kg),
            "tumble_rate_dps": float(self.tumble_rate_dps),
        }


def debris_150kg_3dps_request() -> TargetRequest:
    return TargetRequest("target_debris_v0", 150.0, 3.0)


@dataclass(frozen=True)
class FeasibilityReceipt:
    payload: Mapping[str, Any]
    signature_hmac_sha256: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "payload": dict(self.payload),
            "signature_hmac_sha256": self.signature_hmac_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FeasibilityReceipt":
        if not isinstance(value, Mapping):
            raise ValueError("feasibility receipt must be a mapping")
        payload = value.get("payload")
        signature = value.get("signature_hmac_sha256")
        if not isinstance(payload, Mapping) or not isinstance(signature, str):
            raise ValueError("malformed feasibility receipt")
        return cls(dict(payload), signature)


@dataclass(frozen=True)
class FeasibilityAdmission:
    allowed: bool
    reason_code: str
    receipt_verified: bool


def _signature(payload: Mapping[str, Any]) -> str:
    return hmac.new(
        RECEIPT_HMAC_KEY, canonical_json_bytes(payload), hashlib.sha256
    ).hexdigest().upper()


def resign_receipt_for_negative_control(
    payload: Mapping[str, Any]
) -> FeasibilityReceipt:
    """Re-sign a mutated payload solely so negative controls stay deterministic."""

    copied = dict(payload)
    return FeasibilityReceipt(copied, _signature(copied))


def _anchor_source_literals(path: Path) -> dict[str, float]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        entries: dict[str, ast.AST] = {}
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                entries[key.value] = value
        anchor_node = entries.get("anchor")
        if not (isinstance(anchor_node, ast.Constant) and anchor_node.value == ANCHOR_ID):
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
            raise AnchorSourceError("SIM10_ANCHOR_SOURCE_TYPES_UNKNOWN")
        return {
            "target_mass_kg": float(mass_node.value),
            "tumble_rate_dps": float(speed_node.value),
        }
    raise AnchorSourceError("SIM10_ANCHOR_SOURCE_DEBRIS_ROW_UNKNOWN")


class ActionBoundFeasibilityEvaluator:
    """Hash-bound sim10/sim12 150 kg feasibility and post-grasp evaluator."""

    def __init__(self, *, project_root: str | Path) -> None:
        root = Path(project_root).resolve()
        self.project_root = root
        self.paths = {
            relative: (root / relative).resolve()
            for relative in EXPECTED_ANCHOR_SHA256
        }
        self.anchor_hashes: dict[str, str] = {}
        for relative, path in self.paths.items():
            if not path.is_file():
                raise AnchorSourceError(f"ANCHOR_SOURCE_MISSING:{relative}")
            digest = sha256_file(path)
            if digest != EXPECTED_ANCHOR_SHA256[relative]:
                raise AnchorSourceError(f"ANCHOR_SOURCE_HASH_DRIFT:{relative}")
            self.anchor_hashes[relative] = digest
        self.anchors = self._load_and_crosscheck_anchors()

    def _load_and_crosscheck_anchors(self) -> Mapping[str, Any]:
        gate = json.loads(self.paths[SIM10_GATE_REL].read_text(encoding="utf-8"))
        summary = json.loads(self.paths[SIM10_SUMMARY_REL].read_text(encoding="utf-8"))
        card = yaml.safe_load(self.paths[SIM10_CARD_REL].read_text(encoding="utf-8"))
        literals = _anchor_source_literals(self.paths[SIM10_SOURCE_REL])
        if gate.get("schema_version") != "sim10-gate-v1" or gate.get("verdict") != "SIM10_GATES_PASS":
            raise AnchorSourceError("SIM10_GATE_SCHEMA_OR_VERDICT_DRIFT")
        x1 = gate.get("gates", {}).get("X1_anchors_vs_sim06", {})
        if x1.get("pass") is not True:
            raise AnchorSourceError("SIM10_X1_UNKNOWN_OR_FAIL")
        matches = [item for item in x1.get("checks", []) if item.get("anchor") == ANCHOR_ID]
        if len(matches) != 1:
            raise AnchorSourceError("SIM10_GATE_ANCHOR_UNKNOWN")
        gate_anchor = matches[0]
        summary_anchor = summary.get("anchors", {}).get(ANCHOR_ID)
        if not isinstance(summary_anchor, Mapping):
            raise AnchorSourceError("SIM10_SUMMARY_ANCHOR_UNKNOWN")
        if not (
            gate_anchor.get("ok") is True
            and gate_anchor.get("region") == ANCHOR_REGION
            and gate_anchor.get("region_expected") == ANCHOR_REGION
            and summary_anchor.get("region_default_tier") == ANCHOR_REGION
            and abs(float(gate_anchor.get("w_plus_dps")) - ANCHOR_W_PLUS_DPS) <= 1.0e-15
            and abs(float(summary_anchor.get("w_plus_dps")) - ANCHOR_W_PLUS_DPS) <= 1.0e-15
        ):
            raise AnchorSourceError("SIM10_ANCHOR_CONTENT_DRIFT")
        g1 = card.get("scan", {}).get("geometry_classes", {}).get("G1_slender", {})
        if not (
            card.get("version") == "v0"
            and g1.get("calibration_target") == "target_debris_v0"
            and float(g1.get("calibration_mass_kg")) == ANCHOR_TARGET_MASS_KG
            and literals == {
                "target_mass_kg": ANCHOR_TARGET_MASS_KG,
                "tumble_rate_dps": ANCHOR_TUMBLE_DPS,
            }
        ):
            raise AnchorSourceError("SIM10_PARAMETER_OR_SOURCE_ANCHOR_DRIFT")

        sim12_gate = json.loads(self.paths[SIM12_GATE_REL].read_text(encoding="utf-8"))
        if sim12_gate.get("schema_version") != "sim12-phase1-v1" or sim12_gate.get("verdict") != "SIM12_PHASE1_GATES_PASS":
            raise AnchorSourceError("SIM12_GATE_SCHEMA_OR_VERDICT_DRIFT")
        best = sim12_gate.get("gates", {}).get("GS2_differentiation", {}).get("best_per_case", {})
        if best.get(SIM12_ANCHOR_CASE) != "ABORT":
            raise AnchorSourceError("SIM12_B_ANCHOR_BEST_STRATEGY_NOT_ABORT")
        rows: list[Mapping[str, str]] = []
        with self.paths[SIM12_CSV_REL].open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("case") == SIM12_ANCHOR_CASE:
                    rows.append(row)
        strategies = {row.get("strategy") for row in rows}
        expected_strategies = {
            "S1_passive",
            "S2_velocity_matching",
            "S3a_wheel_bias",
            "S4_post_capture_detumble",
        }
        if strategies != expected_strategies or len(rows) != 4:
            raise AnchorSourceError("SIM12_B_ANCHOR_STRATEGY_SET_DRIFT")
        for row in rows:
            if row.get("feasibility") != "INFEASIBLE":
                raise AnchorSourceError("SIM12_B_ANCHOR_NOT_INFEASIBLE_ALL_STRATEGIES")
            if row.get("binding_gate") != "POST_CAPTURE_RATE":
                raise AnchorSourceError("SIM12_B_ANCHOR_BINDING_GATE_DRIFT")
            if float(row["wheel_margin_Nms"]) >= 0.0:
                raise AnchorSourceError("SIM12_B_ANCHOR_WHEEL_MARGIN_NOT_NEGATIVE")
            if float(row["H_required_Nms"]) <= 0.0:
                raise AnchorSourceError("SIM12_B_ANCHOR_H_REQUIRED_INVALID")
        s1_rows = [row for row in rows if row.get("strategy") == "S1_passive"]
        if abs(float(s1_rows[0]["post_capture_rate_dps"]) - ANCHOR_W_PLUS_DPS) > 1.0e-15:
            raise AnchorSourceError("SIM12_B_ANCHOR_POST_CAPTURE_RATE_DRIFT")
        return {
            "anchor_id": ANCHOR_ID,
            "target_mass_kg": ANCHOR_TARGET_MASS_KG,
            "tumble_rate_dps": ANCHOR_TUMBLE_DPS,
            "w_plus_dps": ANCHOR_W_PLUS_DPS,
            "region": ANCHOR_REGION,
            "sim12_best_strategy": best[SIM12_ANCHOR_CASE],
            "sim12_strategies_infeasible": sorted(strategies),
            "sim12_s1_post_capture_rate_dps": float(s1_rows[0]["post_capture_rate_dps"]),
            "sim12_max_wheel_margin_Nms": max(float(row["wheel_margin_Nms"]) for row in rows),
            "sim12_min_H_required_Nms": min(float(row["H_required_Nms"]) for row in rows),
        }

    def evaluate(self, target: TargetRequest) -> Mapping[str, Any]:
        """Feasibility + post-grasp stability verdict for the request."""

        if target != debris_150kg_3dps_request():
            return {
                "feasibility_verdict": "UNKNOWN",
                "post_grasp_verdict": "UNKNOWN",
                "reason_code": "TARGET_OUTSIDE_BOUND_ANCHOR_UNKNOWN_MASKS_TO_ABORT",
                "feasibility_pass": False,
            }
        anchors = self.anchors
        return {
            "feasibility_verdict": "FEASIBILITY_FAIL",
            "post_grasp_verdict": "POST_GRASP_STABILITY_FAIL_WHEELS_ONLY",
            "reason_code": "MISSION_VETO_INFEASIBLE_RATE",
            "feasibility_pass": False,
            "anchor_region": anchors["region"],
            "anchor_w_plus_dps": anchors["w_plus_dps"],
            "sim12_best_strategy": anchors["sim12_best_strategy"],
            "sim12_max_wheel_margin_Nms": anchors["sim12_max_wheel_margin_Nms"],
            "sim12_min_H_required_Nms": anchors["sim12_min_H_required_Nms"],
        }

    def issue_receipt(
        self,
        *,
        action: Mapping[str, Any],
        target: TargetRequest,
    ) -> FeasibilityReceipt:
        evaluation = self.evaluate(target)
        payload: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "evaluator_id": EVALUATOR_ID,
            "key_class": KEY_CLASS,
            "requested_action_sha256": canonical_digest(action),
            "target_sha256": canonical_digest(target.as_dict()),
            "target": target.as_dict(),
            "evaluation": dict(evaluation),
            "anchor_hashes": dict(self.anchor_hashes),
            "historical_sim10_sim12_pass_inherited_to_current_r2": False,
            "release_credit": False,
            "next_stage_authorized": False,
        }
        return FeasibilityReceipt(payload, _signature(payload))

    def verify_receipt(
        self,
        *,
        receipt: FeasibilityReceipt | None,
        action: Mapping[str, Any],
        target: TargetRequest,
    ) -> FeasibilityAdmission:
        """Fail-closed receipt verification for one action/target pair."""

        def deny(reason: str, verified: bool = False) -> FeasibilityAdmission:
            return FeasibilityAdmission(False, reason, verified)

        if receipt is None:
            return deny("FEASIBILITY_RECEIPT_MISSING")
        if not isinstance(receipt, FeasibilityReceipt):
            return deny("FEASIBILITY_RECEIPT_MALFORMED")
        payload = receipt.payload
        if not isinstance(payload, Mapping) or not isinstance(
            receipt.signature_hmac_sha256, str
        ):
            return deny("FEASIBILITY_RECEIPT_MALFORMED")
        try:
            expected_signature = _signature(payload)
        except (TypeError, ValueError, OverflowError):
            return deny("FEASIBILITY_RECEIPT_MALFORMED")
        if not hmac.compare_digest(receipt.signature_hmac_sha256, expected_signature):
            return deny("FEASIBILITY_RECEIPT_SIGNATURE_INVALID")
        exact_constants = {
            "schema": RECEIPT_SCHEMA,
            "evaluator_id": EVALUATOR_ID,
            "key_class": KEY_CLASS,
            "historical_sim10_sim12_pass_inherited_to_current_r2": False,
            "release_credit": False,
            "next_stage_authorized": False,
        }
        if any(payload.get(key) != value for key, value in exact_constants.items()):
            return deny("FEASIBILITY_RECEIPT_SCOPE_INVALID")
        if payload.get("requested_action_sha256") != canonical_digest(action):
            return deny("FEASIBILITY_RECEIPT_ACTION_MISMATCH")
        if payload.get("target_sha256") != canonical_digest(target.as_dict()):
            return deny("FEASIBILITY_RECEIPT_TARGET_MISMATCH")
        if payload.get("anchor_hashes") != self.anchor_hashes:
            return deny("FEASIBILITY_RECEIPT_ANCHOR_HASH_DRIFT")
        evaluation = payload.get("evaluation")
        if not isinstance(evaluation, Mapping):
            return deny("FEASIBILITY_RECEIPT_MALFORMED")
        current = self.evaluate(target)
        if dict(evaluation) != dict(current):
            return deny("FEASIBILITY_RECEIPT_EVALUATION_DRIFT")
        if evaluation.get("feasibility_pass") is not True:
            return deny("MISSION_VETO_INFEASIBLE_RATE", True)
        return FeasibilityAdmission(True, "FEASIBILITY_PASS_RECEIPT_ACCEPTED", True)


__all__ = [
    "ANCHOR_ID",
    "ANCHOR_REGION",
    "ANCHOR_TARGET_MASS_KG",
    "ANCHOR_TUMBLE_DPS",
    "ANCHOR_W_PLUS_DPS",
    "ActionBoundFeasibilityEvaluator",
    "AnchorSourceError",
    "EVALUATOR_ID",
    "EXPECTED_ANCHOR_SHA256",
    "FeasibilityAdmission",
    "FeasibilityReceipt",
    "RECEIPT_SCHEMA",
    "TargetRequest",
    "debris_150kg_3dps_request",
    "resign_receipt_for_negative_control",
]
