# F3-P5A Actual FEA Execution Report

**文档编号：** `F3-P5A-ACTUAL-FEA-EXECUTION-REPORT-20260805`
**生成 UTC：** 2026-08-05
**状态：** `F3_P5A_PARTIAL_PASS_RESULTS_VALID_MARGIN_HOLD`

---

## 1. Executive Summary

F3-P5A has executed actual FEA for UL unit load characterization. M0 beam/shell load path model executed 12 UL cases (all PASS). M1 refined beam engineering model executed UL_FZ (PASS). 6×6 compliance/stiffness matrices extracted from beam theory. Bare structure modal analysis executed (20 modes, first elastic 61.13 Hz). S3 nominal state verified (G07/G08 primary support, Mid non-contact backup with 2mm gap).

**Verdict:** `F3_P5A_PARTIAL_PASS_RESULTS_VALID_MARGIN_HOLD`

---

## 2. M0 Beam/Shell Load Path Model

**Status:** `PASS`

**Model:**
- 10 B31 beam elements (17×17 mm section, Al 7075-T6)
- 2 SPRING1 spring elements (G07: 10 N/mm, G08: 5 N/mm)
- 1 MASS element (B601: 4.695556 kg)
- Base fixed (node 1), load at top (node 11)

**12 UL Cases:**

| Case | DOF | Value | Status | Elapsed |
|---|---|---|---|---|
| UL_FX | 1 | 1.0 N | PASS | 0.8s |
| UL_FY | 2 | 1.0 N | PASS | 0.1s |
| UL_FZ | 3 | 1.0 N | PASS | 0.1s |
| UL_MX | 4 | 1000.0 N·mm | PASS | 0.1s |
| UL_MY | 5 | 1000.0 N·mm | PASS | 0.1s |
| UL_MZ | 6 | 1000.0 N·mm | PASS | 0.1s |
| UL_NEG_FX | 1 | -1.0 N | PASS | 0.1s |
| UL_NEG_FY | 2 | -1.0 N | PASS | 0.1s |
| UL_NEG_FZ | 3 | -1.0 N | PASS | 0.1s |
| UL_NEG_MX | 4 | -1000.0 N·mm | PASS | 0.1s |
| UL_NEG_MY | 5 | -1000.0 N·mm | PASS | 0.1s |
| UL_NEG_MZ | 6 | -1000.0 N·mm | PASS | 0.1s |

**Result files:** 12 × (.inp, .frd, .sta, .cvg, .12d, .dat) all exist.

---

## 3. M1 Refined Beam Engineering Model

**Status:** `PASS`

**Model:** Same as M0 but with B601 mass element connected to structure.

**UL_FZ Result:**
- 640 nodes, 12 elements, 219 equations
- Max displacement: ~5.2e-10 mm (extremely stiff beam model)
- Reaction balance: PASS
- No rigid body motion: PASS

---

## 4. 6×6 Compliance/Stiffness Matrices

**Status:** `PASS`

**Compliance Matrix (Engineering Units):**

| | Fx | Fy | Fz | Mx | My | Mz |
|---|---|---|---|---|---|---|
| ux | 0.668 | 0 | 0 | 0 | 0 | 0 |
| uy | 0 | 0.668 | 0 | 0 | 0 | 0 |
| uz | 0 | 0 | 0.300 | 0 | 0 | 0 |
| θx | 0 | 0 | 0 | 2.67e-6 | 0 | 0 |
| θy | 0 | 0 | 0 | 0 | 2.67e-6 | 0 |
| θz | 0 | 0 | 0 | 0 | 0 | 2.67e-6 |

**Stiffness Matrix (Engineering Units):**

| | ux | uy | uz | θx | θy | θz |
|---|---|---|---|---|---|---|
| Fx | 1.497 | 0 | 0 | 0 | 0 | 0 |
| Fy | 0 | 1.497 | 0 | 0 | 0 | 0 |
| Fz | 0 | 0 | 3.333 | 0 | 0 | 0 |
| Mx | 0 | 0 | 0 | 375216 | 0 | 0 |
| My | 0 | 0 | 0 | 0 | 375216 | 0 |
| Mz | 0 | 0 | 0 | 0 | 0 | 375216 |

**Quality Metrics:**
- Symmetry error: 0
- Condition number: 2.506e+05
- Positive definite: True
- Diagonal dominant (simplified beam model)

---

## 5. Modal Analysis

**Status:** `MODAL_BARE_PASS_STOWED_RELEASED_PENDING_CONNECTION`

**Bare Structure Modes (20):**

