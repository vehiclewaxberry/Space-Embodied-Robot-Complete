# V22-LAYOUT-AND-DEPLOYMENT-01 CAD brief

## Scope and authority

- Model family: isolated mechanical-layout and deployment staging for the
  embodied-intelligence B601 service spacecraft.
- Task type: STEP-first parametric continuation. No accepted V2.2 file and no
  canonical top-level SolidWorks assembly is edited.
- Units: millimetres.
- Assembly frame: `CS_S`, origin at spacecraft bus centre, `+X` rear-to-task,
  `+Y` left/port, `+Z` spacecraft top.
- Geometry authority: layout, interface tracing, discrete deployment
  diagnostics, and state-entry staging only.
- B601 kinematic and mass authority: the accepted
  `arm_b601_v1.urdf`, consumed read-only. Its exact mass sum remains
  `4.695555949342986 kg`.
- Structural authority: none. Load paths are named intent; strength,
  stiffness, modes, shock, fatigue, tolerance, release reliability,
  manufacturability, and flight qualification remain outside this gate.

## Frozen and preserved inputs

- Task face: `X=+183.0`.
- B601 mounting datum: `X=+198.0`.
- MID1/MID2: `X=+61.0/-61.0`.
- Bus half-width and top exterior plane: `113.15`.
- Four longeron centre coordinates: `|Y|=|Z|=105.65`.
- Solar panel: `227 x 200 x 6`.
- New solar packaging baseline: recessed lower book fold, hinge axis parallel
  to `+X`, proposal axis at `Y=+/-110.0`, `Z=-105.65`.
- Preserved negative result: the previous external hanging package is
  `238.3 mm > 226.3 mm` and its represented root lower-bound width is
  `302.3 mm`; it is rejected for packaging, not rewritten as a pass.
- `PARTIAL` angle remains `UNKNOWN`.
- `SERVICE` geometry and access sequence remain pending human ratification.
- The inherited q0 conservative-box interference record remains a negative
  result and cannot be cleared by suppressing or relabelling components.

## Source positioning and frame mapping

The solar model is already authored in `CS_S`. The Gate-4 arm-stow model is
authored in `V22_TOP_LAYOUT_FRAME`, with axes parallel to `CS_S` and local
support pads spanning `Z=[-6,0]`.

For isolated staging only, the selected transform is:

```text
R_CS_S_TOP = identity
T_CS_S_TOP = [0, 0, +119.15] mm
119.15 = CS_S top exterior plane 113.15 - local pad lower face (-6.0)
```

This puts the lower faces of the four proposal pads on `Z=+113.15`, their
upper faces on `Z=+119.15`, and the two crossbeam lower faces on
`Z=+119.15`. The transform is
`DESIGN_PROPOSAL_SELECTED_FOR_ISOLATED_STAGING`, not a frozen spacecraft
interface. Panel penetration, fasteners, insert design, local pressure, and
transfer into the upper longerons remain `TBD/HOLD`.

## Integrated model content

- Reused read-only from the accepted continuation generator:
  - primary frames, decks, longerons, and split exterior panels, copied into
    the isolated staging model;
  - B601 mount plate, adapter and labelled load-path intent.
- Revised only in the isolated platform copy:
  - bilateral cassette pockets at `X=[-175,53]`,
    `|Y|=[106.5,113.15]`, `Z=[-111.65,94.35]`;
  - pocket subtraction preserves an inboard residual strip of the affected
    15 mm frame/longeron members, but its section adequacy remains `HOLD`.
- Reused from Gate 1-3 source:
  - recessed cassettes and bilateral moving panels;
  - independent left/right angles for failure-state diagnostics.
- Reused from Gate 4 source:
  - two physical crossbeams, pads, end webs, saddle/wrist brackets;
  - central arm, release, HDRM, tool and equipment reservation geometry;
  - all transformed by the explicit mapping above.
- Read-only q0 proxy:
  - ten axis-aligned link envelopes derived previously from accepted URDF/STL
    q0 transforms;
  - geometry is conservative proxy evidence, not vendor HIFI CAD.

## Formal state entry policy

The state manifest contains exactly seven named entrypoints:

1. `STOWED`
2. `DEPLOYED_NOMINAL`
3. `DEPLOY_FAILED_BOTH`
4. `L_FAIL`
5. `R_FAIL`
6. `PARTIAL`
7. `SERVICE`

Five static diagnostic STEP scenes may be generated. `PARTIAL` and `SERVICE`
must remain manifest-only entrypoints with no invented geometry binding.
`STOWED` remains `HOLD_B601_HIFI_ABSENT`: it may show the physical stow
support and solar 0-degree geometry but may not substitute q0 for the missing
stowed vendor representation.

## Validation targets

- Generate and reopen each produced STEP.
- Run baseline CAD inspection with
  `refs --facts --planes --positioning`.
- Verify `V22_TOP_LAYOUT_FRAME -> CS_S` placement numerically.
- Verify the four pad lower faces map to `Z=113.15`.
- Measure solar root and tip frames for 0/90-degree states.
- Evaluate exact solid-to-solid minimum distance for:
  - moving solar panels versus physical arm-stow support;
  - moving solar panels versus q0 conservative link envelopes;
  - fixed solar cassette versus physical arm-stow support.
- Preserve separate results for every sampled pose/state. Do not infer
  continuous collision safety from finite samples.
- Review mandatory isometric, top, front, and state-comparison snapshots.
- Recheck input hashes and confirm the canonical V2.2 top assembly and the
  accepted `100_Mechanical_Continuation` STEP are unchanged.

## Output boundary

All new work stays below:

`110_Layout_and_Deployment_01/`

The primary staging source, STEP state scenes, state manifest, deployment
sequence, validation JSON, snapshots, and final gate report are new isolated
artifacts. No native SolidWorks configuration, mate, suppression, BOM, or mass
readback claim is made.
