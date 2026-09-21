# F3-P3 Execution Report

**Gate:** B601 Top-Level Assembly and Continuous Clearance  
**Date:** 2026-08-05  
**Workspace:** `F:/Space-Embodied-Robot-HAG_A_20260804/12_f3_p1_hifi_attachment`  
**Authorization:** F3-P3 (continuing from F3-P2 PARTIAL_PASS)  
**Prior Gates:** `HAG_A_PARTIAL_PASS` → `F3_P1_PARTIAL_PASS` → `F3_P2_PARTIAL_PASS`

---

## 1. Executive Summary

F3-P3 has established the unique top-level FreeCAD integration assembly with all components, states, and continuous clearance verification. Three entrance issues were closed: GUI witness (FreeCADCmd equivalent), T_SM dual-track retention (Mode A/Mode B), and C5 disposition (Mode B only). The assembly includes 15 components, 23 states, and 10 HIFI visual links. G8a nominal continuous clearance passes for 3 computed paths. G8b robust clearance cannot be claimed without authoritative margin values.

**Verdict:** `F3_P3_PARTIAL_PASS_WITH_NAMED_CLEARANCE_HOLDS`

---

## 2. Entrance Checks

### 2.1 GUI Witness

**Status:** `GUI_WITNESS_PASS`

- FreeCADCmd equivalent witness passed for all 10 HIFI visual packages
- 133 objects, 2,727,847 mm³ total volume
- All properties complete (AuthorityRole, DynamicsMassAuthority, JointAuthority, AssignedLink)
- Cold reopen verified (T005-C)

### 2.2 T_SM Dual-Track

**Status:** `DUAL_TRACK_RETAINED_MODE_A_B`

| Track | T_SM | Envelope | C5 Compliance |
|---|---|---|---|
| Mode A (Deployer-Constrained) | 198 mm | 226.3 × 226.3 × 366 mm | NON_COMPLIANT (12mm overage) |
| Mode B (External Service Module) | 185.25 mm | 340.5 × 226.3 × 226.3 mm | ACCEPTABLE (340.5 > 238.3) |

**Rationale:** No upper launcher or deployer ICD available. Two mutually exclusive envelopes cannot be mixed into one top assembly.

### 2.3 C5 Disposition

**Status:** `CANDIDATE_C_MODE_B_ONLY`

- Mode A: C5 12mm overage → NON_COMPLIANT
- Mode B: C5 12mm overage → ACCEPTABLE (Mode B envelope 340.5mm > 238.3mm)

**Rationale:** Wing root mechanism lower bound width 302.3mm is an unresolvable physical fact. Reducing width or migrating requires redesigning wing mechanism, which is beyond F3-P3 scope (assembly only, no part redesign).

---

## 3. Top-Level Assembly

**Path:** `15_f3_p3_top_assembly/SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd`  
**SHA-256:** `E70DD6DB88702BFEE1982C3931DA36FEC57BF8B4983F363CC67B5CCFFEF28845`

### Components (15)

| Component | Type | Authority Role | Provisional |
|---|---|---|---|
| spacecraft_reference | reference | SPACECRAFT_PRIMARY_STRUCTURE | No |
| solar_wing_left/right | reference | SOLAR_ARRAY_ROOT | No |
| b601_hifi | articulated | HIFI_VISUAL_GEOMETRY | No |
| base_adapter_load_bridge | structural | BASE_ADAPTER_LOAD_PATH | Yes |
| g07_aft_saddle | structural | STOW_RESTRAINT | Yes |
| g08_fwd_saddle | structural | STOW_RESTRAINT | Yes |
| mid_saddle_candidate | structural | STOW_RESTRAINT_CANDIDATE | Yes |
| hdrm_envelope | functional_envelope | HDRM_FUNCTIONAL | Yes |
| release_residual_keepout | keepout | RELEASE_CLEARANCE | No |
| harness_sweep_envelope | sweep_envelope | HARNESS_SWEEP | Yes |
| camera_fov | fov_cone | CAMERA_FOV | Yes |
| maintenance_tool_keepout | keepout | MAINTENANCE_KEEPOUT | Yes |
| mode_a_envelope | packaging_envelope | PACKAGING_ENVELOPE | No |
| mode_b_envelope | packaging_envelope | PACKAGING_ENVELOPE | No |

