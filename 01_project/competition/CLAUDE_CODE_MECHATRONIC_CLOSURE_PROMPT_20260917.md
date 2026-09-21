# Claude Code Prompt — WP10 Mechatronic Closure: Mechanical + Electrical + Thermal + Propulsion Completion

Generated 2026-09-17 by Kimi Work agent from verified workspace evidence. Paste everything below the line into Claude Code.

---

You are continuing an interrupted full-system engineering closure inside an existing aerospace workspace: a 12U CubeSat servicer spacecraft with a B601 6-DOF robotic arm for non-cooperative target capture. Your job: drive the WP10 mechatronic closure from its verified current state toward a same-version, evidence-backed complete design — covering electrical/PCB, thermal, mechanical assembly, and propulsion/ADCS interfaces.

## 0. Read-first order (mandatory, before any write)

Workspace root: `F:/China Graduate Future Flight Vehicle Innovation Competition`

1. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/PROGRESS_PLAN_V35_V36.md` — the 6-work-package closure plan with per-package deliverables and exit conditions. This is your master plan.
2. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/results/DELIVERY_DECISION.json` and `SYSTEM_CLOSURE_MATRIX.csv` — the machine ruling: `VERIFIED_ENGINEERING_DELTAS_AND_RESEARCH_INPUTS__FULL_SYSTEM_DELIVERY_NOT_READY`, 23 of 37 packages open (19 INTERNAL_DESIGN_OPEN + 4 EXTERNAL_INTERFACE_UNBOUND), 13 COMPLETE_SCOPED_SUBITEM.
3. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/HANDOFF_DELTA_20260916_ROUTING_PENDING.md` — the V36 STOP-board breakpoint (PCB work package details).
4. `01_project/competition/CLAUDE_CODE_PCB_CONTINUATION_PROMPT_20260917.md` — companion prompt covering the PCB-specific resume steps; treat its board-level instructions as binding for Work Package 1.

Path convention: `A/` = `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation`.

## 1. Verified current state (do not re-derive; verify against evidence files)

- Formal revision: **V35** (15-page schematic, 237 refs/767 pins, ERC clean; main input PCB 43 footprints; aux protection/sequence PCB 26 footprints, 60×70×1.6 mm). Machine flags: `whole_design_complete=false`, `manufacturing_release=false`, `power_on_release=false`, `hardware_tests=0`.
- Working revision: **V36** (249 refs/795 pins, ERC 0/0) — STOP board placed (103 footprints + 4 holes), first autoroute `STOP_ROUTED_A.ses` saved but NOT imported, 254 unconnected items. See companion PCB prompt.
- Mechanical: 873-instance native SolidWorks 3-state host exists (WP09D). V30 partial deltas (56 sub-parts / 60 solids) verified but NOT reinstalled into the host. Mates, continuous-motion proof, true launch-stowed configuration, materials, per-component mass/COM/inertia NOT unified. "Parking" configuration must never be called launch-stowed.
- Thermal: CHB board-temperature scenario 105.837–107.214 °C EXCEEDS the 105 °C limit; three candidate mounting positions carry 8/7/7 overlaps respectively; V33 thickened-structure candidate was REJECTED (preserved negative). Physical layout + thermal path redesign is mandatory — parameter tweaks are not acceptable.
- Propulsion/ADCS: commercial module candidates and catalog-impulse screening exist only. Per-revision nozzle positions/orientations, concurrency, minimum impulse bit, peak power, plume keep-out ICD are UNBOUND. Catalog total impulse and synthesized arrays must never be reported as vehicle capability. Current true 6-DOF mission capability = UNKNOWN.
- Energy: 360 W arm screening requirement stands; battery minimum loaded voltage and solar-array recharge not closed; full-cycle energy budget open.
- Known unresolved reference: DM公开 URDF mass ≈2.74448 kg vs a 4.5 kg citation — must be explained, not averaged.

## 2. Scope of work (execute in this order)

### WP-1 STOP / regeneration / fault-shutdown chain (electrical, PCB)
Resume per the companion PCB prompt: import `STOP_ROUTED_A.ses`, full post-route DRC (count violations AND unconnected), engineering review (decoupling, 120 pF timing node, thermal-monitor RC, gate/coil return, grounding, power-device thermal), fresh plots, receipts. Then: load-side regenerative energy absorption path; per-item bounds for undervoltage, short power-loss, stuck key, wire break, over-temperature, contactor release, manual re-arm, restart. Deliverables: same-source schematic/PCB/BOM, pin tables, fault matrix, timing and energy budgets. Exit: every link detect → drive-inhibit → gate voltage → coil → contacts → mechanical stop/recovery has an applicable bound; unverified physics stays UNKNOWN.

### WP-2 Whole-craft electrical selection and complete energy path
Separate real purchasable parts / mature modules / logic ports. Add connectors, terminals, wire gauges, protection coordination, charging and heating. Honor the 360 W arm screening; verify battery minimum loaded voltage and array recharge. Deliverables: traceable selection BOM (model/qty/footprint/rating/source/substitution limits per line), power tree, peak/continuous currents, per-pin current limits, charge/discharge cycles, mission energy budget. Exit: startup, run, stop, charge all inside one power boundary.

### WP-3 Thermal structure and in-bus re-layout (thermal)
Model the 23 unmodeled main-input refs; include the 60×70×1.6 mm aux board and 18 mm nominal component height. Physically design the CHB → TIM compression → load-bearing member → fixed radiator path, battery thermal isolation, and tool access. Resolve the >105 °C CHB exceedance and the 8/7/7 candidate-position overlaps by actual geometry change. Deliverables: modified-part CAD, hole/fastener/TIM definitions, equipment envelopes, harness terminations, complete thermal network. Exit: all declared heat sources included and within limits; accepted positions free of disallowed interference; maintenance/harness clearances met.

### WP-4 Native assembly, configuration, materials, mass properties (mechanical)
Reinstall accepted deltas into the 873-component host one by one; establish joints/mates and true working + stowed configurations; resolve the 2.74448 kg vs 4.5 kg DM arm mass discrepancy; assign per-component physical properties and write back the parameter cards. Deliverables: cold-reopenable SLDASM/STEP, assembly BOM, configuration table, mass/COM/inertia tables, continuous-motion and harness checks. Exit: native assembly consistent with source plan; unknown properties never filled with water-density or zero; launch-stowed proven separately.

### WP-5 Propulsion/ADCS real interfaces and mission budget
Bind the same-revision ICD (nozzle positions/orientations, concurrency, minimum impulse, peak power, plume). Build the allocator from real nozzles and current COM; verify single-thruster direction, concurrency, minimum impulse, plume keep-out, total impulse, peak power, time windows. If the controlled ICD is unavailable, register EXTERNAL HOLD and stop that branch — do not invent values. Deliverables: controlled-ICD mapping, mounting interfaces, recomputable allocator, mission resource report.

### WP-6 Same-version digital-prototype acceptance
Aggregate CAD/ECAD/harness/BOM/mass/thermal/propulsion at one version; reopen and recompute in a clean environment. Deliverables: complete digital prototype, version hashes, per-item acceptance evidence, accurate external pending-verification list. Exit: necessary internal items all have same-version evidence; design delivery, manufacturing release, power-on, and flight suitability are ruled SEPARATELY (owner-level gates — you do not pass them).

## 3. External dependencies (register as EXTERNAL HOLD; never fabricate)

P60/BPX release-device pinout; CIC forming interface; propulsion controlled ICD (C-POD same-revision); DM (B601) actual joint configuration; gripper closure-time measurement; as-built mass/COM/inertia metrology; contact calibration CT01-CT05. Document exactly what is needed, from whom, and which package it blocks.

## 4. Hard rules (violating any = task failure)

- Fail-closed: UNKNOWN never becomes PASS; null never zero-filled; a test PASS is not a design Gate PASS; hash mismatch aborts consumption. Never overwrite a FAIL record — append new evidence.
- Every verdict/evidence JSON gets a same-version SHA256 companion. Update `SYSTEM_CLOSURE_MATRIX.csv` row states only with linked evidence.
- Native KiCad/SolidWorks/COM/OCC operations run SERIALLY through the memory guard: start with ≥2048 MiB free, abort below 512 MiB, job-tree RSS cap 1400 MiB. KiCad native python: `G:/Windows_program_file/Kicad/bin/python.exe`; guard: `A/tools/native_delta_guard.py` with a unique run name.
- Do NOT rerun completed writer scripts that would overwrite restore points (see PCB prompt §3 for the list).
- Git: workspace fully version-controlled (branch `docs/fix-third-party-notices-link`, checkpoint `4c8a61e1`). Commit in logical chunks with `git -c core.protectNTFS=false add …`; large CAD binaries are on Git LFS.
- You do NOT declare `whole_design_complete`, manufacturing release, power-on release, or flight qualification. You may only propose evidence-backed state transitions for owner review.

## 5. Definition of done for this engagement

- WP-1 through WP-5 each either meet their exit conditions with same-version evidence, or carry an explicit written blocker (internal remainder or EXTERNAL HOLD with exact missing input).
- Updated `SYSTEM_CLOSURE_MATRIX.csv` + refreshed `DELIVERY_DECISION.json` reflecting only evidenced transitions.
- Git commits per work package with receipts.
- Final English status report: per-package what was done / what failed / what remains UNKNOWN, with absolute file paths of every artifact created or modified.
