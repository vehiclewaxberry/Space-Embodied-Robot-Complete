# External Tool Stack Decision

## 1. 裁决

**当前外部工具 `NOW` 项为零。**

外部工具不得替代 NumPy/SciPy 原生动力学、CSV/JSON 与机器 Gate 真值链。当前
唯一候选科学实施主线是 `ON-ORBIT ASSEMBLY WAVE A`，当前仍
`PLANNED_NOT_AUTHORIZED`；外部最小对拍只是后续、有资源上限
的辅助验证，不得阻塞 Wave A、比赛材料或 2026-09-01 提交。

状态定义：

- `NOW`：当前主线 Gate 必要输入，不执行即阻塞；
- `NEXT`：下一个辅助槽位，可在 Wave A 首个 machine verdict 后或独立空档实施；
- `LATER`：等待 Wave A/Wave B 或比赛后；
- `AUDIT_ONLY`：只作理论/公式/历史口径审计；
- `NOT_NEEDED`：当前范围不能解锁新增科学声明，成本大于增益。

## 2. 证据边界

1. Wave A 规划与三张卡已存在，状态 `READY_WITH_INTERFACE_BLOCKERS`。
2. RF-1/2/3 与全 PROVISIONAL/LITERATURE 接口 SSOT 是当前实质阻塞；外部刚体或
   ADCS 工具不能解除接口几何、公差和锁紧力阻塞。
3. 仓库无 SPART、Pinocchio、Basilisk、MuJoCo、Adams、Isaac Sim 的项目级
   machine Gate、冻结适配器和结果哈希。
4. sim_11 是 `PASS_WITH_PROVISIONAL_PARAMS`；任何刚体工具都不能成为 FFR、
   ANCF、持续接触或目标侧柔性的“真值”。
5. 内部 Radau/BDF 一致性属于同方程交叉求解，不等于独立外部框架验证。

## 3. 逐项定位

| 工具 | 裁决 | 允许定位 | 不得承担 | 启动/停止条件 |
|---|---|---|---|---|
| SPART/Simulink | **LATER** | Pinocchio 三锚点出现不可解释差异，或 Wave A 后确需 GJM/RNS+控制联合仿真时的第二刚体 cross-validator | 不替代 sim_11；不验证 FFR/ANCF/接触/装配成功 | 仅一个冻结场景；出具 verdict 后停 |
| Basilisk | **NEXT** | 一个服务星 ADCS 锚点；核对质量惯量、轮/推力器、角动量账本和分类 | 不验证机械臂柔性、抓取接触、接口或 VLA | Wave A 不受影响且有独立人力；一个锚点后停 |
| MuJoCo | **LATER** | Wave B/C 后用于快速技能、接触状态覆盖、FSM/VLA 环境与交互回放 | 不是柔性、接触认证或空间动力学真值 | ASM-01 接触语义与 UNKNOWN 合同冻结后 |
| Pinocchio | **NEXT** | 三个刚体锚点的首选轻量 cross-validator：质量矩阵、雅可比、基座反冲 | 不验证 FFR/ANCF、接触带宽、卡滞、柔性模态能或装配成功 | Wave A 首个 verdict 后或独立空档；三锚点后停 |
| SpaceDyn | **AUDIT_ONLY** | Yoshida GJM/RNS 公式、参考系、动量分解和历史算例审计 | 不进入比赛交付或形成新主求解链 | 只读公式对照；执行另行许可审查 |
| Adams | **NOT_NEEDED** | 当前六周无新增声明需要其工业多体能力 | 不能以品牌替代项目 Gate | 仅赛后伙伴明确要求时重评 |
| Isaac Sim | **LATER** | Wave C 后的视觉数据、展示和具身交互场景 | 不是动力学/柔性/接触真值；不证明 VLA 泛化 | 先有 ASM Gate、技能合同与 V2.5 |
| 气浮台 | **LATER** | 比赛后 H0–H3 地面组件验证 | 不得称空间、六自由度或微重力验证 | 硬件/测量/安全/接口就绪并与比赛解耦 |

## 4. 最小外部对拍合同

若后续批准 `EXTERNAL CROSS-VALIDATION MINIMAL WAVE`：

### Pinocchio 三个刚体锚点

1. **RIGID-1 质量矩阵**：冻结 B601 URDF、`T_SM`、质量/质心/惯量、一个构型；
   对拍 `M(q)` 对称/正定和关键 base-arm 耦合块。
2. **RIGID-2 雅可比**：对拍末端 body/spatial Jacobian、自由漂浮广义雅可比与
   有限差分；先统一表达系、角速度排列和参考点。
3. **RIGID-3 基座反冲**：复用 sim_05 轨迹，对拍 19.20° 峰值、角动量账本与
   时程；容差预注册，禁止事后放宽。角动量必须同时报告关于惯性原点和系统质心
   两种口径，不得交叉比较；两者转换必须记录平移项。

输入参考系或惯量不等价时必须记
`NOT_EVALUATED_INPUT_MISMATCH`，不得记科学 FAIL。

### Basilisk 一个 ADCS 锚点

- 复用 CTRL-02/任务可行域的一个冻结服务星案例；
- 同一质量、惯量、初始角动量、轮组盒、推力器与脉冲量子；
- 对拍区域分类、轮组利用/饱和、角速度和角动量收支；角动量同样报告关于惯性
  原点和系统质心两种口径，不得交叉比较，转换时记录平移项；
- 禁止为适配 Basilisk 改写 CTRL-02 冻结输入或阈值。

### 统一 verdict

- `CROSS_CHECK_PASS`
- `CROSS_CHECK_REPEAT`
- `NOT_EVALUATED_INPUT_MISMATCH`
- `BLOCKED_BY_TOOL_OR_LICENSE`

外部结果不能直接改写现有 Gate。差异先审计单位、参考点、坐标系、URDF 惯量
约定、积分器和输入哈希；输入等价证明后才可报告 `CROSS_CHECK_REPEAT`。

## 5. 禁止强结论

- SPART/Pinocchio 验证了 sim_11 柔性真值；
- MuJoCo/Adams 认证了装配接触或卡滞；
- Basilisk 验证了机械臂刚柔耦合捕获；
- Isaac Sim 展示证明 VLA 泛化或物理正确性；
- 气浮台等价于空间/微重力/六自由度实物验证；
- 外部求解器优先于项目 machine Gate。
