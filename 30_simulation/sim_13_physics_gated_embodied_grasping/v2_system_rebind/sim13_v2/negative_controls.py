"""Registry and truth-preserving accounting for Sim13 V2 negative controls.

The registry mirrors NC01--NC20 from the frozen rebind boundary.  This module
does not turn a declared requirement into executed evidence: a control receives
PASS only from an explicit execution record satisfying every invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping


class ExecutionClass(str, Enum):
    CURRENT_EVIDENCE = "CURRENT_EVIDENCE_EXECUTABLE"
    SYNTHETIC_PREBIND = "SYNTHETIC_PREBIND_EXECUTABLE"
    DEPENDENCY_HOLD = "NOT_EXECUTABLE_DEPENDENCY_HOLD"


class ControlStatus(str, Enum):
    PASS = "PASS_NEGATIVE_CONTROL_DETECTED"
    FAIL = "FAIL_NEGATIVE_CONTROL_ESCAPED"
    NOT_RUN = "NOT_RUN"
    NOT_RUN_DEPENDENCY_HOLD = "NOT_RUN_DEPENDENCY_HOLD"


@dataclass(frozen=True)
class NegativeControlSpec:
    control_id: str
    stimulus: str
    required_observation: str
    canonical_outcome: str
    future_gate: str
    execution_class: ExecutionClass
    dependency: str | None = None


@dataclass(frozen=True)
class NegativeControlRecord:
    control_id: str
    executed: bool
    observed_outcome: str | None = None
    non_abort_execution_count: int | None = None
    exact_reason_match: bool | None = None
    deterministic_repeat: bool | None = None
    baseline_hash_unchanged: bool | None = None


@dataclass(frozen=True)
class NegativeControlResult:
    control_id: str
    status: ControlStatus
    reason: str


@dataclass(frozen=True)
class NegativeControlSummary:
    total: int
    executed: int
    passed: int
    failed: int
    deferred: int
    not_run_executable: int
    all_controls_passed: bool
    contact_release_eligible: bool
    results: tuple[NegativeControlResult, ...]


_RAW_SPECS = (
    ("NC01", "V1_SCHEMA_OR_FILENAME_AS_V2_BINDING", "binding_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC02", "ARTIFACT_BYTES_OR_SHA256_DRIFT", "binding_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC03", "AGGREGATE_18_LINK_MODE_MASQUERADES_AS_SELECTED_19_LINK_MODE", "topology_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC04", "EXPLICIT_STRUCTURE_DOUBLE_COUNT_TOTAL_37P05784541499227_KG", "mass_recomposition_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC05", "ACCEPTED_B601_EXACT_FIELD_DRIFT", "subtree_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC06", "FRAME_ONLY_LINK_HAS_INERTIAL_VISUAL_OR_COLLISION", "frame_contract_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC07", "D_M_ALIAS_OR_PHYSICAL_PATH_TRAVERSES_M", "load_path_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC08", "MECHANICAL_SYSTEM_BINDING_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
    ("NC09", "HARNESS_RATED_ENVELOPE_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
    ("NC10", "CONTACT_PHYSICS_READY_UNKNOWN_OR_FAIL_WITH_GRASP_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
    ("NC11", "KINEMATIC_BOOTSTRAP_OFFERED_AS_CONTACT_OR_TRAINING_PHYSICS", "backend_scope_rejected", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
    ("NC12", "URDF_ABSENT_OR_ROUTE_C_SCOPE_UNACCEPTED_OR_REBIND_UNAUTHORIZED", "consumer_load_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
    ("NC13", "ANY_INHERITED_V1_GATE_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC14", "CALLER_FORGES_PASS_WITHOUT_HASH_BOUND_EVALUATOR_RECEIPT", "authority_join_denied", "REJECT_BINDING", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC15", "STALE_OR_REPLAYED_GATE_SNAPSHOT", "snapshot_rejected", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC16", "DIRECT_BACKEND_CALL_BYPASSES_SAFETY_SHIELD", "backend_rejects_unshielded_non_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC17", "MASS_OR_INERTIA_PERTURBED_BUT_TRAJECTORY_UNCHANGED", "physics_sensitivity_failure", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC18", "NON_ABORT_STEP_CHANGES_TASK_PHASE_ONLY_WITHOUT_JOINT_BASE_OR_EE_STATE", "dynamics_state_update_failure", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", ExecutionClass.SYNTHETIC_PREBIND, None),
    ("NC19", "OVERLAPPING_GEOMETRY_DOES_NOT_UPDATE_COLLISION_OR_CONTACT_STATE", "contact_detection_failure", "FAIL_GATE", "SIM13_CONTACT_GRASP_GATE_V2", ExecutionClass.DEPENDENCY_HOLD, "authoritative narrow-phase contact backend and geometry"),
    ("NC20", "DEBRIS_150KG_3DPS_REQUESTS_NON_ABORT_WITHOUT_FEASIBILITY_AND_POST_GRASP_PASS", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", ExecutionClass.CURRENT_EVIDENCE, None),
)


REGISTRY: tuple[NegativeControlSpec, ...] = tuple(
    NegativeControlSpec(*values) for values in _RAW_SPECS
)


def _index_records(
    records: Iterable[NegativeControlRecord],
) -> Mapping[str, NegativeControlRecord]:
    output: dict[str, NegativeControlRecord] = {}
    for record in records:
        if record.control_id in output:
            raise ValueError(f"duplicate negative-control record: {record.control_id}")
        output[record.control_id] = record
    unknown = set(output).difference(spec.control_id for spec in REGISTRY)
    if unknown:
        raise ValueError(f"unknown negative-control ids: {sorted(unknown)}")
    return output


def evaluate_negative_controls(
    records: Iterable[NegativeControlRecord],
) -> NegativeControlSummary:
    indexed = _index_records(records)
    results: list[NegativeControlResult] = []
    executed = passed = failed = deferred = not_run_executable = 0
    for spec in REGISTRY:
        record = indexed.get(spec.control_id)
        if record is None or not record.executed:
            if spec.execution_class is ExecutionClass.DEPENDENCY_HOLD:
                deferred += 1
                results.append(
                    NegativeControlResult(
                        spec.control_id,
                        ControlStatus.NOT_RUN_DEPENDENCY_HOLD,
                        spec.dependency or "dependency hold",
                    )
                )
            else:
                not_run_executable += 1
                results.append(
                    NegativeControlResult(
                        spec.control_id,
                        ControlStatus.NOT_RUN,
                        "executable requirement has no execution record",
                    )
                )
            continue

        executed += 1
        invariants = (
            record.observed_outcome == spec.canonical_outcome,
            record.non_abort_execution_count == 0,
            record.exact_reason_match is True,
            record.deterministic_repeat is True,
            record.baseline_hash_unchanged is True,
        )
        if all(invariants):
            passed += 1
            results.append(
                NegativeControlResult(
                    spec.control_id,
                    ControlStatus.PASS,
                    "single-fault stimulus detected with exact fail-closed outcome",
                )
            )
        else:
            failed += 1
            results.append(
                NegativeControlResult(
                    spec.control_id,
                    ControlStatus.FAIL,
                    "one or more execution invariants were not satisfied",
                )
            )

    total = len(REGISTRY)
    all_passed = passed == total and executed == total and failed == 0
    return NegativeControlSummary(
        total=total,
        executed=executed,
        passed=passed,
        failed=failed,
        deferred=deferred,
        not_run_executable=not_run_executable,
        all_controls_passed=all_passed,
        contact_release_eligible=all_passed,
        results=tuple(results),
    )


__all__ = [
    "ControlStatus",
    "ExecutionClass",
    "NegativeControlRecord",
    "NegativeControlResult",
    "NegativeControlSpec",
    "NegativeControlSummary",
    "REGISTRY",
    "evaluate_negative_controls",
]
