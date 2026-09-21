# 几何接口决策记录 v1（2026-07-10 冻结）

来源：三轮只读几何审计（772文件，证据与完整清单在 `.codex_audit/geometry_inventory/`，
不入版本库；本文件是正式结论的唯一入库载体）。逐项状态：**adopted** = 即日生效。

## D-1 机械臂安装接口唯一基线 — adopted
**160×160×12 mm 底板 + Ø100 mm 凸台**（`robot_mount_adapter_v0`，唯一有
STEP+STL+原生SLDPRT三证实体的接口件）。
```
160×160     正式基线（新仿真/URDF/SolidWorks总装只消费此方案）
140×140     deprecated（12U spec法兰primitive，v1骨架改160并复核6.5mm突出规则）
90×180八孔  历史候选（仅存6U需求文档，不进当前总装）
```
旧文件不删除，仅停止消费。

## D-2 `^S T_M` 数值冻结 — adopted（nominal_frozen_v1）
已回填SSOT：`20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/coordinate_frame_definition_v0.md` §3.1
（含完整规范：M在S中的位姿、平移在S系表达、右手系、被动列向量约定、URDF rpy、
scipy四元数、SolidWorks参考几何定义）。
t=[185.25,0,0] mm，R=R_y(+90°)，+Z_M=+X_S=伸展方向，+X_M=−Z_S。
轴向冲突处置：不改服务星坐标系；`reBot_arm_v0_min.urdf`（沿+X_M伸展）标记 **legacy**，
新7DOF臂零位沿+Z_M建立；若复用外部B601 URDF，加显式固定基座变换，不得改其关节轴。

## D-4 帆板等效刚度 — adopted（名义1.0 Hz + 包络）
一阶悬臂频率名义值 f₁=1.0 Hz（**设计假设，非实测**），包络 0.7 / 1.0 / 1.3 Hz 三组：
```
f₁ = (β₁²/2πL²)·√(EI/μ),  β₁≈1.8751,  μ = m_panel/L = 1.7418 kg/m
EI = μ·(2π·f₁·L²/β₁²)²:
  flexible_low   0.7 Hz → EI = 4.363e-3 N·m²
  nominal        1.0 Hz → EI = 8.904e-3 N·m²
  flexible_high  1.3 Hz → EI = 1.505e-2 N·m²
```
报告表述模板："在缺少真实帆板结构刚度数据的情况下，以1 Hz一阶频率作为名义设计假设，
并通过0.7–1.3 Hz包络评估结论对柔性参数不确定性的敏感性。"

## D-5 7DOF臂来源 — 48小时时钟已启动（2026-07-10）
全盘搜索 `reBot_B601_DM_with_gripper.urdf` / `reBot-DevArm_fixend.urdf`（F:/C:/G:盘
后台检索中 + 请团队查备份盘/旧工作区）。
```
48h内找到   → 解析审计，加固定基座变换后复用
48h内找不到 → 立即建立 generic_arm_7dof_v1（任务级7自由度等效机械臂骨架）
```
命名红线：自建模型不得命名B601、不得声称代表真实reBot；构型=肩yaw+pitch+roll、
肘pitch、腕yaw+pitch+roll（3+1+3），轴系见 `.codex_audit/.../coordinate_frame_definition.md` §2。

## D-6 抓捕点唯一源 — adopted
CAD JSON `grasp_points_mm` 为唯一来源；sim_02 硬编码 [0.6,0,1.0] 作废待改（sim_06/08已用JSON值）。

## 质量拆分（防双计，配套D-4）— adopted
太阳板从刚体基座剥离（数值与自动闭合检查见 `20_engineering/config/geometry/`）：
```
m_bus = 23.3033 kg,  m_panel = 0.348366 kg ×2,  闭合检查: m_bus+2·m_panel ≡ 24.000 kg
```
既有 `servicer_12U_v0`（24 kg整星）行保持不动——刚体仿真链（sim_01–06/08）继续用整星值；
ANCF线（sim_07）必须用 `servicer_12U_bus_v1` + 两块独立板。

## 其余（D-3/D-7/D-8/D-9/D-10）
D-3单位规则（SW=mm，STL/URDF/仿真=m）默认生效；D-7真实帆板面密度（7.67 kg/m²偏重）挂起至
D-4包络结果出来；D-8碎片薄壳化=P2；D-9双后缀SLDPRT改名移位=待办卫生项；
D-10 AprilTag布置=HIL实验后定。

## 证据路径
`.codex_audit/geometry_inventory/{geometry_audit.md, reuse_decision.md,
minimum_geometry_gap_list.md, unresolved_geometry_decisions.md, geometry_inventory.csv}`
关键翻案记录：现代SolidWorks容器格式=`4字节校验+00000004`（524样本交叉验证），
`robot_mount_adapter_v0.SLDPRT.SLDPRT` 内容有效非损坏。
