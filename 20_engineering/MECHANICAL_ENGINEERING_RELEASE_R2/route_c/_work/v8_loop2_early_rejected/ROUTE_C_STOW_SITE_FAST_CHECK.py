# ROUTE_C_STOW_SITE_FAST_CHECK.py
# ============================================================================
# Rapid 10-mandatory-key-state clearance check for the current Route-C variant
# mesh pack (single-pose FK per key state, minute-level runtime).
#
# Method: drives ROUTE_C_EXACT_SWEEP_V1.main() verbatim (same loaders, same FK,
# same distance kernels incl. the d5/d6 and frame-correct broad-phase fixes)
# with a DEGENERATE key-state-only mission contract (one from==to segment per
# key pose), then adds a targeted RC-GDE-J6-RING-* vs link5 pair measurement
# at the STOW pose.
#
# SCOPE BANNER: this output is a CLEARANCE-ONLY design-iteration instrument.
# take_up / pinch / carrier_travel / resistance_torque / verdict values inside
# the scratch sweep JSON are NOT VALID (degenerate contract gives wrong joint
# ranges). The authoritative numbers come from the full final sweep.
# ============================================================================
import os
import sys
import json
import math
import importlib.util

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
VARIANT = os.environ.get("RC_VARIANT", "V7").upper()
os.environ["RC_VARIANT"] = VARIANT
os.environ["RC_FAST"] = "1"
SCRATCH = os.path.join(HERE, "_fastcheck_scratch")
os.makedirs(SCRATCH, exist_ok=True)
OUT_JSON = os.path.join(HERE, "ROUTE_C_STOW_SITE_FAST_CHECK_%s.json" % VARIANT)

STOW_RAW_CRITERION_MM = 9.5   # master criterion: J6 ring vs link5 raw at STOW
V3_GATED_BASELINE_MM = 4.9    # V3 key-state gated baseline (regression flag)

# ---- import the sweep module (reads RC_VARIANT / RC_FAST at module level) ---
spec = importlib.util.spec_from_file_location(
    "rc_sweep", os.path.join(HERE, "ROUTE_C_EXACT_SWEEP_V1.py"))
SW = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SW)

# ---- build degenerate key-state-only contract -------------------------------
contract = yaml.safe_load(open(SW.P_CONTRACT, encoding="utf-8"))
states = contract["states"]
KEY_POSES = ["STOW", "RELEASE_CLEAR", "HOME", "TASK_READY", "PREGRASP"]
missing = [p for p in KEY_POSES if p not in states]
if missing:
    raise SystemExit("ABORT: contract missing key poses %s" % missing)
red = dict(contract)
red["segments"] = [
    {"id": "KEYONLY_%s" % p, "from": p, "to": p,
     "purpose": "key-state fast check degenerate single-pose segment"}
    for p in KEY_POSES]
red_path = os.path.join(SCRATCH, "contract_keystates_only.yaml")
with open(red_path, "w", encoding="utf-8", newline="\n") as f:
    yaml.safe_dump(red, f)

SW.P_CONTRACT = red_path
SW.OUT_SWEEP = os.path.join(SCRATCH, "sweep_scratch.json")
SW.OUT_LEDGER = os.path.join(SCRATCH, "ledger_scratch.csv")
SW.OUT_GATE = os.path.join(SCRATCH, "gate_scratch.json")

print("[fastcheck] driving sweep main() with degenerate key-state contract ...", flush=True)
SW.main()

sweep = json.load(open(SW.OUT_SWEEP, encoding="utf-8"))
key_states = sweep["key_states"]

# ---- targeted pair: RC-GDE-J6-RING-* (link6) vs link5 vendor at STOW --------
mount = yaml.safe_load(open(SW.P_MOUNT, encoding="utf-8"))
arm = SW.ArmModel(SW.P_URDF, mount["mount"]["transform_mm_rows"])
q_stow = [float(x) for x in states["STOW"]["q_rad"]]
T = arm.fk(list(q_stow))
T0 = arm.fk([0.0] * 6)
inv_T0_6 = np.linalg.inv(T0["link6"])
inv_TS_5 = np.linalg.inv(arm.mount @ T["link5"])
M_ring_to_S = arm.mount @ T["link6"] @ inv_T0_6

link5_fld = SW.TriField(
    "link5", np.load(os.path.join(SW.P_PACK, "vendor_link5_tris.npy"),
                     allow_pickle=False))
ring_names = ["RC-GDE-J6-RING-0", "RC-GDE-J6-RING-1",
              "RC-GDE-J6-RING-2", "RC-GDE-J6-RING-3"]
ring_files = {"RC-GDE-J6-RING-0": "rc_RC_GDE_J6_RING_0_tris.npy",
              "RC-GDE-J6-RING-1": "rc_RC_GDE_J6_RING_1_tris.npy",
              "RC-GDE-J6-RING-2": "rc_RC_GDE_J6_RING_2_tris.npy",
              "RC-GDE-J6-RING-3": "rc_RC_GDE_J6_RING_3_tris.npy"}
