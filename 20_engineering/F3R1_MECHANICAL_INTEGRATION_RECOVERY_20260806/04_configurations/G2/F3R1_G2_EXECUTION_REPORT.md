# F3R1 G2 执行报告 · CONFIGURATION_DIFFERENTIATION

**任务：** `F3R1_G2_CONFIGURATION_DIFFERENTIATION` · **日期：** 2026-08-06
**裁决：** `G2_CONFIGURATION_DIFFERENTIATION_PASS`（15/15 检查全过，失败项 0）
**止步：** 本轮停在 G2，未进入 G3。

---

## 1. Gate 状态

```text
G0 CURRENT_TRANSFORM_AND_HASH_FREEZE = G0_FROZEN                          PASS
G1 TOP_LEVEL_MATE_ARCHITECTURE       = G1_VERIFIED                        PASS
G2 CONFIGURATION_DIFFERENTIATION     = G2_CONFIGURATION_DIFFERENTIATION_PASS  PASS
G3 REAL_MECHANICAL_INTERFACE_CLOSURE = 建议下一轮唯一授权（未执行）
```

| 检查 | 结果 |
|---|---|
| eight_configs_present | PASS |
| no_junk_configs | PASS |
| all_configs_rebuild | PASS |
| one_real_wing_per_side | PASS |
| no_duplicate_live_wings | PASS |
| mate_errors_zero | PASS |
| arm_drift_zero | PASS |
| root_drift_zero | PASS |
| stress_three_rounds | PASS |
| angles_match_authority | PASS |
| paths_inside_f3r1 | PASS |
| g0_unchanged | PASS |
| g1_unchanged | PASS |
| protected_unchanged | PASS |
| cold_reopen_ok | PASS |

## 2. Phase −1 唯一路径解析

未假设当前目录正确。全库搜索后按 SHA-256 唯一解析（`F3R1_G2_RESOLVED_PATHS.json`，裁决 `G2_PATHS_RESOLVED`）：

| 目标 | 路径 | SHA-256 |
|---|---|---|
| G1 输入 | `03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM` | `E752FFC4CEFAC1D8318F7D21…`（与 G1 报告 POST 一致） |
| G0 冻结原版 | `03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM` | `5F1CB650F1E88ABFC308E132…` |
| G1 报告 | `12_human_review/F3R1_P5_REPORT_01_G0_G1_20260806.md` | `DD85C5DD97778425…` |
| 尝试台账 | `03_native_cad/F3R1_MATE_ATTEMPT_LOG.json` | `C90B2B4D982B3DA8…` |

依赖全部位于 F3R1 隔离树内（**外部依赖 0**）。无 backup/failed_builds/temp/旧版本同名件。

> 过程修正：目录段过滤最初用子串匹配，把 `MATE_ATTEMPT_LOG` 中的 "temp" 误判为 temp 目录；已改为**只匹配目录段**。

## 3. G2 新版本（不覆盖 G1）

```text
输出：03_native_cad/F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V3_CONFIGURED.SLDASM
创建时 SHA：E752FFC4CEFAC1D8…（与 V2 逐字节一致，identical_at_creation=true）
最终 SHA：19D85E9C703BEC107396…
```

`F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM` 未被覆盖；G0 原版仍 `5F1CB650…`。

## 4. 配置与角度权威（未凭外观猜测）

主权威：`state_policy.json` → `V22_LAYOUT_AND_DEPLOYMENT_01_STATE_POLICY`（`20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/110_Layout_and_Deployment_01/design/`）。

**重要发现：SSOT 定义七态，不是八态。** 工作令默认八项与 SSOT 差两处：多出 `SOLAR_DEPLOY_ARM_LOCKED`、并把 `STOWED` 改名。处置：保留 SSOT 七个名称为脊柱，从 B5_0 次级矩阵取 `SOLAR_DEPLOY_ARM_LOCKED` 补齐至八，`STOWED` 按工作令具名为 `STOWED_ENGINEERING_CANDIDATE` 并登记别名。未创建任何 `Configuration1` / `Default-Copy`。

另一发现：该 SSOT 自身记录 `native_solidworks.configurations = "NONE"` —— 印证 D-F3R1-04，G2 是首次原生实现。

## 5. 八配置实测（冷重开，全新进程）

