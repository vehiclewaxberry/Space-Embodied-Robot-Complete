# Numerical and Digital Twin Status

## 1. 审计裁决

**当前最高可证成熟度：`DT2_SCOPE_LIMITED_OFFLINE_REPLAY`。**

准确表述：

> 项目具备 DT0 CAD 数字样机、DT1 可执行动力学，以及针对旧冻结捕获 campaign
> 的局部 DT2 离线证据驱动回放；尚未形成覆盖当前全部模块的统一孪生，更未达到
> DT3 实时状态同步或 DT4 硬件双向闭环。

VIZ-Gate0 冻结于 2026-07-14，v1 研究仪表板形成于 2026-07-15；sim_10/11/12
于 7 月 18 日形成当前 Gate，SAFE/CTRL 于 7 月 19 日收口，组装规划于 7 月 20 日
形成。因此现有仪表板不覆盖当前完整证据链。E16 的“sync”是离线速度匹配参数
`alpha` 扫掠，不是设备—模型实时同步。

## 2. DT0–DT4

| 等级 | 状态 | 证据 | 限制 |
|---|---|---|---|
| DT0 CAD 数字样机 | 已具备 v0 | 12U/6U、目标、适配器 STEP/STL/URDF/JSON；B601 URDF/STL；`20_engineering/config/geometry/` | 多项低置信/PROVISIONAL，不是制造级或实测认证 CAD |
| DT1 可执行动力学 | 已具备 | sim_01–12、CTRL-01/02 的数值结果；当前 Gate JSON | 模块不是持续同步的统一模型；含 provisional 和 REPEAT |
| DT2 离线证据回放 | 局部具备 | VIZ-Gate0 单文件仪表板、6 支 MP4、44 关键帧、冻结哈希 | 覆盖旧捕获子集，不覆盖当前 sim10–12、SAFE/CTRL、Wave1、ASM |
| DT3 实时状态同步 | 未达到 | 无真实遥测、统一时钟、在线估计、陈旧数据规则和实时 Gate | E16 sync 不是 DT3 |
| DT4 硬件双向闭环 | 未启动 | H0–H3 未启动；无双向命令/遥测、急停联锁或 HIL Gate | 固定基座资产不等于硬件闭环 |

## 3. 数值求解与机器证据

| 模块 | 已有数值/工件 | Gate 状态 | 审计结论 |
|---|---|---|---|
| sim_01 | `attitude_rate.csv` | 无独立 Gate | 有数值结果，不得写本模块 scientific PASS |
| sim_02 | `tumble_pose.csv` | 无独立 Gate | 有数值结果，无真实感知链 |
| sim_03 | `base_reaction.csv` | 无独立 Gate | 早期反冲趋势，已被 6R 主线扩展 |
| sim_04 | 走廊 CSV/PNG | 无独立 Gate | 历史筛选资产 |
| sim_05 | 601 行自由漂浮臂时序 | 被 sim_11 G3b 复核 | 19.20° 仅冻结动力学锚 |
| sim_06 | 40 行捕获冲量矩阵 | 被 sim_10 X1 复核 | 捕获≠消旋；无接触时程/柔性 |
| sim_07 | ANCF 响应摘要 | 候选级认证 REPEAT | 有组件数值，非完整柔性认证 |
| sim_08 | 960 行预算扫掠 | 被 sim_10 X3 复核 | placeholder 执行器预算 |
| sim_09/E1 | 72 例 | 无最终 PASS verdict | campaign 已执行 |
| E1.5 | 72 例冻结包 | `REPEAT_E1_5` | 真实负结果 |
| P0-A | 核心证据重算 | coverage PASS；scientific `REPEAT_CORE_NO_SAFE_CANDIDATE` | 覆盖 PASS 不等于安全 PASS |
| P0-B | ANCF 认证运行 | `REPEAT_ANCF_CERTIFICATION` | 候选级认证未闭合 |
| E16 | 216 例，18 动态 | `PASS_WITH_GEOMETRY_AND_FLEX_LIMITATIONS` | formal safe=0；非 DT3 |
| sim_10 | 9002 物理点 | `SIM10_GATES_PASS` | 已完成，FLEX 未入判据 |
| sim_11 | A1/A2、带宽、模态、跨解算器 | `PASS_WITH_PROVISIONAL_PARAMS` | 已完成，参数待转正 |
| sim_12 | 16 例策略证明集 | `SIM12_PHASE1_GATES_PASS` | 已完成并冻结 |
| SAFE-00 | 可执行安全裁决工件 | PASS；`PENDING_REVIEW`；不自动授权 | 决策 Gate，不是新动力学模型；此处不产生装配执行授权 |
| CTRL-01 | 主时序/碰撞时序 | REPEAT | 已执行，真实负结果收口 |
| CTRL-02 | Stage-A/B 时序 | PASS_WITH_PROVISIONAL_SCOPE；`PENDING_REVIEW` | 7/16 仅在 R5 provisional 执行器及时窗模型下稳定；L0 硬件有效稳定性未评估 |
| Wave1 | 集成证据 | `WAVE1_REPEAT` | 已执行但非 PASS |
| ROM/Tools/VLA/H0-H3 | 计划/草案 | NOT_EVALUATED | 不得写成已实现 |

