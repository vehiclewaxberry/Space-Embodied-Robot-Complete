# B5.1R1 driver-ready carrier architecture contract V4

Status: `RECOVERY_REFROZEN / MR2_NOT_CREATED`

V4 is an append-only successor to V3. V2 and MR1 parts remain immutable. MR2
retains all MR1 mate support geometry and adds one lower-offset native Limit
Angle reference plane to each parent of joint1 through joint6.

## Versioned output

- Directory: `03_CAD/12_DRIVER_READY_CARRIERS/`
- File pattern: `B51R1_CARRIER_MR2_<LINK>.SLDPRT`
- MR1 source parts are never overwritten or saved.
- All V2/MR1 zero-body, zero-mass, property, coordinate-system, BOM and
  external-reference rules remain mandatory.

## Revolute driver reference

For each revolute joint, the parent owns:

- `PLANE_ZERO_<joint>_PARENT_SIDE`: q0 pose witness, coincident with the child
  ZERO plane at q=0; it is not selected by the Limit Angle mate.
- `PLANE_LIMIT_REF_<joint>_PARENT_SIDE`: native driver lower reference.
- `SK3D_LIMIT_<joint>_PARENT_SIDE`: internal construction only.

Let `a` be the accepted joint axis, `n0` the q0 ZERO-plane normal and `lower`
the accepted URDF lower limit. The Limit Reference normal is
`Rot(a,lower)*n0`; its plane contains the joint axis and passes through the
parent joint origin. The native driver selects this Limit Reference and the
child `PLANE_ZERO_<joint>`.

The frozen coordinate is therefore:

```text
theta = q - lower
theta_min = 0
theta_max = upper - lower
theta_q0 = -lower
```

The active R constraint set remains exactly concentric axis, coincident seat
and one Limit Angle driver. The additional q0 ZERO plane is a readback witness,
not an additional mate. P, fixed and root constraint sets are unchanged from
V3.

## Construction and verification

The Limit Reference is a true `IRefPlane` constructed from three 3D-sketch
points with selection marks 0/1/2 and three Coincident constraints. Its Gate
checks absolute normal alignment, joint-origin point-to-plane residual,
zero-body/mass/external-reference state, protected source hashes and a separate
read-only cold reopen. J1/J4/J6 branch witnesses and all V3 sign, P, checkpoint
and prohibition rules remain in force.

This contract grants no S05, G4, T005, manufacturing, launch or flight credit.
