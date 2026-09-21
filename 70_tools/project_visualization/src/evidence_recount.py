"""VIZ-Gate 0 Stage 5 -- per-row evidence recount (semantic red line enforcement).

The E1.5 bottleneck table labels 69 rows "UNSAFE", but 66 of those carry NO
fresh dynamic evidence at all (IK_FAIL chain).  The visualization layer must
therefore NEVER color by the raw SAFE/UNSAFE binary.  This module recomputes,
row by row, the four SCIENTIFIC reason classes from `binding_items` of
tables__sim_09_grasp_evaluator__e15_mpcs__e15_bottleneck_summary.csv
(snapshot copy -- iron rule 2):

    rule 1  binding_items contains MPCS_LIMIT_NOT_STRICTLY_POSITIVE
                -> PHYSICAL_LIMIT_EXCEEDED   (a computed number truly exceeds
                                              a registered provisional limit)
    rule 2  else binding_items contains FLEX_SOLVER_FAIL
                -> FLEX_SOLVER_UNKNOWN       (ANCF never converged; cannot judge)
    rule 3  else binding_items consists of missing/invalid evidence codes
                (IK_FAIL / IK_INFEASIBLE / INVALID_OR_MISSING_* /
                 HARD_FLAG_MISSING_OR_INVALID_* / FLEX_STATUS_*)
                -> MISSING_FRESH_EVIDENCE    (no fresh dynamic evidence was
                                              produced this round; NOT a
                                              physical-unsafety statement)
    rule 4  e15_state == SAFE -> VERIFIED_SAFE (expected EMPTY set)

Anything matching none of the rules is reported as UNCLASSIFIED_REVIEW and
must be surfaced, never silently binned.  Expected counts 3/3/66/0, but the
RECOUNT is authoritative -- callers read the returned tally, not the
expectation.

Output: 40_evidence/artifacts/visualization/tables/evidence_recount.csv (one row per case, with
provenance columns).  UNKNOWN != unsafe; missing evidence != physically unsafe.
"""
import _viz_bootstrap as vb  # noqa: F401  (env pins BEFORE numpy)
import csv
import json
import os

SNAP = vb.SNAPSHOT_DIR
BOTTLENECK_CSV = os.path.join(
    SNAP, "tables__sim_09_grasp_evaluator__e15_mpcs__e15_bottleneck_summary.csv")
RUN_MANIFEST = os.path.join(
    SNAP, "results__sim_09_grasp_evaluator__e15_run_manifest.json")
OUT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "evidence_recount.csv")

# the four scientific classes (display names + one-sentence meaning, zh)
CLASSES = {
    "PHYSICAL_LIMIT_EXCEEDED": {
        "color_key": "physical_violation",
        "meaning_zh": "已有数值证明真实超限（post-capture rate 3.06 > 2.0 deg/s，暂行阈值）",
    },
    "FLEX_SOLVER_UNKNOWN": {
        "color_key": "unknown",
        "meaning_zh": "ANCF 柔性求解失败，无法判定（不可判定 ≠ 不安全）",
    },
    "MISSING_FRESH_EVIDENCE": {
        "color_key": "evidence_missing",
        "meaning_zh": "本轮未完成动态证据计算（IK 不可达，未产生新鲜证据；证据缺失 ≠ 物理不安全）",
    },
    "VERIFIED_SAFE": {
        "color_key": "geometry_verified",
        "meaning_zh": "当前无完整证据支持任何案例安全（空集，仅在图例中声明）",
    },
}

# codes that legitimately form a missing/invalid-evidence chain (rule 3)
_MISSING_PREFIXES = (
    "IK_FAIL", "IK_INFEASIBLE",
    "INVALID_OR_MISSING_",
    "HARD_FLAG_MISSING_OR_INVALID_",
    "FLEX_STATUS_",            # SKIPPED_DEFINITE_UNSAFE bookkeeping label
)


def _tokens(binding_items):
    """Split 'a;reason:b;reason:c' into bare code tokens."""
    out = []
    for tok in (binding_items or "").split(";"):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("reason:"):
            tok = tok[len("reason:"):]
        out.append(tok)
    return out


