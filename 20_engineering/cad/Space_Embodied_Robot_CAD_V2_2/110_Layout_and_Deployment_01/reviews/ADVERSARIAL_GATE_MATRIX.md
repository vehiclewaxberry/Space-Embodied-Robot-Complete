# V22-LAYOUT-AND-DEPLOYMENT-01 independent adversarial gate matrix

Review disposition:

```text
OVERALL = REVISE_BEFORE_JOINT_STAGING
ADVERSARIAL_CHECKS = 11 PASS / 9 HOLD / 5 FAIL
GATE_DISPOSITION = 1 ACCEPT / 3 REVISE / 2 HOLD
CAN_WRITE_CANONICAL_TOP = NO
CAN_CLAIM_CLEARANCE_MOTION_STRENGTH = NO
```

The solar and arm artifacts are useful isolated layout evidence. They are not
yet mutually registerable in one `CS_S` staging assembly, and none of the
seven scenario names is presently a native, read-back-verified
configuration.

## Evidence reviewed

- User decision text for `V22-LAYOUT-AND-DEPLOYMENT-01`.
- Read-only `100_Mechanical_Continuation/design/interface_registry.yaml` and
  `configuration_policy.yaml`.
- Solar generator, contract, seven STEP files, 26-check validation summary,
  and twelve snapshots.
- ARM-STOW generator, interface registry, STEP, 12-check validation summary,
  selector checks, and four snapshots.
- Key reviewed hashes:
  - solar generator:
    `c69d0f7b41d5f141d8d95cb1326bf6e28191a4c558cc9aa68f35573d33abefb1`;
  - solar 0-degree STEP:
    `1a852c57ef8a6cfb047e27735c3f40a7d2067e25e50d7f4131aff61eabfe4109`;
  - solar 90-degree STEP:
    `efcdc4f3ac7ed0dede92bf65cff24789e120280bdebc5b3e82bac32fc75d04fe`;
  - ARM-STOW registry:
    `bf53e793ce66250dd507d5c6ef5ad269cdd342521c2100ce4a53ddc5fb5297ab`;
  - ARM-STOW STEP:
    `c4a74aed764e02639aa9c6e76cc5bd758fcc5787c52301a2f04adad0bd7e2913`.

## Adversarial check matrix

