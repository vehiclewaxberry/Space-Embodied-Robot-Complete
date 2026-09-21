---
title: F4R1 C1 内部布局方案 V1（三舱分配 / 质量故事 / CG 故事 / CDS 符合性声明）
generated_at: 2026-08-27
status: DESIGN_RESEARCH_CANDIDATE
source_basis:
  - "B1 基准表与 14 条设计规则 (sha256 738bb4cf6402)"
  - "ODR-F4R1-01 质量口径裁决 (sha256 88fb25431d1a)"
  - "V3 R2 冻结质量账本 C01 (sha256 3fd2557318e9)"
  - "机器核算 CG_INERTIA_CHECK_V1.json (compute_c1_checks.py 可重跑)"
  - "EQUIPMENT_LIST_V1.yaml / MASS_BUDGET_V1.csv (同目录)"
---

# F4R1 C1 内部布局方案 V1

## 1. 三舱分配与理由

布局坐标系：S frame（原点 = 12U 几何中心，x = 纵轴，任务/臂方向为 +x；冻结 340.5 mm 基线，366.0 mm 冲突登记 OI-6）。舱段沿 x：rear_service [-170.25, -56.75] / mid_avionics [-56.75, +56.75] / front_mission [+56.75, +170.25] mm。分舱拓扑继承 PDR-D-003，与商用 12U（ISIS、NanoAvionics M12P）同构（B1 §7.1、R4）。

| 舱 | 内容 | 关键布局决策 | 依据规则 (B1 §6) |
|---|---|---|---|
| front_mission | B601 臂（基座 x=208.0 mm 冻结）、M3R+load_bridge（冻结）、导航相机+照明、F/T 传感器、前向太阳敏感器 | 任务面朝 +x；相机/照明贴近前面板出光；F/T 串入 M3R 与臂基座接口栈，不改站位 | R4（任务朝任务面） |
| mid_avionics | OBC+EPS（PC/104 堆栈 A）、双 BPX 电池（独立 -z 安装面）、4×RW400 轮组（近几何中心金字塔）、IMU、双星敏（±z 面）、磁力矩器×3、太阳敏感器×4 | 重件（电池/轮组）近中心压惯量；敏感器-执行器间距最大化（IMU 距轮组 ≥90 mm）；堆栈先成组件整体入框 | R5（PC/104 双堆栈）、R6（重件居中）、R7（间距）、R8（发热件贴面板）、R9（电池独立面+100 Wh 分档） |
| rear_service | VACCO MiPS 推进（推力轴过质心）、EWC31 电台、GPS 接收机+天线、S-band/UHF 天线（-x 面）、磁强计（远磁源角）、后向太阳敏感器 | 推进/贮箱靠 rear 是 sim_08 消旋刚需；≥3 级 inhibit 空间预留；天线 -x/+z 面无视场遮挡；磁强计距磁力矩器 ≥130 mm | R4（推进朝后）、R7、R10（推进 5 条）、R11（线束走廊 rear→mid→front） |
| distributed | 被动热控（MLI+涂层）、内部线束、二级结构 | 分布质量按 CG 中性建模；高热设备与电池分舱/隔热：EPS/电台贴面板导热，电池独立 -z 面远离 EPS 热源 | R8、R9、R11、R14（泄压/材料待 C2 细化） |

干涉控制：全部设备按含安装间隙的长方体包络建模，关键对（电池↔轮组、EPS↔OBC、MTQ↔电池）已做 z/x/y 向错位（R12）；帆板根部缺口布置 ±y 太阳敏感器为 ASSUMED 布置，待 C3 CAD 验证。

## 2. 设备选型理由（摘要）

- **分布式 ADCS 而非 0.5U 集成件**（4×RW400+ST200×2+nanoSSOC×6+STIM300+CubeTorquer×3 ≈ 1.19 kg）：保留绕质心配平自由度（B1 §7.3 权衡）；轮组仅负姿态保持/预偏置，消旋主责在推进（sim_08：|H_c|=3.65 N·m·s = 12× 轮组容量，B1 §3.1）。轮组安装面规范（ASSUMED）：平面度 0.05 mm、对准 0.1°、局部一阶模态 ≥200 Hz。
- **双 BPX 100 Wh 电池**：200 Wh 支撑 RPO+抓捕高峰值；单包 100 Wh 分档参考 CDS §2.1.5；独立安装面 + 加热/保护板余量（R9，MDPI 扩容案例）。
- **VACCO Standard MiPS（542 g 含工质，44 N·s，0.3U）**：B1 §4 中唯一质量/总冲均有来源的 12U 级全系统；自增压冷气无肼毒险。粗估消旋 150 kg 目标（双 25 mN 推力器 @0.1 m 力臂 ≈ 5×10⁻³ N·m）需约 730 s、36.5 N·s < 44 N·s 容量——可行但余量薄，升级选项登记 OI-7。
- **S-band TT&C（EWC31）+ UHF 备份 + GPS（OEM719）**：RPO 相对导航与测控基线；电台质量为 B1 类目中值 ASSUMED（EWC31 确切质量 B1 §8 列 UNKNOWN，不编造）。
- **F/T 传感器新增**：冻结账本与 V2-UNK-012 均确认 F/T 无 frozen 行，故按 ASSUMED 新增（非重复计）。

