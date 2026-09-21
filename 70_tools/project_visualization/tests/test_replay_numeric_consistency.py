"""VIZ-Gate 0 acceptance test 4 -- replay-video keyframe numeric consistency.

Checks 40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv (written by the six
replay modules at render time; every row ties an on-screen number at a given
frame back to its truth CSV/JSON):
  A. every row has match == True (abs_diff <= tolerance, exact by default);
  B. exactly the expected 44 keyframe rows exist;
  C. all six videos are covered exactly once (no filename aliases).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "70_tools", "project_visualization", "src"))
import _viz_bootstrap as vb  # noqa: E402  (pins OMP/MKL=1 BEFORE numpy)

import csv                   # noqa: E402

KF_CSV = os.path.join(vb.VIZ_TABLES_DIR, "replay_keyframe_check.csv")
EXPECTED_COUNTS = {
    "anim_v01_target_tumble": 7,
    "anim_v02_b601_approach": 7,
    "anim_v03_base_reaction": 6,
    "anim_v04_capture_impulse": 8,
    "anim_v05_flex_diagnostic": 8,
    "anim_v06_gate_explanation": 8,
}


def main(verbose=True):
    assert os.path.isfile(KF_CSV), f"missing {KF_CSV}"
    with open(KF_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    bad = [r for r in rows if r["match"] != "True"]
    assert not bad, ("keyframe mismatches: "
                     + "; ".join(f"{r['video']}#{r['frame_index']}:"
                                 f"{r['quantity']}" for r in bad))

    videos = sorted(set(r["video"] for r in rows))
    per_video = {v: sum(r["video"] == v for r in rows) for v in videos}
    assert per_video == EXPECTED_COUNTS, \
        f"keyframe groups/counts differ: {per_video} != {EXPECTED_COUNTS}"
    assert len(rows) == sum(EXPECTED_COUNTS.values()), \
        f"expected 44 keyframes, found {len(rows)}"
    details = [
        f"{len(rows)}/{len(rows)} keyframe rows match=True (exact contract)",
        f"{len(videos)} videos covered exactly once: "
        + ", ".join(f"{v}({n})" for v, n in per_video.items()),
    ]
    if verbose:
        for d in details:
            print("  " + d)
    return {"name": "test_replay_numeric_consistency", "pass": True,
            "details": details, "n_rows": len(rows), "videos": per_video}


if __name__ == "__main__":
    print("test_replay_numeric_consistency:")
    main()
    print("PASS")
