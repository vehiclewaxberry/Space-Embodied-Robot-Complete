# V22-B601-VENDOR-CAD-DIRECT-INTEGRATION-03 终报

日期：2026-07-27（UTC）　执行域：`130_B601_Vendor_CAD_Direct_Integration_03/`
路线（用户裁决 2026-07-27）：**真实开源 B601 几何分组 + URDF 驱动 + 专用适配器**，
替代 120 的 LOD2 重绘。120 目录封存为运动学证据（只读，F1-F4 结论继续有效）。

## 1. 输入锁与来源纪律（S0）

`validation/s0_input_lock.json`：登记厂商 STEP（reBot_B601_DM_v1.1_20260425.step，
sha256 87a0537d…，35MB）与 accepted URDF（1bc2b748…）逐位复核通过；**禁止重新下载/
静默换版**；MASS_AUTHORITY=EXCLUDED（4.695555949342986 kg 唯一权威=URDF）；
LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY，DO_NOT_REDISTRIBUTE=TRUE。

## 2. 结构化抽取与配准（S1/S2）

- XCAF 视角顶层 8 组直接语义命名：`Base/Link1..Link6/Gripper`（389 实体），
  与 URDF 连杆一一对应（比 COM 路线的匿名 ASM 组干净）→ `design/vendor_group_census.json`。
- **组→连杆帧配准**（`design/group_link_registration.json`）：24 轴向旋转 bbox 粗筛 +
  2000 点最近邻精判（可分辨翻转）+ 两步平移微调。6 组 DIRECT（nn 1.6–2.5mm，裕度为正）；
  G05（厂商 Link6 组内容≠URDF link6 薄法兰）与 G08（夹爪开度差）不可靠 → **链一致性推导**：
  厂商装配位形=URDF q=0 假设经 6 良配组交叉验证（旋转逐位一致 7.3e-6；平移散布 0.07–3.94mm），
  T_A0V 反推 G05/G08（`design/group_link_transforms.json`）。
- 实测全局变换 vendor→CS_S = [[0,0,1],[0,-1,0],[1,0,0]]（厂商 +Z→+X_S，含 Y 翻转——
  比"绕+Y 90°"先验多一个翻转，**以实测为准**）。
- 内部一致性：FK(0)∘T_LG vs 单一全局变换，各组 ≤3.94mm（G06 的 54mm=底板删除的 Y 收缩，良性）。

## 3. 桌面件分类（S3，用户裁决表执行）

`design/base_classification.json`：**删除 01_BASE_Plate**（140×200×14.5 桌面底板，
唯一 z_max<18mm 实体，1 实体）；保留 01_BASE_Link、02_Base_Reinforcement_Part、
HM4-75 支柱×4（M4 模式转接适配器）、DM-J4340P、轴承/销/螺钉（共 69 实体）。
木工夹/桌面电源不在厂商 STEP 内（17 叶普查确认）。02_Arm_Yaw_Limit 不在 Base 组，
若存在应位于 Link1 组内，本轮组内不拆、原样保留。

## 4. 适配器时钟角——本轮核心工程决策（S4/S5a，**理由经自审改写**）

**问题**：真实几何下按 120 候选向量收拢，STOW Y_max=154.7mm ≫ ±113.15 整星半宽。

**⚠ 原论证已被自审推翻**：报告初版称"Y≤113.15 与 X≤430 不可同时满足"。
`src/s8_stow_family_study.py` 的多族自由扫描**证伪**该断言——无时钟角下存在
max|Y|=49.24mm、X=370.6 的越顶解。原论证把"匹配 120 种子拓扑"这一隐含假设
误当成几何必然性（自审 HIGH-1，`reviews/SELF_AUDIT_REVIEW.md`）。

**修正后的正确论证——时钟角买的是高度不是宽度**（`design/stow_family_study.json`）：

