# B3 V2 System Mechanical CAD — 验证报告

> `GATE: COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`
> `MACHINE_VERDICT: V2_SYSTEM_MECHANICAL_CAD_COMPLETE_WITH_PHYSICAL_LIMITATIONS (20/20)`
> `REVIEW_STATUS: PENDING_HUMAN_REVIEW`
> 人工授权：`evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml`（2026-07-25 会话人工指令）

## 1. 交付概览

原生 SolidWorks 2024 交付：57 个原生文件（48 SLDPRT + 9 SLDASM），顶层
`Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM`，六具名配置，全部由
`automation/` 下确定性脚本经 COM 构建（零手工建模），可重入、fail-closed、
全程日志（`evidence/build_logs/*.jsonl`）。

## 2. 阶段裁决链

| 阶段 | 裁决 | 证据 |
|---|---|---|
| B3-00 入口 | B3_ENTRY_BASELINE_LOCKED + B601_HASH_AND_TOPOLOGY_MATCH | b3_00/B3_entry_verification.json（V1 32/32+43/43、三包清单、B601 11 项比对、存档于 archive/） |
| B3-02 骨架 | B3_02_MASTER_SKELETON_VERIFIED | b3_02/master_skeleton_machine_check.json（CS/七面逐位对拍） |
| B3-03 主结构 | B3_03_PRIMARY_STRUCTURE_VERIFIED | b3_03/primary_structure_machine_check.json（14 件包围盒+恒等位姿） |
| B3-08 配置+干涉 | 六配置状态逐配置验证；6×16 干涉全为 B601 代理伪影，结构零干涉（含框测量） | build_logs/b3_10_fix_configs.jsonl + b3_08/interference_*.json |
| B3-09 数字线程 | 16 项清单齐备，claim 审计全 PASS，外部引用零越界 | digital_thread/ |
| B3-10 视图 | 15 视图 raw+annotated + 独立 target 场景（NO_CONTACT 水印） | 10_Review_Overlays/ |
| B3-10 退出 | 20/20 + 57/57 重开重建 | b3_10/v2_cad_01_20_evaluation.json、native_reopen_check.json |

## 3. 多代理评审（单写入者 + 多只读评审）

- **Round 1**（5 评审员：需求/坐标系/结构/维护性/红队）：requirements-auditor 判
  REJECT，3 HIGH + 2 MED（配置抑制未按配置隔离、重建中框未参与终版干涉、太阳翼
  全程未解析、判定谓词空洞、入口证据被覆盖）。全文：`multi_agent_review_round1.json`。
- **整改**：`b3_10_fix_configs.py`（两层修复：模块自查 + 逐配置 SetSuppression2 +
  fail-closed 读回验证）；干涉/视图重跑；判定谓词实质化（V2-CAD-04/13/16）；入口
  证据时间戳存档机制；D-V2-05 偏差登记。
- **Round 2**（requirements-recheck + redteam-recheck）：**ALL_REMEDIATED**，五项
  全闭环，谓词构造性可失败验证通过。全文：`multi_agent_review_round2.json`。

## 4. 已登记偏差（digital_thread/v1_to_v2_deviation_manifest.csv）

D-EQ-01 方程引擎不可用（VBA 缺失，参数权威=规格 YAML+PARAM_* 属性）；
D-V2-01 B601=STL bbox 代理（A3 授权表达）；D-V2-02 框环分段表达；
D-V2-03 无来源 volume owner 零实体；D-V2-04 中框径向内缩 110.15（含框干涉复测支撑）；
D-V2-05 外板配置隐藏语义（子装配子件配置级抑制不可靠）。

## 5. 非阻塞残留（复审登记，后续修订建议）

1. `_check_solar_states` 谓词覆盖 3/6 配置（其余 3 配置本轮经人工核验合规，
   建议补全 want 字典防回归）；
2. 干涉 JSON 记录 suppression 不记录 visibility（外板"隐藏"由渲染图+登记佐证）；
3. V2-CAD-04 对 frame_export 为子串级检查（建议结构化解析 disabled 节）；
4. 真正入口时刻（07-24 深夜）的原始 JSON 时间戳在存档机制建立前被覆盖
   （哈希内容逐位一致，仅时间戳溯源损失）。

## 6. 物理限界（不因本轮改变）

FEA/强度/刚度/模态/热 NOT_EVALUATED；材料/板厚/紧固件/预紧 UNKNOWN_BLOCKED；
质量/质心/惯量 CAD 零权威；T_SB、physical TCP、相机数值 FOV UNKNOWN_BLOCKED；
standard_12U_claim BLOCKED（NON_FLIGHT_DISPLAY_ONLY）；global_collision_safety
BLOCKED（V1 十处 q0 静态干涉 NEGATIVE_RESULT 记录级继承）；V2-UNK-001..017 未闭合。
后续 FEA/URDF round-trip/动力学/制造/A5/Git 提交均未授权。
