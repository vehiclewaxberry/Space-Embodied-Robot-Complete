# Stage 1-C-0 Layout ICD-lite v0

> Doc role: internal ICD-lite (interface contract) | Type: reference / interface
> Version: v0 | Last synced: 2026-07-09 (frames now reference the coordinate-frame SSOT; `B`→`M`, `T_SB`→`T_SM` migration)
> Frames & transforms are defined in [`../04_mass_inertia_budget/coordinate_frame_definition_v0.md`](../04_mass_inertia_budget/coordinate_frame_definition_v0.md) (SSOT); this file references them, it does not redefine.

## 1. Purpose

This document defines the internal ICD-lite for the Stage 1-C CAD input package. It links the 12U/6U servicer layout, reBot-equivalent manipulator mount, camera, target models, and future free-flyer dynamics inputs.

All parameters in this file are Stage 1 estimates or placeholders. They are not flight-certified data, not measured CAD outputs, and not validated simulation inputs until the CAD model, manual dimension review, and mass property review are completed.

## 2. Coordinate Frames — see the SSOT

Coordinate frames are **defined once** in [`../04_mass_inertia_budget/coordinate_frame_definition_v0.md`](../04_mass_inertia_budget/coordinate_frame_definition_v0.md) (the frozen single source of truth). This ICD references that file and does **not** redefine frames.

Frames used by this ICD: `S` (servicer body), `B` (free-flyer / mother base), `M` (arm mounting-face = reBot URDF base), `C` (camera), `E` (end-effector), `T` (target), `D` (debris), `I` (inertial).

> Migration: the frame this ICD previously called `B` = "robot base" is now **`M`** (arm mounting-face); the previous `T_SB` = "servicer → robot base" is now **`T_SM`**. `B` now denotes the servicer free-flyer / mother base. See the SSOT §0 migration table.

## 3. Required Transforms

Transform symbols and conventions are defined in the SSOT (`coordinate_frame_definition_v0.md` §2–§3). This ICD lists which transforms are Stage 1-C outputs / Stage 2 inputs; values remain blank or `TBD` until CAD and manual review provide traceable entries.

| transform | meaning (from Y to X) | minimum fields | source | downstream use |
|---|---|---|---|---|
| `T_SM` | servicer body → arm mounting-face / reBot URDF base (**the old `T_SB` robot bridge**) | translation `x_SM,y_SM,z_SM`; rotation `R_SM` or `roll,pitch,yaw`; source, confidence | Stage 1-C CAD and adapter definition | arm base placement, GJM/RNS coupling |
| `T_SB` | servicer body → free-flyer / mother base | translation; rotation; default identity or CoM offset; source | mass budget CoM / dynamics reference | Basilisk free-flyer, multibody base |
| `T_SC` | servicer body → camera | translation `x_SC,y_SC,z_SC`; camera optical-axis convention; FOV model reference | Stage 1-C CAD and camera placeholder | target-approach visualization, occlusion checks |
| `T_ST` | servicer body → target initial relative pose | initial relative pose, target type, pose source | mission scenario definition | Stage 2 initial condition and report figures |
| `T_SD` | servicer body → debris initial relative pose | initial relative pose, tumble case, angular-rate reference, source | mission scenario definition | Stage 2 tumbling-target initial condition |
| `T_ME(q)` | arm base → end-effector, from `reBot-DevArm_fixend.urdf` + joint state | computed from URDF + `q` | Stage 2 kinematics | workspace, pre-grasp, capture pose |

## 4. Interface Field Contract

| interface class | fields to record | Stage 1-C rule |
|---|---|---|
| mechanical | mounting face, bolt pattern placeholder, rail or tab reference, keepout zones, deployable envelope | document geometry and status; do not claim final CAD until exported |
| power | expected supply category, harness route, connector placeholder, peak/average power field | record as placeholder only unless source document exists |
| thermal | radiator/thermal-control surface, isolation zone, heat path, blocked surfaces | keep robot adapter and solar panel thermal conflicts visible |
| data | camera data link, robot command link, F/T sensor or virtual interface, debug/RBF interface | identify required interfaces without assigning final protocol |
| ADCS | reaction wheel cluster location, IMU location, camera/target line-of-sight impact, deployable disturbance note | support layout and later disturbance discussion |
| mass/inertia | mass, center of mass, inertia tensor, material, density, source, confidence | fill through the mass inertia CSV; mark estimate source clearly |

> Interface-dimension reconciliation (avoid a third taxonomy): the 6 interface classes above map to the 8 columns of [`../04_mass_inertia_budget/subsystem_interface_table_v0.csv`](../04_mass_inertia_budget/subsystem_interface_table_v0.csv) as — **mechanical** → {`volume_interface`, `mounting_interface`, `keepout_interface`}; **mass/inertia** → {`mass_interface`}; **power** → `power_interface`; **thermal** → `thermal_interface`; **data** → `data_interface`; **ADCS** → `adcs_interface`. Use the CSV for per-subsystem rows and this contract for the class definitions.

## 5. Traceability Notes

- `T_SM` (servicer body → arm mounting-face, formerly labeled `T_SB`) is the most important mechanical-to-dynamics bridge for Stage 2 free-flyer, GJM, and RNS work; `T_SB` now fixes the free-flyer/mother base.
- The 12U layout is the main competition display model. The 6U layout is a quick verification model and must not be described as the complete competition accommodation.
- VLA is a high-level task decision layer only. It must not be represented in this ICD as a low-level joint torque output source.
- Any dimension derived from CubeSat Design Specification Appendix B drawings must remain `manual_review_required` until manually checked and recorded.
