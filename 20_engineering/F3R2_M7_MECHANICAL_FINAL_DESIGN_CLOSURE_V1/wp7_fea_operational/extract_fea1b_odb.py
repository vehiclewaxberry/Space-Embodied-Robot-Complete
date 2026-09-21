# -*- coding: utf-8 -*-
"""
FEA-1B ODB extractor -- M7 / WP7 (FEA_OPERATIONAL), ODR-11 three-layer evidence.

Run with:  abaqus python extract_fea1b_odb.py <jobs_dir> <out_subdir>
e.g.       abaqus python extract_fea1b_odb.py jobs_b _extract_b
           abaqus python extract_fea1b_odb.py jobs   _extract_b_baseline

The SAME extractor is applied to the FEA-1 C3D8R baseline ODBs and to the new
FEA-1B ODBs, so every baseline-vs-new comparison uses identical post-processing.
Nothing is defaulted or zero-filled: any quantity the ODB does not contain is
written as null with an explicit *_status string.

Extracted per job (all from real ODB bytes + the sibling .inp for the applied
load of record):
  LAYER 1  solver version, odb/dat bytes, frame count, reaction sums and
           reaction-balance residuals about the load reference point.
  LAYER 2  peak IP von Mises AND peak element-averaged (centroidal) von Mises,
           per zone, plus:
             * far-field peaks with a FIXED geometric exclusion of the point
               constraints (15 mm from any bolt centre) and of the staircase
               circular boundaries (10 mm band about r = 20 / 50 / 75), so the
               compared region is the same physical volume at every mesh level;
             * volume-weighted mean von Mises per zone (mesh-independent
               integral measure);
             * radial region/path profile of element-averaged von Mises in
               5 mm annuli for Stage A and Stage B;
             * energy history ALLIE / ALLSE / ALLAE / ALLWK / ETOTAL.
  Reference nodes are identified automatically as nodes carried by no element,
  so the same code works for both node-numbering schemes.

Element volumes use the axis-aligned bounding box, which is exact for this
structured lattice (every element is a rectangular box by construction).
"""

import json
import math
import os
import sys

from odbAccess import openOdb
from abaqusConstants import ELEMENT_NODAL

HERE = os.path.dirname(os.path.abspath(__file__))
ENERGY_KEYS = ("ALLIE", "ALLSE", "ALLAE", "ALLWK", "ETOTAL", "ALLKE", "ALLPD",
               "ALLVD", "ALLCD", "ALLSD")

# pinned bolt-pattern centres (identical to make_fea1_input.GEOM)
M6_CENTRES = [(70.0, 70.0), (70.0, -70.0), (-70.0, 70.0), (-70.0, -70.0)]
M5_CENTRES = [(62.5 * math.cos(math.radians(22.5 + 45.0 * k)),
               62.5 * math.sin(math.radians(22.5 + 45.0 * k))) for k in range(8)]
M4_CENTRES = [(15.494, 42.4393), (-42.5096, 15.3917),
              (-15.4621, -42.612), (42.5416, -15.5644)]
BOLT_CENTRES = M6_CENTRES + M5_CENTRES + M4_CENTRES
BOLT_EXCL_MM = 15.0
STEP_RADII = (20.0, 50.0, 75.0)
STEP_BAND_MM = 10.0
RADIAL_BIN_MM = 5.0


def safe_str(obj):
    try:
        s = obj if isinstance(obj, type(b"")) else str(obj)
    except Exception as exc:                                   # noqa: BLE001
        return "UNREADABLE_%s" % type(exc).__name__
    if isinstance(s, type(b"")):
        for enc in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                return s.decode(enc)
            except Exception:                                  # noqa: BLE001
                continue
        return "UNDECODABLE_BYTES"
    try:
        s.encode("utf-8")
        return s
    except Exception:                                          # noqa: BLE001
        return "UNDECODABLE_STR"


def mises(c):
    s11, s22, s33, s12, s13, s23 = c
    return math.sqrt(0.5 * ((s11 - s22) ** 2 + (s22 - s33) ** 2 + (s33 - s11) ** 2)
                     + 3.0 * (s12 * s12 + s13 * s13 + s23 * s23))


def cross(r, f):
    return (r[1] * f[2] - r[2] * f[1],
            r[2] * f[0] - r[0] * f[2],
            r[0] * f[1] - r[1] * f[0])