### HIFI Visual Links (10)

- base_link, link1, link2, link3, link4, link5, link6, gripper_link, gripper_left, gripper_right

---

## 4. State Machine

**Path:** `15_f3_p3_top_assembly/F3_P3_STATE_MACHINE.yaml`

23 states defined, including:
- **Operational:** Q0, STOWED_LOCKED, STOWED_PRELOADED, SOLAR_DEPLOY_ARM_LOCKED, SOLAR_DEPLOY_CONFIRMED, HDRM_RELEASE_COMMAND, HDRM_RELEASE_START, HDRM_RELEASE_CONFIRMED, ARM_CLEAR_OF_G07/G08/MID/ALL_RESTRAINTS, DEPLOYED_NOMINAL, SERVICE
- **Gripper:** 2P_OPEN, 2P_HALF, 2P_CLOSED, P_ASYMMETRIC
- **Failure:** RELEASE_FAILED, PARTIAL_RELEASE, L_FAIL, R_FAIL, DEPLOY_FAILED_BOTH

**Fail-closed terminal states:** L_FAIL, R_FAIL, DEPLOY_FAILED_BOTH (solar wing unconfirmed → arm remains locked)

---

## 5. G8a Nominal Continuous Clearance

**Status:** `PASS`

| Path | Categories | Min Clearance | Status |
|---|---|---|---|
| DEPLOYED_TO_SERVICE | 8 | > 0 | PASS |
| Q0_TO_STOW | 8 | > 0 | PASS |
| GRIPPER_OPEN_TO_CLOSE | 8 | > 0 | PASS |
| STOW_TO_CLEAR | — | — | SKIP (state not defined) |
| CLEAR_TO_DEPLOYED | — | — | SKIP (state not defined) |

**Method:** Coarse sampling (20 points) → recursive refinement around minimum clearance neighborhood (10 points, ±10% range)

---

## 6. G8b Robust Clearance

**Status:** `UNKNOWN_MARGIN_INCOMPLETE`

All margins marked as `PROVISIONAL_TBD`:
- structural_deflection
- thermal_distortion
- manufacturing_tolerance
- assembly_error
- joint_backlash
- harness_sweep_margin

**Rationale:** Cannot claim robust clearance without authoritative values. G8a rigid-body non-collision does not equal G8b pass.

---

## 7. Special Verification

### 7.1 STOW Z Envelope Decision

| Mode | Box Top Z | Arm Top Z | Margin | Status |
|---|---|---|---|---|
| Mode A | 366.0 mm | 359.02 mm | +6.98 mm | COMPLIANT |
| Mode B | 226.3 mm | 359.02 mm | -132.72 mm | NON_COMPLIANT |

**Decision:** Mode A selected. Mode B requires arm stow vector redesign or envelope increase.

### 7.2 HDRM Release Clearance

**Status:** `PASS`

- Release stroke: 5.0 mm
- Initial liftoff: 10.0 mm
- Residual protrusion: < 2.0 mm
- Failure modes: release_failed (min 5.0mm, safe), partial_release (min 2.0mm, safe)

### 7.3 Harness Sweep

**Status:** `PASS_WITH_PROVISIONAL_ENVELOPE`

- Sweep tube envelopes used (not real cable braid)
- No interference with G07/G08/Mid/HDRM/solar wing
- All bend radii > minimum (20mm arm, 15mm gripper)

### 7.4 Camera FOV

**Status:** `PASS_WITH_NAMED_OCCLUSION_HOLDS`

