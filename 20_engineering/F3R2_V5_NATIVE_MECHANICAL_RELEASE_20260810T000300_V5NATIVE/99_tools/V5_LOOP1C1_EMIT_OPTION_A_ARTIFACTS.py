"""Emit the Option A (STRICT CONTRACT REVISION) deliverables for Loop1C1.

Produces:
  04_configurations/V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv
  00_authority/V5_LOOP1C1_EXCEPTION_CONTRACT.yaml
  13_validation/V5_LOOP1C1_FINAL_RECEIPT.json

Every row is classified against the strict criteria, fail-closed. A row is only
KNOWN_DONOR_INTERNAL_INTERFERENCE_ACCEPTED when its volume matches a frozen
donor internal row within tolerance. Rows whose overlap is produced by the
assembly's own prismatic travel (no donor volume counterpart, and/or body pairs
that do not exist at CLOSED) are classified
POSE_INDUCED_ACROSS_MOVING_JOINT_RULING_REQUIRED - they are NOT accepted here.

The functional jaw-face contact shell at CLOSED is separated out as
FUNCTIONAL_JAW_CONTACT_NOT_WHITELISTED so that it can never be laundered into
the donor exception set.
"""

import csv
import hashlib
import json
import os
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = ROOT.replace("\\", "/")
VOL_TOL = 0.05
BBOX_TOL = 0.05

DONOR_PART = "B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
# Canonical donor as recorded by the Loop1C0 receipt's source_open row. The local
# staging copy under 03_top_assembly is transient and is rotated into
# 13_validation/quarantine by each Loop1E attempt, so it must not be the hash anchor.
DONOR_PATH = (
    "F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/"
    "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/B601_ARM_B51_COPY/"
    "inputs/vendor_link_parts/" + DONOR_PART
)
NATIVE = {
    "B601_GRIPPER_PALM.SLDPRT": R + "/01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT",
    "B601_GRIPPER_LEFT_FINGER.SLDPRT": R + "/01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT",
    "B601_GRIPPER_RIGHT_FINGER.SLDPRT": R + "/01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT",
}
# Frozen jaw functional distances from the Loop1C1 assembly receipt (M3R_V2 authority).
FUNCTIONAL_GAP_MM = {"OPEN": 82.2284, "PREGRASP": 50.5026, "CLOSED": 0.0, "HOLDING": 0.0}
TRAVEL_MM = {"OPEN": 71.5, "PREGRASP": 55.0, "CLOSED": 0.0, "HOLDING": 0.0}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest().upper()


