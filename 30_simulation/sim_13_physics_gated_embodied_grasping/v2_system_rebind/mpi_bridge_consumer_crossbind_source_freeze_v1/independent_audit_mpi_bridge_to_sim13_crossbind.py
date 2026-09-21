"""Independent audit with direct source recomputation and black-box attacks.

This module imports no ``crossbind`` evaluator. It independently re-reads all
sources, recomputes the bridge and seven-receipt composition, and drives the
public package API only in a separate black-box Python process. The emitted
frozen audit has 79 pre-Gate checks; the read-only command adds five Gate /
terminal / inventory checks for 84 total.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


PACKAGE_ROOT = Path(__file__).resolve().parent
PACKAGE_REL = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/mpi_bridge_consumer_crossbind_source_freeze_v1"
MANIFEST_REL = "manifest/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1.json"
AUDIT_REL = "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_INDEPENDENT_AUDIT_V1.json"
GATE_REL = "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_REL = "results/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_TERMINAL_V1.json"

PINS = (
    ("OWNER_ODR45", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml", "69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5", "yaml", "M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1"),
    ("PHYSICAL_DYNAMICS_BRIDGE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml", "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C", "yaml", "B601_PHYSICAL_DYNAMICS_BRIDGE_V1"),
    ("MPI_BRIDGE_GATE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json", "60911E3C88387E2ED53601F2B541649BF90D689C57C4E74225226AE6FD10C721", "json", "MPI_BRIDGE_GATE_V1"),
    ("E21_BRIDGED_CONSUMER_GATE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/05_e21_bridged/E21_BRIDGED_ARM_PLACEMENT_GATE_V2.json", "7F670C69C6EDCF6CBF783DC22843C9EF53FD82FA88313E913C855FEB0A47E707", "json", "E21_BRIDGED_ARM_PLACEMENT_GATE_V2"),
    ("BRIDGED_MASS_INERTIA", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/06_mass_propagation/SYSTEM_MASS_PROPERTIES_BRIDGED_V1.yaml", "E5D13A8D105B78C703EFA963BCF73714586E564F9951228AFBA9AF81ECB71528", "yaml", "SYSTEM_MASS_PROPERTIES_BRIDGED_V1"),
    ("MECH_DYNAMICS_V6_CANDIDATE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/MECH_DYNAMICS_INTERFACE_V6_CANDIDATE.yaml", "4C52A68AA6E0749A2425D9E8CDB6C9F4477F5D4047C9D6C0BA6F0D95E97D184D", "yaml", "MECH_DYNAMICS_INTERFACE_V6_CANDIDATE"),
    ("EMBODIED_R3_CANDIDATE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/07_rebind/EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE.yaml", "F3D6EC1D370FB26215A259391D5026CA4C261C7C4880AE6FD70AE2C0F0DDFC56", "yaml", "EMBODIED_MECHANICAL_CONTRACT_R3_CANDIDATE"),
    ("UNIFIED_R2_FRAME_TREE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml", "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756", "yaml", "UNIFIED_R2_SYSTEM_FRAME_TREE_V2"),
    ("UNIFIED_R2_SOURCE_GATE", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_URDF_SOURCE_GATE_V2.json", "62BF5F629DEA904D63115EEE5FE7DB718A5B5EDE73B5A78B1EBFE36BC1314D7F", "json", "UNIFIED_R2_URDF_SOURCE_GATE_V2"),
    ("INTAKE_GATE", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/current_system_handoff_intake_v1/results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json", "23903C1AF1A6F7382A18E0685EF6A6010926B8C812163900BC3843B7A44BE5CE", "json", "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1"),
    ("INTAKE_TERMINAL", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/current_system_handoff_intake_v1/results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json", "543EC2247910E4E5B884EF27CC99F78ECE842B8DBF0AE55891656894ADCEBF10", "json", "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1"),
    ("PREEXEC_GATE", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json", "BBD13022F1462A59AC650EFC535C448C2004C113832E6C6ACD04C11F3EDE1F08", "json", "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1"),
    ("PREEXEC_TERMINAL", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1.json", "7E4AF02594E187942AAE67F7AD568B89E3BFD1BEA1369AAD6251F8C34EFD8D06", "json", "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1"),
    ("PREEXEC_RECEIPT_VERIFIER_SOURCE", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/preexec_security/receipts.py", "D20AD3610764C83FE7D0453A47AF6327D8260160B8C16E44E341836F422B890B", "python", None),
    ("PREEXEC_STRICT_JSON_SOURCE", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/preexecution_binding_security_source_freeze_v1/preexec_security/strict_json.py", "789C0FC73A709A8D52CA122D9C94E6D347C03E6D79D91FB4DEC56E2EBAB72E23", "python", None),
)

INTERNAL = frozenset((
    "README.md", "pytest.ini", "crossbind/__init__.py", "crossbind/constants.py", "crossbind/strict_io.py",
    "crossbind/source_bundle.py", "crossbind/bridge.py", "crossbind/receipt.py", "crossbind/policy.py",
    "crossbind/negative_controls.py", "crossbind/package.py",
    "contracts/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_CONTRACT_V1.json",
    "contracts/SYSTEM_BINDING_V3_CANDIDATE_RECEIPT_SCHEMA_V1.json",
    "contracts/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROL_CONTRACT_V1.json",
    "freeze_mpi_bridge_to_sim13_crossbind.py", "run_mpi_bridge_to_sim13_crossbind_negative_controls.py",
    "validate_mpi_bridge_to_sim13_crossbind_source_freeze.py", "independent_audit_mpi_bridge_to_sim13_crossbind.py",
    "verify_mpi_bridge_to_sim13_crossbind_read_only_replay.py", "tests/conftest.py",
    "tests/test_sources_and_bridge.py", "tests/test_receipt_and_policy.py", "tests/test_controls_and_inventory.py",
))
GENERATED = frozenset((
    MANIFEST_REL, "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1.json",
    "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1.json", AUDIT_REL, GATE_REL, TERMINAL_REL,
))
ALLOWED_FILES = INTERNAL | GENERATED
ALLOWED_DIRS = frozenset(("crossbind", "contracts", "manifest", "evidence", "results", "tests"))


class AuditError(ValueError):
    pass


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def find_repo() -> Path:
    for candidate in (PACKAGE_ROOT, *PACKAGE_ROOT.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise AuditError("REPO_NOT_FOUND")


def no_dup(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise AuditError(f"DUPLICATE_KEY:{key}")
        out[key] = value
    return out


def finite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise AuditError("NONFINITE")
    if isinstance(value, dict):
        for child in value.values():
            finite(child)
    elif isinstance(value, list):
        for child in value:
            finite(child)


def parse_json(raw: bytes) -> dict[str, Any]:
    def reject(value: str) -> None:
        raise AuditError(f"NONFINITE_CONSTANT:{value}")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=no_dup, parse_constant=reject)
    if not isinstance(value, dict):
        raise AuditError("JSON_ROOT")
    finite(value)
    return value


def parse_yaml(raw: bytes) -> dict[str, Any]:
    value = yaml.safe_load(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise AuditError("YAML_ROOT")
    finite(value)
    return value


def receipt(path: Path, rel: str) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"path": rel, "bytes": len(raw), "sha256": sha(raw)}


def inverse_rigid(matrix: list[list[float]]) -> list[list[float]]:
    out = [[0.0] * 4 for _ in range(4)]
    for i in range(3):
        for j in range(3):
            out[i][j] = matrix[j][i]
        out[i][3] = -sum(matrix[j][i] * matrix[j][3] for j in range(3))
    out[3] = [0.0, 0.0, 0.0, 1.0]
    return out


def mul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [[sum(left[i][k] * right[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def max_abs(left: list[list[float]], right: list[list[float]]) -> float:
    return max(abs(left[i][j] - right[i][j]) for i in range(4) for j in range(4))


def load_preexec_modules(repo: Path) -> tuple[Any, Any]:
    v2_root = repo / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    sys.path.insert(0, str(v2_root))
    receipts = importlib.import_module("preexecution_binding_security_source_freeze_v1.preexec_security.receipts")
    strict = importlib.import_module("preexecution_binding_security_source_freeze_v1.preexec_security.strict_json")
    return receipts, strict


def independent_composition(repo: Path) -> dict[str, Any]:
    preexec, strict = load_preexec_modules(repo)
    action = {"grasp_candidate_id": "SYNTHETIC_G0", "capture_timing_id": "SYNTHETIC_T0", "strategy_id": "S1"}
    context = {"episode_id": "SYNTHETIC_EPISODE_0001", "configuration_id": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT", "authority_epoch": 1, "target_class": "NONCOOPERATIVE_DEBRIS_150KG_3DPS"}
    kinds = tuple(preexec.KINDS)
    states = {name: "PASS" for name in (
        "ik_reachable", "external_collision_clear", "keep_out_clear", "sim10_gate", "safe00_state",
        "post_grasp_stability_gate", "gripper_configuration_accepted", "target_surface_normal_valid",
        "mechanical_system_binding", "harness_rated_envelope", "contact_physics_ready", "route_c_scope_disposition",
    )}
    payloads = {
        "SYSTEM_BINDING_V2": {"status": "HOLD", "system_urdf_sha256": "A" * 64},
        "RUNTIME_GATE_SNAPSHOT_V2": {"status": "PASS", "gate_count": 12, "gate_digest": strict.canonical_digest(states), "gate_states": states},
        "DYNAMICS_GATE_V2": {"status": "HOLD", "backend_receipt_sha256": "B" * 64},
        "CONTACT_PREFLIGHT_V2": {"status": "HOLD", "contact_receipt_sha256": "C" * 64},
        "SHIELD_ATTESTATION_V2": {"status": "PASS", "capability": preexec.SHIELD_CAPABILITY, "shielded": True},
        "FEASIBILITY_150KG_V2": {"status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0, "post_capture_rate_deg_s": 3.0633, "verdict": "INFEASIBLE_RATE", "sim10_source_sha256": "D" * 64},
        "POST_GRASP_V2": {"status": "FAIL", "target_mass_kg": 150.0, "target_rate_deg_s": 3.0, "stability_receipt_sha256": "E" * 64},
    }
    key = b"MPI-CROSSBIND-PREEXEC-SYNTHETIC-KEY-ONLY-0001"
    store = preexec.ReplayStore()
    ordered = []
    for index, kind in enumerate(kinds, start=1):
        raw = preexec.issue_synthetic_receipt(
            kind=kind, action=action, context=context, payload=payloads[kind], issued_at_unix_s=1000.0,
            expires_at_unix_s=1300.0, nonce=f"PREEXEC_COMPOSITION_FIXTURE_{index:02d}",
            evidence_sha256=f"{index:X}" * 64, key=key,
        )
        verified = preexec.verify_receipt(raw, expected_kind=kind, action=action, context=context, trusted_now_unix_s=1100.0, replay_store=store, key=key)
        body = strict.loads_strict(raw)["body"]
        ordered.append({
            "kind": kind, "sha256": sha(raw), "nonce": verified.nonce, "status": verified.status,
            "action_digest": verified.action_digest, "context_digest": verified.context_digest,
            "issued_at_unix_s": body["issued_at_unix_s"], "expires_at_unix_s": body["expires_at_unix_s"],
            "evidence_sha256": body["evidence_sha256"],
        })
    return {
        "kinds": list(kinds),
        "ordered": ordered,
        "digest": strict.canonical_digest(ordered),
        "common_window": [max(item["issued_at_unix_s"] for item in ordered), min(item["expires_at_unix_s"] for item in ordered)],
        "decision": {"executed_strategy": "ABORT", "allowed": False, "reason": "SOURCE_FREEZE_SCOPE_LOCK", "composite_authorization": False, "release_credit": False},
    }


def black_box_attacks() -> dict[str, Any]:
    script = r'''
import hashlib,hmac,json
from pathlib import Path
from crossbind.bridge import build_crossbind_record
from crossbind.package import find_repo_root
from crossbind.receipt import PRODUCTION_RECEIPT_KIND,V3ReplayStore,_actual_preexec_modules,make_synthetic_v3_fixture,validate_system_binding_v3
from crossbind.source_bundle import load_source_bundle
root=find_repo_root(Path.cwd()); record=build_crossbind_record(load_source_bundle(root)); f=make_synthetic_v3_fixture(record); _,strict=_actual_preexec_modules()
def kw(store=None,pre=None,now=None): return dict(preexec_receipt_bytes_by_kind=pre or f.preexec_receipt_bytes_by_kind,expected_action=f.action,expected_context=f.context,trusted_now_unix_s=f.trusted_now_unix_s if now is None else now,replay_store=store or V3ReplayStore(),preexec_key=f.preexec_key,v3_key=f.v3_key)
def reject(call,frag):
    try: call(); return False
    except Exception as e: return frag in str(e)
def resign(mut):
    o=strict.loads_strict(f.receipt_bytes); mut(o['body']); o['signature_hmac_sha256']=hmac.new(f.v3_key,strict.canonical_json_bytes(o['body']),hashlib.sha256).hexdigest().upper(); return strict.canonical_json_bytes(o)
out={}; s=V3ReplayStore(); v=validate_system_binding_v3(f.receipt_bytes,record,**kw(s)); out['success']=v['decision']['reason']=='SOURCE_FREEZE_SCOPE_LOCK' and not v['decision']['allowed'] and s.seen_count==1
out['replay']=reject(lambda:validate_system_binding_v3(f.receipt_bytes,record,**kw(s)),'V3_REPLAY_NONCE') and s.seen_count==1
bad=strict.loads_strict(f.receipt_bytes); bad['signature_hmac_sha256']='0'*64; badraw=strict.canonical_json_bytes(bad); fs=V3ReplayStore(); out['failure_no_consume']=reject(lambda:validate_system_binding_v3(badraw,record,**kw(fs)),'V3_SIGNATURE_INVALID') and fs.seen_count==0
out['dict_fake']=reject(lambda:validate_system_binding_v3({'receipt_kind':'AUTHENTICATED'},record,**kw()),'SERIALIZED_SIGNED_ENVELOPE_BYTES_REQUIRED')
out['old_v2']=reject(lambda:validate_system_binding_v3(f.preexec_receipt_bytes_by_kind['SYSTEM_BINDING_V2'],record,**kw()),'KEY_SET_MISMATCH')
out['production_kind']=reject(lambda:validate_system_binding_v3(resign(lambda b:b.update(receipt_kind=PRODUCTION_RECEIPT_KIND)),record,**kw()),'NOT_IMPLEMENTED_NO_PRODUCER')
out['action_rebind']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['action'].update(strategy_id='S3a')),record,**kw()),'V3_ACTION_REBIND')
out['context_rebind']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['context'].update(mission_phase_id='X')),record,**kw()),'V3_CONTEXT_REBIND')
out['order']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['preexec_receipts'].reverse()),record,**kw()),'PREEXEC_ORDERED_RECEIPT_SET_MISMATCH')
out['intake_terminal']=reject(lambda:validate_system_binding_v3(resign(lambda b:b.update(intake_terminal_sha256='0'*64)),record,**kw()),'HASH_BINDING_MISMATCH:intake_terminal_sha256')
out['preexec_terminal']=reject(lambda:validate_system_binding_v3(resign(lambda b:b.update(preexec_terminal_sha256='0'*64)),record,**kw()),'HASH_BINDING_MISMATCH:preexec_terminal_sha256')
out['expired_preexec_fresh_v3']=reject(lambda:validate_system_binding_v3(resign(lambda b:b.update(issued_at_unix_s=1350.0,expires_at_unix_s=1500.0)),record,**kw(now=1400.0)),'STALE_RECEIPT')
badpre=dict(f.preexec_receipt_bytes_by_kind); x=strict.loads_strict(badpre['DYNAMICS_GATE_V2']); x['signature_hmac_sha256']='0'*64; badpre['DYNAMICS_GATE_V2']=strict.canonical_json_bytes(x); out['bad_preexec_hmac']=reject(lambda:validate_system_binding_v3(f.receipt_bytes,record,**kw(pre=badpre)),'ATTESTATION_SIGNATURE_INVALID')
out['configuration']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['configuration_mapping'].update(v3_configuration_id='C09')),record,**kw()),'CONFIGURATION_MAPPING_MISMATCH')
out['episode_drop']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['context'].pop('episode_id')),record,**kw()),'KEY_SET_MISMATCH')
out['epoch_drop']=reject(lambda:validate_system_binding_v3(resign(lambda b:b['context'].pop('authority_epoch')),record,**kw()),'KEY_SET_MISMATCH')
sur=b'{"body":{"context":"\\ud800"},"signature_hmac_sha256":"'+b'0'*64+b'"}'; inf=b'{"body":{"issued_at_unix_s":1e999},"signature_hmac_sha256":"'+b'0'*64+b'"}'; dup=b'{"body":{},"body":{},"signature_hmac_sha256":"'+b'0'*64+b'"}'
out['strict']=reject(lambda:validate_system_binding_v3(sur,record,**kw()),'INVALID_UTF8_STRING') and reject(lambda:validate_system_binding_v3(inf,record,**kw()),'NON_FINITE_NUMBER') and reject(lambda:validate_system_binding_v3(dup,record,**kw()),'DUPLICATE_KEY')
print(json.dumps(out,sort_keys=True))
'''
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run([sys.executable, "-B", "-c", script], cwd=PACKAGE_ROOT, env=env, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise AuditError(f"BLACK_BOX_FAILED:{completed.stdout}:{completed.stderr}")
    return json.loads(completed.stdout)


def base_audit() -> dict[str, Any]:
    repo = find_repo()
    manifest_path = PACKAGE_ROOT / MANIFEST_REL
    manifest = parse_json(manifest_path.read_bytes())
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any) -> None:
        if not condition:
            raise AuditError(f"{check_id}:{detail}")
        checks.append({"id": check_id, "status": "PASS", "detail": detail})

    check("A01_MANIFEST_SCHEMA", manifest["schema"] == "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1", manifest["schema"])
    external = {item["id"]: item for item in manifest["external_sources"]}
    check("A02_EXTERNAL_ID_SET", set(external) == {item[0] for item in PINS}, len(external))
    parsed: dict[str, dict[str, Any]] = {}
    for index, (source_id, rel, expected_sha, kind, expected_schema) in enumerate(PINS, start=3):
        raw = (repo / rel).read_bytes()
        check(f"A{index:02d}_SOURCE_SHA_{source_id}", sha(raw) == expected_sha, expected_sha)
    for index, (source_id, rel, expected_sha, kind, expected_schema) in enumerate(PINS, start=18):
        raw = (repo / rel).read_bytes()
        check(f"A{index:02d}_SOURCE_RECEIPT_{source_id}", external[source_id] == {"id": source_id, "path": rel, "bytes": len(raw), "sha256": expected_sha}, rel)
        if kind == "json": parsed[source_id] = parse_json(raw)
        elif kind == "yaml": parsed[source_id] = parse_yaml(raw)
    check("A33_DOCUMENT_SCHEMAS", all(parsed[source_id].get("schema") == expected_schema for source_id, rel, expected_sha, kind, expected_schema in PINS if kind != "python"), "13/13")
    internal = {item["path"].removeprefix(PACKAGE_REL + "/"): item for item in manifest["internal_sources"]}
    check("A34_INTERNAL_SET", set(internal) == INTERNAL, len(internal))
    for index, rel in enumerate(sorted(INTERNAL), start=35):
        check(f"A{index:02d}_INTERNAL_{rel}", internal[rel] == receipt(PACKAGE_ROOT / rel, f"{PACKAGE_REL}/{rel}"), rel)
    check("A58_CONTRACT_SET", {item["path"].removeprefix(PACKAGE_REL + "/") for item in manifest["contracts"]} == {rel for rel in INTERNAL if rel.startswith("contracts/")}, 3)
    check("A59_SOURCE_READ_SCOPE", manifest["each_source_read_once_per_bundle_load"] is True and all(value == 1 for value in manifest["external_source_read_counts"].values()), "per-bundle")

    bridge = parsed["PHYSICAL_DYNAMICS_BRIDGE"]
    dyn = bridge["frame_semantics"]["T_S_A0_dynamics"]["transform_S_A0_rows_m"]
    physical = bridge["frame_semantics"]["T_S_A0_physical"]["transform_S_A0_rows_m"]
    stored = bridge["T_PHYSICAL_TO_DYNAMIC"]["homogeneous_4x4"]
    inverse = bridge["T_DYNAMIC_TO_PHYSICAL_inverse_bridge"]["homogeneous_4x4"]
    derived = mul(inverse_rigid(dyn), physical)
    residual = max_abs(derived, stored)
    check("A60_BRIDGE_EXACT", derived == stored and residual == 0.0, residual)
    check("A61_INVERSE_DISTINCT", max_abs(derived, inverse) > 0.01, max_abs(derived, inverse))
    _, strict = load_preexec_modules(repo)
    bridge_semantics = {"schema": "MPI_PHYSICAL_TO_DYNAMICS_BRIDGE_SEMANTICS_V1", "id": "T_PHYSICAL_TO_DYNAMIC", "direction": "PHYSICAL_TO_DYNAMICS", "matrix_semantics": "ROW_MAJOR__p_parent=T_parent_child@p_child", "from_frame": "A0_PHYSICAL_WP11", "to_frame": "A0_DYNAMICS_ODR01", "reference_point": "B601_A0_ORIGIN", "homogeneous_4x4": stored, "source_sha256": PINS[1][2]}
    bridge_digest = strict.canonical_digest(bridge_semantics)
    check("A62_BRIDGE_SEMANTIC_DIGEST", manifest["immutable_crossbind_record"]["bridge_semantic_digest"] == bridge_digest and manifest["immutable_crossbind_record"]["crossbind_record_digest"] != bridge_digest, bridge_digest)
    owner = parsed["OWNER_ODR45"]
    odr45 = next(item for item in owner["decisions"] if item["id"] == "ODR-45")
    check("A63_OWNER_CONFIRMATION", odr45["structured_decomposition"]["bridge_status_upgrade"]["to"] == "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE" and owner["release_credit"] is False, "confirmed/no-release")
    mass = parsed["BRIDGED_MASS_INERTIA"]
    check("A64_MASS_LEDGER", mass["overall"] == "PASS" and mass["criterion_counts"] == {"total": 8, "pass": 8, "fail": 0}, "8/8")
    check("A65_INTAKE_GATE_TERMINAL", parsed["INTAKE_GATE"]["current_intake_status"] == "HOLD_INCOMPLETE" and parsed["INTAKE_TERMINAL"]["gate"]["sha256"] == PINS[9][2], "HOLD_INCOMPLETE")
    check("A66_PREEXEC_GATE_TERMINAL", parsed["PREEXEC_GATE"]["parent_formal_nc"] == {"passed": 15, "promoted": 0, "total": 20} and parsed["PREEXEC_TERMINAL"]["remaining_holds"] == ["NC18", "NC19"] and parsed["PREEXEC_TERMINAL"]["gate"]["sha256"] == PINS[11][2], "15/20+NC18/19")

    pytest_doc = parse_json((PACKAGE_ROOT / "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1.json").read_bytes())
    negative_doc = parse_json((PACKAGE_ROOT / "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1.json").read_bytes())
    validation_doc = parse_json((PACKAGE_ROOT / "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1.json").read_bytes())
    manifest_receipt = receipt(manifest_path, f"{PACKAGE_REL}/{MANIFEST_REL}")
    check("A67_PYTEST", pytest_doc["passed"] == 28 and pytest_doc["failed"] == 0, 28)
    check("A68_NEGATIVE", negative_doc["passed"] == negative_doc["total"] == 67 and negative_doc["manifest"] == manifest_receipt, 67)
    check("A69_VALIDATION", validation_doc["passed"] == validation_doc["total"] == 38 and validation_doc["manifest"] == manifest_receipt, 38)
    composition = independent_composition(repo)
    detail29 = next(item["detail"] for item in validation_doc["checks"] if item["id"] == "V29_SEVEN_PREEXEC_RAW_RECEIPTS")
    check("A70_COMPOSITION_ORDER", [item["kind"] for item in composition["ordered"]] == composition["kinds"] and detail29["verified"] == 7, composition["kinds"])
    check("A71_COMPOSITION_DIGEST", detail29["ordered_set_digest"] == composition["digest"], composition["digest"])
    check("A72_COMPOSITION_DECISION", detail29["decision"] == composition["decision"], composition["decision"])
    check("A73_COMPOSITION_TIME", composition["common_window"] == [1000.0, 1300.0] and composition["common_window"][1] - composition["common_window"][0] <= 300.0, composition["common_window"])
    black = black_box_attacks()
    check("A74_BLACKBOX_SUCCESS", black["success"], black)
    check("A75_BLACKBOX_REPLAY_AND_FAILURE_COMMIT", black["replay"] and black["failure_no_consume"], black)
    check("A76_BLACKBOX_NO_FAKE_AUTHORITY", black["dict_fake"] and black["old_v2"] and black["production_kind"], black)
    check("A77_BLACKBOX_HMAC_ACTION_CONTEXT_ORDER", black["bad_preexec_hmac"] and black["action_rebind"] and black["context_rebind"] and black["order"], black)
    check("A78_BLACKBOX_TERMINAL_AND_TIME", black["intake_terminal"] and black["preexec_terminal"] and black["expired_preexec_fresh_v3"], black)
    check("A79_BLACKBOX_STRICT_AND_CONTEXT_IDENTITY", black["strict"] and black["configuration"] and black["episode_drop"] and black["epoch_drop"], black)
    if len(checks) != 79:
        raise AuditError(f"PRE_GATE_AUDIT_COUNT_DRIFT:{len(checks)}")
    return {
        "schema": "MPI_BRIDGE_TO_SIM13_CROSSBIND_INDEPENDENT_AUDIT_V1",
        "auditor_independence": "NO_CROSSBIND_EVALUATOR_IMPORT__INDEPENDENT_SOURCE_AND_COMPOSITION_RECOMPUTE__SEPARATE_PROCESS_PUBLIC_API_ATTACKS",
        "manifest": manifest_receipt,
        "bridge_recomputation": {"formula": "inv(T_S_A0_dynamics) @ T_S_A0_physical", "direction": "PHYSICAL_TO_DYNAMICS", "exact_elementwise": True, "max_abs_residual": residual},
        "bridge_semantic_digest": bridge_digest,
        "composition_recomputation": {"preexec_receipts": 7, "ordered_receipt_set_digest": composition["digest"], "decision": composition["decision"], "common_window_unix_s": composition["common_window"]},
        "checks": checks,
        "passed": 79,
        "total": 79,
        "failed": 0,
        "audit_phase": "PRE_GATE_EVIDENCE_ROOTS_COMPLETE",
        "release_credit": False,
    }


def write_atomic(path: Path, value: dict[str, Any]) -> None:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def full_check() -> dict[str, Any]:
    fresh = base_audit()
    frozen = parse_json((PACKAGE_ROOT / AUDIT_REL).read_bytes())
    if frozen != fresh:
        raise AuditError("FROZEN_INDEPENDENT_AUDIT_DRIFT")
    gate = parse_json((PACKAGE_ROOT / GATE_REL).read_bytes())
    terminal = parse_json((PACKAGE_ROOT / TERMINAL_REL).read_bytes())
    checks = list(fresh["checks"])

    def check(check_id: str, condition: bool, detail: Any) -> None:
        if not condition:
            raise AuditError(f"{check_id}:{detail}")
        checks.append({"id": check_id, "status": "PASS", "detail": detail})

    check("A80_GATE_STATUS_AND_DIGESTS", gate["status"] == "PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY" and gate["bridge_semantic_digest"] == fresh["bridge_semantic_digest"] and gate["crossbind_record_digest"] != gate["bridge_semantic_digest"], gate["status"])
    evidence_map = {"pytest": "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1.json", "negative_controls": "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1.json", "validation": "evidence/MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1.json", "independent_audit": AUDIT_REL, "source_manifest": MANIFEST_REL}
    check("A81_GATE_EVIDENCE", all(gate["evidence"][key] == receipt(PACKAGE_ROOT / rel, f"{PACKAGE_REL}/{rel}") for key, rel in evidence_map.items()), "5/5")
    check("A82_FLAGS_PARENT_HOLDS", not any(gate["flags"].values()) and gate["formal_parent_nc"] == {"passed": 15, "total": 20, "promoted": 0} and gate["remaining_holds"] == ["NC18", "NC19"] and gate["system_binding_v3"]["production_authenticated_receipt_present"] is False and gate["review_finding_disposition"] == {"p0_open": 0, "p1_open": 0, "p2_open": 0, "first_round_findings_closed": True}, "false+15/20+NC18/19+P0/P1/P2=0")
    gate_receipt = receipt(PACKAGE_ROOT / GATE_REL, f"{PACKAGE_REL}/{GATE_REL}")
    check("A83_TERMINAL_BINDS_GATE_AND_DIGESTS", terminal["gate"] == gate_receipt and terminal["bridge_semantic_digest"] == gate["bridge_semantic_digest"] and terminal["crossbind_record_digest"] == gate["crossbind_record_digest"] and terminal["review_finding_disposition"] == gate["review_finding_disposition"] and terminal["release_credit"] is False, gate_receipt["sha256"])
    files = {item.relative_to(PACKAGE_ROOT).as_posix() for item in PACKAGE_ROOT.rglob("*") if item.is_file()}
    dirs = {item.relative_to(PACKAGE_ROOT).as_posix() for item in PACKAGE_ROOT.rglob("*") if item.is_dir()}
    check("A84_EXACT_ALLOWLIST", files == ALLOWED_FILES and dirs == ALLOWED_DIRS, {"files": len(files), "directories": len(dirs), "extra_files": sorted(files-ALLOWED_FILES), "extra_dirs": sorted(dirs-ALLOWED_DIRS)})
    if len(checks) != 84:
        raise AuditError(f"FULL_AUDIT_COUNT_DRIFT:{len(checks)}")
    return {"status": "PASS", "passed": 84, "total": 84, "failed": 0, "checks": checks, "gate_sha256": gate_receipt["sha256"], "terminal_sha256": sha((PACKAGE_ROOT / TERMINAL_REL).read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit", action="store_true")
    args = parser.parse_args()
    if args.emit:
        report = base_audit()
        write_atomic(PACKAGE_ROOT / AUDIT_REL, report)
    else:
        report = full_check()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
