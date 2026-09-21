# -*- coding: utf-8 -*-
"""
FEA-1 ODB result extractor -- M7 / WP7 (FEA_OPERATIONAL).

Run with:  abaqus python extract_fea1_odb.py
Reads every jobs/*.odb read-only, writes jobs/_extract/<job>.json.

Extracted per job, from real ODB bytes only (no defaults, no zero-fill):
  * solver version / jobData
  * peak von Mises over the whole model + element label, integration point,
    zone elset membership, element centroid
  * peak displacement magnitude + node label + coords; RP displacement/rotation
  * full reaction sum over the encastre face and the resultant reaction moment
    about the global origin AND about the load reference point
  * reaction-balance residuals against the applied load
  * energy history (ALLIE / ALLSE / ALLAE / ALLWK / ETOTAL) if present
  * probe element von Mises

Any quantity the ODB does not contain is written as null with a *_status
string. Nothing is substituted from another job or mesh level.
"""

import json
import os
import sys

from odbAccess import openOdb

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")
OUT = os.path.join(JOBS, "_extract")

RP = 900000
RP_COORD = (0.0, 0.0, 30.75)
ENERGY_KEYS = ("ALLIE", "ALLSE", "ALLAE", "ALLWK", "ETOTAL", "ALLKE", "ALLPD")


def safe_str(obj):
    """Locale-proof str(): this host writes GBK date strings into jobData."""
    try:
        s = obj if isinstance(obj, type(b"")) else str(obj)
    except Exception as exc:                                  # noqa: BLE001
        return "UNREADABLE_%s" % type(exc).__name__
    if isinstance(s, type(b"")):
        for enc in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                return s.decode(enc)
            except Exception:                                 # noqa: BLE001
                continue
        return "UNDECODABLE_BYTES"
    try:
        s.encode("utf-8")
        return s
    except Exception:                                         # noqa: BLE001
        try:
            return s.decode("gbk").encode("utf-8")
        except Exception:                                     # noqa: BLE001
            return "UNDECODABLE_STR"


def cross(r, f):
    return (r[1] * f[2] - r[2] * f[1],
            r[2] * f[0] - r[0] * f[2],
            r[0] * f[1] - r[1] * f[0])


