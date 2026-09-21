# Route-C R95 Link2-B12 operational-collision local candidates

This isolated package builds twelve ordinary `parent_frame=link2` Route-C objects as STEP-first host-local collision candidates. It excludes all eight J3-carriage objects and modifies neither M01 system registry nor any predecessor package.

Primary geometry is one-root STEP in `link2@q1=q2=0`, millimetres. Runtime PLY/NPZ/STL sidecars are derived only from cold-reopened STEP and converted to metres exactly once. A side-effect-free adapter maps local geometry by

`p_S = T_S_A0 · T_A0_link2(q1,q2) · p_link2`.

The current exact 12-decimal execution mount and accepted URDF raw joint1/joint2 numbers are mandatory. Historical D6 mount reuse, placement reapplication, zero-filled as-built uncertainty, system-pair credit and inherited Link1-B6 credit are forbidden.

Pose evidence covers the full Cartesian grid `q1={-2.8,0,2.8}` × `q2={-3.14,-1.57,0}` (nine configurations). Independent numerical fault controls must reject both an adapter that ignores `q1` and one that reverses the `q1` sign.

Fresh-process evidence launches every child with `python -B` plus a fixed `PYTHONDONTWRITEBYTECODE=1`, `PYTHONHASHSEED=0`, `PYTHONUTF8=1` environment and requires zero package-local cache, bytecode, or temporary files both before and after replay. The pre-repair child-bytecode side effect is retained as zero-credit history in `07_reviews/LINK2_PRE_ROOT_REPLAY_NOT_CLEAN_PASS_V1.json`.

Only `05_results/LOCAL_CANDIDATE_GATE_V1.json` may summarize this package, and only within its stated local-candidate scope.
