# CAD brief — R2 Integrated Digital Prototype C01 V1

- Model: 12U 服务星、Solar R2、M3R 与完整 B601 六自由度机械臂的固定 `q0` 装配候选。
- Task type: 从两个已冻结 STEP 源构建新装配；不修改冻结 master、B601 STEP 或任一 URDF。
- Units: STEP 与装配定位统一为 mm；URDF 保持 m、kg、rad，不在本 CAD 中重发质量或关节权威。
- Assembly frame: `S` 为服务星装配根坐标；冻结 master 保持原位。B601 根安装变换为 `T_S_B601_ARM_BASE = Ry(+90 deg) * Rz(+25.000014 deg)`，平移 `[208, 0, 0] mm`，矩阵精确值由 `INTEGRATED_CANDIDATE_INPUTS_V1.json` 管理。
- Fixed configuration: `C01_DEPLOYED_NOMINAL_FIXED_SOLAR__B601_FIXED_Q0`。固定 STEP 只表达装配与外观，不保留 8 个执行自由度。
- Source filtering: 冻结 41-solid master 仅保留一基索引 `1..8, 27, 28, 41`；删除 B601 轴线见证体与脱离 palm overlay；安装 388-solid B5.0 B601 q0 B-rep。
- Assembly hierarchy: 根装配下恰有两个中间分组：`R2_SERVICER_WITHOUT_AXIS_WITNESS` 与 `B601_FULL_ARM_FIXED_Q0_INSTALLED`。
- Primary output: `R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step`。
- Secondary topology/viewer output: `.R2_INTEGRATED_DIGITAL_PROTOTYPE_C01_V1.step.glb`；它是标准 CAD 工具的隐藏 topology sidecar，不是质量、动力学或独立 native-GLB 权威。
- Expected geometry: 399 个叶级 solids；2 个中间分组；装配 bounds min `[-230.25, -313.15, -274.86072587989787] mm`、max `[488.533214, 313.15, 285.63229786565915] mm`，绝对容差 0.1 mm。
- Primary mating datum: B601 安装后最小 X 与 M3R 外端面均为 210.405 mm，绝对容差 0.01 mm。
- Source authority: 所有输入必须先通过 bytes/SHA-256 pin；不存在从图像比例或未标注外形推断的几何。
- Purchasable parts: 本任务不新增命名的现购件；因此不触发新的 STEP 零件检索。现有源中的目录件几何只沿既有冻结资产继承。
- Validation targets: V1/V2 execution/authority receipt 完整链与 active-lock absence；输入合同、STEP 与 topology GLB bytes/SHA；先用 `inspect refs --topology` 枚举，再以 `--detail --facts --positioning` 验证 399 个 shape 全部 `kind=solid`、体积为有限正数且每叶恰一实体；单根下 11/388 两直接分组；bounds；两个组 selector/label/parent/child 可解析；210.405 mm 安装基准；四视图 snapshot；对任何视觉疑点追加 `measure`、`frame` 或 `align`。
- Snapshot packet: 正/反等轴测、顶视、前视，见 `CAD_CANDIDATE_SNAPSHOT_JOB_V2.json`。
- Assumptions and limits: 固定 q0 几何不覆盖时变关节、Route-C、M01 连续路径、运行级碰撞/接触、ARM HDRM/目标/传感器等缺失硬件权威，也不产生制造、资格鉴定或飞行发布信用。
- Execution condition: 每次运行必须有未消费的命名 run；运行前可用物理内存至少 6 GiB，或具备与该 run/nonce/最长两小时窗口绑定的单次低内存 Owner Override。Override 不得记作 `MEMORY_GATE_PASS`。
