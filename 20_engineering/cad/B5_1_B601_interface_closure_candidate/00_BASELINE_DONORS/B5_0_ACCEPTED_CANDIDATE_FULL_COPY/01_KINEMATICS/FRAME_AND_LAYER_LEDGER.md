# B601 Frame and Model-Layer Ledger

## Authority

`L0_OWNER = arm_b601_v1.urdf`

`MASS_OWNER_ID = B601_URDF_OWNER`

The extraction generator carries the exact source strings for origins, axes,
limits, masses, centres of mass and inertias. SolidWorks mass properties are
excluded from this authority.

## Layers

| Layer | Purpose | Authority | Permitted derivation |
|---|---|---|---|
| L0 | Dynamics and robot topology | Accepted URDF only | Read-only extraction |
| L1 | Native engineering-readable CAD | B5.0 candidate | URDF frames plus registered vendor geometry and explicitly provisional interfaces |
| L2 | Simulation visual/collision assets | Candidate-derived | L1 geometry simplified while retaining L0 names and frames |

## Frame convention

The accepted root is `A0 = base_link`.

For the current spacecraft display track:

`p_S = [198, 0, 0] mm + R_SM p_A0`

For the dynamics/PDR track:

`p_S = [185.25, 0, 0] mm + R_SM p_A0`

with:

`R_SM = [[0,0,1],[0,1,0],[-1,0,0]]`

Therefore `+Z_A0 -> +X_S`. The 12.75 mm track difference is an open interface
ruling and shall not be absorbed into any accepted joint origin.

## Native naming

- Link frames: `CS_LINK_<accepted link name>`
- Joint frames: `CS_JOINT_<accepted joint name>`
- Joint axes: `AXIS_<accepted joint name>`
- Inertial points: `PT_COM_<accepted link name>`
- Visual reference components: `VIS_<accepted link name>`
- Collision reference components: `COL_<accepted link name>`
- Spacecraft mount frames: `CS_MOUNT_DISPLAY_198` and
  `CS_MOUNT_DYNAMICS_185_25`

## State control

| State | Source | Status |
|---|---|---|
| `Q0_ACCEPTED` | all accepted joint values zero | Authoritative reference pose |
| `VENDOR_STOW_V2` | vendor-derived 25 degree study | `CANDIDATE_HOLD` |
| `STOW_V3_O13` | `[145.572,-168,-57,-41.143,-20.954,-3] deg` | `CANDIDATE_HOLD` |
| `GRIPPER_CAPTURE_READY` | accepted consumer lock | Dynamics configuration only; prismatic topology retained |
| `GRIPPER_SERVICE_OPEN` | accepted prismatic limits | Engineering service study; actuator capability not qualified |

No released state may be defined by manually moving a SolidWorks component.

## Vendor registration

G01, G02, G03, G04, G06 and G07 are direct geometric registrations to accepted
link frames. G05 Link6 and G08 Gripper remain `CHAIN_DERIVED_HOLD`; their
geometric use is allowed for candidate visualization but cannot close a datum or
interface drawing.

## Open frames

- `T_E_TCP_PHYSICAL`: `UNKNOWN`
- spacecraft released B601 flange hole pattern: `TBD`
- HDRM hardpoint and release vector: `TBD/HOLD`
- stow contact frames and preload: `TBD/HOLD`
- B106 interface frames: `NOT_AVAILABLE`
