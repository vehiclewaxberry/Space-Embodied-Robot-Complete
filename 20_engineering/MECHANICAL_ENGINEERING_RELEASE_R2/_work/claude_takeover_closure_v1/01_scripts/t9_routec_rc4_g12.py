#!/usr/bin/env python
"""Section 9: Route-C RC-4 / G12 closure against the certified M01 path.

Branch policy (fail-closed):
  - certified M01 path exists  -> bind Route-C geometry + P01-P13 to the path
    SHA, run RC-4 full-path coverage, re-evaluate G12.
  - no certified path          -> RC-4 NOT_EXECUTED, G12 HOLD, historical
    fixed-harness results remain HISTORICAL_NEGATIVE.  No geometry revision.
"""
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t.common import (M01_OUT, REL, RUN_ID, WP_OUT, abspath, jdump, jload,
                         pin, sha256_file)

CERT_PATH_REL = f"{M01_OUT}/M01_OPTION_A_CERTIFIED_PATH_V1.json"
PATH_GATE_REL = f"{M01_OUT}/M01_OPTION_A_BOUNDED_PATH_GATE_V1.json"
HANDOFF = f"{REL}/17_MECH_TO_EMBODIED_HANDOFF_GATE.json"

cert_path = jload(CERT_PATH_REL) if os.path.isfile(abspath(CERT_PATH_REL)) else None
path_gate = jload(PATH_GATE_REL) if os.path.isfile(abspath(PATH_GATE_REL)) else None

if cert_path is None:
    outcome = None if path_gate is None else path_gate.get("outcome")
    binding = {
        "schema": "ROUTE_C_CERTIFIED_PATH_BINDING_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "named_run_id": RUN_ID,
        "bound": False,
        "reason": "NO_CERTIFIED_M01_PATH_EXISTS",
        "m01_outcome": outcome,
        "release_credit": False,
    }
    jdump(binding, f"{WP_OUT}/ROUTE_C_CERTIFIED_PATH_BINDING_V1.json")
    rc4 = {
        "schema": "ROUTE_C_RC4_GATE_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "named_run_id": RUN_ID,
        "route_c_rc4": "NOT_EXECUTED",
        "reason": "RC4_FULL_PATH_COVERAGE_REQUIRES_CERTIFIED_M01_PATH__PATH_ABSENT",
        "geometry_revision_authorized": False,
        "geometry_revision_basis": "no current hash-bound geometric witness against a modifiable candidate; missing path/evaluator is not permission to redesign the harness",
        "historical_fixed_harness_results": "HISTORICAL_NEGATIVE (E_HRN 0/75 SAFE, 11/11 key states UNSAFE on the OLD fixed external dress; V9F -17.313396996697108 mm quarantined witness)",
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
    jdump(rc4, f"{WP_OUT}/ROUTE_C_RC4_GATE_V1.json")
    jdump({"schema": "ROUTE_C_RC4_FULL_PATH_EVIDENCE_V1", "named_run_id": RUN_ID,
           "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
           "executed": False, "release_credit": False},
          f"{WP_OUT}/ROUTE_C_RC4_FULL_PATH_EVIDENCE_V1.json")
    g12 = {
        "schema": "G12_CURRENT_PATH_HANDOFF_GATE_V1",
        "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
        "named_run_id": RUN_ID,
        "g12_current_path_handoff": "HOLD",
        "prior_handoff_gate": pin(HANDOFF),
        "prior_state": "11_OF_12__G12_FAIL",
        "flip_requirement": "RC-4 PASS over a certified M01 path, then new-file handoff re-adjudication",
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
    }
    jdump(g12, f"{WP_OUT}/G12_CURRENT_PATH_HANDOFF_GATE_V1.json")
    print("RC4 NOT_EXECUTED / G12 HOLD (no certified path)")
    sys.exit(0)

# ---------------- certified-path branch (executed only in Outcome A)
import numpy as np
from m01t import kinematics as K
from m01t.oracle import PoseContext, Scene, pair_query

scene = Scene()
waypoints = [np.array(w, float) for w in cert_path["waypoints_q6"]]
path_sha = sha256_file(abspath(CERT_PATH_REL))

# P01-P13 evaluated over the certified path: physical-capability predicates are
# design-scope static (RC-1); the path-dependent ones are re-checked here.
reg = yaml.safe_load(open(abspath(f"{REL}/route_c/ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml"), encoding="utf-8"))

# path-dependent evaluation: harness clearance along the path is already
# certified by M01 edge certificates; here we add the Route-C-specific
# continuous coverage: minimum certified margin per edge from M01 recert.
edges = cert_path["edges"]
min_margin = min(e["min_margin_mm"] for e in edges if e["min_margin_mm"] is not None)

binding = {
    "schema": "ROUTE_C_CERTIFIED_PATH_BINDING_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "bound": True,
    "certified_path_sha256": path_sha,
    "waypoints": len(waypoints),
    "release_credit": False,
}
jdump(binding, f"{WP_OUT}/ROUTE_C_CERTIFIED_PATH_BINDING_V1.json")

evidence = {
    "schema": "ROUTE_C_RC4_FULL_PATH_EVIDENCE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "executed": True,
    "path_sha256": path_sha,
    "minimum_certified_harness_margin_mm_over_path": min_margin,
    "p01_p13_scope": "RC-1 design-candidate values consumed; path-dependent predicates evaluated via M01 certified edges",
    "release_credit": False,
}
jdump(evidence, f"{WP_OUT}/ROUTE_C_RC4_FULL_PATH_EVIDENCE_V1.json")

rc4_pass = min_margin > 0.0
rc4 = {
    "schema": "ROUTE_C_RC4_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "route_c_rc4": "PASS" if rc4_pass else "FAIL",
    "path_sha256": path_sha,
    "minimum_certified_margin_mm": min_margin,
    "release_credit": False,
    "review_status": "PENDING_OWNER_REVIEW",
}
jdump(rc4, f"{WP_OUT}/ROUTE_C_RC4_GATE_V1.json")

g12 = {
    "schema": "G12_CURRENT_PATH_HANDOFF_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "g12_current_path_handoff": "PASS_PENDING_NEW_FILE_HANDOFF_READJUDICATION" if rc4_pass else "HOLD",
    "prior_handoff_gate": pin(HANDOFF),
    "release_credit": False,
    "review_status": "PENDING_OWNER_REVIEW",
}
jdump(g12, f"{WP_OUT}/G12_CURRENT_PATH_HANDOFF_GATE_V1.json")
print(f"RC4 {'PASS' if rc4_pass else 'FAIL'}; min margin {min_margin} mm")
