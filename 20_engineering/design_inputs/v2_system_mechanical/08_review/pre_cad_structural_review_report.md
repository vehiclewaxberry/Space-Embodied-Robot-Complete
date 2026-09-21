# V2 预 CAD 结构审查报告

> `REVIEW_ID: COMP-PROT-03-A4-B2.5-STRUCTURAL-REVIEW`  
> `STATUS: INPUT_PACKAGE_COMPLETE_WITH_OPEN_PHYSICAL_BLOCKERS`  
> `REVIEW_MODE: DOCUMENT_AND_CONTRACT_ONLY`  
> `CAD_AUTHORING_AUTHORIZED: false`  
> `FEA_OR_PHYSICAL_QUALIFICATION_PERFORMED: false`

## 1. 审查目的

本审查只判断 V2 System Mechanical Design Input Package 是否已经把“任务需求—构型—接口—舱段—质量所有权—未知量—CAD 建设顺序”串成可审计的预 CAD 输入链。它不判断结构是否满足强度、刚度、模态、热、发射或在轨载荷要求。

## 2. 输入

- A4-B2 V2 mechanical architecture contract；
- 当前项目 geometry/profile、frame SSOT、accepted B601 URDF 和 A4-B1 V1.0 evidence seal；
- 本包的需求、构型、机械 ICD、接口登记、volume owner、质量所有权、未知量和 Master Skeleton 合同；
- 本地 spacecraft mechanical design knowledge base；
- 已记录的 `DEPLOYED_REFERENCE_Q0` 十处静态干涉负结果。

## 3. 结构审查结论

| 审查对象 | 当前结论 | 状态 | 允许进入 B3 的内容 | 仍禁止的表述或动作 |
|---|---|---|---|---|
| 系统任务边界 | 已区分任务需求、展示场景和已证明能力 | `EVIDENCE_BOUND` | 用作 CAD 架构目标 | 宣称已完成自主捕获、VLA 或在轨验证 |
| 12U 主体包络 | 项目显示 profile 为 `340.5 × 226.3 × 226.3 mm` | `EVIDENCE_BOUND / NON_FLIGHT_DISPLAY_ONLY` | 建立项目 profile 驱动的 Master Skeleton | 宣称符合标准 12U 或具体 deployer |
| 标准冲突 | NASA 2026 SOA 参考尺寸与项目显示 profile 不一致，CDS Appendix B 尚需人工图纸复核 | `UNKNOWN_BLOCKED` | 在图纸和属性中保留 profile 标签 | 把参考尺寸静默替换为项目真值 |
| 三舱构型 | 已有 rear/mid/front 三个 volume owner 和边界平面 | `EVIDENCE_BOUND / DERIVED` | 建立舱段骨架和占位包络 | 由占位包络推断真实设备、热或线束可行性 |
| 主承力拓扑 | 四纵梁、四框环、两舱段边界甲板是继承自 A4-B1 的视觉拓扑提案 | `DESIGN_PROPOSAL` | 建立可抑制的拓扑骨架 | 由此宣称材料、截面、板厚、强度或模态合格 |
| 主载荷路径 | “任务面/机器人安装区—框环/纵梁—主体边界”的概念链可描述 | `LIMITED` | 建立 load-path reference geometry 和 owner | 宣称载荷路径已完成定量闭合 |
| 机器人安装接口 | `T_SM`、安装面和适配器占位几何已绑定，`T_MA0` 为 identity contract | `EVIDENCE_BOUND / LIMITED` | 建立 mount 与 adapter 子装配骨架 | 猜测螺栓、材料、预紧、载荷、刚度和寿命 |
| B601 数字接口 | accepted 10-link/9-joint URDF 与分项质量可作为受限输入 | `EVIDENCE_BOUND / NOT_PHYSICAL_TRUTH` | 建立只读插入坐标和 envelope/reference | 修改 URDF、声称供应商精确 STEP 或制造级结构 |
| 展开附件 | 左右根坐标 `F_L/F_R` 已绑定 | `LIMITED` | 建立 hinge/root reservation | 宣称锁定、释放、线束、展开动力学或碰撞安全完成 |
| 感知与末端接口 | 只保留 volume/interface owner；`T_SC`、`T_E_TCP` 仍为空 | `UNKNOWN_BLOCKED` | 建立禁入区和接口占位 | 创建物理相机、FOV、接触、抓取或主动目标装配 |
| 设备布置 | EPS/电池、算力、ADCS、通信、推进、热控等已有 owner，但无合格硬件包络 | `PLANNED / LIMITED` | 建立带来源标签的可替换 volume reservations | 把通用方块升级为硬件选型或工程闭合 |
| 维护性 | 面板拆卸、托盘抽取和工具接近方向已有设计提案 | `DESIGN_PROPOSAL` | 生成 serviceability review views | 宣称已验证人机工效、工具净空或装配顺序 |
| 质量所有权 | 每个质量项有唯一 owner；已有数值与未知项已分离 | `LIMITED` | 继承现有 source value，并给新增件保持 null | 将 provisional 数值称为称重真值，或计算整星 CoM/惯量 |
| 负结果 | `DEPLOYED_REFERENCE_Q0` 十处静态干涉保留 | `NEGATIVE_RESULT` | 在 B3 设置专门干涉复核视图 | 隐藏、重命名为通过或宣称全局碰撞安全 |
| V1.0 | 作为密封视觉基线保留 | `FROZEN` | 只读参照和差异对照 | 覆盖、重建或把 V2 写回 V1.0 |

