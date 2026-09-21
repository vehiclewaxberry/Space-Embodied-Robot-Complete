# Servicer 6U Quick Layout Baseline v0

> Frame-notation migration (SSOT, 2026-07-09): arm base = mounting-face frame `M` (= reBot URDF base); servicer->mount is written `T_SM`. Old `B` (robot base) and `^S T_B` are compatibility aliases only. See `../04_mass_inertia_budget/coordinate_frame_definition_v0.md` §0.

## 1. Role

The 6U model is a quick verification layout for front-arm installation, camera field of view, target approach direction, and basic mass balance. It is not the competition main display model and does not promise complete accommodation of all subsystems.

## 2. Required Layout Rules

| item | requirement | Stage 1-C output |
|---|---|---|
| front task face | mount the reBot-equivalent manipulator and camera payload on the forward mission face | front-face layout sketch and adapter position |
| camera/robot alignment | keep camera FOV and robot capture workspace near-coaxial where practical | `T_SC`, `T_SM`, FOV clearance note |
| middle bus section | reserve OBC/C&DH, EPS/PMAD, battery, reaction wheel set, and IMU placeholders | volume placeholder table and mass entries |
| rear section | reserve communications, propulsion placeholder, and interface placeholder | volume placeholder table |
| side solar panels | keep side panels outside the robot maximum workspace as much as possible | stowed/deployed clearance checklist |
| mass properties | record estimated mass, center of mass, and inertia for each placeholder | mass inertia CSV entries |
| robot poses | define folded and deployed/reference poses for workspace checks | screenshot/export TODO list |

## 3. Scope Limits

- The 6U layout is a fast design and verification aid.
- It may omit detailed packaging of secondary harnessing, thermal hardware, and deployment mechanisms unless they affect the robot workspace.
- It must not be used to claim full mission accommodation.
- It must remain consistent with rail/contact-surface keepout rules until manual review resolves final dimensions.

## 4. Minimum CAD Entry Inputs

- Provisional 6U body envelope.
- Front task face with robot adapter and camera placeholder.
- Two side solar panel envelopes.
- Minimal bus placeholder stack for OBC/C&DH, EPS/PMAD, battery, RW, IMU.
- Basic mass/CG/MOI placeholders with `stage1_estimate` confidence.
