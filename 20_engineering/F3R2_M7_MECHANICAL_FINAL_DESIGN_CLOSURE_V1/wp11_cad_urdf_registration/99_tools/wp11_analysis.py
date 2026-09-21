# -*- coding: utf-8 -*-
"""WP11 -- CAD vs accepted-URDF registration adjudication (ODR-09 / ODR-10).

Stages (argv[1]):
    inputs   -> 10_intermediate/INPUTS.json          (source register, hashes)
    testa    -> 10_intermediate/TESTA.json           (zero-pose rigid registration)
    testb    -> 10_intermediate/TESTB.json           (multi-configuration)

Nothing here launches FreeCAD or SolidWorks.  STEP is read as text only.
All lengths in mm unless a name says otherwise.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wp11_lib import (  # noqa: E402
    REPO, Urdf, TriDist, apply_T, inv_T, T, icp, kabsch, mesh_volume_and_area,
    pca_extents, read_binary_stl, read_ply, sample_surface, sha256_and_size,
    sha256_lf_normalised, stats, OCT24, R_to_axis_angle,
)

OUT = os.path.join(os.path.dirname(HERE), "10_intermediate")
os.makedirs(OUT, exist_ok=True)

URDF_DIR = os.path.join(REPO, "20_engineering/cad/spacecraft_layout/arm_b601_v1")
URDF_PATH = os.path.join(URDF_DIR, "arm_b601_v1.urdf")
MESH_URDF = os.path.join(URDF_DIR, "meshes_b601_gripper")
CAD_DIR = os.path.join(
    REPO, "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/05_clearance/mesh"
)
M5_DEC = os.path.join(
    REPO,
    "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
    "01_geometry_authority/B601_CAD_MESH_FRAME_DECISION_V1.json",
)
WP1_REP = os.path.join(
    REPO,
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json",
)

ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]
CAD_PART = {k: "B51_REF_%s_LINKLOCAL.stl" % k for k in ARM_LINKS}
CAD_PART["gripper_detail"] = "B51_REF_gripper_detail_LINKLOCAL.stl"

# ODR-01 / WP1 M7 authority mount (T_S_B601_ARM_BASE), station x = 208.0 mm
T_MOUNT_M7 = np.array(
    [
        [0.0, 0.0, 1.0, 208.0],
        [0.422618483193, 0.906307683772, 0.0, 0.0],
        [-0.906307683772, 0.422618483193, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)
# F3R1 mount actually used to build/pose the CAD arm (sin/cos 25 deg exact)
T_MOUNT_F3R1 = np.array(
    [
        [0.0, 0.0, 1.0, 208.0],
        [0.422618261741, 0.906307787037, 0.0, 0.0],
        [-0.906307787037, 0.422618261741, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
)

Q0 = [0.0] * 6
Q_STOW = [np.deg2rad(v) for v in [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]]
Q_TASK_READY = [-1.570796, -1.047198, -2.094395, -0.523599, 0.0, 0.0]   # C06
Q_INTERMEDIATE = [                                                       # C07 PREGRASP
    -1.4722592995215e-05, -1.0482002296028672, -1.3989828152470143,
    -1.220010067943876, 3.673218594813444e-06, 1.8395811591278994e-05,
]
Q_DEPLOYED_HOME = [-1.570796, -2.094395, -1.047198, 0.0, -0.523599, 0.0]  # C01

TESS_DEFLECTION_MM = 0.5   # declared source tessellation linear deflection (M5)
COINCIDENCE_MM = 1.0       # 2 x tessellation deflection


def _u():
    return Urdf(URDF_PATH)


def limits(u):
    lo, hi = [], []
    for j in u.joints[:6]:
        lo.append(j["lower"])
        hi.append(j["upper"])
    return lo, hi


def load_cad(part, config="DEPLOYED"):
    p = os.path.join(CAD_DIR, "parts_" + config, CAD_PART[part])
    tri, n = read_binary_stl(p)
    return tri, n, p


def load_urdf_mesh(link):
    p = os.path.join(MESH_URDF, "%s.STL" % link)
    tri, n = read_binary_stl(p, scale=1000.0)
    return tri, n, p


def dedup_tri(tri, decimals=4):
    """Drop exact duplicate triangles (the CAD export writes a doubled shell)."""
    key = np.sort(np.round(tri, decimals), axis=1).reshape(len(tri), 9)
    _, idx = np.unique(key, axis=0, return_index=True)
    return tri[np.sort(idx)]


# ---------------------------------------------------------------- stage: inputs
def stage_inputs():
    reg = []

    def add(path, role, extra=None):
        ap = path if os.path.isabs(path) else os.path.join(REPO, path)
        sha, n = sha256_and_size(ap)
        rel = os.path.relpath(ap, REPO).replace("\\", "/")
        row = {"path": rel, "bytes": n, "sha256": sha, "role": role}
        if extra:
            row.update(extra)
        reg.append(row)
        return row

    # accepted URDF: all copies, CRLF-normalised comparison
    urdf_copies = [
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/"
        "00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf",
        "20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/"
        "00_BASELINE/PARENT_LOCKED_INPUTS/ACCEPTED_URDF/arm_b601_v1.urdf",
        "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820/06_pack_and_go/"
        "V5R_NEUTRAL_OPERATIONAL_PACKAGE/urdf/arm_b601_v1.urdf",
    ]
    ucheck = []
    for c in urdf_copies:
        raw_sha, raw_n, lf_sha, lf_n = sha256_lf_normalised(os.path.join(REPO, c))
        ucheck.append(
            {
                "path": c,
                "bytes_on_disk": raw_n,
                "sha256_on_disk": raw_sha,
                "bytes_lf_normalised": lf_n,
                "sha256_lf_normalised": lf_sha,
            }
        )
        add(c, "ACCEPTED_URDF_COPY")
    for k in ARM_LINKS + ["gripper_link", "gripper_left", "gripper_right"]:
        add(os.path.join(MESH_URDF, "%s.STL" % k), "ACCEPTED_URDF_COLLISION_MESH")
    for cfg in ("DEPLOYED", "STOWED"):
        for k in list(ARM_LINKS) + ["gripper_detail"]:
            add(
                os.path.join(CAD_DIR, "parts_" + cfg, CAD_PART[k]),
                "CAD_ARM_PART_MESH_%s" % cfg,
            )
    add(M5_DEC, "M5_CAD_MESH_FRAME_DECISION")
    add(WP1_REP, "M7_WP1_DESIGN_FREEZE_BUILD_REPORT")
    add(
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
        "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step",
        "M7_DESIGN_FREEZE_STEP",
    )
    add(
        "20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/"
        "03_native_cad/F3R1_TOP_INTEGRATION_REPORT.json",
        "CAD_ARM_MOUNT_TRANSFORM_SOURCE",
    )
    add(
        "20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/"
        "99_tools/p4_stow_pose.py",
        "CAD_ARM_STOW_POSE_WRITER_PROVENANCE",
    )
    add(
        "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/99_tools/r2_kin.py",
        "OFFLINE_URDF_FK_CONSUMER_PROVENANCE",
    )
    for g in ["G01", "G02", "G03", "G04", "G05", "G06", "G07", "G08"]:
        add(
            "20_engineering/cad/B5_0_B601_space_manipulator_candidate/02_DESIGN/"
            "vendor_reference_linklocal/evidence/%s_receipt.json" % g,
            "PRIOR_VENDOR_TO_URDF_LINK_REGISTRATION_RECEIPT",
        )

    u = _u()
    lo, hi = limits(u)
    topo = {
        "robot_name": u.name,
        "link_count": len(u.links),
        "joint_count": len(u.joints),
        "links": u.links,
        "joints": [
            {
                "name": j["name"], "type": j["type"], "parent": j["parent"],
                "child": j["child"], "origin_xyz_mm": [x * 1000.0 for x in j["xyz_m"]],
                "origin_rpy_rad": j["rpy"], "axis": j["axis"],
                "lower": j["lower"], "upper": j["upper"],
            }
            for j in u.joints
        ],
        "revolute_count": sum(1 for j in u.joints if j["type"] == "revolute"),
        "prismatic_count": sum(1 for j in u.joints if j["type"] == "prismatic"),
        "fixed_count": sum(1 for j in u.joints if j["type"] == "fixed"),
        "urdf_inertial_mass_sum_kg": float(
            sum(v["mass"] for v in u.inertial.values())
        ),
        "pinned_l0_arm_mass_kg": 4.695555949342986,
        "joint_lower_limits_rad": lo,
        "joint_upper_limits_rad": hi,
    }
    topo["urdf_mass_sum_matches_pinned_l0_exactly"] = (
        topo["urdf_inertial_mass_sum_kg"] == topo["pinned_l0_arm_mass_kg"]
    )

    # independent re-derivation of the M5 link-local transforms
    m5 = json.load(open(M5_DEC, encoding="utf-8"))
    fk_m7 = u.fk(Q0, T_MOUNT_M7)
    fk_f3r1 = u.fk(Q0, T_MOUNT_F3R1)
    m5_cmp = {}
    for k in ARM_LINKS:
        B = np.array(m5["components"][k]["T_link_from_assembly_at_q0_rows"])
        for tag, fk in (("mount_M7_WP1", fk_m7), ("mount_F3R1_build", fk_f3r1)):
            A = inv_T(fk[k])
            m5_cmp.setdefault(k, {})[tag] = {
                "max_abs_rotation_delta": float(np.abs(A[:3, :3] - B[:3, :3]).max()),
                "max_abs_translation_delta_mm": float(np.abs(A[:3, 3] - B[:3, 3]).max()),
            }
    mount_delta = {
        "max_abs_element_delta": float(np.abs(T_MOUNT_M7 - T_MOUNT_F3R1).max()),
        "M7_WP1_sin25": 0.422618483193,
        "F3R1_build_sin25": 0.422618261741,
        "exact_sin25": float(np.sin(np.deg2rad(25.0))),
        "M7_orthonormality_defect": float(
            np.abs(T_MOUNT_M7[:3, :3] @ T_MOUNT_M7[:3, :3].T - np.eye(3)).max()
        ),
        "F3R1_orthonormality_defect": float(
            np.abs(T_MOUNT_F3R1[:3, :3] @ T_MOUNT_F3R1[:3, :3].T - np.eye(3)).max()
        ),
        "worst_case_tip_effect_mm_at_460mm_reach": float(
            np.abs(T_MOUNT_M7[:3, :3] - T_MOUNT_F3R1[:3, :3]).max() * 460.0
        ),
    }

    # M7 design-freeze STEP: what B601 representation does it actually hold?
    step_txt = open(
        os.path.join(
            REPO,
            "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
            "wp1_structure_cad/DESIGN_FREEZE_ASSEMBLY_V1.step",
        ),
        encoding="utf-8", errors="replace",
    ).read()
    import re as _re
    counts = {
        e: len(_re.findall(r"=\s*%s\s*\(" % e, step_txt))
        for e in ("MANIFOLD_SOLID_BREP", "ADVANCED_FACE", "CLOSED_SHELL")
    }
    wp1 = json.load(open(WP1_REP, encoding="utf-8"))
    b601w = wp1["source_geometry_metrics"]["B601_arm_q0_frame_axis_witness"]
    step_probe = {
        "entity_counts_text_parsed": counts,
        "wp1_reported_solids": wp1["step_cold_reopen"]["solids"],
        "wp1_reported_faces": wp1["step_cold_reopen"]["faces"],
        "b601_representation_in_design_freeze_step": {
            "component": "INST_B601_ARM_CORE_Q0",
            "source_shape": "B601_arm_q0_frame_axis_witness",
            "solids": b601w["solids"],
            "faces": b601w["faces"],
            "volume_mm3": b601w["volume_mm3"],
            "classification": "KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY",
            "is_physical_arm_geometry": False,
            "note": (
                "817.65 mm3 across 18 solids / 34 faces cannot be a 4.6955 kg "
                "6R manipulator; WP1's own pairwise register labels every pair "
                "involving it KINEMATIC_FRAME_AXIS_WITNESS_OVERLAY_NOT_"
                "INTERFERENCE_GEOMETRY.  The M7 design-freeze STEP therefore "
                "contains NO B601 physical geometry and cannot be the CAD side "
                "of this adjudication."
            ),
        },
    }

    out = {
        "schema": "WP11_INPUTS_V1",
        "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "accepted_urdf_copy_consistency": ucheck,
        "accepted_urdf_all_copies_identical_on_disk": len(
            set(c["sha256_on_disk"] for c in ucheck)
        ) == 1,
        "accepted_urdf_all_copies_identical_lf_normalised": len(
            set(c["sha256_lf_normalised"] for c in ucheck)
        ) == 1,
        "urdf_topology": topo,
        "m5_transform_independent_rederivation": m5_cmp,
        "mount_transform_variants": mount_delta,
        "m7_design_freeze_step_probe": step_probe,
        "source_register": reg,
    }
    json.dump(out, open(os.path.join(OUT, "INPUTS.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "source_register"},
                     indent=1)[:6000])
    print("source_register entries:", len(reg))


# --------------------------------------------------------- registration helpers
def best_rigid(src_pts, dst_tri, dst_pts, trims=(1.0, 0.6), try_oct=False):
    """ICP from identity (and optionally the 24 octahedral datum candidates).
    src_pts / dst_pts are sampled surface points; returns the best (M, dstats)."""
    tree_dst = None
    from scipy.spatial import cKDTree
    tree_dst = cKDTree(dst_pts)
    cands = [np.eye(4)]
    if try_oct:
        cs, cd = src_pts.mean(0), dst_pts.mean(0)
        for R in OCT24:
            cands.append(T(R, cd - R @ cs))
    best = None
    for M0 in cands:
        for tr in trims:
            M, d = icp(src_pts, tree_dst, dst_pts, M0, iters=40, trim=tr)
            rms = float(np.sqrt((np.sort(d)[: max(1, int(0.6 * len(d)))] ** 2).mean()))
            if best is None or rms < best[0]:
                best = (rms, M)
    return best[1]


def surf_residual(src_tri, dst_tri, n=12000, seed=1):
    S = sample_surface(src_tri, n, seed)
    td = TriDist(dst_tri)
    d = td.query(S)
    st = stats(d)
    st["unverified_bound_points"] = td.unverified_count
    return st, S, d


def axis_metrics(pts, origin, axis, band_half_mm, r_max_mm, min_pts=800):
    """Concentricity / parallelism of CAD material about a URDF joint axis,
    with no nonlinear fitting: r-histogram peak + regression of r on s.

    Returns NOT_EVALUABLE unless a sharp cylindrical peak actually exists."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    v = pts - np.asarray(origin, float)
    s = v @ a
    rad = np.linalg.norm(v - s[:, None] * a[None, :], axis=1)
    m = (np.abs(s) <= band_half_mm) & (rad <= r_max_mm)
    if m.sum() < min_pts:
        return {"status": "NOT_EVALUABLE_INSUFFICIENT_POINTS", "points": int(m.sum())}
    s, rad = s[m], rad[m]
    hist, edges = np.histogram(rad, bins=np.arange(0.0, r_max_mm + 0.25, 0.25))
    j = int(np.argmax(hist))
    r_peak = float(0.5 * (edges[j] + edges[j + 1]))
    sel = np.abs(rad - r_peak) <= 1.0
    if sel.sum() < min_pts // 4:
        return {"status": "NOT_EVALUABLE_NO_SHARP_CYLINDRICAL_PEAK",
                "points": int(m.sum()), "peak_population": int(sel.sum())}
    rr, ss = rad[sel], s[sel]
    p10, p90 = np.percentile(rr, [10, 90])
    if len(np.unique(np.round(ss, 3))) > 3 and ss.std() > 1.0:
        A = np.stack([ss, np.ones_like(ss)], 1)
        slope = float(np.linalg.lstsq(A, rr, rcond=None)[0][0])
    else:
        slope = float("nan")
    return {
        "status": "EVALUATED",
        "points_in_band": int(m.sum()),
        "peak_population": int(sel.sum()),
        "dominant_radius_mm": r_peak,
        "radius_spread_p10_p90_mm": float(p90 - p10),
        "implied_axis_eccentricity_bound_mm": float(0.5 * (p90 - p10)),
        "dr_ds_slope": slope,
        "implied_axis_tilt_bound_deg": (
            float("nan") if not np.isfinite(slope)
            else float(np.degrees(np.arctan(abs(slope))))
        ),
    }


