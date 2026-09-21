# V5R Neutral Operational Package

This is a neutral/interface package for competition-prototype on-orbit simulation. It is not a native CAD, manufacturing, launch, or flight release.

## Composition boundary

This is a **package-level composite**, not one monolithically updated STEP assembly. The main STEP/FCStd is the byte-identical F3R2/V2 neutral baseline and still contains the original B51 arm/gripper. The 23 V4 delta STEP files (including M3R Stage A/Stage B, wing-root/support and keep-out geometry) and the gripper R1 palm/full-stroke sweeps are separately hash-bound addenda. Their system placement and composite narrow-phase interference remain HOLD/UNKNOWN.

- Dynamics mass/inertia authority: `urdf/arm_b601_v1.urdf` only.
- Visual/collision STL shall not be used to infer mass.
- Configuration entries are semantic sim13 enums; native rebuild/readback remains HOLD.
- Main-neutral historical external-interference zero does not propagate to the separately packaged addenda.
- `ABORT` must remain available and all UNKNOWN safety inputs must fail closed.
