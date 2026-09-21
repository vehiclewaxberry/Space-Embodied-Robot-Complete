# F3R2_EXECUTION_ORDER.md

## 0. Post-M3R sequence correction

The M3R audit supersedes the old G30/G31 `8 x M3 flange` conclusion: there are
four HM4-75/M4-class axes and no continuous active flange/base plate. Before
any successor V4 integrates the remaining G3 hardware, close the corrected
adapter chain in this order: native ring/body/assembly creation -> B601 and
load-bridge fit-up -> validate the Rev B unique dowel fit/tolerance -> native cold reopen and
interference -> fastener/load review. The AS-BUILT competition interface itself
is authorized, so non-native definition and analysis work may continue; G8
freeze may not.

**PL1-B re-derivation from primary sources, 2026-08-08.** Sources (all read directly): W3-F plan (`…\07_STAGING\AGENT_W3F\W3_F_F3R1_REMEDIATION_PLAN.md`), F3R1 G2 package (`…\F3R1…\04_configurations\G2\F3R1_G3_INTERFACE_CLOSURE_RECOMMENDATION.md`, `F3R1_G2_GATE_STATUS.json`, `12_human_review\F3R1_MECHANICAL_REVIEW_02_20260806.md`), F3R2 gate set (`…\F3R2…\13_gate\F3R2_FINAL_GATE.json`, `15_change_control\*`, `03_native_cad\F3R2_REFERENCE_AUDIT.json`), CM records (WAVE3 acceptance, W4 root map, CM2/CM3 executive summaries), current entry doc (`PROJECT_START_HERE.md` §12).

## 1. Why the order exists at all

WAVE3/G9B accepted F3R1 **assets** and quarantined 3 **engineering defects** into a separate human-authorized task so file governance could close without touching CAD: D1 top-level Mate=0, D2 configurations undifferentiated, D3 saddle placeholder shells. W4 root map declares the W3-F order "顺序不可颠倒" (order not reorderable). F3R1's own G3 recommendation adds the binding geometric reason: all 4 wing panels float 30.0 mm off the hinge pins, so **saddle counterfaces cannot be searched until the wing-root constraint is physical** — WING_ROOT_LUG strictly before saddles.

## 2. Mandated order (what the sources prescribe)

| Seq | Priority | Work item | Source | Depends on |
|---|---|---|---|---|
| 1 | **P0** | Configuration differentiation rollup (G4A): V4 top, 8 configs, one live wing/side; PARTIAL only after human angle approval | W3-F §2 | human PARTIAL-angle ruling |
| 2 | **P0** | Top-mate restoration (G4B): V4 reuses G2's verified 6-mate pattern, 0 mate errors | W3-F §2 | none |
| 3 | **P1** | G3-01 WING_ROOT_LUG_LEFT/RIGHT (r=4.200 bore coaxial with Hinge_Pin r=4.000, axial retention vs Hard_Stop) | F3R1 G3 rec §0/§1 | P0 stable V4 |
| 4 | **P1** | G3-02 real G07/G08/Mid saddles via native nearest-face search; replaceable pads (G07 PTFE+disc-spring 10 N/mm; G08 VMQ60A 5 N/mm); Mid stays 2.00 mm backup | F3R1 G3 rec; P5B specs | G3-01 strictly |
| 5 | **P1** | G3-03 ARM HDRM (never conflate with solar HDRM); 5-state release machine | F3R1 G3 rec | G3-02 |
| 6 | **P2** | G3-04 camera + harness (FOV 60/90/120°, optical frames, min bend radius, release-path clearance; no floating cameras) | F3R1 G3 rec | G3-02 |
| 7 | **P2** | G3-05 gripper two independent finger solids (URDF prismatic, no mimic) | F3R1 G3 rec | none geometric, schedule after P0 |
| 8 | **P2** | Continuous clearance: native interference + IFace2/Measure min-distance over the O13 stow band (≥ +3 mm pad stack), replacing bbox scoring | F3R1 review #2 §5 | G3-01/02 |
| 9 | standing | Native reference integrity: baseline must not carry unresolved external refs; PROTECTED_CHECK PRE/POST every round; never overwrite G0/G1/G2 — build V4 | W3-F §3; F3R1 00_authority | always |

Hard rules from all sources: one round = one authorization; human gates for PARTIAL angle, q_stow promotion, any flight/manufacturing claim; session discipline (kill SLDWORKS.exe, 0 processes, ~22 s) before every write.

## 3. What F3R2 actually executed (2026-08-07, gate 11/14)

Executed sequence: R2A2 reference audit → G3A interference (offline mesh self-checked; 4 native attempts failed then 1 native run succeeded without attribution) → G3B pose search (5,625-point grid) + freeze 5 poses → G3C wing-root **definition** → G3D supports **definition** → G4 HDRM + camera **definitions** → G5 path sweeps → G6 digital thread → 12 witness shots → final gate; evening extensions G30 (T_SM stack freeze) / G31 (base interface ring) / G32 (supports V2) / G33 (gripper 58 solids).

