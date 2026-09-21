# V22 mechanical continuation CAD brief

## Scope and authority

- Model: `V22_MECHANICAL_CONTINUATION`, a new labeled integration assembly.
- Task type: isolated STEP-first assembly; no edit or insertion into the canonical V2.2 top assembly.
- Units: millimetres.
- Source of numeric values: the frozen values stated in decision `V22_B601_CONTINUE_01` and the current `automation/b5_build_spec.yaml`.
- Geometry authority: this model is a mechanical-integration design continuation. It does not replace the registered B601 vendor STEP, accepted URDF, mass properties, BOM, or any released native SolidWorks model.
- Kinematic authority: none.
- Mass authority: excluded.
- Structural claim: load-path intent only. No strength, stiffness, launch-load, fatigue, release-shock, manufacturability, or tolerance claim.

## Coordinate convention

- Assembly frame: `CS_S`.
- Origin: centre of the service-vehicle bus.
- `+X`: rear-to-task direction.
- `+Y`: left solar-array side.
- `+Z`: spacecraft top.
- Task face: `X = +183.0`.
- B601 mounting datum / outer adapter face: `X = +198.0`.
- MID1 and MID2 frame centres: `X = +61.0` and `X = -61.0`.

## Required functional content

### `B601-ICD-01`

- Frozen project interface plate: `160 × 160 × 12`.
- Frozen central interface: `Ø100`, axis parallel to `X`.
- Mating datum and nominal tool/removal direction: `+X`.
- Current source display envelopes:
  - adapter ring: `X=[183,198]`, `OD=180`, `ID=100`;
  - connector reserved opening: `Ø18`, centred at `Y=70, Z=0`;
  - harness passage: `Ø30`, centred at `Y=55, Z=0`.
- The `Ø18` connector reservation and `Ø30` harness passage are offset by
  `15 mm` in `Y`. Their existence does **not** prove a continuous cable path;
  routing, bend radius, strain relief, and connector backshell clearance remain
  `UNKNOWN`.
- Bolt quantity, bolt diameter/thread, bolt circle, locating-pin diameter, pin tolerance, connector model, grounding, thermal interface, launch load, and interface stiffness remain `TBD/HOLD` or `UNKNOWN`. No authoritative holes or pins are generated.

### `B601-MOUNT-01`

- Labeled load-path chain:
  `B601 base → adapter → 160×160 plate → front spreader → four proposal ribs/gussets → four longerons → MID1/MID2 frames`.
- Frame and longeron coordinates come directly from `b5_build_spec.yaml`.
- Four straight bridge webs are modeled at `X=[171,183]`: `±Y` webs run
  from `|Y|=80` to `98.15` with `Z=±7.5`, and `±Z` webs run from
  `|Z|=80` to `98.15` with `Y=±7.5`. They are staging-only
  `DESIGN_PROPOSAL` closures with fasteners and joints `TBD/HOLD`.
- Separate diagonal corner spreader ribs are explicit `DESIGN_PROPOSAL`
  geometry because their section dimensions are not frozen.

### `ARM-STOW-01`

- Main-arm saddle source envelope:
  `X=[40,90], Y=[-30,30], Z=[88,110.15]`.
- Wrist/gripper soft-support source envelope:
  `X=[-150,-110], Y=[-30,30], Z=[88,110.15]`.
- Support-pad thickness, relief dimensions, and arm HDRM reservation blocks are explicit `DESIGN_PROPOSAL`.
- Contact faces are candidates pending B601 LOD1. The model does not assert that the vendor shell is load-capable.

### `SOLAR-ROOT-01`

- Bilateral source geometry follows the current B5 values:
  root base `X=[-79,-43]`, bus-side start `|Y|=113.15`, outward depth `8`, `Z=[-40,40]`;
  two ear stations `X=[-75,-65]` and `[-57,-47]`;
  hinge source envelopes `pin Ø8×24`, spring `Ø16×18`;
  HDRM source envelopes `24×24×8` bases, `Ø10×20` rods at `X=-160,40`;
  hard-stop source envelope `14` square with `8` thickness.
