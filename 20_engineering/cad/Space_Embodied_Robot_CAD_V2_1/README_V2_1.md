# Space Embodied Robot CAD V2.1

## 当前状态

`V2.1 Reference-Grounded Mechanical Refinement` 已建立为独立 SolidWorks 2024 原生目录。
V2.0 终版封存清单现场复核为 `57/57 MATCH`，未被覆盖。

当前允许结论：

- 混合框—纵梁主结构、MID2 节点垫、前端 B601 扩散意图和分段侧板已进入原生 CAD。
- 左、右太阳翼具有独立子装配、DEPLOYED/STOWED 双表示和七个顶层任务状态。
- 根支座、铰链、弹簧、双保持/释放点、止挡和线束已经以零实体具名 reference 建档。

当前禁止结论：

- 根部机构 reference 不是实体机构设计，也不是可制造工程图。
- 未进行 FEA、动力学、接触、部署、机械臂工作空间/轨迹扫掠或视觉遮挡验证。
- 不得声称强度、刚度、碰撞安全、低冲击、部署可靠性、发射/部署器或飞行合规。

## 打开入口

顶层装配：

`Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM`

顶层任务状态：

- `STOWED`
- `DEPLOYED_NOMINAL`
- `DEPLOY_FAILED_BOTH`
- `L_FAIL`
- `R_FAIL`
- `PARTIAL`
- `SERVICE`

`PARTIAL` 因展开角仍为 UNKNOWN，左右翼实体表示均被抑制；它是场景入口，不是假定中间角。

## 证据入口

- `V2_1_DEVIATION_MANIFEST.yaml`
- `evidence/b4_1_00/v2_0_seal_recheck.json`
- `evidence/b4_1_verify/machine_check.json`
- `evidence/acceptance/acceptance_summary.json`
- `evidence/acceptance/A8_A20_contract_status.yaml`
- `evidence/review_views/review_view_manifest.json`

正式 Gate 以这些机器输出的最新时间戳为准。若 `machine_check.json` 或 acceptance summary
不是 PASS/CONDITIONAL 状态，禁止用目录存在或截图代替 Gate。

## 2026-07-25 B4-1 最终门禁

最终状态为 `B4_1_NATIVE_REFERENCE_CAD_BUILT_ACCEPTANCE_HOLD`。
验收结果为 `B4_1_ACCEPTANCE_HOLD`（退出码 `2`），计数为
`0 FAIL / 17 HOLD / 6 PASS`。这表示 V2.1 原生参考 CAD 已建立，但尚未满足
物理机构、工程图、制造或飞行释放条件。完整结论见
`B4_1_EXECUTION_REPORT.md` 与 `evidence/B4_1_GATE_STATUS.yaml`。

## 下一人工 Gate

物理太阳翼机构细化继续 HOLD，至少需要：

1. 项目自有根部机械 ICD 与实体包络；
2. 铰链、弹簧、止挡、保持释放和线束参数的 owner/evidence；
3. 全解析 B601 任务姿态扫掠与相机 frame/FOV；
4. 紧固件、工具轴、维修顺序与干涉证据；
5. C5 收拢包络语义签发；
6. 原生 SLDDRW/PDF 工程图包。
