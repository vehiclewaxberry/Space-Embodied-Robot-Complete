# B5.1R1 carrier architecture contract V2

Status: `REFROZEN_OPERATIONAL_CONTRACT / NATIVE_PARTS_NOT_CREATED`

This contract supersedes the V1 `CS_IN/CS_OUT` and counterintuitive
`CS_PARENT_JOINT/CS_CHILD_JOINT` tokens for execution. Original files remain
immutable historical evidence.

## Native ownership and transform rule

- Parent carrier owns `CS_JOINT_<JOINT>_PARENT_SIDE` at the accepted URDF
  joint origin: `T(parent_link,parent_side)=T_URDF_origin`.
- Child carrier owns `CS_JOINT_<JOINT>_CHILD_SIDE` at link-local identity:
  `T(child_link,child_side)=I`.
- At q0 the two side-frame world transforms must coincide. The URDF origin is
  applied exactly once, on the parent side; it must never be applied again to
  the child carrier.
- A moving joint's child carrier also owns `AXIS_<JOINT>` and
  `PLANE_ZERO_<JOINT>`. The fixed joint uses `GFIX_PLN_X/Y/Z` and no driver.
- `gripper_link` owns two distinct outgoing parent-side frames for the two
  independent prismatic fingers.

## Carrier content

Every carrier is reference-only, zero solid-body, zero CAD mass, free of
external references, excluded from BOM, and carries the accepted URDF SHA-256.
It contains one `CS_LINK_<LINK>`, zero or one incoming child-side frame, every
required outgoing parent-side frame, and one `CS_VISUAL_MOUNT_<LINK>`.

## Motion contract

The chain is `6R + 1 fixed + 2 independent P`, with one native Limit
Angle/Distance driver per moving joint. Imported faces/edges, component Fix,
Move Component, Transform2 and a shared gripper-width driver are prohibited.
Every revolute joint records raw API angle, alignment state, unwrapped branch
index, reconstructed q, axis dot and zero-plane dot. J1/J4/J6 require enhanced
full-range branch probes; J6 seam witnesses include q=-3.13 and +3.13 rad and
must not be collapsed by shortest-angle comparison.

## Authority and limits

Accepted URDF mass/inertia remain authoritative. Fine geometry may attach only
through `CS_VISUAL_MOUNT_<LINK>` and may not drive motion or overwrite dynamics.
This contract grants no native-CAD, H10, T005, manufacturing, launch or flight
credit until the applicable Gate receipts pass.

## Fixed-joint single-constraint-set rule

For `gripper_joint`, the active assembly constraint set is exactly the three
`GFIX_PLN_X/Y/Z` plane mates. Parent-side and child-side coordinate systems are
readback witnesses only and must not be added as an extra coordinate-system mate.
This prevents a redundant fixed-joint constraint loop.
