# Claude Code 任务提示词:星-臂-帆板全耦合动力学场景搭建(路线 A 主线)

> 用法:整段复制给 Claude Code 执行。生成日期 2026-07-17,依据调研报告与决策 D-YH-1~4。

---

## 0. 先读真值,禁止凭记忆推断

按顺序读完再动手:

1. `CLAUDE.md`(仓库根,项目记忆与协作者决策)
2. `docs/90_competition/项目现状总览_20260715.md`
3. `docs/90_competition/协作问题梳理_杨恒_20260717.md`(决策 D-YH-1~4)
4. `docs/90_competition/调研报告_机械臂嵌入刚柔耦合动力学模型_20260717.docx`(用 pandoc 转 markdown 读,三条路线与方程分块在此)
5. 几何/质量 SSOT:`config/geometry/`、`docs/stage1_spacecraft_layout/04_mass_inertia_budget/`
6. 现有代码基线:`sim/common/rigid_body.py`、`sim/common/capture_impulse.py`,以及 sim_05(B601 六关节自由漂浮)、sim_07(ANCF 帆板)的 src/tests/机器裁决 JSON

动手前先复跑 sim_05 与 sim_07 的 tests 确认基线全绿。`docs/90_competition/` 已有 sim10_mission_feasibility_design.md,新目录自行选定不冲突编号(建议 `sim_11_coupled_dynamics/`)并在报告中说明理由。

## 1. 目标与模型规格

把 B601 六自由度机械臂按**树形拓扑分支**嵌入"中心刚体 + 两侧柔性帆板"的浮动基座多体模型(路线 A,决策 D-YH-2),交付可复现场景 + 机器裁决。

- 广义坐标:`q = [r_b(3), q_b(四元数4), θ1..θ6, η_L(m), η_R(m)]`,帆板模态数 m 默认 3,可配置。
- 中心体按 **6DOF 刚体**,臂安装点、帆板界面位姿一律从 `config/geometry/` SSOT 读取,禁止手抄数字(决策 D-YH-1)。
- 帆板用**浮动坐标法 FFR 悬臂模态**(决策 D-YH-3):模态频率与平动/转动模态动量系数(B_t, B_r)由参数卡生成;杨恒的数值案例未到之前用占位参数,并在裁决 JSON 中显式标记 `PROVISIONAL_PARAMS: true`。
- 动力学方程:`M(q)q̈ + C(q,q̇)q̇ + Kq = Q`,质量阵按基座 b / 臂 a / 帆板 η 分块(M_bb, M_ba, M_bη, M_aa, M_aη, M_ηη);K 仅作用于 η(diag(ωᵢ²)),模态阻尼比 ζ 可配置默认 0.005。自由漂浮,无外力外力矩。
- 附加输出:广义雅可比 J*(帆板增广形式)与基座扰动时程。
- 实现约束:纯 numpy/scipy(Radau/BDF),不新增重依赖,不用 pytest(沿用 assert 式 run_all)。

## 2. 场景(工况)定义 → 参数卡

新建 `config/coupled_scene/`,全部参数进 YAML,代码零硬编码:

- **scene_A1_arm_slew**:臂从收拢位形到预抓取位形,关节五次多项式轨迹(时长参照 sim_05 工况),记录基座姿态扰动与帆板模态响应;帆板刚化开关必须能复现 sim_05 的 19.20°。
- **scene_A2_capture**:在 A1 末态叠加 sim_06 矢量式捕获冲量(150 kg 碎片 @3°/s 工况),记录帆板振铃与整星动量重分配。
- YAML 内容:几何/质量/惯量引用 SSOT 路径、帆板模态参数(占位)、轨迹参数、积分器容差、随机种子(如有)。

## 3. 验证 Gate(全过才算数,输出 *_gate_check.json)

1. **动量守恒**:全系统 |Δp|、|ΔL| ≤ 1e-12(目标向 sim_05 的 7.3e-17 看齐)。
2. **能量审计**:无阻尼时,关节输入功 = ΔT + Δ应变能,相对误差 < 1e-8。
3. **退化链**(决策 D-YH-4):
   - 锁死关节 → 与 sim_07 基准一致;
   - 帆板刚化(η≡0)→ 复现 sim_05 基座扰动峰值 19.20°,容差 < 0.1%;
   - 臂+帆板全刚化 → 退化为 sim_01 守恒基线。
4. **收敛性**:m = 2/3/4 与 rtol 扫掠,关键量(基座峰值扰动、帆板末态模态能)变化 < 1%。
5. **交叉求解**:Radau vs BDF 关键量差 < 5%(e15 教训:5.64% 曾判 FAIL,勿重蹈)。

任一 Gate 不过:裁决 JSON 写明 FAIL 与复现命令,不得在文档中口头淡化。

## 4. 交付物(目录四件套)

```
sim_11_coupled_dynamics/
├── src/          动力学核心 + 场景驱动
├── results/      CSV + JSON(含 *_gate_check.json)
├── tests/        run_all.py(assert 式,含退化链与守恒断言)
└── docs/         中文报告 md
```

报告必须包含:方程与分块推导、退化对比表(vs sim_01/05/07)、A1/A2 结果图、PROVISIONAL 参数清单(待杨恒数值案例替换的字段逐一列出)。

收尾更新 `CLAUDE.md` 协作者记忆区:记录本次落地、Gate 结论、待办(等杨恒参数卡后替换占位并重跑全部 Gate)。

## 5. 红线

- 不修改 sim_01..08、e15/e16、src/sim_09、config/geometry 等任何冻结内容;只新增。
- 测试 PASS ≠ 科学 Gate PASS,科学结论只认机器裁决 JSON。
- 引用既有数字(19.20°、92×、7.3e-17、5.64%、3.06°/s、3.65 N·m·s)照抄勿改。
- 路线 B(NCF+ANCF 对标)与 ANCF 捕获瞬态精算**不在本任务范围**,只在报告"后续工作"一节列出。
- 全程中文文档与提交说明。
