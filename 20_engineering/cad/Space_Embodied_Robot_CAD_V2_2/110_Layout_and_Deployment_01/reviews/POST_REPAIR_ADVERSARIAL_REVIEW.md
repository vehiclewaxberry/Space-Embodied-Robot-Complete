# V22-LAYOUT-AND-DEPLOYMENT-01 post-repair adversarial review

Independent disposition:

```text
OVERALL = ACCEPT_ISOLATED_STAGING_WITH_ENGINEERING_HOLDS
ORIGINAL_5_FAILS = 5 CLOSED / 0 OPEN
ADVERSARIAL_CHECKS = 20 PASS / 9 HOLD / 0 FAIL
SIX_GATES = 5 ACCEPT / 0 REVISE / 1 HOLD
CANONICAL_TOP_WRITE = NO
STRUCTURAL_RELEASE = NO
GLOBAL_COLLISION_RELEASE = NO
NATIVE_CONFIGURATION_RELEASE = NO
```

This acceptance is limited to an isolated STEP-first layout staging package,
five diagnostic geometry entrypoints, and two manifest-only state
entrypoints. It is not a flight-mechanism, structural, global-clearance, mass,
BOM, or native SolidWorks release.

## Current evidence set reviewed

- Current source:
  - `staging/layout_staging.py`;
  - `solar/solar_deployment_test_rig.py`;
  - `arm_stow/arm_stow_layout.py`.
- Current contracts:
  - `design/layout_decision_contract.json`;
  - `design/state_policy.json`;
  - `solar/solar_deployment_contract.json`;
  - `arm_stow/interface_claim_registry.json`.
- Current STEP:
  - primary `staging/layout_staging.step`;
  - all five `state_*.step` entrypoints;
  - repaired ARM-STOW STEP;
  - repaired solar sampled-sweep STEP.
- Current machine evidence:
  - `validation/staging_validation.json`, producer tally
    `12 PASS / 5 HOLD / 0 FAIL`, SHA-256
    `18a24b5c58eccb1f9d70f2aa6df38b16a6da948adb13d0ec3861499e436b40ee`;
  - `CURRENT_SUBSYSTEM_CONTRACT_HASH_LOCK = PASS`: the layout-decision
    contract's expected solar hash `a35cef0a...` and ARM-STOW hash
    `5be0bfad...` each equal the current artifact hash;
  - repaired ARM-STOW evidence, `15 PASS / 0 FAIL`;
  - repaired solar evidence, `26 PASS / 0 FAIL`.
- Latest post-repair snapshot packet stamped `20260726T142704Z`.
- Read-only accepted baseline hashes.

Current key hashes:

| Artifact | SHA-256 |
|---|---|
| Canonical V2.2 top | `3b55edb85b460ecbc23eec55b99ff83506c33e0f4cecdb0375babc7b0d50cfb9` |
| Prior mechanical continuation STEP | `c844c07177daf7e7b96d332d5060cfcbffe2c5989ded04602f9ec0dffd7c4b42` |
| Accepted B601 URDF | `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164` |
| q0 conservative-box evidence | `fe16f3b8460574c281351e22f97e51843bac918608443ef91041b6194aff2d8b` |
| Solar contract | `a35cef0a358b56fd32b5fcb63d3cefa2aa9ea988d1f812d48ca57b8aece371f6` |
| ARM-STOW contract | `5be0bfad416af6ebece0744b43f6abb99a44da1afe1f649e7ee3eb49e2cd74c4` |
| ARM-STOW STEP | `539dae5b45e179a8aa5390f32b91fbb5cc7d2af32de11ce4965535ad35878362` |
| Solar sampled-sweep STEP | `23610932784a48cc5b7f5edc724209eb36433ccca91772efa52f82a84473be3b` |
| Primary staging STEP | `6856f339aa9e4925cbb619e8da5793e3c77b1fed732b41f517163fd186b6f426` |

The current layout-decision contract records the current solar and ARM
contract hashes. The repaired ARM Markdown, JSON selector evidence, machine
validation and STEP all agree on hash `539dae...`, width `226.3 mm`, and
main-saddle-to-forward-crossbeam placement.

## Closure of the original five FAILs