| 配置 | SSOT 别名 | 期望 L/R | **实测 L/R** | live 左/右 | 臂配置 | mate 错误 | 干涉 | 角度状态 |
|---|---|---:|---:|---|---|---:|---:|---|
| STOWED_ENGINEERING_CANDIDATE | STOWED | 0/0 | **0.0/0.0** | 1/1 L_STOWED / R_STOWED | STOWED_O13V3 | 0 | 0 | AUTHORITATIVE |
| SOLAR_DEPLOY_ARM_LOCKED | — | 90/90 | **90.0/90.0** | 1/1 L_DEPLOYED / R_DEPLOYED | STOWED_O13V3 | 0 | 0 | PROVISIONAL_ENGINEERING_VALUE |
| DEPLOYED_NOMINAL | DEPLOYED_NOMINAL | 90/90 | **90.0/90.0** | 1/1 L_DEPLOYED / R_DEPLOYED | 默认 | 0 | 0 | AUTHORITATIVE |
| L_FAIL | L_FAIL | 0/90 | **0.0/90.0** | 1/1 L_STOWED / R_DEPLOYED | STOWED_O13V3 | 0 | 0 | AUTHORITATIVE |
| R_FAIL | R_FAIL | 90/0 | **90.0/0.0** | 1/1 L_DEPLOYED / R_STOWED | STOWED_O13V3 | 0 | 0 | AUTHORITATIVE |
| DEPLOY_FAILED_BOTH | DEPLOY_FAILED_BOTH | 0/0 | **0.0/0.0** | 1/1 L_STOWED / R_STOWED | STOWED_O13V3 | 0 | 0 | AUTHORITATIVE |
| PARTIAL | PARTIAL | （无权威） | 90.0/90.0 | 1/1 L_DEPLOYED / R_DEPLOYED | STOWED_O13V3 | 0 | 0 | **UNKNOWN_HOLD_NO_AUTHORITY** |
| SERVICE | SERVICE | （无权威） | 90.0/90.0 | 1/1 L_DEPLOYED / R_DEPLOYED | 默认 | 0 | 0 | **PROVISIONAL_HOLD** |

角度均**由几何反测**（live 为 `*_STOWED` 体即 0°；`*_DEPLOYED` 体按相对其 as-built 变换的残余旋转从 90° 反算），非按输入值回显。

**故障配置左右独立**：`L_FAIL` 与 `R_FAIL` 的 live 面板集互为镜像且不相同，非同一张图复用。

## 6. 每侧唯一真实翼

翼实例审计（`F3R1_G2_WING_INSTANCE_AUDIT.csv`）：4 个实例、source 文件互不相同、`identity_unique=true`。donor 只提供**分立的 STOWED / DEPLOYED 两套实体**（每块 6 平面、**0 圆柱面**，无铰链孔），故"每侧一套可转翼板 + 角度 Mate"用现有几何不可直接构造，而本阶段不授权新建真实零件。

经你裁定采用：四个 donor 实体作为**几何来源**，但**每个配置每侧最多 1 块 live**，其余按组件抑制（离开质量/碰撞/BOM）。八配置 × 3 轮压力测试全程 **live 1/1**，无重复叠放。

## 7. 压力测试与漂移

三轮 `CONFIG_1 → … → CONFIG_8 → CONFIG_1`：

```text
root 漂移最大值        = 0.0 mm
B601 臂漂移最大值      = 0.0 mm / 0.0 deg
压力测试中臂漂移最大值 = 0.0 mm
状态泄漏               = 0（抑制状态、组件数、live 计数全程稳定）
mate 错误              = 0（八配置合计）
```

G0/G1 架构保持：根组件唯一 fixed（`Space_Embodied_Service_Spacecraft_V2_2-1`）、B601 基准面 Mate 与 25° 时钟角保留、6 个 mate 全部无错、无依据 fixed = 0。三接口面继续独立：Central_Boss **208.0**、Adapter_Plate **198.0**、历史 T_SM **185.25**。

## 8. 未闭合项（原样保留，共 12 条见 findings register）

