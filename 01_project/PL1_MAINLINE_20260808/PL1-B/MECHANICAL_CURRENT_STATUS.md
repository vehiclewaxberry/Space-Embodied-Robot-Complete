# MECHANICAL_CURRENT_STATUS.md

**PL1-B status board, 2026-08-08 (post-salvage).** Statuses: **DONE** / **ACTIVE** / **HOLD** / **NOT_STARTED**. REPO = ROOT A; WT = retained source mirror and the only home of the full pre-F3 historical CAD lineage. F3/F3R1/F3R2 are present in REPO as untracked hash-verified copies.

## 0. Post-M3R controlling correction

- Old G30/G31 `8 x M3 flange` claim: **REJECTED/SUPERSEDED**. It double-counted
  two split cylindrical faces on each of four HM4-75 screw shafts.
- Current competition B601 input: **4 x M4-class axes**, 64 x 64 mm square,
  equivalent PCD 90.509642 mm; AS-BUILT competition authority only.
- Corrected ring+load-spreading body: **FreeCAD/STEP geometry PASS**, but
  `M3_TWO_STAGE_ADAPTER_INTERFACE_CLOSED = HOLD` because SLDPRT/SLDASM, native
  cold reopen/interference, B601 fit-up, live M6 mating geometry, clocking-dowel
  fit/tolerance, M6 edge-margin analysis and formal fastener MoS are absent.
  Rev B already contains a unique asymmetric dowel candidate, so the former
  45-degree geometric ambiguity itself is resolved.
- G33A V2 addendum: 58/58 mesh paths hash-resolved and offline three-state
  binding PASS; separate native finger parts/mates/configurations remain HOLD.
- Controlling evidence:
  `20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/`.

## 1. Status board

| Item | Status | One-line fact | Residence |
|---|---|---|---|
| Accepted B601 URDF (L0) | **DONE / frozen** | hashes + mass re-verified 2026-08-08 (see ruling) | REPO (+ WT copy) |
| Geometry SSOT `arm_b601_v1.yaml` | **DONE / frozen** | hybrid provenance, 6R+1F+2P, T_MA0 identity | REPO |
| Vendor source (reBot-DevArm) | **DONE + risk** | 177 files imported (CM3); gitignored, no cold backup | REPO |
| FreeCAD authoritative C1-A | **DONE (imported truth)** | 36 files; F0/F1/F2 PASS; adapter pilot F2 | REPO |
| HiFi donor C1-B (HAGA) | **DONE (donor-locked)** | 21 files; visual-only, mass-excluded | REPO |
| v0 spacecraft layout assets | **DONE (superseded-era)** | build123d block models, low confidence; still feed rigid sims | REPO |
| V2.2_NATIVE frozen baseline | **DONE (frozen donor)** | 108-file canonical copy, sha `30C09B50…`; PENDING_HUMAN_REVIEW since 2026-07-27 | WT only |
| V2_3 three-representations | **DONE (frozen) + gap** | proxy+surrogate built; **STOWED_HIFI never created** | WT only |
| B5.1R1 native skeleton V2 | **HOLD (failed)** | Stage B `FAIL_CLOSED_COORDINATE_API_HANG`; never finalized | WT / 40_evidence |
| F3R1 integration package | **DONE (assets) / CM HOLD** | 363/363 source-destination hashes equal; G2 15/15; untracked/not CM-accepted | REPO + WT mirror |
| F3R2 terminal closure | **HOLD (machine-selected, unratified)** | 482/482 hashes equal; 11/14 gate; 4 engineering HOLDs; `PENDING_HUMAN_REVIEW` | REPO + WT mirror |
| Active F3 package salvage | **DONE (copy/hash) / CM HOLD** | physical copy complete; backup/tracking/reference cold-reopen not closed | REPO + WT mirror |
| Full historical CAD lineage | **HOLD (not copied)** | V0.1→V2.3 + B5.0→B5.1R1, 3,432 files / ~4.0 GB | WT only |
| WING_ROOT_LUG parts | **NOT_STARTED (defined)** | G3C definition frozen; 30.0 mm gap physically open | REPO + WT mirror (definition) |
| Real G07/G08/Mid supports | **NOT_STARTED (defined)** | G32 supports V2 frozen; placeholders still in CAD | REPO + WT mirror (definition) |
| ARM HDRM | **NOT_STARTED (defined)** | G4 demonstrator definition; no device selected | REPO + WT mirror (definition) |
| Camera model | **NOT_STARTED** | nothing exists; all visibility criteria NOT_EVALUATED | — |
| Harness built geometry | **NOT_STARTED** | envelopes + routing rules only | REPO + WT mirror (envelopes) |
| EE stages (V1/V2) | **NOT_STARTED** | F3-E scope, never authorized | — |
| Gripper two-finger CAD components | **NOT_STARTED** | 58 solids measured (G33); independent finger parts not cut | — |
| Service-sequence poses (5 states) | **HOLD (no authority)** | inventing q vectors = fabricating evidence (C11 by design) | — |
| Native pair attribution | **HOLD (tooling)** | SW2024 IInterference API unreachable; workaround blocked | — |
| FEA (structure/modal) | **NOT_STARTED** | adapter unit-load plumbing only | — |
| Manufacturing release | **NOT_STARTED** | 1 pilot part (adapter) at definition-complete; review pending | REPO |
| System mass budget | **HOLD** | bus 23.3033 kg low confidence; panel mass placeholder 5–10× off | REPO |
| Sim chain URDF parser path | **HOLD (broken)** | `b601_model.py` points at pre-REORG04 path; frozen evidence only | REPO |

