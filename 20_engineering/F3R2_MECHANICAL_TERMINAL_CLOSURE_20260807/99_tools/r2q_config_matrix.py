# -*- coding: utf-8 -*-
"""F3R2 configuration matrix: one row per configuration, from THIS campaign's
own measurements -- not copied from the G2 matrix.

Where a column can only come from G2 it says so; where F3R2 measured it fresh,
the F3R2 number is used.
"""
import json
import sys

import r2_common as C

OUT = C.CFG2 / "F3R2_CONFIGURATION_MATRIX.csv"
G2M = (C.F3R1 / "04_configurations" / "G2"
       / "F3R1_G2_CONFIGURATION_MATRIX.csv")


def main():
    import csv
    g2 = {}
    with open(G2M, encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            g2[r["configuration"]] = r
    ra = json.loads((C.NC2 / "F3R2_REFERENCE_AUDIT.json")
                    .read_text(encoding="utf-8"))
    off = json.loads((C.CLR2 / "G3A_NATIVE_INTERFERENCE_RESULTS.json")
                     .read_text(encoding="utf-8"))
    nat = json.loads((C.CLR2 / "G3A_JOURNAL.json").read_text(encoding="utf-8")) \
        if (C.CLR2 / "G3A_JOURNAL.json").is_file() else {}

    rows = []
    for c in C.CONFIGS:
        a = ra["per_configuration"].get(c, {})
        o = off["per_configuration"].get(c, {})
        n = nat.get(c, {}).get("summary", {})
        g = g2.get(c, {})
        rows.append({
            "configuration": c,
            "f3r2_components": a.get("components"),
            "f3r2_suppressed": a.get("suppressed"),
            "f3r2_mates_total": a.get("mates_total"),
            "f3r2_mate_errors": a.get("mates_error"),
            "f3r2_refs_outside_tree": a.get("resolved_outside_f3r2"),
            "arm_referenced_config": (off.get("arm_pose_binding", {})
                                      .get(c, {}).get("arm_referenced_config")),
            "arm_q_deg": json.dumps((off.get("arm_pose_binding", {})
                                     .get(c, {}).get("q_deg"))),
            "live_wings": ";".join(o.get("live_wings", [])),
            "offline_pairs_screened": o.get("pairs_screened"),
            "offline_pairs_mesh_evaluated": o.get("pairs_mesh_evaluated"),
            "offline_interference_or_too_close":
                o.get("interference_or_too_close"),
            "offline_min_gap_mm": o.get("min_gap_mm"),
            "offline_min_gap_pair": o.get("min_gap_pair"),
            "native_run": ("YES" if n else "NOT_RUN"),
            "native_pairs": n.get("count_real"),
            "native_arm_attribution": n.get("arm_involvement_verdict",
                                            "NOT_RUN"),
            "g2_geometric_differentiation":
                g.get("geometric_differentiation"),
            "g2_angle_status": g.get("angle_status"),
            "g2_runtime_compliance": g.get("runtime_compliance"),
            "g2_safe00_entry": g.get("safe00_entry"),
            "f3r2_in_runtime_enum": ("YES" if c in ("DEPLOYED_NOMINAL",
                                                    "SERVICE") else "NO"),
            "f3r2_hold": {
                "STOWED_ENGINEERING_CANDIDATE":
                    "STOW_RESTRAINT_ENGINEERING_HOLD",
                "SOLAR_DEPLOY_ARM_LOCKED":
                    "wing deploy TRANSIT unauthorised (G2)",
                "DEPLOYED_NOMINAL": "",
                "L_FAIL": "off-nominal, arm remains restrained",
                "R_FAIL": "off-nominal, arm remains restrained",
                "DEPLOY_FAILED_BOTH": "off-nominal, arm remains restrained",
                "PARTIAL": "REGISTERED_NOT_GEOMETRICALLY_DIFFERENTIATED",
                "SERVICE": "PENDING_RATIFICATION_HOLD (G2)"}.get(c, ""),
        })
    n = C.write_csv(OUT, rows)
    print("rows:", n, "->", OUT)
    for r in rows:
        print("  %-30s comps=%-3s mates=%s/%s  offline_real=%-2s min=%-9s "
              "native=%-8s %s"
              % (r["configuration"], r["f3r2_components"],
                 r["f3r2_mate_errors"], r["f3r2_mates_total"],
                 r["offline_interference_or_too_close"],
                 r["offline_min_gap_mm"], r["native_pairs"],
                 r["f3r2_hold"][:34]))
    sys.exit(0)


if __name__ == "__main__":
    main()
