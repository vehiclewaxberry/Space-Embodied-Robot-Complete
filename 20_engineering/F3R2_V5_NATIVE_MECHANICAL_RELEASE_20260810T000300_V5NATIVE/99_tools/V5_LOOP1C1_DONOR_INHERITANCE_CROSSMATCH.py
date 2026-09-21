"""Cross-match the frozen native interference fingerprints against the donor's
81 internal positive-volume rows.

Purpose: the Option A acceptance JSON asserts "overlaps pre-exist in the accepted
donor geometry" but only demonstrates volume bit-identity for two volume values.
The native per-configuration totals differ (OPEN 1267.4 / PREGRASP 780.1 /
CLOSED 350.2 mm3), so some native rows cannot be pose-invariant donor rows.
This script partitions every native row into DONOR_VOLUME_MATCHED and
POSE_INDUCED_NO_DONOR_VOLUME_MATCH, fail-closed (no match => not inherited).

Donor rows are expressed in donor part coordinates and native rows in assembly
coordinates, so only volume is comparable without a registered transform. That
limitation is recorded in the output, not hidden.
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "99_tools", "probe_logs")
DONOR_LOG = os.path.join(PROBE, "V5_PROBE_LOOP1C1_DONOR_INHERITANCE_20260811T044327Z.log")
ACCEPT = os.path.join(ROOT, "00_authority", "V5_LOOP1C1_INTERFERENCE_FINGERPRINT_ACCEPTANCE.json")

VOL_TOL = 0.05  # mm^3, same tolerance as the frozen acceptance rule


def load_json_tail(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    start = text.index("{")
    return json.loads(text[start:])


donor = load_json_tail(DONOR_LOG)
donor_volumes = [row["volume_mm3"] for row in donor["rows"]]

with open(ACCEPT, encoding="utf-8") as fh:
    accept = json.load(fh)

report = {
    "schema": "F3R2_V5_LOOP1C1_DONOR_INHERITANCE_CROSSMATCH_V1",
    "method": "volume-only match at |dV| <= %.2f mm3; donor rows are in donor part coordinates and native rows in assembly coordinates, so bbox/centroid are NOT comparable without a registered transform" % VOL_TOL,
    "donor_row_count": len(donor_volumes),
    "fail_closed_rule": "a native row with no donor volume within tolerance is classified POSE_INDUCED, never inherited",
    "configurations": {},
}

for config, rows in accept["fingerprints"].items():
    matched, unmatched = [], []
    pool = list(donor_volumes)
    for idx, row in enumerate(rows):
        vol = row["volume_mm3"]
        hit = None
        for dv in pool:
            if abs(dv - vol) <= VOL_TOL:
                hit = dv
                break
        entry = {
            "row_index": idx,
            "components": row["components"],
            "volume_mm3": vol,
            "donor_volume_mm3": hit,
        }
        if hit is None:
            unmatched.append(entry)
        else:
            pool.remove(hit)
            matched.append(entry)
    report["configurations"][config] = {
        "row_count": len(rows),
        "donor_volume_matched": len(matched),
        "pose_induced_no_donor_volume_match": len(unmatched),
        "matched_volume_mm3": round(sum(r["volume_mm3"] for r in matched), 6),
        "unmatched_volume_mm3": round(sum(r["volume_mm3"] for r in unmatched), 6),
        "unmatched_rows": unmatched,
    }

out = os.path.join(ROOT, "13_validation", "V5_LOOP1C1_DONOR_INHERITANCE_CROSSMATCH.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)

print("donor rows: %d" % len(donor_volumes))
for config, body in report["configurations"].items():
    print(
        "%-9s rows=%2d  donor_matched=%2d (%.3f mm3)  pose_induced=%2d (%.3f mm3)"
        % (
            config,
            body["row_count"],
            body["donor_volume_matched"],
            body["matched_volume_mm3"],
            body["pose_induced_no_donor_volume_match"],
            body["unmatched_volume_mm3"],
        )
    )
print("WROTE " + out)
