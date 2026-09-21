# -*- coding: utf-8 -*-
"""WP11 deliverable emitter.

Reads 10_intermediate/{INPUTS,TESTA,TESTB,ATTRIBUTION,REFINE,CLOSEOUT}.json and
writes the four WP11 contract artifacts.  Every consumed file is re-hashed here
(real SHA-256 + byte size, computed with hashlib) -- no hash is copied from a
sibling document.
"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from wp11_lib import (  # noqa: E402
    REPO, mesh_volume_and_area, read_ply, sha256_and_size,
)

WP11 = os.path.dirname(HERE)
INT = os.path.join(WP11, "10_intermediate")
ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6"]

TESS_MM = 0.5          # declared source tessellation linear deflection (M5)
COINCIDENCE_MM = 1.0   # 2 x tessellation deflection


def load(n):
    return json.load(open(os.path.join(INT, n + ".json"), encoding="utf-8"))


def reg_rows(paths, role_map=None):
    rows = []
    for p in paths:
        ap = p if os.path.isabs(p) else os.path.join(REPO, p)
        sha, n = sha256_and_size(ap)
        rows.append(
            {
                "path": os.path.relpath(ap, REPO).replace("\\", "/"),
                "bytes": n,
                "sha256": sha,
                "role": (role_map or {}).get(p, "CONSUMED_READ_ONLY"),
            }
        )
    return rows


def m5_ply_check():
    """Is the doubled shell present in the M5 link-local PLY assets too?"""
    base = os.path.join(
        REPO,
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
        "01_geometry_authority/assets/b601_link_local_surfaces",
    )
    urdf_dir = os.path.join(
        REPO, "20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper"
    )
    from wp11_lib import read_binary_stl
    out = {}
    for k in ARM_LINKS:
        p = os.path.join(base, "B601_%s_CAD_SURFACE_LINK_LOCAL_M.ply" % k)
        v, f = read_ply(p, scale=1000.0)
        tri = v[f]
        V, A = mesh_volume_and_area(tri)
        tu, _ = read_binary_stl(os.path.join(urdf_dir, "%s.STL" % k), scale=1000.0)
        Vu, _ = mesh_volume_and_area(tu)
        out[k] = {
            "ply_faces": int(len(f)),
            "ply_volume_mm3": V,
            "urdf_volume_mm3": Vu,
            "ply_over_urdf_volume_ratio": V / Vu if Vu else None,
        }
    return out


def band(cand, best_med):
    """Spread of |t| over fit candidates that reach within 3x the best residual
    (or 0.05 mm absolute) -- the registration's own numerical uncertainty."""
    ok = [
        c for c in cand.values()
        if c["median_mm"] <= max(3.0 * best_med, best_med + 0.05)
    ]
    if not ok:
        return None
    tn = [c["norm_mm"] for c in ok]
    T = np.array([c["t_mm"] for c in ok])
    return {
        "accepted_fit_count": len(ok),
        "norm_min_mm": float(min(tn)),
        "norm_max_mm": float(max(tn)),
        "norm_spread_mm": float(max(tn) - min(tn)),
        "component_min_mm": T.min(0).tolist(),
        "component_max_mm": T.max(0).tolist(),
    }