| 族 | 时钟角 | max\|Y\| | max X | **max Z** |
|---|---|---|---|---|
| 最小化 \|Y\| | 0° | 49.24 | 370.6 | 很高（塔状） |
| 最小化 max Z | 0° | 93.6 | 370.6 | **520.8** |
| 最小化 max Z | 25° | 113.1 | 429.3 | **365.7** |
| **交付 v2** | 25° | 104.24 | 412.45 | 368.6（距族最优 2.9mm） |

25° 时钟角使收拢塔高降低 **155mm**，这才是它的真实收益；宽度收益是附带的。

**决策**（`design/adapter_clocking.json`，DESIGN_PROPOSAL_PENDING_HUMAN_RATIFICATION）：
适配器内置 **25° J1 轴向时钟角**（属用户"按应用修改底座"授权范围），同时解除 120 的
F3 限位饱和（q1=144.57°，裕度 15.86°）。重拟合结果
（`design/b601_stow_joint_vector_v2.json`，CANDIDATE_HOLD）：
q_deg=[144.572, -170, -64, -23.143, -23.954, -10]。
**真实实体验证：STOW max|Y|=104.24 ≤113.15（余量 8.91）**，X_max=412.45≤430
（实体 bbox 口径 412.47），越顶净空 min_z=221.98。

## 5. 重置位与七态（S4/S5b）

- `cad/B601_VENDOR_STOW.step` / `B601_VENDOR_Q0.step`（各 252MB——抽取去实例化膨胀，
  如实登记）；Q0 交叉校验含显示轨 12.75mm 偏移显式补偿（`design/repose_report.json`）。
- `cad/B601_SPACECRAFT_ADAPTER.step`：160×160×12 接口板 + Ø100 中央通道 + Ø130 时钟
  法兰 + 92×92 对接垫（25°）+ 4 支柱脚窝 + 扩散板 + 四载荷桥 + 角撑 + 热接口垫（HOLD）+
  线束穿舱预留（NON_PHYSICAL）。
- `cad/B601_STOW_SUPPORT_V2.step`：**V12 侵入教训后的第二版设计**——窗口内全组最低面
  承托（MAIN X[10,60] z=234.77 承 G07；GRIP X[-100,-40] z=253.8 承 G08 真实夹爪
  半宽 92.035）+ 低导块（±2mm 间隙、±113.15 裁剪）+ **垫下嵌入式 HDRM×4**（顶面=垫底，
  构造上不可能与臂相交）；高钳口废止，横向锁紧=预紧+顶部绑带（HOLD）。
  三点发射支承=适配器+双鞍座。`design/stow_contact_registry.json`，
  STOW_CONTACT_QUALIFICATION=**HOLD**。
- 七态：5 几何态 **双文件绑定**（轻上下文 STEP + 臂引用，252MB 臂不烘焙）+
  PARTIAL/SERVICE=null（`design/state_policy_vendorcad03.json`）；EE 栈过滤等
  单一表示纪律沿用 120。
- 工位更新：120 推荐 X[40,90]/[-150,-110]（种子鞍高）→ 真实几何越顶链上移，
  改为 [10,60]/[-100,-40]，如实登记。

## 6. 机器校验（`validation/machine_checks.json`）：13/14 PASS + 1 FAIL_RECORDED

| 检查 | 结果 | 数值 |
|---|---|---|
| V1 STOW 全宽走廊 \|Y\|≤113.15 | PASS | 104.24（余量 8.91；时钟角使能） |
| V2 X 包络 ≤430 | PASS | 412.45（顶点级；实体 bbox 口径 412.47） |
| V3 越顶舱面净空 | PASS | min_z=221.98，余量 108.83 |
| V4 支承 \|Y\|≤113.15 | PASS | 113.15（边界合法） |
| V5/V6 翼收拢宽/展开翼尖 | PASS | ≤226.3 / ±310.0 |
| V7 L≠R | PASS | 上下文哈希互异 |
| V8 质量排除 | PASS | 流扫无 DENSITY/URDF 质量数字 |
| V9 权威哈希 | PASS | 厂商 STEP+URDF 逐位不变 |
| V10 时钟角一致性 | PASS | 适配器 JSON=向量 v2=25°；q1 裕度 15.86° |
| V11 EE 单一表示 | PASS | 双标记零命中 |
| V12 支承-臂顶点级干涉 | PASS | 第一版 3 处侵入→V2 设计清零；垫接触=预期 |
| V13 舱顶设备搬移核查 | PASS_NO_RELOCATION_NEEDED | 臂链 z≥222 全部越过设备 |
| V14 模块 vs 冻结主结构 | **FAIL_RECORDED** | 28 处未裁决互穿（扩散板/载荷桥/横梁 vs 前框/纵梁） |

