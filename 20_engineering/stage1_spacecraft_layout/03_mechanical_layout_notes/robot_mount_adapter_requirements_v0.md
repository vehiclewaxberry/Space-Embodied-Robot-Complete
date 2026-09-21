# Robot Mount Adapter Requirements v0

> Frame-notation migration (SSOT, 2026-07-09): arm base = mounting-face frame `M` (= reBot URDF base; SSOT folds the old robot-base `B` into `M`); servicer->mount is written `T_SM` (old `T_SB`/`^S T_B`). Old `B`/`^S T_B` are compatibility aliases only. See `../04_mass_inertia_budget/coordinate_frame_definition_v0.md` §0.

## 1. Purpose

The robot mount adapter connects the 12U/6U servicer structure to the reBot-equivalent manipulator base. It is a Stage 1-C CAD input and a Stage 2 dynamics interface. It must support later export of `T_SM` (servicer body -> arm mounting-face/base `M`; old `T_SB`) into the Pinocchio/free-flyer model.

## 2. Coordinate Requirements

| coordinate item | definition required | notes |
|---|---|---|
| mounting face frame | adapter mounting plate reference on the servicer front task bay | define origin and normal direction relative to `S` |
| arm base = mounting-face frame `M` (old `B`) | reBot URDF base = `M` per SSOT; matches `reBot-DevArm_fixend.urdf` convention after import check | do not assume a different URDF convention |
| servicer body frame `S` | body frame defined in the ICD-lite and coordinate frame SSOT | `T_SM` is expressed from `S` to `M` (old `T_SB` S->B) |
| transform `T_SM` (old `T_SB`) | translation and rotation from servicer body frame to arm mounting-face/base frame `M` | mandatory Stage 2 input |

## 3. Mechanical Requirements

| feature | requirement | status field |
|---|---|---|
| reBot base fixation | provide a rigid base interface for the reBot-equivalent arm | `TBD` until CAD |
| flange/bolt placeholders | define bolt pattern placeholder without claiming final hardware | `TBD` |
| cable routing channel | reserve passage from servicer bus bay to robot base and optional end-effector wiring | `TBD` |
| force/torque interface | reserve a physical F/T sensor volume or a virtual force/torque interface plane | `TBD` |
| stiffness reinforcement | add reinforcement ribs or thickened regions as CAD placeholders | `TBD` |
| rail/contact exclusion | adapter must not invade rail contact zone or other deployment keepout zones | P0 check |
| protrusion check | folded arm, adapter, camera, and fixtures must be checked against the 6.5 mm protrusion rule where applicable | P0 check |
| first protrusion distance | first external protrusion must be checked against the 8.5 mm rail-to-first-protrusion rule where applicable | P0 check |

## 4. Mass and Material Fields

The adapter must have a row in `mass_inertia_budget_v0_template.csv` with:

- component: `robot_mount_adapter`
- material: `TBD`
- density: `TBD`
- mass: `stage1_estimate` or `TBD`
- center of mass: `x_m,y_m,z_m` in `S`
- inertia tensor: `Ixx,Iyy,Izz,Ixy,Ixz,Iyz` about the documented reference point
- source and confidence fields

## 5. Outputs for Stage 2

- `T_SM` (old `T_SB`) with translation, rotation, source, and confidence.
- Adapter mass, center of mass, and inertia estimate.
- Robot folded envelope and keepout volume.
- Robot base frame visualization marker in CAD screenshots.

## 6. Non-goals

- This document does not create a CAD file.
- This document does not validate adapter stiffness by finite element analysis.
- This document does not define joint torques or low-level control.
