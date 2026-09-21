# B5.1R1 mate-ready carrier architecture contract V3

Status: `RECOVERY_REFROZEN / MR1_NOT_CREATED`

This contract is an append-only recovery successor to V2. V2 Carrier files and
their S04B_R2 hashes remain immutable evidence. The MR1 set retains every V2
coordinate system, property, zero-body/zero-mass rule and accepted URDF frame,
and adds only native reference geometry required by SOLIDWORKS mates.

## Versioned output

- Directory: `03_CAD/11_MATE_READY_CARRIERS/`
- File pattern: `B51R1_CARRIER_MR1_<LINK>.SLDPRT`
- Source V2 parts are never overwritten, renamed or saved.
- MR1 parts remain zero solid-body, zero CAD mass, BOM-excluded and free of
  external references.

## Moving-joint reference geometry

For every outgoing R or P joint, the parent carrier owns:

- `AXIS_<joint>_PARENT_SIDE`
- `PLANE_SEAT_<joint>_PARENT_SIDE`, normal to the joint axis
- `PLANE_ZERO_<joint>_PARENT_SIDE`, containing the joint axis
- `SK3D_DATUM_<joint>_PARENT_SIDE`, internal construction only

Every incoming moving child retains `AXIS_<joint>` and
`PLANE_ZERO_<joint>` and additionally owns
`PLANE_SEAT_<joint>_CHILD_SIDE`, normal to the joint axis. Coordinate
systems remain pose witnesses and are not partial-constraint substitutes.

## Native mate topology and frozen names

Each revolute joint uses exactly:

1. `Jxx_AXIS_CONCENTRIC`, with rotation unlocked;
2. `Jxx_AXIAL_COINCIDENT`, between the two seat planes;
3. `Jxx_LIMIT_ANGLE_DRIVER`, the only command mate, between zero planes.

Each prismatic joint uses exactly:

1. `P0x_AXIS_CONCENTRIC`, with rotation unlocked;
2. `P0x_ANTI_ROTATION_PARALLEL`, between zero planes;
3. `P0x_LIMIT_DISTANCE_DRIVER`, the only command mate, between seat planes.

`gripper_joint` uses only `GFIX_X_COINCIDENT`, `GFIX_Y_COINCIDENT` and
`GFIX_Z_COINCIDENT`. The link6 parent owns
`GFIX_PLN_X/Y/Z_PARENT_SIDE`; the gripper-link child retains
`GFIX_PLN_X/Y/Z`. No component Fix or coordinate-system mate is permitted.

The assembly root is grounded by `J00_ROOT_X/Y/Z_COINCIDENT` between the
assembly origin planes and `ROOT_PLN_X/Y/Z` on the base carrier. Automatic
component Fix is prohibited and must be removed before J00 is accepted.

## Driver coordinates and probes

The native revolute driver is `theta=q-lower`, with native range
`0..(upper-lower)` and native q0 `-lower`. Exact interior sign probes are:
joint1=0, joint2=-1.57, joint3=-1.57, joint4=0, joint5=0 and joint6=0 rad.
The sequence is `q_probe,+1deg,q_probe,-1deg,q_probe,q0`.

Enhanced branch witnesses are:

- joint1: `-2.78,-1.40,0,1.40,2.78` rad;
- joint4: `-1.85,-0.935,0,0.785,1.55` rad;
- joint6: `-3.13,-1.57,0,1.57,3.13` rad with explicit branch index.

Each P driver range is independently `0..0.0715 m`, with q0=0 and half
stroke=0.03575 m. The four corners are `(0,0)`, `(0.0715,0)`,
`(0,0.0715)` and `(0.0715,0.0715)`; asymmetric witnesses are
`(0.03575,0)`, `(0,0.03575)`, `(0.0715,0.03575)` and
`(0.03575,0.0715)`.

## Checkpoint minimum contract

Every J00-J09 checkpoint records input/output hashes, process and SOLIDWORKS
revision, component/fixed/suppression inventory, mate names/types/entities,
alignment and limits, remaining DOF status, raw driver readback, reconstructed
q, axis/plane dot products, FK error, sign/branch trace, ten-cycle raw samples,
save errors/warnings and normal close/exit state. A failed increment preserves
the previous PASS checkpoint and may not write the formal S05 Gate receipt.

## Prohibitions and claim limit

Imported face/edge mates, Move Component, `Transform2`, locked concentric
rotation, Mate Controller truth, a second driver and shared/mimic finger width
are prohibited. This recovery contract grants no S05, G4, T005, fine-geometry,
manufacturing, launch or flight credit until the applicable cold-reopen and
incremental assembly Gates pass.