| Original failure | Post-repair result | Evidence-backed ruling |
|---|---:|---|
| `F01_DEPLOYED_TIP_INTERFACE` | **CLOSED** | The staging contract explicitly selects the physically generated `310.00 mm` endpoint and retires `313.15 mm` for isolated staging. Interface ratification remains HOLD; the value is no longer misrepresented as preserved. |
| `F02_ARM_LOCAL_TO_CS_S_TRANSFORM` | **CLOSED** | The current contract defines identity rotation and `T=[0,0,119.15] mm`; all four local pad lower faces map to `CS_S Z=113.15 mm`. This is accepted for isolated staging only and remains interface-ratification HOLD. |
| `F03_ARM_SUPPORT_STATION_SEMANTICS` | **CLOSED** | Main-saddle brackets are now in the forward range (`X=[51,79]` inside `[40,90]`); wrist brackets are aft (`X=[-144,-116]` inside `[-150,-110]`). Selector alignment `#o1.1.11.f5 -> #o1.1.1.f6` is zero-translation against the forward crossbeam. |
| `F04_ARM_PHYSICAL_Y_PACKAGING` | **CLOSED** | Maximum physical ARM-STOW `|Y|` is now exactly `113.15 mm`; the repaired STEP bounds are `Y=[-113.15,+113.15]`. |
| `F05_ASYMMETRIC_FAILURE_POSES` | **CLOSED** | Separate state STEP labels and bounds substantiate `L_FAIL=(0,90)` and `R_FAIL=(90,0)`. The two top-view snapshots show opposite deployed sides. |

Closure means the prior blocking counterexample no longer applies. It does
not upgrade the associated interfaces or mechanism to flight authority.

## Independent check matrix

