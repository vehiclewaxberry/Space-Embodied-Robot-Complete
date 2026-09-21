# -*- coding: utf-8 -*-
"""WP11 closeout measurements:
  1. link1 translation-only D_i re-fit from multiple initialisations (the
     trim=0.7 mean-shift fit converged to a local minimum at |t|=1.3681 mm).
  2. rotation-necessity test: residual at (I, t_M2) vs full rigid M2.
  3. base_link: characterise the samples NOT explained by the deleted plate.
  4. link6 subset residual percentiles under its translation-only D_i.
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
from wp11_refine import trans_only_icp  # noqa: E402
from wp11_attribution import plate_box_in_link_frame  # noqa: E402


def main():
    u = _u()
    fk0 = u.fk(Q0, T_MOUNT_M7)
    ta = json.load(open(os.path.join(OUT, "TESTA.json"), encoding="utf-8"))
    rf = json.load(open(os.path.join(OUT, "REFINE.json"), encoding="utf-8"))
    out = {
        "schema": "WP11_CLOSEOUT_V1",
        "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    }
    N = 15000

    # ---- 1/2. link1 multi-start translation-only fit + rotation necessity
    lk = {}
    for k in ("link1", "base_link", "link2", "link3", "link4", "link5"):
        tri_c = dedup_tri(
            apply_T(inv_T(fk0[k]), load_cad(k, "DEPLOYED")[0].reshape(-1, 3)
                    ).reshape(-1, 3, 3)
        )
        tri_u = load_urdf_mesh(k)[0]
        Sc = sample_surface(tri_c, N, 61)
        Su = sample_surface(tri_u, N, 62)
        tree = cKDTree(Su)
        tdU = TriDist(tri_u)
        M2 = np.array(ta["links"][k]["D_i_best_fit_rows"])
        starts = {
            "zero": np.zeros(3),
            "from_M2_translation": M2[:3, 3].copy(),
            "bbox_center_delta": Su.mean(0) - Sc.mean(0),
        }
        best = None
        cand = {}
        for tag, t0v in starts.items():
            for tr in (0.5, 0.7, 0.9):
                Mt = T(None, t0v.copy())
                # mean-shift from the given start
                t = t0v.copy()
                for _ in range(80):
                    moved = Sc + t
                    d, idx = tree.query(moved, k=1, workers=-1)
                    keep = d <= np.quantile(d, tr)
                    dt = (Su[idx[keep]] - moved[keep]).mean(0)
                    t = t + dt
                    if np.linalg.norm(dt) < 1e-10:
                        break
                Mt = T(None, t)
                st = stats(tdU.query(apply_T(Mt, Sc)))
                cand["%s_trim%.1f" % (tag, tr)] = {
                    "t_mm": t.tolist(),
                    "norm_mm": float(np.linalg.norm(t)),
                    "median_mm": st["median_mm"],
                    "p95_mm": st["p95_mm"],
                }
                if best is None or st["median_mm"] < best[0]:
                    best = (st["median_mm"], t.copy(), st)
        t_best = best[1]
        st_best = best[2]
        # rotation-necessity: same translation as M2, rotation dropped
        st_norot = stats(tdU.query(apply_T(T(None, M2[:3, 3]), Sc)))
        st_full = stats(tdU.query(apply_T(M2, Sc)))
        tri_c_b = apply_T(T(None, t_best), tri_c.reshape(-1, 3)).reshape(-1, 3, 3)
        st_rev = stats(TriDist(tri_c_b).query(Su))
        lk[k] = {
            "candidates": cand,
            "best_translation_only_D_i_mm": t_best.tolist(),
            "best_translation_only_norm_mm": float(np.linalg.norm(t_best)),
            "best_residual_cad_to_urdf": st_best,
            "best_residual_urdf_to_cad": st_rev,
            "residual_with_M2_translation_rotation_dropped": st_norot,
            "residual_full_rigid_M2": st_full,
            "rotation_is_necessary": bool(
                st_full["median_mm"] < 0.5 * st_norot["median_mm"]
            ),
            "prior_2026_07_translation_dev_mm":
                rf["links"][k]["prior_2026_07_vendorcad03_translation_dev_mm"],
        }
        print("%-10s best |t|=%.4f med %.5f p95 %.5f rev %.5f | noRot(M2 t) med %.5f "
              "| fullM2 med %.5f | rot needed=%s | prior %s"
              % (k, np.linalg.norm(t_best), st_best["median_mm"], st_best["p95_mm"],
                 st_rev["median_mm"], st_norot["median_mm"], st_full["median_mm"],
                 lk[k]["rotation_is_necessary"],
                 lk[k]["prior_2026_07_translation_dev_mm"]))
    out["links"] = lk

    # ---- 3. base_link unexplained samples
    tri_c = dedup_tri(
        apply_T(inv_T(fk0["base_link"]),
                load_cad("base_link", "DEPLOYED")[0].reshape(-1, 3)).reshape(-1, 3, 3)
    )
    tri_u = load_urdf_mesh("base_link")[0]
    Su = sample_surface(tri_u, 40000, 63)
    d = TriDist(tri_c).query(Su)
    lo, hi = plate_box_in_link_frame()
    far = d > 1.0
    for pad in (0.0, 0.5, 2.0, 5.0):
        ins = np.all((Su >= lo - pad) & (Su <= hi + pad), axis=1)
        out.setdefault("base_link_unexplained", {})["explained_fraction_pad_%.1fmm" % pad] = (
            float(ins[far].mean())
        )
    ins0 = np.all((Su >= lo) & (Su <= hi), axis=1)
    rest = Su[far & ~ins0]
    out["base_link_unexplained"].update(
        {
            "far_sample_count": int(far.sum()),
            "far_fraction_of_urdf_surface": float(far.mean()),
            "unexplained_count_pad0": int((far & ~ins0).sum()),
            "unexplained_fraction_of_urdf_surface_pad0": float((far & ~ins0).mean()),
            "unexplained_bbox_link_frame_mm": (
                [rest.min(0).tolist(), rest.max(0).tolist()] if len(rest) else None
            ),
            "unexplained_distance_stats": stats(d[far & ~ins0]) if len(rest) else None,
            "unexplained_z_percentiles_mm": (
                np.percentile(rest[:, 2], [0, 25, 50, 75, 100]).tolist()
                if len(rest) else None
            ),
            "deleted_plate_box_link_frame_mm": [lo.tolist(), hi.tolist()],
        }
    )
    print("base_link unexplained: pad0 %.4f pad0.5 %.4f pad2 %.4f pad5 %.4f  n=%d"
          % (out["base_link_unexplained"]["explained_fraction_pad_0.0mm"],
             out["base_link_unexplained"]["explained_fraction_pad_0.5mm"],
             out["base_link_unexplained"]["explained_fraction_pad_2.0mm"],
             out["base_link_unexplained"]["explained_fraction_pad_5.0mm"],
             int((far & ~ins0).sum())))

    # ---- 4. link6 subset residual under its translation-only D_i
    tri_c6 = dedup_tri(
        apply_T(inv_T(fk0["link6"]),
                load_cad("link6", "DEPLOYED")[0].reshape(-1, 3)).reshape(-1, 3, 3)
    )
    tri_u6 = load_urdf_mesh("link6")[0]
    t6 = np.array(rf["links"]["link6"]["M1_translation_only_D_i_mm"])
    tri_c6b = apply_T(T(None, t6), tri_c6.reshape(-1, 3)).reshape(-1, 3, 3)
    Su6 = sample_surface(tri_u6, 25000, 64)
    st6 = stats(TriDist(tri_c6b).query(Su6))
    out["link6_subset_containment"] = {
        "direction": "URDF_link6_collision_disc -> CAD_link6_wrist_body",
        "D_i_translation_only_mm": t6.tolist(),
        "D_i_norm_mm": float(np.linalg.norm(t6)),
        "residual": st6,
        "interpretation": (
            "the accepted-URDF link6 collision mesh is a geometric SUBSET of "
            "the CAD link6 wrist body; containment, not divergence"
        ),
    }
    print("link6 URDF->CAD med %.5f p95 %.5f p99 %.5f max %.4f frac<=0.5mm %.4f"
          % (st6["median_mm"], st6["p95_mm"], st6["p99_mm"], st6["max_mm"],
             st6["frac_le_0p5mm"]))

    json.dump(out, open(os.path.join(OUT, "CLOSEOUT.json"), "w"), indent=1)
    print("CLOSEOUT written")


if __name__ == "__main__":
    main()