def parse_deck_load(inp_path):
    """Applied load of record, read from the solved deck itself."""
    out = {"deck_path": inp_path.replace("\\", "/"), "cload": [], "eltype": None}
    if not os.path.isfile(inp_path):
        out["status"] = "DECK_NOT_FOUND_BESIDE_ODB"
        return out
    in_cload = False
    with open(inp_path) as f:
        for line in f:
            u = line.strip().upper()
            if u.startswith("*ELEMENT,") and "TYPE=" in u and "OUTPUT" not in u:
                out["eltype"] = u.split("TYPE=")[1].split(",")[0].strip()
            if u.startswith("*"):
                in_cload = u.startswith("*CLOAD")
                continue
            if in_cload and line.strip():
                p = [x.strip() for x in line.split(",")]
                if len(p) >= 3:
                    out["cload"].append([int(p[0]), int(p[1]), float(p[2])])
    out["status"] = "OK"
    return out


def region_flags(cx, cy):
    near_bolt = False
    for bx, by in BOLT_CENTRES:
        if math.hypot(cx - bx, cy - by) <= BOLT_EXCL_MM:
            near_bolt = True
            break
    rc = math.hypot(cx, cy)
    near_step = any(abs(rc - r) <= STEP_BAND_MM for r in STEP_RADII)
    return near_bolt, near_step, rc


