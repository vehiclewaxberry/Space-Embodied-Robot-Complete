"""Inject the computed source_register into the three WP12 ruling artifacts and
build receipt.json. All SHA-256 values are computed here with hashlib; none is
copied from any sibling document.
"""
import hashlib, io, json, os, subprocess

ROOT = r"f:/China Graduate Future Flight Vehicle Innovation Competition"
WP12REL = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp12_secondary_structure_adjudication"
WP12 = os.path.join(ROOT, WP12REL)
HERE = os.path.join(WP12, "probe")

d = json.load(io.open(os.path.join(HERE, "derived.json"), encoding="utf-8"))
SRC = d["source_register"]


def sha(rel):
    h = hashlib.sha256()
    n = 0
    with open(os.path.join(ROOT, rel), "rb") as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
    return {"path": rel, "sha256": h.hexdigest().upper(), "bytes": n}


def yaml_block(reg, indent=2):
    pad = " " * indent
    out = []
    for k in sorted(reg):
        v = reg[k]
        out.append(f"{pad}? {k}" if len(k) > 120 else f"{pad}{k}:")
        if len(k) > 120:
            out.append(f"{pad}: path: {v['path']}")
            out.append(f"{pad}  sha256: {v['sha256']}")
            out.append(f"{pad}  bytes: {v['bytes']}")
        else:
            out.append(f"{pad}  path: {v['path']}")
            out.append(f"{pad}  sha256: {v['sha256']}")
            out.append(f"{pad}  bytes: {v['bytes']}")
    return "\n".join(out)


# ---- JSON artifact
p = os.path.join(WP12, "SECONDARY_STRUCTURE_INTERFERENCE_RULING_V1.json")
t = io.open(p, encoding="utf-8").read()
assert '"source_register": "__SOURCE_REGISTER__"' in t
t = t.replace('"source_register": "__SOURCE_REGISTER__"',
              '"source_register": ' + json.dumps(SRC, indent=2, sort_keys=True).replace("\n", "\n  "))
io.open(p, "w", encoding="utf-8", newline="\n").write(t)
json.load(io.open(p, encoding="utf-8"))          # parse check
print("injected + JSON-valid:", p)

# ---- YAML artifacts
for name in ("SOLAR_HINGE_AND_HARNESS_DATUM_RULING_V1.yaml",
             "TC13_TC14_BLOCKING_CLASSIFICATION_V1.yaml"):
    p = os.path.join(WP12, name)
    t = io.open(p, encoding="utf-8").read()
    assert "source_register: __SOURCE_REGISTER__" in t
    t = t.replace("source_register: __SOURCE_REGISTER__", "source_register:\n" + yaml_block(SRC))
    io.open(p, "w", encoding="utf-8", newline="\n").write(t)
    try:
        import yaml
        yaml.safe_load(io.open(p, encoding="utf-8"))
        print("injected + YAML-valid:", p)
    except ImportError:
        print("injected (pyyaml absent, not parse-checked):", p)

# ---- receipt
produced = [f"{WP12REL}/SECONDARY_STRUCTURE_INTERFERENCE_RULING_V1.json",
            f"{WP12REL}/SOLAR_HINGE_AND_HARNESS_DATUM_RULING_V1.yaml",
            f"{WP12REL}/TC13_TC14_BLOCKING_CLASSIFICATION_V1.yaml",
            f"{WP12REL}/probe/compute_derived.py",
            f"{WP12REL}/probe/inject_and_receipt.py",
            f"{WP12REL}/probe/read_saddles.py",
            f"{WP12REL}/probe/arm_probe.py",
            f"{WP12REL}/probe/g08_forensic.py",
            f"{WP12REL}/probe/body_attrib.py",
            f"{WP12REL}/probe/refine.py",
            f"{WP12REL}/probe/step_probe.py",
            f"{WP12REL}/probe/f2_f3.py",
            f"{WP12REL}/probe/f3_section.py",
            f"{WP12REL}/probe/group_check.py",
            f"{WP12REL}/probe/derived.json",
            f"{WP12REL}/probe/arm_probe_result.json"]

