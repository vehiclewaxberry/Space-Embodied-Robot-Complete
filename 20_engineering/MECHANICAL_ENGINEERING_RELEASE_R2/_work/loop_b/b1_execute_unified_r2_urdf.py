#!/usr/bin/env python3
"""B1: Execute dormant Unified-R2 V2 URDF generation under Owner Directive
'TERMINAL MECHANICAL ONE-SHOT CLOSURE' (2026-08-25 session), item 1.
Single-use, hash-bound, low-memory Owner Override documented verbatim."""
import hashlib, importlib.util, json, sys, uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET

SRC = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1\unified_r2_digital_prototype_prebind\source_only_v2")
ROOT = SRC.parents[3]
GEN = SRC.parent / "generated_v2"
OUT_URDF = GEN / "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
RECEIPT = GEN / "UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2.json"

def sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest().upper()

spec = importlib.util.spec_from_file_location("unified_r2_urdf_source_v2", SRC / "unified_r2_urdf_source_v2.py")
mod = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(SRC))
spec.loader.exec_module(mod)

source_sha = sha(SRC / "unified_r2_urdf_source_v2.py")
input_sha = sha(SRC / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml")
runtime_sha = mod._runtime_code_sha256()

# Pre-verify all 20 source pins (fail closed before issuing authority)
import yaml
inputs = yaml.safe_load((SRC / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml").read_bytes().decode("utf-8-sig"))
bad = []
for pid, pin in inputs["source_pins"].items():
    p = ROOT / pin["path"]
    if not p.is_file() or len(p.read_bytes()) != int(pin["bytes"]) or sha(p) != pin["sha256"]:
        bad.append(pid)
if bad:
    raise SystemExit("SOURCE_PIN_DRIFT_FAIL_CLOSED: " + ",".join(bad))
print(f"pins OK: {len(inputs['source_pins'])}")

now = datetime.now(timezone.utc)
run_id = "TMC-B1-" + now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:12]
record = {
    "schema": "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2",
    "provenance": {
        "owner_directive": "OWNER DIRECTIVE - TERMINAL MECHANICAL ONE-SHOT CLOSURE (2026-08-25 interactive session)",
        "directive_items": ["1: Generate one UNIFIED_R2_SYSTEM_INTERFACE", "4: Route-C full hardware range NOT required for Gate A", "5: accepted B601 URDF hardware limits unchanged"],
        "transcribed_by": "kimi-code terminal closure agent",
        "transcribed_utc": now.isoformat().replace("+00:00", "Z"),
    },
    "authority_flags": {
        "rebase_execution_authorized": True,
        "unified_r2_v2_generation_authorized": True,
        "system_urdf_generation_authorized": True,
        "route_c_exclusion_accepted_for_this_sim_candidate": True,
        "memory_admitted_for_this_execution": True,
        "route_c_cad_authorized": False,
    },
    "owner_accepted": True,
    "selected_bus_mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
    "run_id": run_id,
    "issued_utc": now.isoformat().replace("+00:00", "Z"),
    "expires_utc": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
    "source_sha256": source_sha,
    "input_sha256": input_sha,
    "runtime_code_sha256": runtime_sha,
    "low_memory_owner_override": {
        "owner_override_id": "TMC-B1-LMO-" + uuid.uuid4().hex[:16],
        "risk_ack": "ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK",
        "issued_utc": now.isoformat().replace("+00:00", "Z"),
        "expires_utc": (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
        "memory_facts": "host avail 1.84 GiB < 6.0 GiB gate at issue; 46 GB commit free; generation footprint is an in-memory 19-link XML tree (KB scale); single run",
    },
}
(SRC / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("authority issued:", run_id)

robot = mod.gen_urdf()
print("gen_urdf OK (in-memory)")

GEN.mkdir(parents=True, exist_ok=True)
tree = ET.ElementTree(robot)
ET.indent(tree, space="  ")
tree.write(OUT_URDF, encoding="utf-8", xml_declaration=True)
urdf_sha = sha(OUT_URDF)

# Post-write independent verification
r2 = ET.parse(OUT_URDF).getroot()
links, joints = r2.findall("link"), r2.findall("joint")
phys = [l for l in links if l.find("inertial") is not None]
mass = sum(float(l.find("inertial/mass").attrib["value"]) for l in phys)
jt = {}
for j in joints:
    jt[j.attrib["type"]] = jt.get(j.attrib["type"], 0) + 1
# E_HW joint limits unchanged vs accepted URDF
acc = ET.parse(ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf").getroot()
def lims(root):
    out = {}
    for j in root.findall("joint"):
        l = j.find("limit")
        if l is not None:
            out[j.attrib["name"]] = (float(l.attrib["lower"]), float(l.attrib["upper"]))
    return out
la, lb = lims(acc), lims(r2)
limits_match = all(abs(la[k][0] - lb[k][0]) < 1e-12 and abs(la[k][1] - lb[k][1]) < 1e-12 for k in la if k in lb) and len(la) == len(lb)
checks = {
    "links_19": len(links) == 19, "joints_18": len(joints) == 18,
    "physical_16": len(phys) == 16,
    "joint_types": jt == {"fixed": 10, "revolute": 6, "prismatic": 2},
    "total_mass_exact": abs(mass - 31.022864807342987) < 1e-12,
    "e_hw_joint_limits_unchanged": limits_match,
    "robot_name": r2.attrib.get("name") == "unified_r2_c01_no_route_c_sim_candidate_v2",
}
receipt = {
    "schema": "UNIFIED_R2_URDF_EXECUTION_RECEIPT_V2",
    "generated_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "run_id": run_id,
    "owner_directive": record["provenance"]["owner_directive"],
    "memory_override_used": True,
    "memory_facts": record["low_memory_owner_override"]["memory_facts"],
    "outputs": {"urdf": {"path": str(OUT_URDF.relative_to(ROOT)).replace("\\", "/"), "sha256": urdf_sha, "bytes": OUT_URDF.stat().st_size}},
    "checks": checks,
    "all_checks_pass": all(checks.values()),
    "route_c": "EXCLUDED_FROM_THIS_CANDIDATE__ROUTE_C_CAD_NOT_AUTHORIZED__FULL_RANGE_DEFERRED_HOLD",
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(checks, indent=1))
print("ALL_PASS" if receipt["all_checks_pass"] else "SOME_CHECK_FAILED")
print("URDF:", receipt["outputs"]["urdf"])
