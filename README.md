# 航天服务星具身智能机械臂机器人

**Space Service Robot with Embodied Intelligence**

面向在轨服务的 12U 立方星服务星 + B601 六自由度机械臂的完整数字样机、机械/电气设计与自由漂浮动力学证据库。

*A complete digital prototype, mechanical/electrical design package, and free-floating dynamics evidence base for a 12U CubeSat servicing spacecraft with a B601 6-DOF manipulator.*

---

## 项目定位 / Scope

这是一个**在轨服务空间机器人学的科研项目**，同时承载长期硬件研发。两条线互为约束：

- **研究线** —— 面向抓取后可稳定性的**预见式具身抓取**。核心问题：在自由漂浮、刚柔耦合、目标非合作的条件下，捕获策略的可行域由哪些物理边界决定。
- **工程线** —— 可装配、可参数化、可验证的 12U 服务星与 B601 机械设计，作为研究结论的物理载体与参数来源。

研究产出以**机器裁决证据**（`*_gate_check.json`）与论文结构为组织形式，而非演示件。论文规划入口见 [`10_research/paper1_architecture.md`](10_research/paper1_architecture.md)（Paper 1 = 柔性耦合捕获任务可行域），问题树见 [`10_research/research_questions/`](10_research/research_questions/)。

*This is a research project in on-orbit-servicing space robotics, carried alongside long-term hardware development. The research line studies predictive embodied grasping for post-capture stabilizability — specifically, which physical boundaries determine the feasible domain of capture strategies under free-floating, rigid-flexible coupled, non-cooperative conditions. Outputs are organised as machine-adjudicated evidence and paper structure, not demos.*

> **关于历史来源**：项目起源于中国研究生未来飞行器创新大赛（第十二届）。比赛记录、机器 Gate 与负结果作为**历史证据**原位保留，但**比赛期限与比赛交付不再构成研究议程、工程验收门槛或授权 Gate**。请勿据历史比赛记录升级当前结论。

### 任务设定 / Mission

| 项 | 值 |
|---|---|
| 服务星 | 12U CubeSat 平台 |
| 机械臂 | B601，6R 串联构型 |
| 目标 A | 150 kg 翻滚空间碎片 |
| 目标 B | 22 kg 非合作目标星 |
| 动力学工况 | 自由漂浮（free-floating），基座不固定 |
| 研究线 | 面向抓取后可稳定性的预见式具身抓取 |

---

## 仓库导航 / Repository layout

八个业务域，根目录不再建立平行的 `src/` `docs/` `results/` 树。

| 目录 | 内容 |
|---|---|
| [`01_project/`](01_project/) | 项目入口、治理、协作原件、历次工作包记录 |
| [`10_research/`](10_research/) | 研究问题树、方法、合同、知识库、论文材料 |
| [`20_engineering/`](20_engineering/) | **CAD、电气、BOM、参数、接口与设计证据** |
| [`30_simulation/`](30_simulation/) | 模型、程序、测试、原始结果、机器裁决 |
| [`40_evidence/`](40_evidence/) | 图表、媒体、离线展示 |
| [`50_literature/`](50_literature/) | 题录、阅读卡、BibTeX |
| [`70_tools/`](70_tools/) | 编目、展示、校验工具 |
| [`80_third_party/`](80_third_party/) | 外部来源登记与许可（见 [NOTICE.md](NOTICE.md)） |

全项目导航入口：**[PROJECT_MAP.md](PROJECT_MAP.md)**

---

## 协作者快速上手 / Getting started for collaborators

仓库含 **13 GB Git LFS 内容**（7,328 个对象，主要是 CAD）。**克隆方式选错会出问题**，请按下面来。

### ① 先装 Git LFS —— 不装的话你拿到的是一堆占位符

这是最常见的坑：没装 LFS 就 `git clone`，所有 CAD 文件会变成约 130 字节的指针文本。**文件名看着都在，但一个都打不开。**

```bash
git lfs install
```

