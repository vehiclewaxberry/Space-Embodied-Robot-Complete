# M01 system collision registry V1

This package closes the bookkeeping ambiguity around the M01 collision scene; it does **not** claim that the scene is collision-safe.

The deterministic builder imports and hash-checks the current platform, B601, Solar R2 and Route-C candidate sources. It emits:

- `M01_SYSTEM_COLLISION_REGISTRY_V1.json`: 150 known active collision objects with representation, frame, state and authority limits;
- `M01_PAIR_COVERAGE_V1.csv`: every one of the 11,175 unordered object pairs exactly once;
- `M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json`: the fail-closed machine verdict.

The object split is `F=4` fixed platform objects, `A=10` arm/gripper objects, `S=6` selected-state Solar leaves, `R=121` Route-C physical parts and `C=9` logical bundle envelopes. Missing ARM HDRM, Solar mechanism hardware, target/interface, sensors, fasteners and complete bus external geometry are explicitly registered as missing; they are not hidden by the 150-object count.

Ten Solar R2 hinge/HDRM envelope solids are also registered as conditional `K` virtual-keepout candidates. They are deliberately outside the current 150-object pair universe because the Solar/latch/HDRM state is unbound. Activating any one of them requires a new registry version that enumerates every `K`-involving pair before search; the old 22-solid combined Solar field is never a legal single-state collider.

Only the nine adjacent kinematic pairs inherited from the frozen mechanical contract are active pair-wide exceptions. `gripper_left` versus `gripper_right` remains enabled. The 55 expanded records derived from the 15 local cable/serving-hardware windows remain candidates because their surface patches and runtime predicates are incomplete.

The builder independently reads the old V9F evaluator and rejects inheritance of eight non-J4 segment-wide serving-hardware sets (91 segment/part memberships) and the fixed-part/own-host whole-object skip. Those behaviors must be replaced by bounded section, arclength, station, clamp/bore-axis and exact surface-patch predicates.

The 15 normalized local-window definitions live in `M01_LOCAL_CONTACT_WINDOWS_SOURCE_V1.json`. This registry-owned, hash-pinned source records their original evaluator/centerline/clamp provenance but does not depend on the downstream ODR-60 preflight document. The dependency direction is therefore one-way: frozen engineering sources → system registry → aggregate collision gate → preflight. No circular hash binding is permitted.

The accepted URDF remains the kinematics/topology authority. Its raw `base_link.STL` is explicitly banned from every collision object because it contains the owner-deleted desktop plate. The sibling `base_link_proxy_v2/` STEP-first package is the only currently permitted operational replacement path. Its local geometry gate is PASS, but that status does not evaluate or allow any system object pair.

Reproduce from the workspace root:

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/build_system_collision_registry.py --check
python -m pytest -q 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/test_system_collision_registry.py
```

Expected verdict: structural registry complete, 11,175 pairs enumerated, 9 excepted and 11,166 unassessed fail-closed. `pre_search_ready=false`, `next_stage_authorized=false`, and no path-search or release credit is created.
