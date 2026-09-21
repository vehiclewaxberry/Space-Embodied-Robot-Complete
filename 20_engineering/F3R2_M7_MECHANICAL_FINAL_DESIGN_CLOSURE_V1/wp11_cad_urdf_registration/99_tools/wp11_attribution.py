# -*- coding: utf-8 -*-
"""WP11 attribution stage: explain every non-coincident region by name.

A residual is only admissible as "explained" if it can be attributed to a named,
hash-bound decision or to a named link-content partition boundary.  Anything
left over is reported as UNEXPLAINED, never absorbed into a tolerance.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wp11_lib import (  # noqa: E402
    REPO, TriDist, apply_T, inv_T, mesh_volume_and_area, sample_surface, stats,
)
from wp11_analysis import (  # noqa: E402
    ARM_LINKS, OUT, Q0, T_MOUNT_M7, dedup_tri, load_cad, load_urdf_mesh, _u,
)

# owner-ruled deletion, design/base_classification.json ("用户裁决表 2026-07-27")
PLATE_VENDOR_BBOX = [[-70.0, -100.0, 3.3], [70.0, 100.0, 17.8]]
G06_R = np.diag([-1.0, -1.0, 1.0])
G06_T = np.array([0.085, -0.022, -3.395])


def plate_box_in_link_frame():
    lo = np.array(PLATE_VENDOR_BBOX[0])
    hi = np.array(PLATE_VENDOR_BBOX[1])
    corners = np.array(
        [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    )
    p = corners @ G06_R.T + G06_T
    return p.min(0), p.max(0)


def main():
    u = _u()
    fk0 = u.fk(Q0, T_MOUNT_M7)
    res = {
        "schema": "WP11_ATTRIBUTION_V1",
        "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
    }

    # ---------- 1. base_link: is the extra URDF material the deleted base plate?
    tri_c, _, _ = load_cad("base_link", "DEPLOYED")
    tri_c = apply_T(inv_T(fk0["base_link"]), tri_c.reshape(-1, 3)).reshape(-1, 3, 3)
    tri_u, _, _ = load_urdf_mesh("base_link")
    N = 40000
    Su = sample_surface(tri_u, N, 41)
    td = TriDist(dedup_tri(tri_c))
    d = td.query(Su)
    lo, hi = plate_box_in_link_frame()
    inside = np.all((Su >= lo - 1e-9) & (Su <= hi + 1e-9), axis=1)
    far = d > 1.0
    res["base_link_extra_material_attribution"] = {
        "hypothesis": (
            "the URDF base_link collision mesh still carries the vendor "
            "01_BASE_Plate (desktop base plate) that the owner ruling of "
            "2026-07-27 deleted from the flight-side CAD"
        ),
        "ruling_source": (
            "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
            "130_B601_Vendor_CAD_Direct_Integration_03/design/"
            "base_classification.json  (deleted: 01_BASE_Plate, criterion "
            "z_max<18mm vendor world)"
        ),
        "deleted_plate_bbox_vendor_mm": PLATE_VENDOR_BBOX,
        "deleted_plate_bbox_in_urdf_base_link_frame_mm": [lo.tolist(), hi.tolist()],
        "urdf_surface_samples": int(N),
        "samples_farther_than_1mm_from_cad": int(far.sum()),
        "fraction_of_urdf_surface_farther_than_1mm": float(far.mean()),
        "of_those_fraction_inside_deleted_plate_box": float(
            inside[far].mean() if far.sum() else float("nan")
        ),
        "unexplained_far_samples_outside_plate_box": int((far & ~inside).sum()),
        "unexplained_fraction_of_urdf_surface": float((far & ~inside).mean()),
        "residual_stats_urdf_to_cad_all": stats(d),
        "residual_stats_urdf_to_cad_excluding_plate_box": stats(d[~inside]),
    }
    print("base_link: far frac %.4f, of those inside plate box %.4f, unexplained %d"
          % (far.mean(), inside[far].mean(), (far & ~inside).sum()))

    # ---------- 2. wrist: link6 / gripper_link content-partition boundary
    cad_w = [dedup_tri(load_cad("link6", "DEPLOYED")[0]),
             dedup_tri(load_cad("gripper_detail", "DEPLOYED")[0])]
    urdf_w = []
    for m in ("link6", "gripper_link", "gripper_left", "gripper_right"):
        t, _, _ = load_urdf_mesh(m)
        urdf_w.append(apply_T(fk0[m], t.reshape(-1, 3)).reshape(-1, 3, 3))
    CW = np.concatenate(cad_w, 0)
    UW = np.concatenate(urdf_w, 0)
    n = 25000
    a = stats(TriDist(UW).query(sample_surface(CW, n, 42)))
    b = stats(TriDist(CW).query(sample_surface(UW, n, 43)))
    # and link6 alone against the URDF link6+gripper_link union (no fingers)
    U6 = np.concatenate(urdf_w[:2], 0)
    c = stats(TriDist(U6).query(sample_surface(cad_w[0], n, 44)))
    Vc6, _ = mesh_volume_and_area(load_cad("link6", "DEPLOYED")[0])
    Vcg, _ = mesh_volume_and_area(load_cad("gripper_detail", "DEPLOYED")[0])
    Vu6, _ = mesh_volume_and_area(urdf_w[0])
    Vug, _ = mesh_volume_and_area(np.concatenate(urdf_w[1:], 0))
    res["wrist_partition_attribution"] = {
        "hypothesis": (
            "the accepted URDF assigns the wrist housing to gripper_link and "
            "keeps only the ~9.5 mm tool flange disc in link6, while the vendor "
            "CAD group Link6:1 carries the whole wrist housing; this is a "
            "link-content partition boundary, not a geometry version difference"
        ),
        "prior_registration_note": (
            "B5_0 G05/G08 receipts: method CHAIN_DERIVED, note 'direct 配准不"
            "可靠（内容划分/开度差异）；链推导锁定' -- the same boundary was hit "
            "in 2026-07 and resolved by chain derivation, direct_nn 16.408 mm "
            "(link6) / 8.446 mm (gripper_link)"
        ),
        "cad_link6_single_shell_volume_mm3": Vc6 / 2.0,
        "cad_gripper_detail_single_shell_volume_mm3": Vcg / 2.0,
        "cad_wrist_total_single_shell_volume_mm3": (Vc6 + Vcg) / 2.0,
        "urdf_link6_volume_mm3": Vu6,
        "urdf_gripper_group_volume_mm3": Vug,
        "urdf_wrist_total_volume_mm3": Vu6 + Vug,
        "wrist_total_volume_ratio_cad_over_urdf": ((Vc6 + Vcg) / 2.0) / (Vu6 + Vug),
        "residual_cad_wrist_to_urdf_wrist": a,
        "residual_urdf_wrist_to_cad_wrist": b,
        "residual_cad_link6_alone_to_urdf_link6_plus_gripper_link": c,
        "note_gripper_r1_supersedes": (
            "ODR-04: the flight gripper is the neutral R1 design, not the vendor "
            "gripper; the CAD gripper_detail here is the LEGACY vendor gripper "
            "kept only as the wrist-partition witness (M5 marks it "
            "SUPERSEDED_FOR_ACTIVE_GRIPPER_GEOMETRY_BY_R1_SEPARATED_PALM_AND_"
            "FINGERS).  Gripper shape agreement is therefore NOT claimed."
        ),
    }
    print("wrist: cad->urdf med %.4f p95 %.4f | urdf->cad med %.4f p95 %.4f | "
          "link6 alone vs l6+gl med %.4f p95 %.4f | vol ratio %.4f"
          % (a["median_mm"], a["p95_mm"], b["median_mm"], b["p95_mm"],
             c["median_mm"], c["p95_mm"],
             res["wrist_partition_attribution"]["wrist_total_volume_ratio_cad_over_urdf"]))

    # ---------- 3. link1: localise the 3.9 mm plateau
    tri_c1 = dedup_tri(
        apply_T(inv_T(fk0["link1"]),
                load_cad("link1", "DEPLOYED")[0].reshape(-1, 3)).reshape(-1, 3, 3)
    )
    tri_u1, _, _ = load_urdf_mesh("link1")
    S = sample_surface(tri_c1, 40000, 45)
    d1 = TriDist(tri_u1).query(S)
    hot = d1 > 2.0
    ent = {
        "cad_surface_samples": 40000,
        "fraction_farther_than_2mm": float(hot.mean()),
        "plateau_distance_mm_p50_of_hot": float(np.median(d1[hot])) if hot.any() else None,
        "hot_region_bbox_link_frame_mm": (
            [S[hot].min(0).tolist(), S[hot].max(0).tolist()] if hot.any() else None
        ),
        "cad_link1_bbox_link_frame_mm": [
            tri_c1.reshape(-1, 3).min(0).tolist(), tri_c1.reshape(-1, 3).max(0).tolist()
        ],
        "urdf_link1_bbox_link_frame_mm": [
            tri_u1.reshape(-1, 3).min(0).tolist(), tri_u1.reshape(-1, 3).max(0).tolist()
        ],
    }
    # is the plateau inside the neighbouring links' URDF envelope?
    nbt = []
    for m in ("base_link", "link2"):
        t, _, _ = load_urdf_mesh(m)
        nbt.append(apply_T(inv_T(fk0["link1"]) @ fk0[m], t.reshape(-1, 3)).reshape(-1, 3, 3))
    dn = TriDist(np.concatenate(nbt, 0)).query(S[hot]) if hot.any() else np.array([])
    ent["hot_samples_distance_to_urdf_base_link_plus_link2"] = (
        stats(dn) if dn.size else None
    )
    res["link1_plateau_attribution"] = ent
    print("link1 plateau: frac>2mm %.4f  median %.4f  dist to URDF nbrs med %.4f"
          % (hot.mean(), np.median(d1[hot]) if hot.any() else float("nan"),
             np.median(dn) if dn.size else float("nan")))

    json.dump(res, open(os.path.join(OUT, "ATTRIBUTION.json"), "w"), indent=1)
    print("ATTRIBUTION written")


if __name__ == "__main__":
    main()
