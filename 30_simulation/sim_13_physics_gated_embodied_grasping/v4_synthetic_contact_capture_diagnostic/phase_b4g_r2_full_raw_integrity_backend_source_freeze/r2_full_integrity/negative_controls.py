"""Preregistered mutation controls for the source-only integrity backend."""

from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any, Callable

from .clearance import certify_clearance_independent
from .context import ContextError
from .fixture_factory import write_technical_fixture
from .integrity import G03, G05, G07, G08, G09, G10, G11, G16, evaluate_full_raw_integrity
from .source_api import SourceAPIError, verify_source_bindings


def _case_control(package_root: Path, gate_id: str, mutator: Callable[[dict[str, Any]], None], channel: str = "array") -> bool:
    with tempfile.TemporaryDirectory(prefix=".nc-fixture-", dir=package_root) as directory:
        kwargs = {f"{channel}_mutator": mutator}
        case, context = write_technical_fixture(Path(directory), **kwargs).load()
        report = evaluate_full_raw_integrity(case, context)
        return report["gate_records"][gate_id]["scientific_predicate"] is False


def _context_rejection(package_root: Path, mutator: Callable[[dict[str, Any]], None], channel: str) -> bool:
    with tempfile.TemporaryDirectory(prefix=".nc-fixture-", dir=package_root) as directory:
        kwargs = {f"{channel}_mutator": mutator}
        bundle = write_technical_fixture(Path(directory), **kwargs)
        try:
            bundle.load()
        except ContextError:
            return True
        return False


def run_negative_controls(package_root: Path | None = None) -> dict[str, Any]:
    root = Path(package_root or Path(__file__).resolve().parent.parent).resolve()
    controls: list[dict[str, Any]] = []

    def record(control_id: str, target: str, killed: bool) -> None:
        controls.append({"control_id": control_id, "target": target, "killed": bool(killed)})

    record("FI-NC01", G03, _case_control(root, G03, lambda arrays: arrays["command_Q_14"].__setitem__((1, 0), 1.0e-9)))

    def momentum(arrays):
        arrays["total_linear_momentum_N_s"][-1, 0] = 2.0e-9
        arrays["post_total_linear_momentum_N_s"][:] = arrays["total_linear_momentum_N_s"][-1]

    record("FI-NC02", G05, _case_control(root, G05, momentum))
    record("FI-NC03", G07, _case_control(root, G07, lambda arrays: arrays["contact_force_N"].__setitem__(1, 2.0e-12)))
    record("FI-NC04", G08, _case_control(root, G08, lambda arrays: arrays["command_Q_14"].__setitem__((2, 12), arrays["command_Q_14"][2, 12] + 1.0e-9)))
    record("FI-NC05", G09, _case_control(root, G09, lambda arrays: arrays["left_gap_m"].__setitem__(-2, 0.0)))
    record("FI-NC06", G10, _case_control(root, G10, lambda arrays: arrays["post_service_state_29"].__setitem__((0, 0), 1.0e-9)))
    record("FI-NC07", G11, _case_control(root, G11, lambda parent: parent["terminal_service_state_29"].__setitem__(0, parent["terminal_service_state_29"][0] + 2.0e-12), channel="parent"))
    record("FI-NC08", G16, _case_control(root, G16, lambda arrays: arrays["stage_gap_jacobian_P"].__setitem__((1, 0, 0), arrays["stage_gap_jacobian_P"][1, 0, 0] + 1.0e-6)))

    def acquisition_attack(payload):
        payload["event"]["target"]["position_inertial_m"][0] += 1.0e-6

    record("FI-NC09", "ACQUISITION_INITIAL_STATE_BINDING", _context_rejection(root, acquisition_attack, "acquisition"))
    record("FI-NC10", "PARENT_FILE_BYTE_BINDING", _context_rejection(root, lambda context: context["parent_trace_binding"].__setitem__("bytes", context["parent_trace_binding"]["bytes"] + 1), "context"))
    record("FI-NC11", "AUTHORIZATION_ESCALATION", _context_rejection(root, lambda context: context.__setitem__("execution_evidence_class", "AUTHORIZED_R2_RAW_CASE"), "context"))

    endpoint_result = certify_clearance_independent(
        [0.0, 0.001], [2.0e-6, 2.0e-6], [2.0e-6, 2.0e-6],
        [-0.01, 0.01], [0.0, 0.0], acquisition_time_s=-0.001,
        ledger_interval_certified=[True],
    )
    record("FI-NC12", "ENDPOINT_ONLY_CLEARANCE", endpoint_result["finite_event"] is False)

    from . import source_api

    original = source_api.GEOMETRY_REPLAY_BINDING
    try:
        source_api.GEOMETRY_REPLAY_BINDING = (original[0], "0" * 64)
        try:
            verify_source_bindings()
        except SourceAPIError:
            source_drift_killed = True
        else:
            source_drift_killed = False
    finally:
        source_api.GEOMETRY_REPLAY_BINDING = original
    record("FI-NC13", "FROZEN_SOURCE_DRIFT", source_drift_killed)

    with tempfile.TemporaryDirectory(prefix=".nc-fixture-", dir=root) as directory:
        def ideal_power(arrays):
            arrays["ideal_constraint_power_W"][1] = 2.0e-10

        case, context = write_technical_fixture(Path(directory), array_mutator=ideal_power).load()
        shared_report = evaluate_full_raw_integrity(case, context)
        shared_killed = bool(
            shared_report["gate_records"][G07]["scientific_predicate"] is True
            and shared_report["shared_integrity_preconditions"]["active_ideal_constraint_power_pass"] is False
            and shared_report["technical_fixture_full_raw_integrity_predicate_pass"] is False
        )
    record("FI-NC14", "SHARED_IDEAL_CONSTRAINT_POWER_PRECONDITION", shared_killed)
    passed = all(item["killed"] for item in controls)
    return {
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_NEGATIVE_CONTROLS_V1",
        "passed": passed,
        "control_count": len(controls),
        "killed_count": sum(1 for item in controls if item["killed"]),
        "controls": controls,
        "trajectory_count": 0,
        "execution_credit": False,
    }


__all__ = ["run_negative_controls"]