| ID | Status | Adversarial finding |
|---|---:|---|
| `P01_ACCEPTED_BASELINE_HASHES` | **PASS** | Canonical top, prior continuation STEP, accepted URDF and q0 evidence all match their registered hashes. |
| `P02_COMPOSED_CONTRACT_HASH_LOCK` | **PASS** | Current solar and ARM contract hashes match the current layout-decision source lock. |
| `P03_ARM_STEP_EVIDENCE_SYNC` | **PASS** | ARM STEP, validation JSON, selector JSON and Markdown agree on hash `539dae...`, 150 positive-volume solids and `Y=±113.15`. |
| `P04_SOLAR_STEP_EVIDENCE_SYNC` | **PASS** | Solar sampled-sweep hash `236109...` matches the repaired validation summary; producer result is `26 PASS / 0 FAIL`. |
| `P05_310_MM_DECISION_EXPLICIT` | **PASS** | `310.00 mm` is the only selected staging endpoint; `313.15 mm` is not silently claimed. |
| `P06_NUMERIC_CS_S_MAPPING` | **PASS** | Signed axes, identity rotation and translation `[0,0,119.15]` are machine readable and pad placement is numerically checked. |
| `P07_ARM_STATION_SEMANTICS` | **PASS** | Main saddle is forward and wrist is aft in source, contract and selector evidence. |
| `P08_ARM_Y_CONTAINMENT` | **PASS** | All physical pads and the complete repaired ARM STEP stay within the current `226.3 mm` Y package. |
| `P09_ASYMMETRIC_SOLAR_GENERATION` | **PASS** | Independent left/right angles and distinct L/R failure STEP entrypoints exist. |
| `P10_FIVE_STEP_ENTRYPOINTS_REOPEN` | **PASS** | STOWED, DEPLOYED_NOMINAL, DEPLOY_FAILED_BOTH, L_FAIL and R_FAIL reopen with 280 or 290 positive-volume solids. |
| `P11_STATE_REPRESENTATION_FAIL_CLOSED` | **PASS** | STOWED contains no substituted q0 arm and is labelled HIFI-absent; the other four geometry states contain the q0 conservative proxy and no HIFI representation. |
| `P12_PARTIAL_SERVICE_NO_BINDING` | **PASS** | `PARTIAL` and `SERVICE` have null bindings and no corresponding STEP files; diagnostic angles do not define PARTIAL. |
| `P13_STOWED_POCKET_IDEAL_GEOMETRY` | **PASS** | At 0 degrees the represented moving solar groups have no positive-volume intersection with the revised primary structure. This is ideal-geometry evidence only. |
| `P14_NEGATIVE_INPUT_PRESERVED` | **PASS** | The pre-pocket model still reproduces 44 positive intersection pairs, 22 per side; the repair did not erase the negative input result. |
| `P15_ARM_SUPPORT_CONTINUOUS_LOWER_BOUND` | **PASS** | For represented rigid solar geometry versus listed physical ARM supports, the 1-degree grid minimum `18.7781 mm` minus the `1.74553 mm` motion bound gives `17.03258 mm > 0`, bilaterally. |
| `P16_Q0_CONTINUOUS_LOWER_BOUND` | **PASS** | For represented rigid solar geometry versus accepted-URDF-derived q0 AABB proxies, the scoped continuous lower bound is `131.18890 mm`, bilaterally. |
| `P17_LIPSCHITZ_BOUND_FORM` | **PASS** | With maximum radius `200.02250 mm` and maximum unsampled angle `0.5 deg`, `R*delta_theta=1.74553 mm` is a conservative rigid-rotation displacement bound for the represented set. |
| `P18_STAR_TRACKER_CONFLICT_WITNESS` | **PASS** | The old top-centre star-tracker envelope remains a non-physical conflict witness intersecting the aft crossbeam by exactly `5625 mm3`; it is not hidden as a successful relocation. |
| `P19_LATEST_SNAPSHOT_SEMANTICS` | **PASS** | Latest opposed staging views, STOWED view and L/R failure top views agree with the named scene semantics; no visual claim is used as structural or clearance proof. |
| `P20_AUTHORITY_EXCLUSIONS` | **PASS** | STEP mass is excluded; accepted URDF mass remains `4.695555949342986 kg`; strength, stiffness, reliability, native configuration, BOM and flight qualification are explicitly excluded. |
| `H01_310_MM_INTERFACE_RATIFICATION` | **HOLD** | `310.00 mm` is selected only for isolated staging. A controlling spacecraft-interface ratification has not frozen it. |
| `H02_TOP_SUPPORT_INTERFACE` | **HOLD** | The `119.15 mm` translation establishes placement, not fasteners, insert geometry, local pressure, stiffness or load transfer into upper longerons. |
| `H03_POCKET_RESIDUAL_SECTION` | **HOLD** | The shallow pocket removes `6.65 mm` from a nominal `15 mm` outer member, leaving `8.35 mm`. Positive residual geometry is not strength, stiffness, buckling, fatigue or tolerance proof. |
| `H04_CASSETTE_EMBEDDED_OVERLAPS` | **HOLD** | The reported 50 positive overlaps comprise 44 against other staged primary solids and 6 against non-physical pocket datums; volumes range from `0.5625` to `20430 mm3`. Boolean overlap may express load-path intent or interference, but not a joint. |
| `H05_SOLAR_VERSUS_PRIMARY_CONTINUOUS_CLEARANCE` | **HOLD** | The integer grid finds no sampled interpenetration but reaches zero distance at 0 degrees. No positive global continuous lower bound or qualified tolerance exists. |
| `H06_HDRM_RELEASE_AND_HARNESS` | **HOLD** | HDRM selection, preload, release direction, shock path, latching, spring/stop loads and harness flex remain undefined. |
| `H07_PRE_CAPTURE_SERVICE_AND_GLOBAL_COLLISION` | **HOLD** | PRE_CAPTURE and SERVICE have no accepted joint vectors. No global arm workspace, full device set, flexible-body motion or service-access clearance was evaluated. |
| `H08_NATIVE_CONFIGURATION_BOM_MASS` | **HOLD** | Five separate STEP scenes are not SolidWorks configurations; there is no suppression, mate, BOM-exclusion or mass-property readback. |
| `H09_HIFI_CONTACT_DEVICE_AND_FLIGHT_CLOSURE` | **HOLD** | B601 HIFI/contact faces, actual top devices, FOV/RF/thermal/harness integration, manufacturing and flight qualification remain open. |

Independent tally: `20 PASS / 9 HOLD / 0 FAIL`.

## Shallow-pocket and load-path challenge

The pocket is an honest geometric repair, but its clearances are not an
engineering allowance:

- pocket X bounds exceed the panel by only `0.5 mm` at each end;
- the panel solid has `0.5 mm` nominal inboard Y margin;
- the cell witness has only `0.1 mm` nominal inboard Y margin;
- some root/top boundaries are coincident, producing the observed zero
  distance.