# ----------------------------------------------------------------- stage: testa
def stage_testa():
    u = _u()
    fk0 = u.fk(Q0, T_MOUNT_M7)
    res = {"schema": "WP11_TESTA_V1",
           "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "cad_configuration_of_export": "parts_DEPLOYED (verified below to be q0)",
           "links": {}}
    N = 12000
    for k in ARM_LINKS:
        t0 = time.time()
        tri_c_asm, n_c, p_c = load_cad(k, "DEPLOYED")
        tri_u, n_u, p_u = load_urdf_mesh(k)
        Tinv = inv_T(fk0[k])
        tri_c = apply_T(Tinv, tri_c_asm.reshape(-1, 3)).reshape(-1, 3, 3)
        tri_cd = dedup_tri(tri_c)
        Vc, Ac = mesh_volume_and_area(tri_c)
        Vcd, Acd = mesh_volume_and_area(tri_cd)
        Vu, Au = mesh_volume_and_area(tri_u)
        vc, vu = tri_c.reshape(-1, 3), tri_u.reshape(-1, 3)
        ec = vc.max(0) - vc.min(0)
        eu = vu.max(0) - vu.min(0)
        pc, _, _ = pca_extents(vc)
        pu, _, _ = pca_extents(vu)

        # D = I residuals, both directions
        s_cu, Sc, d_cu = surf_residual(tri_cd, tri_u, N, 11)
        s_uc, Su, d_uc = surf_residual(tri_u, tri_cd, N, 12)

        # best-fit D_i (CAD -> URDF link frame), trimmed ICP
        M = best_rigid(Sc, tri_u, Su, trims=(1.0, 0.6), try_oct=False)
        tri_c_al = apply_T(M, tri_cd.reshape(-1, 3)).reshape(-1, 3, 3)
        s_cu_al, _, _ = surf_residual(tri_c_al, tri_u, N, 13)
        s_uc_al, _, _ = surf_residual(tri_u, tri_c_al, N, 14)
        ax, ang = R_to_axis_angle(M[:3, :3])

        # partition-tolerant: CAD link vs URDF {i-1, i, i+1} union in link frame
        i = ARM_LINKS.index(k)
        nb = [ARM_LINKS[j] for j in (i - 1, i, i + 1) if 0 <= j < len(ARM_LINKS)]
        nb_tri = []
        for m in nb:
            tm, _, _ = load_urdf_mesh(m)
            nb_tri.append(apply_T(Tinv @ fk0[m], tm.reshape(-1, 3)).reshape(-1, 3, 3))
        if k == "link6":
            for m in ("gripper_link", "gripper_left", "gripper_right"):
                tm, _, _ = load_urdf_mesh(m)
                nb_tri.append(
                    apply_T(Tinv @ fk0[m], tm.reshape(-1, 3)).reshape(-1, 3, 3)
                )
            nb = nb + ["gripper_link", "gripper_left", "gripper_right"]
        s_nb, _, _ = surf_residual(tri_cd, np.concatenate(nb_tri, 0), N, 15)

        res["links"][k] = {
            "cad_source": os.path.relpath(p_c, REPO).replace("\\", "/"),
            "urdf_source": os.path.relpath(p_u, REPO).replace("\\", "/"),
            "cad_triangles_raw": int(n_c),
            "cad_triangles_deduplicated": int(len(tri_cd)),
            "cad_shell_duplication_factor": float(n_c / max(len(tri_cd), 1)),
            "urdf_triangles": int(n_u),
            "cad_volume_raw_mm3": Vc,
            "cad_volume_dedup_mm3": Vcd,
            "urdf_volume_mm3": Vu,
            "cad_raw_over_urdf_volume_ratio": Vc / Vu if Vu else None,
            "cad_dedup_over_urdf_volume_ratio": Vcd / Vu if Vu else None,
            "cad_area_dedup_mm2": Acd,
            "urdf_area_mm2": Au,
            "cad_area_over_urdf_area_ratio": Acd / Au if Au else None,
            "bbox_cad_link_frame_mm": [vc.min(0).tolist(), vc.max(0).tolist()],
            "bbox_urdf_link_frame_mm": [vu.min(0).tolist(), vu.max(0).tolist()],
            "bbox_extent_cad_mm": ec.tolist(),
            "bbox_extent_urdf_mm": eu.tolist(),
            "bbox_extent_delta_mm": (ec - eu).tolist(),
            "bbox_corner_max_abs_delta_mm": float(
                np.abs(np.concatenate([vc.min(0) - vu.min(0), vc.max(0) - vu.max(0)])).max()
            ),
            "principal_extents_cad_mm": pc.tolist(),
            "principal_extents_urdf_mm": pu.tolist(),
            "principal_extents_delta_mm": (pc - pu).tolist(),
            "residual_D_identity_cad_to_urdf": s_cu,
            "residual_D_identity_urdf_to_cad": s_uc,
            "D_i_best_fit_rows": M.tolist(),
            "D_i_translation_mm": M[:3, 3].tolist(),
            "D_i_translation_norm_mm": float(np.linalg.norm(M[:3, 3])),
            "D_i_rotation_axis": ax.tolist(),
            "D_i_rotation_angle_deg": float(np.degrees(ang)),
            "residual_after_D_i_cad_to_urdf": s_cu_al,
            "residual_after_D_i_urdf_to_cad": s_uc_al,
            "partition_tolerant_neighbourhood": nb,
            "residual_cad_to_urdf_neighbourhood_union": s_nb,
            "seconds": round(time.time() - t0, 1),
        }
        print("  %-10s D=I med %.4f/%.4f  afterD %.4f/%.4f  nbhd med %.4f p95 %.4f  "
              "dup %.3f volratio %.4f (%.0fs)"
              % (k, s_cu["median_mm"], s_uc["median_mm"], s_cu_al["median_mm"],
                 s_uc_al["median_mm"], s_nb["median_mm"], s_nb["p95_mm"],
                 n_c / max(len(tri_cd), 1), Vcd / Vu if Vu else float("nan"),
                 time.time() - t0))

    # whole-arm aggregate at q0 in the assembly frame
    t0 = time.time()
    cad_all, urdf_all = [], []
    for k in ARM_LINKS:
        tri, _, _ = load_cad(k, "DEPLOYED")
        cad_all.append(dedup_tri(tri))
    tri, _, _ = load_cad("gripper_detail", "DEPLOYED")
    cad_all.append(dedup_tri(tri))
    for k in ARM_LINKS + ["gripper_link", "gripper_left", "gripper_right"]:
        tm, _, _ = load_urdf_mesh(k)
        urdf_all.append(apply_T(fk0[k], tm.reshape(-1, 3)).reshape(-1, 3, 3))
    CA = np.concatenate(cad_all, 0)
    UA = np.concatenate(urdf_all, 0)
    a1, _, _ = surf_residual(CA, UA, 25000, 21)
    a2, _, _ = surf_residual(UA, CA, 25000, 22)
    res["whole_arm_aggregate_q0_assembly_frame"] = {
        "cad_members": ARM_LINKS + ["gripper_detail"],
        "urdf_members": ARM_LINKS + ["gripper_link", "gripper_left", "gripper_right"],
        "cad_triangles": int(len(CA)),
        "urdf_triangles": int(len(UA)),
        "residual_cad_to_urdf": a1,
        "residual_urdf_to_cad": a2,
        "seconds": round(time.time() - t0, 1),
    }
    print("  AGGREGATE cad->urdf med %.4f p95 %.4f p99 %.4f max %.3f | urdf->cad "
          "med %.4f p95 %.4f p99 %.4f max %.3f (%.0fs)"
          % (a1["median_mm"], a1["p95_mm"], a1["p99_mm"], a1["max_mm"],
             a2["median_mm"], a2["p95_mm"], a2["p99_mm"], a2["max_mm"],
             time.time() - t0))

    # joint-axis / interface-plane geometric evidence from CAD shape alone
    jm = {}
    for i, j in enumerate(u.joints[:6]):
        parent, child = j["parent"], j["child"]
        Tp = fk0[parent]
        o = np.array(j["xyz_m"]) * 1000.0
        from wp11_lib import rpy_to_R
        a_parent = rpy_to_R(*j["rpy"]) @ np.asarray(j["axis"], float)
        tri_p, _, _ = load_cad(parent, "DEPLOYED")
        tri_ch, _, _ = load_cad(child, "DEPLOYED")
        Tpi = inv_T(Tp)
        vp = apply_T(Tpi, tri_p.reshape(-1, 3))
        vch = apply_T(Tpi, tri_ch.reshape(-1, 3))
        ent = {
            "joint": j["name"], "parent": parent, "child": child,
            "urdf_origin_in_parent_mm": o.tolist(),
            "urdf_axis_in_parent": a_parent.tolist(),
            "cad_parent_material": axis_metrics(vp, o, a_parent, 25.0, 60.0),
            "cad_child_material": axis_metrics(vch, o, a_parent, 25.0, 60.0),
        }
        # interface plane: axial station histogram of parent/child near the axis
        for tag, V in (("parent", vp), ("child", vch)):
            a = a_parent / np.linalg.norm(a_parent)
            d = V - o
            s = d @ a
            r = np.linalg.norm(d - s[:, None] * a[None, :], axis=1)
            m = r <= 45.0
            if m.sum() > 500:
                ent["axial_extent_%s_near_axis_mm" % tag] = [
                    float(s[m].min()), float(s[m].max())
                ]
            else:
                ent["axial_extent_%s_near_axis_mm" % tag] = None
        jm[j["name"]] = ent
        print("  %-7s parent %s | child %s" % (
            j["name"], ent["cad_parent_material"]["status"],
            ent["cad_child_material"]["status"]))
    res["joint_axis_geometric_evidence"] = jm
    json.dump(res, open(os.path.join(OUT, "TESTA.json"), "w"), indent=1)
    print("TESTA written")


