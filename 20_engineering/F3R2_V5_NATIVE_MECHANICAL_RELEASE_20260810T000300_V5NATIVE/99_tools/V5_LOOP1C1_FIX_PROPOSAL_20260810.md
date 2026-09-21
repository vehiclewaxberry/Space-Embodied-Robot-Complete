# V5 Loop1C1 — Final Report: error-5 root cause, patches, and the interference blocker

Date: 2026-08-11 (live-probe campaign on reserved session PID 87516, attach-only)
Scope honored: only `99_tools/F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py` was patched; shared modules untouched; no receipt overwritten/deleted; protected baselines read-only; session left document-empty after every run.

---

## 1. Outcome

`--execute-assembly` now passes **mate creation (4 guide coincident + 2 advanced limit distance), configuration creation, per-configuration dimension drive, per-state transform/gap/rail-clearance gates**, and fails closed at exactly one remaining gate:

```
code: ASSEMBLY_INTERFERENCE_FAIL   (run 7, receipt V5_LOOP1C1_FAIL_20260811T0314..Z)
```

**The blocker is not an assembly defect — it is donor-inherited geometry.** The current contract gate demands zero cross-component positive-volume interference; the accepted donor geometry intrinsically carries palm↔finger and finger↔finger volumetric overlaps at every kinematic state. Proceeding requires a human/contract decision (see §5).

## 2. Final root cause of LIMIT_MATE_ADD_FAIL (error 5), proven live

1. **Guide coincident alignments rotated the fingers.** Production had `L_A=0, L_B=0, R_A=0, R_B=1`. On this SW2024 SP5 install, a coincident mate between the already-coincident parallel guide planes with alignment 0 flips the component to the 180°-rotated solution branch (probe v2: LEFT→rotY180, RIGHT→rotZ180 after guides).
2. rotZ180 flips the RIGHT limit face's true normal +Y→−Y, making it parallel to the palm's −Y face. The authored R limit mate `alignment=1` (correct for the design pose, where the normals are anti-parallel) then contradicts the rotations locked by the guides → `swAddMateError_OverDefinedAssembly (5)`. LEFT escaped because rotY180 keeps +Y normals. The earlier rounding patch (unrounded `LIMIT_MAX_MM`) fixed a real 2.0e-8 m latent defect but was not the cause.
3. Probe matrix (v2): in the rotated state, EVERY R variant fails (plain/limit, wide/strict range, flip, swapped selection) except align=0, which then yanks the finger off-design. Note: error 5 still leaves a created mate feature behind.
4. **Working recipe (probe v4/v5, all confirmed live):** all four guides at alignment 1 → both fingers keep identity rotation at ty=±71.5 mm; R limit = palm-first, align=1, flip=True; L limit = finger-first (swapped selection), align=0, flip=False; both created as PLAIN distance (upper=lower=0) and converted in place via `IDistanceMateFeatureData.ModifyDefinition` (IsAdvancedMate, min=0, max=base+71.5) — a direct limit create at the range boundary is rejected, and a negative Distance at create returns ErrorUnknown(0).
5. Per-config drive: only `SetSystemValue3(v, 3, VARIANT(VT_ARRAY|VT_BSTR,[name]))` actually stores per-config values here (probe v6); `swThisConfiguration` and plain-list variants silently no-op with status 0. Mate feature handles must be re-fetched AFTER `AddConfiguration2` — stale handles crossed OPEN↔HOLDING slots (probe v8). `GetSystemValue2(name)` readbacks lag one write on fresh handles → the production readback gate runs once over the full 8-cell table after a rebuild (probe v7 table + activation geometry all exact: OPEN/PREGRASP/CLOSED/HOLDING → ty ∓71.5/∓55/0/0).
6. `IMateEntity2.Reference` raises DISP_E_MEMBERNOTFOUND via the makepy static binding; late-bound dynamic dispatch returns the face (micro-probe, accessor A2, valid 807-byte persist refs).
7. Stale component handles after configuration switches read `Transform2` as zeros → `verify_state` re-resolves components per state.

## 3. Production patch inventory (Loop1C1 script only)

- `GUIDE_CONTRACTS`: all four guide alignments → `SW_ALIGN_ANTI (1)`.
- `LIMIT_CONTRACTS`: added per-side `flip`/`swap` (L: swap=True, flip=False, align=0; R: swap=False, flip=True, align=1).
- `add_advanced_limit_distance`: per-side selection order + flip; plain create; existing ModifyDefinition conversion retained; all fail-closed gates unchanged.
- `LIMIT_MAX_MM`: exact `base + 71.5` expressions (first patch, retained).
- `establish_configurations`: fresh feature re-resolution after config creation; typed-BSTR named sets; deferred full-table readback gate; per-side law `base + t` for BOTH sides (was `base − t` for L — measured wrong).
- `configuration_distance_values`: same law fix; readback via `GetSystemValue2(configuration)`.
- `verify_state`: re-resolve the 3 components after each configuration activation (stale handles read zeros).
- `mate_ledger`: mate-entity face reference via dynamic dispatch (A2).
- Comments updated to the measured laws and the true error-5 mechanism.

Verification of every stage by live probes (logs in `99_tools/probe_logs/`): R_LIMIT_MATRIX v2, ALIGN_SIGN v3/v4, DRIVE v5, CONFIG_DRIVE v6/v6b, TRUTH_TABLE v7/v8, MATE_ENTITY_REF, INTERFERENCE v9, DONOR_INHERITANCE v10, INTERFERENCE_BODIES v11.