def classify_row(row):
    """(recount_class, matched_rule) for one bottleneck row."""
    toks = _tokens(row["binding_items"])
    if row.get("e15_state") == "SAFE":
        return "VERIFIED_SAFE", "rule4_e15_state_SAFE"
    if any(t == "MPCS_LIMIT_NOT_STRICTLY_POSITIVE" for t in toks):
        return "PHYSICAL_LIMIT_EXCEEDED", "rule1_MPCS_LIMIT_NOT_STRICTLY_POSITIVE"
    if any(t == "FLEX_SOLVER_FAIL" for t in toks):
        return "FLEX_SOLVER_UNKNOWN", "rule2_FLEX_SOLVER_FAIL"
    informative = [t for t in toks
                   if not t.startswith(_MISSING_PREFIXES)
                   and t not in ("post_capture_rate_dps",)]
    if toks and not informative:
        return "MISSING_FRESH_EVIDENCE", "rule3_missing_or_invalid_chain"
    return "UNCLASSIFIED_REVIEW", f"no_rule_matched:{';'.join(toks)[:120]}"


def recount(write=True):
    """Recompute all rows; optionally write evidence_recount.csv.

    Returns {"rows": [...], "tally": {...}, "expected": {...},
             "matches_expected": bool, "provenance": {...}}.
    """
    with open(BOTTLENECK_CSV, newline="", encoding="utf-8") as f:
        raw = list(csv.DictReader(f))
    manifest = json.load(open(RUN_MANIFEST, encoding="utf-8"))
    commit = vb.repo_commit_short()
    src_rel = os.path.relpath(BOTTLENECK_CSV, vb.REPO_ROOT).replace("\\", "/")

    rows, tally = [], {k: 0 for k in
                       ("PHYSICAL_LIMIT_EXCEEDED", "FLEX_SOLVER_UNKNOWN",
                        "MISSING_FRESH_EVIDENCE", "VERIFIED_SAFE",
                        "UNCLASSIFIED_REVIEW")}
    for r in raw:
        cls, rule = classify_row(r)
        tally[cls] += 1
        rows.append({
            "grid_index": r["grid_index"],
            "case_id": r["case_id"],
            "scenario_hash": r["scenario_hash"],
            "grasp_point_id": r["grasp_point_id"],
            "t_c_s": r["t_c_s"],
            "v_app_mps": r["v_app_mps"],
            "task_constraint_mode": r["task_constraint_mode"],
            "e15_state_raw": r["e15_state"],
            "binding_items": r["binding_items"],
            "recount_class": cls,
            "matched_rule": rule,
            "M_PCS_e15": r["M_PCS_e15"],
            "post_capture_rate_dps": r["post_capture_rate_dps"],
            "limit__post_capture_rate_dps": r["limit__post_capture_rate_dps"],
            "margin__post_capture_rate_dps": r["margin__post_capture_rate_dps"],
            "threshold_registry_status": r["threshold_registry_status"],
            "recount_git_commit": commit,
            "recount_source_file": src_rel,
            "e15_source_commit": manifest["source_commit"][:12],
        })

    expected = {"PHYSICAL_LIMIT_EXCEEDED": 3, "FLEX_SOLVER_UNKNOWN": 3,
                "MISSING_FRESH_EVIDENCE": 66, "VERIFIED_SAFE": 0,
                "UNCLASSIFIED_REVIEW": 0}
    out = {
        "rows": rows,
        "tally": tally,
        "expected": expected,
        "matches_expected": tally == expected,
        "provenance": {
            "git_commit": commit,
            "source_file": src_rel,
            "e15_source_commit": manifest["source_commit"],
            "results_sha256": manifest["results_sha256"],
            "threshold_registry_sha256": manifest["threshold_registry_sha256"],
        },
    }
    if write:
        with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        out["csv_path"] = OUT_CSV
    return out


if __name__ == "__main__":
    res = recount()
    print("recount tally:", res["tally"])
    print("expected     :", res["expected"])
    print("matches_expected:", res["matches_expected"])
    print("written:", res.get("csv_path"))
    if res["tally"]["UNCLASSIFIED_REVIEW"]:
        bad = [r for r in res["rows"]
               if r["recount_class"] == "UNCLASSIFIED_REVIEW"]
        for r in bad:
            print("UNCLASSIFIED:", r["case_id"], r["matched_rule"])
        raise SystemExit(1)
