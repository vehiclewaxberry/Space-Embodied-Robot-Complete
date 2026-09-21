"""VIZ-Gate 0 Phase 4 runner -- builds all six replay videos + the shared
keyframe-consistency table 40_evidence/artifacts/visualization/tables/replay_keyframe_check.csv.

Order: cheap 2D first (v06), then CSV/read-only evidence replays, with the
sim_07 diagnostic reel last. No flexible-dynamics run is triggered. Each module is also runnable
standalone (python <module>.py) and will only replace its own keyframe rows.
"""
import _viz_bootstrap  # noqa: F401
import time

import video_utils as vu


def run():
    import gate_explanation_replay
    import target_tumble_replay
    import sim05_replay
    import sim06_replay
    import sim09_candidate_replay
    import sim07_flex_replay

    mods = [gate_explanation_replay, target_tumble_replay, sim05_replay,
            sim06_replay, sim09_candidate_replay, sim07_flex_replay]
    summary = []
    for m in mods:
        t0 = time.time()
        out = m.main()
        dur, mb, w, h = vu.video_info(out["path"])
        summary.append((out["video"], dur, mb, w, h, time.time() - t0))
    print("\n=== phase-4 replay summary ===")
    for name, dur, mb, w, h, wall in summary:
        print(f"{name}: {dur:.1f} s | {mb:.1f} MB | {w}x{h} | render {wall:.0f} s")
    print(f"keyframe table: {vu.KEYFRAME_CSV}")


if __name__ == "__main__":
    run()