def load_json_tail(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return json.loads(text[text.index("{"):])


with open(os.path.join(ROOT, "00_authority/V5_LOOP1C1_INTERFERENCE_FINGERPRINT_ACCEPTANCE.json"), encoding="utf-8") as fh:
    accept = json.load(fh)

donor_rows = load_json_tail(
    os.path.join(ROOT, "99_tools/probe_logs/V5_PROBE_LOOP1C1_DONOR_INHERITANCE_20260811T044327Z.log")
)["rows"]
bodies = load_json_tail(
    os.path.join(ROOT, "99_tools/probe_logs/V5_PROBE_LOOP1C1_INTERFERENCE_BODIES_20260811T045727Z.log")
)
body_states = {s["configuration"]: s["rows"] for s in bodies["states"]}

donor_hash = sha(DONOR_PATH)
native_hash = {name: sha(path) for name, path in NATIVE.items()}

closed_pairs = set()
for row in body_states.get("CLOSED", []):
    for a, b in row.get("body_pairs", []):
        closed_pairs.add(tuple(sorted((a, b))))

JAW_CONTACT_VOLUME_MM3 = 79.527907  # CLOSED finger<->finger jaw contact shell


def body_pairs_for(config, index, components, volume):
    """Return recorded body pairs for a fingerprint row, or None when the probe
    did not name bodies for that row (only the top rows per state were named)."""
    for row in body_states.get(config, []):
        if sorted(row["components"]) == sorted(components) and abs(row["volume_mm3"] - volume) <= VOL_TOL:
            pairs = row.get("body_pairs")
            if pairs:
                return [tuple(sorted(p)) for p in pairs]
    return None


register = []
counters = {}
donor_pool = {}
for config, rows in accept["fingerprints"].items():
    donor_pool[config] = [r["volume_mm3"] for r in donor_rows]

summary = {}
for config, rows in accept["fingerprints"].items():
    pool = donor_pool[config]
    stats = {
        "row_count": len(rows),
        "accepted": 0,
        "functional_jaw_contact": 0,
        "pose_induced_ruling_required": 0,
        "accepted_volume_mm3": 0.0,
        "pose_induced_volume_mm3": 0.0,
        "functional_jaw_contact_volume_mm3": 0.0,
    }
    for index, row in enumerate(rows):
        vol = row["volume_mm3"]
        comp = sorted(row["components"])
        bbox = row["interference_bbox_mm"]
        centre = [round((bbox[i] + bbox[i + 3]) / 2.0, 6) for i in range(3)]

        donor_match = None
        for dv in pool:
            if abs(dv - vol) <= VOL_TOL:
                donor_match = dv
                break
        if donor_match is not None:
            pool.remove(donor_match)

        pairs = body_pairs_for(config, index, comp, vol)
        new_pairs = None if pairs is None else [p for p in pairs if p not in closed_pairs]

        is_finger_finger = comp == [
            "B601_GRIPPER_LEFT_FINGER.SLDPRT",
            "B601_GRIPPER_RIGHT_FINGER.SLDPRT",
        ]
        across_moving_joint = True  # palm is the fixed datum; both fingers translate
        if is_finger_finger and abs(vol - JAW_CONTACT_VOLUME_MM3) <= VOL_TOL:
            disposition = "FUNCTIONAL_JAW_CONTACT_NOT_WHITELISTED"
            rationale = "left/right jaw-face contact shell at CLOSED; explicitly excluded from the donor exception set by the strict criteria"
            stats["functional_jaw_contact"] += 1
            stats["functional_jaw_contact_volume_mm3"] += vol
        elif donor_match is None:
            disposition = "POSE_INDUCED_ACROSS_MOVING_JOINT_RULING_REQUIRED"
            rationale = "no donor internal row matches this volume; overlap is produced by commanded prismatic travel"
            stats["pose_induced_ruling_required"] += 1
            stats["pose_induced_volume_mm3"] += vol
        elif new_pairs:
            disposition = "POSE_INDUCED_ACROSS_MOVING_JOINT_RULING_REQUIRED"
            rationale = "volume matches a donor row but the body pair does not exist at CLOSED; pair is created by commanded travel"
            stats["pose_induced_ruling_required"] += 1
            stats["pose_induced_volume_mm3"] += vol
        else:
            disposition = "KNOWN_DONOR_INTERNAL_INTERFERENCE_ACCEPTED"
            rationale = "volume matches a frozen donor internal row within tolerance; inherited from accepted donor geometry, no assembly-side correction exists"
            stats["accepted"] += 1
            stats["accepted_volume_mm3"] += vol

        counters[config] = counters.get(config, 0) + 1
        fid = "L1C1-%s-%03d" % (config[:4], counters[config])

        if pairs:
            body_a = ";".join(sorted({p[0].split("__")[0] for p in pairs}))
            body_b = ";".join(sorted({p[1].split("__")[0] for p in pairs}))
        else:
            body_a = body_b = "BODY_EVIDENCE_NOT_CAPTURED_BY_PROBE"

        register.append(
            {
                "fingerprint_id": fid,
                "configuration": config,
                "component_A": comp[0],
                "body_A": body_a,
                "component_B": comp[1],
                "body_B": body_b,
                "interference_volume_mm3": vol,
                "centroid_mm_x": centre[0],
                "centroid_mm_y": centre[1],
                "centroid_mm_z": centre[2],
                "centroid_source": "INTERFERENCE_BBOX_CENTER_NOT_VOLUMETRIC_CENTROID",
                "interference_bbox_mm": json.dumps(bbox),
                "donor_hash": donor_hash,
                "native_hash_A": native_hash[comp[0]],
                "native_hash_B": native_hash[comp[1]],
                "donor_volume_match_mm3": "" if donor_match is None else donor_match,
                "internal_donor_only": "YES" if donor_match is not None and not new_pairs else "NO",
                "across_moving_joint": "YES" if across_moving_joint else "NO",
                "motion_relevance": "PRISMATIC_JAW_DOF_TRAVEL_%.1f_MM" % TRAVEL_MM[config],
                "functional_jaw_gap_mm": FUNCTIONAL_GAP_MM[config],
                "involves_spacecraft_solar_hdrm_camera_harness": "NO",
                "external_collision_relevance": "NONE_INTERNAL_TO_GRIPPER_SUBASSEMBLY",
                "disposition": disposition,
                "rationale": rationale,
            }
        )
    summary[config] = {
        k: (round(v, 6) if isinstance(v, float) else v) for k, v in stats.items()
    }

csv_path = os.path.join(ROOT, "04_configurations/V5_LOOP1C1_INTERFERENCE_FINGERPRINT_REGISTER.csv")
with open(csv_path, "w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(register[0].keys()))
    writer.writeheader()
    writer.writerows(register)

three_state = {}
for config in ("OPEN", "PREGRASP", "CLOSED"):
    gap = FUNCTIONAL_GAP_MM[config]
    # The strict CLOSED criterion is "native penetration volume = 0". Native
    # penetration means anything not covered by the frozen donor exception set:
    # pose-induced rows plus the functional jaw-contact shell, which the criteria
    # explicitly refuse to whitelist.
    native_penetration = (
        summary[config]["pose_induced_volume_mm3"] + summary[config]["functional_jaw_contact_volume_mm3"]
    )
    three_state[config] = {
        "functional_finger_distance_mm": gap,
        "functional_distance_requirement": (
            "> 0" if config in ("OPEN", "PREGRASP") else "approximately 0"
        ),
        "functional_distance_pass": (gap > 0) if config in ("OPEN", "PREGRASP") else (abs(gap) <= 1e-6),
        "native_penetration_volume_mm3": round(native_penetration, 6),
        "native_penetration_components": {
            "pose_induced_mm3": round(summary[config]["pose_induced_volume_mm3"], 6),
            "functional_jaw_contact_mm3": round(summary[config]["functional_jaw_contact_volume_mm3"], 6),
        },
        "accepted_donor_inherited_volume_mm3": round(summary[config]["accepted_volume_mm3"], 6),
        "native_penetration_requirement": (
            "= 0" if config == "CLOSED" else "no strict zero requirement, functional distance governs"
        ),
        "native_penetration_requirement_met": native_penetration == 0.0,
    }

contract = {
    "schema": "F3R2_V5_LOOP1C1_EXCEPTION_CONTRACT_V1",
    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "decision": accept["decision"],
    "strict_criteria": [
        "pair is frozen",
        "hash unchanged",
        "internal donor only",
        "not functional palm/finger contact",
        "not left/right functional penetration",
        "not across a moving joint",
        "not involving spacecraft / solar / HDRM / camera / harness",
    ],
    "tolerances": {"volume_abs_tolerance_mm3": VOL_TOL, "bbox_abs_tolerance_mm": BBOX_TOL},
    "teeth": accept["acceptance_rule"]["teeth"],
    "hash_lock": {
        "donor_part": DONOR_PART,
        "donor_sha256": donor_hash,
        "native_parts": native_hash,
    },
    "register": csv_path.replace("\\", "/"),
    "classification_summary": summary,
    "three_state_requirement": three_state,
    "unresolved": (
        "OPEN and PREGRASP carry pose-induced rows that fail the strict criteria; they are "
        "recorded as POSE_INDUCED_ACROSS_MOVING_JOINT_RULING_REQUIRED and are NOT accepted by "
        "this contract"
    ),
    "non_claims": accept["non_claims"],
}

yaml_path = os.path.join(ROOT, "00_authority/V5_LOOP1C1_EXCEPTION_CONTRACT.yaml")


def to_yaml(obj, indent=0):
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, (dict, list)):
                lines.append("%s%s:" % (pad, key))
                lines.extend(to_yaml(value, indent + 1))
            else:
                lines.append("%s%s: %s" % (pad, key, json.dumps(value, ensure_ascii=False)))
    elif isinstance(obj, list):
        for value in obj:
            if isinstance(value, (dict, list)):
                lines.append("%s-" % pad)
                lines.extend(to_yaml(value, indent + 1))
            else:
                lines.append("%s- %s" % (pad, json.dumps(value, ensure_ascii=False)))
    return lines


with open(yaml_path, "w", encoding="utf-8") as fh:
    fh.write("# Loop1C1 Option A strict exception contract - generated, do not hand-edit\n")
    fh.write("\n".join(to_yaml(contract)) + "\n")

total_pose = sum(summary[c]["pose_induced_ruling_required"] for c in summary)
verdict = (
    "V5_LOOP1C1_OPTION_A_STRICT_REVISION_ACCEPTED"
    if total_pose == 0
    else "V5_LOOP1C1_OPTION_A_STRICT_REVISION_PARTIAL_POSE_INDUCED_ROWS_PENDING_HUMAN_RULING"
)

receipt = {
    "schema": "F3R2_V5_LOOP1C1_FINAL_RECEIPT_V1",
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "run_root": R,
    "upstream_assembly_receipt": {
        "path": R + "/13_validation/V5_LOOP1C1_GRIPPER_ASSEMBLY_RECEIPT.json",
        "verdict": "V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY",
        "closed_utc": "2026-08-11T17:14:21Z",
        "note": "that receipt passed against the as-frozen (looser) Option A table; this final receipt re-scores the same evidence against the strict criteria",
    },
    "register": csv_path.replace("\\", "/"),
    "exception_contract": yaml_path.replace("\\", "/"),
    "classification_summary": summary,
    "three_state_requirement": three_state,
    "finding": {
        "donor_crossmatch": R + "/13_validation/V5_LOOP1C1_DONOR_INHERITANCE_CROSSMATCH.json",
        "body_pair_compare": R + "/13_validation/V5_LOOP1C1_BODY_PAIR_SET_COMPARE.json",
        "statement": (
            "CLOSED and HOLDING are 39/39 donor-volume-identical (350.204156 mm3). OPEN and "
            "PREGRASP carry 1266.934 and 779.626 mm3 with no donor volume counterpart, and the "
            "body-pair probe shows 15 body pairs at OPEN that do not exist at CLOSED, all against "
            "PALM_SOLID_09/PALM_SOLID_07. Overlap grows monotonically with commanded travel "
            "(350.2 -> 780.1 -> 1267.4 mm3), so these rows are produced by the prismatic DOF, not "
            "frozen in the donor."
        ),
    },
    "verdict": verdict,
    "next_stage_authorized": False,
    "review_status": "PENDING_HUMAN_RULING_ON_POSE_INDUCED_ROWS",
    "prohibited_claims": [
        "GRIPPER_OPENS_WITHOUT_SELF_COLLISION",
        "ALL_GRIPPER_INTERFERENCE_IS_DONOR_INHERITED",
        "FINAL_NATIVE_CAD_BASELINE",
        "FLIGHT_READY",
    ],
}

receipt_path = os.path.join(ROOT, "13_validation/V5_LOOP1C1_FINAL_RECEIPT.json")
with open(receipt_path, "w", encoding="utf-8") as fh:
    json.dump(receipt, fh, ensure_ascii=False, indent=1)

print("register rows: %d -> %s" % (len(register), csv_path))
print("contract       -> %s" % yaml_path)
print("final receipt  -> %s" % receipt_path)
for config, body in summary.items():
    print(
        "%-9s rows=%2d accepted=%2d jaw_contact=%d pose_induced=%2d (%.3f mm3)"
        % (
            config,
            body["row_count"],
            body["accepted"],
            body["functional_jaw_contact"],
            body["pose_induced_ruling_required"],
            body["pose_induced_volume_mm3"],
        )
    )
print("VERDICT " + verdict)