- Pin diameter and all release-mechanism details remain source-display proposals and are not signed hardware.
- Harness loop/tube size and bend radius are explicit `DESIGN_PROPOSAL`.
- Bilateral staging-only `ROOT_NODE_SPINE_L/R` plates bridge the current
  root/node-pad gap at `X=[-67,-55]`, `Z=[-75,75]`,
  `Y=[110.15,121.15]` (mirrored on the right). They are deliberately
  embedded proposal solids; fasteners and joints remain `TBD/HOLD`.

### `FIDELITY-01A_PLATFORM`

- Bus frames, decks, four longerons, split exterior panels, and node/load-path features are labeled.
- Stowed wing panels use the current B5 envelope:
  `X=[-174.5,52.5]`, `|Y|=[113.15,119.15]`, `Z=[-200,0]`.
- Wing border width `6` and solar-cell-zone inset `10` use current B5 values.
- Panel skin thickness, panel seam gaps, access-cover sizes, fastener markers, visual-window depth, and any nozzle exit diameter are explicit `DESIGN_PROPOSAL`.
- Existing B5 envelope values are used for camera/antenna/radiator/capture-head/propulsion visual-interface features, each labeled as display-only.

### `C5-PACKAGE-01`

- Available bus width: `226.3 = 2×113.15`.
- Stowed package width: `238.3 = 2×119.15`.
- The primary geometry must retain this negative result:
  `238.3 mm > 226.3 mm`, overage `12.0 mm`.
- The current bilateral root hardware reaches `|Y|=151.15`, so the represented
  mechanism has a derived lower-bound width of `302.3 mm`. This is a source
  envelope observation, not a packaging closure.
- `C5-PACKAGE-01` remains `TBD/HOLD`.
- No display component is hidden, thinned, or moved to create a false pass.

## Proposal-only parameters

Every numeric choice absent from the frozen decision or current B5 source is prefixed `DESIGN_PROPOSAL_` in the Python source. Important examples:

- spreader-rib and gusset sections;
- panel/deck representation thicknesses and seam gap;
- saddle relief and soft-pad thickness;
- arm-HDRM reservation size;
- tool-axis and root-keep-out visual-reference sizes;
- harness bend radius/tube diameter;
- access-cover and fastener-marker dimensions;
- capture-window depth;
- thruster-bell exit radius.

These parameters are geometric candidates only and cannot be consumed as an ICD, manufacturing drawing, analysis mesh, or procurement definition.

## Output paths

- Generator: `v22_mechanical_continuation.py`
- Primary STEP: `v22_mechanical_continuation.step`
- Validation outputs: `validation/`
- Snapshots: `snapshots/`

## Validation targets

- STEP generation succeeds and produces labeled positive-volume solids.
- Baseline: `inspect refs --facts --planes --positioning`.
- Deterministic source contract:
  - bus axial length `366.0`;
  - bus width/height `226.3`;
  - plate `160×160×12`;
  - central bore `Ø100`;
  - adapter outer face `X=198.0`;
  - longeron centres `Y,Z=±105.65`;
  - MID1/MID2 frame centres `X=±61.0`;
  - stowed wing total width `238.3`;
  - C5 overage `12.0`.
- Targeted CLI measurements will be selected from post-generation refs to confirm key plate, bus, and wing extents.
- Mandatory CAD snapshots: isometric physical assembly, front interface view, stow-support/root-mechanism view, and a side/end view exposing the C5 width.

## Claim limits

- This assembly proves that the platform mechanical mainline can continue while `B601_FULL_HIFI_358_COMPONENT_ROUTE` remains `HOLD`.
- It does not prove B601 vendor geometry recovery, LOD1 contact-face suitability, mechanical release reliability, solar deployment clearance, C5 closure, arm task clearance, or structural adequacy.
- Visual-reference keep-outs and interface reservations are separate labeled solids and are not hardware.
