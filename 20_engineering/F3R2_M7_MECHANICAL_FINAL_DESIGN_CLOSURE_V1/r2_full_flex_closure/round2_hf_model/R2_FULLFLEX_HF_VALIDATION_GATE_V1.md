# R2_FULLFLEX_HF_VALIDATION_GATE_V1 — 人读版（机器字段以同basename JSON 为准）

- schema: `R2_FULLFLEX_HF_VALIDATION_GATE_V1`
- 生成时间：2026-08-23T20:45:41.771960+08:00（宿主机本地钟）
- 生成方：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure) / AGENT-B1 round2_hf_model builder (pure numpy/scipy; upstream read-only)
- 裁决对象：`R2_FULLFLEX_HF_MODEL_V1.yaml` + `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json`
- **overall_gate = FAIL**；`review_status=PENDING_OWNER_REVIEW`；
  `next_stage_authorized=false`；`release_credit=false`；fail-closed。

## 判据

| ID | 判据 | 实测 | 门槛 | 裁决 |
|---|---|---|---|---|
| G1_MASS_CLOSURE_EXACT | HF total per wing == 0.78 kg exact to fp noise (kinetic leaf 0.54 + MC-A rigid non-tracking ledger 0.24) | {"kinetic_leaf_mass_kg": 0.5343991071428571, "abs_error_leaf_kg": 0.005600892857142936, "total_per_wing_kg": 0.774399107… | abs error < 1e-12 kg | **FAIL** |
| G2_SPD | M_hf and K_hf (latched nominal) symmetric positive definite | {"M_hf_min_eigenvalue": 1.6367769490747446e-09, "K_hf_latched_nominal_min_eigenvalue": 0.1026489260643135, "min_generali… | min eigenvalues > 0 | **PASS** |
| G3_MESH_CONVERGENCE | mesh convergence < 1% on first 3 modes between N=20 and N=40 per leaf | {"max_abs_shift_pct_first3_N20_vs_N40": 0.019277186563037504, "shift_pct_N20_vs_N40_first8": [2.747509782750146e-05, 0.0… | < 1.0 % | **PASS** |
| G4_NO_FORBIDDEN_R1_VALUES | no forbidden R1-lane values anywhere in outputs | {"files_scanned": ["build_r2_hf_model.py", "R2_FULLFLEX_HF_MODEL_V1.yaml", "R2_FULLFLEX_HF_MODEL_V1.md", "R2_FULLFLEX_HF… | unclassified hits == 0 and narrative hits == 0 | **PASS** |
| G5_NO_ZERO_FILLED_UNKNOWNS | independent latch stiffness stays explicit null (never zero-filled) | {"card_latch_is_null": true, "evidence_latch_is_null": true}… | both null | **PASS** |
| G6_PROVISIONAL_CLASSES_SPELLED | PROVISIONAL_DERIVED class spelled on every candidate band (EI, GJ, zeta, k_theta_root, k_theta_inter) | {"EI": "PROVISIONAL_DERIVED", "k_theta_root": "PROVISIONAL_DERIVED", "k_theta_inter": "PROVISIONAL_DERIVED", "GJ": "PROV… | every band carries PROVISIONAL_DERIVED | **PASS** |

## 黑名单扫描（检测器定义）

needles = ["29.226410622980581", "0.3483933", "1.7419665", "measured_mass", "24.0 kg legacy"]（遗留 R1 车道禁值；本目录产物中仅以检测器定义语境出现；
命中明细与语境分类见 JSON criteria[3].measured）。

## nonclaims（逐字）

- not a ROM yet (no modal truncation delivered)
- not a coupled evaluation (fixed-base per-wing only)
- r2_full_flexible_coupling not closed by this file (stays NOT_EVALUATED)
- e15 REPEAT_ANCF_CERTIFICATION unchanged
- no production/manufacturing/qualification/launch/flight authority
- no PROVISIONAL band promoted; candidate != authority

## 备注

- test PASS ≠ gate PASS；本 gate PASS 只在候选级解除上述六条判据，不授权任何下一阶段。
- ODR-45..49 钉状态：PINNED。
- self_hash_policy：SELF_REFERENCE_EXCLUDED - this file carries no hash of itself; downstream consumers pin its sha256 after emission (same policy as e21/V5 manifests and 02_bridge)
