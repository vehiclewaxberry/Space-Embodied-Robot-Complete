# B601 Base Adapter Design

Current decision:
`REFERENCE_GEOMETRY_READY / PHYSICAL_BASE_ADAPTER_HOLD`

Authoritative native reference run:
`B50_BASE_REF_20260728T0029Z`

## Scope

The present SolidWorks model implements only the source-bound datum and
envelopes that can be drawn without inventing a released B601 physical
interface. It is a design-proposal reference assembly, not a manufacturing
adapter.

The following properties are embedded in every native file:

- `DESIGN_STATUS=DESIGN_PROPOSAL_REFERENCE_ENVELOPE`
- `PHYSICAL_QUALIFICATION=FALSE`
- `MANUFACTURING_AUTHORITY=NONE`
- `MASS_AUTHORITY=EXCLUDED_ACCEPTED_URDF_ONLY`
- `MATERIAL=UNKNOWN`
- `INSTALL_LOADS_6D=UNKNOWN_BLOCKED`
- `BOLT_PATTERN=TBD`
- `LOCATING_PINS=TBD`
- `NO_HOLES_OR_FASTENERS=TRUE`

## Bound source hierarchy

| Source | Role | SHA-256 |
|---|---|---|
| accepted B601 URDF | Kinematic and mass truth | `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164` |
| `gate_0_ruling_record.yaml` | Approved V2.2 display-track ruling | `EDD794B21221EB7EFA9F01E67BF52732A993B83C74D8CE040C88A316C0528B71` |
| `V2_interface_register.yaml` | Baseline interface identities; physical fields open | `3BF778FB23843976889EFA0909941EBE8EBCDE90BA142492CA37AD757082225E` |
| `robot_mount_preliminary_design.md` | PDR topology and envelope basis | `BBD4F7C0C61652879F8C1DBF1F906A91526265105BF1ED5F145C1FA01F1F0959` |
| `robot_mount_load_interface.yaml` | Explicitly blocked six-dimensional loads | `262B4D898CA8DA49AB78EEE28E5AF254F6774DCE8416A947BBF79E5F1A76805F` |

## Datum and dual-track ruling

- B601 root frame: accepted `A0 = base_link`.
- Dynamics/PDR track: `p_SM = [185.25, 0, 0] mm`.
- V2.2 display mount plane: `X = 198.0 mm`.
- Explicit track delta: `12.75 mm`.
- Track policy: `DUAL_TRACK_EXPLICIT_NO_SILENT_MERGE`.

The 12.75 mm display/dynamics difference is not hidden in a joint origin and
does not change the accepted URDF.

## Admitted envelope stack

| Component | X range (mm) | YZ envelope | Native role |
|---|---:|---:|---|
| Primary boss envelope | 156–171 | Ø100 mm | Primary-structure boss reference |
| Spreader plate envelope | 171–183 | 160 × 160 mm | Task-face load-spreading reference |
| Upper flange envelope | 183–198 | 160 × 160 mm | B601 upper-install reference |

The assembled bounding box is
`[156,-80,-80]` to `[198,80,80] mm`.

## Load-path intent

The currently supported topology is:

`B601 A0 → upper flange envelope → spreader plate envelope → primary boss envelope → task-face spreading region → front frame → longerons → primary structure`

This is a topology statement only. No section, material, bolt group, preload,
strength, stiffness, mode, or safety factor has been qualified.

## Native CAD

- `10_reference_parts/B50_BASE_ADAPTER_UPPER_FLANGE_ENVELOPE.SLDPRT`
- `10_reference_parts/B50_BASE_ADAPTER_SPREADER_PLATE_ENVELOPE.SLDPRT`
- `10_reference_parts/B50_BASE_ADAPTER_PRIMARY_BOSS_ENVELOPE.SLDPRT`
- `20_assembly/B601_BASE_ADAPTER.SLDASM`
- `40_drawings/B601_BASE_ADAPTER_REFERENCE.SLDDRW`
- `30_exports/B601_BASE_ADAPTER_REFERENCE.step`

Cold verification established:

- three native one-body SLDPRT files;
- zero external and auxiliary references;
- zero 3D Interconnect features;
- three fixed assembly components, all inside the run root;
- zero component-transform error;
- one model-backed drawing view;
- three STEP solids;
- maximum STEP bounding-box error
  `9.999999406318238e-08 mm`;
- unchanged artifact hashes after cold read.

## Donor conflict retained

The existing V2.2 native design proposal uses a different local stack,
including approximately a 150 × 150 × 3 mm flange and a Ø110/Ø100 pilot
feature. Those values conflict with the Gate-0/PDR stack and have
`MANUFACTURING_AUTHORITY=NONE`; they were not copied into the B5.0 reference
assembly.

## Physical-interface HOLD

The following remain unresolved:

- released B601 bolt pattern, hole count, hole diameter, and bolt circle;
- locating pins and repeatable positioning features;
- physical mating stack and tolerances;
- fastener grade, preload, locking, and access;
- materials and surface treatment;
- thermal isolation and electrical ground bond;
- connector and harness penetrations;
- all six-dimensional launch, capture, and ground load cases;
- stiffness, displacement, modal, strength, and buckling requirements.

The next gate is:
`PHYSICAL_BASE_ADAPTER_INTERFACE_FIELDS_AND_LOAD_CASES`.
