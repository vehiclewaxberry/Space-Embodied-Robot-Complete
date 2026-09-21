# E23 — R2 full-flex coupled recertification with the Round4 seven-mode ROM

E23 reruns the E22 Checkpoint-A coupled diagnostic campaign with the Round4
V3 per-wing seven-mode ROM (BENDING_1..3 + TORSION_1..4), closing E22's failed
G11 (183-DOF HF to five-mode truncation 3.51% > 1%) and G17 (three-lane
comparison completeness) under Owner directive TMC-01 (2026-08-25 Terminal
Mechanical One-Shot Closure).

## What changed vs E22

- ROM: Round3 five-mode (immutable historical) -> Round4 seven-mode
  (`20_engineering/.../r2_full_flex_closure/round4_hf_rom_v3/`), the exact
  family the independent ROM5 falsifier proved passing (7D, 0.27%).
- Nested truncation order: [B1,T1,T2,B2,T3,T4,B3]; coupled truncation gate is
  m6->m7 <= 1%; HF-to-ROM dynamic truncation gate is seven-mode <= 1%.
- G17 redefined honestly: Rigid vs Solar-R2-flex-seven-mode numeric comparison
  at both anchors (22 kg @ 0.5 deg/s, 150 kg @ 3 deg/s); the legacy R1 flex
  lane remains co-presented as HISTORICAL_REFERENCE_ONLY with
  numeric_comparison_authorized = false and an explicit non-causal guard.
- Owner authority: TMC-01..TMC-03 transcription (round4 package); e15 legacy
  ANCF gate remains REPEAT (preserved hard negative); harness remains
  UNSAFE_INDEPENDENT_FACT.

## Run

```powershell
cd 30_simulation/e23_r2_full_flex_coupled_recert/src
python build_e23.py
cd ../tests
python independent_recompute.py
python replay_determinism.py
python -m pytest test_e23.py -q
```

## Current machine verdict

`E23_R2_FULL_FLEX_COUPLED_GATE_V1.json`: PASS_WITH_DECLARED_PROVISIONAL_PHYSICS
18/18; seven-mode HF reconstruction 0.2714% <= 1%; Radau/BDF cross 1.81e-05
<= 5%; rigid degeneration exact 0.0; all provisional EI/GJ/k/zeta declared.
review_status = PENDING_OWNER_REVIEW; next_stage_authorized = false;
release_credit = false.
