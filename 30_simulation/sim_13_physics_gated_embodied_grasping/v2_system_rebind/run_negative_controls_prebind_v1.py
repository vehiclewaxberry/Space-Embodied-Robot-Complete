#!/usr/bin/env python3
"""Execute the conservative Sim13 V2 NC01--NC20 prebind subset.

This runner never creates or binds a URDF/interface and never upgrades a Gate.
Every executed control starts from a qualified baseline and applies one
deep-copied conceptual fault.  Controls whose required production interface is
absent remain ``NOT_RUN_DEPENDENCY_HOLD`` instead of being filled with a
synthetic PASS.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Callable, Mapping
from unittest.mock import patch
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from sim13_v2 import authority_resolver as resolver_module
from sim13_v2.authority_resolver import AuthorityResolver
from sim13_v2.contact_preflight import (
    ContactDecision,
    ContactState,
    contact_release_allowed,
)
from sim13_v2.contracts import (
    GateEvidence,
    GateState,
    HighLevelAction,
    REQUIRED_GATES,
    _authority_snapshot,
    enforce_fail_closed,
    parse_action,
)
from sim13_v2.env import Sim13V2Environment
from sim13_v2.free_floating_dynamics import (
    BACKEND_SCOPE,
    PRODUCTION_DYNAMICS_GATE_PASSED,
    URDFTreeDynamics,
)
from sim13_v2.negative_controls import (
    ControlStatus,
    NegativeControlRecord,
    REGISTRY,
    evaluate_negative_controls,
)
from sim13_v2.system_model import EXPECTED_FRAME_ONLY_LINKS, SystemModel


EVIDENCE_PATH = HERE / "evidence" / "SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json"
SOURCE_V2_DIR = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/source_only_v2"
)
URDF_SOURCE_PATH = SOURCE_V2_DIR / "unified_r2_urdf_source_v2.py"
EXPECTED_TOTAL_MASS_KG = 31.022864807342987
DOUBLE_COUNT_TOTAL_MASS_KG = 37.05784541499227


@dataclass(frozen=True)
class ProbeResult:
    baseline_qualified: bool
    detected: bool
    observed_outcome: str
    exact_reason: str
    non_abort_execution_count: int
    scope: str
    baseline_assertion: str
    mutation_path: str
    mutation_description: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class RunnerContext:
    urdf_bytes: bytes
    source_pin_paths: tuple[Path, ...]
    temporary_root: Path


Probe = Callable[[RunnerContext, str], ProbeResult]


EXPECTED_REASON = {
    "NC01": "DOCUMENT_SCHEMA_MISMATCH",
    "NC02": "BYTES_OR_SHA256_MISMATCH",
    "NC03": "UNIFIED_R2_TOPOLOGY_19_LINKS_18_JOINTS_REQUIRED",
    "NC04": "TOTAL_MASS_RECOMPOSITION_MISMATCH",
    "NC05": "B601_PARENT_CHILD_SIGNATURE_MISMATCH",
    "NC06": "FRAME_ONLY_LINK_HAS_INERTIAL_VISUAL_OR_COLLISION",
    "NC07": "PHYSICAL_LOAD_PATH_TRAVERSES_M_DYNAMICS_NONPHYSICAL",
    "NC08": "MECHANICAL_SYSTEM_BINDING_UNKNOWN",
    "NC09": "HARNESS_RATED_ENVELOPE_UNKNOWN",
    "NC10": "CONTACT_PHYSICS_READY_FAIL",
    "NC11": "BACKEND_SCOPE_REJECTS_CONTACT_OR_TRAINING_CLAIM",
    "NC12": "SYSTEM_URDF_NOT_HASH_BOUND_AND_AVAILABLE",
    "NC13": "IK_REACHABLE_FAIL",
    "NC14": "CALLER_SUPPLIED_PASS_FIELD_REJECTED",
    "NC17": "SINGLE_LINK_MASS_SENSITIVITY_DETECTED",
}


DEPENDENCY_HOLDS = {
    "NC15": "fresh action/context-bound snapshot receipt, trusted clock, nonce and replay store are not implemented",
    "NC16": "backend capability token and mandatory shield-attestation admission interface are not implemented",
    "NC18": "integrated non-ABORT joint/base/end-effector state evolution backend is not implemented",
    "NC19": "authoritative narrow-phase contact backend and released contact geometry are absent",
    "NC20": "action-bound 150 kg feasibility/post-grasp evaluator receipt is not implemented",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_digest(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _load_source_model(temporary_root: Path) -> RunnerContext:
    spec = importlib.util.spec_from_file_location("sim13_v2_nc_source", URDF_SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load dormant Unified R2 source module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs, _ = module._load_inputs_snapshot()
    payloads = module._verify_source_pins(inputs)
    robot = module._build_robot(inputs, payloads)
    source_pins = tuple(
        sorted(
            (PROJECT_ROOT / record["path"]).resolve()
            for record in inputs["source_pins"].values()
        )
    )
    return RunnerContext(
        ET.tostring(robot, encoding="utf-8"),
        source_pins,
        temporary_root,
    )


def _artifact_record(
    path: str,
    payload: bytes | None,
    *,
    schema: str | None = None,
    verdict: str | None = None,
    next_stage_authorized: bool | None = None,
) -> dict[str, Any]:
    return {
        "path": path,
        "bytes": None if payload is None else len(payload),
        "sha256": None if payload is None else _sha256_bytes(payload),
        "schema": schema,
        "verdict": verdict,
        "next_stage_authorized": next_stage_authorized,
    }


def _unit_authority_config(project: Path, config_dir: Path, interface_payload: bytes) -> dict[str, Any]:
    absent = _artifact_record("future/not_instantiated", None)
    return {
        "schema": "SIM13_V2_AUTHORITY_BINDINGS_V1",
        "scope": "SOURCE_ONLY_PREBIND_NOT_BOUND_NOT_LOADED",
        "project_root": os.path.relpath(project, config_dir).replace(os.sep, "/"),
        "artifacts": {
            "system_interface": _artifact_record(
                "evidence/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
                interface_payload,
                schema="MECH_RL_SYSTEM_INTERFACE_V2",
                verdict="UNIT_BASELINE_HOLD",
                next_stage_authorized=False,
            ),
            "system_urdf": absent,
        },
        "gate_sources": {
            name: {
                "artifact": "system_interface",
                "field": "/next_stage_authorized",
                "pass_value": True,
            }
            for name in REQUIRED_GATES
        },
    }


def _resolve_unit_case(case_root: Path, config: Mapping[str, Any], interface_payload: bytes):
    project = case_root / "project"
    config_dir = project / "30_simulation/sim13/v2_system_rebind/config"
    interface_path = project / "evidence/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    config_dir.mkdir(parents=True, exist_ok=True)
    interface_path.parent.mkdir(parents=True, exist_ok=True)
    interface_path.write_bytes(interface_payload)
    config_path = config_dir / "authority_bindings_v2.json"
    config_path.write_text(
        json.dumps(config, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    with (
        patch.object(resolver_module, "_AUTHORITY_BINDINGS_PATH", config_path),
        patch.object(resolver_module, "_EXPECTED_PROJECT_ROOT", project),
    ):
        return AuthorityResolver().resolve()


def _probe_nc01(context: RunnerContext, repeat: str) -> ProbeResult:
    case_root = context.temporary_root / f"NC01_{repeat}"
    baseline_document = {
        "schema": "MECH_RL_SYSTEM_INTERFACE_V2",
        "technical_verdict": "UNIT_BASELINE_HOLD",
        "next_stage_authorized": False,
    }
    baseline_payload = json.dumps(baseline_document, sort_keys=True).encode("utf-8")
    project = case_root / "project"
    config_dir = project / "30_simulation/sim13/v2_system_rebind/config"
    baseline_config = _unit_authority_config(project, config_dir, baseline_payload)
    baseline = _resolve_unit_case(case_root, baseline_config, baseline_payload)

    mutation = copy.deepcopy(baseline_document)
    mutation["schema"] = "MECH_RL_INTERFACE_V1"
    mutated_payload = json.dumps(mutation, sort_keys=True).encode("utf-8")
    mutated_config = copy.deepcopy(baseline_config)
    mutated_config["artifacts"]["system_interface"].update(
        {
            "bytes": len(mutated_payload),
            "sha256": _sha256_bytes(mutated_payload),
        }
    )
    mutated = _resolve_unit_case(case_root, mutated_config, mutated_payload)
    artifact = mutated.artifacts.get("system_interface")
    reason = artifact.reason_code if artifact is not None else "ARTIFACT_RESULT_MISSING"
    detected = reason == EXPECTED_REASON["NC01"]
    return ProbeResult(
        baseline.config_valid and baseline.artifacts["system_interface"].verified,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        reason,
        0,
        "UNIT_KERNEL_NOT_PRODUCTION_RUNTIME",
        "hash-bound V2-schema interface document is accepted by the isolated resolver",
        "/artifacts/system_interface/document/schema",
        "replace only the interface schema with the legacy V1 schema; refreshed pins are derived bookkeeping",
        {"mutated_artifact_verified": artifact.verified if artifact else None},
    )


def _probe_nc02(context: RunnerContext, repeat: str) -> ProbeResult:
    case_root = context.temporary_root / f"NC02_{repeat}"
    document = {
        "schema": "MECH_RL_SYSTEM_INTERFACE_V2",
        "technical_verdict": "UNIT_BASELINE_HOLD",
        "next_stage_authorized": False,
    }
    payload = json.dumps(document, sort_keys=True).encode("utf-8")
    project = case_root / "project"
    config_dir = project / "30_simulation/sim13/v2_system_rebind/config"
    baseline_config = _unit_authority_config(project, config_dir, payload)
    baseline = _resolve_unit_case(case_root, baseline_config, payload)
    mutation = copy.deepcopy(baseline_config)
    mutation["artifacts"]["system_interface"]["sha256"] = "0" * 64
    mutated = _resolve_unit_case(case_root, mutation, payload)
    artifact = mutated.artifacts.get("system_interface")
    reason = artifact.reason_code if artifact is not None else "ARTIFACT_RESULT_MISSING"
    detected = reason == EXPECTED_REASON["NC02"]
    return ProbeResult(
        baseline.config_valid and baseline.artifacts["system_interface"].verified,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        reason,
        0,
        "UNIT_KERNEL_NOT_PRODUCTION_RUNTIME",
        "the exact interface bytes and SHA-256 pin verify before mutation",
        "/artifacts/system_interface/sha256",
        "replace only the expected SHA-256 with a wrong 64-hex digest",
        {"mutated_artifact_verified": artifact.verified if artifact else None},
    )


def _xml_root(context: RunnerContext) -> ET.Element:
    return ET.fromstring(context.urdf_bytes)


def _find_named(root: ET.Element, tag: str, name: str) -> ET.Element:
    matches = [item for item in root.findall(tag) if item.get("name") == name]
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {tag} named {name}")
    return matches[0]


def _probe_nc03(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_root = _xml_root(context)
    baseline = SystemModel.from_xml_bytes(
        ET.tostring(baseline_root, encoding="utf-8"), artifact_root=SOURCE_V2_DIR
    )
    mutation = copy.deepcopy(baseline_root)
    mutation.remove(_find_named(mutation, "link", "bus_primary_structure_candidate_v1"))
    mutation.remove(
        _find_named(mutation, "joint", "bus_to_bus_primary_structure_candidate_v1")
    )
    reason = "MUTATION_NOT_REJECTED"
    try:
        SystemModel.from_xml_bytes(
            ET.tostring(mutation, encoding="utf-8"), artifact_root=SOURCE_V2_DIR
        )
    except ValueError as exc:
        if str(exc) == "Unified-R2 topology must be exactly 19 links / 18 joints":
            reason = EXPECTED_REASON["NC03"]
    detected = reason == EXPECTED_REASON["NC03"]
    return ProbeResult(
        len(baseline.link_names) == 19 and len(baseline.joint_names) == 18,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        reason,
        0,
        "SOURCE_ONLY_IN_MEMORY_URDF_KERNEL",
        "selected explicit-structure baseline parses as exactly 19 links / 18 joints",
        "/robot/{bus_primary_structure_link,bus_to_structure_joint}",
        "remove the single explicit-structure branch to inject the aggregate 18-link mode",
        {"mutated_links": 18, "mutated_joints": 17},
    )


def _probe_nc04(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_root = _xml_root(context)
    baseline = SystemModel.from_xml_bytes(context.urdf_bytes, artifact_root=SOURCE_V2_DIR)
    mutation = copy.deepcopy(baseline_root)
    bus = _find_named(mutation, "link", "spacecraft_bus")
    mass = bus.find("inertial/mass")
    if mass is None:
        raise RuntimeError("spacecraft_bus mass is absent")
    added_mass = DOUBLE_COUNT_TOTAL_MASS_KG - EXPECTED_TOTAL_MASS_KG
    mass.set("value", f"{float(mass.get('value')) + added_mass:.17g}")
    mutated_payload = ET.tostring(mutation, encoding="utf-8")
    recomposed_mass = URDFTreeDynamics(mutated_payload).total_mass_kg
    kernel_exception = "MUTATION_NOT_REJECTED"
    try:
        SystemModel.from_xml_bytes(mutated_payload, artifact_root=SOURCE_V2_DIR)
    except ValueError as exc:
        kernel_exception = str(exc)
    detected = (
        abs(recomposed_mass - DOUBLE_COUNT_TOTAL_MASS_KG) <= 1.0e-12
        and kernel_exception
        == "Unified-R2 total mass must equal the selected 31.022864807342987 kg contract"
    )
    return ProbeResult(
        abs(baseline.total_mass_kg - EXPECTED_TOTAL_MASS_KG) <= 1.0e-12,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        EXPECTED_REASON["NC04"] if detected else "MASS_CONTRACT_ACCEPTED_DOUBLE_COUNT",
        0,
        "SOURCE_ONLY_IN_MEMORY_MASS_CONTRACT",
        "baseline recomposes to 31.022864807342987 kg",
        "/robot/link[@name='spacecraft_bus']/inertial/mass/@value",
        "add the already represented 6.034980607649281 kg primary structure once more",
        {
            "baseline_mass_kg": baseline.total_mass_kg,
            "mutated_mass_kg": recomposed_mass,
            "forbidden_total_kg": DOUBLE_COUNT_TOTAL_MASS_KG,
            "kernel_exception": kernel_exception,
        },
    )


_B601_PARENT_CHILD = {
    "joint1": ("base_link", "link1"),
    "joint2": ("link1", "link2"),
    "joint3": ("link2", "link3"),
    "joint4": ("link3", "link4"),
    "joint5": ("link4", "link5"),
    "joint6": ("link5", "link6"),
    "gripper_joint": ("link6", "gripper_link"),
    "gripper_joint1": ("gripper_link", "gripper_left"),
    "gripper_joint2": ("gripper_link", "gripper_right"),
}


def _b601_signature(root: ET.Element) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for name in _B601_PARENT_CHILD:
        joint = _find_named(root, "joint", name)
        parent = joint.find("parent")
        child = joint.find("child")
        if parent is None or child is None:
            raise RuntimeError(f"{name} parent/child missing")
        result[name] = (str(parent.get("link")), str(child.get("link")))
    return result


def _probe_nc05(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_root = _xml_root(context)
    baseline_signature = _b601_signature(baseline_root)
    mutation = copy.deepcopy(baseline_root)
    joint3 = _find_named(mutation, "joint", "joint3")
    joint3.find("parent").set("link", "spacecraft_bus")  # type: ignore[union-attr]
    changed_signature = _b601_signature(mutation)
    detected = changed_signature != _B601_PARENT_CHILD
    return ProbeResult(
        baseline_signature == _B601_PARENT_CHILD,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        EXPECTED_REASON["NC05"] if detected else "B601_SIGNATURE_DRIFT_NOT_DETECTED",
        0,
        "SOURCE_ONLY_IN_MEMORY_SUBTREE_KERNEL",
        "all nine accepted B601 joint parent/child pairs match the frozen signature",
        "/robot/joint[@name='joint3']/parent/@link",
        "replace only joint3 parent link2 with spacecraft_bus",
        {"expected_joint3": ["link2", "link3"], "mutated_joint3": list(changed_signature["joint3"])},
    )


def _frame_contract_clean(root: ET.Element) -> bool:
    return all(not list(_find_named(root, "link", name)) for name in EXPECTED_FRAME_ONLY_LINKS)


def _probe_nc06(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_root = _xml_root(context)
    mutation = copy.deepcopy(baseline_root)
    ET.SubElement(_find_named(mutation, "link", "M_DYNAMICS_NONPHYSICAL"), "visual")
    detected = not _frame_contract_clean(mutation)
    return ProbeResult(
        _frame_contract_clean(baseline_root),
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        EXPECTED_REASON["NC06"] if detected else "FRAME_ONLY_POLLUTION_NOT_DETECTED",
        0,
        "SOURCE_ONLY_IN_MEMORY_FRAME_KERNEL",
        "D, D-pattern and M links contain no inertial, visual or collision children",
        "/robot/link[@name='M_DYNAMICS_NONPHYSICAL']/visual",
        "add one visual child to the M frame-only link",
        {"polluted_frame": "M_DYNAMICS_NONPHYSICAL", "injected_child": "visual"},
    )


def _probe_nc07(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_root = _xml_root(context)
    SystemModel.from_xml_bytes(context.urdf_bytes, artifact_root=SOURCE_V2_DIR)
    mutation = copy.deepcopy(baseline_root)
    joint = _find_named(mutation, "joint", "m3r_lumped_link_to_base_link")
    joint.find("parent").set("link", "M_DYNAMICS_NONPHYSICAL")  # type: ignore[union-attr]
    raw_reason = "MUTATION_NOT_REJECTED"
    try:
        SystemModel.from_xml_bytes(
            ET.tostring(mutation, encoding="utf-8"), artifact_root=SOURCE_V2_DIR
        )
    except ValueError as exc:
        if str(exc) in {
            "Unified-R2 joint identity/type/parent-child tree has drifted",
            "B601 physical load path does not follow S-D-pattern-bridge-M3R-base",
        }:
            raw_reason = EXPECTED_REASON["NC07"]
    detected = raw_reason == EXPECTED_REASON["NC07"]
    return ProbeResult(
        True,
        detected,
        "REJECT_BINDING" if detected else "BINDING_ESCAPED",
        raw_reason,
        0,
        "SOURCE_ONLY_IN_MEMORY_LOAD_PATH_KERNEL",
        "baseline B601 physical path is S-D-pattern-bridge-M3R-base and excludes M",
        "/robot/joint[@name='m3r_lumped_link_to_base_link']/parent/@link",
        "replace only the physical mount parent with M_DYNAMICS_NONPHYSICAL",
        {"mutated_parent": "M_DYNAMICS_NONPHYSICAL"},
    )


def _gate_probe(
    context: RunnerContext,
    repeat: str,
    *,
    control_id: str,
    gate_name: str,
    state: GateState,
) -> ProbeResult:
    baseline_evidence = {
        name: GateEvidence(GateState.PASS, "UNIT_BASELINE", f"/{name}", f"{name.upper()}_PASS")
        for name in REQUIRED_GATES
    }
    baseline_snapshot = _authority_snapshot(baseline_evidence)
    action = HighLevelAction("UNIT_CANDIDATE", "UNIT_TIMING", "S1")
    baseline_decision = enforce_fail_closed(action, baseline_snapshot)
    mutation = copy.deepcopy(baseline_evidence)
    mutation[gate_name] = GateEvidence(
        state, "UNIT_SINGLE_GATE_MUTATION", f"/{gate_name}", f"{gate_name.upper()}_{state.value}"
    )
    decision = enforce_fail_closed(action, _authority_snapshot(mutation))
    expected = EXPECTED_REASON[control_id]
    detected = (
        decision.executed_action.is_abort
        and decision.intervened
        and decision.reason_codes == ("SHIELD_EXECUTED_ABORT", expected)
    )
    return ProbeResult(
        not baseline_decision.intervened and not baseline_decision.executed_action.is_abort,
        detected,
        "MASK_TO_ABORT_ONLY" if detected else "NON_ABORT_ESCAPED",
        expected if detected else "GATE_MUTATION_REASON_MISMATCH",
        0 if decision.executed_action.is_abort else 1,
        "UNIT_KERNEL_NOT_PRODUCTION_RUNTIME",
        "a private-factory 12-PASS unit snapshot admits one high-level non-ABORT only inside the contract kernel",
        f"/gate_snapshot/{gate_name}",
        f"replace only {gate_name} PASS with {state.value}",
        {"mutated_gate": gate_name, "mutated_state": state.value, "executed_strategy": decision.executed_action.strategy_id},
    )


def _probe_nc08(context: RunnerContext, repeat: str) -> ProbeResult:
    return _gate_probe(context, repeat, control_id="NC08", gate_name="mechanical_system_binding", state=GateState.UNKNOWN)


def _probe_nc09(context: RunnerContext, repeat: str) -> ProbeResult:
    return _gate_probe(context, repeat, control_id="NC09", gate_name="harness_rated_envelope", state=GateState.UNKNOWN)


def _probe_nc10(context: RunnerContext, repeat: str) -> ProbeResult:
    return _gate_probe(context, repeat, control_id="NC10", gate_name="contact_physics_ready", state=GateState.FAIL)


def _probe_nc11(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_claim = {
        "requested_scope": "PRESCRIBED_JOINT_MOTION_MOMENTUM_PREBIND",
        "contact_or_training_claim": False,
    }
    mutation = copy.deepcopy(baseline_claim)
    mutation["contact_or_training_claim"] = True
    local_pass = ContactDecision(ContactState.PASS, ("UNIT_LOCAL_PREFLIGHT_PASS",))
    release = contact_release_allowed(
        local_pass,
        system_binding_passed=True,
        runtime_gate_passed=True,
        dynamics_gate_passed=PRODUCTION_DYNAMICS_GATE_PASSED,
    )
    detected = (
        mutation["contact_or_training_claim"] is True
        and "NOT_CONTACT" in BACKEND_SCOPE
        and PRODUCTION_DYNAMICS_GATE_PASSED is False
        and release is False
    )
    return ProbeResult(
        baseline_claim["contact_or_training_claim"] is False
        and BACKEND_SCOPE == "PRESCRIBED_JOINT_MOTION_MOMENTUM_PREBIND_NOT_TORQUE_DRIVEN_NOT_CONTACT",
        detected,
        "FAIL_GATE" if detected else "CONTACT_CLAIM_ESCAPED",
        EXPECTED_REASON["NC11"] if detected else "BACKEND_SCOPE_GUARD_MISSING",
        0,
        "SOURCE_ONLY_BACKEND_SCOPE_AND_CONTACT_ALL_OF_KERNEL",
        "momentum backend declares NOT_CONTACT and production_dynamics_gate_passed=false",
        "/consumer_claim/contact_or_training_claim",
        "replace only the diagnostic momentum claim with a contact/training claim",
        {"backend_scope": BACKEND_SCOPE, "contact_release_allowed": release},
    )


def _probe_nc12(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline_request = {"kind": "ABORT", "action": HighLevelAction.abort().as_dict()}
    mutation = copy.deepcopy(baseline_request)
    mutation["kind"] = "NON_ABORT"
    mutation["action"] = {
        "grasp_candidate_id": "GC_PRIMARY",
        "capture_timing_id": "T_NOMINAL",
        "strategy_id": "S1",
    }
    baseline_env = Sim13V2Environment()
    baseline_env.reset()
    _, _, _, _, baseline_info = baseline_env.step(baseline_request["action"])
    env = Sim13V2Environment()
    observation, _ = env.reset()
    _, _, _, _, info = env.step(mutation["action"])
    model_error = observation["system"]["model_error"]
    detected = (
        baseline_info["executed_action"]["strategy_id"] == "ABORT"
        and info["executed_action"]["strategy_id"] == "ABORT"
        and model_error == EXPECTED_REASON["NC12"]
    )
    return ProbeResult(
        baseline_info["shield_intervened"] is False,
        detected,
        "REJECT_BINDING" if detected else "CONSUMER_LOAD_ESCAPED",
        model_error if isinstance(model_error, str) else "SYSTEM_MODEL_ERROR_MISSING",
        0 if info["executed_action"]["strategy_id"] == "ABORT" else 1,
        "CURRENT_HASH_BOUND_PREBIND_AUTHORITY",
        "canonical ABORT remains executable under the current absent-URDF authority state",
        "/consumer_request",
        "replace the one high-level request object ABORT with an S1 grasp request",
        {"system_status": observation["system"]["status"], "executed_strategy": info["executed_action"]["strategy_id"]},
    )


def _probe_nc13(context: RunnerContext, repeat: str) -> ProbeResult:
    return _gate_probe(context, repeat, control_id="NC13", gate_name="ik_reachable", state=GateState.FAIL)


def _probe_nc14(context: RunnerContext, repeat: str) -> ProbeResult:
    baseline = {
        "grasp_candidate_id": "UNIT_CANDIDATE",
        "capture_timing_id": "UNIT_TIMING",
        "strategy_id": "S1",
    }
    parsed = parse_action(baseline)
    mutation = copy.deepcopy(baseline)
    mutation["mechanical_system_binding"] = "PASS"
    exact_exception = (
        "action keys must be exactly ['capture_timing_id', 'grasp_candidate_id', 'strategy_id']; "
        "extra=['mechanical_system_binding'], missing=[]"
    )
    actual = "NO_EXCEPTION"
    try:
        parse_action(mutation)
    except ValueError as exc:
        actual = str(exc)
    detected = actual == exact_exception
    return ProbeResult(
        parsed.strategy_id == "S1",
        detected,
        "REJECT_BINDING" if detected else "FORGED_PASS_ESCAPED",
        EXPECTED_REASON["NC14"] if detected else actual,
        0,
        "UNIT_KERNEL_NOT_PRODUCTION_RUNTIME",
        "the exact three-field high-level action parses before mutation",
        "/action/mechanical_system_binding",
        "add one caller-supplied PASS field to the action mapping",
        {"exception_exact_match": detected},
    )


def _probe_nc17(context: RunnerContext, repeat: str) -> ProbeResult:
    model = URDFTreeDynamics(context.urdf_bytes)
    baseline_request = {
        "link_name": "spacecraft_bus",
        "mass_scale": 1.0,
        "inertia_scale": 1.0,
    }
    mutation = copy.deepcopy(baseline_request)
    mutation["mass_scale"] = 1.01
    baseline_matrix = model.mass_matrix(None)
    identity_model = model.perturbed_link_model(**baseline_request)
    baseline_delta = float(__import__("numpy").linalg.norm(identity_model.mass_matrix(None) - baseline_matrix, ord="fro"))
    audit = model.single_link_sensitivity(None, **mutation)
    detected = (
        float(audit["mass_matrix_frobenius_delta"]) > 0.0
        and float(audit["Hbb_frobenius_delta"]) > 0.0
        and audit["original_snapshot_unchanged"] is True
    )
    return ProbeResult(
        baseline_delta <= 1.0e-15,
        detected,
        "FAIL_GATE" if detected else "PHYSICS_SENSITIVITY_ESCAPED",
        EXPECTED_REASON["NC17"] if detected else "MASS_MATRIX_UNCHANGED_AFTER_PERTURBATION",
        0,
        "SOURCE_ONLY_RIGID_MULTIBODY_MOMENTUM_SENSITIVITY_KERNEL",
        "a unity-scale deep-copied link model leaves the baseline mass matrix unchanged",
        "/single_link_perturbation/mass_scale",
        "replace only spacecraft_bus mass_scale 1.0 with 1.01",
        {
            "link_name": audit["link_name"],
            "baseline_total_mass_kg": audit["baseline_total_mass_kg"],
            "perturbed_total_mass_kg": audit["perturbed_total_mass_kg"],
            "mass_matrix_frobenius_delta": audit["mass_matrix_frobenius_delta"],
            "Hbb_frobenius_delta": audit["Hbb_frobenius_delta"],
            "Hbm_frobenius_delta": audit["Hbm_frobenius_delta"],
        },
    )


PROBES: Mapping[str, Probe] = {
    "NC01": _probe_nc01,
    "NC02": _probe_nc02,
    "NC03": _probe_nc03,
    "NC04": _probe_nc04,
    "NC05": _probe_nc05,
    "NC06": _probe_nc06,
    "NC07": _probe_nc07,
    "NC08": _probe_nc08,
    "NC09": _probe_nc09,
    "NC10": _probe_nc10,
    "NC11": _probe_nc11,
    "NC12": _probe_nc12,
    "NC13": _probe_nc13,
    "NC14": _probe_nc14,
    "NC17": _probe_nc17,
}


def _tracked_source_paths(context: RunnerContext) -> tuple[Path, ...]:
    static = (
        Path(__file__).resolve(),
        HERE / "sim13_v2/negative_controls.py",
        HERE / "sim13_v2/contracts.py",
        HERE / "sim13_v2/authority_resolver.py",
        HERE / "sim13_v2/system_model.py",
        HERE / "sim13_v2/env.py",
        HERE / "sim13_v2/free_floating_dynamics.py",
        HERE / "sim13_v2/contact_preflight.py",
        URDF_SOURCE_PATH,
        SOURCE_V2_DIR / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml",
        PROJECT_ROOT
        / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
        / "unified_r2_digital_prototype_prebind/sim13_versioned_rebind_boundary_v2"
        / "SIM13_VERSIONED_REBIND_BOUNDARY_V2.yaml",
    )
    return tuple(sorted(set(static).union(context.source_pin_paths)))


def _source_hashes(paths: tuple[Path, ...]) -> dict[str, str]:
    output: dict[str, str] = {}
    for path in paths:
        relative = path.resolve().relative_to(PROJECT_ROOT).as_posix()
        output[relative] = _sha256_file(path)
    return output


def _safe_probe(probe: Probe, context: RunnerContext, repeat: str) -> ProbeResult:
    try:
        return probe(context, repeat)
    except Exception as exc:  # evidence must record a hold instead of fabricating PASS
        return ProbeResult(
            False,
            False,
            "NOT_EXECUTED_BASELINE_OR_PROBE_ERROR",
            f"{type(exc).__name__}:{exc}",
            0,
            "PROBE_ERROR_FAIL_CLOSED",
            "baseline qualification raised an exception",
            "NONE",
            "no accepted single-fault execution",
            {},
        )


def build_evidence() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="sim13_v2_nc_prebind_") as temporary:
        context = _load_source_model(Path(temporary))
        tracked = _tracked_source_paths(context)
        before = _source_hashes(tracked)
        probe_pairs: dict[str, tuple[ProbeResult, ProbeResult]] = {
            control_id: (
                _safe_probe(probe, context, "A"),
                _safe_probe(probe, context, "B"),
            )
            for control_id, probe in PROBES.items()
        }
        after = _source_hashes(tracked)

    hashes_unchanged = before == after
    execution_records: list[NegativeControlRecord] = []
    baseline_holds: dict[str, str] = {}
    for control_id, (first, second) in probe_pairs.items():
        deterministic = first == second
        baseline_qualified = first.baseline_qualified and second.baseline_qualified
        if not baseline_qualified:
            baseline_holds[control_id] = first.exact_reason
            continue
        execution_records.append(
            NegativeControlRecord(
                control_id=control_id,
                executed=True,
                observed_outcome=first.observed_outcome,
                non_abort_execution_count=first.non_abort_execution_count,
                exact_reason_match=first.exact_reason == EXPECTED_REASON[control_id],
                deterministic_repeat=deterministic,
                baseline_hash_unchanged=hashes_unchanged,
            )
        )

    evaluated = evaluate_negative_controls(execution_records)
    evaluated_by_id = {item.control_id: item for item in evaluated.results}
    specs_by_id = {item.control_id: item for item in REGISTRY}
    rows: list[dict[str, Any]] = []
    executed = passed = failed = holds = 0
    for control_id in [item.control_id for item in REGISTRY]:
        spec = specs_by_id[control_id]
        if control_id in probe_pairs and control_id not in baseline_holds:
            first, second = probe_pairs[control_id]
            evaluated_result = evaluated_by_id[control_id]
            status = evaluated_result.status.value
            executed += 1
            if evaluated_result.status is ControlStatus.PASS:
                passed += 1
            else:
                failed += 1
            row = {
                "control_id": control_id,
                "stimulus": spec.stimulus,
                "required_observation": spec.required_observation,
                "canonical_outcome": spec.canonical_outcome,
                "future_gate": spec.future_gate,
                "registry_execution_class": spec.execution_class.value,
                "registry_dependency": spec.dependency,
                "executed": True,
                "status": status,
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
                "exact_reason_expected": EXPECTED_REASON[control_id],
                "exact_reason_observed": first.exact_reason,
                "exact_reason_match": first.exact_reason == EXPECTED_REASON[control_id],
                "deterministic_repeat": first == second,
                "repeat_digest": _canonical_digest(asdict(first)),
                "baseline_source_hashes_unchanged": hashes_unchanged,
                "details": dict(first.details),
                "hold_dependency": None,
            }
        else:
            holds += 1
            dependency = baseline_holds.get(control_id, DEPENDENCY_HOLDS.get(control_id))
            if dependency is None:
                dependency = "required qualified single-fault baseline is unavailable"
            row = {
                "control_id": control_id,
                "stimulus": spec.stimulus,
                "required_observation": spec.required_observation,
                "canonical_outcome": spec.canonical_outcome,
                "future_gate": spec.future_gate,
                "registry_execution_class": spec.execution_class.value,
                "registry_dependency": spec.dependency,
                "executed": False,
                "status": "NOT_RUN_DEPENDENCY_HOLD",
                "runner_scope": None,
                "baseline": {"qualified": False, "assertion": None},
                "mutation": {"deep_copy": False, "single_fault": False, "path": None, "description": None},
                "observed_outcome": None,
                "non_abort_execution_count": None,
                "exact_reason_expected": None,
                "exact_reason_observed": None,
                "exact_reason_match": None,
                "deterministic_repeat": None,
                "repeat_digest": None,
                "baseline_source_hashes_unchanged": hashes_unchanged,
                "details": {},
                "hold_dependency": dependency,
            }
        rows.append(row)

    total = len(REGISTRY)
    if executed + holds != total:
        raise RuntimeError("negative-control accounting does not sum to 20")
    verdict = (
        "PASS_EXECUTED_SUBSET_WITH_DEPENDENCY_HOLDS"
        if failed == 0 and passed == executed and holds > 0
        else "FAIL_EXECUTED_NEGATIVE_CONTROL_SUBSET"
    )
    return {
        "schema": "SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1",
        "generated_date_local": "2026-08-24",
        "scope": "FORMAL_SINGLE_FAULT_PREBIND_EXECUTION__NOT_PRODUCTION_RUNTIME_NOT_CONTACT_RELEASE",
        "registry_source": "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/negative_controls.py",
        "registry_sha256": before[
            "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/sim13_v2/negative_controls.py"
        ],
        "source_hashes_before": before,
        "source_hashes_after": after,
        "source_hashes_unchanged": hashes_unchanged,
        "summary": {
            "total": total,
            "executed": executed,
            "passed": passed,
            "failed": failed,
            "pass": passed,
            "fail": failed,
            "hold": holds,
            "not_run_dependency_hold": holds,
        },
        "controls": rows,
        "release": False,
        "next": False,
        "release_credit": False,
        "contact_release_eligible": False,
        "next_stage_authorized": False,
        "negative_controls_all_passed": False,
        "formal_runner_verdict": verdict,
        "truth_guard": "only executed single-fault probes may PASS; absent interfaces remain dependency HOLD",
    }


def write_evidence(path: Path = EVIDENCE_PATH) -> dict[str, Any]:
    document = build_evidence()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    # Byte-mode output freezes LF on every host; text-mode output would turn
    # this into CRLF on Windows and break an otherwise semantic-equivalent pin.
    path.write_bytes(payload.encode("utf-8"))
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE_PATH)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    document = build_evidence() if args.check_only else write_evidence(args.output)
    print(json.dumps(document["summary"], sort_keys=True))
    print(document["formal_runner_verdict"])
    return 0 if document["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