## 3. 质量故事（M1 结论）

**M1：31.0229 kg 是否已含内部设备？——双读法并列，分解状态 UNKNOWN。**

- 证据链：(i) V3 R2 C01 行项目 = bus 23.3032134 + B601 4.6955559 + M3R 0.7619 + bridge 0.7021955 + 双帆板 2×0.78，**无任何设备行**；(ii) bus 23.3032134 的出处是 `service_spacecraft_v1.yaml`：servicer_12U_v0 **24 kg 整星块模型减去 2 帆板的拆分余额**——物理上它是"整星全部内容（含设备）"的集总包络 proxy，且 02_PRODUCT_STRUCTURE 自述 "solid envelope proxy: no internal structure, no bays"。
- **读法 A（主口径，登记）**：bus 块隐含整星设备分摊 → 新增设备行是对块内质量的分摊说明，**不作加法**；TOTAL_DESIGN_POINT = **31.022864807 kg**（ODR-F4R1-01 主口径，ESPA 级登记，"12U-derived form factor" 与 deployer 合规解绑）。
- **读法 B（加法上限，声明不登记）**：若把 bus 块当纯结构，设备须另加 → **36.659864807 kg**。
- **分解 UNKNOWN**：23.303 kg 块的结构/设备份额现有证据不可分（as-built 计量 HOLD，GAP-MA-02 / V2-UNK-007/008），禁止猜测，待实物称重（OI-2）。

两口径总计：

| 口径 | 总质量 | 说明 |
|---|---|---|
| TOTAL_DESIGN_POINT（主） | **31.0229 kg** | = 冻结 C01；读法 A；ESPA 级登记 |
| TOTAL_DESIGN_POINT_READING_B（上限） | 36.6599 kg | 读法 B 加法上界，声明不登记 |
| TOTAL_CDS_VARIANT_24KG | **17.6601 kg（含 15% 余量）** | ≤ 24 kg ✓（余量 6.34 kg） |

CDS 变体从主口径砍掉/替换的行与理由：**替换 FRZ-BUS（23.303 kg 包络 proxy）→ ST-STRUCT-REAL 2.0 kg（B1 表 3：12U 真实结构 1.2–2.0 kg，取保守上限）+ EQ-SEC-STRUCT 1.0 kg 二级结构**；理由：proxy 的 provenance 是 24 kg 块模型拆分余额而非物理结构，CDS 合规线必须按真实结构重建。臂/M3R/桥/双帆板/全部设备原样保留；余量按 B1 R2（VMMO 15%）。与 V3 R2 调和：6 个冻结行逐值一致，新增 5.637 kg 设备行声明为 C-ISS-04 缺口闭合，机器复算未解释项 = 0。

## 4. CG 故事

CDS 包络映射：CDS_Z（纵轴）→ S_x ±70 mm；CDS_X/Y → S_y/S_z ±45 cm→mm（±45 mm）。冻结 C01 自身 CG = [+65.76, -26.59, -17.68] mm，x 裕量仅 4.24 mm（臂前拉所致）。布局策略：设备质量向后舱/中舱后部集中（电池 x=-10、推进/电台 x=-113.5、天线 x=-170），把 CG 回拉：

| 场景 | 总质量 kg | CG_S mm | 裕量 mm (x/y/z) | 判定 |
|---|---|---|---|---|
| A 主口径（读法 A 切出） | 31.0229 | [+63.24, -26.88, -19.02] | +6.76 / +18.12 / +25.98 | **pass** |
| B 上限（读法 B 加法） | 36.6599 | [+53.40, -22.75, -16.01] | +16.60 / +22.25 / +28.99 | **pass** |
| CDS 变体 | 15.3567 | [+127.83, -54.30, -39.10] | **-57.83 / -9.30** / +5.90 | **fail（登记 OI-1）** |