| ID | Result | Finding and counterexample |
|---|---:|---|
| `A01_SOLAR_AXIS_CONSTRUCTION` | **PASS** | Source constructs both sides about world-X axes at `Y=±110`, `Z=-105.65`; both stations use those same axes. This passes layout-axis construction only. |
| `A02_SOLAR_STOWED_WHOLE_RIG_Y_CONTAINMENT` | **PASS** | The 0-degree rig bounds stop at `Y=±113.15`; panel outer faces stop at `±113.0`. The pass includes proposal/reference solids, not future fasteners or purchased HDRM hardware. |
| `A03_SOLAR_STOWED_PANEL_Z_CONTAINMENT` | **PASS** | Panel span `Z=[-105.65,+94.35]` is inside the current `±113.15` platform envelope. |
| `A04_SOLAR_CELL_FACE_SIGN` | **PASS** | Signed checks support left `-Y` and right `+Y` in stow, and both `+Z` at 90 degrees. |
| `A05_HINGE_STATION_LEVER_ARM_GEOMETRY` | **PASS** | Station separation is `149.82 mm = 0.66×227 mm`, inside the proposed 60–75% band. This is not torsional-capacity proof. |
| `A06_SAMPLED_ROOT_PIVOT` | **PASS** | Sampled panel-root frames remain on `[-61,±110,-105.65]` at the checked poses. |
| `A07_CASSETTE_LOADPATH_INTENT` | **PASS** | Cassette spine and MID2 bracket geometry overlaps the lower-longeron/MID2 reference geometry, so a continuous *layout-intent* chain is visible. No real V2.2 joint is proved. |
| `A08_ARM_LOCAL_CROSSBEAM_CONTACTS` | **PASS** | Both local crossbeams span `211.30 mm`; twelve declared pad/web/bracket contacts have zero gap and positive in-plane overlap. |
| `A09_ARM_LOCAL_EQUIPMENT_ZONING` | **PASS** | All eight modeled equipment/radiator/sensor/antenna reservations remain at least `20 mm` outside the frozen `|Y|=40` corridor. These are envelopes, not devices. |
| `A10_PARTIAL_AND_SERVICE_FAIL_CLOSED` | **PASS** | `PARTIAL` remains angle `UNKNOWN`; `SERVICE` remains pending ratification. Neither is silently assigned a sampled pose. |
| `A11_AUTHORITY_BOUNDARY` | **PASS** | Both isolated models exclude mass, strength, stiffness, qualification, and native-configuration authority; accepted URDF authority is not duplicated. |
| `H01_HINGE_AND_PANEL_STRUCTURAL_CAPACITY` | **HOLD** | Pin, lug, doubler, bearing, stop, material, load, stiffness, mode, and tolerance data are absent. The 66% station ratio cannot establish torsional adequacy. |
| `H02_HDRM_LOAD_AND_RELEASE_PATH` | **HOLD** | Fixed/moving boxes are reservations. At stow they overlap by `1.5 mm` in Y (`105..106.5` versus `105..107` on the left, mirrored right), which may depict an interface but is not a device, release direction, preload, or shock path. |
| `H03_CONTINUOUS_SOLAR_SWEEP` | **HOLD** | The output is six superposed samples, not a fused continuous swept solid. A collision at, for example, 8 or 47 degrees can evade every sample. |
| `H04_CASSETTE_INTERNAL_VOLUME` | **HOLD** | The real side wall, internal equipment, tray, thermal path, and harness volume are absent; a reference overlap does not close cassette integration. |
| `H05_B601_Q0_AND_LOD1_CONTACT_AUTHORITY` | **HOLD** | ARM-STOW has `kinematic_authority=NONE`, contains no accepted-URDF transform chain, and cannot validate arm-shell contact or q0 placement. |
| `H06_REAL_TOP_DEVICE_INTEGRATION` | **HOLD** | Camera/FOV, antenna/RF keepout, radiator thermal allocation, harness, connectors, and actual device shapes are not instantiated. |
| `H07_NATIVE_CONFIGURATION_AND_MASS_READBACK` | **HOLD** | Static STEP cannot establish seven configurations, mutual exclusion, BOM exclusion, or mass-property readback. |
| `H08_ARM_SOLAR_CLEARANCE_SCENARIOS` | **HOLD** | No common-frame checks exist for stowed arm versus solar sweep, q0 versus deployed wing, PRE_CAPTURE, SERVICE, or gripper versus top devices. |
| `H09_FULL_STOWED_REPRESENTATION` | **HOLD** | Configuration policy calls for HIFI in `STOWED`, but B601 LOD1 remains unavailable. A solar-0 plus empty corridor is only a layout candidate. |
| `F01_DEPLOYED_TIP_INTERFACE` | **FAIL** | The generated endpoint is `|Y_tip|=110+200=310.00 mm`, not `313.15 mm`; delta is `-3.15 mm` (`-1.006%`). Exact legacy preservation and the inboard hinge cannot both be claimed with a 200 mm panel. |
| `F02_ARM_LOCAL_TO_CS_S_TRANSFORM` | **FAIL** | ARM-STOW declares only `LOCAL_LAYOUT_FRAME_ONLY`; it provides no numeric translation, rotation, or homogeneous transform into `CS_S`. “Longitudinal/forward” is not a signed axis mapping. Joint staging would require guessing. |
| `F03_ARM_SUPPORT_STATION_SEMANTICS` | **FAIL** | Existing interface registry assigns main saddle to `X=[40,90]` and wrist support to `[-150,-110]`. New ARM-STOW assigns saddle brackets to the aft range and wrist brackets to the forward range. This is an unapproved semantic inversion. |
| `F04_ARM_PHYSICAL_Y_PACKAGING` | **FAIL** | ARM-STOW physical pads reach `Y=±115.65`, exceeding the current platform half-width `113.15` by `2.50 mm` per side. The local validation did not test this platform-envelope relation. |
| `F05_ASYMMETRIC_FAILURE_POSES` | **FAIL** | The solar generator accepts one common angle and applies it bilaterally. It cannot generate `L_FAIL=(0,90)` or `R_FAIL=(90,0)` as separate state entries without source change. |

## Gate decisions