ring_pair = []
for rn in ring_names:
    fld = SW.TriField(rn, np.load(os.path.join(SW.P_PACK, ring_files[rn]),
                                  allow_pickle=False))
    P_S = SW.xform_batch(M_ring_to_S, fld.v0)
    Pl = SW.xform_batch(inv_TS_5, P_S)
    d, exact = link5_fld.min_dist_batch(Pl)
    c = link5_fld.signed_clearance_batch(Pl, SW.RC_SAMPLE_ALLOW)
    rec = {"ring": rn,
           "verts": int(len(Pl)),
           "raw_vertex_dist_min_mm": (float(d[exact].min()) if exact.any()
                                      else "BEYOND_HORIZON(>%.1f)" % link5_fld.D),
           "signed_minus_sample_allow_min_mm": (float(np.nanmin(c))
                                                if np.isfinite(c).any() else None)}
    ring_pair.append(rec)
ring_worst = min(r["signed_minus_sample_allow_min_mm"]
                 for r in ring_pair if r["signed_minus_sample_allow_min_mm"] is not None)

# ---- decision summary ---------------------------------------------------------
stow_ks = next(k for k in key_states if k["state_id"] == "ARM_STOWED_ONORBIT_C05")
others = [k for k in key_states if k["state_id"] != "ARM_STOWED_ONORBIT_C05"]
others_worst_gated = min(k["clearance_mm_gated"] for k in others)
n_unsafe = sum(1 for k in key_states if not k["pass"])
regressions = [k["state_id"] for k in others
               if k["clearance_mm_gated"] < V3_GATED_BASELINE_MM]
stow_ok = (ring_worst >= STOW_RAW_CRITERION_MM) and stow_ks["pass"]
clamp_support_ok = sweep["predicates"].get("clamp_and_guide_support_bore_axis", {}).get("pass", False)
d3_retention_ok = sweep["predicates"].get("d3_open_sector_retention", {}).get("pass", False)
recommendation = ("PROCEED_TO_FINAL_SWEEP" if (stow_ok and n_unsafe == 0 and not regressions
                                                and clamp_support_ok and d3_retention_ok)
                  else "V8_TARGETED_FIX_OR_FAIL_DOCUMENTED")

report = {
    "schema": "ROUTE_C_STOW_SITE_FAST_CHECK_%s" % VARIANT,
    "stage": "RC-4_KEY_STATE_FAST_CHECK",
    "scope_banner": ("CLEARANCE-ONLY design-iteration instrument. take_up / pinch / "
                     "carrier_travel / resistance_torque / verdict inside the scratch "
                     "sweep JSON are NOT VALID (degenerate single-pose contract)."),
    "variant": VARIANT,
    "criteria": {
        "stow_j6_ring_vs_link5_raw_min_mm": STOW_RAW_CRITERION_MM,
        "all_key_states_gated_ge_0": True,
        "regression_baseline_v3_gated_mm": V3_GATED_BASELINE_MM,
    },
    "key_states": key_states,
    "stow_targeted_pair_j6_rings_vs_link5": {
        "pose": "STOW", "q_rad": q_stow,
        "sample_allowance_mm": SW.RC_SAMPLE_ALLOW,
        "per_ring": ring_pair,
        "worst_signed_minus_allow_mm": ring_worst,
        "criterion_met": bool(ring_worst >= STOW_RAW_CRITERION_MM),
    },
    "summary": {
        "stow_key_state_gated_mm": stow_ks["clearance_mm_gated"],
        "stow_key_state_raw_mm": stow_ks["clearance_mm_raw"],
        "stow_key_state_detail": stow_ks["detail"],
        "other_key_states_worst_gated_mm": others_worst_gated,
        "key_states_unsafe_count": n_unsafe,
        "clamp_and_guide_support_bore_axis_pass": clamp_support_ok,
        "d3_open_sector_retention_pass": d3_retention_ok,
        "regression_flags_vs_v3_baseline": regressions,
        "recommendation": recommendation,
    },
    "authority_rules": {"allowed": ["DESIGN_CANDIDATE", "PROVISIONAL_DERIVED",
                                    "BOUNDED_DATASHEET_RANGE"],
                        "forbidden": ["MEASURED", "AS_BUILT", "FLIGHT_QUALIFIED"]},
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
    f.write(SW.jdump(report))

print("[fastcheck] STOW gated %.3f raw %.3f | ring-vs-link5 worst %.3f (crit %.1f) | "
      "others worst gated %.3f | unsafe %d | regressions %s"
      % (stow_ks["clearance_mm_gated"], stow_ks["clearance_mm_raw"], ring_worst,
         STOW_RAW_CRITERION_MM, others_worst_gated, n_unsafe, regressions), flush=True)
print("[fastcheck] recommendation: %s" % recommendation, flush=True)
print("[fastcheck] wrote %s" % OUT_JSON, flush=True)
