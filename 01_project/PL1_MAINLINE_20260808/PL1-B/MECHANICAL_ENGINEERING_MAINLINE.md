# MECHANICAL_ENGINEERING_MAINLINE.md

**Task:** SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION / PL1-B (mechanical mainline recon, READ-ONLY)
**Date of measurement:** 2026-08-08 · **Git HEAD (ROOT A):** `5c5adde` (branch `publication/stage3-integrity-closure`)
**Rule enforced throughout:** L0 DYNAMICS_TRUTH (accepted URDF) > L1 ENGINEERING_NATIVE_CAD (SolidWorks native line) > L2 SIMULATION_MODEL > L3 REFERENCE/DONOR. CAD mass never overrides URDF mass; FreeCAD detail level never confers authority (F3R1 donor down-select, human-ratified, already demoted the FreeCAD top assemblies to EVIDENCE_ONLY).

**Path abbreviations used below**
- `REPO` = `F:\China Graduate Future Flight Vehicle Innovation Competition`
- `WT` = `F:\_SEI_PROJECT_CONSOLIDATION_20260807\12_WAVE4\WORKTREE_RECONCILIATION\20_engineering` (Wave-4 verified source mirror for the active F3R1/F3R2 packages, and still the only residence of the full historical CAD lineage)
- `ARCH` = `F:\SEI_PROJECT_ARCHIVE\CONFIGURATION_MANAGEMENT\20260807_CONSOLIDATION`

---

## 0. Five-minute answers

> **Post-M3R correction (2026-08-08):** every G30/G31 statement below that
> calls the B601 feature an `8 x M3 flange` is superseded by the independent
> M3R unique-axis audit. The active STEP contains four HM4-75/M4-class screw
> axes on a 64 x 64 mm square (equivalent PCD 90.509642 mm), not eight holes,
> and the continuous vendor base plate is absent from the active donor. The
> competition interface authority is PASS at AS-BUILT scope; the new two-stage
> FreeCAD/STEP adapter is a geometry candidate and native closure remains HOLD.
> Rev B is the controlling geometry revision: the Stage-A M5 bearing zone is
> 8.0 mm thick, both parts use diameter-5.5 through clearances, and one
> asymmetric dowel candidate removes the former 45-degree geometric ambiguity.
> Dowel fit/tolerance, the 6.7 mm nominal M6 net edge margin, live mating
> geometry, fastener MoS, physical fit-up and SolidWorks native closure remain
> HOLD. Any later historical `8 x M3` or old G31 mass statement is superseded.

