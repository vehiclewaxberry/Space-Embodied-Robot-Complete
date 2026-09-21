# B5.1R1 G07/G08 restraint architecture contract

Status: `FUNCTIONAL_ALLOCATION_CANDIDATE / PHYSICAL_LOAD_CREDIT_NONE`

The root base is the primary geometric locator. G07 and G08 are launch/stow
restraints, not two additional fully rigid installations. The current
candidate allocation is:

- G07 provides a one-direction axial-stop function plus contact-normal
  closure;
- G08 retains an explicit spacecraft-X float candidate and may provide a
  separate normal/lateral support function;
- HDRM supplies preload and release only; it is not an additional datum.

This is a functional hypothesis, not a released restraint design. Exact
normal and tangent vectors cannot be assigned until the four G07/G08 shoe
bottom faces have durable SOLIDWORKS identities and occurrence transforms.

No G07/G08 interface may simultaneously constrain all translations and
rotations. The future detailed design shall use slots, spherical/replaceable
pads, compliant elements, controlled clearance, or another source-bound
method to absorb installation error without silently creating a rigid
base–G07–G08 loop.

The following remain `TBD/HOLD`:

- preload magnitude and direction;
- material, stiffness, friction, tolerance, fastener, and pad stack;
- HDRM hardware and release direction;
- post-release protrusion and snag envelope;
- tool access and replacement access;
- exact contact area, projected overlap, edge margin, and load credit;
- arm and solar release clearances.

The H10 baseline remains 0/28 closed. G07 owns rows V14-17..V14-21 and G08
owns V14-22..V14-28; no row may close until an exact replacement part,
configuration-specific BREP result, local evidence, and replacement mapping
all exist.
