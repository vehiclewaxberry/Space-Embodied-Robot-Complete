# -*- coding: utf-8 -*-
"""Same-physical-point surface-stress convergence probe for the Z series."""
import json, os, glob, math
HERE = os.path.dirname(os.path.abspath(__file__))
B = {}
for p in glob.glob(os.path.join(HERE, "jobs_b", "_extract_b", "*.json")):
    r = json.load(open(p)); B[r["job_name"]] = r
ZS = [("kz1", "l3_mm_fine", 1), ("kz2", "z2_zr_n20k2", 2), ("kz3", "t3_tt_fine", 3),
      ("kz4", "z4_zr_n20k4", 4), ("kz6", "z6_zr_n20k6", 6)]
M4 = [(15.494, 42.4393), (-42.5096, 15.3917), (-15.4621, -42.612), (42.5416, -15.5644)]
case = "capture_150kg_qs"

maps = {}
for tag, lv, kz in ZS:
    r = B["fea1b_%s_%s_c3d8i" % (case, lv)]
    maps[tag] = r["stage_a_top_surface_nodal_averaged_mises_by_xy"]
    print("%-4s nodes on Stage A top surface = %d  status=%s" % (
        tag, r["stage_a_top_surface_node_count"], r["nodal_averaged_stress_status"]))
common = set(maps["kz1"])
for t in maps:
    common &= set(maps[t])
print("common (x,y) points across all 5 levels:", len(common))

def d4(k):
    x, y = [float(t) for t in k.split("|")]
    return min(math.hypot(x - a, y - b) for a, b in M4)

print()
print("### SAME-NODE nodal-averaged surface von Mises, Stage A top face, 150 kg")
for label, lo, hi in [("PATCH r<=12", 0.0, 12.0), ("COLLAR 12-25", 12.0, 25.0),
                      ("COLLAR 25-40", 25.0, 40.0), ("ALL", 0.0, 1e9)]:
    sel = sorted(k for k in common if lo < d4(k) + 1e-12 and d4(k) <= hi)
    if not sel:
        continue
    # max over the FIXED point set at each level
    vals = [max(maps[t][k] for k in sel) for t, _l, _k in ZS]
    ch = [100.0 * (vals[i] / vals[i - 1] - 1) for i in range(1, len(vals))]
    print(" %-13s n=%3d  max over fixed set: %s" % (
        label, len(sel), " ".join("%.6f" % v for v in vals)))
    print("               successive change:  %s" % " ".join("%+7.3f%%" % c for c in ch))
    # single hottest FIXED point (chosen at the finest level, then tracked)
    hot = max(sel, key=lambda k: maps["kz6"][k])
    v2 = [maps[t][hot] for t, _l, _k in ZS]
    c2 = [100.0 * (v2[i] / v2[i - 1] - 1) for i in range(1, len(v2))]
    print("               tracked node (%s, d_M4=%.3f mm): %s" % (
        hot, d4(hot), " ".join("%.6f" % v for v in v2)))
    print("               successive change:  %s" % " ".join("%+7.3f%%" % c for c in c2))

print()
print("### element-averaged (moving centroid) vs nodal-averaged (fixed node)")
print("%-5s %-9s %-14s %-14s %-14s" % ("kz", "top_z", "el_avg_peak", "nodal_avg_peak", "collar12_25_nodal"))
for tag, lv, kz in ZS:
    r = B["fea1b_%s_%s_c3d8i" % (case, lv)]
    print("%-5s %-9.4f %-14.6f %-14.6f %-14.6f" % (
        tag, 30.75 - 2.0 / kz,
        r["peak_mises_element_averaged"]["value_MPa"],
        r["peak_mises_nodal_averaged"]["value_MPa"],
        r["stage_a_top_surface_region_maxima"]["COLLAR_12_TO_25MM"]["max_MPa"]))
    print("      peak nodal-averaged at %s  d_M4=%.3f near_constraint=%s" % (
        [round(c, 3) for c in r["peak_mises_nodal_averaged"]["node_coords_mm"]],
        min(math.hypot(r["peak_mises_nodal_averaged"]["node_coords_mm"][0] - a,
                       r["peak_mises_nodal_averaged"]["node_coords_mm"][1] - b)
            for a, b in M4),
        r["peak_mises_nodal_averaged"]["near_point_constraint"]))