## 4. 关键未闭合物理问题

以下问题阻止“工程结构已完成”或“可制造/可发射”的结论，但不阻止在人工批准后开始受控的 B3 参数化 CAD：

1. 项目显示 profile 与参考 12U 标准尺寸冲突；
2. deployer、rail/tab、发射边界和 Appendix B 图纸尚未人工裁决；
3. 机器人安装载荷、发射载荷和在轨操作载荷为空；
4. 材料、截面、板厚、紧固件、连接刚度和制造工艺为空；
5. 整星物理质量、质心和惯量未测量或闭合；
6. 太阳翼收拢、锁定、释放、线束和载荷接口未定义；
7. 相机、末端执行器、TCP、接触和目标接口未选定；
8. 设备真实包络、散热、线束、EMC 和维护工具净空未定义；
9. B3 具名人工授权不存在。

权威未知量清单见：

`../06_unknown_register/V2_unknown_register.yaml`

## 5. B3 允许的最小动作范围

只有在获得具名人工 Gate 后，B3 才可：

- 新建独立的 V2 Master Skeleton、子装配骨架和 review configuration；
- 消费本包中标记为 `EVIDENCE_BOUND` 或 `DERIVED` 的参数；
- 将 `DESIGN_PROPOSAL` 建成可抑制、可替换、带属性标签的候选几何；
- 将所有 `UNKNOWN_BLOCKED` 保持为 null、reserved volume、keepout 或 disabled branch；
- 输出评审截图、BOM/属性表和干涉清单，但不得由视觉结果升级科学状态。

B3 仍不得：

- 修改 V1.0、A3、URDF、Gate、仿真、geometry SSOT 或证据；
- 填入未经来源支持的材料、载荷、板厚、紧固件、质量、CoM、惯量或性能；
- 运行 FEA、动力学、控制、Isaac/ROS、VLA/RL 或硬件动作；
- 宣称完成结构资格、飞行适航、标准合规、捕获或碰撞安全。

## 6. 裁决

```text
B2_5_SYSTEM_MECHANICAL_DESIGN_INPUT_PACKAGE_COMPLETE
B3_CAD_READY_TO_REQUEST_HUMAN_APPROVAL
B3_CAD_AUTHORING_NOT_AUTHORIZED
V1_0_UNMODIFIED
PHYSICAL_QUALIFICATION_NOT_STARTED
```

本裁决表示“设计输入链完整且可审计”，不表示“机械系统设计完成”。
