# Stage 1-C CAD Modeling Entry Plan

## 1. CAD Start Conditions

CAD modeling may begin when the following inputs are present:

- Stage 1-B+ standard extraction is available and P0 constraints are listed.
- Appendix B manual dimension review has a working table, even if values are still open.
- The provisional reference is set to `rail-reference`, with a rule to switch if manual review finds it unsuitable.
- ICD-lite defines `S`, `B`, `C`, `E`, `T`, `I`, `T_SB`, `T_SC`, and `T_ST` fields.
- Mass/inertia CSV has all major placeholder rows.
- Dimension, deployable, workspace, and collision checklists exist.
- The work scope is limited to CAD/layout preparation; no dynamics simulation is run.

## 2. Modeling Order

1. Create the 12U main servicer body envelope and rail/contact keepout overlay.
2. Split the body into front task bay, middle bus bay, and rear service bay.
3. Add internal placeholders: OBC/C&DH, EPS/PMAD, battery, reaction wheel set, IMU.
4. Add rear placeholders: communications, propulsion, antenna, thermal-control area.
5. Add side solar panel stowed/deployed envelopes.
6. Add robot mount adapter placeholder and frame marker for `B`.
7. Add camera mount placeholder and frame marker for `C`.
8. Add reBot-equivalent folded, pre-grasp, and maximum-extension envelopes as references.
9. Add target model placeholders and collision envelopes.
10. Export screenshots and mass/inertia entries for review.

## 3. Naming Convention

| object class | suggested prefix | example |
|---|---|---|
| servicer assembly | `servicer_12U_v0` | `servicer_12U_v0_main_assembly` |
| bay placeholder | `bay_` | `bay_front_task_v0` |
| subsystem placeholder | `ph_` | `ph_battery_pack_v0` |
| robot adapter | `adapter_` | `adapter_rebot_mount_v0` |
| frame marker | `frame_` | `frame_S_v0`, `frame_B_v0` |
| keepout volume | `ko_` | `ko_robot_workspace_v0` |
| target model | `target_` | `target_failed_12U_v0` |

## 4. Minimum Completion Definition

Stage 1-C CAD v0 is minimally complete when it provides:

- 12U exterior envelope with rail/contact keepout overlay.
- front/middle/rear compartment split.
- robot adapter and camera placeholders with `T_SB` and `T_SC`.
- left/right solar panel stowed/deployed envelopes.
- folded and maximum robot workspace envelopes.
- at least three target model placeholders.
- mass/inertia CSV entries with source and confidence.
- screenshots for dimension review, workspace clearance, and keepout zones.

## 5. Export Requirements

Required exports:

- screenshots for report and review: front, side, top, folded robot, deployed robot, FOV, keepout overlay.
- STEP or equivalent neutral geometry export when a CAD model exists.
- STL or mesh export only for visualization or collision proxy when needed.
- mass properties report with material, density, mass, COM, and inertia tensor.

## 6. Mass/Inertia Recording Method

- Record CAD material and density before exporting mass properties.
- Export component mass, COM, and inertia into `mass_inertia_budget_v0_template.csv`.
- Mark every row with source and confidence.
- If a row is an estimate, keep it labeled as `stage1_estimate` and do not write it as measured.