## 2. What is REAL engineering today

- Accepted URDF + geometry SSOT (L0): mass/inertia/kinematics — verified, frozen, consumed by all dynamics.
- F3R1↔F3R2 native assembly: V2_2 donor structure + B51 arm (URDF-aligned) + wing donors, 8 configs present/gate-checked, 6-mate top, 0-error. PARTIAL is not differentiated and SERVICE lacks angle authority; do not claim 8 fully differentiated configs.
- F3R2/M3R measurement rulings: T_SM interface stack (185.25/198/208) plus four disconnected HM4-75 screw-end faces at x=210.405; the old `8 x M3 flange` claim is rejected. Gripper 58-solid grouping, pose freeze and clearance numbers remain real measured engineering within their stated scopes.
- FreeCAD C1-A: parametric skeleton + carriers + kinematic assembly (11/11 consistency vs URDF) + base-adapter manufacturing definition (drawing/BOM/FEM plumbing) — real, claim-capped at pilot level.
- Joint ICDs, structure tree, BOM plan, mass register — real interface engineering, with TBD fields honestly marked.

## 3. What is VISUAL-ONLY CAD (no engineering claims allowed)

- HAGA_HIFI_FREECAD donor (C1-B): `ACCEPTED_VISUAL_GEOMETRY_CANDIDATE`, `DynamicsMassAuthority=EXCLUDED`, `ManufacturingAuthority=DONOR_REFERENCE_ONLY`.
- V0.1/V1.0 assemblies (`GEOMETRY_ONLY` / `ENGINEERING_VISUAL_ONLY`).
- V2_3 B601_STOWED_HIFI: empty — does not exist at all (do not cite as visual either).
- URDF `meshes_b601_gripper` STLs serve as visual+collision in URDF; never rendered in sim.

## 4. What is PLACEHOLDER (physically in the model, not real)

- 3 stow saddles: hollow shells (down-facing 1200 mm² top, two 4 mm ledges) — R3-04 open; the stow pose physically rests on them (0.0011 mm), which is why C12 fails at t=0.
- Wing panels: 4 planar solids with no hinge bore, floating 30.0 mm off the hinge pins — D-F3R1-06 open.
- Harness_Passage / Service_Loop / Release_Clearance_Envelope / Launch_Lock_Interface_Reference: envelope solids, TBD intent.
- Solar panels in dynamics: 0.348 kg/panel SSOT placeholder (real areal density implies 5–10×).
- ARM HDRM/camera/harness/supports/lugs from F3R2: definitions with dimensions and mass estimates — buildable but not built.

## 5. What the (residual) F3R2 round will close when authorized + ratified

1. Human ratification of F3R2 gate + CM acceptance/backup/reference cold-reopen for the already copied F3R1/F3R2 packages. The separate 3,432-file historical lineage needs its own disposition Gate.
2. Model `WING_ROOT_LUG_LEFT/RIGHT` (closes D-F3R1-06) → then model real supports (closes R3-04, STOW_RESTRAINT hold; C12 t=0 failure disappears because the pose no longer rests on placeholders).
3. Model ARM HDRM demonstrator + camera + harness provisions (OI-2/OI-7; enables camera-visibility criteria).
4. Cut independent gripper finger components (G3-05; enables open-jaw clearance).
5. Obtain service-sequence pose authority (human) → complete official-path sweeps (C11).
6. Repair or formally waive native pair attribution (OI-1) — either fix the SW2024 API path (newer install / different API route) or ratify the offline mesh measurement as the clearance authority.
7. Repair `sim_05 b601_model.py` URDF path (one line) so the L2 chain is re-runnable against the accepted URDF.

Nothing in this list authorizes "fix everything at once": the mandated sequencing is in `F3R2_EXECUTION_ORDER.md`.