# ----------------------------------------------------------------- stage: testb
def stage_testb():
    u = _u()
    res = {"schema": "WP11_TESTB_V1",
           "generated_local": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "configurations": {}, "links": {}}
    lo, hi = limits(u)
    CFG = [
        ("q0", Q0, "URDF zero pose", "CAD_EXPORT_parts_DEPLOYED"),
        ("Q_STOW_C05_ARM_STOWED_ONORBIT", Q_STOW,
         "O13-v3 stow, deg [145.572,-168,-57,-41.143,-20.954,-3]",
         "CAD_EXPORT_parts_STOWED"),
        ("Q_TASK_READY_C06", Q_TASK_READY, "ARM_TASK_READY", "NO_CAD_EXPORT"),
        ("Q_INTERMEDIATE_C07_PREGRASP", Q_INTERMEDIATE,
         "representative intermediate", "NO_CAD_EXPORT"),
        ("Q_DEPLOYED_HOME_C01", Q_DEPLOYED_HOME, "deployed home", "NO_CAD_EXPORT"),
        ("Q_JOINT_LOWER_LIMITS", lo, "all joints at lower limit", "NO_CAD_EXPORT"),
        ("Q_JOINT_UPPER_LIMITS", hi, "all joints at upper limit", "NO_CAD_EXPORT"),
    ]
    for name, q, note, avail in CFG:
        res["configurations"][name] = {
            "q_rad": [float(x) for x in q],
            "q_deg": [float(np.degrees(x)) for x in q],
            "note": note,
            "cad_geometry_available": avail,
            "inside_joint_limits": bool(
                all(lo[i] - 1e-9 <= q[i] <= hi[i] + 1e-9 for i in range(6))
            ),
        }

    # ---- empirical: registration of the SAME CAD body across the two exports
    fk0 = u.fk(Q0, T_MOUNT_M7)
    fks = u.fk(Q_STOW, T_MOUNT_M7)
    N = 9000
    for k in ARM_LINKS:
        t0 = time.time()
        tri0, _, _ = load_cad(k, "DEPLOYED")
        tris, _, _ = load_cad(k, "STOWED")
        tri0 = dedup_tri(tri0)
        tris = dedup_tri(tris)
        # URDF-predicted rigid motion of this body between the two configs
        Mpred = fks[k] @ inv_T(fk0[k])
        # measured motion: ICP of the moved q0 body onto the stowed export
        S0 = sample_surface(tri0, N, 31)
        Ss = sample_surface(tris, N, 32)
        from scipy.spatial import cKDTree
        tree = cKDTree(Ss)
        Mmeas, dres = icp(S0, tree, Ss, Mpred, iters=60, trim=0.9)
        # residual of the URDF-predicted motion, evaluated surface-to-surface
        pred_tri = apply_T(Mpred, tri0.reshape(-1, 3)).reshape(-1, 3, 3)
        sp, _, _ = surf_residual(pred_tri, tris, N, 33)
        sp2, _, _ = surf_residual(tris, pred_tri, N, 34)
        Delta = inv_T(Mpred) @ Mmeas
        ax, ang = R_to_axis_angle(Delta[:3, :3])
        # D_i determined at each configuration, in that configuration's link frame
        Dq0 = np.eye(4)                       # reference definition of body coords
        Dst = inv_T(fks[k]) @ (Mmeas @ fk0[k])
        dax, dang = R_to_axis_angle(Dst[:3, :3])
        res["links"][k] = {
            "urdf_predicted_motion_rows": Mpred.tolist(),
            "icp_measured_motion_rows": Mmeas.tolist(),
            "motion_discrepancy_translation_mm": float(
                np.linalg.norm(Delta[:3, 3])
            ),
            "motion_discrepancy_rotation_deg": float(np.degrees(ang)),
            "urdf_predicted_pose_surface_residual_pred_to_stowed": sp,
            "urdf_predicted_pose_surface_residual_stowed_to_pred": sp2,
            "icp_correspondence_rms_mm": float(np.sqrt((dres ** 2).mean())),
            "D_i_at_q0_rows": Dq0.tolist(),
            "D_i_at_stow_rows": Dst.tolist(),
            "D_i_invariance_translation_mm": float(np.linalg.norm(Dst[:3, 3])),
            "D_i_invariance_rotation_deg": float(np.degrees(dang)),
            "seconds": round(time.time() - t0, 1),
        }
        print("  %-10s predicted-pose residual med %.5f/%.5f max %.4f | "
              "D_i invariance dt %.3e mm dR %.3e deg (%.0fs)"
              % (k, sp["median_mm"], sp2["median_mm"], sp["max_mm"],
                 float(np.linalg.norm(Dst[:3, 3])), float(np.degrees(dang)),
                 time.time() - t0))

    # ---- analytic propagation of the fixed D_i to configurations without a
    #      CAD export: exact by rigid-body composition; the *testable* content is
    #      adjacent-link interface coincidence, evaluated numerically per config.
    prop = {}
    for name, q, note, avail in CFG:
        fk = u.fk(q, T_MOUNT_M7)
        rows = []
        for i, j in enumerate(u.joints[:6]):
            p, c = j["parent"], j["child"]
            o_world = apply_T(fk[p], (np.array(j["xyz_m"]) * 1000.0)[None, :])[0]
            c_world = fk[c][:3, 3]
            rows.append(
                {
                    "joint": j["name"],
                    "parent_predicted_joint_origin_mm": o_world.tolist(),
                    "child_frame_origin_mm": c_world.tolist(),
                    "closure_residual_mm": float(np.linalg.norm(o_world - c_world)),
                }
            )
        ee = fk["gripper_link"][:3, 3]
        prop[name] = {
            "chain_closure_rows": rows,
            "max_closure_residual_mm": max(r["closure_residual_mm"] for r in rows),
            "gripper_link_origin_S_mm": ee.tolist(),
            "D_i_application": "EXACT_BY_RIGID_BODY_COMPOSITION_D_i_IS_BODY_FIXED",
            "empirical_cad_geometry_at_this_configuration": avail,
        }
    res["fixed_D_i_propagation"] = prop
    json.dump(res, open(os.path.join(OUT, "TESTB.json"), "w"), indent=1)
    print("TESTB written")


if __name__ == "__main__":
    {"inputs": stage_inputs, "testa": stage_testa, "testb": stage_testb}[
        sys.argv[1]
    ]()
