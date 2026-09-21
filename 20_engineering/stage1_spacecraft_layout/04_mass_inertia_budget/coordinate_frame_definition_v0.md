# Coordinate Frame Definition v0 — Single Source of Truth (SSOT)

> Doc role: coordinate-frame **single source of truth** | Type: reference / interface baseline
> Language: English working doc (key terms bilingual)
> Version: v0 | SSOT frozen: 2026-07-09 (added `M`/`D` frames; adopted `S/B/M/T/D/C` primary naming; unified `T_XY` notation)
> Rule: every CAD / URDF / simulation script / report **references this file only** for frame and transform definitions. No other file may define its own coordinate frames — they cite this file. Values here may be `TBD`; the *definitions, symbols, and conventions* are frozen.

---

## 0. Migration note (v0 → SSOT) — read this first

Frame letters were realigned to the project frame table (`S/B/M/T/D/C`). Old usages are demoted to **compatibility aliases** — do not use them as the primary symbol.

| new (primary) | meaning | old / deprecated alias | consequence |
|---|---|---|---|
| `S` | servicer geometric / body frame (CAD, layout, mass properties) | `S` (unchanged) | — |
| `B` | servicer **free-flyer / mother-body base** frame (multibody base for GJM/RNS/SPART) | previously folded into `S` | NEW distinct role; `T_SB` = S→B |
| `M` | **arm mounting-face** frame = reBot URDF base reference | old `B` "robot base frame" | old robot-base `B` is now `M`; old `^S T_B` ≡ new **`T_SM`** |
| `T` | target (failed satellite) body frame | `T` (unchanged) | — |
| `D` | **debris / upper-stage** body frame | (new) | NEW |
| `C` | camera optical frame | `C` (unchanged) | — |
| `E` | end-effector / capture-tool frame | `E` (unchanged) | retained; arm kinematics `T_ME(q)` |
| `I` | inertial / world frame | `I` (unchanged) | retained; Stage 2 dynamics |

> ⚠️ **The transform historically emphasized as `T_SB` (servicer → robot base — the mechanical-to-dynamics bridge) is renamed `T_SM`** under this SSOT, because the robot mount/base is now `M`. `T_SB` now means servicer body → free-flyer base. Files still reading "`T_SB` = servicer to robot base" are using the deprecated alias and are to be migrated to `T_SM` (see §7 consumers). This is the one consequential relabeling from the frozen scheme.

---

## 1. Frame summary (primary `S/B/M/T/D/C`, plus retained `E/I`)

| frame | definition | origin | axes convention (right-handed) | primary consumers |
|---|---|---|---|---|
| `S` | servicer body/geometry frame for layout, CAD, mass properties | servicer CAD reference point (reconcile with geometric center & CoM, §4) | `+X_S` rear service bay → front task bay; `+Y_S` toward right solar-panel side; `+Z_S` completes RH | servicer CAD, mass budget, layout, thruster/RW placement |
| `B` | servicer free-flyer / mother-body **base** frame (multibody floating base) | servicer dynamics reference point (default: CoM; else documented) | aligned with `S` unless explicitly documented; `T_SB` records any offset | Basilisk free-flyer, SPART/GJM/RNS base body |
| `M` | arm **mounting-face** frame = adapter flange datum **and** reBot URDF base reference | adapter mounting-plate datum / bolt-array center | `+Z_M` mount-face normal, toward arm reach direction; `+X_M` along task-face / main bolt array | robot_mount_adapter, reBot URDF base, workspace |
| `T` | target (failed satellite) body frame | selected target model reference point | target-specific RH convention (document per model) | target pose, grasp point, target inertia, collision envelope |
| `D` | debris / upper-stage body frame | debris primitive reference point (e.g., cylinder axis mid-point) | RH; `+Z_D` = nominal tumble/symmetry axis (document per case) | tumble dynamics, debris capture sim, contact |
| `C` | camera optical frame | optical center of main vision sensor | optical-axis convention fixed by camera model before CAD export (state `+Z_C` = boresight) | pose estimation, FOV/occlusion, visual servo |
| `E` | end-effector / capture-tool frame | gripper / capture-tool reference point | inherited from reBot URDF + tool definition | grasp pose, pre-grasp, workspace envelope |
| `I` | inertial / world frame | free-flyer simulation world reference | inertial RH convention | Stage 2 dynamics propagation, trajectory plots |