The `8.35 mm` residual width is one derived cross-section result; the model
does not prove minimum section over every cut member or structural
connectivity after subtraction. Likewise, the 50 overlap records are not 50
qualified attachments. Six involve non-physical datum witnesses, and all
remaining intersections still lack fastener, weld, bonded-joint, contact,
material and load definitions.

Therefore:

```text
POCKET_GEOMETRY = ACCEPT_LAYOUT_ONLY
CASSETTE_LOADPATH_INTENT = PRESENT
CASSETTE_STRUCTURAL_CLOSURE = HOLD
```

## Continuous-bound challenge

The 1-degree plus Lipschitz argument is valid for the represented rigid moving
solar group against the exact listed static proxy sets:

```text
d_continuous >= d_grid_min - R * 0.5deg_in_radians
```

It supports the two scoped positive lower bounds reported above. It does not
cover:

- revised primary structure, whose sampled minimum is zero;
- manufacturing and joint tolerances;
- hinge-axis error, panel flexibility, modal response or latch rebound;
- uninstantiated devices, harness loops, HDRM release hardware or B601 HIFI;
- PRE_CAPTURE, SERVICE or arbitrary arm workspace.

Thus the scoped arm-support and q0 checks pass, while global continuous
collision clearance remains HOLD.

## Seven-state ruling

| State | Post-repair ruling |
|---|---|
| `STOWED` | **Geometry entry exists, status HOLD.** It represents solar 0/0 and physical support layout but intentionally contains no q0 substitute and no unavailable HIFI arm. |
| `DEPLOYED_NOMINAL` | **Diagnostic geometry entry accepted:** solar 90/90 plus q0 conservative proxy. |
| `DEPLOY_FAILED_BOTH` | **Diagnostic geometry entry accepted:** solar 0/0 plus q0 conservative proxy. |
| `L_FAIL` | **Diagnostic geometry entry accepted:** left 0/right 90 plus q0 conservative proxy. |
| `R_FAIL` | **Diagnostic geometry entry accepted:** left 90/right 0 plus q0 conservative proxy. |
| `PARTIAL` | **Manifest only; no geometry binding.** Angle remains UNKNOWN. |
| `SERVICE` | **Manifest only; no geometry binding.** Human ratification and access sequence remain absent. |

These are five files plus two manifest-only entries, not seven native
SolidWorks configurations.

## Six-gate final decision

| Gate | Decision | Exact release boundary |
|---|---:|---|
| `SOLAR-LAYOUT-TRADE-01` | **ACCEPT** | Recessed lower book-fold is accepted for isolated staging at the actual 310 mm endpoint; controlling interface ratification remains HOLD. |
| `SOLAR-CASSETTE-01` | **HOLD** | Pocket and embedded overlap evidence establish layout/load-path intent only; residual-section, internal-volume, joint and tolerance closure are absent. |
| `SOLAR-KINEMATIC-01` | **ACCEPT** | Discrete, asymmetric and scoped rigid-body continuous-bound diagnostics are accepted. Global solar-to-platform clearance and mechanism reliability remain HOLD. |
| `ARM-STOW-LAYOUT-02` | **ACCEPT** | Corrected stations, platform Y containment and explicit CS_S staging placement are accepted as layout. Structure, attachment and contact qualification remain HOLD. |
| `ARM-SOLAR-CLEARANCE-01` | **ACCEPT** | Accepted only for represented solar versus physical support and q0 proxy sets under the stated rigid-body bound. PRE_CAPTURE, SERVICE and global collision remain HOLD. |
| `LAYOUT-STAGING-ASSEMBLY-01` | **ACCEPT** | Five isolated STEP entrypoints plus two null-bound manifest entries are accepted. Native configurations, BOM, mass and canonical-top integration remain HOLD/not authorised. |

Gate tally: `5 ACCEPT / 0 REVISE / 1 HOLD`.

## Final adversarial verdict

The repair is sufficient to continue into the next isolated mechanical-design
iteration. It is not sufficient to:

- release cassette or top-support structure;
- claim a flight-clear deployment mechanism;
- claim arbitrary arm/solar/device collision safety;
- define PARTIAL, PRE_CAPTURE or SERVICE geometry;
- claim native SolidWorks configuration, BOM or mass closure;
- write the canonical V2.2 top.

The next evidence gate should address pocket/cassette structural and tolerance
closure, then add accepted PRE_CAPTURE geometry and real-device integration
before expanding the collision claim.
