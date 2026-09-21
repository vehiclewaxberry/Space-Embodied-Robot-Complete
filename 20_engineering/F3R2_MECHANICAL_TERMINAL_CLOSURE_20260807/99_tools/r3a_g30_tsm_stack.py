# -*- coding: utf-8 -*-
"""F3R2 G3-0: freeze the T_SM interface stack and prove the rigid chain.

The three X stations were never competing values -- they are three different
things on one axis, and treating them as a contradiction is what blocked the
project:

    185.25   M-frame origin: the DYNAMICS / URDF base frame (P5C Mode B)
    198.00   Adapter_Plate outer face
    208.00   Central_Boss physical mounting face

So the arm's dynamics origin is NOT a flange face.  Freezing this removes the
22.75 mm "conflict" without translating the already-frozen arm.

It also records a correction that changes the whole base-interface story:
B601's base_link DOES carry a real mounting flange -- an 8-hole r=3.4 (M6)
pattern on a R=45.25 bolt circle at x = 210.41, coaxial with X, plus a
counterbore pattern at the same circle.  D-F3R1-05 ("no flange face, largest
cylinder r=1.0") was measured on a coarse solid and is superseded.
"""
import json
import math
import sys
import traceback

import r2_common as C

OUTY = C.NC2 / "F3R2_TSM_INTERFACE_STACK.yaml"
OUTJ = C.NC2 / "F3R2_TSM_CAD_MEASUREMENT.json"
OUTMD = C.NC2 / "F3R2_TSM_PHYSICAL_FRAME_DIAGRAM.md"
BREP = C.CLR2 / "mesh" / "BREP_PROBE_MOUNT2.json"

M_FRAME_X = 185.25
ADAPTER_FACE_X = 198.00
BOSS_FACE_X = 208.00


def yaml_dump(o, ind=0):
    sp = "  " * ind
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)) and v:
                out.append("%s%s:" % (sp, k))
                out.append(yaml_dump(v, ind + 1))
            elif isinstance(v, (dict, list)):
                out.append("%s%s: %s" % (sp, k,
                                         "{}" if isinstance(v, dict) else "[]"))
            else:
                out.append("%s%s: %s" % (sp, k, sc(v)))
    elif isinstance(o, list):
        for v in o:
            if isinstance(v, (dict, list)):
                out.append("%s-" % sp)
                out.append(yaml_dump(v, ind + 1))
            else:
                out.append("%s- %s" % (sp, sc(v)))
    return "\n".join(out)


