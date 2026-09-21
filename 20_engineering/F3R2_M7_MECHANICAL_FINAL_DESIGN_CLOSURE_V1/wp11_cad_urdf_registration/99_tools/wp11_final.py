# -*- coding: utf-8 -*-
"""WP11 final closing measurements.

(a) post-D_i, partition-tolerant residual per link (CAD link i vs the URDF
    union {i-1, i, i+1}, plus the gripper group for link6) -- the number that
    actually answers "does the CAD arm coincide with the accepted-URDF arm".
(b) post-D_i whole-arm aggregate residual in the assembly frame at q0.
(c) axis-wise observability of each D_i: how much can t move along each axis
    before p95 degrades?  Long prismatic links are weakly observable along
    their prism axis and that must be stated, not hidden.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wp11_lib import (  # noqa: E402
    REPO, T, TriDist, apply_T, inv_T, sample_surface, stats,
)
from wp11_analysis import (  # noqa: E402
    ARM_LINKS, OUT, Q0, T_MOUNT_M7, dedup_tri, load_cad, load_urdf_mesh, _u,
)


def main():
    u = _u()
    fk0 = u.fk(Q0, T_MOUNT_M7)
    CO = json.load(open(os.path.join(OUT, "CLOSEOUT.json"), encoding="utf-8"))
    RF = json.load(open(os.path.join(OUT, "REFINE.json"), encoding="utf-8"))
    D = {}
    for k in ARM_LINKS:
        if k in CO["links"]:
            D[k] = np.array(CO["links"][k]["best_translation_only_D_i_mm"])
        else:
            D[k] = np.array(RF["links"][k]["M1_translation_only_D_i_mm"])
    out = {
        "schema": "WP11_FINAL_V1",
        "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "D_i_translation_mm_used": {k: v.tolist() for k, v in D.items()},
    }

    # ---- (a) post-D_i partition-tolerant per link
    per = {}
    N = 15000
    for k in ARM_LINKS:
        t0 = time.time()
        tri_c = dedup_tri(
            apply_T(inv_T(fk0[k]) , load_cad(k, "DEPLOYED")[0].reshape(-1, 3)
                    ).reshape(-1, 3, 3)
        )
        tri_c = apply_T(T(None, D[k]), tri_c.reshape(-1, 3)).reshape(-1, 3, 3)
        i = ARM_LINKS.index(k)
        nb = [ARM_LINKS[j] for j in (i - 1, i, i + 1) if 0 <= j < len(ARM_LINKS)]
        if k == "link6":
            nb += ["gripper_link", "gripper_left", "gripper_right"]
        parts = []
        for m in nb:
            tm = load_urdf_mesh(m)[0]
            parts.append(
                apply_T(inv_T(fk0[k]) @ fk0[m], tm.reshape(-1, 3)).reshape(-1, 3, 3)
            )
        st = stats(TriDist(np.concatenate(parts, 0)).query(sample_surface(tri_c, N, 71)))
        per[k] = {"neighbourhood": nb, "residual_cad_to_urdf_union": st}
        print("%-10s post-D_i nbhd med %.5f p95 %.5f p99 %.5f max %.4f f<=0.5 %.4f "
              "(%.0fs)" % (k, st["median_mm"], st["p95_mm"], st["p99_mm"],
                           st["max_mm"], st["frac_le_0p5mm"], time.time() - t0))
    out["post_D_i_partition_tolerant_per_link"] = per

    # ---- (b) post-D_i whole-arm aggregate (assembly frame, q0)
    t0 = time.time()
    cad, urdf = [], []
    for k in ARM_LINKS:
        tri = dedup_tri(load_cad(k, "DEPLOYED")[0])
        # D_i lives in the link frame: assembly -> link -> +D -> assembly
        M = fk0[k] @ T(None, D[k]) @ inv_T(fk0[k])
        cad.append(apply_T(M, tri.reshape(-1, 3)).reshape(-1, 3, 3))
    cad.append(dedup_tri(load_cad("gripper_detail", "DEPLOYED")[0]))
    for k in ARM_LINKS + ["gripper_link", "gripper_left", "gripper_right"]:
        tm = load_urdf_mesh(k)[0]
        urdf.append(apply_T(fk0[k], tm.reshape(-1, 3)).reshape(-1, 3, 3))
    CA = np.concatenate(cad, 0)
    UA = np.concatenate(urdf, 0)
    a1 = stats(TriDist(UA).query(sample_surface(CA, 25000, 72)))
    a2 = stats(TriDist(CA).query(sample_surface(UA, 25000, 73)))
    out["post_D_i_whole_arm_aggregate_q0"] = {
        "residual_cad_to_urdf": a1, "residual_urdf_to_cad": a2,
        "seconds": round(time.time() - t0, 1),
    }
    print("AGGREGATE post-D_i cad->urdf med %.5f p95 %.5f p99 %.5f max %.4f "
          "f<=0.5 %.4f | urdf->cad med %.5f p95 %.5f f<=0.5 %.4f (%.0fs)"
          % (a1["median_mm"], a1["p95_mm"], a1["p99_mm"], a1["max_mm"],
             a1["frac_le_0p5mm"], a2["median_mm"], a2["p95_mm"],
             a2["frac_le_0p5mm"], time.time() - t0))

    # ---- (c) axis-wise observability of D_i
    obs = {}
    for k in ARM_LINKS:
        t0 = time.time()
        tri_c0 = dedup_tri(
            apply_T(inv_T(fk0[k]), load_cad(k, "DEPLOYED")[0].reshape(-1, 3)
                    ).reshape(-1, 3, 3)
        )
        tri_u = load_urdf_mesh(k)[0]
        td = TriDist(tri_u)
        Sc = sample_surface(tri_c0, 3000, 74)
        base = stats(td.query(Sc + D[k]))["p95_mm"]
        tol = max(1.5 * base, base + 0.05)
        ent = {"baseline_p95_mm": base, "degradation_threshold_p95_mm": tol,
               "sweep_points": 3000, "sweep_range_mm": [-4.0, 4.0],
               "sweep_step_mm": 0.5}
        for ax in range(3):
            span = []
            for s in np.arange(-4.0, 4.001, 0.5):
                dd = D[k].copy()
                dd[ax] += s
                if stats(td.query(Sc + dd))["p95_mm"] <= tol:
                    span.append(s)
            ent["axis_%d_admissible_offset_mm" % ax] = (
                [float(min(span)), float(max(span))] if span else None
            )
        obs[k] = ent
        print("%-10s observability axes: %s %s %s (%.0fs)"
              % (k, ent["axis_0_admissible_offset_mm"],
                 ent["axis_1_admissible_offset_mm"],
                 ent["axis_2_admissible_offset_mm"], time.time() - t0))
    out["D_i_axis_observability"] = obs
    json.dump(out, open(os.path.join(OUT, "FINAL.json"), "w"), indent=1)
    print("FINAL written")


if __name__ == "__main__":
    main()
