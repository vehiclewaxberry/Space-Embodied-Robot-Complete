# V22-B601-GEOMETRY-AND-POSEMAP-02 终报

日期：2026-07-26（UTC）　执行域：`120_B601_Geometry_and_PoseMap_02/`（唯一写区）
工具链：STEP_FIRST_PARAMETRIC（build123d；资源裁决 DOWNGRADE_8GROUP_BODY_MAPPING_ROUTE，
free_phys 1074 MiB < 4 GiB 阈值；headless LoadFile4 维持 FORBIDDEN；未伪造任何 SLDPRT/SLDASM）。

## 1. 权威与输入锁（G1）

`validation/frozen_zone_precheck.json`：canonical_top / accepted_urdf / registered_step /
scratch_native 四项 authority_match 全 true；另钉 110 太阳翼位姿、arm_stow、swap01 映射等 7 项输入哈希。
收尾复核 MC7 再次全匹配——冻结区零改动。

- KINEMATIC_AUTHORITY = accepted URDF（唯一）；MASS_AUTHORITY = EXCLUDED（4.695555949342986 kg 不入 CAD）
- GEOMETRY 尺寸依据 = `b601_q0_boxes.json`（URDF 网格 q0 实测盒）+ `body_mapping.yaml` 8 组语义
- LICENSE_CLASS=E3_INTERNAL_RESEARCH_ONLY；DO_NOT_REDISTRIBUTE=TRUE；DERIVATION_CLASS=SPACECRAFT_ADAPTATION

## 2. S2 帧映射与收拢向量（核心科学发现）

产物：`design/b601_urdf_to_cad_frame_map.yaml`、`design/b601_joint_axis_registry.yaml`、
`design/b601_stow_joint_vector.json`。安装映射 T_S_base=[198,0,0]（显示轨）+ R_SM（URDF z→+X_S）。

**运动学发现（全部由 accepted URDF 真值导出，机器可复核）：**

| ID | 发现 | 后果 |
|---|---|---|
| F1 | 种子大臂 -X 后倾**不可达**：joint2 轴与臂向量恒 ⊥X_S，(axis×arm) 的 X 分量对 q1 不变号，q2∈[-π,0]⇒sin q2≤0⇒X 倾恒≥0 | 可达收拢族=大臂近垂直+前臂越顶回折；种子仅拓扑参考 |
| F2 | 中央走廊 \|Y\|≤40 违规（关节心 max\|Y\|=70.9；实体级 118.6，含夹爪 154mm 掌板固有宽度） | MC1 FAIL_RECORDED；托架鞍座宽度按实测 Y 包络 |
| F3 | 越顶族解 q1=+160.0°（≈上限）、q2=-179.9°（≈下限）**双限位饱和** | 收拢位形限位裕度为零；展开首步只能向限位内侧 |
| F4 | 弃用族：厂商 q=0 折叠（Z 下探 -260 破包络）；外悬下折（X 594 外悬 411mm） | 记录于 stow JSON |

**收拢向量（STOW_VECTOR_STATUS=CANDIDATE_HOLD，禁止写成 accepted）：**
q_deg = [160.0, -179.909, -53.909, -25.143, -29.954, **157.591**]；
EE=[-121.9,-38.8,161.1]（种子 [-150,0,145]，残差 50.6mm）。q6=157.591° 为掌板调平步
（雅可比证明 q6 纯自旋不动 EE），消除掌板角点下探舱面 11.6mm（MC10 根因修复）。
方向误差：upper 69.25°（=F1 不可达代价）、fore 23.45°、wrist 16.07°。

## 3. S3 LOD2 臂几何

`cad/B601_LOD2_STOW.step` / `cad/B601_LOD2_Q0.step`（各 21 实体，8 组按 body_mapping：
基座壳+颈筒 / J1 电机筒 / 肩叉架+J2 筒 / 成对大臂板+罩 / 成对前臂板+J3/J4 筒 /
腕连接+J5 筒 / 腕支架+J6 筒 / 掌板+双导轨+双指）。可辨识拓扑达标（视图 v01/v02）。
**独立对拍**：Q0 位形整体包络 X_max=461.98 vs 实测盒 467.45、Z_min=-269.2 vs -260——
FK 置位链与厂商网格实测一致（差值=LOD2 简化截面所致，非位姿错误）。

## 4. S4 安装 / 收拢支承 / 捕获头

- `cad/B601_MOUNT_MODULE.step`（13 实体）：接口板 160×160×12、适配环 D130/D100、加强载体、
  前扩载板、四载荷桥（至 ±105.65 纵梁）、四角撑、线束/连接器预留（NON_PHYSICAL）。
