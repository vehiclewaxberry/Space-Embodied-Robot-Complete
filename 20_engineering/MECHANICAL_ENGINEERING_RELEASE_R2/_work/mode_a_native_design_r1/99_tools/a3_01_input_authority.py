"""A3.1 - input authority freeze for SEI-MECH-MODE-A-NATIVE-DESIGN-R1.

Read-only over the whole repository. Hashes every input this candidate design
will consume, records the F3R2 identity drift explicitly, and emits:
  A3_00_INPUT_AUTHORITY.json
  A3_01_PROTECTED_HASHES.csv
  A3_02_DONOR_IDENTITY_WARNING.md

Writes ONLY inside 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/
mode_a_native_design_r1/. Touches no donor, URDF, ODR or simulation baseline.
"""
import hashlib, json, os, csv, sys

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
OUT = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
A0 = os.path.join(OUT, "00_authority")
os.makedirs(A0, exist_ok=True)

# role, repo-relative path, registered sha256 (upper) or None, note
INPUTS = [
    ("L0_ACCEPTED_URDF", r"20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf",
     "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
     "modification FORBIDDEN; mass 4.695555949342986 kg; 6R+1F+2P"),
    ("FROZEN_GEOMETRY_DONOR", r"20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM",
     "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
     "CORRECT frozen donor for Mode A candidate; copy/derive only, never edit in place"),
    ("IDENTITY_MISMATCH_DO_NOT_USE", r"20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM",
     "19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
     "rewritten 2026-08-30; DO_NOT_USE_AS_FROZEN_DONOR"),
    ("V2_2_NATIVE_DONOR", r"20_engineering\cad\Space_Embodied_Robot_CAD_V2_2_NATIVE\Assembly\Space_Embodied_Service_Spacecraft_V2_2.SLDASM",
     "30C09B50A0D2967EC1F48050CAAC34D12A43565C44978D54E3785595202DEF7A",
     "bus donor, registered bytes intact"),
    ("A03_MASTER_GEOMETRY_STEP", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\04_MASTER_GEOMETRY.step",
     "8C85585E9C051AEBB849E48F56354B48BF4204F61103B550BD92FC77BA99EA9E",
     "41 solids; B601 = FRAME_AXIS_WITNESS_ONLY; wings = LEGACY_R1; bus = solid proxy"),
    ("A03_MASTER_GEOMETRY_FCSTD", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\03_MASTER_GEOMETRY.FCStd",
     "013DA84FE9A5C388252DB18516628411C484BB818959FA1A5CF8D950485636E7", ""),
    ("SOLAR_R2_CANDIDATE_STEP", r"20_engineering\F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1\ecr_solar_array_r2\SOLAR_ARRAY_R2_CANDIDATE_V1.step",
     "21FF77B882DBFAB87B3E77DD56817EFC7F321C68E30AFEDCDDBB4D79B9915795",
     "three-leaf R2 wing, FROZEN; NOT present in A03"),
    ("PARENT_RELEASE_GATE", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\00_RELEASE_GATE.json",
     "14D30FD40AC60253C0716A71BA46950E1DF6B8E69DCE3F12690319B970A48674",
     "GATE_A_NOT_PASSED; this candidate must not reissue it"),
    ("PRODUCT_STRUCTURE", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\02_PRODUCT_STRUCTURE.yaml",
     "0F9897EF4E41666DDB29CB0FC621DD737FDD8CCDE3F5527030E53A9D1604681A", ""),
    ("ODR_F4R1_01", r"20_engineering\F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1\00_charter\ODR_F4R1_01_SIGNED.md",
     None, "clause 4 conflicts with Mode A; registered, NOT modified by this package"),
    ("ODR_F4R1_02", r"20_engineering\F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1\00_charter\ODR_F4R1_02_SIGNED.md",
     None, "clause 3 registers FreeCAD 1.1.3 + OCP as the authorised toolchain"),
    ("H9_PACKAGING_DECISION", r"20_engineering\cad\B5_1R1_B601_interface_native_rework_candidate\00_BASELINE\PARENT_LOCKED_INPUTS\PARENT_H9_DECISION\B51_PACKAGING_ENVELOPE_DECISION.md",
     None, "Mode A / Mode B definitions; still HUMAN_DECISION_REQUIRED in repo"),
    ("GEO_SSOT_SERVICER", r"20_engineering\config\geometry\service_spacecraft_v1.yaml", None,
     "flange 160x160x15 vs arm_mount 12 -> conflict registered"),
    ("GEO_SSOT_ARM_MOUNT", r"20_engineering\config\geometry\arm_mount_v1.yaml", None, ""),
    ("GEO_SSOT_FRAME_TREE", r"20_engineering\config\geometry\frame_tree_v1.yaml", None,
     "T_SM = [185.25,0,0] mm + Ry(90 deg), nominal_frozen_v1"),
    ("F4R1_C3_INTERNAL_STRUCTURE", r"20_engineering\F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1\70_c3_cad\CA_A_R1_INTERNAL_STRUCTURE_V2.step",
     None, "prior internal secondary structure candidate, 32 parts 1244.9 g"),
    ("A1_STOW_LAYOUT", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1\A1_STOW_LAYOUT_R1.json", None, ""),
    ("A2_JOINT_REOPT", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1\A2_JOINT_REOPT_R1.json", None, ""),
    ("A2B_SUBSETS", r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1\A2B_EXACTNESS_AND_SUBSETS_R1.json", None, ""),
]
MESHDIR = r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
for f in sorted(os.listdir(os.path.join(ROOT, MESHDIR))):
    if f.lower().endswith(".stl"):
        INPUTS.append(("L0_ACCEPTED_MESH", os.path.join(MESHDIR, f), None, "collision+visual source, FORBIDDEN to modify"))


def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


rows, drift, missing = [], [], []
for role, rel, exp, note in INPUTS:
    fp = os.path.join(ROOT, rel)
    if not os.path.exists(fp):
        rows.append(dict(role=role, path=rel, exists=False, bytes=None, sha256=None,
                         registered_sha256=exp, identity="MISSING", note=note))
        missing.append(rel); continue
    cur, nb = sha(fp), os.path.getsize(fp)
    if exp is None:
        ident = "RECORDED_NO_PRIOR_REGISTRATION"
    elif cur == exp:
        ident = "MATCH"
    else:
        ident = "IDENTITY_MISMATCH"
        drift.append((role, rel, exp, cur, nb))
    rows.append(dict(role=role, path=rel, exists=True, bytes=nb, sha256=cur,
                     registered_sha256=exp, identity=ident, note=note))

with open(os.path.join(A0, "A3_01_PROTECTED_HASHES.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["role", "path", "exists", "bytes", "sha256",
                                       "registered_sha256", "identity", "note"])
    w.writeheader(); w.writerows(rows)

authority = {
    "schema": "A3_INPUT_AUTHORITY_V1",
    "task": "SEI-MECH-MODE-A-NATIVE-DESIGN-R1",
    "phase": "A3.1_INPUT_AUTHORITY_FREEZE",
    "claim_ceiling": "RESEARCH_AND_ENGINEERING_CANDIDATE_ONLY",
    "stage_verdict": ["MODE_A_GEOMETRY_FEASIBLE", "NATIVE_CANDIDATE_DESIGN_AUTHORIZED",
                      "12U_DEPLOYER_COMPLIANCE_NOT_YET_CLAIMED", "SSOT_AND_ODR_PROMOTION_HOLD"],
    "write_boundary": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/",
    "toolchain": {
        "authorised_by": "ODR_F4R1_02_SIGNED.md clause 3",
        "geometry_kernel": "OCP / OpenCascade 7.9.3.1",
        "assembly": "FreeCAD 1.1.3 FreeCADCmd",
        "solidworks_native_assembly": "BLOCKED",
        "solidworks_block_reasons": [
            "solidworks-agent MCP registers 40 tools, zero can create assemblies or mates (TOOL-01)",
            "no live SolidWorks process",
            "6 GiB memory gate unmet (measured ~1.2 GiB free)",
            "project .claude/settings.json denies win32com / pythoncom / SldWorks.Application",
        ],
        "consequence": "A3 delivers FCStd + STEP + review package; SolidWorks native rebuild deferred with MANUAL MATE CARDs",
    },
    "prohibitions": [
        "no modification of accepted B601 URDF or meshes",
        "no modification of any frozen donor, ODR, or simulation gate",
        "base_link must remain an independent component with independent mass",
        "base_link must not be boolean-merged into bus structure",
        "LEGACY 15x140x140 flange is LEGACY_REFERENCE_ONLY / NOT_FOR_NEW_DESIGN",
        "+6.55 mm is not a uniform all-face protrusion allowance",
        "no claim of standard 12U deployer compliance",
    ],
    "counts": {"inputs": len(rows), "match": sum(1 for r in rows if r["identity"] == "MATCH"),
               "identity_mismatch": len(drift), "missing": len(missing),
               "recorded_no_prior_registration": sum(1 for r in rows if r["identity"] == "RECORDED_NO_PRIOR_REGISTRATION")},
    "identity_mismatches": [dict(role=d[0], path=d[1], registered=d[2], current=d[3], bytes=d[4]) for d in drift],
    "missing": missing,
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
}
json.dump(authority, open(os.path.join(A0, "A3_00_INPUT_AUTHORITY.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

warn = ["# A3.02 Donor identity warning", "",
        "`DO_NOT_USE_AS_FROZEN_DONOR`", "", "```text"]
for role, rel, exp, cur, nb in drift:
    warn += [f"{rel}", f"  registered : {exp}", f"  current    : {cur}  ({nb:,} B)", ""]
warn += ["```", "",
         "Correct frozen geometry donor for this candidate:", "",
         "```text",
         r"20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM",
         "sha256 19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0",
         "29,594,924 B", "```", "",
         "Copy or derive only. Never edit the donor in place.", "",
         "The drift was introduced 2026-08-30 and is registered in no repository receipt.",
         "This package records it; it does not adjudicate it. Owner decision required."]
open(os.path.join(A0, "A3_02_DONOR_IDENTITY_WARNING.md"), "w", encoding="utf-8").write("\n".join(warn))

print(f"inputs {len(rows)}  MATCH {authority['counts']['match']}  "
      f"MISMATCH {len(drift)}  MISSING {len(missing)}  "
      f"NO_PRIOR_REG {authority['counts']['recorded_no_prior_registration']}")
for d in drift:
    print(f"  MISMATCH {d[0]:<28} {os.path.basename(d[1])}")
    print(f"           registered {d[2][:16]}…  current {d[3][:16]}…  {d[4]:,} B")
for m in missing:
    print("  MISSING ", m)
print("wrote", A0)