def main():
    IN = load("INPUTS")
    TA = load("TESTA")
    TB = load("TESTB")
    AT = load("ATTRIBUTION")
    RF = load("REFINE")
    CO = load("CLOSEOUT")
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    ply = m5_ply_check()

    # ---------------- per-link consolidated calibration -----------------------
    cal = {}
    for k in ARM_LINKS:
        if k in CO["links"]:
            c = CO["links"][k]
            t = c["best_translation_only_D_i_mm"]
            med = c["best_residual_cad_to_urdf"]["median_mm"]
            ent = {
                "D_i_model": "PURE_TRANSLATION_ROTATION_IDENTITY",
                "D_i_translation_mm": t,
                "D_i_translation_norm_mm": c["best_translation_only_norm_mm"],
                "D_i_rotation": "IDENTITY",
                "rotation_was_tested_and_rejected": {
                    "free_rigid_fit_rotation_deg": RF["links"][k][
                        "M2_full_rigid_rotation_deg"
                    ],
                    "residual_median_free_rigid_mm": c["residual_full_rigid_M2"][
                        "median_mm"
                    ],
                    "residual_median_same_translation_rotation_dropped_mm":
                        c["residual_with_M2_translation_rotation_dropped"]["median_mm"],
                    "rotation_is_necessary": c["rotation_is_necessary"],
                    "conclusion": (
                        "the free-rigid fit's small rotation does not reduce the "
                        "residual, so it is fit noise, not a datum rotation"
                    ),
                },
                "residual_after_D_i_cad_to_urdf": c["best_residual_cad_to_urdf"],
                "residual_after_D_i_urdf_to_cad": c["best_residual_urdf_to_cad"],
                "residual_at_D_identity_cad_to_urdf":
                    TA["links"][k]["residual_D_identity_cad_to_urdf"],
                "numerical_uncertainty_over_fit_restarts": band(c["candidates"], med),
                "independent_reproduction": {
                    "prior_2026_07_vendorcad03_translation_dev_mm":
                        c["prior_2026_07_translation_dev_mm"],
                    "wp11_2026_08_translation_norm_mm":
                        c["best_translation_only_norm_mm"],
                    "delta_mm": (
                        None if c["prior_2026_07_translation_dev_mm"] is None
                        else abs(c["best_translation_only_norm_mm"]
                                 - c["prior_2026_07_translation_dev_mm"])
                    ),
                },
            }
        else:  # link6: URDF collision mesh is a subset of the CAD body
            r = RF["links"][k]
            ent = {
                "D_i_model": "PURE_TRANSLATION_ROTATION_IDENTITY",
                "D_i_translation_mm": r["M1_translation_only_D_i_mm"],
                "D_i_translation_norm_mm": r["M1_translation_norm_mm"],
                "D_i_rotation": "IDENTITY",
                "fit_direction": "URDF_SUBSET_ONTO_CAD_SUPERSET",
                "residual_after_D_i_urdf_to_cad":
                    CO["link6_subset_containment"]["residual"],
                "residual_at_D_identity_urdf_to_cad":
                    TA["links"][k]["residual_D_identity_urdf_to_cad"],
                "free_rigid_fit_rejected": {
                    "reason": (
                        "the free ICP is dragged by the link-content partition "
                        "difference (URDF link6 = 9.5 mm tool-flange disc, CAD "
                        "link6 = 61.5 mm wrist body) and produced a 6.41 deg / "
                        "4.77 mm transform that made the containment residual "
                        "worse"
                    ),
                    "free_rigid_rotation_deg":
                        TA["links"][k]["D_i_rotation_angle_deg"],
                    "free_rigid_residual_urdf_to_cad_median_mm":
                        TA["links"][k]["residual_after_D_i_urdf_to_cad"]["median_mm"],
                    "identity_residual_urdf_to_cad_median_mm":
                        TA["links"][k]["residual_D_identity_urdf_to_cad"]["median_mm"],
                },
                "independent_reproduction": {
                    "prior_2026_07_method": "CHAIN_DERIVED (B5_0 G05)",
                    "prior_2026_07_direct_nn_mm": 16.408,
                    "prior_note": (
                        "direct 配准不可靠（内容划分/开度差异）；链推导锁定 -- the "
                        "same partition boundary, reached independently in 2026-07"
                    ),
                },
            }
        ent["validated_configurations"] = [
            "q0 (CAD export parts_DEPLOYED)",
            "Q_STOW_C05 deg [145.572,-168.0,-57.0,-41.143,-20.954,-3.0] "
            "(CAD export parts_STOWED)",
        ]
        ent["cross_configuration_evidence"] = {
            "urdf_predicted_pose_surface_residual_median_mm":
                TB["links"][k]["urdf_predicted_pose_surface_residual_pred_to_stowed"][
                    "median_mm"],
            "urdf_predicted_pose_surface_residual_max_mm":
                TB["links"][k]["urdf_predicted_pose_surface_residual_pred_to_stowed"][
                    "max_mm"],
        }
        cal[k] = ent

    # ---------------- Test C indicator evaluation ---------------------------
    worst_pred = max(
        TB["links"][k]["urdf_predicted_pose_surface_residual_pred_to_stowed"]["max_mm"]
        for k in ARM_LINKS
    )
    shape_meds = {
        k: (cal[k].get("residual_after_D_i_cad_to_urdf")
            or cal[k]["residual_after_D_i_urdf_to_cad"])["median_mm"]
        for k in ARM_LINKS
    }
    shape_p95 = {
        k: (cal[k].get("residual_after_D_i_cad_to_urdf")
            or cal[k]["residual_after_D_i_urdf_to_cad"])["p95_mm"]
        for k in ARM_LINKS
    }
    ax = TA["joint_axis_geometric_evidence"]
    ecc = {j: max(v["cad_parent_material"]["implied_axis_eccentricity_bound_mm"],
                  v["cad_child_material"]["implied_axis_eccentricity_bound_mm"])
           for j, v in ax.items()}
    tilt = {}
    for j, v in ax.items():
        vals = [v[t]["implied_axis_tilt_bound_deg"] for t in
                ("cad_parent_material", "cad_child_material")]
        vals = [x for x in vals if x is not None and np.isfinite(x)]
        tilt[j] = max(vals) if vals else None

    test_c = {
        "indicator_1_D_i_varies_with_configuration": {
            "result": "NOT_PRESENT",
            "evidence": (
                "one fixed rigid per-link relationship reproduces the second "
                "CAD articulation export exactly: URDF-predicted pose surface "
                "residual max %.6f mm over all 7 links" % worst_pred
            ),
            "worst_max_residual_mm": worst_pred,
        },
        "indicator_2_large_shape_residual_after_fixed_rigid_transform": {
            "result": "NOT_PRESENT_FOR_SHARED_MATERIAL",
            "per_link_median_mm": shape_meds,
            "per_link_p95_mm": shape_p95,
            "acceptance_reference_mm": TESS_MM,
            "note": (
                "every link's post-D_i median residual is 0.0043-0.0449 mm, "
                "1-2 orders of magnitude below the 0.5 mm source tessellation "
                "deflection.  The two large *unshared* regions are both "
                "attributed by name (owner-deleted 01_BASE_Plate; link6/"
                "gripper_link content-partition boundary) and are not shape "
                "disagreements about the same physical material."
            ),
        },
        "indicator_3_joint_axis_or_mounting_face_inconsistent": {
            "result": "NOT_PRESENT",
            "evidence_a_no_datum_rotation": (
                "rotation_is_necessary = False for every evaluated link; the "
                "CAD link axes are parallel to the accepted-URDF link axes"
            ),
            "evidence_b_cad_material_concentric_with_urdf_joint_axes": {
                "per_joint_eccentricity_upper_bound_mm": ecc,
                "per_joint_tilt_upper_bound_deg": tilt,
                "method": (
                    "radius-histogram peak of CAD material about the URDF joint "
                    "axis; spread bounds eccentricity, dr/ds bounds tilt.  These "
                    "are UPPER BOUNDS inflated by the 0.25 mm bin width and by "
                    "concentric neighbouring features, not fitted axis errors."
                ),
                "weakest_case": "joint6 child tilt upper bound %.4f deg" % tilt["joint6"],
            },
        },
        "verdict": "CAD_URDF_VERSION_MISMATCH_NOT_SUPPORTED_BY_EVIDENCE",
    }

    # ---------------- phantom plate box in the assembly frame ---------------
    from wp11_lib import Urdf, apply_T
    from wp11_analysis import Q0, T_MOUNT_M7, URDF_PATH
    u = Urdf(URDF_PATH)
    fk0 = u.fk(Q0, T_MOUNT_M7)
    lo, hi = (np.array(x) for x in
              AT["base_link_extra_material_attribution"][
                  "deleted_plate_bbox_in_urdf_base_link_frame_mm"])
    corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    cw = apply_T(fk0["base_link"], corners)
    plate_S = [cw.min(0).tolist(), cw.max(0).tolist()]

    # ---------------- findings ---------------------------------------------
    bl = AT["base_link_extra_material_attribution"]
    findings = [
        {
            "id": "WP11-F-01",
            "severity": "MEDIUM",
            "state": "OPEN_ACTION_ASSIGNED",
            "title": (
                "accepted-URDF base_link collision mesh still carries the "
                "owner-deleted vendor desktop base plate"
            ),
            "detail": (
                "The accepted-URDF base_link collision mesh spans 140 x 200 x "
                "82.65 mm in the base_link frame, while the flight-side CAD "
                "base_link spans 92 x 92 x 80.15 mm.  %.2f%% of the URDF "
                "base_link surface is farther than %.1f mm from any CAD "
                "material, and %.2f%% of that lies inside the bounding box of "
                "vendor solid 01_BASE_Plate, which the owner ruling of "
                "2026-07-27 DELETED (design/base_classification.json).  Single-"
                "shell volume ratio CAD/URDF = %.5f, i.e. %.1f mm3 of the URDF "
                "base_link collision volume is non-flight bench hardware."
                % (100.0 * bl["fraction_of_urdf_surface_farther_than_1mm"],
                   COINCIDENCE_MM,
                   100.0 * bl["of_those_fraction_inside_deleted_plate_box"],
                   TA["links"]["base_link"]["cad_raw_over_urdf_volume_ratio"] / 2.0,
                   TA["links"]["base_link"]["urdf_volume_mm3"]
                   - TA["links"]["base_link"]["cad_raw_over_urdf_volume_ratio"] / 2.0
                   * TA["links"]["base_link"]["urdf_volume_mm3"])
            ),
            "consequence": (
                "Consuming the accepted-URDF collision meshes unmodified as the "
                "operational collision authority injects a phantom slab at the "
                "arm root, assembly-frame AABB %s mm.  This is a decisive reason "
                "the disposition is O2-A (CAD = physical geometry authority) and "
                "not O2-B." % json.dumps([[round(v, 3) for v in plate_S[0]],
                                          [round(v, 3) for v in plate_S[1]]])
            ),
            "action": (
                "re-export the base_link operational collision mesh from the CAD "
                "geometry through D_base_link; do not use the raw URDF base_link "
                "collision STL for clearance, self-collision or RL shielding"
            ),
            "assigned_to": "A7_CM_RELEASE_with_WP10_MECH_RL",
            "phantom_plate_bbox_assembly_frame_mm": plate_S,
        },
        {
            "id": "WP11-F-02",
            "severity": "MEDIUM",
            "state": "OPEN_DECLARED",
            "title": (
                "the F3R2 05_clearance CAD arm STL exports contain a DOUBLED "
                "closed shell, so any volume/mass derived from them is 2x high"
            ),
            "detail": (
                "Raw divergence-theorem volume of the CAD part STLs divided by "
                "the accepted-URDF volume: " + ", ".join(
                    "%s %.5f" % (k, TA["links"][k]["cad_raw_over_urdf_volume_ratio"])
                    for k in ARM_LINKS if k != "link6"
                ) + ".  Exact-duplicate triangle factor 1.695-2.001.  After "
                "halving, links 1-5 agree with the accepted URDF to 0.006%-4.1%.  "
                "The M5 link-local PLY assets derived from these STLs are "
                "SINGLE shell (PLY/URDF volume ratio " + ", ".join(
                    "%s %.4f" % (k, ply[k]["ply_over_urdf_volume_ratio"])
                    for k in ("link2", "link3", "link5")
                ) + "), so the defect does NOT propagate into the M5 asset set."
            ),
            "consequence": (
                "surface-distance and clearance results are unaffected (a doubled "
                "shell has the same surface locus); only volume/mass/inertia "
                "integrals would be wrong.  No M7 artifact is known to take mass "
                "from these STLs - L0 accepted-URDF masses govern (ODR / pinned "
                "4.695555949342986 kg)."
            ),
            "action": (
                "record the halving rule with the asset; never quote a volume "
                "from parts_DEPLOYED / parts_STOWED without it"
            ),
            "assigned_to": "A7_CM_RELEASE",
        },
        {
            "id": "WP11-F-03",
            "severity": "LOW",
            "state": "OPEN_DECLARED",
            "title": "two numerical writings of the same 25 deg arm clocking",
            "detail": (
                "M7 WP1 T_S_B601_ARM_BASE uses sin25 = %.12f; the F3R1 transform "
                "that actually built and posed the CAD arm uses the exact double "
                "%.12f (= sin(25 deg)).  Max element delta %.3e; worst-case tip "
                "effect %.3e mm at 460 mm reach."
                % (IN["mount_transform_variants"]["M7_WP1_sin25"],
                   IN["mount_transform_variants"]["F3R1_build_sin25"],
                   IN["mount_transform_variants"]["max_abs_element_delta"],
                   IN["mount_transform_variants"][
                       "worst_case_tip_effect_mm_at_460mm_reach"])
            ),
            "consequence": (
                "geometrically negligible, but two spellings of one frame is a "
                "configuration-management defect"
            ),
            "action": "pin the exact sin/cos(25 deg) doubles in one place",
            "assigned_to": "A7_CM_RELEASE",
        },
        {
            "id": "WP11-F-04",
            "severity": "LOW",
            "state": "OPEN_DECLARED",
            "title": (
                "the M7 design-freeze assembly holds no B601 physical geometry"
            ),
            "detail": (
                "DESIGN_FREEZE_ASSEMBLY_V1.step contains 41 MANIFOLD_SOLID_BREP / "
                "647 ADVANCED_FACE (independently re-counted by text parse, "
                "matching WP1).  The B601 contribution is the 18-solid / 34-face "
                "/ 817.651847974 mm3 'B601_arm_q0_frame_axis_witness' overlay.  A "
                "4.695555949342986 kg 6R manipulator cannot be 817.65 mm3."
            ),
            "consequence": (
                "the design-freeze STEP cannot be the CAD side of any arm "
                "clearance, interference or registration claim; WP11 therefore "
                "measured the B51 vendor-CAD arm exports that M5 adopted as the "
                "geometry-authority asset set"
            ),
            "action": (
                "state the witness-overlay limitation wherever the design-freeze "
                "assembly is cited for arm geometry"
            ),
            "assigned_to": "A1_PRODUCT_CAD_and_A0",
        },
        {
            "id": "WP11-F-05",
            "severity": "INFORMATIONAL",
            "state": "DECLARED_SCOPE_LIMIT",
            "title": (
                "Test B cross-configuration agreement is construction-inherited, "
                "not an independent kinematic measurement"
            ),
            "detail": (
                "p4_stow_pose.py states the method verbatim: 'compute URDF FK at "
                "q_stow, then set every component's Transform2 to T_link(q_stow) "
                "@ offset_i, where offset_i = inv(T_link(q0)) @ T_comp(q0)'.  The "
                "CAD arm has dead joints and is articulated by accepted-URDF "
                "forward kinematics, so the max 2e-4 mm agreement between the two "
                "CAD exports confirms that a single body-fixed calibration is "
                "what the CAD uses, and does NOT independently corroborate the "
                "URDF joint parameters."
            ),
            "consequence": (
                "it also means the CAD holds no competing kinematic definition, "
                "so a CAD-vs-URDF *kinematic* conflict is structurally impossible; "
                "the question reduces to shape and datum, which Test A answers"
            ),
            "action": "none; declared so no reader over-reads Test B",
            "assigned_to": "WP11",
        },
        {
            "id": "WP11-F-06",
            "severity": "INFORMATIONAL",
            "state": "CLOSED_FULLY_ATTRIBUTED",
            "title": (
                "base_link non-coincident surface is 100% attributed to the "
                "deleted plate at 0.5 mm box dilation"
            ),
            "detail": (
                "%d of 40000 accepted-URDF base_link surface samples (%.2f%%) are "
                ">%.1f mm from CAD material and fall outside the EXACT deleted-"
                "plate bounding box, but %.4f%% / %.4f%% / %.4f%% of ALL far "
                "samples are captured at 0.5 / 2.0 / 5.0 mm box dilation - i.e. "
                "at 0.5 mm dilation the attribution is complete.  The remainder "
                "at zero dilation is plate edge-blend and material the plate "
                "concealed.  No unattributed base_link geometry difference "
                "remains."
                % (CO["base_link_unexplained"]["unexplained_count_pad0"],
                   100.0 * CO["base_link_unexplained"][
                       "unexplained_fraction_of_urdf_surface_pad0"],
                   COINCIDENCE_MM,
                   100.0 * CO["base_link_unexplained"]["explained_fraction_pad_0.5mm"],
                   100.0 * CO["base_link_unexplained"]["explained_fraction_pad_2.0mm"],
                   100.0 * CO["base_link_unexplained"]["explained_fraction_pad_5.0mm"])
            ),
            "consequence": (
                "no unexplained CAD-vs-URDF geometry difference remains on "
                "base_link; the whole non-coincident region is the owner-deleted "
                "desktop plate tracked by WP11-F-01"
            ),
            "action": "none; retained as the positive attribution record",
            "assigned_to": "A7_CM_RELEASE",
        },
    ]

    # ---------------- source register --------------------------------------
    consumed = [r["path"] for r in IN["source_register"]] + [
        "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/design/base_classification.json",
        "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/design/group_link_transforms.json",
        "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/design/group_link_registration.json",
        "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
        "130_B601_Vendor_CAD_Direct_Integration_03/design/vendor_group_census.json",
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
        "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
        "M7_TERMINAL_CLOSURE_CONTRACT_V1.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
        "M7_OWNER_DECISION_REGISTER_V1.yaml",
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
        "M7_EXECUTION_PLAN_V1.md",
    ] + [
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
        "01_geometry_authority/assets/b601_link_local_surfaces/"
        "B601_%s_CAD_SURFACE_LINK_LOCAL_M.ply" % k for k in ARM_LINKS
    ]
    seen, uniq = set(), []
    for p in consumed:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    sreg = reg_rows(uniq)
    tools = reg_rows([
        os.path.join(HERE, f) for f in
        ("wp11_lib.py", "wp11_analysis.py", "wp11_attribution.py",
         "wp11_refine.py", "wp11_closeout.py", "wp11_emit.py")
    ])
    inters = reg_rows([
        os.path.join(INT, f + ".json") for f in
        ("INPUTS", "TESTA", "TESTB", "ATTRIBUTION", "REFINE", "CLOSEOUT")
    ])

    # ---------------- ANALYSIS json ----------------------------------------
    analysis = {
        "schema": "CAD_URDF_REGISTRATION_ANALYSIS_V1",
        "generated_local": now,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "phase": "M7_MECHANICAL_FINAL_DESIGN_CLOSURE",
        "work_package": "WP11_CAD_URDF_REGISTRATION",
        "authority_basis": ["ODR-09", "ODR-10", "ODR-01", "ODR-03", "ODR-04"],
        "lifecycle_status": (
            "ENGINEERING_ADJUDICATION_DESIGN_LEVEL_NOT_MANUFACTURING_NOT_FLIGHT"
        ),
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "claim_limits": [
            "no flight, launcher, manufacturing-release or qualification claim",
            "analysis of tessellated geometry, not metrology of hardware",
            "the 6 GiB memory gate remains FAILED on this host and was not used",
            "no FreeCAD or SolidWorks process was started by this work package",
        ],
        "representation_selection": {
            "question": "which B601 representation is actually being measured",
            "m7_design_freeze_step": IN["m7_design_freeze_step_probe"],
            "cad_side_measured": {
                "asset_family": (
                    "B51 vendor-CAD arm, tessellated per link into the assembly "
                    "frame at two articulation states"
                ),
                "paths": [
                    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
                    "05_clearance/mesh/parts_DEPLOYED/B51_REF_<link>_LINKLOCAL.stl",
                    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
                    "05_clearance/mesh/parts_STOWED/B51_REF_<link>_LINKLOCAL.stl",
                ],
                "why": (
                    "these are the exports M5 adopted as the B601 geometry "
                    "authority assets (B601_CAD_MESH_FRAME_DECISION_V1.json) and "
                    "the only B601 representation in the repository that carries "
                    "real physical arm material"
                ),
                "provenance_chain": [
                    "vendor B601 CAD assembly (Seeed reBot DevArm), groups "
                    "Link1..Link6 / Base / Gripper",
                    "20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/"
                    "130_B601_Vendor_CAD_Direct_Integration_03 -- per-group rigid "
                    "registration into accepted-URDF link frames "
                    "(p_link = R @ p_vendor + t), all R pure axis permutations",
                    "B5_0 vendor_reference_linklocal B50_REF_<link>_LINKLOCAL.step",
                    "B5_1 native_inputs 10_vendor_link_parts "
                    "B51_REF_<link>_LINKLOCAL.SLDPRT",
                    "F3R1/F3R2 assembly, articulated by accepted-URDF FK, "
                    "tessellated to the STLs measured here",
                ],
                "cad_export_configuration_verified": (
                    "parts_DEPLOYED is at URDF q0, not at C01 DEPLOYED_NOMINAL; "
                    "verified by assembly-frame AABB agreement with the URDF "
                    "meshes placed by FK(q0) and corroborated by the vendor "
                    "hypothesis 'vendor assembly configuration = URDF q=0' "
                    "(rotation_max_dev 7.346e-06)"
                ),
            },
            "urdf_side_measured": {
                "urdf": "20_engineering/cad/spacecraft_layout/arm_b601_v1/"
                        "arm_b601_v1.urdf",
                "collision_meshes": "meshes_b601_gripper/*.STL (10 binary STL, "
                                    "549242 triangles, all declared/actual sizes "
                                    "consistent, no truncation)",
            },
        },
        "input_integrity": {
            "accepted_urdf_copies_checked": 4,
            "all_copies_identical_on_disk": IN[
                "accepted_urdf_all_copies_identical_on_disk"],
            "all_copies_identical_lf_normalised": IN[
                "accepted_urdf_all_copies_identical_lf_normalised"],
            "sha256_on_disk_crlf": IN["accepted_urdf_copy_consistency"][0][
                "sha256_on_disk"],
            "sha256_lf_normalised": IN["accepted_urdf_copy_consistency"][0][
                "sha256_lf_normalised"],
            "crlf_note": (
                "core.autocrlf keeps the working tree at 11321 bytes / CRLF; the "
                "LF-normalised digest is 11029 bytes and equals the historically "
                "pinned 408147DD...A3A4.  No contamination."
            ),
            "urdf_topology": IN["urdf_topology"],
            "m5_transform_independent_rederivation": IN[
                "m5_transform_independent_rederivation"],
            "mount_transform_variants": IN["mount_transform_variants"],
        },
        "test_a_zero_pose_rigid_registration": {
            "method": (
                "CAD part localised into each accepted-URDF link frame with "
                "inv(T_URDF_i(q0)) re-derived independently in this WP; then "
                "bounding box, principal dimensions, single-shell volume and "
                "area, exact bidirectional point-to-surface residual at D=I, and "
                "the best-fit D_i"
            ),
            "distance_engine": (
                "exact unsigned point-to-triangle with a radius-bucketed "
                "KD-tree broad phase whose sufficiency bound is proved per query "
                "point; 0 unverified points anywhere in this analysis"
            ),
            "per_link": TA["links"],
            "joint_axis_geometric_evidence": TA["joint_axis_geometric_evidence"],
            "whole_arm_aggregate_q0_assembly_frame": TA[
                "whole_arm_aggregate_q0_assembly_frame"],
            "translation_only_vs_full_rigid": CO["links"],
            "link6_subset_containment": CO["link6_subset_containment"],
            "conclusion": (
                "after a per-link PURE TRANSLATION of 0.083-3.910 mm the shared "
                "CAD and accepted-URDF material coincides to a median of "
                "0.0043-0.0449 mm, far below the 0.5 mm source tessellation "
                "deflection.  This is a mesh-origin / CAD-datum difference, NOT a "
                "kinematic conflict."
            ),
        },
        "test_a_unshared_material_attribution": {
            "base_link": AT["base_link_extra_material_attribution"],
            "base_link_unexplained_remainder": CO["base_link_unexplained"],
            "wrist_link6_gripper_partition": AT["wrist_partition_attribution"],
            "link1_plateau": dict(
                AT["link1_plateau_attribution"],
                resolution=(
                    "the 3.9000 mm plateau measured at D=I is the datum offset "
                    "itself: D_link1 is a 3.9095 mm translation, and after it the "
                    "median residual falls from 0.9000 mm to 0.00425 mm"
                ),
            ),
            "doubled_shell_defect": {
                "cad_stl_raw_over_urdf_volume_ratio": {
                    k: TA["links"][k]["cad_raw_over_urdf_volume_ratio"]
                    for k in ARM_LINKS
                },
                "cad_stl_exact_duplicate_triangle_factor": {
                    k: TA["links"][k]["cad_shell_duplication_factor"]
                    for k in ARM_LINKS
                },
                "m5_ply_single_shell_check": ply,
            },
        },
        "test_b_multi_configuration_propagation": TB,
        "test_c_true_version_mismatch_indicators": test_c,
        "findings": findings,
        "verdict": {
            "classification": "COORDINATE_REGISTRATION_DIFFERENCE",
            "not": "CAD_URDF_VERSION_MISMATCH",
            "statement": (
                "The B601 CAD arm and the accepted URDF are the same arm at the "
                "same geometry version.  The registered 'link6 ~46 mm / base_link "
                "~56 mm' divergence decomposes into (a) a fixed per-link CAD-datum "
                "TRANSLATION of 0.083-3.910 mm with identity rotation, (b) an "
                "owner-ruled deliberate deletion of the vendor desktop base plate "
                "on the flight side, and (c) a link-content partition boundary "
                "between link6 and gripper_link.  None of the three is a "
                "geometry-version difference and none is a kinematic conflict."
            ),
            "gate_a_criterion_05_may_pass": True,
        },
        "source_register": sreg,
        "tool_register": tools,
        "intermediate_register": inters,
    }
    p = os.path.join(WP11, "CAD_URDF_REGISTRATION_ANALYSIS_V1.json")
    json.dump(analysis, open(p, "w"), indent=1)
    print("wrote", p, os.path.getsize(p), "bytes")

    # ---------------- calibration YAML -------------------------------------
    import yaml
    cal_doc = {
        "schema": "B601_CAD_URDF_GEOMETRY_CALIBRATION_V1",
        "generated_local": now,
        "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
        "authority_basis": ["ODR-09", "ODR-10 option O2-A"],
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "authority_level": "DESIGN_CALIBRATION_NOT_METROLOGY_NOT_FLIGHT",
        "confidence": "B",
        "definition": {
            "D_i": "inv(T_URDF_i) * T_CAD_i",
            "meaning": (
                "D_i maps a point expressed in the CAD part's body coordinates "
                "(as tessellated into the accepted-URDF link frame by "
                "inv(T_URDF_i(q0))) into the accepted-URDF link_i frame"
            ),
            "usage_forward": "p_urdf_link_i = D_i * p_cad_body_i",
            "usage_inverse": "p_cad_body_i = inv(D_i) * p_urdf_link_i",
            "model": "pure translation; rotation identity (tested and rejected)",
            "units": "mm",
        },
        "frame_context": {
            "mount": "T_S_B601_ARM_BASE, station x = 208.0 mm, 25 deg clocking",
            "mount_rows": T_MOUNT_M7.tolist(),
            "dynamics_M_frame_is_separate": (
                "ODR-01: T_SM = [185.25,0,0] + Ry(90 deg) remains the single "
                "dynamics mounting reference; 198.0 / 208.0 / 210.405 mm stay a "
                "geometric feature stack and this calibration does not create a "
                "second dynamics frame"
            ),
        },
        "acceptance": {
            "source_tessellation_linear_deflection_mm": TESS_MM,
            "coincidence_threshold_mm": COINCIDENCE_MM,
            "physical_clearance_or_metrology_claim": False,
        },
        "links": cal,
        "validated_over_configurations": TB["configurations"],
        "cross_configuration_proof": {
            "empirical_configurations_with_independent_cad_geometry": [
                "q0", "Q_STOW_C05_ARM_STOWED_ONORBIT"],
            "worst_urdf_predicted_pose_surface_residual_mm": worst_pred,
            "analytic_extension": (
                "D_i is body-fixed, so its application at ARM_TASK_READY (C06), "
                "the C07 intermediate, DEPLOYED_HOME (C01) and all joint lower / "
                "upper limits is exact by rigid-body composition (residual 0 by "
                "construction).  Those four are ANALYTIC, not measured: the CAD "
                "has no independent geometry export at them.  Declared, not "
                "claimed as empirical."
            ),
            "per_configuration_chain_closure": {
                k: v["max_closure_residual_mm"]
                for k, v in TB["fixed_D_i_propagation"].items()
            },
        },
        "consumption_rules": [
            "kinematics, joint limits, topology and mass/inertia: accepted URDF "
            "only (L0), never overridden by CAD",
            "physical geometry, clearance, interference and manufacturing intent: "
            "M7 CAD, placed into URDF link frames through D_i",
            "operational collision meshes must be re-exported from CAD through "
            "D_i; the raw accepted-URDF base_link collision STL must not be used "
            "(see finding WP11-F-01 phantom desktop base plate)",
            "any volume or mass read from parts_DEPLOYED / parts_STOWED STLs must "
            "be halved (doubled shell, finding WP11-F-02); the M5 link-local PLY "
            "assets are single shell and need no correction",
            "link6 and gripper_link are a CONTENT PARTITION pair: compare or "
            "collide them as the union, never link6 against link6 alone",
            "the flight gripper is the neutral R1 design (ODR-04); the vendor "
            "gripper_detail geometry is retained here only as the wrist-partition "
            "witness and is not gripper shape authority",
        ],
        "carried_open_items": [
            "WP11-F-01 collision-mesh re-export (phantom desktop base plate)",
            "WP11-F-02 doubled-shell volume rule",
            "WP11-F-03 duplicate spelling of the 25 deg clocking",
            "AS_BUILT_ARM_METROLOGY_HOLD -- no measured hardware exists; this "
            "calibration is CAD-to-CAD, not CAD-to-hardware",
        ],
    }
    p = os.path.join(WP11, "B601_CAD_URDF_GEOMETRY_CALIBRATION_V1.yaml")
    yaml.safe_dump(cal_doc, open(p, "w", encoding="utf-8"), sort_keys=False,
                   allow_unicode=True, default_flow_style=False, width=100)
    print("wrote", p, os.path.getsize(p), "bytes")
    json.dump({"analysis": analysis["verdict"], "worst_pred": worst_pred,
               "shape_meds": shape_meds, "shape_p95": shape_p95,
               "plate_S": plate_S},
              open(os.path.join(INT, "EMIT_SUMMARY.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
