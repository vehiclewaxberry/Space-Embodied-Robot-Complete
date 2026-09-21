# V22-LAYOUT-AND-DEPLOYMENT-01 / Gate 4 — ARM-STOW CAD brief

- Model: isolated top-deck arm-stow and equipment-zoning layout assembly.
- Task type: new STEP-first parametric layout assembly; no modification of any accepted V2.2 artifact.
- Units: millimetres.
- Coordinate convention:
  - origin: local top-layout frame on the spacecraft centre plane and the nominal upper-longeron support plane;
  - +X: longitudinal/forward;
  - +Y: left/port;
  - +Z: outward/up from the top support plane.
- Frozen inputs:
  - arm centreline: `Y = 0`;
  - central arm keep-out: `|Y| <= 40`;
  - upper-longeron support centre lines: `Y = +/-105.65`;
  - forward support X region: `[40, 90]`;
  - aft support X region: `[-150, -110]`.
- Physical design-proposal geometry:
  - one forward crossbeam filling X `[40, 90]`, spanning Y `[-105.65, +105.65]`;
  - one aft crossbeam filling X `[-150, -110]`, spanning the same Y range;
  - four lower attachment pads and four outboard end webs;
  - paired main-saddle and wrist-support brackets seated on the crossbeams.
- Non-physical reservation geometry:
  - frozen arm corridor, proposal-only outer clearance, release sweep, HDRM, tool and two soft-support envelopes;
  - left/port and right/starboard top-equipment bands;
  - four split radiator-strip reservations;
  - relocated sensor and antenna reservation envelopes.
- Positioning:
  - all placements are authored from named source parameters and exact axis-aligned bounding boxes;
  - no manual top-level dragging and no imported vendor-shell mating claim;
  - physical support pads contact the crossbeam lower faces; end webs contact crossbeam end faces; saddle/wrist brackets contact crossbeam upper faces.
  - main-saddle brackets occupy the frozen forward region `X=[40,90]`;
    wrist-support brackets occupy the frozen aft region `X=[-150,-110]`.
  - the isolated staging transform is numerically registered as identity axes
    plus `T=[0,0,119.15] mm`, derived by placing the local pad lower face
    `Z=-6` on the `CS_S` bus-top exterior `Z=113.15`; it remains a
    `DESIGN_PROPOSAL` with interface ratification `HOLD`.
- Primary outputs:
  - `arm_stow_layout.py`
  - `arm_stow_layout.step`
  - `interface_claim_registry.json`
  - `validation_results.json`
  - `snapshots/*.png`
- Validation targets:
  - both crossbeam Y spans equal `211.30`;
  - crossbeam X footprints remain within the two frozen support regions;
  - frozen corridor width equals `80.00`;
  - every equipment/radiator/sensor/antenna reservation remains entirely outside `|Y| <= 40`;
  - every declared physical support/contact pair has zero geometric gap and positive overlap on the other two axes;
  - every physical pad stays within the platform half-width `|Y|<=113.15`;
  - exported STEP contains positive-volume solids and traceable labels.
- Assumptions and claim limits:
  - proposal outer half-clearance is `55`, and equipment bands start at `|Y| = 60`; both are layout proposals, not accepted clearances;
  - Z elevations, beam/bracket sections, attachment details, pads, contact faces and support geometry are layout placeholders;
  - HDRM arrangement, release direction/sweep, tool envelope, radiator allocation, sensor and antenna allocations remain `TBD/HOLD`;
  - launch loads, stiffness, strength, local pressure, thermal, grounding, harness and manufacturing closure are not established;
  - no vendor-shell support suitability, structural adequacy, flight qualification, mass authority or manufacturability claim is made.
