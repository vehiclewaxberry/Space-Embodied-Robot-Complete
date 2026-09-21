# 仓库真值审计（只读）— 2026-07-11

审计代理：总控审计与研发代理 ｜ 事实来源：磁盘 + Git历史 + **当日复跑**的测试/脚本输出 + CSV/PNG原始文件。
不采信任何旧总结。本轮零文件修改（仅新增本审计包6个文件）。

## 1. Git 事实层
- 分支 `doc-reorg-stage1`，共 **14 次提交**（0a6df16 → e03233d），标签 `gate-a-capture-impulse-v1`@4bc0fa3。
- 工作树干净；untracked：`.codex_audit/`（审计产物，约定不入库）、B601网格27MB（LFS未决）、
  3份标准PDF、损坏命名的SLDPRT副本、根目录`空间机械臂.docx`。
- 目录现状：`cad/ config/ docs/ external/ sim/`。**不存在**：`models/ src/ scripts/ tests/(顶层) results/(顶层) figures/ tables/`（本审计新建tables/）、Case B/C、视觉、HIL、报告书、视频。

## 2. 定量声明逐条核验（详细矩阵见 tables/competition_claim_evidence_matrix.csv）

| # | 声明 | 判定 | 当日复核证据 |
|---|---|---|---|
| 1 | 1620例安全走廊 | **VERIFIED** | capture_corridor_summary.csv 行数=1620（当日重算） |
| 2 | SAFE 19.3% | **VERIFIED** | SAFE=312/1620=19.26%；朴素臂SAFE=0 同时核验 |
| 3 | 24例假安全 | **VERIFIED** | corridor_migration_v2.csv：SAFE→FAIL=24（全部debris@2.0°/s），FAIL→SAFE=0 |
| 4 | 捕获后3.0→3.06°/s | **VERIFIED** | capture_impulse_matrix_v0.csv debris/3/0.01行=3.06333 |
| 5 | 标量式低估2.9–12.3% | **VERIFIED** | 全网格err∈[−12.335%,−2.864%]（表述"2.9"为−2.864四舍五入，建议报告写−2.9%~−12.3%） |
| 6 | 3.65 N·m·s | **VERIFIED** | actuator_budget_sweep.csv debris@3.0=3.65099 |
| 7 | 12倍轮组容量 | **VERIFIED** | 3.65099/0.3=12.17×（3×100 mN·m·s轮组）；表述"12×"成立 |
| 8 | 36.5 g冷气 | **VERIFIED** | 同CSV lever=0.17/cold_gas行=36.4998 g |
| 9 | 19.20°基座反作用 | **VERIFIED\*** | sim_05_base_attitude.csv base_dev_angle峰值=19.20；\*见§4约束合规注记（臂模型口径） |
| 10 | 2.617°几何相位 | **VERIFIED** | 当日复跑test_dynamics：2.6168°（复现） |
| 11 | ANCF基准5/5 | **VERIFIED** | 当日复跑ancf_beam_benchmark.py：b1..b5全过（静挠度1.03e-4，f1误差2.1e-6） |
| 12 | 刚性锁定激振约100倍 | **PARTIAL(精度)** | task_response_summary.csv实际比值92.1–92.4×。结论定性成立（近两个数量级），但报告/图注应写"≈92×/近两个数量级"，不写"100倍"。且3DOF数值为指示性下界（假设A3：其主激励在面内方向，平面模型未覆盖） |
| 13 | 振铃37–75 s | **VERIFIED\*** | t5pct∈[37.03,75.17] s；\*为包络对数拟合外推值（超出15s仿真窗），与单模态理论ln20/(ζω₁)偏差<4%，CSV已标fit_extrapolated——报告须注明外推 |
| 14 | 自动化测试52项全绿 | **VERIFIED** | 当日复跑：sim_06套件25/25 + sim_05套件22/22 + ANCF基准5/5 = 52。另有sim_07a回归R1/R2/R3三项PASS未计入52（实际55项） |

仪表板其余定量声明抽核：|H_bm·q̇|峰值0.089 kg·m²/s（CSV核验✓）、质量拆分23.3032134+2×0.3483933=24.000（mass_split_check.py当日重跑闭合误差=0 ✓）、B601混合4.6956 kg（URDF求和✓）。