---

## 2. Notation convention (unified — frozen)

- **Primary form `T_XY`**: homogeneous transform expressing frame `Y` in frame `X`; maps a point `p_Y` to `p_X = T_XY · p_Y`. Read as "from `Y` to `X`" (matches the project frame table).
  ```text
  T_XY = [ R_XY   p_XY ]   with p_X = T_XY · p_Y
         [ 0 0 0    1  ]
  ```
- **Deprecated (compatibility only, never the working symbol)**: leading-superscript `^X T_Y` (≡ `T_XY`), and `Y_to_X` / `B_to_S` word forms. If encountered in older files, translate to `T_XY`.
- Units: SI — meter, kilogram, kilogram·meter² (`kg m^2`), radian (or explicitly documented degree convention). All frames right-handed. Always state whether a rotation is a matrix, quaternion, or roll-pitch-yaw, and name the frame of every vector quantity.

---

## 3. Primary transforms (SSOT — the only transform symbols in use)

| transform | expresses `Y` in `X` (from `Y` to `X`) | minimum fields | priority | downstream use |
|---|---|---|---|---|
| `T_SB` | S → B: body frame to free-flyer/mother base (default identity or CoM offset) | translation, rotation, convention, source, confidence | P0 | GJM/RNS multibody base, Basilisk free-flyer base |
| `T_SM` | S → M: body frame to arm mounting-face / URDF base — **the mechanical-to-dynamics bridge (old `T_SB`)** | translation, rotation, convention, source, confidence | P0 | adapter definition, arm base placement, coupled inertia |
| `T_ME(q)` | M → E: arm base to end-effector, from `reBot-DevArm_fixend.urdf` + joint state `q` | computed from URDF + joint angles | P1 | workspace, pre-grasp, capture pose |
| `T_SC` | S → C: body to camera | translation, rotation, optical-axis convention, FOV reference | P0 | perception, camera occlusion, visual-servo narrative |
| `T_ST` | S → T: body to target initial relative pose | initial relative pose, target type, scenario name, source | P1 | Stage 2 initial condition, report figures |
| `T_SD` | S → D: body to debris initial relative pose | initial relative pose, tumble case, angular rate ref, source | P1 | Stage 2 tumbling-target IC, capture-corridor sim |
| `T_IS` / `T_IB` | I → S / I → B: world to servicer body / base | initial attitude & position, source | P1 | Stage 2 propagation, trajectory plots |

> A small change in `T_SM` (arm mount placement) changes the coupled inertia and base-reaction response, so it must be **exported and reviewed with the adapter model**, not guessed after CAD begins. `T_SB` fixes the multibody base and must be single-valued (see the `B` "与 S 关系必须唯一" requirement).

### 3.1 `T_SM` numeric freeze — **nominal_frozen_v1** (2026-07-10, decision D-2)

Definition being frozen: **`^S T_M` — the pose of the arm mounting-face frame `M` in the
servicer body frame `S`** (i.e. `T_SM` maps coordinates of a point expressed in `M` into `S`:
`p_S = R_SM · p_M + t_SM`). Both frames right-handed. `R_SM` is a **passive frame-to-frame
rotation matrix whose COLUMNS are the `M` axes expressed in `S`**.

```
t_SM = [185.25, 0, 0] mm      (expressed in S; = outer datum face of the 160x160 adapter
                               flange on the +X_S front task face, decision D-1)
R_SM = R_y(+90 deg)  =  [[ 0, 0, 1],
                         [ 0, 1, 0],
                         [-1, 0, 0]]
axes: +Z_M = +X_S (mount-face normal = arm reach & target-approach direction)
      +Y_M = +Y_S
      +X_M = -Z_S   <- note sign: exact matrix supersedes the loose "+X_M along +Z_S"
                       wording in servicer_12U_v0.json (bolt-array line is sign-agnostic)
```

