#!/usr/bin/env python3
"""Compute saddle/envelope vertical relationships from the v2 open-report bboxes.

No CAD launch needed: the v2 macro already exported every object's bounding box.
This answers audit question 15.8 "is Mid held at 2 mm nominal non-contact" at the
bbox level, and flags whether the arm-stow envelope block rests on the saddles.

bbox-level result only -- a bbox gap is an upper bound on the true surface gap and
cannot prove non-contact for non-prismatic shapes. Recorded as such.
"""
import json
import os

AUDIT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(AUDIT, "01_native_cad", "F3_TOP_ASSEMBLY_OPEN_REPORT_V2.json")
V1 = os.path.join(AUDIT, "01_native_cad", "F3_TOP_ASSEMBLY_OPEN_REPORT.json")
OUT = os.path.join(AUDIT, "02_configuration", "F3_SADDLE_GAP_BBOX_ANALYSIS.json")

# frozen S3 nominal values (F3_P5A_SOURCE_GEOMETRY_MANIFEST + F3_P5_0 gate)
FROZEN = {
    "native_STOWED041": {"role": "G07_AFT_SADDLE", "x": [-20.0, 0.0], "top_z": 261.08},
    "native_STOWED043": {"role": "G08_FWD_SADDLE", "x": [160.0, 180.0], "top_z": 209.42},
    "native_STOWED042": {"role": "MID_SADDLE", "x": [80.0, 100.0], "top_z": 214.92},
}
ENVELOPE = "native_STOWED046"
MID_NOMINAL_GAP_MM = 2.0


def load_objects():
    """v1 report carries the full 206-object bbox inventory."""
    with open(V1, "r", encoding="utf-8") as fh:
        return {o["name"]: o for o in json.load(fh)["objects"]}


def overlaps(a, b):
    """XY footprint overlap between two bbox lists [xmin,ymin,zmin,xmax,ymax,zmax]."""
    return not (a[3] < b[0] or a[0] > b[3] or a[4] < b[1] or a[1] > b[4])


def main():
    objs = load_objects()
    rep = {
        "schema": "F3_SADDLE_GAP_BBOX_ANALYSIS_V1",
        "method": "axis-aligned bounding boxes exported by read-only FreeCAD open; "
                  "no CAD modification; bbox gap is an UPPER BOUND on true surface gap",
        "limitation": "bbox analysis cannot prove surface non-contact; a zero bbox gap "
                      "means potential contact, a positive bbox gap means the solids "
                      "cannot touch within that footprint",
        "saddles": {},
    }

    env = objs.get(ENVELOPE)
    if env and env.get("bbox_mm"):
        rep["arm_stow_envelope"] = {
            "name": ENVELOPE, "bbox_mm": env["bbox_mm"],
            "volume_mm3": env.get("volume_mm3"),
            "z_bottom_mm": env["bbox_mm"][2], "z_top_mm": env["bbox_mm"][5],
        }

    for name, spec in FROZEN.items():
        o = objs.get(name)
        if not o or not o.get("bbox_mm"):
            rep["saddles"][spec["role"]] = {"status": "NOT_FOUND_OR_NO_SHAPE", "name": name}
            continue
        bb = o["bbox_mm"]
        entry = {
            "name": name,
            "bbox_mm": bb,
            "x_range_mm": [bb[0], bb[3]],
            "frozen_x_range_mm": spec["x"],
            "x_matches_frozen": [bb[0], bb[3]] == spec["x"],
            "top_z_mm": bb[5],
            "frozen_nominal_top_z_mm": spec["top_z"],
            "top_z_matches_frozen": abs(bb[5] - spec["top_z"]) < 1e-6,
            "bottom_z_mm": bb[2],
            "height_mm": round(bb[5] - bb[2], 3),
            "footprint_mm": [round(bb[3] - bb[0], 3), round(bb[4] - bb[1], 3)],
            "volume_mm3": o.get("volume_mm3"),
            "solids": o.get("solids"),
            "shape_valid": o.get("valid"),
        }

        above = []
        for other_name, other in objs.items():
            if other_name == name or not other.get("bbox_mm"):
                continue
            ob = other["bbox_mm"]
            if not overlaps(bb, ob):
                continue
            if ob[2] >= bb[5] - 1e-9:
                above.append({"name": other_name,
                              "bbox_gap_mm": round(ob[2] - bb[5], 4),
                              "z_range_mm": [ob[2], ob[5]]})
        above.sort(key=lambda d: d["bbox_gap_mm"])
        entry["solids_above_within_footprint"] = above[:8]
        entry["nearest_bbox_gap_above_mm"] = above[0]["bbox_gap_mm"] if above else None
        entry["nothing_above_footprint"] = not above

        if spec["role"] == "MID_SADDLE":
            g = entry["nearest_bbox_gap_above_mm"]
            entry["mid_2mm_nominal_check"] = (
                "NO_SOLID_ABOVE_FOOTPRINT_CANNOT_EVALUATE" if g is None else
                "BBOX_GAP_EQUALS_2MM_NOMINAL" if abs(g - MID_NOMINAL_GAP_MM) < 1e-6 else
                "BBOX_GAP_%.4fMM_VS_NOMINAL_2MM" % g)
        rep["saddles"][spec["role"]] = entry

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)

    if "arm_stow_envelope" in rep:
        e = rep["arm_stow_envelope"]
        print("arm_stow_envelope %s  z=[%.2f, %.2f]  vol=%.0f mm3"
              % (e["name"], e["z_bottom_mm"], e["z_top_mm"], e["volume_mm3"]))
    for role, s in rep["saddles"].items():
        if s.get("status"):
            print("%-16s %s" % (role, s["status"]))
            continue
        print("\n%-16s %s" % (role, s["name"]))
        print("   x=%s frozen=%s match=%s" % (s["x_range_mm"], s["frozen_x_range_mm"],
                                              s["x_matches_frozen"]))
        print("   top_z=%.3f frozen=%.3f match=%s"
              % (s["top_z_mm"], s["frozen_nominal_top_z_mm"], s["top_z_matches_frozen"]))
        print("   height=%.1f footprint=%s vol=%.0f solids=%s valid=%s"
              % (s["height_mm"], s["footprint_mm"], s["volume_mm3"],
                 s["solids"], s["shape_valid"]))
        print("   nearest bbox gap above = %s" % s["nearest_bbox_gap_above_mm"])
        for a in s["solids_above_within_footprint"][:4]:
            print("      %-22s gap=%8.3f  z=%s" % (a["name"], a["bbox_gap_mm"],
                                                   a["z_range_mm"]))
        if "mid_2mm_nominal_check" in s:
            print("   MID CHECK -> %s" % s["mid_2mm_nominal_check"])
    print("\nwritten -> %s" % OUT)


if __name__ == "__main__":
    main()
