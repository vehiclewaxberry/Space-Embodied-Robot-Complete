# sim_13_viability_extension_r1

`RESEARCH_COUPLED_CLOSURE_R1` — mechanics → capture dynamics → safe constrained control.

**Isolation method:** directory-level. No new Git branch or worktree was created because the
user worktree carries ~180 dirty entries (mostly untracked governance output); everything here
is new and untracked, and no existing file outside this directory has been modified. The
`git checkout -b` decision belongs to the Owner.

**Authority discipline**

- The accepted B601 URDF, donor CAD, and all existing sim/Sim13/SAFE/control Gates are
  **read-only**. Protected hashes are re-verified at the start of every builder.
- `b601_kinematics.B601` refuses to run if the accepted URDF hash drifts (fail-closed).
- Nothing here carries release credit. Every emitted Gate sets
  `next_stage_authorized = false` and `release_credit = false`.
- `UNKNOWN` is never `PASS`. Absent Gate components are recorded as `ABSENT`, never zero-filled.

## Layout

| Directory | Contents | Status |
|---|---|---|
| `00_authority/` | R0 parent/child authority reconciliation + builder | **PASS** |
| `00_external_inputs/` | read-only quarantine for externally supplied tables | empty (none supplied) |
| `01_mechanical_handoff/` | M1 joint/frame/sign registers, FK witnesses, discrepancy ledger | **core PASS, R1 blocked** |
| `02_sim12_factorial_reissue/` | D1 24-cell factorial, global Gate vector, Pareto, GS2 V2 | **PASS** |
| `03_reference_dynamics/` | D2 independent free-floating reference model | not started |
| `04_capture_map/` | D3 finite-contact capture transition | not started |
| `05_flex_bridge/` | M6 / D4 e23 re-binding and uncertainty | not started |
| `06_ctrl03/` | C2–C5 controller formulations | not started |
| `07_cross_validation/` | C6 reference model vs MuJoCo | not started (MuJoCo not installed) |
| `08_gates/` | integrated research Gates | not started |

## Reproduction

```bash
python 30_simulation/sim_13_viability_extension_r1/00_authority/build_r0_reconciliation.py
```

```bash
python 30_simulation/sim_13_viability_extension_r1/01_mechanical_handoff/build_m1_registers.py
```

```bash
python 30_simulation/sim_13_viability_extension_r1/02_sim12_factorial_reissue/build_d1_factorial.py
```

All three are deterministic and side-effect-free outside this directory.

## Key findings so far

1. **Sim13 dual authority is not a conflict.** Parent `15/20` (ABORT-only) and child `20/20`
   (backend negative-control subscope) have different scopes; the repository's own append-only
   addendum already records `historical_15_of_20_superseded = false`.
2. **The prismatic axis/sign "conflict" was apparent only.** The URDF encodes left/right
   asymmetry in the joint-origin `rpy` (`Rz(∓90°)`), not in the axis vector. Travel magnitude
   and sign agree to 4.8e-13 m.
3. **`joint2` axis `0 0 -1` is deliberate**, not a typo: joints 2 and 3 are antiparallel about
   the shared link2 Z line, both with one-sided limits `[-3.14, 0]`.
4. **The sim_12 factorial defect is real and fixed.** `S1/S3a/S4` shared one physical
   transition; the Gate subset changed with the mode. V2 uses one strategy-invariant Gate
   vector over all 24 cells.
5. **No cell is `ROBUST_SAFE`** — 9 `UNKNOWN`, 15 `UNSAFE`.
6. **`DISC-010`: the sim_10 frozen-input hash pins are stale after REORG04**, so sim_10 and
   sim_12 are not currently re-executable. Threshold numerics were independently verified
   unwidened. Owner decision required.