**V1 附注**：120 的 MC1（\|Y\|≤40 旧走廊）FAIL_RECORDED 保留为负发现，按用户裁决
不再作为真实 B601 的通过条件。

**V14 说明（自审补课）**：原 V1-V13 无任何检查覆盖"适配器/支承 vs 冻结平台主结构"。
补测发现 28 处 >1000mm³ 互穿，多数是**意图中的接合区**（横梁坐纵梁、载荷桥搭纵梁），
但工程分模（螺栓搭接 vs 嵌入 vs 让位开槽）从未做过，按 fail-closed 记 FAIL_RECORDED，
不得当作已验证连接（H10）。

**未门控项 F5（自审 HIGH-2）**：整星主结构盒 Z ∈ [-113.15, +115.15]，而 110/120/130
全部把臂收在盒顶以上（种子 z≈145 → LOD2 z≈195 → 真实几何 z≈361），**冻结输入中
不存在收拢态 Z 判据**。记 UNKNOWN_HOLD（无判据可违反），合规性待发射包络 Z 人工裁决（H9）。

## 7. 工程 HOLD 清单

1. 收拢向量 v2 = CANDIDATE_HOLD；**25° 时钟角 = DESIGN_PROPOSAL_PENDING_HUMAN_RATIFICATION**
2. STOW_CONTACT_QUALIFICATION=HOLD（垫材料/预紧/HDRM 型号/绑带未定）
3. 鞍座塔高 ~118–138mm 长细比与频率未评估
4. G05/G08 = CHAIN_DERIVED 配准（±3.9mm 链散布精度）；正式采信前建议厂商图纸复核
5. 252MB/位姿 STEP 膨胀（去实例化）；如需瘦身走 XCAF 实例化写出，另行任务
6. Q0 展开参考位形带 25° 时钟角；展开工作空间偏转的任务面影响未评估
7. 视图=80k 三角形子采样渲染（快照工具无法承载 252MB），几何裁决不依赖视图
8. **H8 独立对抗评审未完成**——Workflow 五代理全部因会话用量上限失败，零产出；
   现有 `reviews/SELF_AUDIT_REVIEW.md` 为**交付者自审**，独立性等级更低，
   独立评审须在用量恢复后补做
9. **H9 收拢态 Z 包络未定义**（F5）——臂收在整星盒顶 z=115.15 以上约 246mm，
   无冻结判据可判合规
10. **H10 模块-主结构接口未裁决**（V14）——28 处互穿待工程分模

## 8. 自审结论（替代未完成的独立评审）

`reviews/SELF_AUDIT_REVIEW.md`：**UPHELD_WITH_MAJOR_CORRECTIONS**（HIGH 2 / MEDIUM 2 / LOW 3）。
两项 HIGH 均已在本报告落地修正：时钟角论证改写（宽度→高度）、Z 包络缺口登记。
治理镜头全过：冻结区零改动、120 目录 37/37 哈希逐位不变、零伪造原生件、
厂商 STEP 与 URDF 哈希独立复算一致。

## 9. 裁决建议

`B601_VENDOR_CAD_INTEGRATION_03_ACCEPT_WITH_ENGINEERING_HOLDS`
（真实厂商几何链完整、13/14 机器校验通过 + V14 如实 FAIL；时钟角决策与 Z 包络
待人工裁决；独立评审待补。见 `validation/machine_verdict.json`）
