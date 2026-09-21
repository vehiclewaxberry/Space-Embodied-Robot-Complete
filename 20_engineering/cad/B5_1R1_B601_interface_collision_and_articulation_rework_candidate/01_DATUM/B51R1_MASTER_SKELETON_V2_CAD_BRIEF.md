# Master Skeleton V2 CAD brief

Status:

`BRIEF_READY / SOURCE_BOUND_DATUM_CANDIDATES / NATIVE_PART_NOT_AUTHORIZED`

## Purpose

The future Master Skeleton V2 must prevent another geometry field from being
promoted without its source, authority, configuration, and unit. It is a datum
and interface-control part, not a mass, stiffness, attachment, or flight
model.

## Source-bound reference candidates

| Item | Value | Role | Current authority |
|---|---:|---|---|
| `CS_S` | spacecraft structural frame | global parent frame | inherited |
| four longeron centrelines | `Y/Z=±101.65 mm` | primary centreline datum | canonical native source |
| longeron section | `17×17 mm` | primary geometry datum | canonical native source |
| primary outer surfaces | `Y/Z=±110.15 mm` | candidate load-introduction reference | canonical native source; attachment not proven |
| removable-panel outer surfaces | `Y/Z=±113.15 mm` | envelope/panel reference only | canonical native source |
| spacecraft task face | `X=183.0 mm` | canonical geometry face | keep distinct from mount origins |
| dynamics/PDR mount origin | `X=185.25 mm` | dynamics track | `EVIDENCE_BOUND`, unresolved against display track |
| V2.2 display mount origin | `X=198.0 mm` | display/native integration track | human adjudication required |
| B601 clocking | `25 deg` | engineering candidate only | not a released interface |

The Skeleton must not resolve the `185.25/198.0 mm` conflict by adding a hidden
offset to a joint origin.

## Required named features

- `CS_S`
- `PLN_TASK_FACE_X183`
- `PLN_PRIMARY_PY_Y110_15`, `PLN_PRIMARY_NY_YN110_15`
- `PLN_PRIMARY_PZ_Z110_15`, `PLN_PRIMARY_NZ_ZN110_15`
- `PLN_PANEL_OUTER_PY_Y113_15`, `PLN_PANEL_OUTER_NY_YN113_15`
- `PLN_PANEL_OUTER_PZ_Z113_15`, `PLN_PANEL_OUTER_NZ_ZN113_15`
- `AX_LONGERON_PY_PZ`, `AX_LONGERON_PY_NZ`
- `AX_LONGERON_NY_PZ`, `AX_LONGERON_NY_NZ`
- separate `CS_M_DYNAMICS_X185_25` and `CS_M_DISPLAY_X198`
- candidate `CS_A0_CLOCKED_25_DEG` with property
  `RATIFIED_FOR_B5_1_ENGINEERING_CANDIDATE_ONLY`
- named G07/G08 interface origins, normals, two tangents, and allowed-slip
  directions; these remain TBD until Phase 1.

## Every datum property must include

- source file and field;
- SHA-256;
- units;
- authority class;
- configuration and occurrence path;
- sign convention and parent frame;
- frozen/candidate/HOLD state;
- measurement or construction method;
- downstream consumers.

## Contact-layer rules

1. A longeron centreline, primary outer face, panel inner face, panel outer
   face, saddle lower face, and arm contact pad are different semantic layers.
2. A part at `113.15 mm` may be on the outer panel envelope while remaining
   `3 mm` from primary structure.
3. Zero distance and zero common volume are not attachment proof.
4. An approved interface must name the physical load-transfer member, contact
   law, fastener/bond/HDRM concept, access direction, and replacement mapping.

## Phase 1 validation targets

- Exact readback of all named datums and custom properties.
- Full `CS_S -> occurrence` transforms with unit and rotation checks.
- Named-face signed distance, normal, tangent, contact area, projected overlap,
  edge margin, and exact common volume.
- Explicit obsolete-occurrence exclusion/replacement map.
- H10 row linkage for every affected part.
- Deterministic STEP inspection and snapshots after visible geometry exists.

## Preserved unknowns

Material, thickness, tolerances, fasteners, holes, preload, contact stiffness,
friction, load spectrum, structural margin, mass trend, HDRM hardware, harness,
thermal/environmental qualification, and manufacturing process are
`UNKNOWN/TBD`. This brief does not authorize values for them.

