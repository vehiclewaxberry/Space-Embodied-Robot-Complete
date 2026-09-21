# Claude Code Prompt — WP10 PCB Design Continuation (STOP board routing import → complete PCB closure)

Generated 2026-09-17 by Kimi Work agent from verified workspace evidence. Paste everything below the line into Claude Code.

---

You are continuing an interrupted KiCad PCB design task inside an existing aerospace engineering workspace. All prior state is real, hash-checked, and must be preserved. Your job: resume exactly at the registered breakpoint, finish the STOP control board routing, then drive the remaining PCB work packages to a verifiable, same-version closure.

## 0. Workspace and read-first order

Workspace root: `F:/China Graduate Future Flight Vehicle Innovation Competition`

Read these files IN THIS ORDER before touching anything:

1. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/HANDOFF_DELTA_20260916_ROUTING_PENDING.md` — the authoritative breakpoint document (2026-09-16 08:28). Its instructions override anything below where they conflict.
2. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/HANDOFF_LATEST.json` — hash snapshot to verify before any write.
3. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/HANDOFF_TO_CLAUDE_CODE_20260916.md` — older handoff (system goals, resources, tooling); partially superseded by (1).
4. `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation/coupled_closure/PROGRESS_PLAN_V35_V36.md` — the full 6-work-package closure plan.

Path convention: below, `A/` = `01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation`.

## 1. Verified current state (do not re-derive; verify against HANDOFF_LATEST.json)

- Formal released revision: **V35** (15-page schematic, 237 refs / 767 pins, ERC clean with 4 inherited ignore classes; main input PCB 43 electrical footprints; auxiliary protection/sequence PCB 26 footprints + 6 mounting holes, 60×70×1.6 mm). `whole_design_complete=false`, `manufacturing_release=false`, `power_on_release=false`, `hardware_tests=0`.
- Working revision: **V36** — NOT yet promoted. Schematic: 249 refs / 795 pins, 15-page ERC 0 errors / 0 warnings; adds the STOP output stage (UCC27517 + SN74LV1T04, RAW independent enable, default-inhibit resistor, U102 independent bias) and 9 thermal-filter parts (R350–352 = CRCW06031K00FKEA 1k; C314–319 = C0603C102F5GACTU 1nF).
- **STOP board** `A/ecad/revisions/v36/wp10_stop_control.kicad_pcb`: 90×70×1.6 mm, 2-layer, 103 electrical footprints + 4 mounting holes. Placement and silkscreen DONE. Placement DRC (`A/results/stop_v36/pcb/layout_20260916/PLACEMENT_DRC_R2.json`): 0 violations, **254 unconnected items**. Board currently has 0 track segments and 0 vias.
- **First autoroute finished but not imported**: `A/results/stop_v36/pcb/layout_20260916/STOP_ROUTED_A.ses` (router exited normally, 34.45 s). SES import, post-route DRC, and net-consistency verification have NOT been executed. Pre-import board SHA256 must be `e9828defa2742e5db157eca9149640a345d81516540736eedc57fae13371ad7c`.
- Stale artifacts that must NOT be used as build inputs: `A/ecad/revisions/v36/wp10_system.xml` (older 239/771), `A/results/stop_v36/pcb/native_checkpoint_20260916/` (240/777 checkpoint), `A/coupled_closure/PROGRESS_PLAN_V35_V36.html`.

## 2. Immediate task (breakpoint resume): import routing and verify

Execute steps 1–6 of the handoff delta document, verbatim in intent:

1. Read `HANDOFF_LATEST.json`; verify source/PCB/project-rules/DSN/SES hashes. Confirm no other writer and no unsaved KiCad state. You are the ONLY writer; at most one read-only reviewer.
2. Back up the existing STOP board. Verify pre-import board SHA256 = `e9828def…ad7c`.
3. Import with native KiCad Python: `pcbnew.ImportSpecctraSES(board, ses_path)` against `A/results/stop_v36/pcb/layout_20260916/STOP_ROUTED_A.ses`. Do NOT rebuild the board — placement/silkscreen are final. Save, cold-reload, then verify: 103 electrical footprints + 4 holes unchanged in position, per-pad nets unchanged, board outline and layer count unchanged. Record the API return value and save a receipt JSON. (For via diameter queries use `GetWidth(pcbnew.F_Cu)`.)
4. Run a FULL DRC in a new evidence directory, counting BOTH `violations` and `unconnected_items`. The autorouter's exit 0 is not proof. Fix all residual unconnected nets, shorts, and clearance errors that are real (the 5 declared ignore rules — `missing_courtyard`, `track_not_centered_on_via`, `tuning_profile_track_geometries`, `footprint_filters_mismatch`, `footprint_type_mismatch` — stay declared; do not widen ignores silently).
5. Engineering review of the routed result: decoupling placement, the 120 pF timing node, precision thermal-monitor RC nodes, gate-drive and coil return paths, ground strategy, power-device copper/thermal relief. Document findings; do not claim what you did not check.
6. Re-export board plots (SVG/PNG) and actually look at them. The existing `STOP_PLACEMENT.svg` predates silkscreen fixes and must not be presented as final.

Only after native checks AND engineering review: update `A/ecad/revisions/v36/WORKING_REVISION.json` and same-version evidence; then evaluate whether V36 may be promoted to formal. A successful autoroute alone never promotes anything.

## 3. Execution environment and hard rules

- KiCad native Python: `G:/Windows_program_file/Kicad/bin/python.exe`. Anaconda Python: `G:/Windows_program_file/Anaconda/python.exe`.
- Run all native writes through the memory guard (do not reuse old log names):

```powershell
$wp10Impl = 'F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp10_mechatronic_closure_20260908/implementation'
Set-Location -LiteralPath $wp10Impl
& 'G:/Windows_program_file/Anaconda/python.exe' -B -X utf8 tools/native_delta_guard.py <unique_run_name> -- 'G:/Windows_program_file/Kicad/bin/python.exe' tools/<your_script>.py
```

Memory floor: start with ≥2048 MiB free; abort below 512 MiB; job-tree RSS cap 1400 MiB. Native CAD/KiCad/COM/OCC/Java operations run strictly SERIALLY.
- DO NOT rerun these completed writer scripts (they would overwrite restore points): `prepare_stop_filter_v36.py`, `finish_stop_filter_v36.py`, `build_stop_board_v36.py`, `place_stop_silkscreen_v36.py`. The 9-part export script is `export_stop_filter_v36.py`. Do not use 240-ref-era differential contracts against the 249-ref source.
- Fail-closed evidence discipline: UNKNOWN never becomes PASS; never zero-fill nulls; never overwrite a FAIL record with a later PASS — keep both. Every verdict JSON you touch gets a same-version SHA256 companion.
- Git: the workspace is now fully version-controlled (branch `docs/fix-third-party-notices-link`, checkpoint commit `4c8a61e1`). Commit your work in logical chunks with `git -c core.protectNTFS=false add …` (one evidence file legally uses the reserved name `aux.dsn`). Large CAD binaries are on Git LFS.

## 4. Remaining PCB scope after the STOP board (the "complete PCB design" goal)

Per `PROGRESS_PLAN_V35_V36.md` work packages 1–2, in order:

1. **STOP / regeneration / fault shutdown chain**: load-side regenerative energy absorption path; per-item analysis of undervoltage, short power-loss, stuck key, wire break, over-temperature, contactor release, manual re-arm, restart. Deliverables: same-source schematic/PCB/BOM, pin tables, fault matrix, timing and energy budgets, counterexample checks. Exit condition: every link of detect → drive-inhibit → gate voltage → coil → contacts → mechanical stop/recovery has an applicable bound; unverified physics stays UNKNOWN.
2. **Whole-craft electrical selection and complete energy path**: real purchasable parts vs mature modules vs logic ports separated; connectors, terminals, wire gauges, protection coordination, charging and heating; keep the 360 W arm screening requirement; check battery minimum loaded voltage and array recharge. Deliverables: traceable selection BOM, power tree, peak/continuous currents, per-pin current limits, charge/discharge cycles, mission energy budget. Exit condition: every real procurement line has model/qty/footprint/rating/source/substitution limits; startup, run, stop, charge within one power boundary.
3. Keep interface honesty: C-POD thruster ICD, DM arm stop/regeneration characteristics, and contactor waveforms are external dependencies — register them as EXTERNAL holds, do not invent values.

## 5. Definition of done for this engagement

- STOP board: SES imported, full DRC report with 0 real violations AND 0 unconnected items (or an explicit, justified residual list), engineering review notes, fresh board plots, receipt JSONs with hashes — all committed.
- V36 promotion evaluated against evidence and either promoted with updated `WORKING_REVISION.json`/`CURRENT_WORKING_CANDIDATE.json`, or left as working copy with a written reason.
- A short English status report at the end: what was done, what failed, what remains UNKNOWN, exact file paths of every artifact created or modified.
- You do NOT declare `whole_design_complete`, manufacturing release, or power-on release. Those are owner-level gates and remain false.
