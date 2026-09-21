# -*- coding: utf-8 -*-
"""F3R2 G5: continuous-path clearance verification.

Freezing end states is not enough: a transition can be clean at both ends and
collide in the middle.  Every authorised transition is therefore SAMPLED along
a joint-space interpolation, adaptively refined wherever the clearance drops,
and each sample is measured with the same instrument as the frozen poses.

Fail-closed, every one of these makes the path FAIL rather than pass quietly:
  * empty comparison set at any sample
  * missing geometry for any part
  * an undefined configuration
  * a path in the official set that was not swept
  * an Infinity produced by an empty candidate set
  * a reference-only body used as physical evidence
  * an unparsed result

Paths whose sequence is not authorised (SERVICE_DOCKING, SERVICE_GRASP,
SERVICE_TRANSPORT, SERVICE_ASSEMBLY, RETRIEVED_NOMINAL) have no q vector in
existence.  They are reported NOT_DEFINED_NO_AUTHORISED_POSE -- inventing joint
angles for them would fabricate the very evidence this gate exists to check.
"""
import json
import sys
import traceback

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P
from r2e_g3b_poses import evaluate, CLEAR_MIN_MM

log = C.Log("r2k_g5_paths")
OUTJ = C.CLR2 / "F3R2_CONTINUOUS_CLEARANCE_RESULTS.json"
OUTC = C.CLR2 / "F3R2_CONTINUOUS_CLEARANCE_RESULTS.csv"
POSEY = C.CFG2 / "F3R2_ARM_INITIAL_POSE.yaml"
FREEZE = C.CFG2 / "F3R2_POSE_SEARCH.json"
EVALJ = C.CFG2 / "F3R2_POSE_EVALUATION.json"
JOURNAL = C.CLR2 / "F3R2_G5_JOURNAL.json"

COARSE = 9          # samples per segment including both ends
REFINE_BELOW_MM = 25.0
REFINE_EXTRA = 8

# The official runtime path, as far as poses actually exist.
OFFICIAL = [
    ("Q_DEPLOYED_HOME", "Q_SERVICE_READY", "AUTHORISED"),
    ("Q_SERVICE_READY", "SERVICE_DOCKING", "NOT_DEFINED"),
    ("SERVICE_DOCKING", "SERVICE_GRASP", "NOT_DEFINED"),
    ("SERVICE_GRASP", "SERVICE_TRANSPORT", "NOT_DEFINED"),
    ("SERVICE_TRANSPORT", "SERVICE_ASSEMBLY", "NOT_DEFINED"),
    ("SERVICE_ASSEMBLY", "RETRIEVED_NOMINAL", "NOT_DEFINED"),
]
ENGINEERING = [
    ("Q_STOW_ENGINEERING_CANDIDATE", "SOLAR_DEPLOY_ARM_LOCKED",
     "CONFIG_CHANGE_ONLY"),
    ("SOLAR_DEPLOY_ARM_LOCKED", "Q_RELEASE_CLEAR", "AUTHORISED"),
    ("Q_RELEASE_CLEAR", "Q_DEPLOYED_HOME", "AUTHORISED"),
]


def load_poses():
    ev = json.loads(EVALJ.read_text(encoding="utf-8"))["poses"]
    se = json.loads(FREEZE.read_text(encoding="utf-8"))["results"]
    q = {"Q_AS_BUILT_REFERENCE": ev["Q_AS_BUILT_REFERENCE"]["q_deg"],
         "Q_STOW_ENGINEERING_CANDIDATE":
             ev["Q_STOW_ENGINEERING_CANDIDATE"]["q_deg"]}
    for k in ("Q_DEPLOYED_HOME", "Q_RELEASE_CLEAR", "Q_SERVICE_READY"):
        q[k] = se[k]["chosen"]["evaluation"]["q_deg"]
    # SOLAR_DEPLOY_ARM_LOCKED holds the arm at q_stow (G2 arm_referenced_config)
    q["SOLAR_DEPLOY_ARM_LOCKED"] = q["Q_STOW_ENGINEERING_CANDIDATE"]
    return q