## 4. 三维回放覆盖

| 回放 | 真实覆盖 | 禁止外推 |
|---|---|---|
| `anim_v01_target_tumble.mp4` | 旧目标翻滚/捕获语境 | 不证明感知或当前全链 |
| `anim_v02_b601_approach.mp4` | E1.5 构型与接近场景 | 构型选中不等于动力学可接受 |
| `anim_v03_base_reaction.mp4` | sim_05 CSV 离线回放 | 非实时、非硬件 |
| `anim_v04_capture_impulse.mp4` | sim_06 冲量与 sim_08 预算解释 | 非接触控制/消旋闭环 |
| `anim_v05_flex_diagnostic.mp4` | sim_07 聚合证据与失败记录 | `NO_REPLAYABLE_TIME_HISTORY`；不是柔性变形回放 |
| `anim_v06_gate_explanation.mp4` | E1.5 Gate 语义 | 不改变科学 REPEAT |

允许说“旧冻结捕获 campaign 的离线三维证据回放”；禁止说“当前全模块实时数字
孪生”。

## 5. ASM 结论

ASM-00/01/02 均为 NOT_STARTED；未发现 `30_simulation/` 实施目录、ASM 结果
CSV/JSON、ASM Gate JSON、装配时序或回放。现有内容只有 SSOT 草案、Gate 注册、
风险、详细计划和任务卡。ASM-01 Phase A 的预注册上限仍是
`ASM01_SCREENING_ONLY`。

允许：

> 在轨组装规划包已完成并形成 `READY_WITH_INTERFACE_BLOCKERS`；ASM 数值仿真、
> 装配成功 Gate 与 ASM-TWIN-00 均待 Wave A 批准后实施。

禁止：

- ASM 仿真已完成或已通过；
- 装配孪生闭环；
- 已验证自主在轨组装；
- sim_11 已覆盖目标侧柔性、卡滞、锁紧和装配成功；
- 规划 Gate 注册表等于已产生机器裁决。

## 6. 升级门

1. 当前化 DT2：绑定 sim_10–12、SAFE/CTRL、Wave1 最新 Gate/时序，建立不可变输入
   清单；完成前只能称“局部历史 DT2”。
2. ASM-TWIN-00：等待 ASM-00/01/02 的真实时序、接触状态、质量转移、相位账本和
   machine Gate 后再生成。
3. DT3：需要真实/台架状态流、统一时钟、在线状态估计、延迟/丢包/陈旧数据规则、
   provenance 与实时 Gate。
4. DT4：需要 H0、双向命令与遥测、急停联锁、硬件触发重跑和 HIL 裁决。
