"""Deterministic fail-closed evaluator for the additive contact-velocity contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml


HERE = Path(__file__).resolve().parent
DEFAULT_CONTRACT = HERE / "CONTACT_VELOCITY_RECONCILIATION_CANDIDATE_V1.yaml"
DEFAULT_GATE = HERE / "CONTACT_VELOCITY_RECONCILIATION_GATE_V1.json"
LEDGER = HERE / "CONTACT_VELOCITY_DESIGN_LEDGER_V1.yaml"
TEST_FILE = HERE / "tests" / "test_contact_velocity_reconciliation.py"

QUANTITY_FIELDS = (
    "estimate",
    "lower_bound",
    "upper_bound",
    "si_unit",
    "standard_uncertainty",
    "uncertainty_type",
    "distribution",
    "degrees_of_freedom",
    "authority",
    "source",
    "confidence",
    "status",
)


def project_root() -> Path:
    for candidate in (HERE, *HERE.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("project root not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def close(a: Any, b: float, tol: float = 1e-15) -> bool:
    return is_finite_number(a) and math.isclose(float(a), b, rel_tol=0.0, abs_tol=tol)


def quantity_record(
    estimate: float | None,
    lower: float | None,
    upper: float | None,
    unit: str,
    authority: str,
    source: str,
    status: str,
) -> dict[str, Any]:
    return {
        "estimate": estimate,
        "lower_bound": lower,
        "upper_bound": upper,
        "si_unit": unit,
        "standard_uncertainty": None,
        "uncertainty_type": "NOT_EVALUATED_FOR_SEMANTIC_DIAGNOSTIC",
        "distribution": "NOT_APPLICABLE_DETERMINISTIC_RECORD_COMPARISON",
        "degrees_of_freedom": None,
        "authority": authority,
        "source": source,
        "confidence": "HIGH_SEMANTIC_ONLY",
        "status": status,
    }


def evaluate(contract_path: Path) -> tuple[dict[str, Any], bool]:
    root = project_root()
    contract = load_yaml(contract_path)
    errors: list[str] = []
    criteria: list[dict[str, Any]] = []

    def criterion(cid: str, name: str, passed: bool, observed: Any) -> None:
        state = "PASS" if passed else "FAIL"
        criteria.append({"id": cid, "name": name, "state": state, "observed": observed})
        if not passed:
            errors.append(f"{cid}: {name}")

    bindings = contract.get("input_bindings")
    binding_results: list[dict[str, Any]] = []
    bindings_ok = isinstance(bindings, list) and len(bindings) == 4
    if isinstance(bindings, list):
        for binding in bindings:
            if not isinstance(binding, dict):
                bindings_ok = False
                continue
            rel = binding.get("path")
            p = root / rel if isinstance(rel, str) else root / "__invalid__"
            exists = p.is_file()
            actual_bytes = p.stat().st_size if exists else None
            actual_sha = sha256(p) if exists else None
            match = (
                exists
                and actual_bytes == binding.get("bytes")
                and actual_sha == binding.get("sha256")
            )
            bindings_ok = bindings_ok and match
            binding_results.append(
                {
                    "id": binding.get("id"),
                    "path": rel,
                    "exists": exists,
                    "expected_bytes": binding.get("bytes"),
                    "actual_bytes": actual_bytes,
                    "expected_sha256": binding.get("sha256"),
                    "actual_sha256": actual_sha,
                    "match": match,
                }
            )
    criterion("CVR-G01", "frozen input byte counts and SHA-256 values match", bindings_ok, binding_results)

    quantities = contract.get("quantities")
    quantity_errors: list[str] = []
    if not isinstance(quantities, dict) or not quantities:
        quantity_errors.append("quantities missing or empty")
        quantities = {}
    for name, q in quantities.items():
        if not isinstance(q, dict):
            quantity_errors.append(f"{name}: not a mapping")
            continue
        missing = [field for field in QUANTITY_FIELDS if field not in q]
        if missing:
            quantity_errors.append(f"{name}: missing {missing}")
            continue
        numeric = (q["estimate"], q["lower_bound"], q["upper_bound"])
        if any(value is not None and not is_finite_number(value) for value in numeric):
            quantity_errors.append(f"{name}: non-finite estimate/bounds")
        if q["standard_uncertainty"] is not None:
            if not is_finite_number(q["standard_uncertainty"]) or q["standard_uncertainty"] < 0:
                quantity_errors.append(f"{name}: invalid standard uncertainty")
        if all(is_finite_number(value) for value in numeric):
            if not (q["lower_bound"] <= q["estimate"] <= q["upper_bound"]):
                quantity_errors.append(f"{name}: estimate outside bounds")
        elif any(value is not None for value in numeric):
            quantity_errors.append(f"{name}: estimate and bounds must be all numeric or all null")
        for field in ("si_unit", "uncertainty_type", "distribution", "authority", "source", "confidence", "status"):
            if not isinstance(q[field], str) or not q[field].strip():
                quantity_errors.append(f"{name}: {field} must be non-empty text")
    criterion("CVR-G02", "all physical quantity records carry complete SI and uncertainty metadata", not quantity_errors, quantity_errors)

    q_design = quantities.get("current_design_target_hard_upper_bound", {})
    q_original = quantities.get("original_provisional_contact_scenario_speed", {})
    q_reduced = quantities.get("reduced_current_contact_consumer_candidate", {})
    q_asbuilt = quantities.get("as_built_first_contact_closing_speed", {})

    source_values_ok = False
    source_observed: dict[str, Any] = {}
    try:
        interface_path = root / next(b["path"] for b in bindings if b["id"] == "GRIPPER_ACTUATION_INTERFACE")
        contact_path = root / next(b["path"] for b in bindings if b["id"] == "DESIGN_CONTACT_MODEL")
        interface = load_yaml(interface_path)
        contact = load_yaml(contact_path)
        source_design = interface["design_target_layer"]["first_contact_speed_max_m_s"]
        source_contact = contact["gripper_actuator"]["first_contact_closing_velocity_mps"]
        source_values_ok = (
            close(source_design, 0.005)
            and close(source_contact["nominal"], 0.05)
            and close(source_contact["lower"], 0.01)
            and close(source_contact["upper"], 0.1)
            and source_contact["unit"] == "m/s"
            and source_contact["authority"] == "DESIGN_ESTIMATE_UNVERIFIED"
        )
        source_observed = {
            "design_target_quantity_ref": "quantities.current_design_target_hard_upper_bound",
            "original_provisional_quantity_ref": "quantities.original_provisional_contact_scenario_speed",
            "design_target_source_path": "design_target_layer.first_contact_speed_max_m_s",
            "provisional_source_path": "gripper_actuator.first_contact_closing_velocity_mps",
            "provisional_source_authority": source_contact["authority"],
            "source_units_match_si_m_per_s": source_contact["unit"] == "m/s",
        }
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        source_observed = {"error": f"{type(exc).__name__}: {exc}"}
    criterion("CVR-G03", "source values and authority classes are extracted without reinterpretation", source_values_ok, source_observed)

    design_ok = (
        close(q_design.get("estimate"), 0.005)
        and close(q_design.get("lower_bound"), 0.0)
        and close(q_design.get("upper_bound"), 0.005)
        and q_design.get("si_unit") == "m/s"
        and q_design.get("standard_uncertainty") is None
        and q_design.get("status") == "CURRENT_DESIGN_TARGET_HARD_UPPER_BOUND__NOT_MEASURED_CAPABILITY"
    )
    criterion("CVR-G04", "0.005 m/s is encoded as the current design-target hard upper bound only", design_ok, q_design)

    original_ok = (
        close(q_original.get("estimate"), 0.05)
        and close(q_original.get("lower_bound"), 0.01)
        and close(q_original.get("upper_bound"), 0.1)
        and q_original.get("si_unit") == "m/s"
        and q_original.get("standard_uncertainty") is None
        and q_original.get("distribution") == "UNKNOWN_NOT_DECLARED"
        and "REJECTED_FOR_CURRENT_CONTACT_CONSUMER" in str(q_original.get("status"))
    )
    criterion("CVR-G05", "0.05 m/s is retained exactly as an uncertainty-unqualified provisional source record", original_ok, q_original)

    consumer_bindings = contract.get("consumer_bindings", {})
    original_binding = consumer_bindings.get("original_provisional_0p05_scenario", {}) if isinstance(consumer_bindings, dict) else {}
    original_rejected = (
        original_binding.get("quantity_ref") == "original_provisional_contact_scenario_speed"
        and original_binding.get("retained_as_source_record") is True
        and original_binding.get("consumer_disposition") == "REJECT_CURRENT_CONTACT_CONSUMER"
        and close(q_original.get("estimate"), 0.05)
        and is_finite_number(q_design.get("estimate"))
        and q_original["estimate"] > q_design["estimate"]
    )
    criterion("CVR-G06", "the original 0.05 m/s scenario is machine-rejected for the current consumer", original_rejected, original_binding)

    current_binding = consumer_bindings.get("current_contact_consumer", {}) if isinstance(consumer_bindings, dict) else {}
    reduced_ok = (
        current_binding.get("permitted_quantity_ref") == "reduced_current_contact_consumer_candidate"
        and current_binding.get("hard_upper_bound_quantity_ref") == "current_design_target_hard_upper_bound"
        and close(q_reduced.get("estimate"), 0.005)
        and close(q_reduced.get("lower_bound"), 0.0)
        and close(q_reduced.get("upper_bound"), 0.005)
        and q_reduced.get("si_unit") == "m/s"
        and is_finite_number(q_design.get("estimate"))
        and q_reduced["estimate"] <= q_design["estimate"]
        and q_reduced["upper_bound"] <= q_design["estimate"]
        and current_binding.get("accepted_scope") == "BOUNDED_DESIGN_DIAGNOSTIC_ONLY"
    )
    criterion("CVR-G07", "an explicit <=0.005 m/s reduced candidate is compatible only in bounded design diagnostics", reduced_ok, {"quantity": q_reduced, "binding": current_binding})

    asbuilt_ok = (
        q_asbuilt.get("estimate") is None
        and q_asbuilt.get("lower_bound") is None
        and q_asbuilt.get("upper_bound") is None
        and q_asbuilt.get("standard_uncertainty") is None
        and q_asbuilt.get("si_unit") == "m/s"
        and q_asbuilt.get("distribution") == "UNKNOWN_UNMEASURED"
        and "NULL_MUST_NOT_BE_ZERO_FILLED" in str(q_asbuilt.get("status"))
    )
    criterion("CVR-G08", "as-built speed and its uncertainty remain explicit nulls", asbuilt_ok, q_asbuilt)

    ruling = contract.get("ruling", {})
    release_flags_ok = (
        contract.get("frozen_inputs_modified") is False
        and ruling.get("frozen_contracts_changed") is False
        and ruling.get("next_stage_authorized") is False
        and ruling.get("release_credit") is False
        and current_binding.get("physical_contact_authorized") is False
        and current_binding.get("production_dynamics_authorized") is False
        and current_binding.get("non_abort_grasp_authorized") is False
        and ruling.get("physical_actuator_speed_authority") == "HOLD"
        and ruling.get("current_design_target_hard_upper_bound_quantity_ref") == "current_design_target_hard_upper_bound"
        and ruling.get("original_provisional_scenario_quantity_ref") == "original_provisional_contact_scenario_speed"
        and ruling.get("explicitly_reduced_design_diagnostic_quantity_ref") == "reduced_current_contact_consumer_candidate"
    )
    criterion("CVR-G09", "all physical, production and non-ABORT release paths remain fail closed", release_flags_ok, {"ruling": ruling, "binding": current_binding})

    ratio = float(q_original["estimate"] / q_design["estimate"]) if original_rejected else float("nan")
    excess = float(q_original["estimate"] - q_design["estimate"]) if original_rejected else float("nan")
    all_pass = all(item["state"] == "PASS" for item in criteria)

    support_files = []
    for path, role in ((Path(__file__), "EVALUATOR"), (LEDGER, "DESIGN_LEDGER"), (TEST_FILE, "TEST_SUITE")):
        support_files.append(
            {
                "role": role,
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size if path.is_file() else None,
                "sha256": sha256(path) if path.is_file() else None,
            }
        )

    gate = {
        "schema": "CONTACT_VELOCITY_RECONCILIATION_GATE_V1",
        "evaluation_time_policy": "OMITTED_FOR_BYTE_DETERMINISM",
        "authority_scope": contract.get("authority_scope"),
        "subject": {
            "path": contract_path.resolve().relative_to(root).as_posix() if contract_path.resolve().is_relative_to(root) else str(contract_path.resolve()),
            "bytes": contract_path.stat().st_size,
            "sha256": sha256(contract_path),
        },
        "support_files": support_files,
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_passed": sum(item["state"] == "PASS" for item in criteria),
        "derived_quantities": {
            "original_to_design_speed_ratio": quantity_record(
                ratio if math.isfinite(ratio) else None,
                ratio if math.isfinite(ratio) else None,
                ratio if math.isfinite(ratio) else None,
                "1",
                "DETERMINISTIC_EVALUATOR",
                "original provisional estimate divided by current design-target hard upper bound",
                "VALID_SEMANTIC_DIAGNOSTIC" if math.isfinite(ratio) else "INVALID_NOT_REPORTABLE",
            ),
            "original_nominal_excess_over_design_bound": quantity_record(
                excess if math.isfinite(excess) else None,
                excess if math.isfinite(excess) else None,
                excess if math.isfinite(excess) else None,
                "m/s",
                "DETERMINISTIC_EVALUATOR",
                "original provisional estimate minus current design-target hard upper bound",
                "VALID_SEMANTIC_DIAGNOSTIC" if math.isfinite(excess) else "INVALID_NOT_REPORTABLE",
            ),
        },
        "errors": errors,
        "semantic_reconciliation": "PASS" if all_pass else "FAIL",
        "original_0p05_current_contact_consumer": "REJECT" if original_rejected else "FAIL_TO_REJECT",
        "reduced_0p005_design_diagnostic_consumer": "ACCEPT_BOUNDED_DIAGNOSTIC_ONLY" if reduced_ok else "REJECT",
        "physical_actuator_speed_authority": "HOLD",
        "physical_contact_ready": False,
        "production_dynamics_ready": False,
        "non_abort_grasp_ready": False,
        "verdict": (
            "PASS_RECONCILIATION__0P005_MPS_HARD_BOUND__0P05_MPS_REJECTED_FOR_CURRENT_CONSUMER__PHYSICAL_AUTHORITY_HOLD"
            if all_pass
            else "FAIL_CONTACT_VELOCITY_RECONCILIATION__CURRENT_CONSUMER_MUST_ABORT"
        ),
        "gate": "PASS_WITH_PHYSICAL_HOLD" if all_pass else "FAIL",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return gate, all_pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    gate, passed = evaluate(args.contract.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(gate, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(gate["verdict"])
    print(f"criteria: {gate['criteria_passed']}/{gate['criteria_total']}")
    print(f"gate_sha256: {hashlib.sha256(payload.encode('utf-8')).hexdigest().upper()}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