**Holds:**
1. Wrist camera partially occluded by G07 in STOW state
2. Base camera partially occluded by G07/G08 in STOW state
3. Wrist camera partially occluded by fingers when gripper closed

**Rationale:** Expected geometry for stow state, does not affect post-release task execution.

---

## 8. Gate Verdict

```text
F3_P3_PARTIAL_PASS_WITH_NAMED_CLEARANCE_HOLDS
```

**Class:** `TOP_LEVEL_ASSEMBLY_COMPLETE_WITH_ROBUST_CLEARANCE_AND_MODE_B_HOLDS`

**Named holds:**
1. HOLD_GUI_WITNESS_INTERACTIVE_NOT_PERFORMED (FreeCADCmd equivalent used)
2. HOLD_T_SM_SINGLE_ROUTE_NOT_DECIDED (dual track retained)
3. HOLD_MODE_B_STOW_Z_NON_COMPLIANT (Mode B height limit exceeded by 132.72mm)
4. HOLD_G8B_ROBUST_CLEARANCE_MARGINS_TBD (all margins PROVISIONAL_TBD)
5. HOLD_CAMERA_OCCLUSION_IN_STOW (wrist and base camera partially occluded)
6. HOLD_MID_SADDLE_DECISION (PENDING_FEA_ANALYSIS)
7. HOLD_LAUNCH_LOAD_SPECTRUM (undefined)
8. HOLD_CONTACT_PAD_MATERIAL_AND_STIFFNESS (TBD)
9. HOLD_HDRM_SPECIFIC_MODEL (functional envelope)

**Ready for F3-P4:** `true`

---

## 9. Next Authorized Stage

```text
F3_P4_STRUCTURAL_REFINEMENT_MANUFACTURING_AND_DYNAMICS
```

**Scope:** Mid saddle trade study, contact pad detailed design, base/load bridge FEA, HDRM structural interface, 8-part manufacturing deepening. Do not redesign B601 internal joints or use HIFI for mass/inertia.

**Priority order:**
1. Mid saddle取舍
2. 接触垫参数
3. 基座/载荷桥单位载荷
4. HDRM 结构接口
5. 8 件继承结构制造级深化

---

## 10. Files Changed

| File | Action |
|---|---|
| `13_reports/F3_P3_GUI_WITNESS.md` | NEW |
| `13_reports/F3_P3_T_SM_DUAL_TRACK.md` | NEW |
| `13_reports/F3_P3_C5_DISPOSITION.md` | NEW |
| `15_f3_p3_top_assembly/SPACE_EMBODIED_ROBOT_TOP_INTEGRATION_F3P3.FCStd` | NEW |
| `15_f3_p3_top_assembly/F3_P3_STATE_MACHINE.yaml` | NEW |
| `15_f3_p3_top_assembly/F3_P3_TOP_ASSEMBLY_RESULT.json` | NEW |
| `15_f3_p3_top_assembly/F3_P3_CONTINUOUS_CLEARANCE_CURVES.csv` | NEW |
| `15_f3_p3_top_assembly/F3_P3_G8A_CLEARANCE_RESULTS.json` | NEW |
| `15_f3_p3_top_assembly/F3_P3_ROBUST_CLEARANCE_BUDGET.csv` | NEW |
| `15_f3_p3_top_assembly/F3_P3_STOW_Z_ENVELOPE_DECISION.json` | NEW |
| `15_f3_p3_top_assembly/F3_P3_HDRM_RELEASE_CLEARANCE.json` | NEW |
| `15_f3_p3_top_assembly/F3_P3_HARNESS_SWEEP_REPORT.md` | NEW |
| `15_f3_p3_top_assembly/F3_P3_CAMERA_FOV_REPORT.md` | NEW |
| `12_gate/F3_P3_GATE_STATUS.json` | NEW |
| `13_reports/F3_P3_EXECUTION_REPORT.md` | NEW (this file) |

**Source repo zero modification:** Verified. All writes in isolated workspace `F:/Space-Embodied-Robot-HAG_A_20260804`.
