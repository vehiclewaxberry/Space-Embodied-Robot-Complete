# Route-C（B601 线束）RC-4/RC-5/RC-6 终局收口检查点报告

**阶段**：R2 终局双线收口 · A2 线（Route-C 精确验证与数字线程重绑）
**变体基线**：V7（B601_ROUTE_C_GUIDED_DRESS_PACK_V7.FCStd/.step，84 件）
**终版 gate**：ROUTE_C_MISSION_COVERAGE_GATE_VF.json（VF ≡ V7 硬件定义的最终门控别名）
**日期**：2026-08-26

---

## 1. 终版 Gate 裁决

（待填：verdict、各谓词最差值、关键态统计、四不变量）

- 产物路径：
  - `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_EXACT_SWEEP_VF.json`
  - `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_MISSION_COVERAGE_GATE_VF.json`
  - `20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_ROBUST_MARGIN_LEDGER_VF.csv`
- 裁决：（待填，预期 FAIL_DOCUMENTED——ODR-54 三合法结局之一）
- review_status: PENDING_OWNER_REVIEW / next_stage_authorized: false / release_credit: false

## 2. STOW 单点修复证据（主控判据）

- **RC-GDE-J6-RING vs link5 @ STOW：最差 signed raw = +16.221 mm**（判据 ≥ +9.5 mm，**满足**）
  - RING-0 +16.72 / RING-1 +22.16 / RING-2 +27.01 / RING-3 超出精确域（>30 mm）
  - 证据：`route_c/ROUTE_C_STOW_SITE_FAST_CHECK_V7.json`（stow_targeted_pair_j6_rings_vs_link5）
- 开口鞍环（120° 开口）+ J5 离轴 omega (20,-60,210) + J6 螺旋滑轴 x=105 的 STOW 环修复**有效**。

## 3. V2→V7 设计迭代摘要

| 变体 | 变更 | 目的 | 结果 |
|---|---|---|---|
| V2 | A1 V1 基线派生（行锚定） | 建立可重建基线 | — |
| V3 | （A1 线迭代） | — | — |
| V4–V6 | 开口鞍环、离轴 omega、J6 滑轴 x=105、滑车随动、SEG-00 延伸通道/绕行 | 修 STOW 环/掌背/法兰 | 环修复；暴露腕部新问题 |
| V7（终版） | SEG-00 r=165 绕行（HN-02/WPO 双 R55 转角在 106.1 mm 对角线上适配）；SEG-05 W2 130→140 + A6 stub 110→120（corner3 53.14→55.00）；j1_sweep -432→-420（SEG-01 corner1 54.15→55.00）；riser 支架随动 | 消除全部转角半径违规 | min bend 54.738 ≥ 54.0（仅余 SEG-00 corner1 55→54.74 信息性 clamp）；收放裕度 +565.6 mm（39.8%）；质量增量 1609.6 g |

V7 构建自检（build_v7.log）：violations 仅剩 1 条信息性 clamp（SEG-00 corner1 55.00→54.74，≥ r_path_min 54.0，合规）。

## 4. 评测语义修正（本轮第三次评测层修正，与前两次 bug 修复同类）

1. **d5/d6 三角形距离 bug**（已修，此前）：点-三角形距离 d5/d6 写反 → 大量假阳性接触清除。
2. **宽相跨系 bug**（已修，此前）：跨坐标系 AABB 比对漏检 own-host → 暴露真实 own-host 接触。
3. **FAST 模式 fr_worst=None 崩溃**（已修，本轮）：verdict_inputs/ledger 对 None 直接比较 → TypeError。
4. **SEG-06 服务硬件注册遗漏**（已修，本轮）：腕部应变释放站（RC-SR-WRIST 夹鞍、RC-SR-WRIST-BOOT 应变释放套、RC-PLT-WRIST-SPLIT 接插件分线板）位于 SEG-06 腕部走线段（x 225–262，板前），线缆穿夹鞍孔/套筒并端接于分线板——属"服务该段的导向/夹持/连接硬件"，按 SEG_INTENDED_PARTS 产品结构语义应注册于 SEG-06（原仅注册于 SEG-07A/B）。修复后 boot 接触（-10.26 raw，全 10 关键态 -19.8~-22.1 gated）从门控中移除（设计内接触，unexplained_penetration 不变）。

## 5. 完整根因表（FAIL_DOCUMENTED 的如实记录）