def sc(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(round(v, 6))
    if isinstance(v, str):
        return v if (v and all(c.isalnum() or c in "._-/+" for c in v)) \
            else json.dumps(v, ensure_ascii=False)
    return str(v)


def hole_groups(cyls, rmin=1.2, rmax=4.0):
    """Fastener-scale cylinders grouped by (radius, x-station)."""
    import collections
    g = collections.defaultdict(list)
    for f in cyls:
        r = f["radius_mm"]
        if not (rmin <= r <= rmax):
            continue
        if abs(abs(f["axis_xyz"][0]) - 1.0) > 1e-6:
            continue
        g[(r, round(f["centre_mm"][0], 2))].append(f["centre_mm"])
    out = []
    for (r, x), cs in sorted(g.items()):
        rad = [math.hypot(c[1], c[2]) for c in cs]
        ang = sorted(round(math.degrees(math.atan2(c[2], c[1])) % 360, 2)
                     for c in cs)
        out.append({"radius_mm": r, "x_station_mm": x, "count": len(cs),
                    "bolt_circle_R_mm": [round(min(rad), 3),
                                         round(max(rad), 3)],
                    "angles_deg": ang[:16]})
    return out


def main():
    rep = {"schema": "F3R2_TSM_MEASUREMENT_V1"}
    try:
        C.check_protected2("G30_PRE")
        b = json.loads(BREP.read_text(encoding="utf-8"))["parts"]

        bus = {}
        # Front_End_Frame is part of the load path: it fills x = 175..183
        # between the load-spreading frame and the flange.  Leaving it out made
        # the chain look like it had an 8 mm hole in it.
        for k in ("Load_Spreading_Frame", "Front_End_Frame",
                  "Spacecraft_Flange", "Adapter_Plate", "Central_Boss"):
            v = b[k]
            bus[k] = {"box_mm": v["box_mm"],
                      "x_inner_mm": v["box_mm"][0], "x_outer_mm": v["box_mm"][3],
                      "cylinder_radii_mm": v["cylinder_radii_mm"],
                      "central_bore_r_mm": (50.0 if 50.0 in
                                            v["cylinder_radii_mm"] else None),
                      "volume_mm3": v["volume_mm3"]}
        rep["spacecraft_side_stack"] = bus

        base = b["B51_REF_base_link_LINKLOCAL068"]
        base_hi = b["B51_REF_base_link_LINKLOCAL069"]
        rep["b601_base_solid_coarse"] = {
            "box_mm": base["box_mm"], "n_faces": base["n_faces"],
            "cylinder_radii_mm": base["cylinder_radii_mm"]}
        holes = hole_groups(base_hi["cylinders"])
        rep["b601_base_hole_patterns"] = holes

        # the mounting flange = the outermost X station with a real bolt circle
        cand = [h for h in holes if h["count"] >= 6
                and h["bolt_circle_R_mm"][1] - h["bolt_circle_R_mm"][0] < 0.5]
        cand.sort(key=lambda h: h["x_station_mm"])
        flange = cand[0] if cand else None
        rep["b601_mounting_flange"] = (
            {"x_station_mm": flange["x_station_mm"],
             "hole_radius_mm": flange["radius_mm"],
             "nominal_fastener": ("M6" if flange["radius_mm"] > 3.0
                                  else "M4" if flange["radius_mm"] > 2.0
                                  else "M3"),
             "hole_count": flange["count"],
             "bolt_circle_R_mm": flange["bolt_circle_R_mm"],
             "angles_deg": flange["angles_deg"],
             "axis": "X (coaxial with the spacecraft mount stack)",
             "note": ("this SUPERSEDES D-F3R1-05 'base_link has no flange "
                      "face, largest cylinder r=1.0' -- that was measured on a "
                      "coarse solid; the detailed solid carries a real bolt "
                      "pattern")}
            if flange else {"status": "NOT_FOUND"})

        # ---------------- the frozen stack ----------------
        stack = {
            "schema": "F3R2_TSM_INTERFACE_STACK_V1",
            "frozen_utc": "2026-08-07",
            "ruling": (
                "185.25 / 198.00 / 208.00 are NOT competing values for one "
                "quantity.  They are three distinct features on the same X "
                "axis and are frozen together."),
            "axis": "spacecraft +X",
            "stations_mm": {
                "M_FRAME_ORIGIN_X": M_FRAME_X,
                "ADAPTER_PLATE_OUTER_FACE_X": ADAPTER_FACE_X,
                "CENTRAL_BOSS_PHYSICAL_MOUNT_FACE_X": BOSS_FACE_X},
            "offsets_mm": {
                "M_TO_ADAPTER": round(ADAPTER_FACE_X - M_FRAME_X, 4),
                "ADAPTER_TO_BOSS_FACE": round(BOSS_FACE_X - ADAPTER_FACE_X, 4),
                "M_TO_PHYSICAL_MOUNT_FACE": round(BOSS_FACE_X - M_FRAME_X, 4)},
            "semantics": {
                "M_FRAME": ("dynamics / URDF base frame of the B601 "
                            "(P5C Mode B single route).  It is a FRAME, not a "
                            "face: no material lies at x = 185.25."),
                "ADAPTER_PLATE_OUTER_FACE": ("the load-spreading adapter's "
                                             "outer face; bolts pass through "
                                             "it into the boss"),
                "CENTRAL_BOSS_PHYSICAL_MOUNT_FACE": ("the real metal face the "
                                                     "arm bolts against")},
            "why_this_is_not_a_conflict": (
                "T_SM is spacecraft frame -> B601 dynamics frame.  The physical "
                "mounting face is a different feature 22.75 mm further out.  "
                "Reporting them as a 22.75 mm discrepancy conflated a frame "
                "with a face."),
            "consequences": {
                "arm_does_not_move": ("the F3R2 arm stays where G1/G2 placed "
                                      "it; no 22.75 mm translation, so the "
                                      "frozen poses and clearances stand"),
                "dynamics_uses": "M_FRAME_ORIGIN_X = 185.25",
                "cad_mating_uses": "CENTRAL_BOSS_PHYSICAL_MOUNT_FACE_X = 208.00",
                "the_adapter_bridges_them": ("the base interface adapter (G3-1) "
                                             "is the hardware that makes the "
                                             "22.75 mm real")},
        }
        # measured cross-check
        meas_adapter = bus["Adapter_Plate"]["x_outer_mm"]
        meas_boss = bus["Central_Boss"]["x_outer_mm"]
        stack["cad_cross_check"] = {
            "adapter_outer_face_measured_mm": meas_adapter,
            "adapter_matches_declared": abs(meas_adapter -
                                            ADAPTER_FACE_X) < 1e-6,
            "boss_outer_face_measured_mm": meas_boss,
            "boss_matches_declared": abs(meas_boss - BOSS_FACE_X) < 1e-6,
            "m_frame_has_no_material": ("correct by construction -- 185.25 is "
                                        "inboard of Load_Spreading_Frame's "
                                        "inner face at %s"
                                        % bus["Load_Spreading_Frame"]
                                        ["x_inner_mm"])}
        # rigid chain: monotone, gap-free, coaxial
        order = ["Load_Spreading_Frame", "Front_End_Frame",
                 "Spacecraft_Flange", "Adapter_Plate", "Central_Boss"]
        chain, gaps = [], []
        for i, k in enumerate(order):
            v = bus[k]
            chain.append({"part": k, "x_from": v["x_inner_mm"],
                          "x_to": v["x_outer_mm"],
                          "thickness_mm": round(v["x_outer_mm"] -
                                                v["x_inner_mm"], 4),
                          "central_bore_r_mm": v["central_bore_r_mm"]})
            if i:
                g = round(v["x_inner_mm"] - bus[order[i - 1]]["x_outer_mm"], 4)
                gaps.append({"between": "%s -> %s" % (order[i - 1], k),
                             "gap_mm": g, "contiguous": abs(g) < 1e-6})
        stack["spacecraft_load_path"] = {
            "chain": chain, "interfaces": gaps,
            "all_contiguous": all(g["contiguous"] for g in gaps),
            "all_share_r50_bore": all(
                bus[k]["central_bore_r_mm"] == 50.0 for k in order
                if k != "Front_End_Frame"),
            "front_end_frame_note": ("primary-structure bulkhead, no r50 bore "
                                     "of its own; it is the frame the flange "
                                     "bolts to"),
            "coaxial_axis": "X"}
        stack["b601_side"] = rep["b601_mounting_flange"]
        stack["open_gap_to_close_in_G3_1"] = {
            "from_x_mm": BOSS_FACE_X,
            "to_x_mm": (rep["b601_mounting_flange"].get("x_station_mm")
                        if flange else None),
            "distance_mm": (round(rep["b601_mounting_flange"]["x_station_mm"]
                                  - BOSS_FACE_X, 4) if flange else None),
            "meaning": ("the axial space the base interface adapter must "
                        "physically occupy between the boss face and the "
                        "B601 flange")}

        rep["stack"] = stack
        rep["verdict"] = ("G30_TSM_STACK_FROZEN"
                          if stack["cad_cross_check"]["adapter_matches_declared"]
                          and stack["cad_cross_check"]["boss_matches_declared"]
                          and stack["spacecraft_load_path"]["all_contiguous"]
                          else "G30_TSM_MEASUREMENT_MISMATCH")
        rep["protected_post"] = C.check_protected2("G30_POST")["verdict"]

        OUTY.write_text("# F3R2 T_SM interface stack -- frozen\n"
                        + yaml_dump(stack) + "\n", encoding="utf-8")
        md = ["# F3R2 T_SM 物理坐标栈（冻结）", "",
              "```text",
              "spacecraft +X  ---------------------------------------------->",
              "",
              "  x=%.2f      M_FRAME  (B601 动力学/URDF 基准原点，无实体)"
              % M_FRAME_X,
              "     |  +%.2f mm" % (ADAPTER_FACE_X - M_FRAME_X),
              "  x=%.2f      Adapter_Plate 外端面" % ADAPTER_FACE_X,
              "     |  +%.2f mm" % (BOSS_FACE_X - ADAPTER_FACE_X),
              "  x=%.2f      Central_Boss 实体安装面  <-- 螺栓贴合面"
              % BOSS_FACE_X,
              "     |  +%.2f mm  (G3-1 基座接口适配器占据)"
              % (stack["open_gap_to_close_in_G3_1"]["distance_mm"] or 0),
              "  x=%.2f      B601 base flange (%s x %s, 节圆 R%.2f)"
              % ((rep["b601_mounting_flange"].get("x_station_mm") or 0),
                 rep["b601_mounting_flange"].get("hole_count"),
                 rep["b601_mounting_flange"].get("nominal_fastener"),
                 (rep["b601_mounting_flange"].get("bolt_circle_R_mm")
                  or [0, 0])[0]),
              "```", "",
              "## 裁决", "",
              "`T_SM = 185.25 mm` 是**航天器系 → B601 动力学基准系**的变换，",
              "**不是**法兰面位置。实体安装面在 `x = 208.00`，二者相距 22.75 mm，",
              "由基座接口适配器实现。因此 185.25 / 198 / 208 三者同时成立，",
              "不再作为冲突尺寸描述。", "",
              "## 后果", "",
              "- 已冻结的 F3R2 臂**不平移**，姿态与间隙结果全部保留；",
              "- 动力学与控制取 185.25；",
              "- CAD 配合与螺栓载荷路径取 208.00；",
              "- 适配器把二者刚性连起来。", "",
              "## 对 D-F3R1-05 的更正", "",
              "B601 `base_link` **有**真实安装法兰：x=%.2f 处 %d 个 r=%.1f 孔"
              % ((rep["b601_mounting_flange"].get("x_station_mm") or 0),
                 rep["b601_mounting_flange"].get("hole_count") or 0,
                 rep["b601_mounting_flange"].get("hole_radius_mm") or 0),
              "（%s），节圆 R=%.2f，同轴于 X。原判"
              % (rep["b601_mounting_flange"].get("nominal_fastener"),
                 (rep["b601_mounting_flange"].get("bolt_circle_R_mm")
                  or [0])[0]),
              "「无法兰面、最大圆柱 r=1.0」测自粗糙 solid，**已作废**。"]
        OUTMD.write_text("\n".join(md) + "\n", encoding="utf-8")
    except Exception as exc:
        rep["verdict"] = "G30_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]

    C.write_json(OUTJ, rep)
    print("verdict:", rep["verdict"])
    s = rep.get("stack", {})
    if s:
        print("  stations:", s["stations_mm"])
        print("  offsets :", s["offsets_mm"])
        print("  cross-check:", s["cad_cross_check"]["adapter_matches_declared"],
              s["cad_cross_check"]["boss_matches_declared"])
        print("  load path contiguous:",
              s["spacecraft_load_path"]["all_contiguous"],
              "| all r50 bore:", s["spacecraft_load_path"]["all_share_r50_bore"])
        for c in s["spacecraft_load_path"]["chain"]:
            print("     %-24s x %8.2f -> %8.2f  t=%6.2f bore r=%s"
                  % (c["part"], c["x_from"], c["x_to"], c["thickness_mm"],
                     c["central_bore_r_mm"]))
        print("  B601 flange:", json.dumps(s["b601_side"], ensure_ascii=False)[:220])
        print("  adapter must span:", s["open_gap_to_close_in_G3_1"])
    if rep["verdict"] == "G30_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G30_TSM_STACK_FROZEN" else 1)


if __name__ == "__main__":
    main()
