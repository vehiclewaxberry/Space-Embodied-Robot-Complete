# B5.1R1 native carrier architecture contract

Status: `CONTRACT_READY / NATIVE_PARTS_AND_ASSEMBLY_NOT_CREATED`

Authority:

- accepted URDF SHA-256:
  `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`;
- accepted q0 joint-axis export SHA-256:
  `73F1E674A57F3EB7863BEBF32D497DF8829E4348DBB84C6A1A796106036845C0`;
- topology: 10 links, 6 revolute joints, 1 fixed joint, and 2 independent
  prismatic joints;
- accepted URDF model-mass sum: `4.6955559493429862 kg`.

The ten carriers do not form a ten-link serial chain. `gripper_link` is a
branch parent with two outgoing prismatic frames, one for each independent
finger.

## Required content of every carrier

Each native carrier part shall remain reference-only and shall contain:

- `CS_LINK`, exactly equal to the accepted URDF link frame;
- `CS_IN_<JOINT>` for the incoming joint frame;
- every required `CS_OUT_<JOINT>` from the URDF joint origin;
- `AXIS_<JOINT>_POS` using the joint-local accepted axis;
- `PLN_<JOINT>_Q0` plus an unambiguous positive-direction witness plane;
- `CS_VISUAL`; all current URDF visual origins are zero and therefore
  coincide with `CS_LINK`.

`B51R1_CARRIER_LINK_07` must contain both `CS_OUT_P1` and `CS_OUT_P2`.

## Native mate rule

For each revolute joint:

- one concentric axis mate with rotation explicitly unlocked;
- one axial coincident mate to remove only axial translation;
- one native limit-angle mate whose current value is the sole command
  parameter.

For each prismatic joint:

- one axis-coincident mate;
- one anti-rotation plane mate;
- one native limit-distance mate whose current value is the sole command
  parameter.

The fixed gripper joint shall use its exact URDF transform through three
orthogonal reference-plane coincidences. It shall not use `Fix Component`.

No joint may use `Move Component`, component `Transform2`, a fixed child
carrier, concentric rotation lock, a second angle/distance command mate, or
Mate Controller as its source of truth. If SOLIDWORKS cannot expose the
limit-mate value as the unique stable driver, the joint remains HOLD pending
an isolated API capability probe; a second driver must not be added by
assumption.

## q0 reset and sign contract

`q0` means all nine URDF joint values are numerically zero; the fixed joint
remains at its exact transform. Reset may write only the eight named native
limit-mate values (six angle, two distance), rebuild, and read them back.
Absolute component transforms are forbidden.

After reset:

1. derive every relative joint transform from the ten carrier frames;
2. remove the fixed URDF joint-origin transform;
3. compare all ten link frames with accepted forward kinematics;
4. record `e_p`, `e_R`, `e_q`, and `e_max`;
5. perform the reset in the same open document after a nonzero test state.

J2 and J3 q0 are at their upper limits. P1 and P2 q0 are at their numeric
lower limits and may only be called `MIN_NUMERIC`, not mechanically closed,
until physical zero calibration exists.

The current historical `e_max <= 2.0e-7` value is diagnostic compatibility
only. Phase 1 acceptance tolerances remain `TBD_HUMAN_AUTHORITY`.

## Geometry and mass separation

Fine B601 geometry may later be rigidly attached to the appropriate carrier
for display, interference, STEP, drawing, and visual-mesh work. Imported
faces and edges may not define motion mates. Carrier or visual-part automatic
mass properties do not override accepted URDF mass, centre of mass, or
inertia.

## Current stop condition

No carrier `.SLDPRT` and no
`B51R1_B601_NATIVE_ARTICULATED.SLDASM` have been created. Phase 1 authoring is
not blocked by the durable measurement Gate: that Gate has passed and permits
carrier kinematic authoring. The current sequential hold is instead:

- final `B51R1_MASTER_SKELETON_V2.SLDPRT` does not exist after the Stage B
  coordinate-system API hang;
- the validated Stage A reference-only part must remain unchanged;
- the single-coordinate `InsertCoordinateSystem` diagnostic is offline-ready
  but has not run;
- the previously authorized one visible SOLIDWORKS launch has been consumed,
  and another visible launch requires fresh explicit user authorization.

Therefore the contract and neutral q0 witness are ready, but native carrier
authoring remains `NOT_RUN`; neither artifact grants native motion, H10, or
T005 credit.
