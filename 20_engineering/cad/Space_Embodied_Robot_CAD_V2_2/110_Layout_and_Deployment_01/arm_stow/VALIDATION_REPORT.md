# V22 Gate 4 ARM-STOW layout validation report

## Post-adversarial revision notice

This report now reflects the repaired isolated Gate 4 artifact. The main saddle
is on the forward station, the wrist support is on the aft station, every
physical pad is contained within `|Y| <= 113.15 mm`, and the explicit
`V22_TOP_LAYOUT_FRAME -> CS_S` staging transform is recorded. The machine
authority is `validation_results.json`.

## Verdict

`PASS_WITH_ENGINEERING_HOLDS`

The isolated layout satisfies the requested geometric zoning and contact checks. It does not release crossbeam sizing, attachment design, HDRM, load definition, arm contact faces, vendor-shell support suitability, structural adequacy or flight qualification.

## Generated artifact

- STEP: `arm_stow_layout.step`
- SHA-256: `539dae5b45e179a8aa5390f32b91fbb5cc7d2af32de11ce4965535ad35878362`
- Size: `2,694,743 bytes`
- Exported structure: `165 occurrences`, `150 leaf occurrences`, `150 shapes`
- Topology: `900 faces`, `1,800 edges`
- Bounding box: `[-180.0, -113.15, -6.0]` to `[160.0, 113.15, 150.0] mm`
- Positive-volume solids: `150`; minimum solid volume `40.0 mm^3`
- Required entity labels: `29/29 present`

## Deterministic geometry checks

- Forward crossbeam Y span: `211.30 mm` using `#o1.1.1.f3` to `#o1.1.1.f4` — PASS.
- Aft crossbeam Y span: `211.30 mm` using `#o1.1.2.f3` to `#o1.1.2.f4` — PASS.
- Forward crossbeam X footprint: `[40.0, 90.0] mm` — PASS.
- Aft crossbeam X footprint: `[-150.0, -110.0] mm` — PASS.
- Main saddle and wrist station semantics: forward `[40,90] mm`, aft
  `[-150,-110] mm` — PASS.
- Four physical pads satisfy `max(|Y|)=113.15 mm` — PASS.
- Staging transform: identity rotation plus translation
  `[0,0,119.15] mm`; all four pad lower faces map to `Z=113.15 mm` —
  PASS for isolated staging, interface ratification HOLD.
- Frozen corridor: `Y=[-40.0,+40.0] mm`, width `80.00 mm` using `#o1.2.1.1.f3` to `#o1.2.1.3.f4` — PASS.
- Port equipment-band gap from frozen boundary: `20.00 mm` using `#o1.2.1.3.f4` to `#o1.3.1.1.f3` — PASS.
- Starboard equipment-band gap from frozen boundary: `20.00 mm` using `#o1.3.2.3.f4` to `#o1.2.1.1.f3` — PASS.
- Minimum gap for all eight equipment/radiator/sensor/antenna reservations from `|Y|=40`: `20.00 mm` — PASS.
- Twelve declared physical support/contact pairs: distance `0.00 mm`, with positive overlap on the two in-plane axes — PASS.
- Forward-port pad top `#o1.1.3.f6` to forward-crossbeam bottom `#o1.1.1.f5`: flush delta `[0,0,0] mm`, no rotation — PASS.
- Main-saddle port bracket bottom `#o1.1.11.f5` to forward-crossbeam top `#o1.1.1.f6`: flush delta `[0,0,0] mm`, no rotation — PASS.
- Claim boundary: mass/kinematic/strength/stiffness/qualification authorities excluded; vendor-shell support suitability not claimed — PASS.

Machine validation summary: `15 PASS / 0 FAIL`.

## Snapshot review

The original four-view packet predates the adversarial repairs and is retained
as history. The governing post-repair image is:

- `../snapshots/arm_stow_repaired_iso_20260726T142704Z.png`

Visual findings:

- the central corridor runs longitudinally along X and remains centred on `Y=0`;
- equipment bands and their internal reservations are on the two outside lanes;
- the two physical crossbeams bridge the two lateral support regions;
- physical pads/webs/brackets appear seated; zero-gap deterministic checks confirm the non-floating condition;
- cage-style reservation geometry is visually distinct from the solid physical members;
- no visual repair was required.

## Holds and non-claims

- `CROSSBEAM_SECTION`: `DESIGN_PROPOSAL / TBD / HOLD`
- `ATTACHMENT_AND_PAD_DETAIL`: `DESIGN_PROPOSAL / TBD / HOLD`
- `HDRM_ARCHITECTURE`: `DESIGN_PROPOSAL / TBD / HOLD`
- `LAUNCH_AND_SERVICE_LOADS`: `UNKNOWN / HOLD`
- `ARM_CONTACT_FACES_AND_LOCAL_PRESSURE`: `UNKNOWN / HOLD`
- `VENDOR_SHELL_SUPPORT_SUITABILITY`: `NOT_CLAIMED / HOLD`

No conclusion is made for strength, stiffness, shock transmission, thermal behaviour, grounding, harness routing, mass properties, manufacturability or flight suitability.