def extract(jobs_dir, job):
    path = os.path.join(jobs_dir, job + ".odb")
    odb = openOdb(path, readOnly=True)
    res = {"job_name": job, "odb_path": path.replace("\\", "/"),
           "odb_bytes": os.path.getsize(path)}
    dat = os.path.join(jobs_dir, job + ".dat")
    res["dat_bytes"] = os.path.getsize(dat) if os.path.isfile(dat) else None
    res["dat_status"] = "OK" if res["dat_bytes"] else "DAT_MISSING"
    res["applied_load_of_record"] = parse_deck_load(
        os.path.join(jobs_dir, job + ".inp"))

    jd = odb.jobData
    res["solver"] = {"version": safe_str(jd.version),
                     "precision": safe_str(jd.precision),
                     "analysis_code": safe_str(jd.analysisCode),
                     "creation_time": safe_str(jd.creationTime)}

    inames = list(odb.rootAssembly.instances.keys())
    inst = odb.rootAssembly.instances[inames[0]]
    res["instances"] = inames

    ncoord = {}
    for n in inst.nodes:
        ncoord[n.label] = tuple(float(c) for c in n.coordinates)
    econn = {}
    for e in inst.elements:
        econn[e.label] = tuple(e.connectivity)
    used = set()
    for c in econn.values():
        used.update(c)
    ref_nodes = sorted(set(ncoord.keys()) - used)
    res["reference_nodes_detected"] = ref_nodes
    rp = None
    for nl in ref_nodes:
        x, y, z = ncoord[nl]
        if abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z - 30.75) < 1e-9:
            rp = nl
    res["load_reference_node"] = rp
    res["load_reference_node_status"] = (
        "OK" if rp is not None else "ARM_RP_NOT_FOUND_AT_0_0_30_75")
    rp_coord = ncoord[rp] if rp is not None else (0.0, 0.0, 30.75)

    zone_of = {}
    for zname in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
        if zname in inst.elementSets.keys():
            for e in inst.elementSets[zname].elements:
                zone_of[e.label] = zname
    probe_labels = []
    if "EPROBES" in inst.elementSets.keys():
        probe_labels = sorted(e.label for e in inst.elementSets["EPROBES"].elements)
    fixed_labels = set()
    if "NFIXED" in inst.nodeSets.keys():
        fixed_labels = set(n.label for n in inst.nodeSets["NFIXED"].nodes)

    # element geometry (axis-aligned boxes)
    egeo = {}
    for el, conn in econn.items():
        xs = [ncoord[n][0] for n in conn]
        ys = [ncoord[n][1] for n in conn]
        zs = [ncoord[n][2] for n in conn]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        cz = sum(zs) / len(zs)
        vol = (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))
        nb, ns, rc = region_flags(cx, cy)
        egeo[el] = {"c": (cx, cy, cz), "v": vol, "r": rc,
                    "near_bolt": nb, "near_step": ns,
                    "far_field": (not nb) and (not ns)}
    res["model"] = {
        "n_nodes_total": len(ncoord), "n_structural_nodes": len(used),
        "n_elements": len(econn), "n_fixed_nodes": len(fixed_labels),
        "probe_elements": probe_labels,
        "element_volume_total_mm3": sum(g["v"] for g in egeo.values()),
        "n_far_field_elements": sum(1 for g in egeo.values() if g["far_field"]),
        "far_field_rule": {
            "bolt_centre_exclusion_radius_mm": BOLT_EXCL_MM,
            "stepped_boundary_exclusion_band_mm": STEP_BAND_MM,
            "stepped_radii_mm": list(STEP_RADII),
            "fixed_geometric_not_mesh_proportional": True},
    }

    step = odb.steps["QS_STEP"]
    res["step"] = {"name": "QS_STEP", "n_frames": len(step.frames),
                   "procedure": safe_str(step.procedure),
                   "total_time": float(step.timePeriod)}
    frame = step.frames[-1]
    res["frame_value"] = float(frame.frameValue)
    fo = frame.fieldOutputs
    res["field_keys"] = sorted(fo.keys())

    # ---------------- stress ------------------------------------------------
    if "S" in fo.keys():
        ip_peak = None                       # (vm, el, ip, comps)
        acc = {}                             # el -> [sum comps, n]
        for v in fo["S"].values:
            el = int(v.elementLabel)
            d = [float(x) for x in v.data]
            vm = float(v.mises)
            if ip_peak is None or vm > ip_peak[0]:
                ip_peak = (vm, el, int(v.integrationPoint), d)
            a = acc.get(el)
            if a is None:
                acc[el] = [list(d), 1]
            else:
                for k in range(6):
                    a[0][k] += d[k]
                a[1] += 1
        el_avg = {}
        for el, (s, n) in acc.items():
            el_avg[el] = mises([c / float(n) for c in s])
        res["integration_points_per_element"] = (
            sorted(set(n for _s, n in acc.values())))

        def loc(el):
            g = egeo.get(el, {})
            return {"element": el, "zone": zone_of.get(el),
                    "centroid_mm": list(g.get("c", (None, None, None))),
                    "radius_mm": g.get("r"),
                    "near_point_constraint": g.get("near_bolt"),
                    "near_stepped_boundary": g.get("near_step"),
                    "in_far_field_region": g.get("far_field")}

        res["peak_mises_ip"] = dict(loc(ip_peak[1]))
        res["peak_mises_ip"].update({
            "value_MPa": ip_peak[0], "integration_point": ip_peak[2],
            "stress_components_S11_S22_S33_S12_S13_S23": ip_peak[3]})
        best = max(el_avg.items(), key=lambda kv: kv[1])
        res["peak_mises_element_averaged"] = dict(loc(best[0]))
        res["peak_mises_element_averaged"]["value_MPa"] = best[1]

        # per zone
        pz = {}
        for z in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
            els = [e for e in el_avg if zone_of.get(e) == z]
            if not els:
                pz[z] = None
                continue
            b = max(els, key=lambda e: el_avg[e])
            vsum = sum(egeo[e]["v"] for e in els)
            wmean = sum(el_avg[e] * egeo[e]["v"] for e in els) / vsum
            ff = [e for e in els if egeo[e]["far_field"]]
            zb = {"peak_element_averaged_MPa": el_avg[b],
                  "peak_element_averaged_at": loc(b),
                  "volume_weighted_mean_MPa": wmean,
                  "zone_volume_mm3": vsum,
                  "n_elements": len(els),
                  "n_far_field_elements": len(ff)}
            if ff:
                bf = max(ff, key=lambda e: el_avg[e])
                zb["far_field_peak_element_averaged_MPa"] = el_avg[bf]
                zb["far_field_peak_at"] = loc(bf)
                vs = sum(egeo[e]["v"] for e in ff)
                zb["far_field_volume_weighted_mean_MPa"] = (
                    sum(el_avg[e] * egeo[e]["v"] for e in ff) / vs)
            else:
                zb["far_field_peak_element_averaged_MPa"] = None
                zb["far_field_peak_status"] = "NO_FAR_FIELD_ELEMENT_IN_ZONE"
            pz[z] = zb
        res["per_zone"] = pz

        ff_all = [e for e in el_avg if egeo[e]["far_field"]]
        if ff_all:
            bf = max(ff_all, key=lambda e: el_avg[e])
            res["far_field_peak_element_averaged"] = dict(loc(bf))
            res["far_field_peak_element_averaged"]["value_MPa"] = el_avg[bf]
        else:
            res["far_field_peak_element_averaged"] = None
        vtot = sum(egeo[e]["v"] for e in el_avg)
        res["model_volume_weighted_mean_mises_MPa"] = (
            sum(el_avg[e] * egeo[e]["v"] for e in el_avg) / vtot)

        # radial region / path profile (element-averaged), 5 mm annuli
        prof = {}
        for z in ("ESTAGEA", "ESTAGEB", "EBRIDGE"):
            bins = {}
            for e in el_avg:
                if zone_of.get(e) != z:
                    continue
                b = int(egeo[e]["r"] // RADIAL_BIN_MM)
                rec = bins.setdefault(b, {"n": 0, "max": 0.0, "vsum": 0.0,
                                          "wsum": 0.0})
                rec["n"] += 1
                rec["max"] = max(rec["max"], el_avg[e])
                rec["vsum"] += egeo[e]["v"]
                rec["wsum"] += el_avg[e] * egeo[e]["v"]
            prof[z] = [{"r_lo_mm": b * RADIAL_BIN_MM,
                        "r_hi_mm": (b + 1) * RADIAL_BIN_MM,
                        "n_elements": r["n"],
                        "max_element_averaged_MPa": r["max"],
                        "volume_weighted_mean_MPa": r["wsum"] / r["vsum"]}
                       for b, r in sorted(bins.items())]
        res["radial_region_profile_element_averaged"] = prof

        # ODR-11 singularity rule: fixed-geometry regions around the arm-base
        # kinematic coupling. PATCH = at/inside the rigid node patch (contains
        # the constraint singularity). COLLAR = a fixed annular band clear of
        # the patch boundary; this is the design-relevant, singularity-free
        # region stress. Both regions are the SAME physical volume at every
        # mesh level, so their convergence is meaningful.
        def m4_dist(cx, cy):
            return min(math.hypot(cx - bx, cy - by) for bx, by in M4_CENTRES)
        regs = {"SPIDER_PATCH_R_LE_12MM": (0.0, 12.0),
                "SPIDER_COLLAR_12_TO_25MM": (12.0, 25.0),
                "SPIDER_COLLAR_25_TO_40MM": (25.0, 40.0)}
        out_r = {}
        for rname, (lo, hi) in regs.items():
            els = [e for e in el_avg
                   if zone_of.get(e) == "ESTAGEA"
                   and lo < m4_dist(egeo[e]["c"][0], egeo[e]["c"][1]) + 1e-12
                   and m4_dist(egeo[e]["c"][0], egeo[e]["c"][1]) <= hi]
            if not els:
                out_r[rname] = None
                continue
            vs = sum(egeo[e]["v"] for e in els)
            b = max(els, key=lambda e: el_avg[e])
            out_r[rname] = {
                "n_elements": len(els), "region_volume_mm3": vs,
                "max_element_averaged_MPa": el_avg[b],
                "max_at": loc(b),
                "volume_weighted_mean_MPa":
                    sum(el_avg[e] * egeo[e]["v"] for e in els) / vs,
                "rule": "ESTAGEA elements whose centroid xy distance to the "
                        "nearest as-built M4 centre lies in (%.1f, %.1f] mm"
                        % (lo, hi)}
        res["spider_fixed_geometry_regions"] = out_r

        # -------- nodal-extrapolated (ELEMENT_NODAL, node-averaged) stress ----
        # Element-averaged values are sampled AT THE ELEMENT CENTROID, which
        # moves toward the loaded surface as the through-thickness layer count
        # rises (Stage A top-element centroid z = 30.75 - 2/kz mm). A trend in
        # that quantity therefore mixes discretization error with a moving
        # sample point. Nodal-extrapolated, node-averaged stress is evaluated
        # AT THE NODES, and for the fixed-in-plane Z series the top-surface
        # node coordinates are identical at every kz, so the same physical
        # points are compared. This is the admissible convergence datum for a
        # bending-dominated surface stress.
        try:
            sen = fo["S"].getSubset(position=ELEMENT_NODAL)
            accn = {}
            for v in sen.values:
                nl = int(v.nodeLabel)
                d = [float(x) for x in v.data]
                a = accn.get(nl)
                if a is None:
                    accn[nl] = [list(d), 1]
                else:
                    for k in range(6):
                        a[0][k] += d[k]
                    a[1] += 1
            nvm = {}
            for nl, (s, n) in accn.items():
                nvm[nl] = mises([c / float(n) for c in s])
            res["nodal_averaged_stress_status"] = "OK"
            bn = max(nvm.items(), key=lambda kv: kv[1])
            nb, ns, rc = region_flags(ncoord[bn[0]][0], ncoord[bn[0]][1])
            res["peak_mises_nodal_averaged"] = {
                "value_MPa": bn[1], "node": bn[0],
                "node_coords_mm": list(ncoord[bn[0]]),
                "radius_mm": rc, "near_point_constraint": nb,
                "near_stepped_boundary": ns,
                "n_contributing_element_nodal_values": accn[bn[0]][1]}
            # Stage A top surface map, keyed by rounded (x,y) so the SAME
            # physical point can be tracked across levels with different
            # node numbering
            top_z = 30.75
            smap = {}
            for nl, vmv in nvm.items():
                x, y, z = ncoord[nl]
                if abs(z - top_z) > 1e-6:
                    continue
                smap["%.4f|%.4f" % (x, y)] = vmv
            res["stage_a_top_surface_nodal_averaged_mises_by_xy"] = smap
            res["stage_a_top_surface_node_count"] = len(smap)
            # fixed-geometry region maxima on that surface
            surf = {}
            for rname, (lo, hi) in {"COLLAR_12_TO_25MM": (12.0, 25.0),
                                    "COLLAR_25_TO_40MM": (25.0, 40.0),
                                    "PATCH_R_LE_12MM": (0.0, 12.0)}.items():
                sel = []
                for k, vmv in smap.items():
                    x, y = [float(t) for t in k.split("|")]
                    dd = min(math.hypot(x - bx, y - by) for bx, by in M4_CENTRES)
                    if lo < dd + 1e-12 and dd <= hi:
                        sel.append((k, vmv))
                if sel:
                    b = max(sel, key=lambda kv: kv[1])
                    surf[rname] = {"n_nodes": len(sel), "max_MPa": b[1],
                                   "max_at_xy": b[0],
                                   "mean_MPa": sum(v for _k, v in sel) / len(sel)}
                else:
                    surf[rname] = None
            res["stage_a_top_surface_region_maxima"] = surf
        except Exception as exc:                                # noqa: BLE001
            res["peak_mises_nodal_averaged"] = None
            res["nodal_averaged_stress_status"] = (
                "ELEMENT_NODAL_SUBSET_UNAVAILABLE_%s: %s"
                % (type(exc).__name__, exc))

        res["probe_mises"] = {
            str(e): {"element_averaged_MPa": el_avg.get(e),
                     "zone": zone_of.get(e),
                     "centroid_mm": list(egeo[e]["c"]) if e in egeo else None}
            for e in probe_labels}
    else:
        res["peak_mises_ip"] = None
        res["peak_mises_status"] = "S_FIELD_ABSENT_IN_ODB"

    # ---------------- displacement -----------------------------------------
    if "U" in fo.keys():
        best = None
        rp_u = None
        for v in fo["U"].values:
            lab = int(v.nodeLabel)
            d = [float(x) for x in v.data]
            if lab == rp:
                rp_u = d
                continue
            if lab not in used:
                continue
            mag = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            if best is None or mag > best[0]:
                best = (mag, lab, d)
        res["peak_disp"] = {"magnitude_mm": best[0], "node": best[1],
                            "node_coords_mm": list(ncoord[best[1]]),
                            "U1_U2_U3_mm": best[2]}
        res["rp_translation_mm"] = rp_u
        res["rp_translation_status"] = "OK" if rp_u else "RP_NOT_IN_U_FIELD"
    else:
        res["peak_disp"] = None
        res["peak_disp_status"] = "U_FIELD_ABSENT_IN_ODB"

    if "UR" in fo.keys():
        rp_ur = None
        for v in fo["UR"].values:
            if int(v.nodeLabel) == rp:
                rp_ur = [float(x) for x in v.data]
        res["rp_rotation_rad"] = rp_ur
        res["rp_rotation_status"] = "OK" if rp_ur else "RP_NOT_IN_UR_FIELD"
    else:
        res["rp_rotation_rad"] = None
        res["rp_rotation_status"] = "UR_FIELD_ABSENT_IN_ODB"

    # ---------------- reactions --------------------------------------------
    if "RF" in fo.keys():
        sf = [0.0, 0.0, 0.0]
        mo = [0.0, 0.0, 0.0]
        n_r = 0
        off = []
        mx = None
        for v in fo["RF"].values:
            lab = int(v.nodeLabel)
            if lab not in ncoord:
                continue
            d = [float(x) for x in v.data]
            if abs(d[0]) + abs(d[1]) + abs(d[2]) == 0.0:
                continue
            n_r += 1
            if lab not in fixed_labels:
                off.append(lab)
            for k in range(3):
                sf[k] += d[k]
            c = cross(ncoord[lab], d)
            for k in range(3):
                mo[k] += c[k]
            mag = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
            if mx is None or mag > mx[0]:
                mx = (mag, lab, d)
        m_rp = list(mo)
        c = cross((-rp_coord[0], -rp_coord[1], -rp_coord[2]), sf)
        for k in range(3):
            m_rp[k] += c[k]
        res["reactions"] = {
            "n_nodes_with_nonzero_RF": n_r,
            "nonzero_RF_nodes_outside_NFIXED": sorted(off),
            "sum_RF_N": sf,
            "sum_reaction_moment_about_origin_N_mm": mo,
            "sum_reaction_moment_about_RP_N_mm": m_rp,
            "max_single_node_RF": ({"magnitude_N": mx[0], "node": mx[1],
                                   "RF_N": mx[2],
                                   "node_coords_mm": list(ncoord[mx[1]])}
                                  if mx else None)}
    else:
        res["reactions"] = None
        res["reactions_status"] = "RF_FIELD_ABSENT_IN_ODB"

    # ---------------- energies ---------------------------------------------
    en = {}
    regions = []
    for rname in step.historyRegions.keys():
        hr = step.historyRegions[rname]
        regions.append(rname)
        for okey in hr.historyOutputs.keys():
            if okey in ENERGY_KEYS:
                data = hr.historyOutputs[okey].data
                if len(data):
                    en[okey] = float(data[-1][1])
    res["history_regions"] = regions
    res["energy_odb"] = en if en else None
    if not en:
        res["energy_odb_status"] = "NO_ENERGY_HISTORY_IN_ODB"

    odb.close()
    return res


def main():
    jd = sys.argv[1] if len(sys.argv) > 1 else "jobs_b"
    od = sys.argv[2] if len(sys.argv) > 2 else "_extract_b"
    jobs_dir = os.path.join(HERE, jd)
    out = os.path.join(jobs_dir, od)
    if not os.path.isdir(out):
        os.makedirs(out)
    jobs = sorted(f[:-4] for f in os.listdir(jobs_dir) if f.endswith(".odb"))
    print("jobs found in %s: %d" % (jd, len(jobs)))
    ok = 0
    for j in jobs:
        try:
            r = extract(jobs_dir, j)
            with open(os.path.join(out, j + ".json"), "w") as f:
                json.dump(r, f, indent=1, sort_keys=True)
            pi = r.get("peak_mises_ip") or {}
            pa = r.get("peak_mises_element_averaged") or {}
            en = r.get("energy_odb") or {}
            allie = en.get("ALLIE")
            allae = en.get("ALLAE")
            frac = (allae / allie) if (allie not in (None, 0.0)
                                       and allae is not None) else None
            print("OK  %-50s ipmax=%.6g  elavg=%.6g  ALLAE/ALLIE=%s" % (
                j, pi.get("value_MPa", float("nan")),
                pa.get("value_MPa", float("nan")),
                ("%.6g" % frac) if frac is not None else "NA"))
            ok += 1
        except Exception as exc:                               # noqa: BLE001
            print("FAIL %-50s %s: %s" % (j, type(exc).__name__, exc))
    print("extracted %d/%d" % (ok, len(jobs)))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