## 3. 资产存在性盘点（申报材料视角）
| 资产 | 状态 |
|---|---|
| sim_01–08 + 扩展（04_v2/07a） | 存在、可复跑、结果入库 ✓ |
| Case A（普通轨迹基线） | 存在（=sim_05_headline，19.20°+\|H_bm·q̇\|基线曲线） |
| **Case B（反作用最小化）** | **MISSING**（无优化器代码） |
| **Case C（冲量感知联合优化）** | **MISSING** |
| 六维捕获冲量求解器 | 存在（rigidize + rigidize_point_contact，25项验证） |
| 执行机构预算 | 存在（sim_08，assumptions.yaml为等级值待选型替换） |
| **视觉/AprilTag** | **MISSING**（仅目标JSON中的AprilTag字段，未填数） |
| **HIL/B601实物耦合** | **MISSING**（本仓库零HIL代码；ROS2控制器在F:/Robotic arm侧仓库，未耦合。现状既非闭环也非回放——是未开始） |
| 五张评审图 | 2.5/5（详见 tables/five_figure_readiness.csv） |
| **项目报告书** | **MISSING**（0页） |
| **演示视频** | **MISSING** |
| 证据包（约束12全要素） | **PARTIAL**：输入/命令/提交/确定性(无随机)齐；**缺环境版本清单与结果哈希**（见P1-5） |

## 4. 硬约束合规核查
| 约束 | 现状 | 判定 |
|---|---|---|
| 3/4 动力学主模型=DevArm_fixend；B601_with_gripper仅几何 | **偏差**：sim_05动力学用`arm_b601_v1.urdf`（混合=B601运动学+DevArm质量集+B601夹爪质量0.2665 kg）。质量口径已是DevArm（厂商4.5 kg一致），但运动学与夹爪质量来自with_gripper | **PARTIAL** → P0-1裁决：纯DevArm_fixend复跑sim_05对照（预计运动学差异<2%：joint6原点差4.3 mm、末端差4.3 mm、末端质量0.500 vs 0.285） |
| 5 Pinocchio前缀/package_dirs | 本仓库尚未用Pinocchio（自写FK/动力学）；约束记录在案，供HIL/交叉验证阶段执行 | N/A(记录) |
| 6 接口160×160×12+Ø100 | config/geometry/arm_mount_v1.yaml=D-1已冻结 | ✓ |
| 7 T_SM名义值冻结 | SSOT§3.1 nominal_frozen_v1，未被改动 | ✓ |
| 8 质量拆分23.3032134+2×0.3483933 | budget CSV两行+闭合自动检查当日重跑=0误差 | ✓ |
| 9 flexible_appendage_v1为唯一柔性输入 | sim_07/07a实际读取该yaml（代码核验） | ✓ |
| 11 禁用语 | 仓库README/图注未发现"首次ANCF/在轨验证"表述；"动力学同构"未出现（HIL叙事未写）。仪表板"≈100×"需改92× | ✓(1处精度修正) |

## 5. 复跑记录（约束12格式）
- 命令：`python sim/sim_06_capture_impulse/tests/run_all.py`（25/25）、`python sim/sim_05_free_floating_arm/tests/run_all.py`（22/22，几何相位2.6168°）、`python sim/sim_07_ancf_flexible/ancf_beam_benchmark.py`（5/5，f1=1.00021）、CSV核验脚本与零空间分析脚本（scratchpad，只读）。
- 基准提交：e03233d ｜ 随机性：全部确定性（无随机数；测试用固定种子20260710/20260711）｜ 环境：Windows 11，Python 3.13.9，numpy/scipy/matplotlib（**精确版本清单待P1-5证据包脚本生成**）。

## 6. 阶段B新增数值证据：6R臂零空间可行性（只读分析，种子20260711，6个构型）
用已入库sim_05模块计算堆叠矩阵 [J_task; H_bm,ang] 的秩与最优解：
- **6DOF末端任务：无瞬时冗余**（J满秩6×6，q̇唯一，|H_ang·q̇|不可选择）→ 只能轨迹/构型/时机优化；
- **3DOF位置任务：零姿态反作用解处处存在**（6×6堆叠矩阵在全部6构型满秩；cond 2.4e3~1.2e4；解出的q̇范数0.38–1.38 rad/s@1 cm/s任务速度，未超1.5 rad/s限速但接近）→ 接近段可实现近零姿态反作用跟踪（须做全轨迹QP含限位验证，Gate C的达成路径）；
- **5DOF轴对称任务：瞬时零空间仅1维**，零空间内优化仅降1.03–1.47×→ 5DOF模式的显著收益必须来自捕获构型选择+时间参数+路径形状的轨迹级优化（与sim_06冲量联合，即Case C）。

**结论：Gate C可达，但正确的叙事是"3DOF接近段近零反作用 + 终端对准段付出有界反作用 + 构型级冲量优化"，而非全程零反作用。**

—— 阶段A只读审计完毕。关键路径判断见 `01_award_strategy_and_critical_path.md`。未经人工批准不进入修改阶段。