receipt = {
 "schema": "M7_WP12_SECONDARY_STRUCTURE_ADJUDICATION_RECEIPT_V1",
 "generated_local": subprocess.check_output(["date", "-Iseconds"], text=True).strip(),
 "generated_clock_source": "HOST_LOCAL_CLOCK_ASIA_SHANGHAI_UTC_PLUS_08",
 "work_package": "WP12_SECONDARY_STRUCTURE_ADJUDICATION",
 "role": "A1_PRODUCT_CAD",
 "status": "WP12_COMPLETE_THREE_RULINGS_ISSUED_WITH_REPRODUCIBLE_GEOMETRY_EVIDENCE",
 "verdict": (
   "ADJUDICATED. FINDING 1: G07 = NO_INTERFERENCE_IN_AUTHORITY_BASELINE (the 0.425611 mm is a "
   "measurement-window overrun; 4 of the 5 driving vertices lie 4.10-4.62 mm outside the part in x; "
   "0 of 920536 arm triangles have an AABB overlapping the Aft_Saddle solid; the declared pad face is "
   "13.593469977 mm above the assembly z-max). G08 = SUPERSEDED_NATIVE_ONLY_ARTIFACT (a real "
   "2.254534 mm overlap exists, but only between the native V1 Fwd_Saddle and the native stowed arm at "
   "the unratified Q_STOW pose, 251.8x smaller than that pose's 567.734 mm FK residual; the declared "
   "208.4929 mm pad station is a single isolated mesh vertex with no reproducible provenance). "
   "MID_SUPPORT = NO_INTERFERENCE_IN_AUTHORITY_BASELINE (0 AABB overlaps; declared 2.000 mm gap "
   "reproduced to 3.0e-05 mm; independent clearance to existing hardware 2.99893 mm). "
   "unexplained_positive_interference_count = 0, carried with an explicit statement of the six "
   "coverage limits. FINDING 2: the hinge axis is corroborated by a real native Oe8 pin; the panel box "
   "is a mass/envelope proxy never registered to it; hinge interface geometry declared "
   "DEFINED_NOT_MODELLED + HOLD; KO-03 defined analytically in two forms (fail-closed unconditional, "
   "and design-intent sector with 27.0 mm bus clearance); deployment-clearance verification stays HOLD. "
   "FINDING 3: x = 215.0 mm is a genuinely unmodelled feature on a real part - it lies inside the L0 "
   "accepted-URDF base_link body (x 208.0 to 290.65 mm, 514 triangles cross that plane); WP1's stated "
   "conflict is a datum-side category error. TC-13 = NON_BLOCKING_EXTERNAL_EQUIPMENT_INTEGRATION_HOLD "
   "(all five ODR-13 conditions verified). TC-14 = NON_BLOCKING_FLIGHT_QUALIFICATION_HOLD (all four "
   "ODR-13 blocker probes negative on mechanism-identity evidence). Gate B remains HOLD."),
 "findings_adjudicated": {
   "FINDING_1_G07": "NO_INTERFERENCE_IN_AUTHORITY_BASELINE",
   "FINDING_1_G08": "SUPERSEDED_NATIVE_ONLY_ARTIFACT",
   "FINDING_1_MID_SUPPORT": "NO_INTERFERENCE_IN_AUTHORITY_BASELINE",
   "FINDING_2_SOLAR_HINGE": "PANEL_PROXY_IS_A_MASS_AND_ENVELOPE_PROXY__HINGE_INTERFACE_DEFINED_NOT_MODELLED__KEEP_OUT_DEFINED_ANALYTICALLY__SWEEP_CLEARANCE_HELD",
   "FINDING_3_HARNESS_DATUM": "GENUINELY_UNMODELLED_FEATURE_ON_A_REAL_PART__NOT_STALE_NOT_A_WRONG_DATUM",
   "TC_13": "NON_BLOCKING_EXTERNAL_EQUIPMENT_INTEGRATION_HOLD",
   "TC_14": "NON_BLOCKING_FLIGHT_QUALIFICATION_HOLD"},
 "terminal_release_condition_contribution": {
   "unexplained_positive_interference_count": 0,
   "high_severity_open_findings_raised_by_wp12": 0,
   "internal_holds_raised_by_wp12": 0,
   "non_blocking_holds_raised_by_wp12": 8,
   "hash_mismatch_count": 0,
   "hash_verification_note": (
     "all six WP1 artifact hashes pinned in wp1_structure_cad/receipt.json were independently "
     "recomputed with hashlib and match bit-for-bit: PRODUCT_STRUCTURE_V1.yaml, HARNESS_ROUTING_V1.yaml, "
     "KEEP_OUT_REGISTER_V1.yaml, SUPPORT_AND_BRACKET_CANDIDATES_V1.yaml, "
     "DESIGN_FREEZE_ASSEMBLY_V1.step and DESIGN_FREEZE_ASSEMBLY_BUILD_REPORT_V1.json")},
 "independent_reproduction_performed": {
   "wp1_native_mesh_measurements_reproduced": 7,
   "wp1_measurements_that_failed_to_reproduce": 0,
   "new_conservative_tests_added": [
     "triangle-AABB overlap of all 920536 arm triangles against each exact saddle box union",
     "exact-bit connected-component decomposition of the arm tessellation (344 bodies)",
     "STEP text re-count of MANIFOLD_SOLID_BREP / CLOSED_SHELL / ADVANCED_FACE",
     "STEP control-point occupancy test of the three support head volumes and the three full support columns",
     "triangle-for-triangle decomposition of 04_ARM_STOW_SUPPORT.stl",
     "plane-straddling triangle cross-section of the L0 base_link at five stations",
     "closed-form solve of the hinge axis implied by the native stowed/deployed panel box pair"]},
 "wp1_corrections_required_in_terminal_round_2": [
   "SUP-OPEN-G07-01: downgrade DESIGN_BLOCKING to DEFINITION_INCOMPLETE_HEAD_CENTRING_UNSTATED",
   "SUP-OPEN-G07-02: the 'effectively hard contact 0.004 mm' statement is scoped wrong; the correct native relationship is a 0.990844 mm prong clearance",
   "SUP-OPEN-G08-01: uphold as a declaration defect, reclassify as NATIVE_LINE_DECLARATION_DEFECT_NOT_A_GATE_A_BLOCKER, and do not adopt the proposed relief region because it is defined relative to the unreproducible pad face",
   "SUP-OPEN-MID-01: uphold with the circularity qualification and add the 2.99893 mm independent clearance",
   "HARNESS_ROUTING_V1.yaml arm exit_point: replace the 'conflict' text with the datum-side statement given in SOLAR_HINGE_AND_HARNESS_DATUM_RULING_V1.yaml",
   "receipt.json retained_holds: HOLD_HDRM_ARCHITECTURE_NOT_SELECTED is stale - WP5 selected HDRM-N02 at candidate level; the accurate hold is HOLD_INTERFACE_GEOMETRY_NOT_RELEASED",
   "KEEP_OUT_REGISTER_V1.yaml KO-03: adopt the two analytic envelope definitions and the DEFINED_NOT_MODELLED hinge interface declaration"],
 "prohibitions_honored": {
   "wp1_files_edited": False, "sibling_wp_files_edited": False, "authority_files_edited": False,
   "freecad_launched": False, "solidworks_launched": False, "abaqus_launched": False,
   "design_freeze_geometry_rebuilt": False, "formal_fea_run_count": 0,
   "zero_fill_of_unknowns": False, "l0_urdf_masses_overridden": False,
   "baseline_files_modified": False,
   "files_written_outside_wp12_secondary_structure_adjudication": False,
   "candidate_promoted_to_manufacturing_authority": False,
   "flight_launcher_or_qualification_claimed": False,
   "next_stage_authorized": False, "m8_or_m9_planning_artifact_created": False,
   "gate_b_remains_hold": True, "voting_used": False, "owner_escalation_required": False},
 "memory_gate": d["memory_gate"] | {
   "declaration": ("the 6 GiB memory gate is FAILED on this host and stays declared as failed. "
                   "This work package launched no CAD kernel, no FEA and no boolean operation - only "
                   "chunked binary-STL streaming, STEP text parsing and numpy/scipy analysis.")},
 "review_status": "PENDING_OWNER_REVIEW",
 "next_stage_authorized": False,
 "gate_b": "MECHANICAL_FLIGHT_QUALIFICATION_RELEASED remains HOLD",
 "produced_files": [sha(p) for p in produced],
 "source_register": SRC,
}
io.open(os.path.join(WP12, "receipt.json"), "w", encoding="utf-8", newline="\n").write(
    json.dumps(receipt, indent=2, ensure_ascii=True))
print("wrote receipt.json with", len(receipt["produced_files"]), "produced files and",
      len(SRC), "source register entries")
