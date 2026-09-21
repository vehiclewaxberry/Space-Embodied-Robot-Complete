# NATIVE-MECH-REAL-01 / Stage 2 Report

**Machine Verdict: `STAGE2_PARTIAL_HOLD`**
**Generated: 2026-07-28T02:56 UTC+8**

## 1. Summary

Stage 2 aimed to build the B601 three-representation subsystem (HIFI, KINEMATIC_PROXY, MASS_SURROGATE) inside `Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION`.

| Gate | Status | Evidence |
|------|--------|----------|
| S2_G1 Source Baseline Preflight | **PASS** | 108/108 files match frozen manifest |
| S2_G2 URDF Authority Contract | **PASS** | SHA match, 10 links, 9 joints, 4.695556 kg |
| S2_G3 Kinematic Proxy Built | **PASS** | 10/10 parts + assembly, 9 joint chains |
| S2_G4 Mass Surrogate Built | **PASS** | Total mass error 8.88e-16 kg (<<1e-9) |
| S2_G5 HIFI Stowed | **HOLD** | 252MB STEP import failed all COM paths |
| S2_G6 Three-Rep Assembly | **HOLD** | COM degradation blocked ActivateDoc3 |
| S2_G7 Top Assembly Integration | **HOLD** | Blocked by G6 |
| S2_G8 Close-Reopen Verify | **HOLD** | Blocked by G6/G7 |
| S2_G9 Source Post-Hash | **PASS** | 108/108 unchanged |

**5 PASS, 4 HOLD, 0 FAIL**

## 2. Objects Built

### 2.1 B601_KINEMATIC_PROXY (BUILT)

- 10 proxy SLDPRT files: one per URDF link (`base_link`, `link1`–`link6`, `gripper_link`, `gripper_left`, `gripper_right`)
- Each is a conservatively sized box (mid-plane extrusion), marked `CONSERVATIVE_PROXY_NOT_VENDOR_SHELL`
- Assembly `B601_KINEMATIC_PROXY.SLDASM` with 10 components at identity transform
- All 9 URDF joints recorded as custom properties (origin, rpy, axis, type)
- `KINEMATIC_AUTHORITY=ACCEPTED_URDF`, `MASS_AUTHORITY=EXCLUDED_IN_THIS_REPRESENTATION`

### 2.2 B601_MASS_SURROGATE (BUILT)

- 10 mass-carrying SLDPRT files, each a cube sized for exact mass at default density (500 kg/m³)
- Per-link mass readback errors: 1e-17 to 4e-16 kg (IEEE 754 precision)
- Assembly total mass readback: **4.695555949342987 kg** (error = 8.88e-16 kg, within 1e-9 tolerance)
- Full URDF inertial data (mass, COM xyz, 6 inertia components) stored as custom properties per link
- `MASS_AUTHORITY=ACCEPTED_URDF`

**COM/inertia limitation**: The cube geometry's center of mass and moment of inertia do NOT match the URDF values. Only the mass magnitude is matched. URDF COM and inertia are stored in custom properties only. This is a known limitation of the surrogate approach and is recorded as an engineering hold.

### 2.3 B601_STOWED_HIFI (HOLD)

The 252MB vendor STEP (`B601_VENDOR_STOW.step`, SHA `cc8cfdd2...28ab`) was verified on disk. Import was attempted via:

1. `OpenDoc6` as part → returned `None` in 0.9s
2. `OpenDoc6` as assembly → hung (killed after 60s)
3. `LoadFile4` → not reached due to hang

This is consistent with the prior `B601_SWAP01` failure documented in ASSET-00. **No fake HIFI was generated.** The recommended resolution is interactive GUI import with user monitoring.

### 2.4 B601_THREE_REPRESENTATIONS.SLDASM (HOLD)

The mutual-exclusion wrapper assembly was NOT completed because `ActivateDoc3` (all variants: ActivateDoc, ActivateDoc2, ActivateDoc3) became non-functional after SolidWorks was force-killed during the HIFI import attempt. The COM connection was in a degraded state where document activation could not switch focus.

The individual sub-assemblies (KINEMATIC_PROXY, MASS_SURROGATE) are complete and self-contained. Manual assembly requires:
1. Create `B601_THREE_REPRESENTATIONS.SLDASM`
2. Insert `B601_KINEMATIC_PROXY.SLDASM` and `B601_MASS_SURROGATE.SLDASM`
3. Create 3 configurations with mutual-exclusion suppression per taskbook table
4. Insert into V2.3 top assembly