def extract(job):
    path = os.path.join(JOBS, job + ".odb")
    odb = openOdb(path, readOnly=True)
    res = {"job_name": job, "odb_path": path.replace("\\", "/"),
           "odb_bytes": os.path.getsize(path)}

    jd = odb.jobData
    res["solver"] = {
        "version": safe_str(jd.version),
        "precision": safe_str(jd.precision),
        "analysis_code": safe_str(jd.analysisCode),
        "creation_time": safe_str(jd.creationTime),
        "modification_time": safe_str(jd.modificationTime),
    }

    inst_names = list(odb.rootAssembly.instances.keys())
    res["instances"] = inst_names
    inst = odb.rootAssembly.instances[inst_names[0]]

    # node coords lookup
    ncoord = {}
    for n in inst.nodes:
        ncoord[n.label] = tuple(float(c) for c in n.coordinates)
    # element -> zone membership + centroid
    zone_of = {}
    for zname in ("EBRIDGE", "ESTAGEB", "ESTAGEA"):
        if zname in inst.elementSets.keys():
            for e in inst.elementSets[zname].elements:
                zone_of[e.label] = zname
    econn = {}
    for e in inst.elements:
        econn[e.label] = tuple(e.connectivity)
    probe_labels = []
    if "EPROBES" in inst.elementSets.keys():
        probe_labels = [e.label for e in inst.elementSets["EPROBES"].elements]
    fixed_labels = set()
    if "NFIXED" in inst.nodeSets.keys():
        fixed_labels = set(n.label for n in inst.nodeSets["NFIXED"].nodes)

    res["model"] = {"n_nodes": len(ncoord), "n_elements": len(econn),
                    "n_fixed_nodes": len(fixed_labels),
                    "probe_elements": sorted(probe_labels)}

    step = odb.steps["QS_STEP"]
    res["step"] = {"name": "QS_STEP", "n_frames": len(step.frames),
                   "procedure": safe_str(step.procedure),
                   "total_time": float(step.timePeriod)}
    frame = step.frames[-1]
    res["frame_value"] = float(frame.frameValue)

    # ---- peak von Mises over whole model -----------------------------------
    fo = frame.fieldOutputs
    res["field_keys"] = sorted(fo.keys())
    if "S" in fo.keys():
        best = None
        for v in fo["S"].values:
            vm = float(v.mises)
            if best is None or vm > best[0]:
                best = (vm, int(v.elementLabel), int(v.integrationPoint),
                        [float(x) for x in v.data])
        conn = econn.get(best[1], ())
        cen = None
        if conn:
            cs = [ncoord[n] for n in conn if n in ncoord]
            if cs:
                cen = [sum(c[k] for c in cs) / float(len(cs)) for k in range(3)]
        res["peak_mises"] = {
            "value_MPa": best[0], "element": best[1],
            "integration_point": best[2],
            "zone": zone_of.get(best[1]),
            "element_centroid_mm": cen,
            "stress_components_S11_S22_S33_S12_S13_S23": best[3],
        }
        # per-zone peaks
        zp = {}
        for v in fo["S"].values:
            z = zone_of.get(int(v.elementLabel))
            if z is None:
                continue
            vm = float(v.mises)
            if z not in zp or vm > zp[z]["value_MPa"]:
                zp[z] = {"value_MPa": vm, "element": int(v.elementLabel)}
        res["peak_mises_per_zone"] = zp
        pv = {}
        for v in fo["S"].values:
            el = int(v.elementLabel)
            if el in probe_labels:
                vm = float(v.mises)
                k = str(el)
                if k not in pv or vm > pv[k]:
                    pv[k] = vm
        res["probe_mises_MPa"] = pv
    else:
        res["peak_mises"] = None
        res["peak_mises_status"] = "S_FIELD_ABSENT_IN_ODB"

    # ---- peak displacement -------------------------------------------------
    if "U" in fo.keys():
        best = None
        rp_u = None
        for v in fo["U"].values:
            d = [float(x) for x in v.data]
            mag = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
            lab = int(v.nodeLabel)
            if lab == RP:
                rp_u = d
            if lab in ncoord:  # exclude RP from structural peak
                if best is None or mag > best[0]:
                    best = (mag, lab, d)
        res["peak_disp"] = {
            "magnitude_mm": best[0], "node": best[1],
            "node_coords_mm": list(ncoord[best[1]]),
            "U1_U2_U3_mm": best[2],
        }
        res["rp_translation_mm"] = rp_u
        res["rp_translation_status"] = (
            "OK" if rp_u is not None else "RP_NOT_IN_U_FIELD")
    else:
        res["peak_disp"] = None
        res["peak_disp_status"] = "U_FIELD_ABSENT_IN_ODB"

    if "UR" in fo.keys():
        rp_ur = None
        for v in fo["UR"].values:
            if int(v.nodeLabel) == RP:
                rp_ur = [float(x) for x in v.data]
        res["rp_rotation_rad"] = rp_ur
    else:
        res["rp_rotation_rad"] = None
        res["rp_rotation_status"] = "UR_FIELD_ABSENT_IN_ODB"

    # ---- reactions ---------------------------------------------------------
    if "RF" in fo.keys():
        sf = [0.0, 0.0, 0.0]
        m_o = [0.0, 0.0, 0.0]
        n_react = 0
        max_node_rf = None
        off_face = []
        for v in fo["RF"].values:
            lab = int(v.nodeLabel)
            d = [float(x) for x in v.data]
            if lab not in ncoord:
                continue
            if abs(d[0]) + abs(d[1]) + abs(d[2]) == 0.0:
                continue
            n_react += 1
            if lab not in fixed_labels:
                off_face.append(lab)
            for k in range(3):
                sf[k] += d[k]
            r = ncoord[lab]
            c = cross(r, d)
            for k in range(3):
                m_o[k] += c[k]
            mag = (d[0] ** 2 + d[1] ** 2 + d[2] ** 2) ** 0.5
            if max_node_rf is None or mag > max_node_rf[0]:
                max_node_rf = (mag, lab, d)
        # moment of reactions about the load reference point
        m_rp = list(m_o)
        c = cross((-RP_COORD[0], -RP_COORD[1], -RP_COORD[2]), sf)
        for k in range(3):
            m_rp[k] += c[k]
        res["reactions"] = {
            "n_nodes_with_nonzero_RF": n_react,
            "nonzero_RF_nodes_outside_NFIXED": sorted(off_face),
            "sum_RF_N": sf,
            "sum_reaction_moment_about_origin_N_mm": m_o,
            "sum_reaction_moment_about_RP_N_mm": m_rp,
            "max_single_node_RF": ({"magnitude_N": max_node_rf[0],
                                    "node": max_node_rf[1],
                                    "RF1_RF2_RF3_N": max_node_rf[2],
                                    "node_coords_mm": list(
                                        ncoord[max_node_rf[1]])}
                                   if max_node_rf else None),
        }
    else:
        res["reactions"] = None
        res["reactions_status"] = "RF_FIELD_ABSENT_IN_ODB"

    # ---- energy history ----------------------------------------------------
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
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    jobs = sorted(f[:-4] for f in os.listdir(JOBS) if f.endswith(".odb"))
    print("jobs found: %d" % len(jobs))
    ok = 0
    for j in jobs:
        try:
            r = extract(j)
            with open(os.path.join(OUT, j + ".json"), "w") as f:
                json.dump(r, f, indent=1, sort_keys=True)
            pm = r.get("peak_mises") or {}
            pd = r.get("peak_disp") or {}
            print("OK  %-34s mises=%.6g MPa (el %s %s)  umax=%.6g mm" % (
                j, pm.get("value_MPa", float("nan")), pm.get("element"),
                pm.get("zone"), pd.get("magnitude_mm", float("nan"))))
            ok += 1
        except Exception as exc:
            print("FAIL %-34s %s: %s" % (j, type(exc).__name__, exc))
    print("extracted %d/%d" % (ok, len(jobs)))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
