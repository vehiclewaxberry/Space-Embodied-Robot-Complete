# V22-LAYOUT-AND-DEPLOYMENT-01 final gate report

## Final disposition

```text
OVERALL = ACCEPT_ISOLATED_STAGING_WITH_ENGINEERING_HOLDS
PRODUCER_VALIDATION = 12 PASS / 5 HOLD / 0 FAIL
INDEPENDENT_ADVERSARIAL = 20 PASS / 9 HOLD / 0 FAIL
ORIGINAL_BLOCKING_FAILS = 5 CLOSED / 0 OPEN
SIX_GATES = 5 ACCEPT / 0 REVISE / 1 HOLD
CANONICAL_V2_2_TOP_WRITE = NO
```

The next spacecraft mechanical-design baseline is now an isolated, traceable
STEP-first staging package. It freezes a recessed lower book-fold solar-array
layout, a top longitudinal B601 stow corridor with two support bridges, a
solar-first/B601-release-second sequence, five geometry state entrypoints and
two deliberately unbound manifest states.

Acceptance is limited to layout and the explicitly represented diagnostic
scope. It is not structural release, global collision release, release
reliability, HIFI B601 completion, native SolidWorks configuration, BOM,
STEP-derived mass, or flight qualification.

## Selected mechanical architecture

- Spacecraft frame: `+X` toward the task face, `+Y` port/left, `+Z` top.
- Solar baseline: bilateral recessed lower book-fold cassettes about X-axis
  hinges at `Y=+/-110 mm`.
- Solar panel: `227 x 200 x 6 mm`; actual 90-degree endpoint
  `|Y|=310.00 mm`.
- Legacy `313.15 mm` endpoint: retired for this isolated staging only;
  controlling interface ratification remains HOLD.
- B601 stow: top longitudinal `|Y|<=40 mm` corridor.
- Main saddle: forward support region `X=[40,90] mm`.
- Wrist support: aft support region `X=[-150,-110] mm`.
- Local top-layout to `CS_S`: identity rotation and translation
  `[0,0,119.15] mm`; interface ratification remains HOLD.
- Deployment order: solar release/deploy and confirmation first, B601 release
  second.

## Six-gate ruling

| Gate | Decision | Boundary |
|---|---:|---|
| `SOLAR-LAYOUT-TRADE-01` | ACCEPT | Recessed book-fold selected for isolated staging at 310 mm; interface ratification HOLD. |
| `SOLAR-CASSETTE-01` | HOLD | Pocket/load-path intent exists; residual section, internal volume, joint and tolerance closure absent. |
| `SOLAR-KINEMATIC-01` | ACCEPT | Discrete, asymmetric and scoped rigid-body diagnostics accepted; global platform clearance and mechanism reliability HOLD. |
| `ARM-STOW-LAYOUT-02` | ACCEPT | Correct station semantics, Y containment and numeric `CS_S` placement accepted as layout; attachment/structure/contact qualification HOLD. |
| `ARM-SOLAR-CLEARANCE-01` | ACCEPT | Scoped solar-to-support and solar-to-q0 proxy bounds accepted; PRE_CAPTURE, SERVICE and global collision HOLD. |
| `LAYOUT-STAGING-ASSEMBLY-01` | ACCEPT | Five isolated STEP scenes plus two null-bound manifest states accepted; native configuration/BOM/mass integration not authorised. |

## Seven-state contract

| State | Solar L/R | B601 representation | Geometry binding | Status |
|---|---:|---|---|---|
| `STOWED` | `0/0` | HIFI required but unavailable; q0 not substituted | `staging/state_STOWED_HOLD_B601_HIFI.step` | HOLD |
| `DEPLOYED_NOMINAL` | `90/90` | q0 conservative proxy | `staging/state_DEPLOYED_NOMINAL_Q0.step` | diagnostic |
| `DEPLOY_FAILED_BOTH` | `0/0` | q0 conservative proxy | `staging/state_DEPLOY_FAILED_BOTH_Q0.step` | diagnostic |
| `L_FAIL` | `0/90` | q0 conservative proxy | `staging/state_L_FAIL_Q0.step` | diagnostic |
| `R_FAIL` | `90/0` | q0 conservative proxy | `staging/state_R_FAIL_Q0.step` | diagnostic |
| `PARTIAL` | unknown | pending pose definition | none | UNKNOWN/HOLD |
| `SERVICE` | pending ratification | pending human ratification | none | HOLD |

The `0/5/15/30/60/90 deg` solar samples are diagnostic samples and do not
define `PARTIAL`.

## Current artifact locks

