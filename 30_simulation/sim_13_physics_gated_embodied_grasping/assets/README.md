# Asset boundary

`BOOTSTRAP_TEST_FRAME_TREE.json` is a test-only frame graph used to exercise
the strict loader before the mechanical package is published.  It is not a
substitute for `SYSTEM_FRAME_TREE.yaml` from the mechanical digital thread.

The production sim_13 gate requires a `MECH_RL_INTERFACE_V1.yaml` that binds:

- the accepted B601 URDF;
- whole-system visual and collision meshes;
- the production system frame tree;
- accepted mechanical configurations;
- the M3R mount transform;
- gripper contact and camera reserve frames;
- keep-out definitions;
- accepted-URDF mass and inertia authority.

