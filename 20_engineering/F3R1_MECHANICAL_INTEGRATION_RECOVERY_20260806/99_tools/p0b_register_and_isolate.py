# -*- coding: utf-8 -*-
"""P0b/P0d: candidate register + donor isolation copy with per-file hash proof.

Pack and Go deviation (registered): GetPackAndGo COM binding fails on this
machine (InvokeTypes(207) "非选择性的参数", B3 campaign log) — the equivalent
verifiable method is a per-file copy with pairwise SHA-256 proof, followed by an
in-SolidWorks reference-ownership check (trap #9: whole-tree copies can resolve
components back to the source tree via baked absolute paths).

Donors (read-only, hashed PRE and POST):
  D1 V2_2_NATIVE full tree      -> SPACECRAFT_V2_2_NATIVE_COPY/   (canonical spacecraft)
  D2 B51 articulated arm run    -> B601_ARM_B51_COPY/             (6R datum-hinge arm)
  D3 V2_2 wing panels (4 parts) -> WING_PANEL_DONORS/             (V2_2=REFERENCE_DONOR_ONLY)
"""
import csv
import json
import os
import shutil
import sys
from pathlib import Path

from f3r1_env import ENG, F3R1, JLog, check_protected, sha256_file

log = JLog("p0b_register_isolate")
CAD = ENG / "cad"

D1_SRC = CAD / "Space_Embodied_Robot_CAD_V2_2_NATIVE"
D2_SRC = (CAD / "B5_1_B601_interface_closure_candidate/03_CAD/native_articulated"
          / "B51_ARTICULATED_20260728T008")
D3_SRC = CAD / "Space_Embodied_Robot_CAD_V2_2"
D3_PARTS = [
    "50_Solar_Array_Left/parts/WING_L_DEPLOYED.SLDPRT",
    "50_Solar_Array_Left/parts/WING_L_STOWED.SLDPRT",
    "50_Solar_Array_Right/parts/WING_R_DEPLOYED.SLDPRT",
    "50_Solar_Array_Right/parts/WING_R_STOWED.SLDPRT",
]

D1_DST = F3R1 / "03_native_cad" / "SPACECRAFT_V2_2_NATIVE_COPY"
D2_DST = F3R1 / "03_native_cad" / "B601_ARM_B51_COPY"
D3_DST = F3R1 / "03_native_cad" / "WING_PANEL_DONORS"

SKIP_PREFIX = "~$"          # SolidWorks crash-lock residue: never copy
SKIP_DIRS = {"__pycache__"}


def tree_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.startswith(SKIP_PREFIX):
                continue
            out.append(Path(dirpath) / fn)
    return sorted(out)


def copy_tree_verified(src_root, dst_root, entries):
    """Copy files preserving relative layout; return per-file proof rows."""
    rows = []
    for src in entries:
        rel = src.relative_to(src_root)
        dst = dst_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            raise RuntimeError("REFUSING_TO_OVERWRITE: %s" % dst)
        pre = sha256_file(src)
        shutil.copy2(src, dst)
        post = sha256_file(dst)
        rows.append({"rel": str(rel).replace("\\", "/"), "bytes": src.stat().st_size,
                     "src_sha256": pre, "dst_sha256": post,
                     "match": pre == post})
        if pre != post:
            raise RuntimeError("COPY_HASH_MISMATCH: %s" % rel)
    return rows