1. **Current spacecraft mechanical model (L1 native CAD):** `REPO\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM` (29,594,924 B, sha256 `19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0`; byte-identical to F3R1 `F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM`). It is the **CURRENT_MACHINE_SELECTED_MECHANICAL_CANDIDATE**, not a human-ratified baseline: 82 components, 6 top components, 6 top mates / 0 errors, and 8 registered/gate-checked configurations, of which 7 are geometrically differentiated (`PARTIAL` is intentionally `NOT_DIFFERENTIATED_FROM_DEPLOYED_NOMINAL`). `F3R2_FINAL_GATE.json` is 11/14, fails C11/C12/C14, carries 4 HOLD verdict tokens plus 7 open items, and remains `PENDING_HUMAN_REVIEW`.
2. **B601 truth file (L0):** `REPO\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf` — 11,321 B. Re-computed 2026-08-08: raw sha256 `1bc2b7483cd8025d…c164` (CRLF disk bytes), LF-normalized `408147ddc9cc0bba…a3a4` — **both match the CM-declared frozen values exactly**. Mass re-parsed from the file: **4.695555949342986 kg** (10 links). The byte-identical B5.1R1 copy under `WT\cad\B5_1R1_B601_interface_native_rework_candidate\00_BASELINE\AUTHORITIES\accepted_urdf\` is a historical duplicate, not a second authority; `PROJECT_START_HERE.md` now points to the ROOT A authority.
3. **Why F3R2 exists:** the governance hand-off isolated mechanical closure from file-governance closure. F3R1 G0→G2 produced the mated/configured carrier; F3R2 added operational definitions, poses, clearance evidence and a machine gate, while the top SLDASM remained byte-identical to F3R1 V3. No V4 was built, and human review remains open.
4. **Donor vs current:** Donors = V2_2_NATIVE tree (D1, ratified canonical), protected B51 articulated arm (D2), 4 V2_2 wing panels (D3), HAGA_HIFI_FREECAD (C1-B visual-only), reBot-DevArm vendor files, V2_3 (rejected, hash drift), FreeCAD F3P3 top assemblies (demoted EVIDENCE_ONLY). Current = accepted URDF + geometry SSOT (L0), FreeCAD authoritative C1-A engineering estimates (L1-adjacent, mass-excluded), F3R1-V3/F3R2 machine-selected native candidate (L1, pending human review), F3R2 G3C/G3D/G4 definitions (DEFINED_NOT_MODELLED).

---

## 1. The chain, link by link

Legend: **DONE** (closed with evidence) / **ACTIVE** (current authority, work may continue) / **HOLD** (blocked, evidence registered) / **NOT_STARTED**. Residence: REPO (active F3R1/F3R2 rescue copies, currently untracked) / WT (verified source mirror and full historical lineage) / ARCH.

### 1. Requirements
- **Authority:** `REPO\20_engineering\stage1_spacecraft_layout\03_mechanical_layout_notes\` (stage1_layout_design_brief, servicer_6U/12U + robot_mount_adapter + target requirements, `_v0`); `REPO\01_project\competition\F3_P0_mechanical_architecture_freeze_draft_20260804.md` (F3-A..F3-E requirement mapping to V2_3 reality).
- **Status:** DONE (stage-1 v0, 2026-07-08/09); F3-level requirements = planning draft, never upgraded to authorization (`PDR_STAGE_PLANNING_DRAFT`).
- **Superseded:** 140×140 and 90×180 adapter footprints (D-1, deprecated); 7-DOF generic arm narrative (D-5 audit corrected to 6R).
- **Holds:** F3 requirements remain draft pending HAG-F3-P0/P1 human gates.

### 2. Interface (spacecraft ↔ arm)

- **M3R controlling correction:**
  `REPO\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\M3_interface_authority\M3R_INTERFACE_AUTHORITY_GATE.json`
  is the current ruling. `185.25/198.0/208.0/210.405 mm` are respectively the
  dynamics origin, existing plate face, physical installation face, and four
  disconnected screw-end faces. The last value is not a continuous flange.
  The former G30 face-count result and G31 `8 x M3` ring are class D,
  superseded evidence. A corrected 4-M4-class Stage-A ring and 4-M6-candidate
  Stage-B body exist as FCStd/STEP only; M6 mating load-bridge geometry,
  SolidWorks native files/cold reopen, physical fit-up, clocking-dowel fit and
  tolerance, M6 edge-margin analysis and formal fastener MoS remain HOLD.
- **Authority:** D-1 sole mount baseline 160×160×12 mm plate + Ø100×15 mm boss (`REPO\20_engineering\config\geometry\arm_mount_v1.yaml`; `06_reviews\geometry_audit_decisions_v1.md`, frozen 2026-07-10). T_SM frozen stack (F3R2 G30, `REPO\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\F3R2_TSM_INTERFACE_STACK.yaml`): **185.25 mm = M dynamics frame (no material) / 198.0 = adapter plate outer face / 208.0 = Central_Boss physical mount face / B601 flange at 210.41 (8×M3, bolt circle R45.18–45.33)** — "three distinct features on the same X axis, frozen together"; the old `T_SM_TRACK_CONFLICT` is thereby voided as frame-vs-face conflation. Load path contiguous 171→208 (5 parts, all share r50 bore).
- **Status:** DONE (frozen, measured cross-check PASS).
- **Superseded:** D-F3R1-05 ("base_link has no flange") — falsified by G30/G31 B-rep measurement.
- **Holds:** 2.41 mm physical gap (208.0→210.41) must be occupied by the G3-1 base-interface adapter ring — DEFINED (6 parts, 298.9 g) NOT modelled. Joint PCD/bolt/dowel TBD pending vendor interface drawing (`JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml` open_items).

### 3. Master Skeleton
- **Current:** (a) `00_Master_Skeleton_V2_2.SLDPRT` (280,052 B; 18 datum planes + 3D envelope sketches + 34 parameter properties, zero solid bodies; carries C5 negative-result params) — inside `REPO\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\SPACECRAFT_V2_2_NATIVE_COPY\00_Master_Skeleton\` (also in the active F3R2 tree and the WT source mirror). This is the skeleton that actually drives the current native assembly. (b) `REPO\20_engineering\cad\freecad_authoritative\B51R1_MASTER_SKELETON_FREECAD.FCStd` — FreeCAD skeleton, 9/9 validation PASS, zero solids, clock 25° (`40_evidence\c1_evidence\MASTER_SKELETON_VALIDATION.json`).
- **Status:** DONE for both roles (native driver / parametric SSOT). 
- **Superseded/failed:** B5.1R1 *native* Master Skeleton V2 — Stage A PASS, **Stage B `FAIL_CLOSED_COORDINATE_API_HANG`** (2026-07-29/30); never finalized in SolidWorks (`40_evidence\c1_evidence\B51R1_PHASE1_INTERMEDIATE_GATE_20260729.json`). `B51R1_FREECAD_SSOT_PARAMETERS.yaml` = L1 interface/system truth parameter names (spreadsheet aliases mandatory).
- **Holds:** none open against the skeleton itself; parameter register carries O3 (`T_SM_DYNAMICS_X` vs `MOUNT_FACE_X` dual track) — superseded by F3R2 G30 stack ruling, register not yet re-issued.

### 4. B601 kinematics (L0)
- **Authority:** accepted URDF (see §0.2) + `REPO\20_engineering\config\geometry\arm_b601_v1.yaml` (geometry SSOT; HYBRID provenance: kinematics/meshes/gripper from `reBot_B601_DM_with_gripper.urdf`, inertial set from `reBot-DevArm_fixend.urdf`; 6R + 1 fixed + 2P; confidence medium pending physical weighing).
- **Status:** DONE / frozen. `modify_accepted_B601_URDF` is prohibited by the B5.1R1 phase-1 authorization and every downstream gate; F3R2 `protected_post = ALL_PROTECTED_UNCHANGED`.
- **Holds:** physical weighing of the real arm (evidence-rank-1 upgrade) — open external dependency.

### 5. B601 engineering CAD (native arm)
- **Current:** `REPO\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\B601_ARM_B51_COPY\assembly\B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM` (25,720,876 B, current sha256 `597C297526BC4111C3424535139B8A1C93906E7A799FF5346D030700FEF1A32F`). `F3R1_ARM_RECOPY_PROOF.json` proves equality only at initial recopy time; the integrated carrier was later resaved/changed and is **not** byte-identical to the protected D2 donor (25,610,223 B, sha256 `603B87BBD4398FDDB3F732FFBFA7E1C080ED91ED6E0A026D56CBDCBA08DE2E22`). The carrier has 20 components (8 vendor link solids incl. `B51_REF_gripper_detail`, 12 datum hinge parts), 25 mates (13 MateLock + 6 Concentric + 6 Coincident), **all 6 revolute joints ALIGNED vs accepted URDF** (origin err < 0.5 mm, axis dot = 1.0) — F3R1 P2/G2 evidence. Gripper solidity: **58 solids** (L24/R24/palm10, mirrored per URDF jaw axis; OPEN 82.23 mm / PREGRASP 50.50 mm no-collision, mesh-measured) — F3R2 G33, supersedes the "single solid" register.
- **Status:** DONE as engineering carrier (kinematic fidelity verified). NOT manufacturing-grade (no joint housings/bearing seats — F3-A scope, never authorized).
- **Superseded:** B5.0 fixed-q0 rigid arm reference; V2_3 KINEMATIC_PROXY/MASS_SURROGATE (off-tree with V2_3; mass surrogate always EXCLUDED from dynamics). B601_STOWED_HIFI: **CONFIRMED_NOT_CREATED** (35 MB vendor STEP import failure history) — never built in any generation.
- **Holds:** two independent finger components matching URDF prismatic joints not yet modelled as separate CAD parts (G3-05 residual; "no mimic" rule).

### 6. Base adapter

- **M3R current candidate:**
  `03_native_cad\M3_interface_authority\cad\B601_BASE_INTERFACE_RING_F3R2.step`
  + `B601_LOAD_SPREADING_ADAPTER_F3R2.step` + their two-object FCStd document.
  Independent geometry build evidence is PASS, but this is not in the active
  top assembly and is not a manufacturing release. The legacy M8 BCD130 set is
  rejected because one hole is breached by the harness slot; the four complete
  M6 holes at (+/-70,+/-70) are only a competition primary-pattern candidate
  until a live mating load bridge is measured.
- **Current (interface reference):** `REPO\20_engineering\cad\spacecraft_layout\robot_mount_adapter_v0\` (STEP+STL+SLDPRT triple-evidence, D-1 sole baseline; 1.2 kg block-model estimate, confidence low).
- **Current (manufacturing pilot):** `REPO\20_engineering\cad\freecad_authoritative\B601_BASE_ADAPTER.FCStd` (+ `.step`, `_DRAWING.FCStd`, `_FEM.FCStd`, `_BOM.csv`) — **F2_PASS** (2026-08-04): single valid solid 384,988.78 mm³, AL6061-T6 estimate **1.0395 kg** (`MASS_AUTHORITY=DESIGN_ESTIMATE_ONLY_EXCLUDED_FROM_URDF`), TechDraw A4, CalculiX unit-load `PASS_WITH_SCOPE` (**not load-qualified**).
- **F3R2 G31:** recessed base-interface ring (8×M3 over r50 bore), 6 parts 298.9 g — `G31_BASE_INTERFACE_DEFINED`, NOT modelled.
- **Status:** DONE (F2 pilot, claim ceiling `PILOT_PART_MANUFACTURING_DEFINITION_COMPLETE`); drawing human review pending.
- **Superseded:** 140×140 / 90×180 footprints (D-1). V2_3 `Adapter_Plate.SLDPRT`/`Central_Boss.SLDPRT` inherited as V2_2 donor parts, not redesigned.

### 7. Stowage (stow vector / pose)
- **Current:** O13 stow vector v3 — clock 25° (ratified `FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`), q = [145.572, −168.0, −57.0, −41.143, −20.954, −3.0] deg, geometric clearance 15.56 mm PASS — `STOW_VECTOR_STATUS = CANDIDATE_HOLD` (contact qualification open). F3R2 froze it as `Q_STOW_ENGINEERING_CANDIDATE` with hold `O13_V3_CANDIDATE_HOLD_PROVISIONAL` (`F3R2_ARM_POSE_REGISTER.csv`: min_arm_to_saddle = 0.0011 mm — it rests on the placeholder saddles).
- **Status:** HOLD (candidate; never promoted to runtime).
- **Evidence:** `ARCH\RECOVERY_EVIDENCE\RECOVERY_O13_STOW_VECTOR_V3_REPORT.md`; `WT\Space_Embodied_Robot_CAD_V2_2_NATIVE\O13_STOW_VECTOR_V3_REPORT.md`; F3R2 pose freeze.

### 8. Cradle / stow saddles (G07/G08/Mid)
- **Current physical CAD:** `REPO\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\SPACECRAFT_V2_2_NATIVE_COPY\04_ARM_STOW_SUPPORT\parts\{Aft,Mid,Fwd}_Saddle.SLDPRT` + `Launch_Lock_Interface_Reference` + `Release_Clearance_Envelope` — **all three saddles are hollow placeholder shells** (1200 mm² top face pointing DOWN, two 4 mm ledges, cavity floor z=113.15). R3-04 **NOT closed**.
- **Definitions (not modelled):** F3R2 G3D/G32 `G32_SUPPORTS_V2_DEFINED` — support heads 54×54 / 34×34 / 34×34.4, 16 parts, 336.1 g; P5B pad specs: G07 disc-spring+PTFE 10 N/mm, G08 VMQ60A 5 N/mm; Mid = 2.00 mm nominal-gap backup (F3_P4 decision S3).
- **Stations (measured O13 v3):** Aft X[−20,0] z=261.08 (tower 147.93) / Mid X[80,100] z=214.92 (101.77) / Fwd X[160,180] z=209.42 (96.27); contact allocation G07=Aft(link6, Tz+Tx+Rx), G08=Fwd(gripper_link, Ry) (F3_P2 freeze).
- **Status:** HOLD — real supports DEFINED_NOT_MODELLED; contact-pad material TBD (HAG-A blocked); launch spectrum undefined.
- **Retracted negative:** F3R1 review #1's "saddle penetration −27.0/−19.3/−58.9 mm" was **disproven** (bbox-vs-bbox artifact; real proximities: gripper@G07 +0.1 mm, link5@Mid −0.4 mm — search seeds only).

### 9. Solar wing (panels + root mechanism)
- **Current:** `REPO\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\03_native_cad\WING_PANEL_DONORS\WING_{L,R}_{DEPLOYED,STOWED}.SLDPRT` (4 parts, 59–65 KB; 6 planar faces, **0 cylindrical faces, no hinge bore**, 200×227×6 mm) + wing-root hardware in the V2_2 donor (`05/06_Solar_Array_Root_*`: hinge pins r=4.000 @ |y|=143.15, ears r=4.200, hard stops, torsion springs, root spines, solar-side HDRM parts).
- **Status:** HOLD — **D-F3R1-06 OPEN: all 4 panels sit 30.0 mm off the true hinge axis** (panels at |y|=113.15 vs pins at |y|=143.15); G2 wing angles are `KINEMATIC_CONFIGURATION_CANDIDATE` only. WING_ROOT_LUG parts DEFINED (G3C/G3-01) NOT modelled.
- **Preserved negatives:** C5 stowed package 238.3 > 226.3 mm (+12.0, `NEGATIVE_PRESERVED_NOT_CLOSED`); wing-root mechanism min width 302.3 mm (unresolvable, registered into Master Skeleton).
- **Panel dynamics (sim side):** 0.3483933 kg/panel SSOT placeholder (D-4; real areal density 2–5 kg/m² → 5–10× discrepancy, Yang-Heng TODO-3; f1 nominal 1.0 Hz + 0.7/1.3 envelope).

### 10. HDRM
- **Solar-wing HDRM:** EXISTS (V2_2 donor: `HDRM_Base_{1,2}_*` + `HDRM_Rod_{1,2}_*` ×2 sides — 4 base + 4 rod parts).
- **Arm HDRM:** does NOT exist as hardware. F3R2 G4 `G4_DEFINED_NOT_MODELLED`: demonstrator definition only (latch/preload/stroke candidate 6 mm; states ARM_HDRM_LOCKED/RELEASE_START/RELEASED/RELEASE_FAILED/GROUND_UNLOCK; starting envelopes `Launch_Lock_Interface_Reference` x[−10,10] y[−84,84] z[132,168], `Release_Clearance_Envelope` x[−110,70] y[−70,110] z[264.1,354.0]). No device selected (OI-7).
- **Earlier FreeCAD-line closure:** F3_P4 closed HDRM *interfaces* (flange 60×60×10, PCD Ø50, 4×M5, preload 50 N, stroke 5 mm, residual <2 mm, manual ground unlock) as `MODEL_PROCUREMENT_TBD`.
- **Status:** HOLD (solar side: donor geometry only; arm side: definition only, flight qualification not claimable).

### 11. Harness
- **Current:** envelopes only — `Harness_Passage.SLDPRT` (x[64,171] y[−30,30] z[−82,−58]) and `Harness_Service_Loop_{Left,Right}.SLDPRT` in the V2_2 donor; F3R2 G4 camera/harness definitions (`08_camera_harness\F3R2_CAMERA_HARNESS_GRIPPER.json`); routing rule "no tension / no kink / no through-axis, bend radius ≥ HARNESS_MIN_BEND_RADIUS×OD" in `JOINT_INTERFACE_CONTROL_DOCUMENTS.yaml` (per-joint envelopes J01–J06). F3_P3 harness sweep = PASS provisional (FreeCAD line).
- **Status:** NOT_STARTED as built geometry (routing provisions/envelopes only). Cables themselves are BUY.

### 12. Sensors
- **Camera:** **NOT modelled anywhere** (F3R2 OI-2; every camera-visibility criterion `NOT_EVALUATED_NO_CAMERA`). Camera optical frame PROPOSED_NOT_CALIBRATED (F3R2 frame mapping, parent link6). F3_P3 camera FOV report: PASS with 3 occlusion holds (FreeCAD line, envelope-level).
- **F/T sensor:** mount only as F3-E/EE_V1 plan; BUY item, TBD.
- **Grasp features / visual markers:** D-6 — CAD JSON `grasp_points_mm` is the sole source (`target_models_v1.yaml`); sim_02 hardcoded value deprecated.
- **Status:** HOLD (camera) / NOT_STARTED (F/T mount) / DONE (grasp-point SSOT).

### 13. End effector (gripper + EE stages)
- **Gripper (kinematics, L0):** accepted URDF — `gripper_link` (fixed J07) + `gripper_left`/`gripper_right` (2 independent prismatic, 71.5 mm travel each, no mimic); meshes `REPO\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper\` (10 STL, ~27 MB, git-untracked pending LFS decision). Vendor hardware STEP: `80_third_party\vendor\reBot-DevArm\hardware\reBot_B601_DM\reBot_B601_DM_v1.1_20260425.step` (177-file vendor tree, gitignored, disk dependency — backup gap registered).
- **Gripper (native CAD):** 58-solid mirrored solid set measured (F3R2 G33); two *independent finger components* not modelled (G3-05 residual). Gripper T_c (contact bandwidth) measurement pending hardware team (sim_11 gate dependency).
- **EE stages:** EE_V1 (wrist flange/camera/FT/capture center) + EE_V2 (compliant) = competition priority, EE_V3 deferred post-competition — all PLANNED_NOT_AUTHORIZED (F3-P3 scope, never gated).
- **Status:** DONE (URDF kinematics) / HOLD (native fingers, EE stages).

### 14. Top assembly
- **Current machine-selected candidate:** `F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM` (§0.1) — top components: `B51_B601_ARTICULATED_ENGINEERING_ARM-1`, `Space_Embodied_Service_Spacecraft_V2_2-1`, `WING_{L,R}_{DEPLOYED,STOWED}-1` (6 top components; 82 total; 6 top mates: 1 MateParallel + 1 MatePlanarAngleDim 25° clock + 4 MateCoincident wing; 0 mate errors; root = spacecraft sole fixed component). Lineage inside F3R1: G0 `…INTEGRATION.SLDASM` (sha `5F1CB650…`) → G1 `…V2_MATED.SLDASM` (`E752FFC4…`) → G2 `…V3_CONFIGURED.SLDASM` (`19D85E9C…`) → F3R2 candidate = V3 bytes renamed. **No V4 was ever built.**
- **Residence:** active copies now reside under `REPO\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806\` (363/363 hash-identical rescue) and `REPO\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\` (482/482 hash-identical rescue); WT remains the verified source mirror. Both ROOT A trees are untracked (`git ls-files=0`) and remain on CM-acceptance, backup/DR and native-reference-integrity HOLD. The full V0.1→V2.3/B5.0→B5.1R1 historical CAD lineage (3,432 files / 4.0 GB) remains WT-only.
- **Status:** MACHINE-SELECTED CANDIDATE / `PENDING_HUMAN_REVIEW`, not a ratified baseline. Final gate = 11/14 with C11/C12/C14 failed, four HOLD verdict tokens and seven open items. Native reference integrity: R2A2 audit `REPAIR_REQUIRED` (3 components resolve outside F3R2 tree in STOWED_ENGINEERING_CANDIDATE, 1 in others; final gate C1 registered `refs_outside_f3r2: 10`).
- **Rejected/demoted tops:** V2_3 integration tree (R3-02 hash drift `76A3B289` vs declared `30C09B50`); FreeCAD `SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd` (R3-01 zero geometry → STATE_REFERENCE_ONLY) and `F3_P3_TOP_ASSEMBLY.FCStd` (R3-03 → EVIDENCE_ONLY).

### 15. Configuration (assembly configs + poses)
- **Assembly configurations (8 registered/gate-checked in V3/F3R2):** STOWED_ENGINEERING_CANDIDATE (AUTHORITATIVE), SOLAR_DEPLOY_ARM_LOCKED (PROVISIONAL, end-state only), DEPLOYED_NOMINAL (AUTHORITATIVE), L_FAIL / R_FAIL / DEPLOY_FAILED_BOTH (AUTHORITATIVE), PARTIAL (**UNKNOWN_HOLD_NO_AUTHORITY** and explicitly `NOT_DIFFERENTIATED_FROM_DEPLOYED_NOMINAL`; no authoritative partial angle), SERVICE (**PROVISIONAL_HOLD** pending human ratification). Thus “8 configs” does **not** mean eight differentiated states: seven are geometrically differentiated and PARTIAL intentionally is not. Legacy STOWED_LOCKED/DEPLOYED_NOMINAL/默认 also present (10 on cold reopen). Each registered row reports 6 mates / 0 errors / drift 0.0 / interference 0 / `RuntimeCompliance=FALSE`, `EngineeringEvaluationOnly=TRUE` (F3R1 G2, 15/15 PASS).
- **Frozen arm poses (F3R2 G3B, 5):** Q_AS_BUILT_REFERENCE (0s; NOT a control start — joint2/3 sit on their 0.000° stops, margin 0.0°), Q_STOW_ENGINEERING_CANDIDATE (hold), **Q_DEPLOYED_HOME** [−90,−120,−60,0,−30,0] (runtime, controller init truth), **Q_RELEASE_CLEAR** [−90,−120,−120,−60,−30,0] (runtime; release *sequence* not authorized), **Q_SERVICE_READY** [−90,−60,−120,−30,0,0] (runtime; SERVICE config still PENDING_RATIFICATION). 20 transition rows.
- **State machine (F3R2):** runtime states DEPLOYED_NOMINAL / SERVICE_STAGING / SAFE_STOP / MANUAL_RECOVERY; authorized transitions DEPLOYED_NOMINAL↔SERVICE_STAGING (G5-swept); all others non-runtime.
- **Status:** DONE for registration/gate checks and seven-state geometric differentiation, with HOLDs on PARTIAL, SERVICE and q_stow.

### 16. Interference (native)
- **F3R1:** clean-session native interference **0 clashes / 0 mm³** for the eight G2 registered configuration rows (`04_configurations\G2\F3R1_G2_CONFIGURATION_MATRIX.csv` plus G2 gate/execution evidence). `05_clearance\F3R1_MECH_REVIEW.json` (sha256 `c065ce17…`, re-verified 2026-08-08) supports the G0 whole-assembly clean scan, not by itself an eight-config claim. One phantom 649-clash report was session contamination (D-F3R1-07); only clean-session results are trusted.
- **F3R2:** C13 native B-rep interference RAN (DEPLOYED_NOMINAL 20 pairs, STOWED_ENGINEERING_CANDIDATE 94 pairs) but **C14 FAIL: pair→component attribution unreachable on this SolidWorks 2024 install** (IInterference.GetComponents/GetBox broken; ARM-DIFFERENCE workaround blocked by SetSuppression2). Offline CAD-mesh measurement (instrument self-checked): DEPLOYED_NOMINAL & SERVICE = zero arm-involved interference; stow family = three arm↔saddle-placeholder contacts 0.001–0.319 mm.
- **Status:** HOLD (`NATIVE_PAIR_ATTRIBUTION_HOLD`); arm-clearance claims rest on the offline mesh measurement, not native pairs.

### 17. Clearance (continuous / path)
- **F3R2 G5:** official runtime path — 1/6 segments defined+swept PASS (worst 60.328 mm); 5/6 official segments `NOT_DEFINED` (no authorized q for SERVICE_DOCKING/GRASP/TRANSPORT/ASSEMBLY/RETRIEVED_NOMINAL — C11 fails by design). Engineering release path C12 FAIL at t=0 only (0.0011 mm = stow pose resting on placeholder saddles; recovers to 9.2 mm @ t=0.125, 60.3 mm @ t≥0.375).
- **Earlier:** F3_P3 G8a nominal continuous clearance PASS (3 paths × 8 categories, FreeCAD line); G8b robust = `UNKNOWN_MARGIN_INCOMPLETE`. F3R1: face-to-face continuous sampling "not yet built" (was G5/P6 scope).
- **Status:** HOLD — full end-to-end official-path verification impossible until service-sequence pose authority exists; stow t=0 contact resolves only when real supports are modelled.

### 18. Mass (ledger)
- **L0 (frozen):** arm 4.4293 + gripper 0.2665 = **4.6955559493429862 kg** — accepted URDF only; `cad_mass_override_authorized=false` everywhere. Per-link values registered in `FREECAD_MASS_REGISTER.yaml`.
- **CAD estimates (additive, never replacing):** base adapter 1.0395 kg (HIGH, AL6061-T6); F3R2 external hardware budget **507.22 g total, provisional** (WING_ROOT_INTERFACE 89.292 / STOW_SUPPORT 94.808 / ARM_HDRM_CAMERA_HARNESS 302.856 / FASTENERS 20.26 g; tier-3 ±15 %, tier-4 −40/+80 %; inertia `NOT_COMPUTED` — parts don't exist as solids; use as point masses on the spacecraft body, NOT on arm links).
- **Spacecraft side:** 24.0 kg whole (v0 rigid sims) / 23.3032134 kg bus + 2×0.3483933 kg panels (v1 ANCF split; closure ≡ 24.000 kg) — confidence low; mass budget `UNSOURCED_BLOCKED` at system level.
- **Status:** DONE (arm, L0 frozen) / HOLD (system budget, saddles/HDRM/EE masses TBD pending modelling).

### 19. FEA
- **Done:** base-adapter CalculiX unit-load plumbing `PASS_WITH_SCOPE` (explicitly **not load-qualified**).
- **Framework only:** F3_P4 = `PRELIMINARY_ANALYSIS_FRAMEWORK`, execution pending; Mid saddle decision = PENDING_FEA; modal cases 1/2 (arm deployed / whole-sat) = 待 F3-P1/P2 (never run).
- **Status:** NOT_STARTED for the structure as a whole. No strength/stiffness/modal/thermal numbers exist anywhere — claiming any is prohibited.

### 20. Manufacturing candidate
- **Only candidate:** `B601_BASE_ADAPTER` (F2 pilot: parametric recompute, 9 fully-constrained sketches, STEP roundtrip, A4 drawing, BOM row, mass register row) — claim ceiling `PILOT_PART_MANUFACTURING_DEFINITION_COMPLETE`; drawing human review pending. BOM plan: `REPO\20_engineering\cad\freecad_authoritative\F3_BOM_PLAN.csv` (28 rows, MAKE/BUY/ENVELOPE, freeze statuses F2_PASS / F3-P1..P3 / CANDIDATE_HOLD).
- **Everything else:** PLANNED or DEFINED_NOT_MODELLED. `F3R2_FINAL_GATE.json` sets `next_stage_authorized=true` only for F4 deployed-control / embodied continuation under the registered HOLDs; it neither human-ratifies the mechanical candidate nor authorizes V4 or residual CAD writes. Any remaining mechanical modelling requires a new, scope-specific change authorization. `declare_manufacturing_ready` / `declare_flight_ready` remain prohibited.
- **Status:** DONE (1 pilot part) / NOT_STARTED (rest).

### 21. Simulation export (L2)
- **Consumers of the accepted URDF:** the project-integrated mechanical chain is pure Python: `sim_05_free_floating_arm\b601_model.py` (direct xml.etree parse; gripper merged into link6) ← sim_05 dynamics, sim_11 coupled (config_loader asserts T_SM vs frame_tree SSOT), sim_09 grasp evaluator (IK/limits/FK), control_01, control_02, e16_sync_capture. A MuJoCo checkout exists only as third-party/reference material; no project MJCF, MuJoCo consumption, mission integration or authority was found. No project-integrated Isaac/ROS2/USD/xacro mechanical model was found. **e16 hash-pins the URDF** (`config\experiment_v1.yaml`) — pin matches the current file (valid).
- **Collision representation:** in the URDF, `<collision>` = the same 10 STLs as `<visual>` (no hulls/primitives); sim_09 uses a capsule model (r=45 mm over FK chain; bus=box; panels=thin boxes; targets=cylinder/box; assumptions A1–A7 in `config\grasp_evaluator\collision_geometry_v1.yaml`); EE tool envelope proposal 2×capsule D30×120 mm = TBD (`capture_interface_v1.yaml`).
- **SAFE-00:** consumes **no URDF/mechanical model** — hash-bound decision core over frozen evidence (`safety_policy_v1.yaml`; bus mass reference 24.0 kg; sim_10/11/12 gate JSONs; baseline stdout logs). Verdict PASS(47/47) `PENDING_REVIEW`, `next_stage_authorized=false`.
- **KNOWN DEFECT (NEW, found this recon):** `sim_05_free_floating_arm\b601_model.py:39-40` builds `URDF_PATH = <repo_root>\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf` — the **pre-REORG04 path** (no `cad\` at repo root since 284c882, 2026-07-22). The whole URDF-consuming chain (sim_05/09/11, CTRL-01/02, e16) therefore cannot re-execute as-is; frozen PASS evidence insulates existing verdicts but they are not regenerable until the path is repaired (one-line fix, not authorized by this recon).
- **Legacy superseded:** `robot_mount_adapter_v0\reBot_arm_v0_min.urdf` (2-DOF-era; still hard-coded in sim_03/sim_04/sim_06 physics — documented superseded; the 13.1°/19.20° base-reaction figures trace to it and `arm_b601_v1.yaml` impact_note demands sim_05 re-derivation before any report figure).

---

## 2. Standing prohibitions inherited by every future round

- Never modify: accepted URDF, mass/inertia ledger, V2_2 donor tree, G0/G1/G2 assemblies, frozen sim configs/gates. If a future scope-specific change authorization permits native CAD work, build V4 and never overwrite the frozen carriers; the present F4 continuation token alone is insufficient authority.
- Never claim: manufacturing-ready, flight-ready, continuous-clearance PASS (before real supports + full official path), CAD mass = dynamics mass, FreeCAD detail = authority, static images = motion evidence.
- Session discipline (D-F3R1-07): kill all SLDWORKS.exe, confirm 0, wait ~22 s before any write; PROTECTED_CHECK PRE/POST every round.
- q_stow stays `O13_V3_CANDIDATE_HOLD_PROVISIONAL`; PARTIAL has no angle authority; SERVICE pending ratification; deploy transit path unauthorized (G4 continuous motion scope).

## 3. NEW_CONTRADICTION register (found by this recon, 2026-08-08)

- **NC-1 (paths, rescue resolved / CM HOLD remains):** the 18:12 rescue copied F3R1 **363/363** and F3R2 **482/482** files into the active ROOT A paths, with source/destination hash manifests identical; WT remains untouched as the verified source mirror. The prior pre-rescue absence claim is obsolete. The new ROOT A trees are still untracked (`git ls-files=0`), so CM acceptance, backup/DR and reference-integrity HOLDs remain. The full historical `20_engineering\cad` lineage remains WT-only.
- **NC-2 (status, execution resolved / review HOLD remains):** `F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807` executed on 2026-08-07 and was rescued into ROOT A. Its machine gate is 11/14 (C11/C12/C14 fail), four HOLD verdict tokens, seven open items, `next_stage_authorized=true`, and `PENDING_HUMAN_REVIEW`; therefore it is a machine-selected candidate, not an accepted baseline. `PROJECT_START_HERE.md` has now been brought forward to this state.
- **NC-3 (ordering, inherited):** three F3R2 orderings exist — F3R1 human-review #2 (saddles first P5-A → mates P5-B → configs P5-C), W3-F plan (mates/configs P0 → saddles P1, declared "顺序不可颠倒" by W4 root map), F3R1 G3 recommendation (WING_ROOT_LUG strictly first). W3-F is the one all CM docs cite; see `F3R2_EXECUTION_ORDER.md`.
- **NC-4 (candidate-file identity):** the F3R2 SLDASM whose filename contains `OPERATIONAL_BASELINE` is byte-identical to F3R1 V3 (sha `19D85E9C…`) — no V4 exists. The filename is not a human gate claim: assembly bytes are unchanged, while definitions/poses/thread were added around the machine-selected candidate.
- **NC-5 (gripper):** F3R2 final gate OI-3 "gripper is a single CAD solid" was falsified ~8 h later by G33 (58 solids, mirrored L24/R24/palm10, OPEN 82.23 mm). Gate JSON was not updated; downstream readers must use G33.
- **NC-6 (health check, current):** structure checks PASS; aggregate result is **FAIL 1**, solely because the worktree is dirty (use the health-check's live `porcelain_entries`, because PL1 report creation changes the count). This is not a mechanical-content failure, but the storage/CM gate remains red until the dirty state is dispositioned.