| Artifact | SHA-256 |
|---|---|
| Primary isolated staging STEP | `6856f339aa9e4925cbb619e8da5793e3c77b1fed732b41f517163fd186b6f426` |
| ARM-STOW STEP | `539dae5b45e179a8aa5390f32b91fbb5cc7d2af32de11ce4965535ad35878362` |
| Solar sampled-sweep STEP | `23610932784a48cc5b7f5edc724209eb36433ccca91772efa52f82a84473be3b` |
| `STOWED` STEP | `04914c3148fc81fd43919b5b8a64c5f6a53a063f0d6857ecac6ceea5dd8db6c6` |
| `DEPLOYED_NOMINAL` STEP | `2b4a604da391ea0fb2e95d359ea6e9e5dc20eade2c9db7e6d55b8be62cea5b4e` |
| `DEPLOY_FAILED_BOTH` STEP | `2ea2c09187e5924cfbbbf4a049c5b46eb8a9ccbfd92a1ee5d68511dbb53cb6b6` |
| `L_FAIL` STEP | `3fd42f9c0a1936fc26e344c3848aeccbd79debd404b8cf4cf8facc573ffb6ba4` |
| `R_FAIL` STEP | `bbd846b761f7725e61a5fa45babccbdac046fa8a3c3a95d75fdb4737d07850b0` |
| Joint validation JSON | `18a24b5c58eccb1f9d70f2aa6df38b16a6da948adb13d0ec3861499e436b40ee` |
| Final adversarial JSON | `92692b597f9ec2828bdaad13e2d584a9c97a9b0e3842c462eed15a02a6abb385` |

The joint validator also passed the current solar-contract and ARM-interface
contract hash lock. Accepted baselines remain unchanged:

- canonical V2.2 top:
  `3b55edb85b460ecbc23eec55b99ff83506c33e0f4cecdb0375babc7b0d50cfb9`;
- prior mechanical-continuation STEP:
  `c844c07177daf7e7b96d332d5060cfcbffe2c5989ded04602f9ec0dffd7c4b42`;
- accepted B601 URDF:
  `1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164`;
- q0 box evidence:
  `fe16f3b8460574c281351e22f97e51843bac918608443ef91041b6194aff2d8b`.

The accepted URDF remains the sole mass authority at
`4.695555949342986 kg`; STEP mass is excluded.

## Deterministic findings

- ARM-STOW: `15 PASS / 0 FAIL`; repaired Y extent is exactly
  `[-113.15,+113.15] mm`, the centered corridor is `80 mm` wide, and all
  12 declared physical support contacts have zero geometric gap with positive
  face overlap.
- Solar: `26 PASS / 0 FAIL`; current per-pose topology is
  67 occurrences, 61 leaf occurrences and 65 shapes; independent left/right
  angles produce distinct `L_FAIL` and `R_FAIL` scenes.
- The original pre-pocket stowed conflict is retained as negative evidence:
  44 positive-volume pairs, 22 per side.
- The isolated pocket repair removes the represented moving-panel
  interpenetrations at 0 degrees. It leaves only `8.35 mm` of the nominal
  15 mm outer member, so structure/stiffness/tolerance remain HOLD.
- Fifty cassette/primary overlaps remain as load-path intent or possible
  interference, not qualified joints.
- Represented solar versus physical arm supports has a scoped continuous lower
  bound of `17.03258 mm`.
- Represented solar versus q0 conservative proxies has a scoped continuous
  lower bound of `131.18890 mm`.
- Solar versus revised primary structure reaches zero sampled distance at
  0 degrees; global continuous platform clearance therefore remains HOLD.
- The legacy top star-tracker conflict is preserved as a non-physical
  `5625 mm3` witness. Its side relocation still needs FOV, mount and harness
  closure.

## Adversarial repair closure

The independent review first found five blocking failures. All five were
closed without rewriting the canonical top:

1. 310 versus 313.15 mm was converted into an explicit staging decision and
   interface HOLD.
2. The missing top-layout-to-`CS_S` transform was made numeric.
3. Main-saddle and wrist stations were restored to forward/aft semantics.
4. Physical pads were brought within `|Y|<=113.15 mm`.
5. Independent left/right solar angles and asymmetric state STEP files were
   generated.

The review also exposed stale evidence reuse. The solar CAD CLI validator now
regenerates every selector record instead of reusing results merely because
the command text is unchanged. Current STEP hashes, selector evidence,
machine summaries and reports are synchronized.

## Remaining next gate

The controlling next gate is `SOLAR-CASSETTE-STRUCTURE-02`, not further
exterior-detail growth. It must close:

- a real cassette-to-primary joint model and fastener/bonded-interface
  definition;
- material, launch/service load cases and load-path boundary conditions;
- section, stiffness, buckling, fatigue and tolerance checks for the
  `8.35 mm` residual member;
- internal-volume, HDRM, hinge/stop/latch and harness compatibility;
- a positive qualified platform-clearance allowance.

Only after that gate should accepted PRE_CAPTURE/SERVICE joint vectors,
real-device envelopes and wider collision claims be introduced.

## Viewer and visual evidence

The documented `agent:start` script is absent from the installed CAD Viewer
package, but its provided `serve` runtime is active. Directory activation and
the catalog entry for `layout_staging.step` both returned HTTP 200:

`http://127.0.0.1:4178/?dir=F%3A%2FChina%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition%2F20_engineering%2Fcad%2FSpace_Embodied_Robot_CAD_V2_2%2F110_Layout_and_Deployment_01%2Fstaging&file=layout_staging.step`

The governing visual packet is recorded in
`validation/snapshot_review_postrepair.md`; screenshots are visual
legibility evidence only.