Tool-specific expressions (all equivalent, all SI in sims):
- **URDF** (`<origin>` of the mount fixed joint): `xyz="0.18525 0 0" rpy="0 1.5707963 0"`
  (URDF rpy = extrinsic fixed-axis X-Y-Z; pure +90° about Y).
- **Python/scipy**: `Rotation.from_euler('y', 90, degrees=True)`; quaternion
  `[w,x,y,z] = [0.70710678, 0, 0.70710678, 0]` (scalar-first).
- **SolidWorks**: frame `M` = reference CS on the adapter flange outer face,
  origin at face centre; axis Z along face normal (+X_S), axis Y = +Y_S.

Status: `nominal_frozen_v1` — value read from existing CAD (`servicer_12U_v0.json
features.mount_face_M`); it is a design nominal, NOT a measured value. 6U variant
(origin [191,0,0], `servicer_6U_v0.json`) is off-mainline and does not share this freeze.
Known legacy conflict: `reBot_arm_v0_min.urdf` extends along `+X_M` — marked **legacy**;
all new arm models (7-DOF skeleton) must take zero-config reach along `+Z_M`
(see `20_engineering/stage1_spacecraft_layout/06_reviews/geometry_audit_decisions_v1.md`, D-2/D-5).

---

## 4. Servicer reference points

| reference point | meaning | Stage 1-C treatment | maps to |
|---|---|---|---|
| CAD origin | geometric modeling origin of the CAD assembly | may differ from CoM; must be recorded | origin of `S` |
| geometric center | envelope center of the servicer body | for sketches; not necessarily a dynamic reference | expressed in `S` |
| center of mass (CoM) | mass-weighted center after components assigned | exported via mass-inertia CSV | default origin of `B` |
| dynamics reference point | free-flyer base reference used in Stage 2 | mapped to `B`; `T_SB` records S→B offset | origin of `B` |

---

## 5. Sign and unit rules

- SI units: meter, kilogram, `kg m^2`, radian (or documented degree convention).
- Right-handed coordinate frames only.
- State whether rotations are matrices, quaternions, or roll-pitch-yaw.
- Do not mix body-fixed and inertial-frame quantities without naming the frame.
- Inertia tensors must state their reference point and axes; inertia about different reference points must not be mixed without the parallel-axis transform (see mass-inertia notes).

---

## 6. Scenario frames (`T`, `D`) — Stage 2 hand-off

- `T_ST` and `T_SD` are Stage 1-C outputs / Stage 2 inputs; they remain `TBD` until the scenario matrix and target/debris models provide traceable entries.
- Target (`T`) and debris (`D`) inertia are **self-defined / estimated**, never claimed as measured (see risk `RA-003`, `R-014`). Record `frame`, `reference_point`, `confidence` for each.

---

## 7. Consumers — files that must reference this SSOT (not redefine frames)

| file | current usage | required alignment |
|---|---|---|
| `03_.../layout_icd_lite_v0.md` | redefined the same frames | reference this file; keep only the interface-field contract |
| `03_.../robot_mount_adapter_requirements.md` (+ `_v0` en) | defines `S`/`M`/`B`(=robot base) and `^S T_B` | `B`(robot base) → `M`; `^S T_B` → `T_SM`; cite this file for `S`/`M` |
| `03_.../servicer_12U_layout_requirements.md`, `servicer_6U_layout_requirements.md` | restate "reBot base relative to body" | use `T_SM` (arm mount) and cite this file |
| `04_.../mass_inertia_budget_notes.md` (+ `_v0` en), `mass_inertia_budget_v0_template.csv` | `frame`/reference-point wording | every object row carries `frame` (from this table) + `reference_point`; see notes |
| `05_.../collision_avoidance_requirements.md`, workspace checklists | clearance vs frames | cite `M`/`E`/`T`/`D` from this file for envelopes |
| Stage 2: Basilisk / SPART / 42 / SmallSatSim inputs | consume `T_SB`,`T_SM`,`T_ST`,`T_SD`,`T_SC` | import symbols verbatim from this file |

> This file is the judgment/definition baseline. Migrating the consumer files (esp. the `B`→`M` and `T_SB`→`T_SM` relabel) is a follow-on step, to be confirmed and done on this branch after review.
