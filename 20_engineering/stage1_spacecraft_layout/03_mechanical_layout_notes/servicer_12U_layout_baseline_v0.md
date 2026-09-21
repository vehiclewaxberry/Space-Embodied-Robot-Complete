# Servicer 12U Layout Baseline v0

> Frame-notation migration (SSOT, 2026-07-09): arm base = mounting-face frame `M` (= reBot URDF base); servicer->mount is written `T_SM`. Old `B` (robot base) and `^S T_B` are compatibility aliases only. See `../04_mass_inertia_budget/coordinate_frame_definition_v0.md` §0.

## 1. Baseline Positioning

The Stage 1-C main scheme uses a 12U display-type servicer as the primary competition visual model. It supports three report narratives: target capture, on-orbit servicing, and debris removal. The CAD work has not been completed in this stage; this document only fixes the modeling input baseline.

## 2. Compartment Layout

| compartment | provisional function | required placeholders | design intent |
|---|---|---|---|
| front task bay | mission interaction face | reBot-equivalent manipulator, robot mount adapter, camera payload, target-facing markers | keep robot workspace and camera FOV near-coaxial where possible |
| middle bus bay | platform bus | OBC/C&DH, EPS, PMAD, battery, reaction wheel set, IMU | concentrate major bus masses near the servicer reference region and later center-of-mass estimate |
| rear service bay | service and support face | communications, propulsion placeholder, thermal interface placeholder, antenna placeholder | separate plume/antenna/thermal placeholders from the robot capture workspace |
| side deployables | power generation and display | left and right solar panels | avoid the robot arm maximum workspace and camera line of sight |

## 3. Reference Deployment System

- The provisional reference system is `rail-reference`.
- The rail-reference choice is temporary and must be revisited after Appendix B manual drawing review.
- If manual review shows that rail-reference is unsuitable for the 12U display model, Stage 1-C must record the switch and update the keepout definitions.

## 4. ASCII Layout Sketch

Provisional body axes:

```text
X_S: rear service bay -> front task bay / target approach
Y_S: left-right solar panel direction
Z_S: completes right-hand frame
```

Top view:

```text
Y_S+
  ^
  |        [solar_panel_left - stowed/deployed envelope TBD]
  |
  +------------------------------------------------------------+
  | rear service bay | middle bus bay       | front task bay   |
  | comms/propl/TCS  | OBC EPS batt RW IMU  | camera + reBot   | --> X_S+
  +------------------------------------------------------------+
  |
  |        [solar_panel_right - stowed/deployed envelope TBD]
  v
Y_S-
```

Front task face:

```text
             Z_S+
              ^
              |
        +-------------+
        | camera FOV  |
        |   [C]       |
        |             |
        | robot [M]   |
        +-------------+
              |
              +----------> Y_S+
```

## 5. Stage 1-C Outputs Required

- 12U external envelope drawing and manual dimension review status.
- Front task bay robot folded pose, pre-grasp pose, and maximum extension envelope.
- Side solar panel stowed/deployed envelope and robot clearance view.
- Camera FOV and robot workspace relative view.
- Mass, center of mass, and inertia estimate table entries for all major placeholders.
- `T_SM` (servicer body -> arm mounting-face; old `T_SB`) and `T_SC` definitions with source and confidence.

## 6. Report and Dynamics Traceability

- This layout must support the later `naive planning vs RNS planning` comparison by exporting geometry and inertia parameters.
- This layout must support the GJM/RNS base reaction suppression figures, especially base attitude disturbance and end-effector tracking plots.
- No statement in this document means that a finished CAD model, verified mass property, or simulation result already exists.