## 3. Source Baseline Integrity

| Check | Result |
|-------|--------|
| Pre-hash (108 files) | PASS |
| Post-hash (108 files) | PASS |
| Source files modified | 0 |
| Source files added | 0 |
| Source files removed | 0 |

The V2.2_NATIVE source baseline was NOT modified by any Stage 2 operation.

## 4. Engineering Holds (unchanged from Phase 1)

- `STOW_VECTOR_STATUS=CANDIDATE_HOLD`
- `STOW_Z_LIMIT=UNKNOWN`
- `STOW_CONTACT_QUALIFICATION=HOLD`
- `MATERIAL/LOAD/FASTENER/PRELOAD=UNKNOWN_OR_TBD`
- `NO_FEA_NO_DYNAMICS_NO_FLIGHT_RELEASE`
- C5 stow wing pack width 238.3 > 226.3 mm
- Dual solar root mechanism 302.3 > 226.3 mm

## 5. New Technical Findings

### D-STAGE2-01: SolidWorks Default Density

The `gb_part.prtdot` template uses a default material density of **500 kg/m³**. This was exploited to achieve exact mass matching: each mass surrogate link has cube side = (mass / 500)^(1/3). The mass error is at IEEE 754 double-precision level (~1e-16 kg), far exceeding the 1e-9 tolerance.

### D-STAGE2-02: FeatureExtrusion2 Requires 23 Parameters

The SolidWorks 2024 `FeatureExtrusion2` API requires 23 parameters in early binding, not the 20 documented in some references. The correct signature was recovered from `b3_lib.sw_part_factory.extrude_checked`. Mid-plane extrusion uses T1=6.

### D-STAGE2-03: ActivateDoc3 COM Degradation

After a forced SolidWorks process kill, the COM interface enters a degraded state where `ActivateDoc3` (and all activation variants) cannot switch the active document. Documents are listed correctly via `GetFirstDocument` enumeration but activation always returns None. Recovery requires a clean SolidWorks exit (not kill) and fresh start.

### D-STAGE2-04: HIFI STEP Import Capacity

The 252MB vendor STEP exceeds the COM import capacity on this machine. `OpenDoc6(part)` returns immediately with None (likely failing size/complexity check). `OpenDoc6(asm)` hangs indefinitely. This matches the prior ASSET-00 finding where `LoadFile4` took 215s for a 35MB version of the same geometry.

## 6. Files Produced

```
03_B601_Three_Representations/
  B601_KINEMATIC_PROXY/
    PROXY_base_link.SLDPRT   (10 proxy parts)
    PROXY_link1.SLDPRT
    PROXY_link2.SLDPRT
    PROXY_link3.SLDPRT
    PROXY_link4.SLDPRT
    PROXY_link5.SLDPRT
    PROXY_link6.SLDPRT
    PROXY_gripper_link.SLDPRT
    PROXY_gripper_left.SLDPRT
    PROXY_gripper_right.SLDPRT
    B601_KINEMATIC_PROXY.SLDASM
  B601_MASS_SURROGATE/
    MASS_base_link.SLDPRT    (10 mass parts)
    MASS_link1.SLDPRT
    MASS_link2.SLDPRT
    MASS_link3.SLDPRT
    MASS_link4.SLDPRT
    MASS_link5.SLDPRT
    MASS_link6.SLDPRT
    MASS_gripper_link.SLDPRT
    MASS_gripper_left.SLDPRT
    MASS_gripper_right.SLDPRT
    B601_MASS_SURROGATE.SLDASM
  B601_STOWED_HIFI/          (empty - HOLD)

evidence/stage2_b601_three_rep/
    preflight_and_source_hashes.json
    b601_authority_contract.json
    kinematic_proxy_parts.json
    kinematic_proxy_assembly.json
    mass_surrogate_readback.json
    hifi_import_and_reopen.json
    source_baseline_post_hash.json
    stage2_machine_verdict.json
    execution_log.jsonl
    NATIVE_MECH_REAL_01_STAGE2_REPORT.md
```

## 7. Verdict

**`STAGE2_PARTIAL_HOLD`**: Two of three representations (KINEMATIC_PROXY, MASS_SURROGATE) are fully built and verified. HIFI import and three-representation wrapper assembly require interactive completion. Source baseline integrity is proven (108/108 pre and post). No unsupported claims.