| Gate | Decision | What is accepted | Minimal repair to advance |
|---|---:|---|---|
| `SOLAR-LAYOUT-TRADE-01` | **ACCEPT** | Recessed lower book-fold is the V2.2 layout baseline; external hanging remains rejected; Z-fold remains a growth option. | Ratify either the new 310 mm tip or an authorised geometry change before treating endpoint as frozen. |
| `SOLAR-CASSETTE-01` | **REVISE** | Cassette/MID2/lower-longeron load-path *intent* is legible. | Bind the cassette to actual staging occurrences, add named joint/fastener interfaces, check internal-volume interference, and trace both HDRM reactions into primary structure. |
| `SOLAR-KINEMATIC-01` | **REVISE** | 0/5/15/30/60/90-degree rigid-body samples, hinge-axis sign, pivot, and cell-face orientation are usable diagnostic evidence. | Generate a continuous swept solid or bounded adaptive collision search; add independent left/right angles and explicit failure-state outputs. |
| `ARM-STOW-LAYOUT-02` | **REVISE** | Local crossbeam/contact and equipment-zoning geometry is useful. | Add signed numeric `T_CS_S_FROM_TOP_LAYOUT`; restore main-saddle/wrist station semantics or approve a deviation; keep all physical support geometry inside the authorised platform envelope; revalidate against actual upper-longeron occurrences. |
| `ARM-SOLAR-CLEARANCE-01` | **HOLD** | Nothing is accepted beyond preparation of inputs. | Complete common-frame staging, accepted-URDF q0/PRE_CAPTURE transforms, continuous solar sweep, and actual-device/envelope intersection tests. `SERVICE` stays out. |
| `LAYOUT-STAGING-ASSEMBLY-01` | **HOLD** | Isolated STEP artifacts may be referenced read-only. | Repair the three arm integration defects and asymmetric solar states, then build a new isolated staging top with representation mutual exclusion and machine-readable state provenance. |

## Local ARM frame ruling

`V22_TOP_LAYOUT_FRAME` is **not sufficient for joint staging**. A prose origin
and local axis names do not define a transform. Do not infer
`translation=[0,0,105.65]`: that value is plausible from longeron centres but
is not registered, and applying it would place local bracket tops at
`CS_S Z=133.65`, inconsistent with the earlier support envelope ending at
`Z=110.15`.

Required repair:

```text
T_CS_S_FROM_V22_TOP_LAYOUT:
  translation_mm: [tx, ty, tz]   # numeric and authority-tagged
  rotation_matrix: [[...],[...],[...]]
  axis_equivalence:
    local_+X: CS_S_+X_or_minusX
    local_+Y: CS_S_+Y
    local_+Z: CS_S_+Z
```

After ratification, transform every physical and non-physical bbox and rerun
containment/contact/intersection checks in `CS_S`.

## `310` versus `313.15 mm` ruling

The current geometry correctly proves an incompatibility. The preferred
minimal repair is an explicit interface decision:

1. If `≈313.15 mm` permits a 1.006% reduction, freeze the V2.2 endpoint at
   `310.00 mm` and record `313.15 mm` as retired legacy geometry.
2. If `313.15 mm` is exact, retain the inboard `|Y_hinge|=110 mm` axis and
   separately authorise a `203.15 mm` radial panel, followed by new packaging,
   power, mass, stiffness, and sweep checks.
3. Do not move the hinge to `113.15 mm`; that defeats the inboard-root intent.
4. Do not add a 3.15 mm offset link merely to preserve a display number; it
   adds mechanism and sweep cases without a requirement.

Until one choice is signed, endpoint status is `REVISE / DECISION_REQUIRED`,
not PASS.

## Seven-state geometry-binding ruling

No state is presently a native configuration. For the next isolated staging
iteration:

| State | Geometry-entry disposition |
|---|---|
| `STOWED` | `HOLD_FULL_STATE`; only a clearly named `STOWED_LAYOUT_CANDIDATE` may combine solar 0/0 with ARM-STOW reservations while B601 HIFI LOD1 is unavailable. |
| `DEPLOYED_NOMINAL` | Eligible for a separate geometry entry after common-frame/q0 repair: solar 90/90 plus accepted-URDF q0 proxy. |
| `DEPLOY_FAILED_BOTH` | Eligible after common-frame/q0 repair: solar 0/0 plus accepted-URDF q0 proxy. |
| `L_FAIL` | Eligible only after asymmetric generation: left 0/right 90 plus accepted-URDF q0 proxy. |
| `R_FAIL` | Eligible only after asymmetric generation: left 90/right 0 plus accepted-URDF q0 proxy. |
| `PARTIAL` | **No fixed geometry binding.** Angle remains `UNKNOWN`; sampled angles remain diagnostics only. |
| `SERVICE` | **No geometry binding.** Pending human ratification and access-sequence definition. |

`CAPTURE_SAFE`, although outside the seven-state list, also remains an unknown
candidate with no geometry binding.

## Required next repair order

1. Fix ARM station semantics, physical Y containment, and numeric `CS_S`
   transform.
2. Ratify 310.00 versus 313.15 mm.
3. Add independent left/right solar-angle generation and continuous-sweep
   evidence.
4. Build a new isolated joint staging assembly; do not write the canonical
   top.
5. Run arm–solar–device clearance gates using accepted URDF transforms.
6. Keep strength, stiffness, release reliability, mass, BOM, and flight
   qualification on HOLD until their own evidence gates exist.

