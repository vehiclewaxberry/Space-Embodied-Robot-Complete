#!/usr/bin/env python3
"""Terminal validator for the Sim13 V2 runtime fail-closed backends package.

Checks, in order:

1. the three contract schemas and the released contact geometry are present
   and strict-parse;
2. the historical 15/20 prebind artifacts remain at their frozen digests
   (read-only; this validator never rewrites them);
3. the five backend NC evidence rows, the three backend gates, the three
   backend receipts, the 20/20 registry evidence, and the SIM13_20_OF_20_GATE
   checkpoint are present, schema-correct, and self-consistent;
4. the MECH_RL_SYSTEM_INTERFACE_V2.yaml instance exists with the six core
   artifacts and nine gate-stage slots, with truthful authority values;
5. the full pytest suite passes;
6. deterministic replay: fresh in-memory rebuilds equal the on-disk bytes.

The validator writes exactly one file:
``results/SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1.json``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import yaml

HERE = Path(__file__).resolve().parent
V2_REBIND_ROOT = HERE.parent
PROJECT_ROOT = HERE.parents[3]
for candidate in (str(HERE), str(V2_REBIND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from sim13_v2_backends.canonical import sha256_bytes, write_canonical_json


VALIDATION_PATH = HERE / "results" / "SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1.json"
GENERATED_DATE_LOCAL = "2026-08-25"

HISTORICAL_PINS = {
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json": (
        2282,
        "DBFFF803A656F4AD74934F0C886BC258E219CDC6904647D2855F15D2C3916906",
    ),
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json": (
        40970,
        "C9DAEC35A677B945C09C1BD8D4EEB6401E04EB92D11473BBC68F4D0DFE4E243F",
    ),
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_PREBIND_VALIDATION_V1.json": (
        13027,
        "803388161591A67292283F374DE068D39722D89E964A77DDE1F011E3D5567DA6",
    ),
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_PREBIND_SOURCE_SHA256_V1.csv": (
        3519,
        "5EA4E337AAA21B2C4ED0CC5F0CBF2391F6BD2AC50CFC9FFF54640EE1869C2451",
    ),
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_PREBIND_RECEIPT_V1.md": (
        1706,
        "702455BF8868EB53E04577FE85EEA77B98FB8D93A8A91D696679768930152FE7",
    ),
}
CONTRACT_FILES = (
    "contracts/SIM13_V2_GATE_SNAPSHOT_RECEIPT_SCHEMA_V1.json",
    "contracts/SIM13_V2_BACKEND_CAPABILITY_TOKEN_SCHEMA_V1.json",
    "contracts/SIM13_V2_ACTION_BOUND_FEASIBILITY_RECEIPT_SCHEMA_V1.json",
)
INTERFACE_RELATIVE = (
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    "/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
)


def _check(checks: dict, key: str, ok: bool, detail: object = None) -> bool:
    checks[key] = {"pass": bool(ok), "detail": detail}
    return ok


def run_checks() -> dict:
    checks: dict[str, dict] = {}

    # 1. contracts + released geometry parse strictly
    contract_ok = True
    for relative in CONTRACT_FILES:
        try:
            document = json.loads((HERE / relative).read_bytes().decode("utf-8"))
            contract_ok = contract_ok and document.get("review_status") == "PENDING_OWNER_REVIEW"
            contract_ok = contract_ok and document.get("next_stage_authorized") is False
            contract_ok = contract_ok and document.get("release_credit") is False
        except (OSError, json.JSONDecodeError):
            contract_ok = False
    geometry = json.loads(
        (HERE / "assets/SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1.json").read_bytes().decode("utf-8")
    )
    contract_ok = contract_ok and geometry.get("schema") == "SIM13_V2_RELEASED_CONTACT_GEOMETRY_V1"
    _check(checks, "V01_contracts_and_released_geometry_strict", contract_ok)

    # 2. historical prebind artifacts frozen
    historical_detail: dict[str, object] = {}
    historical_ok = True
    for relative, (expected_bytes, expected_sha) in HISTORICAL_PINS.items():
        path = PROJECT_ROOT / relative
        if not path.is_file():
            historical_ok = False
            historical_detail[relative] = "MISSING"
            continue
        payload = path.read_bytes()
        actual = (len(payload), sha256_bytes(payload))
        ok = actual == (expected_bytes, expected_sha)
        historical_ok = historical_ok and ok
        historical_detail[relative] = {"bytes": actual[0], "sha256": actual[1], "pin_match": ok}
    _check(
        checks,
        "V02_historical_15_of_20_prebind_artifacts_frozen_read_only",
        historical_ok,
        historical_detail,
    )

    # 3. new evidence / gates / receipts
    evidence = json.loads(
        (HERE / "evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json").read_bytes().decode("utf-8")
    )
    _check(
        checks,
        "V03_backend_negative_controls_5_of_5",
        evidence["summary"] == {"total": 5, "executed": 5, "passed": 5, "failed": 0}
        and evidence["source_hashes_unchanged"] is True,
        evidence["summary"],
    )
    gate_ok = True
    gate_detail: dict[str, object] = {}
    for name, schema in (
        ("SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2"),
        ("SIM13_DYNAMICS_BACKEND_GATE_V2.json", "SIM13_DYNAMICS_BACKEND_GATE_V2"),
        ("SIM13_CONTACT_GRASP_GATE_V2.json", "SIM13_CONTACT_GRASP_GATE_V2"),
    ):
        gate = json.loads((HERE / "results" / name).read_bytes().decode("utf-8"))
        ok = (
            gate.get("schema") == schema
            and gate.get("gate_passed") is True
            and gate.get("review_status") == "PENDING_OWNER_REVIEW"
            and gate.get("next_stage_authorized") is False
            and gate.get("release_credit") is False
        )
        gate_ok = gate_ok and ok
        gate_detail[name] = {"gate_passed": gate.get("gate_passed"), "verdict": gate.get("verdict")}
    _check(checks, "V04_three_backend_gates_pass_without_release_credit", gate_ok, gate_detail)
    receipt_ok = True
    for name, schema in (
        ("SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json", "SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1"),
        ("SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1.json", "SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1"),
        ("SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1.json", "SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1"),
    ):
        receipt = json.loads((HERE / "evidence" / name).read_bytes().decode("utf-8"))
        receipt_ok = receipt_ok and receipt.get("schema") == schema
        receipt_ok = receipt_ok and receipt.get("all_checks_pass") is True
        receipt_ok = receipt_ok and receipt.get("next_stage_authorized") is False
        receipt_ok = receipt_ok and receipt.get("release_credit") is False
    _check(checks, "V05_three_backend_receipts_all_checks_pass", receipt_ok)

    full = json.loads(
        (HERE / "evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json").read_bytes().decode("utf-8")
    )
    _check(
        checks,
        "V06_full_nc_registry_20_of_20",
        full["summary"]["all_controls_passed"] is True
        and full["summary"]["passed"] == 20
        and full["summary"]["executed"] == 20
        and full["summary"]["failed"] == 0,
        full["summary"],
    )
    checkpoint = json.loads(
        (HERE / "results/SIM13_20_OF_20_GATE_V1.json").read_bytes().decode("utf-8")
    )
    _check(
        checks,
        "V07_sim13_20_of_20_gate_checkpoint",
        checkpoint.get("schema") == "SIM13_20_OF_20_GATE_V1"
        and checkpoint.get("nc_score") == "20/20"
        and checkpoint.get("gate_passed") is True
        and checkpoint.get("next_stage_authorized") is False
        and checkpoint.get("release_credit") is False
        and checkpoint.get("evidence", {}).get("sha256")
        == sha256_bytes(
            (HERE / "evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json").read_bytes()
        ),
        {"nc_score": checkpoint.get("nc_score"), "verdict": checkpoint.get("verdict")},
    )

    # 4. interface instance
    interface_path = PROJECT_ROOT / INTERFACE_RELATIVE
    interface_ok = interface_path.is_file()
    interface_detail: dict[str, object] = {}
    if interface_ok:
        instance = yaml.safe_load(interface_path.read_text(encoding="utf-8"))
        gate_stages = instance.get("artifacts", {}).get("gate_stages", {})
        slots = sum(len(slots) for slots in gate_stages.values())
        values = instance.get("authority", {}).get("current_values", {})
        interface_ok = (
            instance.get("schema") == "MECH_RL_SYSTEM_INTERFACE_V2"
            and slots == 9
            and len(instance.get("artifacts", {})) - 1 == 6
            and values.get("owner_accepted") is False
            and values.get("consumer_load_all_of_passed") is False
            and values.get("current_consumer_load_authorized") is False
            and values.get("current_contact_grasp_authorized") is False
            and values.get("runtime_fail_closed_gate_passed") is True
            and values.get("dynamics_backend_gate_passed") is True
            and values.get("contact_grasp_gate_passed") is True
            and instance.get("next_stage_authorized") is False
            and instance.get("release_credit") is False
        )
        interface_detail = {
            "path": INTERFACE_RELATIVE,
            "bytes": interface_path.stat().st_size,
            "sha256": sha256_bytes(interface_path.read_bytes()),
            "gate_stage_slots": slots,
        }
    _check(checks, "V08_interface_instance_9_gate_slots_truthful_authority", interface_ok, interface_detail)

    # 5. pytest suite
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    tail = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    _check(
        checks,
        "V09_pytest_suite_all_pass",
        completed.returncode == 0 and " passed" in tail and "failed" not in tail,
        {"return_code": completed.returncode, "summary": tail},
    )

    # 6. deterministic replay: fresh in-memory rebuilds equal on-disk bytes
    import run_negative_controls_backends_v2 as backends_runner
    import run_full_registry_intake_v2 as registry_runner

    replay_ok = True
    replay_detail: dict[str, object] = {}
    rebuilt = backends_runner.build_package()
    for name, document in (
        ("evidence/SIM13_V2_BACKENDS_NEGATIVE_CONTROLS_V2.json", rebuilt["evidence"]),
        ("evidence/SIM13_V2_DYNAMICS_BACKEND_VALIDATION_RECEIPT_V1.json", rebuilt["dynamics_receipt"]),
        ("evidence/SIM13_V2_CONTACT_BACKEND_VALIDATION_RECEIPT_V1.json", rebuilt["contact_receipt"]),
    ):
        on_disk = json.loads((HERE / name).read_bytes().decode("utf-8"))
        ok = on_disk == document
        replay_ok = replay_ok and ok
        replay_detail[name] = ok
    runtime_receipt = backends_runner.build_runtime_evaluator_receipt(rebuilt)
    on_disk = json.loads(
        (HERE / "evidence/SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json").read_bytes().decode("utf-8")
    )
    ok = on_disk == dict(runtime_receipt)
    replay_ok = replay_ok and ok
    replay_detail["evidence/SIM13_V2_RUNTIME_EVALUATOR_RECEIPT_V1.json"] = ok
    registry_evidence = registry_runner.build_full_registry()
    on_disk = json.loads(
        (HERE / "evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json").read_bytes().decode("utf-8")
    )
    ok = on_disk == registry_evidence
    replay_ok = replay_ok and ok
    replay_detail["evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json"] = ok
    _check(checks, "V10_deterministic_replay_byte_identical", replay_ok, replay_detail)

    all_pass = all(item["pass"] for item in checks.values())
    return {
        "schema": "SIM13_V2_BACKENDS_PACKAGE_VALIDATION_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "checks": checks,
        "score": {"pass": sum(1 for item in checks.values() if item["pass"]), "total": len(checks)},
        "all_checks_pass": all_pass,
        "verdict": (
            "SIM13_V2_BACKENDS_PACKAGE_VALIDATION_PASS__20_OF_20_NC__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT"
            if all_pass
            else "SIM13_V2_BACKENDS_PACKAGE_VALIDATION_FAIL"
        ),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    document = run_checks()
    print(json.dumps(document["score"], sort_keys=True))
    for key, item in document["checks"].items():
        print(f"{'PASS' if item['pass'] else 'FAIL'} {key}")
    print(document["verdict"])
    if not args.check_only:
        write_canonical_json(VALIDATION_PATH, document)
    return 0 if document["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
