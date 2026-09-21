"""Freeze the six-panel solar array as V5_MULTI_PANEL_SOLAR_ARRAY_FROZEN.

Authority basis, all read from disk:
  - 13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json
    verdict V5_SOLAR_ARRAY_COMPLETION_PASS, 42 cold pose rows all within tolerance
  - 02_native_subassemblies/L_SOLAR_ARRAY.SLDASM and R_SOLAR_ARRAY.SLDASM

The freeze forbids reverting to a single-panel array. It does NOT upgrade the
candidate placeholder status, does not ratify panel angles, and does not touch
the L0 mass truth - the receipt's own non_claims are carried through verbatim.
"""

import datetime
import hashlib
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = ROOT.replace("\\", "/")
RECEIPT = "13_validation/V5_SOLAR_ARRAY_COMPLETION_RECEIPT_20260811T113120.766168Z.json"


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


with open(os.path.join(ROOT, RECEIPT), encoding="utf-8") as fh:
    receipt = json.load(fh)

if receipt["verdict"] != "V5_SOLAR_ARRAY_COMPLETION_PASS":
    raise SystemExit("refusing to freeze: completion receipt verdict is " + receipt["verdict"])

cold_rows = []
for side in receipt["cold_reverification"]:
    cold_rows.extend(side["cold_pose_rows"])
if len(cold_rows) != 42:
    raise SystemExit("refusing to freeze: expected 42 cold pose rows, found %d" % len(cold_rows))
out_of_tol = [row for row in cold_rows if not row["cold_within_tolerance"]]
if out_of_tol:
    raise SystemExit("refusing to freeze: %d cold pose rows out of tolerance" % len(out_of_tol))

panel_names = [panel["name"] for panel in receipt["panels"]]
expected = ["SOLAR_PANEL_L1", "SOLAR_PANEL_L2", "SOLAR_PANEL_L3",
            "SOLAR_PANEL_R1", "SOLAR_PANEL_R2", "SOLAR_PANEL_R3"]
if panel_names != expected:
    raise SystemExit("refusing to freeze: panel set is %s" % panel_names)

panels = []
for panel in receipt["panels"]:
    rel = "01_native_parts/solar_array/%s.SLDPRT" % panel["name"]
    path = os.path.join(ROOT, rel)
    live = sha(path) if os.path.exists(path) else None
    panels.append({
        "name": panel["name"],
        "side": panel["name"][-2],
        "index": int(panel["name"][-1]),
        "path": R + "/" + rel,
        "receipt_post_sha256": panel["post_sha256"],
        "live_sha256": live,
        "live_matches_receipt": live == panel["post_sha256"],
    })

assemblies = []
for side, name in (("LEFT", "L_SOLAR_ARRAY.SLDASM"), ("RIGHT", "R_SOLAR_ARRAY.SLDASM")):
    rel = "02_native_subassemblies/" + name
    path = os.path.join(ROOT, rel)
    receipt_sha = next(
        row["target"]["sha256"] for row in receipt["cold_reverification"] if row["side"] == side[0]
    )
    live = sha(path) if os.path.exists(path) else None
    assemblies.append({
        "side": side,
        "path": R + "/" + rel,
        "receipt_sha256": receipt_sha,
        "live_sha256": live,
        "live_matches_receipt": live == receipt_sha,
    })

drift = [row for row in panels + assemblies if not row["live_matches_receipt"]]

freeze = {
    "schema": "F3R2_V5_MULTI_PANEL_SOLAR_ARRAY_FREEZE_V1",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "tag": "V5_MULTI_PANEL_SOLAR_ARRAY_FROZEN",
    "configuration": {"LEFT": ["L1", "L2", "L3"], "RIGHT": ["R1", "R2", "R3"], "panel_count": 6},
    "authority": {
        "completion_receipt": R + "/" + RECEIPT,
        "completion_receipt_sha256": sha(os.path.join(ROOT, RECEIPT)),
        "verdict": receipt["verdict"],
        "cold_pose_rows": len(cold_rows),
        "cold_pose_rows_within_tolerance": len(cold_rows) - len(out_of_tol),
        "pose_tolerance_m": receipt.get("pose_tolerance_m"),
    },
    "panels": panels,
    "side_assemblies": assemblies,
    "live_hash_drift": drift,
    "prohibition": "REVERTING_TO_SINGLE_PANEL_SOLAR_ARRAY_IS_PROHIBITED",
    "freeze_does_not_grant": [
        "PLACEHOLDER_TO_QUALIFIED_PANEL_UPGRADE",
        "PANEL_ANGLE_RATIFICATION",
        "DEPLOYER_MECHANISM_QUALIFICATION",
        "SOLAR_CELL_DETAIL",
        "L0_MASS_OVERRIDE",
    ],
    "carried_non_claims": receipt["non_claims"],
    "still_pending_loop2": ["collision_state", "camera_visibility", "arm_clearance_mm"],
    "known_state_register_issue": {
        "statement": (
            "SOLAR_LEFT_FAIL and SOLAR_RIGHT_FAIL are encoded identically on BOTH side assemblies "
            "(config_pose_map ignores the side parameter), so single-side failure is not "
            "differentiated in the as-built geometry"
        ),
        "authoritative_intent": receipt["fail_config_registration"]["authoritative_mapping"],
        "status": "CANDIDATE_INTERMEDIATE_ANGLE_ENCODING_NOT_AUTHORITATIVE",
        "carried_from": "receipt fail_config_registration.mapping_note",
    },
}

target = os.path.join(ROOT, "00_authority/V5_MULTI_PANEL_SOLAR_ARRAY_FREEZE.json")
with open(target, "w", encoding="utf-8") as fh:
    json.dump(freeze, fh, ensure_ascii=False, indent=1)

print("panels frozen: %d" % len(panels))
for row in panels:
    print("  %-16s live_matches_receipt=%s" % (row["name"], row["live_matches_receipt"]))
for row in assemblies:
    print("  %-16s live_matches_receipt=%s" % (row["side"], row["live_matches_receipt"]))
print("cold pose rows: %d/%d within tolerance" % (len(cold_rows) - len(out_of_tol), len(cold_rows)))
print("live hash drift rows: %d" % len(drift))
print("WROTE " + target)
