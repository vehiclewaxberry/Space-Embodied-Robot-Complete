# SIM12 FACTORIAL REPRODUCTION REPORT V2

`RESEARCH_COUPLED_CLOSURE_R1 / RC1-R2` — generated 2026-08-29. `review_status = PENDING_OWNER_REVIEW`. No parent artifact was mutated.

## 1. What changed

- Legacy sim_12 Phase 1: **16 cells**, 6 labelled `FEASIBLE`, `flex_status = UNKNOWN_NOT_IN_CRITERIA`.
- V2 factorial: **24 cells** = 4 cases x 2 alpha x 3 modes, one strategy-invariant Gate vector, classifications {"UNKNOWN": 9, "UNSAFE": 15}.
- **No cell is `ROBUST_SAFE`.** Every previously `FEASIBLE` cell is now `UNKNOWN`, because `m_tauw`, `m_clearance` and `m_flex` have no evaluable value and the frozen-input hash chain is broken.

## 2. The two structural defects that V2 removes

**Defect 1 — collapsed factor structure.** In `strategy_eval.py` the pre-contact factor is set by `alpha = 1.0 if strategy == 'S2_velocity_matching' else 0.0`, so `S1_passive`, `S3a_wheel_bias` and `S4_post_capture_detumble` share one identical physical transition. Verified: `impulse_Ns`, `H_required_Nms` and `post_capture_rate_dps` are byte-identical across those three labels in all four cases. The four labels are therefore 4 of 24 factorial cells, not 4 strategies.

**Defect 2 — strategy-dependent Gate subset.** `S4` used `feas = gate1 and gate3 and gate4` (wheel Gate deleted); `S1/S2/S3a` used `feas = gate1 and gate2` (thruster Gates deleted). Symptom in the frozen CSV: `C_transition / S4` is `FEASIBLE` while carrying `wheel_margin_Nms = -0.068886`. In V2 the thruster mode reports `m_Hw = 1.0` because its *demand* is zero — the Gate itself is never removed.

## 3. Global Gate vector and M_phys

`m_k = (L_k - y_k)/s_k` for upper bounds, `(y_k - L_k)/s_k` for lower bounds, with `s_k = L_k` frozen. `M_phys_restricted = min_k m_k` over evaluable components only; absent components are never zero-filled.

Monotonicity argument: adding a component can only lower the min, so `M_phys_restricted < 0` is **decisive** for `UNSAFE`, while `>= 0` is necessary but not sufficient for safety. This is why negative-margin cells are still classified `UNSAFE` despite the broken hash chain, and non-negative cells are not promoted above `UNKNOWN`.

| component | limit | status |
|---|---|---|
| `m_omega` | 2.0 deg/s | FROZEN |
| `m_Hw` | 0.3 N*m*s | FROZEN |
| `m_tauw` | None N*m | ABSENT |
| `m_dv` | 32.205882352941174 N*s | FROZEN |
| `m_fuel` | 54.73476731425644 g | FROZEN |
| `m_time` | 3600.0 s | FROZEN_LIMIT__VALUE_ABSENT_FOR_WHEEL_MODES |
| `m_clearance` | 0.02 m | FROZEN_LIMIT__VALUE_ABSENT_NO_L2_MODEL |
| `m_flex` | 0.001 J | FROZEN_LIMIT__VALUE_ABSENT_DISC_001_UNRESOLVED |
| `m_domain` | None boolean | VALIDITY_GATE_NOT_A_MARGIN |
| `m_evidence` | None boolean | VALIDITY_GATE_NOT_A_MARGIN |

## 4. Old M reproducibility

The externally supplied margins **reproduce exactly** under `s_k = L_k`; in both cases the binding component is `m_omega`. The prior audit recorded them as `UNVERIFIED` because no margin normalization was defined anywhere in the repository — that is now closed.

| cell | claimed M | recomputed M | abs diff | binding |
|---|---|---|---|---|
| C_transition|a0|WHEEL_BIAS | 0.013381 | 0.013381287449 | 2.874490000002311e-07 | m_omega |
| C_transition|a1|THRUSTER | 0.048817 | 0.048817015595 | 1.559499999970182e-08 | m_omega |

## 5. Scientific results found

**Result A — strict feasibility reversal: 1 found.**

- `C_transition / WHEEL_BIAS`: velocity matching cuts contact impulse 21.7408% (0.157439 -> 0.123211 N*s) and raises captured momentum 68.8908%, driving `M_phys` 0.013381287449 -> -0.076717763971 and the classification `UNKNOWN` -> `UNSAFE`.

**Result B — binding-Gate switches: 11 found across 5 independent (case, driver) combinations.** The three analytic wheel-bias boundaries all hold: `True`.

| case | driver | held fixed | from | to | class from | class to |
|---|---|---|---|---|---|---|
| A_low | mode | alpha=0 | WHEEL_DIRECT -> m_omega | WHEEL_BIAS -> m_Hw | UNKNOWN | UNKNOWN |
| A_low | mode | alpha=0 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNKNOWN | UNKNOWN |
| A_low | mode | alpha=1 | WHEEL_DIRECT -> m_omega | WHEEL_BIAS -> m_Hw | UNKNOWN | UNKNOWN |
| A_low | mode | alpha=1 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNKNOWN | UNKNOWN |
| B_anchor | mode | alpha=0 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNSAFE | UNSAFE |
| B_anchor | mode | alpha=1 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNSAFE | UNSAFE |
| C_transition | alpha | mode=WHEEL_BIAS | a0 -> m_omega | a1 -> m_Hw | UNKNOWN | UNSAFE |
| C_transition | mode | alpha=0 | WHEEL_DIRECT -> m_Hw | WHEEL_BIAS -> m_omega | UNSAFE | UNKNOWN |
| C_transition | mode | alpha=1 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNSAFE | UNKNOWN |
| D_extreme | mode | alpha=0 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNSAFE | UNSAFE |
| D_extreme | mode | alpha=1 | WHEEL_BIAS -> m_Hw | THRUSTER -> m_omega | UNSAFE | UNSAFE |

**Result C — SAFE to UNKNOWN.** Cause histogram over the 9 `UNKNOWN` cells: `{"m_clearance": 9, "m_flex": 9, "m_tauw": 9, "m_time": 5, "_hash_chain_block_applies_to_all_nonunsafe": true}`.

**Result D — honest ABORT region preserved.** Cases in which every one of the six cells is `UNSAFE`: `['B_anchor', 'D_extreme']`. These are retained, not deleted.

## 6. Reproduction

```bash
python 30_simulation/sim_13_viability_extension_r1/02_sim12_factorial_reissue/build_d1_factorial.py
```

## 7. What this does not authorize

- No cell is SAFE. No FLEX qualification. No Sim13 parent PASS.
- No CTRL-03 closure, no Engineering Release, no competition claim.
- `next_stage_authorized = false`, `release_credit = false`.
