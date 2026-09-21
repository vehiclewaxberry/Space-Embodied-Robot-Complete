#!/usr/bin/env python3
"""Rerun the complete Sim13 V2 NC01--NC20 registry to 20/20.

This runner re-executes, in one fresh pass:

- the 15 prebind negative controls (NC01--NC14, NC17) via the unmodified
  ``run_negative_controls_prebind_v1.py`` probe functions in the parent
  package -- historical 15/20 evidence is preserved read-only, never
  overwritten or rewritten;
- the 5 new backend negative controls (NC15/16/18/19/20) via the
  ``runtime_fail_closed_backends_v2`` probes.

All 20 records are evaluated by the unchanged
``sim13_v2.negative_controls.evaluate_negative_controls`` registry.  The
output lands only inside this package:

- ``evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json``
- ``results/SIM13_20_OF_20_GATE_V1.json``
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from typing import Any, Mapping

HERE = Path(__file__).resolve().parent
V2_REBIND_ROOT = HERE.parent
PROJECT_ROOT = HERE.parents[3]
for candidate in (str(HERE), str(V2_REBIND_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from sim13_v2.negative_controls import (
    ControlStatus,
    NegativeControlRecord,
    REGISTRY,
    evaluate_negative_controls,
)
from sim13_v2_backends.canonical import (
    canonical_digest,
    sha256_bytes,
    write_canonical_json,
)
import run_negative_controls_backends_v2 as backends_runner


PREBIND_RUNNER_PATH = V2_REBIND_ROOT / "run_negative_controls_prebind_v1.py"
HISTORICAL_EVIDENCE_PATH = (
    V2_REBIND_ROOT / "evidence" / "SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json"
)
EVIDENCE_PATH = HERE / "evidence" / "SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json"
GATE_PATH = HERE / "results" / "SIM13_20_OF_20_GATE_V1.json"
GENERATED_DATE_LOCAL = "2026-08-25"


def _load_prebind_runner():
    spec = importlib.util.spec_from_file_location(
        "sim13_v2_nc_prebind_runner", PREBIND_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the prebind negative-control runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _execute_prebind_subset(module, temporary_root: Path):
    with tempfile.TemporaryDirectory(
        prefix="sim13_v2_full_registry_prebind_", dir=temporary_root
    ) as temporary:
        context = module._load_source_model(Path(temporary))
        tracked = module._tracked_source_paths(context)
        before = module._source_hashes(tracked)
        probe_pairs = {
            control_id: (
                module._safe_probe(probe, context, "A"),
                module._safe_probe(probe, context, "B"),
            )
            for control_id, probe in module.PROBES.items()
        }
        after = module._source_hashes(tracked)
    return probe_pairs, before == after


def _execute_backend_subset(temporary_root: Path):
    with tempfile.TemporaryDirectory(
        prefix="sim13_v2_full_registry_backends_", dir=temporary_root
    ) as temporary:
        context = backends_runner.build_context(Path(temporary))
        tracked = backends_runner._tracked_source_paths()
        before = backends_runner._source_hashes(tracked)
        probe_pairs = {
            control_id: (
                backends_runner._safe_probe(probe, context, "A"),
                backends_runner._safe_probe(probe, context, "B"),
            )
            for control_id, probe in backends_runner.PROBES.items()
        }
        after = backends_runner._source_hashes(tracked)
    return probe_pairs, before == after


def build_full_registry() -> dict[str, Any]:
    module = _load_prebind_runner()
    with tempfile.TemporaryDirectory(prefix="sim13_v2_full_registry_") as temporary:
        prebind_pairs, prebind_hashes_unchanged = _execute_prebind_subset(
            module, Path(temporary)
        )
        backend_pairs, backend_hashes_unchanged = _execute_backend_subset(
            Path(temporary)
        )

    records: list[NegativeControlRecord] = []
    baseline_holds: dict[str, str] = {}
    for control_id, (first, second) in prebind_pairs.items():
        deterministic = first == second
        if not (first.baseline_qualified and second.baseline_qualified):
            baseline_holds[control_id] = first.exact_reason
            continue
        records.append(
            NegativeControlRecord(
                control_id=control_id,
                executed=True,
                observed_outcome=first.observed_outcome,
                non_abort_execution_count=first.non_abort_execution_count,
                exact_reason_match=(
                    first.exact_reason == module.EXPECTED_REASON[control_id]
                ),
                deterministic_repeat=deterministic,
                baseline_hash_unchanged=prebind_hashes_unchanged,
            )
        )
    for control_id, (first, second) in backend_pairs.items():
        deterministic = first == second
        if not (first.baseline_qualified and second.baseline_qualified):
            baseline_holds[control_id] = first.exact_reason
            continue
        records.append(
            NegativeControlRecord(
                control_id=control_id,
                executed=True,
                observed_outcome=first.observed_outcome,
                non_abort_execution_count=first.non_abort_execution_count,
                exact_reason_match=(
                    first.exact_reason
                    == backends_runner.EXPECTED_REASON[control_id]
                ),
                deterministic_repeat=deterministic,
                baseline_hash_unchanged=backend_hashes_unchanged,
            )
        )

    evaluated = evaluate_negative_controls(records)
    evaluated_by_id = {item.control_id: item for item in evaluated.results}
    specs_by_id = {item.control_id: item for item in REGISTRY}

    rows: list[dict[str, Any]] = []
    for spec in REGISTRY:
        control_id = spec.control_id
        if control_id in prebind_pairs and control_id not in baseline_holds:
            first, second = prebind_pairs[control_id]
            expected = module.EXPECTED_REASON[control_id]
            source = "PREBIND_RUNNER_REEXECUTED_UNMODIFIED"
        elif control_id in backend_pairs and control_id not in baseline_holds:
            first, second = backend_pairs[control_id]
            expected = backends_runner.EXPECTED_REASON[control_id]
            source = "RUNTIME_FAIL_CLOSED_BACKENDS_V2"
        else:
            rows.append(
                {
                    "control_id": control_id,
                    "status": "NOT_RUN_BASELINE_HOLD",
                    "hold_reason": baseline_holds.get(control_id),
                }
            )
            continue
        evaluated_result = evaluated_by_id[control_id]
        rows.append(
            {
                "control_id": control_id,
                "stimulus": spec.stimulus,
                "required_observation": spec.required_observation,
                "canonical_outcome": spec.canonical_outcome,
                "future_gate": spec.future_gate,
                "execution_source": source,
                "executed": True,
                "status": evaluated_result.status.value,
                "runner_scope": first.scope,
                "baseline": {
                    "qualified": first.baseline_qualified,
                    "assertion": first.baseline_assertion,
                },
                "mutation": {
                    "deep_copy": True,
                    "single_fault": True,
                    "path": first.mutation_path,
                    "description": first.mutation_description,
                },
                "observed_outcome": first.observed_outcome,
                "non_abort_execution_count": first.non_abort_execution_count,
                "exact_reason_expected": expected,
                "exact_reason_observed": first.exact_reason,
                "exact_reason_match": first.exact_reason == expected,
                "deterministic_repeat": first == second,
                "repeat_digest": canonical_digest(asdict(first)),
                "details": dict(first.details),
            }
        )

    summary = {
        "total": evaluated.total,
        "executed": evaluated.executed,
        "passed": evaluated.passed,
        "failed": evaluated.failed,
        "not_run_dependency_hold": evaluated.deferred,
        "not_run_executable": evaluated.not_run_executable,
        "all_controls_passed": evaluated.all_controls_passed,
    }
    historical_sha = sha256_bytes(HISTORICAL_EVIDENCE_PATH.read_bytes())
    return {
        "schema": "SIM13_V2_FULL_REGISTRY_20_OF_20_V2",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "scope": "FULL_NC01_NC20_REGISTRY_REEXECUTION__NOT_PRODUCTION_AUTHORIZATION",
        "work_order": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/loop_b/SIM13_BACKEND_WORK_ORDERS_V1.json",
        "registry_source": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/negative_controls.py",
        "prebind_hashes_unchanged": prebind_hashes_unchanged,
        "backend_hashes_unchanged": backend_hashes_unchanged,
        "summary": summary,
        "controls": rows,
        "historical_15_of_20_evidence": {
            "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json",
            "sha256": historical_sha,
            "disposition": "PRESERVED_READ_ONLY_NOT_OVERWRITTEN_NOT_REWRITTEN",
        },
        "release_credit": False,
        "next_stage_authorized": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "truth_guard": "only executed single-fault probes may PASS; UNKNOWN is never PASS",
    }


def build_gate(evidence: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = evidence["summary"]
    all_pass = (
        summary["total"] == 20
        and summary["executed"] == 20
        and summary["passed"] == 20
        and summary["failed"] == 0
        and summary["all_controls_passed"] is True
    )
    per_control = {
        row["control_id"]: row["status"] for row in evidence["controls"]
    }
    return {
        "schema": "SIM13_20_OF_20_GATE_V1",
        "generated_date_local": GENERATED_DATE_LOCAL,
        "checkpoint": "SIM13_20_OF_20_GATE",
        "nc_score": "20/20" if all_pass else f"{summary['passed']}/20",
        "per_control_status": per_control,
        "evidence": {
            "path": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/runtime_fail_closed_backends_v2/evidence/SIM13_V2_FULL_REGISTRY_20_OF_20_V2.json",
            "sha256": None,  # filled after write by the emitter
        },
        "new_backend_gates": {
            "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2": "results/SIM13_RUNTIME_FAIL_CLOSED_GATE_V2.json",
            "SIM13_DYNAMICS_BACKEND_GATE_V2": "results/SIM13_DYNAMICS_BACKEND_GATE_V2.json",
            "SIM13_CONTACT_GRASP_GATE_V2": "results/SIM13_CONTACT_GRASP_GATE_V2.json",
        },
        "maximum_operational_state": "ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY",
        "mech_to_embodied_handoff_g12_harness": "NOT_IN_A3_SCOPE_DEPENDS_ON_MECHANICAL_ROUTE_C_LINE__REGISTERED_NOT_FORGED",
        "gate_passed": all_pass,
        "verdict": (
            "SIM13_NC_REGISTRY_20_OF_20_PASS__PENDING_OWNER_REVIEW__NO_RELEASE_CREDIT"
            if all_pass
            else "SIM13_NC_REGISTRY_NOT_20_OF_20"
        ),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def write_all() -> dict[str, Any]:
    evidence = build_full_registry()
    write_canonical_json(EVIDENCE_PATH, evidence)
    gate = dict(build_gate(evidence))
    gate["evidence"]["sha256"] = sha256_bytes(EVIDENCE_PATH.read_bytes())
    write_canonical_json(GATE_PATH, gate)
    return {"evidence": evidence, "gate": gate}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if args.check_only:
        evidence = build_full_registry()
        print(json.dumps(evidence["summary"], sort_keys=True))
        return 0 if evidence["summary"]["all_controls_passed"] else 1
    output = write_all()
    print(json.dumps(output["evidence"]["summary"], sort_keys=True))
    print(output["gate"]["verdict"])
    return 0 if output["gate"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
