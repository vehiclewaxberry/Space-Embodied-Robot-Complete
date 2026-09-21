# WP7 Critical Load Path Map V1 (ODR-11 layer 3)

generated_local: 2026-08-22T16:36:10.657133+08:00
source: 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational/FEA1B_ELEMENT_FORMULATION_EVIDENCE_V1.json (sha256-16 58e420c0aa966bce)
verdict context: OPERATIONAL_STRUCTURAL_VERIFICATION_PASS — operational structural verification only;
NOT flight qualification (ODR-12 forbidden verdicts not asserted).

## The load path

```text
CAPTURE_150KG_QS (150 kg debris capture)   <-- governing load case
   |
Target (22 kg / 150 kg debris scenario anchors)
   |
Gripper (neutral R1; retention demand per finger, MAV-02)
   |
Wrist / link6 + gripper_link (content-partition union, WP11)
   |
B601 joint chain (6 revolute; kinematics = accepted URDF, L0)
   |
Arm base bolt pattern (as-built 4xM4, 64x64 mm, PCD 90.509642 mm)
   |
M3R Stage A ring  <== CONTROLLING PART (every case, every mesh level)
   |
M3R Stage B (secondary)
   |
Load bridge 160x160x10.75 mm (secondary)
   |
BUS primary structure (z=0 encastre in WP7 = STIFF BOUND, BC_BUS_001 HOLD)
```

## Why this structure is enough — the five layer-3 answers

1. **Controlling load case:** CAPTURE_150KG_QS (150 kg debris capture) — peak element-averaged stress
   1.038 MPa; 8.682x the 22 kg case, 42.08x e-stop,
   84.17x maneuver. Driver: M_z, not F_y: the 150 kg case applies 19073.27 N*mm against 1846.14 N*mm for 22 kg, because the grasp lever arm is 1.21521 m against 0.25173 m. The contact impulse itself differs by only 1.88x; the lever arm differs by 4.83x.
2. **Controlling part:** STAGE_A_RING at the B601 arm-base bolt interface. every case and every mesh level puts the maximum in ESTAGEA, in the top layer, at the as-built M4 pattern (the bolt at x=42.5416, y=-15.5644 mm, i.e. the one closest to the applied transverse load direction). Stage B and the load bridge are secondary.
3. **150 kg genuinely more controlling than 22 kg?** YES
   (stress factor 8.682; moment factor 10.33 — moment-dominated).
4. **E-stop more severe than capture?** NO — capture 150 kg is
   42.08x the e-stop stress.
5. **6061 -> 7075 changes the controlling location?** NO -- it does not change the location and it does not change the stresses at all

## Per-case governing quantities (reference level Z6_ZR_N20K6, element-averaged)

| case | applied Fy [N] | applied Mz [N*mm] | peak elem-avg vM [MPa] | critical zone |
|---|---|---|---|---|
| ARM_MANEUVER_QS | 0.3105 | 217.36 | 0.01233 | ESTAGEA |
| ARM_ESTOP_QS | 0.621 | 434.71 | 0.02465 | ESTAGEA |
| CAPTURE_22KG_QS | 7.212 | 1846.1 | 0.1195 | ESTAGEA |
| CAPTURE_150KG_QS | 13.55 | 19073 | 1.038 | ESTAGEA |

## Zone ordering at reference level (element-averaged MPa)

| zone | peak |
|---|---|
| EBRIDGE | 0.3804 |
| ESTAGEA | 1.038 |
| ESTAGEB | 0.4341 |

## What this map does NOT claim

- No margin of safety is asserted (margin_of_safety_asserted =
  False): candidate typical properties are not flight allowables.
- Mesh convergence in-plane is not claimed (FEA1B-FIND-01); the map reports
  element-averaged values at a fixed reference discretization per the ODR-11
  singularity rule.
- The BUS-side boundary is a stiff bound, not an interface stiffness
  (BC_BUS_001_INTERFACE_STIFFNESS_HOLD).