- **F-G2-02（HIGH）** `PARTIAL` 无权威角度（`state_policy.json` 为 null，且政策明确 5/15/30/60° 诊断样本不定义 PARTIAL）。首次尝试写入 30° 未存住——G1 的翼板 coincident mate 把翼板约束在甲板上，SolidWorks 重解拉回 90°。**未为了凑绿灯而抑制该 mate 强行造角度**，改为显式声明该配置**未几何分化**（`GeometricDifferentiation=NOT_DIFFERENTIATED_FROM_DEPLOYED_NOMINAL`）：已登记、未定义。
- **F-G2-04（HIGH）** D-F3R1-06 翼根缺口现已对称量化：四块翼板**全部距铰链轴 30.0 mm**。G2 角度实现仅 `KINEMATIC_CONFIGURATION_CANDIDATE`，未声称物理连接。
- **F-G2-10（HIGH）** q_stow 仍 `O13_V3_CANDIDATE_HOLD_PROVISIONAL`；八配置每个都写入 `RuntimeCompliance=FALSE`、`Safe00ExecutionEntry=FALSE`、`EngineeringEvaluationOnly=TRUE`。配置可重建**不等于**运行真值。
- **F-G2-11（HIGH）** R3-04 鞍座仍为同参空心占位框（顶面法向朝下、仅两条 4 mm 朝上窄边），G2 范围外。
- F-G2-03 `SERVICE` 待人工批准；F-G2-12 `SOLAR_DEPLOY_ARM_LOCKED` 仅末态、展开过渡路径未授权。

继承科学负结果不受影响：e15 `REPEAT_ANCF_CERTIFICATION`、SAFE-00 `next_stage_authorized=false`、C5 收拢翼包 238.3>226.3、6×6 解析对角近似。

## 9. 源资产未修改

`F3R1_G2_SOURCE_NON_MODIFICATION_REPORT.json`：G0 原版、G1 V2_MATED、V2_2 donor 全树、accepted B601 URDF、accepted 质量惯量账本**全部未改**。G2A/G2B/G2C/G2D 各 PRE+POST 保护检查均 `ALL_PROTECTED_UNCHANGED`。

## 10. 会话纪律（D-F3R1-07）

每次写入运行：清除全部 `SLDWORKS.exe` → 确认进程数 0 → 等 ~22 s 让 COM 服务释放 → 启动唯一新会话 → 记录版本 32.5.0 → 关闭并确认归零。全 G2 过程**无伪 AddMate 错误、无伪干涉**（八配置干涉均为 0）。

> 过程修正：组件句柄是**按配置**的——配置切换后旧句柄的 `Transform2` 读为 None，首轮表现为 inf 漂移并中止。已改为每次激活/重建后重取句柄。

## 11. 输出清单

`04_configurations/G2/` 下：`F3R1_G2_EXECUTION_REPORT.md`（本文）、`F3R1_G2_GATE_STATUS.json`、`F3R1_G2_RESOLVED_PATHS.json`、`F3R1_G2_CONFIG_ANGLE_AUTHORITY.json`、`F3R1_G2_CONFIGURATION_MATRIX.csv`、`F3R1_G2_COMPONENT_SUPPRESSION_MATRIX.csv`、`F3R1_G2_MATE_STATUS_REGISTER.csv`、`F3R1_G2_WING_INSTANCE_AUDIT.csv`、`F3R1_G2_TRANSFORM_DRIFT_REPORT.json`、`F3R1_G2_COLD_REOPEN_REPORT.json`、`F3R1_G2_COLD_REOPEN_PER_CONFIG.csv`、`F3R1_G2_SOURCE_NON_MODIFICATION_REPORT.json`、`F3R1_G2_FINDINGS_REGISTER.csv`、`F3R1_G3_INTERFACE_CLOSURE_RECOMMENDATION.md`、`F3R1_G2_SCREENSHOT_INDEX.md`、`step/F3R1_V3_*.step`（4 个关键态）。

## 12. 下一唯一建议授权

```text
G3_REAL_MECHANICAL_INTERFACE_CLOSURE
```

优先顺序（依 G2 实测数据固定）：**翼根凸耳与铰链接口 → G07/G08/Mid 真实鞍座 → ARM HDRM → 相机/线束 → 夹爪双指**。理由见 `F3R1_G3_INTERFACE_CLOSURE_RECOMMENDATION.md` 第 0 节：翼根未物理成立前设计鞍座，会使鞍座承托面依赖不可追溯的姿态。

**本轮未声明飞行资格；ECR 批准栏保持留空待人工签署。**