- `cad/B601_STOW_SUPPORT.step`：横梁×2（跨 ±105.65）+ 主鞍座（X 40..90，夹持腕连接件+J5 筒，
  接触高 z=156.45 实测）+ 腕鞍座（X -150..-110，夹持导轨+指，z=140.02）+ 接触垫 + HDRM×4。
  **主鞍座 +Y 钳口被 ±113.15 包络裁剪至 1.2mm→弃用，登记顶部绑带 HOLD**。
  三点发射支承 = 安装法兰 + 主鞍座 + 腕鞍座。
  `design/stow_contact_registry.json`：STOW_CONTACT_QUALIFICATION=**HOLD**（无强度/预紧权威）。
- `cad/CAPTURE_HEAD_CANDIDATE.step`：独立模块（接口环 D120/外壳 D140/三径向指/LED 环/视觉通道），
  与 B601 夹爪互斥，不入七态。

**鞍高种子修正**：110 种子布局假设走廊 z=145；FK 真值走廊 z≈158–195，鞍高以实测为准（S5 已替换）。

## 5. S5 七态 staging

`staging/state_{STOWED,DEPLOYED_NOMINAL,DEPLOY_FAILED_BOTH,L_FAIL,R_FAIL}_LOD2.step` +
PARTIAL/SERVICE=null（fail-closed，继承 110 语义）。`design/state_policy_posemap02.json`。
太阳翼角度=110 冻结策略原样；STOWED 由 HOLD_B601_HIFI_ABSENT 升级为 LOD2_STOW@CANDIDATE_HOLD。

**单一表示替换（每子系统唯一表示）**：110 B601 安装代理→本任务安装模块；110 种子收拢布局→
本任务支承模块；110 AABB q0 代理→LOD2 臂；**110 旧捕获末端显示栈 FIDELITY_CAPTURE_*
（X 480–580）→剔除**（评审中发现的 EE 双重表示，MC8 已扩展扫描封堵）。

## 6. 机器校验（`validation/machine_checks.json`）

| 检查 | 结果 | 数值 |
|---|---|---|
| MC1 臂中央走廊 \|Y\|≤40 | **FAIL_RECORDED** | 118.62（F1/F2+夹爪固有宽；运动学事实非建模缺陷） |
| MC2 支承 \|Y\|≤113.15 | PASS | 110.0 |
| MC3 收拢翼宽 ≤226.3 | PASS | 实测（110 冻结源） |
| MC4 展开翼尖 ±310 | PASS | -310.0/+310.0 |
| MC5 L_FAIL≠R_FAIL | PASS | 哈希互异 |
| MC6 质量排除 | PASS | 无 DENSITY/URDF 质量数字 |
| MC7 权威哈希 | PASS | 四项全匹配 |
| MC8 EE 互斥 | PASS | CAP_*/FIDELITY_CAPTURE_* 双标记零命中 |
| MC9 X 包络 | PASS | 臂 382.69≤430；支承 [-170,110]⊂[-183,198] |
| MC10 越顶净空 >113.15 | PASS | min_z=128.53（余量 15.38mm，q6 调平后） |
| MC11 支承-臂 AABB | REGISTERED_COARSE_DIAGNOSTIC_NOT_A_GATE | 登记器非校验器（评审 M3）：垫切贴构造下 AABB 恒零，真实干涉判定留待 L3 |

## 7. 工程 HOLD 清单（不随本裁决消解）

1. STOW_VECTOR=CANDIDATE_HOLD（正式收拢向量需人工/载荷侧批准；F3 双限位饱和需展开策略评审）
2. STOW_CONTACT_QUALIFICATION=HOLD（垫材料/预紧/HDRM 型号未定；主鞍座 +Y 侧顶部绑带待设计）
3. MC1 走廊违规为 URDF 运动学事实——若走廊 |Y|≤40 为硬性发射需求，需重议走廊定义或臂安装方位
4. MC11 AABB 粗判非实体干涉证明；L3 精判未授权
5. LOD2 为集成级派生几何：无强度/质量/制造权威；厂商精细几何（P-C 路线）另行授权
6. 环境不支持原生 SW 件生成（资源裁决）——本轮交付=参数化源码+STEP，SLDPRT/SLDASM 零伪造

## 8. 裁决建议

`B601_GEOMETRY_POSEMAP02_ACCEPT_WITH_ENGINEERING_HOLDS`
（几何/映射/状态链完整且机器可复现；MC1 如实 FAIL + 六项 HOLD 在案；见 machine_verdict.json）
