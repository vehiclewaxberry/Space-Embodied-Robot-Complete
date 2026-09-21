# Stage 2 Dynamics Input Requirements v0

## 1. Scope

This document defines what Stage 2 dynamics needs from Stage 1-C. It does not run simulation and does not claim any GJM/RNS result.

## 2. Required Inputs

| input | required content | status |
|---|---|---|
| robot URDF | `reBot-DevArm_fixend.urdf` | required for Stage 2 |
| prohibited robot URDF | do not use `reBot_B601_DM_with_gripper.urdf` for dynamics | rule |
| `T_SB` | servicer body frame to robot base frame transform | required |
| `T_SC` | servicer body frame to camera frame transform | required |
| servicer mass/CG/MOI | total mass, center of mass, inertia tensor, reference frame | required |
| robot mass | from URDF/model or documented equivalent source | required |
| mount adapter mass/CG/MOI | adapter mass properties in `S` or documented reference | required |
| target mass/CG/MOI | target model mass properties and reference frame | required |
| initial relative pose | `T_ST` for each scenario | required |
| naive planning baseline | baseline end-effector trajectory or joint-space plan without RNS reaction suppression | required |
| GJM/RNS metrics | tracking error, base attitude disturbance, base angular velocity, reaction reduction indicator | required |

## 3. Stage 2 Task List

- Build the free-flyer base model.
- Import or reference `reBot-DevArm_fixend.urdf`.
- Attach the robot model through `T_SB`.
- Add servicer mass, CG, and MOI.
- Add mount adapter and target mass properties.
- Implement generalized Jacobian matrix calculation.
- Implement reaction null-space planning.
- Compare naive planning and RNS planning.
- Plot base attitude disturbance curves.

## 4. Killer Figures for Stage 2

1. End-effector trajectory tracking under GJM.
2. Base attitude disturbance comparison under RNS planning vs naive planning.

## 5. Start Conditions

Stage 2 should not start until:

- `T_SB` and `T_SC` are exported from the CAD/layout input.
- servicer mass/CG/MOI entries have at least traceable Stage 1 estimates.
- robot adapter mass/CG/MOI is recorded.
- target mass/CG/MOI and initial relative pose are defined.
- workspace and collision keepout checks have open/closed status.
- the selected robot dynamics file is confirmed as `reBot-DevArm_fixend.urdf`.
