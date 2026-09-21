"""Compare the OPEN and CLOSED interference body-pair sets.

The donor cross-match showed CLOSED/HOLDING are 39/39 donor-volume-identical
while OPEN/PREGRASP carry 1266.9 / 779.6 mm3 with no donor volume counterpart.
Two readings are possible:

  (a) the same donor modelling defect (rail passing through a finger guide bore
      modelled as solid), whose overlap volume grows with prismatic travel; then
      no NEW body pair may appear at OPEN, and
  (b) a genuinely new assembly-side collision at OPEN; then new body pairs appear.

This script decides between them from the probe body-pair evidence. Fail-closed:
any body pair present at OPEN but absent at CLOSED is reported as NEW.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(
    ROOT, "99_tools", "probe_logs", "V5_PROBE_LOOP1C1_INTERFERENCE_BODIES_20260811T045727Z.log"
)


def load_json_tail(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    return json.loads(text[text.index("{"):])


data = load_json_tail(LOG)
states = {s["configuration"]: s for s in data["states"]}


def pair_set(config):
    out = set()
    for row in states[config]["rows"]:
        for a, b in row.get("body_pairs", []):
            out.add(tuple(sorted((a, b))))
    return out


def solid_set(config):
    out = set()
    for row in states[config]["rows"]:
        for a, b in row.get("body_pairs", []):
            out.add(a.split("__")[0])
            out.add(b.split("__")[0])
    return out


open_pairs, closed_pairs = pair_set("OPEN"), pair_set("CLOSED")
open_solids, closed_solids = solid_set("OPEN"), solid_set("CLOSED")

new_pairs = sorted(open_pairs - closed_pairs)
new_solids = sorted(open_solids - closed_solids)

# The probe named bodies only for the top rows of each state, so the CLOSED pair
# set is a SUBSET of the true CLOSED pair set. A pair reported new at OPEN could
# still live in an unnamed CLOSED row. This comparison is therefore corroborating
# evidence with stated coverage, not a closed proof; the primary discriminator is
# the donor volume cross-match, which uses the complete tables.
rows_with_pairs = {
    config: sum(1 for row in states[config]["rows"] if row.get("body_pairs"))
    for config in states
}

report = {
    "schema": "F3R2_V5_LOOP1C1_BODY_PAIR_SET_COMPARE_V1",
    "source_log": LOG.replace("\\", "/"),
    "configurations_with_body_evidence": sorted(states),
    "coverage_limitation": {
        "statement": "the probe named bodies only for the top rows of each state",
        "rows_with_named_bodies": rows_with_pairs,
        "total_rows_in_frozen_table": {"OPEN": 28, "PREGRASP": 16, "CLOSED": 39, "HOLDING": 39},
        "consequence": "body_pairs_new_at_open is an upper bound; the primary discriminator is the donor volume cross-match over the complete tables",
    },
    "open": {"row_count": len(states["OPEN"]["rows"]), "body_pair_count": len(open_pairs), "solid_count": len(open_solids)},
    "closed": {"row_count": len(states["CLOSED"]["rows"]), "body_pair_count": len(closed_pairs), "solid_count": len(closed_solids)},
    "body_pairs_new_at_open": new_pairs,
    "body_pairs_new_at_open_count": len(new_pairs),
    "solids_new_at_open": new_solids,
    "verdict": (
        "OPEN_INTRODUCES_BODY_PAIRS_ABSENT_FROM_NAMED_CLOSED_ROWS"
        if new_pairs
        else "OPEN_SUBSET_OF_NAMED_CLOSED_BODY_PAIRS"
    ),
}

out = os.path.join(ROOT, "13_validation", "V5_LOOP1C1_BODY_PAIR_SET_COMPARE.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)

print("OPEN   rows=%d pairs=%d solids=%d" % (len(states["OPEN"]["rows"]), len(open_pairs), len(open_solids)))
print("CLOSED rows=%d pairs=%d solids=%d" % (len(states["CLOSED"]["rows"]), len(closed_pairs), len(closed_solids)))
print("NEW body pairs at OPEN: %d" % len(new_pairs))
for pair in new_pairs[:40]:
    print("   %s  <->  %s" % pair)
print("NEW solids at OPEN: %s" % (new_solids or "none"))
print("VERDICT " + report["verdict"])
print("WROTE " + out)
