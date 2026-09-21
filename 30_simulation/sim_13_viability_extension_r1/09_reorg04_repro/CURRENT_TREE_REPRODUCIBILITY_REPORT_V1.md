# CURRENT-TREE REPRODUCIBILITY REPORT V1

`RESEARCH_COUPLED_CLOSURE_R1 / SEI-RC-04 lane A` — 2026-08-30. `review_status = PENDING_OWNER_REVIEW`. The active worktree was not modified.

## 1. Four-layer separation

| Layer | State |
|---|---|
| Runtime path | REPAIRED (2 constants, isolated worktree only) |
| Software reproducibility | as-found 2 of 4 modules; all 4 after migration rebind |
| Scientific verdicts | **UNCHANGED** |
| New research closure | separate program (R1..R7) |

## 2. As-found vs after migration rebind

| Capsule | Expected | As found | After rebind | Root cause |
|---|---|---|---|---|
| `sim_05` | 22 | 22/22 | 22/22 | NONE__PATH_REPAIR_SUFFICIENT |
| `sim_11` | 27 | 27/27 | 27/27 | NONE__PATH_REPAIR_SUFFICIENT |
| `ctrl_01` | 22 | 21/22 | 22/22 | REORG04_MIGRATION_HASH_DRIFT_ONLY |
| `ctrl_02` | 24 | 12/24 | 24/24 | REORG04_MIGRATION_HASH_DRIFT_ONLY |

The **after rebind** column is a conditional root-cause demonstration performed in a disposable worktree. It is not a proposed edit to the active tree and carries no authority.

## 3. Corrected root-cause ruling

The incoming diagnosis treated CTRL-01 as a CRLF/raw-hash problem separate from CTRL-02's frozen-hash drift. **They are one root cause.**

`control_01_run_summary.json` records `config_sha256 = bfacf8d1…` and `matrix_sha256 = 278dc59f…`. Those are exactly the **pre-REORG04 normalized-LF** hashes of `control_01_v0.yaml` and `experiment_matrix_v0.yaml`. REORG04 rewrote 4 and 1 path lines inside those files. Neither the raw nor the LF hash of the current files matches, so line endings are not the mechanism — the content changed, and the change is path-prefix text only.

## 4. Migration-only proof

`REORG04_FROZEN_INPUT_DRIFT_IS_MIGRATION_ONLY__NO_SCIENTIFIC_FIELD_CHANGED`

For every drifted artifact, all five proofs hold: `numeric_values_unchanged`, `booleans_unchanged`, `field_structure_unchanged`, `verdict_text_unchanged`, `thresholds_widened = false`, plus an identical scientific-projection SHA-256.

8 rebinds were required; 0 were aborted for scientific drift.

## 5. Runner safety

`control_02/tests/run_all.py` overwrote `results/control_02_gate_check.json` during a **failing** run — the reported Gate truncation reproduced under observation. It is classified `DESTRUCTIVE_ON_FAILURE` and is forbidden in the active tree.

`safe_capsule_verify.py` monitored 373 protected files; active tree intact = `True`.

## 6. What did not change

- CTRL-01 remains **REPEAT** (negative result). 22/22 tests is software reproducibility, not a Gate.
- CTRL-02 remains **PASS_WITH_PROVISIONAL_SCOPE**. 24/24 does not upgrade its provisional actuator/time-window scope.
- sim_11 remains `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`.

## 7. Reproduction

```bash
python 30_simulation/sim_13_viability_extension_r1/09_reorg04_repro/safe_capsule_verify.py
```
