# Baseline Truth Hierarchy

## Priority

1. Accepted B601 URDF and its pinned package hashes:
   - topology;
   - link/joint names;
   - parent-child relationships;
   - joint type, axis, origin and limits;
   - link mass, centre of mass and inertia.
2. Frozen project interface/frame contracts and current machine Gates.
3. Frozen V2.2/V2.2_NATIVE native CAD evidence:
   - spacecraft layout;
   - mount/load-path design intent;
   - stow-support and solar-root design intent;
   - explicit negative results and UNKNOWN fields.
4. Pinned vendor B601 STEP and vendor documentation:
   - visual exterior geometry reference only.
5. V2.2 donor STEP/native subassemblies:
   - layout and engineering reference only.
6. Images, papers and undimensioned proportions:
   - design-intent reference only.
7. New B5.0 engineering candidates:
   - provisional geometry until their own Gates pass.

## Authority separation

| Quantity | Controlling source | Forbidden substitution |
|---|---|---|
| B601 kinematic tree | accepted URDF | vendor STEP or CAD appearance |
| B601 model mass/CoM/inertia | accepted URDF | SolidWorks default density or volume-fit solids |
| B601 visual exterior | pinned vendor STEP/accepted meshes | arbitrary industrial-arm styling |
| spacecraft display layout | frozen V2.2 evidence | silent use of the dynamics envelope |
| spacecraft dynamics frame | current project frame/config contract | native display mount face |
| materials/loads/fasteners/HDRM | `UNKNOWN/TBD` until signed | plausible catalogue assumptions |

## Preserved conflicts and negative results

- 366 mm native display length versus 340.5 mm dynamics/display history;
- `MOUNT_FACE_X=198 mm` visual track versus `T_SM=185.25 mm` dynamics/PDR track;
- 25° clock approval wording conflict;
- O13 stow vector remains `CANDIDATE_HOLD`;
- `STOW_Z_LIMIT=UNKNOWN`;
- C5 `238.3 mm > 226.3 mm`;
- solar-root lower-bound width `302.3 mm > 226.3 mm`;
- structural loads, materials, joints and fasteners remain unknown;
- physical TCP, F/T hardware, camera selection, contact and HDRM qualification remain open.

No candidate CAD feature may close these items by hiding, suppressing, thinning, moving or assigning an unsupported default.
