# B601 Accepted Kinematic Chain

Status: `READ_ONLY_ACCEPTED_TRUTH_EXTRACT`

Source:
`20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf`

Source SHA-256:
`1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`

This report is a readable projection of `accepted_chain.json`; the URDF remains
the authority. Values below retain the source units and source decimal strings.
They are not re-estimated from CAD.

## Topology

- Root link: `base_link`
- Links: 10
- Joints: 9
- Revolute joints: 6
- Fixed joints: 1
- Prismatic joints: 2
- Accepted total mass: `4.6955559493429862 kg`
- CAD mass authority: `EXCLUDED`

## Joint contract

| Joint | Type | Parent | Child | Origin xyz (m) | Origin rpy (rad) | Axis | Lower | Upper |
|---|---|---|---|---|---|---|---:|---:|
| joint1 | revolute | base_link | link1 | -8.416E-05 0 0.08465 | 0 0 0 | 0 0 1 | -2.8 | 2.8 |
| joint2 | revolute | link1 | link2 | 0.020084 0.031625 0.05555 | -1.5708 0 0 | 0 0 -1 | -3.14 | 0 |
| joint3 | revolute | link2 | link3 | -0.264 0 0 | 0 0 0 | 0 0 1 | -3.14 | 0 |
| joint4 | revolute | link3 | link4 | 0.2426 -0.054 -0.001625 | 0 0 0 | 0 0 1 | -1.87 | 1.57 |
| joint5 | revolute | link4 | link5 | 0.078308 -0.0375 -0.03 | -1.5708 0 0 | 0 0 1 | -1.57 | 1.57 |
| joint6 | revolute | link5 | link6 | 0.023692 0 0.04 | 0 1.5708 0 | 0 0 1 | -3.14 | 3.14 |
| gripper_joint | fixed | link6 | gripper_link | 0 0 0.15971 | 0 -1.5708 0 | 0 0 0 | — | — |
| gripper_joint1 | prismatic | gripper_link | gripper_left | -0.042091 2.7531E-05 -1.3031E-05 | 0 0 -1.5708 | 1 0 0 | 0 | 0.0715 |
| gripper_joint2 | prismatic | gripper_link | gripper_right | -0.042091 -2.7531E-05 1.3031E-05 | 0 0 1.5708 | 1 0 0 | 0 | 0.0715 |

## Link mass and mesh contract

| Link | Accepted mass (kg) | Accepted visual mesh | Mesh SHA-256 |
|---|---:|---|---|
| base_link | 0.83660000 | meshes_b601_gripper/base_link.STL | 22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65 |
| link1 | 0.16130000 | meshes_b601_gripper/link1.STL | 9DB637A63D37BC2C6398EA5B8BA32FB54122C637D5D77DC134C8782839B654CD |
| link2 | 1.32660000 | meshes_b601_gripper/link2.STL | DEF0D9D82343DCCC1EFF0D9D5572ECA49B3C134DB9807CA12302B99D153DF65E |
| link3 | 0.83530000 | meshes_b601_gripper/link3.STL | CA14D73B5D63F352051F440F4CABC3989567F25EE9D19E7DD749F2D6F0D0561D |
| link4 | 0.52000000 | meshes_b601_gripper/link4.STL | 061909364F20BB387F9FF82CB80E506AF959142F9FBB4A39DC86FC8244EE768A |
| link5 | 0.38300000 | meshes_b601_gripper/link5.STL | 3A32006227C1F9DBC70E77E07055C61E3F195F1054D4D2EB480262F0873BF001 |
| link6 | 0.36630000 | meshes_b601_gripper/link6.STL | C586A7D0B8345D2CD32EAB7DFD2E334ABA56E83F582A6298D41BBF718F2EBEF1 |
| gripper_link | 0.181800159145243 | meshes_b601_gripper/gripper_link.STL | A826E164D420A6922E8AD5EE27813F39FA809F6E4FDF39B42FD8A59E7D12E847 |
| gripper_left | 0.0423278952416158 | meshes_b601_gripper/gripper_left.STL | C4E0DE70F776B3573D975A6EAAA746CCCBE57C2D5BB12501DA8889979D3AF268 |
| gripper_right | 0.0423278949561274 | meshes_b601_gripper/gripper_right.STL | 615B119C0BB97A032BADD5882144E4A2A50C905A3E071AF1FA28B83BFE9B1B65 |

## Spacecraft-frame mapping

The accepted extraction records:

- `R_SM = [[0,0,1],[0,1,0],[-1,0,0]]`
- Display mount-face track: `[198.0, 0.0, 0.0] mm`
- Dynamics `T_SM` track: `[185.25, 0.0, 0.0] mm`
- Explicit track delta: `12.75 mm`

Ruling: `DUAL_TRACK_EXPLICIT`; the 12.75 mm delta must not be hidden in a
joint origin.

## Claim limit

This is accepted digital kinematic and inertial truth only. It is not a
physical weigh-in, actuator qualification, manufacturing, structural, launch,
or flight authority.