- **Closed:** deployed operational baseline; pose authority for 3 runtime poses; T_SM pseudo-conflict (185.25/198/208 = frame/faces stack); the old D-F3R1-05 interpretation is superseded by the M3R four-axis measurement (not an `8 x M3` flange); digital thread emitted; protected assets unchanged.
- **NOT executed as mandated:** no V4; no mate restoration *write* (V3 already carried 6 mates/0 errors from G1 — the P0 write items were overtaken by F3R1's own G1/G2); all interface hardware left DEFINED_NOT_MODELLED.
- **Verdict:** `F3R2_DEPLOYED_OPERATIONAL_BASELINE_CLOSED` + `F4_DEPLOYED_CONTROL_AND_EMBODIED_GO` + 4 HOLDs; C11/C12/C14 fail; `PENDING_HUMAN_REVIEW`; `next_stage_authorized=true` is read as machine-gated F4 continuation, not blanket authorization to write V4 CAD.

## 4. Residual execution order (the work that remains, re-prioritized)

**P0 — unblock the baseline itself (nothing mechanical may start before these):**
1. **Human review & ruling on F3R2** (`13_gate\F3R2_FINAL_GATE.json` + `12_human_review\F3R2_HUMAN_REVIEW_BOOK.html`). Without ratification every downstream number is candidate-grade.
2. **CM acceptance/backup/reference preflight for the completed salvage**: F3R1 363/363 and F3R2 482/482 are already in REPO with source=destination SHA manifests. Remaining work is tracking policy, cold backup, CM acceptance, pointer closure and reference cold-reopen; retain WT source until acceptance. The 3,432-file historical CAD lineage is a separate Gate.
3. **WING_ROOT_LUG modelling (G3-01)** — first CAD cut; everything mechanical queues behind the physical hinge constraint. Closes D-F3R1-06.

**P1 — close the stow/restraint chain:**
4. **Real G07/G08/Mid supports (G3-02)** per G32 definition (heads 54×54/34×34/34×34.4; P5B pad specs) → placeholder shells leave the assembly; the C12 t=0 failure mode (0.0011 mm rest on placeholders) disappears structurally.
5. **Continuous clearance over the stow band** re-run on real supports (min-distance, not bbox) → promotes q_stow candidate toward qualification review (still needs human promotion).
6. **ARM HDRM device selection + modelling (G3-03)**; release-sequence authorization is a separate human gate — do not couple.

**P2 — complete the operational envelope:**
7. **Camera + harness modelling (G3-04)** → unlocks all `NOT_EVALUATED_NO_CAMERA` criteria.
8. **Gripper two-finger components (G3-05)** → open-jaw clearance; G33 measurements are the starting geometry.
9. **Service-sequence pose authority** (human-authorized q for SERVICE_DOCKING/GRASP/TRANSPORT/ASSEMBLY/RETRIEVED_NOMINAL) → then complete official-path sweeps (C11). Inventing vectors is evidence fabrication — stays blocked until a human rules.
10. **Native pair attribution repair or formal waiver** (OI-1): fix on a SolidWorks install with a working IInterference API, or ratify the offline mesh measurement as clearance authority of record.
11. **Native reference integrity repair** (R2A2 `REPAIR_REQUIRED`; 3 external refs in stowed config / 10 registered at gate): after ROOT A CM acceptance/reference-repair authorization, re-point or internalize references and verify by cold-reopen 0-leak. Pack-and-Go proof currently ends `R2A_FAIL` because OpenDoc6 RPC failed.
12. **sim_05 `b601_model.py` URDF path repair** (one line, repo-relative `20_engineering/cad/…`) so the L2 chain is re-executable; then re-run sim_05/e16 hash checks.

**Explicitly never:** "fix everything at once" — every source (W3-F, G3 rec, W4 root map, F3R2 change control's 6-level ladder of which only level 3 was used) mandates single-scope authorized rounds with PRE/POST protected checks.

## 5. Coverage check vs mandated topics

| Mandated topic | Where it stands | Covered by step |
|---|---|---|
| Mate=0 | Closed inside F3R1 (G1, 6 mates/0 err); F3R2 inherited | done — verify on post-salvage CM acceptance/cold reopen (step 2/11) |
| Configuration set | G2 gate 15/15 with 8 configs present; PARTIAL is not differentiated and SERVICE lacks angle authority | step 9 (SERVICE), human ruling (PARTIAL) |
| Cradle placeholder (R3-04) | Defined, not modelled | step 4 |
| WING_Root_Lug | Defined, not modelled; gap physically open | step 3 |
| HDRM | Solar = donor parts; ARM = demonstrator definition | step 6 |
| Continuous clearance | G5 partial (1/6 official swept); t=0 placeholder artifact | steps 4→5→9 |
| Harness | Envelopes + ICD rules only | step 7 |
| Native reference integrity | R2A2 REPAIR_REQUIRED; tolerated at gate (10 refs) | steps 2→11 |