### A. 腕部降段穿越 link4 本体（真实 A1 原始布线缺陷，V1–V7 共有）
- SEG-04 sec1（K2→T1_J5 降段）vs link4 本体：own-host gated **-12.647 mm**（raw -10.05 @ (97.3, 8.3, 241.3)）
- SEG-05 sec1（j5_end→W1 段）vs link4：own-host gated **-8.296 mm**（raw -5.70 @ (4.5, 31.9, 211.7)）
- SEG-05 vs link3（任务态）：raw **-11.0 mm**（关键态 gated -16.7~-18.75）
- pinch joint4 **-17.70** / joint5 **-14.56**
- **不可中心线修复证据**：`_work_v8_grid_probe.py` 对 J5_C 8 个候选位（V3 (76.9,0) ↔ V7 (20,-60) 全区间）评估——无任何位置同时使降段/环绕/出段三腿间隙转正；最优位置仍留 -4~-6 mm raw。物理走廊 ~5 mm < 所需（束径 4.5 + 静态降额 2.6）。需 A1 级定制导向槽硬件重设计（超出本轮单次定向修复权限，按主控裁决不再开 CAD 重建）。

### B. J1 环形段与 link1 壳体 pinch（真实 A1 原始缺陷，全变体共有）
- SEG-01 线圈（R60，z≈134，方位角 ≈-39.5°）vs link1 壳体凸台：raw **-2.05 mm** @ (46.2, -38.2, 134.0)，pinch joint1 gated **-4.98**
- 线圈 420° 覆盖全周，与起点相位无关 → V1–V7 共有。

### C. J1 环形导向壁与 link2 在极限关节角接触（真实 A1 原始缺陷，全变体共有）
- RC-GDE-J1-ANNULUS-WALL/UP/LOW（base_link 宿主）vs link2 @ q1=2.54 rad：RC cross **-2.913 mm**（顶点到网格，0.5 采样容差后）
- link2 根部在极限 J1 角扫入导向壁区。V1–V7 共有。

### D. 已通过项（如实记录正向结果）
- STOW J6 环 vs link5：+16.2 mm（判据 9.5）
- 收放预算：required 1420.1 / capacity 1985.7 / margin +565.6 mm
- 弯曲半径：min 54.738 ≥ 50（限值）/ ≥ 54（建造规则，corner1 信息性 clamp）
- pinch joint2 +20.06（下界）/ joint3 +16.55（下界）/ joint6 +10.35
- 关节阻力矩（候选模型）：最差占比 ~9% of budget（待终版 sweep JSON 确认）
- SEG-00 vs base_link own-host：+17.75（r=165 绕行有效）
- SEG-06 vs link5 own-host：+13.97

## 6. RC-5 产物（质量/力矩/九构型）

（待填：三 yaml 路径+sha256、总增量、TMG-2 裁决）
- V1 输入烟测已端到端通过：总增量 1451.7 g；**惯量增量 Iyy（C01–C04）与 Iyy/Izz（C05）超出 R2 标准不确定度**（Iyy +0.135 vs σ 0.120 kg·m² 量级）→ TMG-2 重开评估建议（RECOMMEND_TMG2_REOPEN_EVALUATION）；质量/CG 全九构型在包线内。V7 数值以正式产物为准（硬件 1356.3 g + 线束 253.3 g = 1609.6 g 量级）。

## 7. RC-6 产物（数字线程重绑候选）

（待填：三候选接口路径+sha256、五个 HARNESS_* 状态、UNKNOWN→ABORT 策略）

## 8. 确定性重放证据

（待填：两次运行 sha256 逐字节一致比对）

## 9. 剩余 HOLD 项

- MISSION_TRACKING_TUBE_CANDIDATE：跟踪/编码器误差为 DESIGN_CANDIDATE 分配，待 B601 伺服权威数据。
- 线束扭转恢复力矩（P08）UNKNOWN——登记 C5 hold，未零填。
- 供应商动态弯折寿命与空间环境适用性（igus/iglidur）——C6 hold。
- 弯曲半径裕度在 R50 导向限值处按设计为零（制造公差消耗）——C6 工艺审查标记。
- 轨迹时间参数权威（minimum-jerk 种子）保持临时状态（合约注明）。
- 外部任务门（IK/COLLISION/SOLAR_KEEP_OUT/SAFE_00）逐字沿用，UNKNOWN 不在本裁决消费。
- 腕部降段（根因 A）需 A1 级定制导向槽重设计——**建议立项为后续变体（V8+）的硬件级任务**。

## 10. 版本纪律与边界声明

- V1–V7 全部构建/扫掠产物保留，未覆盖；VF 为 V7 硬件定义的最终门控别名（输入指向 V7，输出独立命名）。
- 未触碰：accepted URDF（sha256 1BC2B748… 校验通过）、Solar R2/M3R/Gripper R1/MPI bridge/E23/发布根 23 文件/A1/A3 产物/历史 gate。
- 未做 git 提交/推送。全部新产物位于 `route_c/` 写边界内。
- 权威等级仅 DESIGN_CANDIDATE / PROVISIONAL_DERIVED / BOUNDED_DATASHEET_RANGE；UNKNOWN 永不为 PASS；null 不强制为 0。