主口径两读法均过包络，且布局后 x 裕量由 4.24 mm 改善到 6.76 mm（A）/16.60 mm（B）。**CDS 变体 CG 失败是真实工程发现**：bus 减重 21.3 kg 后，4.70 kg 机械臂占全船 30.6%，其 CG（x=+377, y=-176 mm）主导全船；确定性 x 向配重迭代（6 旋钮推至舱内边界，最大移程 41.75 mm）仅改善 0.85 mm，残余 -57.83 mm，判定 INFEASIBLE_WITHIN_X_KNOBS；y 超差不受 x 旋钮影响（NOT_ADDRESSABLE）。出路（进 C2）：(i) 用臂收拢发射构型重核（该构型质量特性在 CDR 口径 NOT_EVALUABLE，OI-3）；(ii) 后舱结构级配重（粗估 ~3.2 kg @x=-170 mm 量级）或推进/贮箱大型化后移；(iii) owner 豁免。惯量输出（信息性）：场景 A Ixx/Iyy/Izz = 0.764/1.157/1.548 kg·m²；CDS 变体 0.365/0.599/0.857 kg·m²（冻结成员按质点近似，仅影响惯量不影响 CG）。

基线声明：全部 CG 核算基于 C01 在轨展开构型；CDS 发射符合性的最终裁决须待收拢构型质量特性闭合（OI-3）。

## 5. CDS 符合性声明写法建议（供论文/报告直接引用）

**英文（主口径，2 段）：**

> The servicer is a 12U-derived form-factor free-flying servicing spacecraft (226.3 × 226.3 mm cross-section, 340.5 mm bus length per the frozen project baseline). It is not manifested against a 12U P-POD/deployer constraint; its design mass of 31.02 kg is therefore registered under an ESPA-class rideshare/smallsat mass scope rather than the CubeSat Design Specification (CDS) Rev 14.1 12U limit of 24.00 kg (ODR-F4R1-01, 2026-08-27).
>
> As a parallel compliance line, a CDS-conformant variant budget was constructed bottom-up (real 12U primary structure of 2.0 kg class replacing the 23.303 kg envelope-proxy lump): 15.357 kg dry, 17.660 kg including a 15% system margin, i.e. within the 24.00 kg limit. Its center of mass, however, exceeds the CDS envelope in the on-orbit deployed configuration (CG at [+127.8, -54.3, -39.1] mm versus ±70/±45/±45 mm limits — an exceedance of 57.8 mm in +x and 9.3 mm in -y), because the 4.70 kg capture arm dominates a 15.4 kg vehicle; closure is deferred to the stowed-launch-configuration mass properties and an aft-ballast study (registered open item OI-1/OI-3).

**中文（主口径，2 段）：**

> 本服务星为 12U 形式因子衍生的自由飞行服务航天器（横截面 226.3×226.3 mm，冻结基线舱长 340.5 mm），不承诺 12U P-POD/deployer 发射约束；其设计质量 31.02 kg 按 ESPA 级拼车/小卫星搭载口径登记，而非 CDS Rev 14.1 的 12U 24.00 kg 上限（ODR-F4R1-01，2026-08-27）。
>
> 作为并行合规线，CDS 合规变体按自下而上重建（2.0 kg 级真实 12U 主结构替换 23.303 kg 包络 proxy 块）：干重 15.357 kg，含 15% 系统余量 17.660 kg，满足 24.00 kg 上限；但其质心在在轨展开构型下超出 CDS 包络（CG=[+127.8, -54.3, -39.1] mm，限值 ±70/±45/±45 mm，即 +x 向超出 57.8 mm、-y 向超出 9.3 mm）——4.70 kg 抓捕臂在 15.4 kg 量级全船中占主导所致；闭合依赖收拢发射构型质量特性与后部压载研究（登记开放项 OI-1/OI-3）。

## 6. 遗留项清单（进 C2/C3）

| 去向 | 事项 |
|---|---|
| C2 | OI-1 CDS 变体 CG：后部压载/推进大型化/设备再分配权衡；OI-7 推进总冲升级（44→500 N·s 级）与后舱空间；OI-4 ASSUMED 行 datasheet 化；电池/推进泄压孔与非金属材料 TML/CVCM（R14）；轮组隔振与微振动评估 |
| C2 | OI-3 收拢发射构型质量特性（需臂收拢关节向量，frozen ledger blocking input） |
| C3（2026-09-02 后，ODR 限制） | 二级结构 CAD（GAP-IL-06）、干涉检查 R12 全量、托盘抽取方向（GAP-IL-07, post_paper） |
| owner | OI-5 T_SB 签署（CAND-1: B≡S）；OI-6 外廓 340.5/366.0 裁决（post_paper）；OI-2 as-built 计量资源 |
| 不碰（纪律） | 帆板参数（C2 专属）、Route-C 外部线束实物（HOLD）、冻结区任何文件、比赛提交包 |

## 7. 复算方式

`python compute_c1_checks.py`（仅标准库）重算：质量预算行（csv↔yaml 一致、V2 9 placeholder 合计、两口径总计、15% 余量）、V3 R2 调和（未解释=0）、三场景 CG/惯量、CDS 包络与配重迭代日志，输出与 `CG_INERTIA_CHECK_V1.json` 一致。