*Install [Git LFS](https://git-lfs.com/) first. Without it every CAD file clones as a ~130-byte pointer stub — the filenames all look right, but nothing opens.*

### ② 推荐：先不拉 CAD，按需取件

完整克隆会下载 13 GB，**消耗仓库的 LFS 带宽配额**；配额耗尽后**所有人**的 LFS 下载都会被阻断。除非确实需要全部 CAD，否则请用：

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete.git
```

这样能拿到全部代码、文档、仿真结果与机器裁决（约 256 MB），CAD 先留作指针。需要某个具体部件时再单独拉：

```bash
# 例：只取最新整星总装
git lfs pull --include="20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/**"

# 例：只取某一批 STEP
git lfs pull --include="20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/**"
```

*Full clones pull 13 GB and consume the repository's shared LFS bandwidth quota; once it is exhausted, LFS downloads are blocked for everyone. Prefer the skip-smudge clone above and fetch only what you need.*

### ③ 确实需要全部 CAD 时

```bash
git clone https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete.git
```

请先知会仓库所有者——这一次操作会占用约 13 GB 带宽配额。

### 打开 CAD 需要什么

| 格式 | 仓库内文件数 | 需要的软件 |
|---|---|---|
| `.STEP` | 3,404 | **任意 CAD 软件**（FreeCAD、Fusion、CATIA、NX…）— 没有 SolidWorks 就用这个 |
| `.SLDASM` / `.SLDPRT` | 6,233 | SolidWorks 2024 及以上 |
| `.FCStd` | 89 | FreeCAD |
| `.glb` / `.stl` | 873 | 任意三维查看器（仅可视化，非设计源） |

全部 CAD 合计 13 GB LFS（7,328 个去重对象——同内容的文件共享一份存储，所以实际下载量小于按文件数的估计）。

---

## 研究线 / Research programme

### 六层架构

研究按六层组织，**各层分别取证，不由某层结论覆盖其它层**：

| 层 | 职责 | 状态 |
|---|---|---|
| **L0** | 任务可行性 / 策略 | 已实现（`sim_10`、`sim_12`） |
| **L1** | SAFE 证据核 | `SAFE-00` 47/47 PASS，`review_status=PENDING_REVIEW` |
| **L2** | 确定性控制 | `CTRL-01/02`，带 PROVISIONAL 范围限定 |
| **L3** | 刚柔世界模型 | `sim_11` v1.1，含占位参数 |
| **L4** | 具身候选生成 | 规划态，未实施 |
| **L5** | 地面验证 | H0–H3 规划态，未实施 |

导航：[`10_research/00_project_architecture/`](10_research/00_project_architecture/)

### 论文线

| 论文 | 主题 | 状态 |
|---|---|---|
| **Paper 1** | 柔性耦合捕获任务可行域 | 证据/查新收口中，结构见 [`paper1_architecture.md`](10_research/paper1_architecture.md) |
| **Paper 2** | 接触带宽 / 保真度 | 候选，未启动 |

问题树 Q1–Q6、理论假设与主张-证据关系见 [`10_research/research_questions/`](10_research/research_questions/)、[`theory_graph/`](10_research/theory_graph/)、[`contribution_map/`](10_research/contribution_map/)。

文献主清单：[`50_literature/references/manifest.yaml`](50_literature/references/manifest.yaml)（44 篇 PDF / 29 张阅读卡；**PDF 全文因版权不随仓库分发**，按 manifest 自行获取）。

### 规划态支线（**尚未授权实施**）

`BRIDGE-UT` 带界不确定目标操作、`Q6-L1` 预制接口装配、On-Orbit Assembly Wave A、Physics-Gated Agent、ROM、VLA —— 这些目录存在**不等于**实施完成或已授权。请按各目录内的具名合同理解其范围。

---

## 当前硬件基线 / Current hardware baseline

这是接手后续开发时**首先要看的**部分。

| 要做的事 | 入口 |
|---|---|
| 四系统硬件主设计（机械 / 电气线束 / 能源热控 / 动力推进） | [`20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/`](20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/) |
| **最新整星总装（数字样机）** | [`SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM`](20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/) |
| 电气选型当前指针 | [`20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json`](20_engineering/SERVICE_STAR_ELECTRICAL_LATEST.json) |
| R7 安装布局草案（**未完成项**） | [`20_engineering/SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921/`](20_engineering/SERVICE_STAR_AUX_STOP_INSTALLATION_R7_20260921/) |
| 上游机械来源（星体本体） | [`20_engineering/service_robot_wp03_spacecraft_body_r1/`](20_engineering/service_robot_wp03_spacecraft_body_r1/) |

**读法约定**：选型候选与未安装草案分别看待，**不按目录日期推定完工**。R6H 原件保留，没有回退为早期 WP03。

### CAD 格式说明

原生件为 SolidWorks（`.SLDPRT` / `.SLDASM`），中性交换格式为 `.STEP`，二者均通过 Git LFS 存储。**克隆方式与所需软件见上文[协作者快速上手](#协作者快速上手--getting-started-for-collaborators)**——直接 `git clone` 而未装 LFS 会拿到占位符而非真实 CAD。

---

## 已验证的核心结果 / Verified results

以下数值来自各模块的**机器裁决 JSON**（`*_gate_check.json`），引用时请勿改动。注意：**测试 PASS ≠ 科学 Gate PASS**。

| 编号 | 结论 | 关键数值 |
|---|---|---|
| `sim_05` | B601 自由漂浮，臂运动致基座姿态扰动 | 峰值 **19.20°**；动量守恒 7.3e-17 |
| `sim_06` | 矢量式捕获冲量——**捕获 ≠ 消旋** | 碎片 @3°/s → 捕获后 3.06°/s |
| `sim_07` | ANCF 柔性帆板，点捕获激振 vs 刚性锁定 | ≈ **92×**；振铃 37–75 s |
| `sim_08` | 150 kg 碎片消旋**必须用推力器** | `\|H_c\|` = 3.65 N·m·s = **12×** 轮组容量 |
| `sim_10` | 任务可行域 9000 点四门 fail-closed 扫描 | 裁决 `SIM10_GATES_PASS` |
| `sim_11` v1.1 | 刚柔耦合，有限接触窗口 | `SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS` |
| `sim_12` Phase1 | 16 例策略证明集——**最优捕获策略是 binding gate 的函数** | `SIM12_PHASE1_GATES_PASS` |
| `SAFE-00` | 运行时安全门 | 47/47 PASS，七绕过面全封 |

### 对后续在轨服务开发的直接含义

1. **基座扰动不可忽略**：自由漂浮下 19.20° 的姿态耦合意味着臂规划必须与姿态控制联合求解。
2. **捕获与消旋是两个问题**：捕获冲量不消除目标角动量；150 kg 级目标的消旋超出轮组容量一个数量级。
3. **柔性帆板是激振主源**：点捕获相对刚性锁定放大约 92 倍，接触策略必须考虑帆板模态。
4. **策略选择依赖于约束边界**：不同 binding gate 下最优策略不同（S1 / S3a / ABORT）。

---

## 明确的未完成项与占位参数 / Known gaps

本节是**刻意保留**的。项目约定：负结果、UNKNOWN 与占位参数不得被整理或总结所掩盖。

| 项 | 状态 | 影响 |
|---|---|---|
| **帆板质量 0.348 kg** | **占位值**。真实面密度 2–5 kg/m²，差 5–10 倍 | 真实参数下「柔性反馈可忽略」的结论**可能翻转**。当前最大硬伤 |
| **接触窗口 `T_c` = 20 ms** | `PROVISIONAL`，待 B601 夹爪实测 | 需替换 `scene_A2_capture.yaml` 后重跑带宽口径 Gate |
| 帆板模态参数 | 占位 | 同上 |
| `e15` ANCF 认证 | 交叉求解最大差 5.64% > 5% 门槛 → `REPEAT_ANCF_CERTIFICATION` | 全耦合新模型须重过该 Gate |
| `FLEX` | `UNKNOWN`，不入 `sim_10` 判据 | 可行域为**刚体边界** |
| R7 安装布局 | 草案，未安装 | 不得按日期推定完工 |
| `CTRL-02` 姿态分账 | `PASS_WITH_PROVISIONAL_SCOPE` | 硬件有效稳定性 `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS` |

> 引用控制类结论时必须带限定语：「**在冻结增益与预注册轨迹下**」。

---

## 证据与结论约定 / Evidence conventions

这套约定是项目的核心工程文化，接手者请遵守：

- **科学结论只认机器裁决 JSON**（`*_gate_check.json`），不认文档摘要。
- **测试通过 ≠ 科学 Gate 通过**。
- 每个 `sim_XX` / `eXX` 模块自带 `src/` `tests/` `results/` `docs/`，自包含。
- 失败、`UNKNOWN`、受限结果**留在原拥有者目录**，不被后续工作覆盖。
- 不同模型与版本的结果**不互相覆盖**，导航不汇总为单一通过状态。
- 目录同名、同日期或位于 `archive/` `_work/` **不足以证明文件无用**。

---

## 复现 / Reproducing

各仿真模块自包含。典型流程：

```bash
cd 30_simulation/sim_11_coupled_dynamics
python -m pytest tests/          # 模块测试
python src/run_all.py            # 重跑场景与 Gate
cat results/sim_11_gate_check.json   # 读机器裁决
```

> **注意**：`control_01` / `control_02` 的 `run_all.py` 会**覆写** `results/` 下的 gate JSON。运行前请先 snapshot，运行后 restore。

---

## 第三方 / Third-party

本仓库**不转发**上游第三方代码库。所使用的外部平台（Basilisk、Exudyn、Chrono、SPART、SpaceDyn、Astrobee、OpenVLA、openpi 等）及其许可证登记于 **[NOTICE.md](NOTICE.md)**，请从各自上游获取。

外部参考 CAD 与供应商模型的来源、版本与许可见 [`80_third_party/README.md`](80_third_party/README.md)。

---

## 引用 / Citation

见 [CITATION.cff](CITATION.cff)。

---

## 许可 / License

见 [LICENSE](LICENSE)。第三方组件各自适用其上游许可，见 [NOTICE.md](NOTICE.md)。