## 4. The interference blocker — evidence

`verify_state` → `interference_fact` (TreatCoincidenceAsInterference=False, multibody internal included) fails on real volumetric overlaps (run-7 receipt + probe v9 per-state table):

| state | rows | total mm³ | max single mm³ |
|---|---|---|---|
| OPEN | 28 | 1267.42 | 435.91 (rail interface @ guide plane x≈−74.06, palm +Y end region) |
| PREGRASP | 16 | 780.11 | 259.38 |
| CLOSED | 39 | 350.20 | 79.53 (jaw contact shell, ~0.03 mm thick over the jaw face) |
| HOLDING | 39 | 350.20 | 79.53 |

**Donor-inheritance proof (probe v10):** the donor source part `B51_REF_gripper_detail_LINKLOCAL.SLDPRT` (57 bodies, LINK6_LOCAL, static arrangement = CLOSED state) contains **81 internal positive-volume interferences**, including:
- max row **79.527907 mm³** — bit-identical volume to the V5 CLOSED finger↔finger jaw shell;
- **16 rows of exactly 12.055338 mm³** — bit-identical volumes to the V5 CLOSED palm↔finger rows.

**Drive-sign hypothesis (W1) — tested and REFUTED (probes v9/v10/v11):**
- Overlaps occur at EVERY state, including CLOSED (travel 0, no drive influence): 39 rows / 350.20 mm³.
- The donor part — no mates, no drive at all — contains the identical CLOSED overlap set (volumes match to 6 decimals).
- At OPEN the measured jaw gap is exactly the authority 82.2284 mm and the opposed-transform gate passes, so the fingers are at the authority-correct pose; a wrong drive direction would move the jaw gap off authority.
- Body-level identification (v11): the dominant OPEN overlap (435.91 mm³) is `PALM_SOLID_09__...LINKLOCAL054` (palm detail body carrying the guide/limit faces) against the finger rail solids (`RIGHT_FINGER_SOLID_01__...LINKLOCAL`, `..._06__...016`, mirrored LEFT bodies); the CLOSED 12.055338 mm³ rows are `PALM_SOLID_09 (054)` / `PALM_SOLID_07 (050)` / `PALM_SOLID_08 (051)` against finger solids 016/028/033/043/044/046 etc.

Identical volumes at 6 decimals prove the Loop1C0 body copy was faithful and the overlaps pre-exist in the accepted donor geometry. The travel-dependent growth (12→259→435 mm³ as CLOSED→OPEN) is the same rail interface geometry articulated; the donor CAD was only ever mesh-checked (0.25 mm tessellation, minimum-distance witnesses) and never natively interference-checked (closure docs: `05_clearance/F3R2_NATIVE_INTERFERENCE_OUTCOME.json` records that native probing failed on this machine at the time).

**Consequence:** the zero-cross-component-interference gate is unsatisfiable with the accepted donor parts at authority-correct poses (jaw gap 82.2284/50.5026/0.0 and travel gates all pass). No assembly-side choice (mates, alignment, drive) can remove overlaps that live inside the parts.

## 5. Decision required (human/contract level — F3 NOT executed)

- **Option A (recommended): contract amendment.** Accept the donor-inherited contact-interface overlaps as documented design contact interfaces, evidenced by the v9/v10 tables (exact volumes/bboxes), while keeping the gate's teeth for *new* collisions: e.g., gate on "cross-component interference set equals the documented donor-inherited table" (frozen volume/bbox fingerprints per state). This changes the recorded contract — needs human sign-off.
- **Option B: part rework.** Trim the overlapping interface solids in the three native parts (new Loop1C0′), then re-derive guide/limit face contracts. Cascades: new part hashes → new Loop1C1 inputs; travel-clearance authority re-measurement. Heavy.
- **Option C: accept overlaps as-is into the release narrative** without a gate — NOT recommended (unbounded claim).

## 6. Rerun once decided

```bat
cd /d "F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
G:\Windows_program_file\Anaconda\python.exe 99_tools\F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py --execute-assembly
```

State is PENDING (no target/checkpoint exists), static audit authorizes execution. After the interference gate, the untested remainder is: `save_assembly` → `cold_verify` (read-only cold reopen, per-state re-verify, B-rep bbox, reference audit) → checkpoint + final receipt (`V5_LOOP1C1_NATIVE_GRIPPER_ASSEMBLY_PASS_MECHANICAL_MAINLINE_FREEZE_READY`).

## 7. Artifacts

- Patched script: `99_tools/F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY.py` (py_compile clean; static audit `V5_LOOP1C1_STATIC_AUDIT_PASS_EXECUTION_AUTHORIZED`).
- Probes (attach-only, self-cleaning): `99_tools/V5_PROBE_LOOP1C1_{R_LIMIT_MATRIX,ALIGN_SIGN,DRIVE,CONFIG_DRIVE,TRUTH_TABLE,INTERFERENCE,DONOR_INHERITANCE}.py`, `V5_PROBE_MATE_ENTITY_REF.py`, `V5_SESSION_STATUS_CLEANUP.py`.
- Logs: `99_tools/probe_logs/*.log`.
- Fail receipts (write-once, newest last): `…T232652` (R limit error 5), `…T013206`/`…T014649` (config drive), `…T022149`/`…T024640` (transform contract), `…T032928` (Reference member), `…T0314*`/run-7 (interference).