def main():
    check_protected("P0B_PRE")
    log.ev("PROTECTED_PRE_OK")

    proof = {"schema": "F3R1_PACK_AND_GO_PROOF_V1",
             "method": ("verified per-file copy (Pack&Go COM InvokeTypes(207) broken on "
                        "this machine -- registered deviation D-F3R1-01); pairwise SHA-256 "
                        "for every file; overwrite refused; ~$ locks excluded"),
             "donors": {}}

    # D1 spacecraft
    d1 = tree_files(D1_SRC)
    log.ev("D1_SCAN", files=len(d1))
    rows1 = copy_tree_verified(D1_SRC, D1_DST, d1)
    proof["donors"]["D1_SPACECRAFT_V2_2_NATIVE"] = {
        "src": str(D1_SRC), "dst": str(D1_DST), "files": len(rows1),
        "all_match": all(r["match"] for r in rows1)}
    log.ev("D1_COPIED", files=len(rows1))

    # D2 arm
    d2 = tree_files(D2_SRC)
    rows2 = copy_tree_verified(D2_SRC, D2_DST, d2)
    proof["donors"]["D2_B601_ARM_B51_ARTICULATED"] = {
        "src": str(D2_SRC), "dst": str(D2_DST), "files": len(rows2),
        "all_match": all(r["match"] for r in rows2)}
    log.ev("D2_COPIED", files=len(rows2))

    # D3 wing panels (flat copy)
    rows3 = []
    D3_DST.mkdir(parents=True, exist_ok=True)
    for rel in D3_PARTS:
        src = D3_SRC / rel
        dst = D3_DST / Path(rel).name
        if dst.exists():
            raise RuntimeError("REFUSING_TO_OVERWRITE: %s" % dst)
        pre = sha256_file(src)
        shutil.copy2(src, dst)
        post = sha256_file(dst)
        rows3.append({"rel": rel, "bytes": src.stat().st_size,
                      "src_sha256": pre, "dst_sha256": post, "match": pre == post})
    proof["donors"]["D3_WING_PANELS_V2_2"] = {
        "src": str(D3_SRC), "dst": str(D3_DST), "files": len(rows3),
        "all_match": all(r["match"] for r in rows3)}
    log.ev("D3_COPIED", files=len(rows3))

    proof["per_file"] = {"D1": rows1, "D2": rows2, "D3": rows3}
    out = F3R1 / "01_asset_selection" / "F3R1_PACK_AND_GO_PROOF.json"
    out.write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")

    # candidate register (the named candidates considered for down-select)
    reg = F3R1 / "01_asset_selection" / "F3R1_CANDIDATE_ASSEMBLY_REGISTER.csv"
    top_candidates = [
        ("SPACECRAFT_CANONICAL", D1_SRC / "Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
         "SELECTED_AS_D1", "canonical native baseline per human ruling (hash-bound 30C09B50); "
         "structure+decks+panels+mount+3 saddles+solar roots incl solar HDRM; NO wing panels, NO arm"),
        ("SPACECRAFT_V2_3_COPY", CAD / "Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
         "REJECTED", "R3-02: drifted from manifest (76A3B289 vs declared 30C09B50); no controlled digest"),
        ("B601_ARM_ARTICULATED", D2_SRC / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM",
         "SELECTED_AS_D2", "6R datum hinges J1-J6 (CONCENTRIC+COINCIDENT), 8 vendor link parts, "
         "build trace errors:0 warnings:0 full_rebuild:true, 25.6MB, sha 603B87BB"),
        ("B601_ARM_Q0_RIGID", CAD / "B5_0_B601_space_manipulator_candidate/03_CAD/native_runs/B50_NATIVE_20260727T2214Z/20_assembly/B50_B601_ENGINEERING_ARM_Q0.SLDASM",
         "REJECTED", "q0 rigid pretest, superseded by articulated run"),
        ("B51R1_CARRIER_PILOT_R14", CAD / "B5_1R1_B601_interface_native_rework_candidate/03_CAD/20_NATIVE_ASSEMBLY/PILOT/CHECKPOINTS/B51R1_CARRIER_J00_ROOT_PILOT_R14.SLDASM",
         "REJECTED", "pilot checkpoint only; B51R1 S01 never produced the final skeleton (COM 0x8002802B)"),
        ("F3P3_TOP_FCSTD", Path(r"F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment/15_f3_p3_top_assembly/F3_P3_TOP_ASSEMBLY.FCStd"),
         "REJECTED_AS_TOP__EVIDENCE_ONLY", "R3-03: STEP-import flat 206 solids, arm scattered, no wings, "
         "3 INVALID_SHAPE; per ECR now INCOMPLETE_GEOMETRY_DONOR_AND_AUDIT_EVIDENCE_ONLY"),
        ("F3P3_STATE_FCSTD", Path(r"F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment/15_f3_p3_top_assembly/SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd"),
         "REJECTED_AS_TOP__STATE_REFERENCE_ONLY", "R3-01: zero geometry; per ECR now "
         "STATE_AND_ENVELOPE_REFERENCE_ONLY / NOT_AUTHORITATIVE_GEOMETRIC_ASSEMBLY"),
        ("WING_PANELS_V2_2", D3_SRC / "50_Solar_Array_Left/parts/WING_L_DEPLOYED.SLDPRT",
         "SELECTED_AS_D3", "real wing panel parts (DEPLOYED/STOWED states as parts); "
         "V2_2 tree itself = REFERENCE_DONOR_ONLY, individual parts allowed"),
        ("WING_V2_1", CAD / "Space_Embodied_Robot_CAD_V2_1/08_Solar_Wing_L/SV21_Solar_Wing_L.SLDASM",
         "REJECTED", "older lineage than V2_2 panels; V2_1 root stations superseded by O9/O10"),
    ]
    with open(reg, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate", "path", "exists", "bytes", "sha256", "decision", "rationale"])
        for name, p, decision, why in top_candidates:
            ex = p.is_file()
            w.writerow([name, str(p), ex,
                        p.stat().st_size if ex else "",
                        sha256_file(p) if ex else "", decision, why])
    log.ev("REGISTER_WRITTEN", path=str(reg))

    check_protected("P0B_POST")
    log.ev("PROTECTED_POST_OK")
    print("P0B_DONE  D1=%d D2=%d D3=%d files copied, all hash-verified"
          % (len(rows1), len(rows2), len(rows3)))


if __name__ == "__main__":
    sys.exit(main())
