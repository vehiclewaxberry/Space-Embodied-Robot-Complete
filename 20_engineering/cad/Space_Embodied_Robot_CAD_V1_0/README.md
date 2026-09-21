# Space Embodied Robot CAD V1.0

> `STATUS: ENGINEERING_VISUAL_ONLY`  
> `VERDICT: A4_ENGINEERING_VISUAL_COMPLETE_WITH_PHYSICAL_LIMITATIONS`  
> `SOLIDWORKS: 2024 SP5.0`  
> `NO_DYNAMICS / NO_CONTROL / NO_VLA / NON_FLIGHT`

## 打开入口

主总装：

`Assembly/Space_Embodied_Robot_V1_0.SLDASM`

建议先查看：

- `evidence/annotated/01_whole_vehicle_isometric_annotated.png`
- `evidence/annotated/04_three_bay_cutaway_review_annotated.png`
- `evidence/annotated/06_B601_link_joint_frame_q0_annotated.png`
- `evidence/annotated/09_evidence_state_colored_isometric_annotated.png`
- `evidence/annotated/10_independent_target_scene_annotated.png`

## 目录职责

| 目录 | 内容 |
|---|---|
| `00_Master_Skeleton/` | `S/M/A0/G/E_virtual` 和总体语义骨架 |
| `01_Primary_Structure/` | 12U 外框、纵梁、框环、设备板、外板和任务面 |
| `02_Robot_Mount/` | 160 mm 接口与设计提案加强/走线视觉特征 |
| `03_B601_Visual/` | accepted STL/URDF 派生的 10-link/9-joint q=0 视觉重构 |
| `04_Solar_Wings/` | `F_L/F_R` 展开参考 |
| `05_Sensor_Reference/` | 非物理、无数值的传感器语义参考 |
| `06_End_Effector_Reference/` | 非物理 `E_virtual` |
| `07_Rear_Service_Visual/` | 后舱服务模块视觉占位 |
| `08_Target_Scene_Reference/` | 与 active assembly 隔离的目标参考场景 |
| `10_Review_Overlays/` | 爆炸、三舱和安全显示评审装配 |
| `evidence/` | manifest、原生检查、inventory、视图与封存记录 |

## 使用边界

- B601 不是 vendor-exact CAD；供应商 STEP 未导入或复制。
- 所有质量/质心/惯量属性均不具动力学权威。
- `T_SB`、physical TCP、接触与抓取接口保持禁用。
- 传感器参考为零实体，不代表相机选型、FOV、标定或感知实现。模板导出的默认材料/“质量 0.00”字段没有材料、质量或制造权威。
- 独立 target scene 包含 target proxy；`TARGET_INCLUDED=FALSE` 只表示未进入 active engineering/operational assembly。场景没有组件间 mate/contact/rigid-lock；各组件相对场景坐标系静态放置不代表捕获。
- `DEPLOYED_REFERENCE_Q0` 记录到 10 处静态干涉，因此碰撞安全保持 `BLOCKED`。
- 禁止把本目录作为制造、强度、动力学、控制、Isaac/ROS、SAFE、RL、VLA 或飞行证据。

## 证据入口

- 原生文件哈希：`evidence/native_component_manifest.csv`
- 原生检查：`evidence/native_inspection.json`
- 文档/属性/特征/组件清单：`evidence/native_*_inventory.csv`、`evidence/assembly_component_inventory.csv`
- 清单校验：`evidence/inventory_validation.json`
- 原生视图哈希：`evidence/review_view_hash_manifest.csv`
- 带注释视图哈希：`evidence/annotated_review_view_manifest.csv`
- 最终封存：`evidence/evidence_seal_manifest.csv`

封存记录为 `43/43 HASH_MATCH`；seal manifest 自身 SHA-256 为
`dce2b66ac9f60a32329388c4579fec8d7174b7be3c1dfc60dccc716c7a8969f0`。
