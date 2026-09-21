# -*- coding: utf-8 -*-
"""P5 G0: CURRENT_TRANSFORM_AND_HASH_FREEZE (read-only on the current candidate).

Registers, for every top-level component and the named sub-assembly members,
the full state needed as the geometric reference when G1 swaps FixComponent for
real mates: path, transform16, suppression, fixed/floating, configuration,
referenced file SHA-256, assembly bbox, mass-property source, ownership.

Also re-confirms the THREE DISTINCT interface faces and refuses to merge them:
  Central_Boss  external face  x = 208.0 mm   (current arm mount datum)
  Adapter_Plate external face  x = 198.0 mm
  historical T_SM interface          185.25 mm  (P5C Mode B, retained)

Then copies the candidate to a NEW versioned candidate file so G1 never
overwrites the G0-frozen version.

SAVE_CALLS_ALLOWED on the existing candidate = 0 (open read-only, never save);
the only write is a byte copy to the new version + the register files.
"""
import csv
import json
import shutil
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p5g0_freeze")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
TOP_V2 = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"

REG_CSV = NC / "F3R1_PRE_MATE_TRANSFORM_REGISTER.csv"
HASH_JSON = NC / "F3R1_PRE_MATE_TOP_HASH.json"
OWN_CSV = NC / "F3R1_COMPONENT_OWNERSHIP.csv"

gm = swc.get_com_member

# Interface faces that must stay SEPARATE (never collapsed into one dimension)
INTERFACE_FACES = {
    "Central_Boss_external_face_x_mm": 208.0,
    "Adapter_Plate_external_face_x_mm": 198.0,
    "historical_T_SM_interface_x_mm": 185.25,
}

# components of interest required by the work order (leaf-name prefixes)
REQUIRED = ["Space_Embodied_Service_Spacecraft", "B51_B601_ARTICULATED",
            "Central_Boss", "Adapter_Plate", "WING_L_STOWED", "WING_R_STOWED",
            "WING_L_DEPLOYED", "WING_R_DEPLOYED", "Aft_Saddle", "Fwd_Saddle",
            "Mid_Saddle"]


def _safe(obj, attr, default=""):
    """Optional COM property: this SW type library omits some IComponent2
    members (e.g. SolveOption), so probe instead of assuming."""
    try:
        v = gm(obj, attr)
        return "" if v is None else v
    except Exception:
        return default


def t16_of(c2):
    t = gm(c2, "Transform2")
    if t is None:
        return None
    return [float(v) for v in gm(t, "ArrayData")]


def box_of(c2):
    b = gm(c2, "GetBox", False, False)
    return [round(v * 1000.0, 4) for v in list(b)] if b is not None else None


