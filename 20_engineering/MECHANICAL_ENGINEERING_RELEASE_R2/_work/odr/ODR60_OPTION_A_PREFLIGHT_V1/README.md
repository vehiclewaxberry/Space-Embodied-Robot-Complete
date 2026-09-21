# ODR-60 Option-A pre-execution readiness package

This directory prepares the fixed-endpoint M01 path study without starting it.
It creates no q-path, waypoint, trajectory, CAD, mesh, URDF or Release artifact.

## What is now machine-checked

- All 35 authority-pin occurrences match live files.
- The accepted B601 description parses as 10 links and 9 joints: 6 revolute plus 2 gripper prismatic joints.
- STOW and RELEASE_CLEAR match the M01 contract exactly and both pass the frozen 0.25-degree robust joint-limit inset.
- The only inherited arm self-collision exclusions are the 9 adjacent-link pairs in the mechanical contract; left and right fingers remain collision-enabled.
- The collision universe now contains 150 active objects and all 11,175 unordered object pairs. Only the 9 frozen adjacent-link pairs are exceptions; 11,166 pairs remain `UNASSESSED_FAIL_CLOSED`.
- The 15 existing Route-C cable-to-serving-hardware windows expand to 55 candidate object-pair records with exact segment, section, cumulative arclength and clamp witness fields. They are not active exceptions because surface patches and runtime predicates are still absent. Eight legacy segment-wide sets (91 segment/part memberships) and the fixed-own-host whole-object skip are explicitly rejected.
- Ten Solar R2 virtual keepout candidates remain outside the active pair universe until the mission state, latch and HDRM bindings are supplied; activating any one requires a new registry version and complete `K`-pair enumeration.
- Unknown, missing, empty, non-finite, hash drift, wildcard and caller-supplied exemptions all remain ABORT.

## Why search is still not allowed

The missing Owner selection is only one blocker. The current M01 contract defines six arm coordinates, while the operational model has eight movable coordinates. Both gripper positions are absent. Solar R2 and its latch state, ARM HDRM release snapshots, the target-presence state and the complete bus scene are also not bound.

The legacy V9F mesh pack consumes the accepted URDF `base_link` STL. WP11-F-01 proves that mesh still contains a deleted desktop base plate, so it cannot be used as operational clearance or self-collision truth. The new 150-object registry does not consume that raw mesh, so the phantom-plate conflict is contained.

The first replacement attempt remains an immutable negative result: the filtered B50 STEP has 69 solids, only 67 pass BRepCheck and 11 of 3,116 non-zero-area faces cannot be triangulated. The active V2 replacement closes that local geometry defect without changing the accepted URDF: 66 exact BRep solids are preserved, while the DM-J4340P anomaly region and one thin-plate anomaly are replaced by strict tolerance-aware containing AABBs. The emitted STEP contains 68/68 valid solids; the cleaned operational mesh has 207,490 triangles, zero boundary edges, zero non-manifold edges and zero orientation mismatches. Independent validation and a fresh-process replay pass. This is only a local collision-geometry PASS; no object pair, path or release is thereby accepted.

There is no installed OMPL/MoveIt2/FCL stack. This is not fatal: after authorization and input closure, a deterministic NumPy/SciPy bidirectional RRT-Connect can use a conservative low-cost broadphase, with only one finalist sent to an isolated exact-evaluator adapter and independent FreeCAD B-rep replay. However, the existing exact evaluator needs about 17.6 seconds for one observed pose and cannot be used inside a sampling-planner loop.

The existing 0.25-degree sweep is finite sampling, not a continuous-collision proof. A final candidate needs recursive edge subdivision plus a conservative bound on relative body motion; any interval without a valid bound remains UNKNOWN.

## Memory policy

Execution must remeasure available physical memory immediately before launch. At least 6 GiB available is the nominal gate. If less is available, the prior project policy requires a fresh run id, a window no longer than 7200 seconds and the exact Owner risk confirmation:

```text
ACCEPT_SINGLE_RUN_LOW_MEMORY_RISK
```

The resulting record must say `OWNER_OVERRIDE_LOW_MEMORY` while keeping `memory_gate_passed=false`. A prior override cannot be reused, and only a single process may run under the override.

## Reproduction

From the workspace root:

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/validate_odr60_option_a_preflight.py
python -m pytest -q 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_PREFLIGHT_V1/test_odr60_option_a_preflight.py
```

Expected status is an integrity PASS combined with `pre_search_ready=false`. The raw-mesh conflict is contained and the V2 local proxy geometry passes, but 11,166 unassessed pairs, missing scene-state bindings, incomplete ACM/backend/continuous-edge authority, absent Owner branch selection and fresh runtime memory admission remain blockers.

This preflight package itself still creates no CAD, trajectory or URDF. It hash-binds the STEP/NPZ/STL/receipt/validation emitted by the sibling `base_link_proxy_v2/` package. The accepted URDF remains byte-unchanged. A deterministic CAD snapshot was created and inspected there; the optional CAD Viewer handoff could not start because the installed viewer package lacks the skill-required `agent:start` script, so no substitute server or port was invented.
