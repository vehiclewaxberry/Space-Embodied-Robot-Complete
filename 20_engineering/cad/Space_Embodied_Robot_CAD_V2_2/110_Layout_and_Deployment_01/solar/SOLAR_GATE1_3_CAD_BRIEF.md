# V22-LAYOUT-AND-DEPLOYMENT-01 — Solar Gate 1–3 CAD Brief

## Task classification

- Model: bilateral recessed lower-plane book-deployment solar-array test rig.
- Task type: new isolated parametric assembly plus discrete kinematic verification poses.
- Scope: `SOLAR-LAYOUT-TRADE-01`, `SOLAR-CASSETTE-01`, and
  `SOLAR-KINEMATIC-01`.
- Units: millimetres and degrees.
- Output authority: layout and kinematic diagnostic geometry only.
- Excluded authority: mass, strength, stiffness, release reliability,
  manufacturability, thermal, electrical, and flight qualification.
- Native-CAD status: no SolidWorks/native assembly claim; STEP is primary.

## Coordinate convention

- Origin: spacecraft geometric centre.
- `+X`: rear toward task face.
- `+Y`: left solar-array direction.
- `+Z`: spacecraft top.
- MID2 reference plane: `X=-61`.
- Lower-longeron reference centres:
  `Y=±105.65`, `Z=-105.65`.
- Left and right hinge axes are parallel to world `+X`.

## Frozen input geometry

- Panel X span: `[-174.5, +52.5]`; X length `227`.
- Panel radial/height dimension: `200`.
- Panel thickness baseline: `6`.
- Platform external half-width: `113.15`.
- Stowed panel outer surfaces must satisfy `|Y|<=113.15`.
- Discrete verification samples: `0, 5, 15, 30, 60, 90 deg`.
- These samples do **not** define the formal `PARTIAL` state.
  `PARTIAL` remains angle `UNKNOWN`.
- Joint staging requires a bilateral shallow pocket in the isolated platform
  copy: `X=[-175,53]`, outer-side depth from `|Y|=106.5` to `113.15`, and
  `Z=[-111.65,94.35]`. Moving ears, local doublers and HDRM pads are kept on
  or outboard of the `|Y|=106.5` pocket datum. The retained inboard frame and
  longeron strip is layout evidence only; its strength and joint detail remain
  `HOLD`.

## Baseline proposal parameters

- Hinge-axis absolute Y: `110.0`.
- Hinge-axis Z: `-105.65`.
- Stowed panel Z span: `[-105.65, +94.35]`.
- Stowed panel Y spans:
  - left: `[+107.0, +113.0]`;
  - right: `[-113.0, -107.0]`.
- Hinge station separation ratio: `0.66 × 227 = 149.82`.
- Hinge station X coordinates:
  `-61 ± 74.91 = [-135.91, +13.91]`.
- The 60–75% station-separation band is a `DESIGN_PROPOSAL`, not an
  accepted hinge sizing or load-analysis result.
- HDRM interface-reservation stations: `X=-160` and `X=+40`.
  The solids are reservation envelopes, not invented purchased parts.

## Source-level kinematics

- Each panel rotates about its fixed world-X hinge line.
- Left panel angle is `-theta` about `+X`.
- Right panel angle is `+theta` about `+X`.
- At `theta=0`, the cell face is inward:
  - left cell normal `-Y`;
  - right cell normal `+Y`.
- At `theta=90 deg`, both cell normals are `+Z`.
- At `theta=90 deg`, the left panel extends toward `+Y` and the right panel
  extends toward `-Y`.

## Explicit packaging incompatibility

With a 200 mm panel and an inboard hinge axis at `|Y|=110`, the actual
90-degree tip is:

```text
/- (110 + 200) = +/-310 mm
```

It is therefore incompatible with simultaneously preserving the legacy
`|Y_tip|≈313.15 mm` value. Preserving `313.15 mm` would require one of:

1. moving the hinge axis to `|Y|=113.15`, outside the authorised
   `105.65–110 mm` inboard range;
2. adding a 3.15 mm radial offset/link mechanism; or
3. increasing panel radial length to 203.15 mm.

None is silently introduced. This brief freezes the honest baseline at
`|Y_tip|=310 mm` and records the legacy-tip requirement as
`HOLD_INTERFACE_RATIFICATION`.

## Fixed test-rig references

- MID2 lower crossmember reference.
- Left/right lower-longeron reference bars.
- Left/right recessed cassette backplanes and perimeter/load-path members.
- MID2-to-cassette bracket references.
- Dual fixed hinge clevis ears and X-axis pins per side.
- Fixed stop proposals and two HDRM fixed-end reservation envelopes per side.

All these are load-path/reference intent only. Their cross-sections, fasteners,
materials, tolerances, and purchased hardware are not specified.

## Moving test-rig geometry

- One panel sandwich per side.
- One inward cell-face witness per side.
- Two moving hinge lugs/doublers per side.
- Two HDRM moving-pad reservation envelopes per side.
- Perimeter back-frame witness strips.

## Output paths

- Generator: `solar_deployment_test_rig.py`.
- Pose STEP files:
  - `solar_deployment_pose_000deg.step`
  - `solar_deployment_pose_005deg.step`
  - `solar_deployment_pose_015deg.step`
  - `solar_deployment_pose_030deg.step`
  - `solar_deployment_pose_060deg.step`
  - `solar_deployment_pose_090deg.step`
- Multi-pose diagnostic:
  `solar_deployment_sweep_samples.step`.
- Validation: `validation/`.
- Snapshots: `snapshots/`.

## Validation targets

- Every STEP reopens and reports closed positive-volume solids.
- Panel X span remains exactly 227 mm at every pose.
- Stowed left/right panel outer surfaces remain within `|Y|<=113.15`.
- The actual 90-degree radial tip is `|Y|=310`, not 313.15.
- Hinge pins have their long dimension along X.
- Left/right symmetry is retained at each sample.
- Cell faces are inward at 0 degrees and on the +Z side at 90 degrees.
- Source asserts the 0.66 hinge-station separation ratio is inside the
  proposal-only 0.60–0.75 band.
- `refs --facts --planes --positioning`, targeted `measure`, targeted `frame`,
  and saved snapshots are required before Gate 3 is reported.

## Claim limits

This model does not establish:

- hinge-pin size, bearing selection, preload, spring torque, or stop load;
- HDRM product selection, release direction qualification, or redundancy;
- panel stiffness, mode frequency, thermal distortion, or cell survivability;
- harness bend radius, electrical continuity, grounding, or EMC;
- bus internal-volume compatibility behind the recessed cassette;
- arm–solar dynamic clearance or formal seven-state configuration closure.
