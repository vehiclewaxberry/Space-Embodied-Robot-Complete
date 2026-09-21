# arm_b601_v1 — mainline 6R arm (decision D-5-final, 2026-07-10)

Hybrid URDF: kinematics/meshes/gripper from `reBot_B601_DM_with_gripper.urdf`, inertial
set (base+link1..6) from `reBot-DevArm_fixend.urdf` (vendor-consistent ~4.5 kg self-weight;
the with_gripper masses are ~2x light = CAD export without motors). Total 4.6956 kg.
Full evidence chain + mount transform + task-mode taxonomy: `20_engineering/config/geometry/arm_b601_v1.yaml`.

Upstream: Seeed reBot-DevArm (hardware CERN-OHL-W-2.0, software Apache-2.0) — attributed
derivative for 10_research/competition use. Source files remain in
`80_third_party/vendor/reBot-DevArm (CM3: imported from external root, see hardware_step)` (the team's own arm project).

`meshes_b601_gripper/` (10 binary STL, ~27 MB) is copied here but left UNTRACKED pending
a git-LFS decision — dynamics (sim_05) needs only the URDF inertials, not the meshes.
