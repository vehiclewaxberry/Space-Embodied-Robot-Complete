# -*- coding: utf-8 -*-
"""WP11 refine stage: is D_i a pure translation, and does it reproduce the
independent 2026-07 VENDORCAD03 registration?

Free-rigid ICP on a near-perfect match absorbs fit noise into a spurious small
rotation, so the "pure translation" claim must be tested by *constraining* the
model, not by reading the free fit's rotation angle.  Three models per link:
    M0  D = I
    M1  D = translation only  (rotation locked to identity)
    M2  D = full rigid        (from the testa stage)
If M1 reaches M2's residual, D_i is a translation.
"""
import json
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wp11_lib import (  # noqa: E402
    REPO, T, TriDist, apply_T, inv_T, sample_surface, stats,
)
from wp11_analysis import (  # noqa: E402
    ARM_LINKS, OUT, Q0, T_MOUNT_M7, dedup_tri, load_cad, load_urdf_mesh, _u,
)

# 2026-07 VENDORCAD03 per-group translation deviation from the single common
# vendor->URDF datum transform (design/group_link_transforms.json)
PRIOR_DEV_MM = {
    "link1": 3.943, "link2": 0.225, "link3": 1.14, "link4": 2.214,
    "base_link": 0.072, "link5": 1.609,
}
PRIOR_DIRECT_NN_MM = {
    "link1": 2.5, "link2": 1.959, "link3": 2.23, "link4": 2.201,
    "link5": 1.907, "base_link": 1.573, "link6": 16.408,
}


def trans_only_icp(src, tree, dst, iters=60, trim=0.7):
    """ICP with rotation locked to identity: iterate t <- mean(dst_nn - src)."""
    t = np.zeros(3)
    for _ in range(iters):
        moved = src + t
        d, idx = tree.query(moved, k=1, workers=-1)
        keep = d <= np.quantile(d, trim)
        dt = (dst[idx[keep]] - moved[keep]).mean(0)
        t = t + dt
        if np.linalg.norm(dt) < 1e-10:
            break
    return T(None, t)


def main():
    u = _u()
    fk0 = u.fk(Q0, T_MOUNT_M7)
    ta = json.load(open(os.path.join(OUT, "TESTA.json"), encoding="utf-8"))
    N = 15000
    out = {
        "schema": "WP11_REFINE_V1",
        "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "links": {},
    }
    for k in ARM_LINKS:
        t0 = time.time()
        tri_c = dedup_tri(
            apply_T(inv_T(fk0[k]), load_cad(k, "DEPLOYED")[0].reshape(-1, 3)
                    ).reshape(-1, 3, 3)
        )
        tri_u = load_urdf_mesh(k)[0]
        Sc = sample_surface(tri_c, N, 51)
        Su = sample_surface(tri_u, N, 52)
        # for a subset relationship, fit in the direction where the SMALLER
        # surface is the moving set, so the fit is not dragged by unshared
        # material: link6 (URDF subset of CAD) and base_link (CAD subset of URDF)
        if k == "link6":
            M1inv = trans_only_icp(Su, cKDTree(Sc), Sc, trim=0.8)
            M1 = inv_T(M1inv)                      # CAD -> URDF link frame
        else:
            M1 = trans_only_icp(Sc, cKDTree(Su), Su, trim=0.7)
        tdU = TriDist(tri_u)
        r0 = stats(tdU.query(Sc))
        r1 = stats(tdU.query(apply_T(M1, Sc)))
        M2 = np.array(ta["links"][k]["D_i_best_fit_rows"])
        r2 = stats(tdU.query(apply_T(M2, Sc)))
        # reverse direction under M1
        tri_c1 = apply_T(M1, tri_c.reshape(-1, 3)).reshape(-1, 3, 3)
        r1r = stats(TriDist(tri_c1).query(Su))
        ent = {
            "M0_identity_residual_cad_to_urdf": r0,
            "M1_translation_only_D_i_mm": M1[:3, 3].tolist(),
            "M1_translation_norm_mm": float(np.linalg.norm(M1[:3, 3])),
            "M1_residual_cad_to_urdf": r1,
            "M1_residual_urdf_to_cad": r1r,
            "M2_full_rigid_residual_cad_to_urdf": r2,
            "M2_full_rigid_rotation_deg": ta["links"][k]["D_i_rotation_angle_deg"],
            "M2_full_rigid_translation_norm_mm": ta["links"][k][
                "D_i_translation_norm_mm"
            ],
            "translation_only_reaches_full_rigid": bool(
                r1["median_mm"] <= r2["median_mm"] * 1.5 + 0.01
            ),
            "prior_2026_07_vendorcad03_translation_dev_mm": PRIOR_DEV_MM.get(k),
            "prior_2026_07_direct_nn_mm": PRIOR_DIRECT_NN_MM.get(k),
            "independent_reproduction_delta_mm": (
                None if PRIOR_DEV_MM.get(k) is None
                else abs(float(np.linalg.norm(M1[:3, 3])) - PRIOR_DEV_MM[k])
            ),
            "seconds": round(time.time() - t0, 1),
        }
        out["links"][k] = ent
        print("%-10s M0 med %.4f | M1(t only, |t|=%.4f) med %.4f p95 %.4f rev %.4f | "
              "M2(full) med %.4f rot %.3f deg | prior_dev %s delta %s"
              % (k, r0["median_mm"], ent["M1_translation_norm_mm"], r1["median_mm"],
                 r1["p95_mm"], r1r["median_mm"], r2["median_mm"],
                 ent["M2_full_rigid_rotation_deg"],
                 PRIOR_DEV_MM.get(k), ent["independent_reproduction_delta_mm"]))
    json.dump(out, open(os.path.join(OUT, "REFINE.json"), "w"), indent=1)
    print("REFINE written")


if __name__ == "__main__":
    main()