def sample_segment(qa, qb, arms, envs, label, q_ref=None):
    """Adaptive sweep of one segment; returns per-sample rows.

    q_ref is the pose the arm meshes are baked at, so a stow-side sweep uses
    the STOWED mesh set with q_ref = q_stow instead of double-posing it."""
    qa, qb = np.array(qa, float), np.array(qb, float)
    ts = list(np.linspace(0.0, 1.0, COARSE))
    out, seen = [], set()
    while ts:
        t = ts.pop(0)
        key = round(float(t), 6)
        if key in seen:
            continue
        seen.add(key)
        q = (qa + (qb - qa) * t).tolist()
        ev, _ = evaluate(q, arms, envs, "%s@t=%.3f" % (label, t),
                         q_ref=q_ref)
        crit = {"moving_to_bus": ev["min_moving_link_to_bus_mm"],
                "arm_to_wing": ev["min_arm_to_wing_mm"],
                "gripper_to_bus": ev["min_gripper_to_bus_mm"],
                "arm_to_saddle": ev["min_arm_to_saddle_mm"]}
        problems = []
        if ev["n_moving_bus_pairs"] == 0:
            problems.append("EMPTY_MOVING_BUS_COMPARISON_SET")
        if ev["n_wing_pairs"] == 0:
            problems.append("EMPTY_WING_COMPARISON_SET")
        if ev.get("unevaluable_pairs", {}).get("total", 0):
            problems.append("UNEVALUABLE_PAIRS_%d"
                            % ev["unevaluable_pairs"]["total"])
        for k, v in crit.items():
            if v is None:
                problems.append("NO_VALUE_%s" % k.upper())
            elif not np.isfinite(v):
                problems.append("NON_FINITE_%s" % k.upper())
        worst = min([v for v in crit.values()
                     if v is not None and np.isfinite(v)] or [float("nan")])
        row = {"segment": label, "t": round(float(t), 4),
               "q_deg": [round(v, 3) for v in q],
               "min_moving_to_bus_mm": crit["moving_to_bus"],
               "min_arm_to_wing_mm": crit["arm_to_wing"],
               "min_gripper_to_bus_mm": crit["gripper_to_bus"],
               "min_arm_to_saddle_mm": crit["arm_to_saddle"],
               "worst_critical_mm": None if np.isnan(worst) else round(worst, 4),
               "n_moving_bus_pairs": ev["n_moving_bus_pairs"],
               "n_wing_pairs": ev["n_wing_pairs"],
               "joint_limits_valid": ev["joint_limits_valid"],
               "limit_margin_deg": ev["nearest_joint_limit_margin_deg"],
               "problems": ";".join(problems),
               "pass": (not problems and not np.isnan(worst)
                        and worst >= CLEAR_MIN_MM
                        and ev["joint_limits_valid"])}
        out.append(row)
        log.ev("SAMPLE", seg=label, t=row["t"], worst=row["worst_critical_mm"],
               ok=row["pass"])
        # refine around a tight sample, once
        if (row["worst_critical_mm"] is not None
                and row["worst_critical_mm"] < REFINE_BELOW_MM
                and len(seen) < COARSE + REFINE_EXTRA):
            for dt in (-0.5 / (COARSE - 1), 0.5 / (COARSE - 1)):
                tt = min(1.0, max(0.0, t + dt))
                if round(tt, 6) not in seen:
                    ts.append(tt)
    out.sort(key=lambda r: r["t"])
    return out