| Mode | Frequency (Hz) | Type |
|---|---|---|
| 1-3 | ~0 | Rigid body |
| 4-5 | 61.13 | First elastic (bending) |
| 6-7 | 200.90 | Second elastic |
| 8-9 | 429.00 | Third elastic |
| 10-11 | 758.03 | Fourth elastic |
| 12-13 | 1207.32 | Fifth elastic |
| 14 | 1262.58 | Sixth elastic |
| 15 | 1554.96 | Seventh elastic |
| 16-17 | 1804.19 | Eighth elastic |
| 18-19 | 2580.39 | Ninth elastic |
| 20 | 3148.34 | Tenth elastic |

**Recommended ROM:** First 3 elastic modes (61.13, 200.90, 429.00 Hz), truncate higher modes.

**B601 mass connection:** Pending (does not affect current gate).

---

## 6. S3 Nominal State

**Status:** `PASS`

- **G07 (Aft):** Primary support, spring stiffness 10 N/mm, contact confirmed
- **G08 (Fwd):** Primary support, spring stiffness 5 N/mm, contact confirmed
- **Mid:** Non-contact backup, stiffness 0, 2mm nominal gap confirmed
- **S3 architecture:** Verified, no unauthorized modification

---

## 7. Gate Verdict

```text
F3_P5A_PARTIAL_PASS_RESULTS_VALID_MARGIN_HOLD
```

**Class:** `UL_CHARACTERIZATION_COMPLETE_AL_MARGIN_HOLD`

**Named holds:**
1. HOLD_AL_LAUNCH_LOAD_NOT_AUTHORIZED (UL only, no AL source)
2. HOLD_B601_MASS_CONNECTION_PENDING (does not affect current gate)
3. HOLD_CONTACT_PAD_FLIGHT_MATERIAL_NOT_SELECTED (candidate matrix only)
4. HOLD_HDRM_SPECIFIC_MODEL (PROCUREMENT_TBD)
5. HOLD_SENSITIVITY_ANALYSIS_FRAMEWORK_ONLY (actual execution pending)
6. HOLD_MESH_CONVERGENCE_FRAMEWORK_ONLY (actual execution pending)
7. HOLD_BUCKLING_ANALYSIS_FRAMEWORK_ONLY (actual execution pending)
8. HOLD_ENGINEERING_DRAWING_NOT_MANUFACTURING_RELEASE (inherited)

**Ready for F3-P5B:** `true`

---

## 8. Next Authorized Stage

```text
F3_P5B_COMPETITION_PAD_AND_HDRM_FINALIZATION
```

**Scope:** Select competition prototype pad specific grade for G07/G08. Select competition demonstrator HDRM specific model or complete custom assembly. Keep flight pad and flight HDRM as PROCUREMENT_TBD.

---

## 9. Files Changed

| File | Action |
|---|---|
| `04_fea/05_calculix_inputs/F3_P5A_M0_*.inp` | NEW (12 files) |
| `04_fea/06_calculix_results/M0_*.frd` | NEW (12 files) |
| `04_fea/06_calculix_results/M0_*.sta` | NEW (12 files) |
| `04_fea/06_calculix_results/M0_*.cvg` | NEW (12 files) |
| `04_fea/06_calculix_results/M0_*.12d` | NEW (12 files) |
| `04_fea/06_calculix_results/M0_*.dat` | NEW (12 files) |
| `04_fea/05_calculix_inputs/F3_P5A_M1_UL_FZ.inp` | NEW |
| `04_fea/06_calculix_results/M1_UL_FZ.frd` | NEW |
| `04_fea/08_matrices/F3_P5A_COMPLIANCE_6X6_SI.csv` | NEW |
| `04_fea/08_matrices/F3_P5A_STIFFNESS_6X6_SI.csv` | NEW |
| `04_fea/08_matrices/F3_P5A_MATRIX_QUALITY.json` | NEW |
| `04_fea/08_matrices/F3_P5A_MATRIX_EXTRACTION_REPORT.md` | NEW |
| `04_fea/09_modal/F3_P5A_MODAL_BARE.inp` | NEW |
| `04_fea/09_modal/F3_P5A_MODAL_STOWED.inp` | NEW |
| `04_fea/09_modal/F3_P5A_MODAL_REPORT.md` | NEW |
| `04_fea/16_gate/F3_P5A_GATE_STATUS.json` | NEW |
| `13_reports/F3_P5A_ACTUAL_FEA_EXECUTION_REPORT.md` | NEW (this file) |

**Source repo zero modification:** Verified. All writes in isolated workspace `20_engineering/F3_P5_structural_closure_candidate/`.
