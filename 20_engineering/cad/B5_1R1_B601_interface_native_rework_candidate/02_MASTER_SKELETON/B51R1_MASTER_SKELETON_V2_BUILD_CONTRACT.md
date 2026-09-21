# B5.1R1 Master Skeleton V2 build contract

Status: `STAGE_A_NATIVE_REFERENCE_GEOMETRY_PASS / FINAL_MASTER_SKELETON_HOLD_AFTER_COORDINATE_API_HANG`

This native part is an interface-control skeleton, not a structural, mass,
stiffness, attachment, manufacturing, or flight model. The durable measurement
gate has passed. H9 remains explicitly split into `MODE_A_EVALUATION` and
`MODE_B_EVALUATION`; neither branch is selected.

## Common datum set

- `CS_S` is the spacecraft structural parent frame.
- `PLN_TASK_FACE_X183` remains separate from both mount-origin tracks.
- `CS_M_DYNAMICS_X185_25` and `CS_M_DISPLAY_X198` must coexist. No hidden
  offset may reconcile them.
- Primary faces are at `±110.15 mm`; removable-panel outer faces are at
  `±113.15 mm` and have no primary load-path credit.
- Four longeron axes use `Y/Z=±101.65 mm`.
- `CS_A0_CLOCKED_25_DEG` is an installation candidate only; it is not J1
  zero and is not a released physical interface.
- The `160 × 160 mm` mount face and `Ø100 mm` central keep-clear channel are
  human-authorized design targets, not vendor or flight-interface evidence.

## Durable measurement disposition

`01_MEASUREMENT/B51R1_DURABLE_DATUM_MEASUREMENT_FINAL.json` records
`PASS_DURABLE_SOURCE_BOUND_MEASUREMENT_WITNESS`.

- The signed 4 mm discrepancy is causally closed as a stale section-and-layer
  datum. No rigid-body translation is required, and the old bridge or saddles
  must not be translated by 4 mm. This does not constitute a geometry repair;
  no repair has been performed.
- The signed 3 mm result is a removable-panel-layer relationship. It is not a
  generic panel-thickness allowance, a shim requirement, or primary-structure
  credit.
- Four source-bound shoe-bottom footprint windows are available on the
  `Z=113.15 mm` panel-layer plane:

  | Window | X range (mm) | Y range (mm) |
  |---|---:|---:|
  | `G07_NY` | 10 to 60 | -113.15 to -98.15 |
  | `G07_PY` | 10 to 60 | 98.15 to 113.15 |
  | `G08_NY` | -100 to -40 | -113.15 to -98.15 |
  | `G08_PY` | -100 to -40 | 98.15 to 113.15 |

These windows are source-bound panel-layer footprint data only. They provide
no contact-degree-of-freedom allocation and no primary load, attachment, or
physical contact credit.

## Native implementation status

Stage A is preserved as
`B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT`. Its readback status is
`PASS_STAGE_A_NATIVE_REFERENCE_GEOMETRY_SAME_SESSION_REOPEN`: all 16 required
named reference features and all three configurations were present, with zero
solid bodies and zero external file references.

Stage B failed closed while authoring the first formal coordinate system through
`IFeatureManager.CreateCoordinateSystem`. The API call hung, the exact
SolidWorks process was contained, and the validated Stage A file hash remained
unchanged. No coordinate-system checkpoint, Stage B receipt, or final
`B51R1_MASTER_SKELETON_V2.SLDPRT` exists.

## Remaining holds and authoring boundary

- Final Master Skeleton release remains on hold pending a successful,
  evidence-preserving coordinate-system authoring path.
- `KO_SOLAR_SWEEP`, `KO_ARM_RELEASE`, `KO_HARNESS`, and
  `KO_SERVICE_ACCESS` geometry remain `TBD/HOLD`.
- H9 is unresolved; both evaluation branches must remain available.
- Detailed adapter and G07/G08 authoring is not released. A concept downselect,
  named and evidenced primary load path, fastener/tool-access definition,
  loads, boundary conditions, and FEA evidence are still absent.
- No contact freedoms, preload directions, attachment details, or load paths
  may be inferred from the footprint windows.

The current evidence ceiling is Stage A native reference geometry only. It does
not establish a final Master Skeleton, native carriers, articulated assembly,
H10 closure, T005 completion, manufacturing readiness, or flight readiness.