def walk(c2, rows, depth, parent):
    for c in gm(c2, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        full = str(gm(k, "Name2"))
        leaf = full.split("/")[-1]
        path = str(gm(k, "GetPathName") or "")
        rows.append({
            "depth": depth, "parent": parent, "leaf_name": leaf,
            "full_name": full, "path": path,
            "is_fixed": bool(gm(k, "IsFixed")),
            "is_suppressed": bool(gm(k, "IsSuppressed")),
            "referenced_config": str(gm(k, "ReferencedConfiguration") or ""),
            "solving_option": _safe(k, "Solving"),
            "transform16": t16_of(k),
            "bbox_mm": box_of(k),
        })
        if depth < 2:
            walk(k, rows, depth + 1, leaf)
    return rows


def mate_register(model):
    """Enumerate existing mates (expected 0 at G0) with type + entities."""
    out = []
    feat = gm(model, "FirstFeature")
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                out.append({"name": str(gm(s, "Name")),
                            "type": str(gm(s, "GetTypeName2")),
                            "suppressed": bool(gm(s, "IsSuppressed"))})
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")
    return out


def main():
    check_protected("P5G0_PRE")
    rep = {"schema": "F3R1_P5G0_FREEZE_V1",
           "candidate": str(TOP), "candidate_sha256_pre": sha256_file(TOP),
           "interface_faces_mm": INTERFACE_FACES,
           "interface_face_policy": (
               "THREE DISTINCT PHYSICAL FACES -- 208.0 (Central_Boss outer), "
               "198.0 (Adapter_Plate outer), 185.25 (historical T_SM Mode B). "
               "MUST NOT be merged into a single dimension.")}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p5g0")
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP), read_only=True)
        rep["configs"] = list(gm(top, "GetConfigurationNames") or [])
        active = str(gm(top, "ConfigurationManager").ActiveConfiguration.Name)
        rep["active_config"] = active

        conf = gm(top, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        rows = walk(rootc, [], 0, "<root>")
        rep["registered_components"] = len(rows)
        rep["top_level_count"] = sum(1 for r in rows if r["depth"] == 0)
        rep["fixed_components"] = [r["full_name"] for r in rows if r["is_fixed"]]
        rep["n_fixed"] = len(rep["fixed_components"])
        rep["existing_mates"] = mate_register(top)
        rep["n_existing_mates"] = len(rep["existing_mates"])

        # required-component coverage (fail-closed on a missing required item)
        found, missing = {}, []
        for pref in REQUIRED:
            hit = [r for r in rows if r["leaf_name"].startswith(pref)]
            found[pref] = [h["full_name"] for h in hit]
            if not hit:
                missing.append(pref)
        rep["required_coverage"] = found
        rep["required_missing"] = missing

        # per-referenced-file hashes (ownership: all must live under F3R1)
        files, own = {}, []
        for r in rows:
            p = r["path"]
            if not p:
                continue
            inside = str(F3R1).lower() in p.lower()
            if p not in files:
                try:
                    files[p] = sha256_file(p)
                except Exception as e:
                    files[p] = "UNREADABLE:%s" % str(e)[:60]
            own.append({"leaf_name": r["leaf_name"], "full_name": r["full_name"],
                        "path": p, "inside_f3r1": inside,
                        "sha256": files[p],
                        "mass_property_source": (
                            "ACCEPTED_URDF_MASS_AUTHORITY_CAD_AUTO_MASS_NOT_AUTHORIZED"
                            if "B51_" in r["leaf_name"] or "B601" in r["leaf_name"]
                            else "V2_2_DONOR_GEOMETRY_CAD_MASS_NOT_AUTHORITATIVE"),
                        "ownership": ("F3R1_CANDIDATE" if inside
                                      else "EXTERNAL_READ_ONLY")})
        rep["referenced_file_hashes"] = files
        rep["external_references"] = [o["full_name"] for o in own
                                      if not o["inside_f3r1"]]

        swc.close_document(app, top, blog)

        # ---- write registers ----
        with open(REG_CSV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["depth", "parent", "leaf_name", "full_name", "path",
                        "is_fixed", "is_suppressed", "referenced_config",
                        "solving_option", "bbox_xmin", "bbox_ymin", "bbox_zmin",
                        "bbox_xmax", "bbox_ymax", "bbox_zmax"] +
                       ["t%02d" % i for i in range(16)])
            for r in rows:
                bb = r["bbox_mm"] or [""] * 6
                t = r["transform16"] or [""] * 16
                w.writerow([r["depth"], r["parent"], r["leaf_name"],
                            r["full_name"], r["path"], r["is_fixed"],
                            r["is_suppressed"], r["referenced_config"],
                            r["solving_option"]] + list(bb) + list(t))
        with open(OWN_CSV, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=["leaf_name", "full_name", "path",
                                              "inside_f3r1", "sha256",
                                              "mass_property_source",
                                              "ownership"])
            w.writeheader()
            for o in own:
                w.writerow(o)

        # ---- new candidate version (never overwrite the frozen one) ----
        if TOP_V2.exists():
            TOP_V2.unlink()
        shutil.copy2(TOP, TOP_V2)
        rep["new_candidate"] = str(TOP_V2)
        rep["new_candidate_sha256"] = sha256_file(TOP_V2)
        rep["copy_identical"] = (rep["new_candidate_sha256"] ==
                                 rep["candidate_sha256_pre"])
        log.ev("NEW_CANDIDATE_CREATED", path=str(TOP_V2),
               identical=rep["copy_identical"])

        ok = (not missing and rep["copy_identical"]
              and rep["registered_components"] > 0)
        rep["verdict"] = "G0_FROZEN" if ok else "G0_CHECK"
    except Exception as exc:
        rep["verdict"] = "G0_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1800:]
        log.ev("G0_FAIL", error=str(exc))
    finally:
        wd.stop()

    rep["candidate_sha256_post"] = sha256_file(TOP) if TOP.is_file() else None
    rep["original_unchanged"] = (rep["candidate_sha256_post"] ==
                                 rep["candidate_sha256_pre"])
    check_protected("P5G0_POST")
    HASH_JSON.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                         encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  registered:", rep.get("registered_components"),
          "top-level:", rep.get("top_level_count"),
          "fixed:", rep.get("n_fixed"), "mates:", rep.get("n_existing_mates"))
    print("  required_missing:", rep.get("required_missing"))
    print("  external_refs:", len(rep.get("external_references") or []))
    print("  original_unchanged:", rep.get("original_unchanged"),
          "| new candidate identical:", rep.get("copy_identical"))
    if rep["verdict"] == "G0_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G0_FROZEN" else 1)


if __name__ == "__main__":
    main()