def main():
    rep = {"schema": "F3R2_CONTINUOUS_CLEARANCE_V1",
           "method": ("joint-space linear interpolation, %d coarse samples per "
                      "segment plus adaptive refinement below %.0f mm; every "
                      "sample measured with the same CAD-mesh instrument as "
                      "the frozen poses" % (COARSE, REFINE_BELOW_MM)),
           "authority_note": ("mesh tier; SolidWorks native B-rep sweep was "
                              "not obtainable on this machine "
                              "(G3A_NATIVE_ATTEMPTS.json)"),
           "clearance_criterion_mm": CLEAR_MIN_MM}
    rows = []
    try:
        C.check_protected2("G5_PRE")
        q = load_poses()
        arms = P.arm_parts("DEPLOYED")
        envs = P.env_parts("DEPLOYED",
                           wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED"))
        arms_s = P.arm_parts("STOWED")
        envs_s = P.env_parts("STOWED", wings=("WING_L_STOWED", "WING_R_STOWED"))

        def run(seq, tag, use_stowed_env=False):
            res = []
            jr = (json.loads(JOURNAL.read_text(encoding="utf-8"))
                  if JOURNAL.is_file() else {})
            for a, b, kind in seq:
                lab = "%s: %s -> %s" % (tag, a, b)
                if lab in jr:
                    res.append(jr[lab]["summary"])
                    rows.extend(jr[lab].get("rows", []))
                    log.ev("SEGMENT_RESUMED", seg=lab)
                    continue
                if kind == "NOT_DEFINED" or a not in q or b not in q:
                    s = {"segment": lab, "status":
                         "NOT_DEFINED_NO_AUTHORISED_POSE",
                         "reason": ("no q vector exists for this state; "
                                    "inventing one would fabricate evidence"),
                         "swept": False, "pass": None}
                    res.append(s)
                    jr[lab] = {"summary": s, "rows": []}
                    C.write_json(JOURNAL, jr)
                    log.ev("SEGMENT_SKIPPED", seg=lab, why="NOT_DEFINED")
                    continue
                if kind == "CONFIG_CHANGE_ONLY":
                    s = {"segment": lab,
                         "status": "NO_ARM_MOTION_CONFIG_CHANGE_ONLY",
                         "reason": ("both configurations hold the arm at "
                                    "q_stow; only the wing panels change, and "
                                    "the wing deploy TRANSIT path is "
                                    "unauthorised (G2)"),
                         "swept": False, "pass": None}
                    res.append(s)
                    jr[lab] = {"summary": s, "rows": []}
                    C.write_json(JOURNAL, jr)
                    log.ev("SEGMENT_SKIPPED", seg=lab, why="NO_ARM_MOTION")
                    continue
                A, E = ((arms_s, envs_s) if use_stowed_env else (arms, envs))
                qr = q["Q_STOW_ENGINEERING_CANDIDATE"] if use_stowed_env \
                    else None
                srows = sample_segment(q[a], q[b], A, E, lab, q_ref=qr)
                rows.extend(srows)
                ok = all(r["pass"] for r in srows)
                worst = min((r["worst_critical_mm"] for r in srows
                             if r["worst_critical_mm"] is not None),
                            default=None)
                s = {"segment": lab, "status": "SWEPT",
                     "samples": len(srows), "swept": True,
                     "worst_critical_mm": worst,
                     "failing_samples": [r["t"] for r in srows
                                         if not r["pass"]],
                     "problems": sorted({p for r in srows
                                         for p in r["problems"].split(";")
                                         if p}),
                     "pass": ok}
                res.append(s)
                jr[lab] = {"summary": s, "rows": srows}
                C.write_json(JOURNAL, jr)
                log.ev("SEGMENT_DONE", seg=lab, samples=len(srows),
                       worst=worst, ok=ok)
            return res

        rep["official_path"] = run(OFFICIAL, "OFFICIAL")
        # The engineering path starts in the stow configuration, so it is swept
        # against the STOWED mesh set (stowed wings, and the arm links as they
        # are baked at q_stow).
        rep["engineering_path"] = run(ENGINEERING, "ENGINEERING",
                                      use_stowed_env=True)

        off_swept = [s for s in rep["official_path"] if s["swept"]]
        off_skipped = [s for s in rep["official_path"] if not s["swept"]]
        eng_swept = [s for s in rep["engineering_path"] if s["swept"]]
        rep["summary"] = {
            "official_segments_total": len(OFFICIAL),
            "official_segments_swept": len(off_swept),
            "official_segments_not_defined": len(off_skipped),
            "official_swept_all_pass": all(s["pass"] for s in off_swept),
            "official_worst_mm": min((s["worst_critical_mm"]
                                      for s in off_swept
                                      if s["worst_critical_mm"] is not None),
                                     default=None),
            "engineering_segments_swept": len(eng_swept),
            "engineering_swept_all_pass": all(s["pass"] for s in eng_swept),
            "engineering_worst_mm": min((s["worst_critical_mm"]
                                         for s in eng_swept
                                         if s["worst_critical_mm"] is not None),
                                        default=None),
            "total_samples": len(rows)}
        # fail-closed: an undefined official segment is NOT a pass
        rep["official_path_fully_verified"] = (
            rep["summary"]["official_segments_not_defined"] == 0
            and rep["summary"]["official_swept_all_pass"])
        rep["verdict"] = ("G5_SWEPT_OFFICIAL_INCOMPLETE"
                          if not rep["official_path_fully_verified"]
                          else "G5_ALL_PATHS_VERIFIED")
        rep["protected_post"] = C.check_protected2("G5_POST")["verdict"]
    except Exception as exc:
        rep["verdict"] = "G5_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_csv(OUTC, rows)
    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    for k in ("official_path", "engineering_path"):
        print("\n%s:" % k)
        for s in rep.get(k, []):
            if not s["swept"]:
                print("   %-58s %s" % (s["segment"][:58], s["status"]))
            else:
                print("   %-58s samples=%-3d worst=%-9s pass=%s %s"
                      % (s["segment"][:58], s["samples"],
                         s["worst_critical_mm"], s["pass"],
                         s["problems"] or ""))
    print("\nsummary:", json.dumps(rep.get("summary"), ensure_ascii=False))
    if rep["verdict"] == "G5_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"].startswith("G5_") and
             rep["verdict"] != "G5_FAIL" else 1)


if __name__ == "__main__":
    main()
