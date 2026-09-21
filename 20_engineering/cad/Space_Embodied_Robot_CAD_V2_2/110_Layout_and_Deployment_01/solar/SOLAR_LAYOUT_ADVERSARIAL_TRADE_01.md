# SOLAR-LAYOUT-TRADE-01 — Adversarial Review

## Decision

```text
BASELINE = RECESSED_LOWER_BOOK_FOLD
GROWTH_OPTION = TWO_PANEL_Z_FOLD
CURRENT_EXTERNAL_HANGING = REJECT_FOR_PACKAGING
PARTIAL_ANGLE = UNKNOWN
LEGACY_313_15_TIP_COMPATIBILITY = HOLD_INTERFACE_RATIFICATION
```

The ruling is a layout decision only. It is not a flight-mechanism release.

## Three-way trade matrix

| Criterion | External hanging/downward panel | Recessed lower book fold | Two-panel Z fold |
|---|---|---|---|
| Stowed Y packaging | Fails current physical envelope: panel outer surface reaches `119.15`, giving `238.3 > 226.3 mm` | Passes geometric test-rig target with panel surfaces at `|Y|<=113.0` | Can fit in principle, but requires a second stacked panel and inter-panel clearance not yet allocated |
| Stowed Z packaging | Existing concept descends to `Z=-200`, outside the platform bottom | Panel spans `Z=-105.65..+94.35`, inside `±113.15` | First panel can follow baseline; second-panel stack thickness and edge hardware are unresolved |
| Root load-path legibility | Existing root node is externally cantilevered and reaches the known `302.3 mm` mechanism-width lower bound | Cassette references connect the root to MID2 and lower-longeron references | Root can inherit baseline, but outer-panel loads add an inter-panel hinge and higher root moment |
| Mechanism count | One main hinge, but current geometry is not packaged | One main DOF per side, two separated hinge stations, two HDRM reservations | Adds an inter-panel hinge, latching, harness crossing, and likely deployment synchronisation |
| Failure-state observability | Poor while the root remains a display spine | Left/right sides are independent and six discrete samples expose early-release and mid-sweep geometry | More internal failure combinations than the existing formal state list represents |
| Cell protection | External cells may remain exposed depending on face choice | Cells face inward stowed and `+Z` at 90 degrees | Can protect cells, but stack face order and inter-panel rubbing clearance are unresolved |
| Mechanical-arm spatial separation | Downward panel is separate from the top arm but root protrusion remains wide | Deployment stays on the low plane around `Z=-105.65`, leaving the top-centre arm corridor conceptually separate | Similar final separation but larger multi-stage sweep and more collision cases |
| Area growth | Limited to one `227×200` panel per side | Same baseline area | Higher area potential |
| Evidence burden | Packaging already has a negative result | Bounded and testable now | Needs power requirement, second-panel dimensions, hinge law, harness and deployment sequencing |
| Ruling | **REJECT_FOR_PACKAGING** | **BASELINE_CONDITIONAL** | **GROWTH_OPTION_HOLD** |

## Proponent case for the baseline

1. A single rigid panel per side uses the smallest credible mechanism tree.
2. A fixed X-axis near the lower longeron moves the 90-degree wing into a low
   horizontal plane while preserving the top arm corridor.
3. Recessing the 6 mm panel moves the stowed outer surface from 119.15 mm to
   113.0 mm without reducing displayed panel thickness.
4. Two hinge stations separated by 66% of panel X length make the root support
   intent visible and avoid the earlier narrow central hinge cluster.
5. Two HDRM reservation stations near the panel X ends make the stowed
   constraint topology inspectable without claiming a device selection.

## Red-team challenge

1. The side-wall recess consumes internal volume and may interrupt structural
   skins, internal trays, thermal paths, and harness routes. The test rig has
   not proven that the bus can provide this cavity.
2. A hinge axis at `|Y|=110` cannot also give a 200 mm panel a
   `|Y_tip|=313.15` endpoint. The actual endpoint is 310 mm.
3. The 66% hinge separation is a geometry proposal only. No hinge load,
   panel torsion, or local bearing analysis supports it.
4. The model has no spring, damper, lock, sensor, or qualified HDRM product.
   Blocks labelled HDRM are only interface reservations.
5. The cell-face result is a rigid-body orientation check; it does not prove
   thermal suitability, illumination, contamination control, or deployment
   reliability.
6. The sampled sweep is not continuous collision certification. Inter-sample
   interference could remain.
7. The model does not include the B601 proxy, top equipment, deployment
   adapter, or full side-wall internal equipment. Arm–wing clearance therefore
   remains a downstream Gate 5 question.

## Verification response

- Challenges 1, 3, 4, 5, 6, and 7 remain `HOLD`/`UNKNOWN`; no wording upgrade is
  permitted from geometric generation alone.
- Challenge 2 is encoded as a machine-readable incompatibility:
  `actual_tip_abs_y_mm=310.0`,
  `legacy_tip_abs_y_mm=313.15`,
  `delta_mm=-3.15`.
- The baseline is accepted only for Gate 2–3 geometry construction and
  discrete kinematic testing.
- The Z-fold route is retained as an interface-growth option but is not
  instantiated, because no accepted power-area requirement authorises its
  additional mechanism.

## Gate ruling

```text
SOLAR-LAYOUT-TRADE-01 = PASS_BASELINE_SELECTED_WITH_HOLDS
SOLAR-CASSETTE-01 = PROCEED_GEOMETRY_ONLY
SOLAR-KINEMATIC-01 = PROCEED_DISCRETE_SAMPLES_ONLY
ARM_SOLAR_CLEARANCE = NOT_EVALUATED_IN_THIS_SUBTASK
STRENGTH_AND_RELEASE_RELIABILITY = NOT_EVALUATED
```

