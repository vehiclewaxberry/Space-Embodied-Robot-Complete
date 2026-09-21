"""VIZ-Gate 0 acceptance test 5 -- semantic red lines + self-containment.

  1. Evidence recount: evidence_recount.recount() recomputed in-process must
     tally PHYSICAL_LIMIT_EXCEEDED/FLEX_SOLVER_UNKNOWN/MISSING_FRESH_EVIDENCE/
     VERIFIED_SAFE = 3/3/66/0 (UNCLASSIFIED_REVIEW = 0), the on-disk
     40_evidence/artifacts/visualization/tables/evidence_recount.csv must agree row-for-row, and
     the tally must be self-consistent with e15_gate_check.json state_counts
     (SAFE = VERIFIED_SAFE, UNKNOWN = FLEX_SOLVER_UNKNOWN,
      UNSAFE = PHYSICAL_LIMIT_EXCEEDED + MISSING_FRESH_EVIDENCE).
  2. Dashboard HTML text semantics: project_visualization_v0.html must NOT
     claim any non-zero VERIFIED_SAFE count (regex 'VERIFIED_SAFE:\\s*[1-9]'),
     MUST carry the REPEAT_E1_5 banner, MUST carry the DIAGNOSTIC marker for
     flexible-dynamics content, and MUST name all four reason classes.
  3. Self-containment: static scan of BOTH the dashboard and the grasp
     explorer HTML -- zero external fetch targets (no src=/href= pointing at
     http(s), no external <script src>, no @import/url(http...)).
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap as vb  # noqa: E402  (pins OMP/MKL=1 BEFORE numpy)

import csv                   # noqa: E402
import json                  # noqa: E402

DASHBOARD = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                         "project_visualization_v0.html")
EXPLORER = os.path.join(REPO, "40_evidence", "artifacts", "visualization",
                        "grasp_geometry_explorer_v0.html")
RECOUNT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "evidence_recount.csv")
GATE_JSON = os.path.join(vb.SNAPSHOT_DIR,
                         "results__sim_09_grasp_evaluator__e15_gate_check.json")

EXPECTED_TALLY = {"PHYSICAL_LIMIT_EXCEEDED": 3, "FLEX_SOLVER_UNKNOWN": 3,
                  "MISSING_FRESH_EVIDENCE": 66, "VERIFIED_SAFE": 0,
                  "UNCLASSIFIED_REVIEW": 0}

_MARKUP_PATTERNS = (
    r'(?:src|href)\s*=\s*["\']\s*https?://',   # any external src/href
    r'@import\s+url\(\s*["\']?https?://',
    r'url\(\s*["\']?https?://',
)


def _scan_external(path):
    """External fetch targets in MARKUP. Scripts must be inline (no src
    attribute); script BODIES are stripped before the markup scan because the
    inlined plotly bundle legitimately contains href/src strings inside JS
    literals (never fetched by the document)."""
    with open(path, encoding="utf-8") as f:
        html = f.read()
    hits = [m.group(0) for m in re.finditer(r"<script\b[^>]*\bsrc\s*=", html)]
    markup = re.sub(r"<script\b[^>]*>.*?</script>", "<script></script>",
                    html, flags=re.S)
    for pat in _MARKUP_PATTERNS:
        hits += [m.group(0) for m in re.finditer(pat, markup)]
    return html, hits


def main(verbose=True):
    details = []

    # ---- 1. recount 3/3/66/0 + gate-check self-consistency ---------------
    import evidence_recount
    rec = evidence_recount.recount(write=False)
    assert rec["tally"] == EXPECTED_TALLY, \
        f"recount tally {rec['tally']} != expected {EXPECTED_TALLY}"
    assert rec["matches_expected"], "recount reports matches_expected=False"

    assert os.path.isfile(RECOUNT_CSV), f"missing {RECOUNT_CSV}"
    with open(RECOUNT_CSV, newline="", encoding="utf-8") as f:
        disk = list(csv.DictReader(f))
    assert len(disk) == 72, f"evidence_recount.csv rows {len(disk)} != 72"
    fresh = {r["case_id"]: r["recount_class"] for r in rec["rows"]}
    mism = [r["case_id"] for r in disk
            if fresh.get(r["case_id"]) != r["recount_class"]]
    assert not mism, f"on-disk recount_class differs for: {mism[:5]}"

    gate = json.load(open(GATE_JSON, encoding="utf-8"))
    sc = gate["state_counts"]
    t = rec["tally"]
    assert sc["SAFE"] == t["VERIFIED_SAFE"], (sc, t)
    assert sc["UNKNOWN"] == t["FLEX_SOLVER_UNKNOWN"], (sc, t)
    assert sc["UNSAFE"] == (t["PHYSICAL_LIMIT_EXCEEDED"]
                            + t["MISSING_FRESH_EVIDENCE"]), (sc, t)
    details.append(
        f"recount tally {t['PHYSICAL_LIMIT_EXCEEDED']}/"
        f"{t['FLEX_SOLVER_UNKNOWN']}/{t['MISSING_FRESH_EVIDENCE']}/"
        f"{t['VERIFIED_SAFE']} (UNCLASSIFIED {t['UNCLASSIFIED_REVIEW']}), "
        f"on-disk CSV agrees (72 rows), gate state_counts "
        f"SAFE {sc['SAFE']} / UNKNOWN {sc['UNKNOWN']} / UNSAFE {sc['UNSAFE']} "
        "self-consistent")

    # ---- 2. dashboard text semantics --------------------------------------
    assert os.path.isfile(DASHBOARD), \
        f"dashboard missing: {DASHBOARD} (build it first)"
    html, dash_hits = _scan_external(DASHBOARD)

    bad_safe = re.findall(r"VERIFIED_SAFE:\s*[1-9]", html)
    assert not bad_safe, f"dashboard claims non-zero VERIFIED_SAFE: {bad_safe}"
    assert "REPEAT_E1_5" in html, "dashboard lacks the REPEAT_E1_5 banner"
    assert "DIAGNOSTIC" in html, "dashboard lacks the DIAGNOSTIC marker"
    for cls in ("PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
                "MISSING_FRESH_EVIDENCE", "VERIFIED_SAFE"):
        assert cls in html, f"dashboard lacks reason class {cls}"
    details.append("dashboard: no non-zero VERIFIED_SAFE claim; REPEAT_E1_5 "
                   "banner present; DIAGNOSTIC marker present; all four "
                   "reason classes named")

    # ---- 3. zero external references (dashboard + explorer) --------------
    assert not dash_hits, f"dashboard external refs: {dash_hits[:5]}"
    assert os.path.isfile(EXPLORER), f"explorer missing: {EXPLORER}"
    _, exp_hits = _scan_external(EXPLORER)
    assert not exp_hits, f"explorer external refs: {exp_hits[:5]}"
    details.append("static scan: 0 external src/href/script/@import/url() "
                   "targets in dashboard AND explorer (fully offline)")

    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_status_semantics", "pass": True, "details": details}


if __name__ == "__main__":
    print("test_status_semantics:")
    main()
    print("PASS")
