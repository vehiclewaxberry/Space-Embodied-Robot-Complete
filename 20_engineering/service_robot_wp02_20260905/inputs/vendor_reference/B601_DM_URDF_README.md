# ReBot Arm DM Mechanical Description Package

<p align="center">
  <strong>
    <a href="./README_zh.md">简体中文</a> &nbsp;|&nbsp;
    <a href="./README.md">English</a>
  </strong>
</p>

This directory contains the self-contained B601-DM mechanical description resources. See the parent [`README.md`](../README.md) for the overall RS/DM differences and cross-engine reuse guidance.

```text
DM/
├── urdf/
│   └── ReBot_Arm_DM.urdf
└── meshes/
    ├── visual/             # Parts used only for URDF rendering and colors
    ├── collision/          # Complete URDF collision meshes
    ├── shared/             # Shared by URDF rendering and MuJoCo collision
    └── mujoco_collision/   # Segmented MuJoCo finger-collision meshes
```

- `urdf/ReBot_Arm_DM.urdf` is the current main DM model and defines both the arm and gripper.
- `meshes/visual/` contains 30 material-separated parts used only for URDF rendering and colors.
- `meshes/collision/` contains 10 complete URDF collision meshes.
- `meshes/shared/` contains four finger-carriage and travel-stop meshes shared by URDF rendering and MuJoCo collision.
- `meshes/mujoco_collision/` contains six MuJoCo collision meshes for the front, middle, and rear segments of both fingers.
- The URDF uses `../meshes/...` relative paths and does not depend on ROS package URIs. Copy the complete `DM/` directory to use it.
- The ROS 2 runtime model remains in `reBotArm_ros2_DM/src/rebotarm_bringup/description/`. Compare and synchronize the two locations after model updates.

For example, load it from the repository root with:

```python
from pathlib import Path

urdf_path = Path("Rebot_Arm_description/DM/urdf/ReBot_Arm_DM.urdf")
```
