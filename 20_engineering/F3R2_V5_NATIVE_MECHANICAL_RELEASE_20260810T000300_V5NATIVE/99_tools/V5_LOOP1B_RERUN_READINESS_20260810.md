# V5 Loop1B 翼根真铰链装配 — 根因分析与重跑就绪报告（R2，探针实证版）

日期：2026-08-10（R2 更新，取代 R1 的"无求解放置"假设）｜ 证据：5 份内存探针日志 + 2 份冷开探针日志（`13_validation/V5_DIAG_LOOP1B_PROBE{1..7}_20260810.log`）｜ 会话：PID 87516 独占

## 0. 结论摘要

HINGE_GROUP_KINEMATIC_DRIFT 的真实根因不是位姿驱动方式，而是 **SW2024 同心配合创建时的对齐方向约定**：`AddMate3(CONCENTRIC, ALIGNED)` 作用于"凸耳内孔（内圆柱面）× 销外圆（外圆柱面）"时，SolidWorks 在**配合创建瞬间**把 PANEL/LUG 锁合组绕 Z 轴翻转 180° 以满足其轴线同向约定（探针 1，P4 相位实测：t=(-164,286.3,0)，R=Rz180）。该翻转位姿同时满足同心与重合约束（探针数学复核），终态可通过配合健康检查，因此此前所有"位姿被求解器覆盖"的表象都是配合创建期翻转的下游后果。修复由四个探针实证、双侧对称验证（探针 5，R 侧全过）。

## 1. 探针实证链（每条均可复查日志）

| 探针 | 内容 | 关键证据 |
|---|---|---|
| P1 | 逐相位变换转储 | 插入/对齐/锁定后全 identity；**同心配合创建后 PANEL/LUG 跳到翻转分支**（t=(-164,286.3,0)，rdiag=(-1,-1,1)）；重合 CLOSEST 在翻转分支上定 SOLVE 为 ALIGNED |
| P2 | 同心 ANTI_ALIGNED 变体 | 凸耳-销 ANTI → 创建零位移；保持架-销 ANTI 反而翻转保持架（两者方向约定相反）；双组件驱动时 PANEL 累积 1e-5~0.286 偏差 |
| P3 | 最终配合配方 + 三种驱动 | 配方（锁定 CLOSEST；凸耳-销同心 ANTI；凸耳-垫圈重合 CLOSEST→ANTI；保持架-销同心 ALIGNED；保持架-销重合 CLOSEST→ANTI）**五配合创建全程零位移**；锁定配合在 SetTransformAndSolve3 下**不传动**（仅驱凸耳时 PANEL 完全不动，刚组误差=全行程）且配合无报错 |
| P4 | 锁定配合抑制驱动法 | **抑制锁定→无求解绝对放置 PANEL/LUG→解除抑制→重建**：±0.5°/0/±90° 全部 lug_err=panel_err=rigid_err=0（≤1.7e-18），双组件 exact_true_1r=True |
| P5 | R 侧复验 | 与 L 侧完全一致：配合零位移、驱动全 EXACT、1R 通过 |
| P6 | 冷开 DOF 行为 | 保存的 L 装配（轻量组件）在 STOWED/DEPLOYED/L_FAIL/R_FAIL/默认 配置 DOF 正常；**DEPLOYING/BOTH_FAIL 配置 GetRemainingDOFs 返回 2、槽位全零**（只读/可编辑同现象） |
| P7 | 冷开 DOF 修复手段 | DEPLOYING/BOTH_FAIL：EditRebuild3 无效，**ForceRebuild3(True) 后 DOF 恢复精确 1R**（只读文档内存中重建，不落盘） |

## 2. 根因裁决（12+2 份 FAIL 回执）

| 类别 | 裁决 |
|---|---|
| F1 BrokenPipe（17:23Z） | 环境（stdout 管道被调用方关闭）；1B0 checkpoint 已正常写盘。重跑重定向到文件即可 |
| F2 AVAILABLE_RAM_HOLD ×5 | 环境门禁；已由签署用户覆盖（`V5_MEMORY_GATE_USER_OVERRIDE.json`）豁免 |
| F3 IMate2.Name（17:42Z） | 前代修订脚本缺陷，现行修订已修复（mate_ledger 重写 + 前代哈希白名单） |
| F4 X_PLANE_SIGNATURE_FAIL（17:56Z） | 中间修订缺陷，现行 `spacer_axial_plane_entity` 已修复 |
| F5 DEPLOYING_1R_FAIL（18:01Z） | 中间修订；配合系统在翻转分支 → swNoSolution；同族于 F6 |
| F6 HINGE_GROUP_KINEMATIC_DRIFT ×3+1 | **配合创建期同心对齐翻转**（探针实证），非会话绑定（17:30Z 回执在 PID 87516 上复现）；**P6/P7 另发现冷开 DOF 陈旧态**（TRUE_1R_COMPONENT_FAIL 21:49Z 回执） |

## 3. 已落补丁（仅限 `99_tools/F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py`，共享模块零改动）

1. **凸耳-销同心 `ALIGNED→ANTI_ALIGNED`**（build_wing_assembly；保持架-销保持 ALIGNED——探针 2/3 实证两者方向相反）。
2. **配合创建零位移门禁**：5 配合创建完成后立即校验 PANEL/LUG/RETAINER 变换=恒等（1e-9），任何创建期翻转立即 `MATE_CREATION_MOTION_FAIL` fail-closed。
3. **位姿驱动改为探针 4 实证序列**（`apply_hinge_group_pose`）：抑制锁定配合（全配置）→ 重建 → LUG/PANEL 无求解绝对放置 → 解除抑制（读回校验）→ 重建。新增 `lock_mate_feature` 助手与 `SW_SUPPRESS_FEATURE/SW_UNSUPPRESS_FEATURE/SW_ALL_CONFIGURATIONS` 常量。
4. **冷开逐配置 ForceRebuild3(True)**（探针 7 实证；只读文档内存重建，不改文件），消除冷开 DOF 陈旧态导致的 TRUE_1R_COMPONENT_FAIL。
5. 回执描述字段与实际机制一致（`command_driver`/`driver`/`follower`）。

所有既有 fail-closed 闸门原样保留：2e-7 变换读出、刚组误差、5 配合台账健康、exact true-1R、六配置冷开复验、受保护哈希前后审计。

## 4. 重跑命令与预期产物

```bash
cd "F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
python 99_tools/F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py execute --stage ALL > 13_validation/V5_LOOP1B_RERUN4_20260810_stdout.log 2>&1
```

成功：`13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json`（`V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS`）＋ `V5_LOOP1B1_WING_ROOT_CHECKPOINT.json` ＋ `V5_LOOP1B_ARTIFACT_{L,R}_ASSEMBLY.json` ＋ `14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt` ＋ 两件 `02_native_subassemblies/{LEFT,RIGHT}_WING_ROOT_TRUE_HINGE.SLDASM`。失败：`V5_LOOP1B_FAIL_<UTC>.json`（write-once，不覆盖）。

## 5. 运行记录

- RERUN3（21:04Z→21:49Z）：位姿机制实跑生效，L 侧通过运动证明+六配置+保存；冷开 DEPLOYING 配置 DOF 查询返回 2 → `TRUE_1R_COMPONENT_FAIL`（V5_LOOP1B_FAIL_20260810T214933Z）。遗留未证实 L SLDASM（无 checkpoint）已按 fail-closed 原则删除后重跑（非回执文件，UNPAIRED_PARTIAL_ARTIFACT_HOLD 解除）。
- RERUN4（22:06Z→23:00Z，补丁 1-4 全量）：**PASS，exit=0**。最终回执 `13_validation/V5_LOOP1B_WING_ROOT_RECEIPT.json`，verdict `V5_LOOP1B_DUAL_WING_ROOT_NATIVE_CLOSURE_PASS`；双侧装配各 6 配置冷开复验通过、各 5 配合（16,2 / 1,1 / 0,1 / 1,0 / 0,1）；`V5_LOOP1B1_WING_ROOT_CHECKPOINT.json`、`V5_LOOP1B_ARTIFACT_{L,R}_ASSEMBLY.json`、`14_release/V5_LOOP1B_WING_ROOT_MANIFEST_SHA256.txt`、`02_native_subassemblies/{LEFT,RIGHT}_WING_ROOT_TRUE_HINGE.SLDASM` 全部落盘；内存采样记录于回执（min 1.677 GiB，用户覆盖已签署）；会话结束 document-empty（卫生探针复核 SESSION_CLEAN）。

## 6. 残余风险

- 无未决阻塞。Loop1B 双侧真铰链装配闭合完成；`remaining_holds`（紧固件/弹簧预载/止挡接触/线束弯折/Loop2 干涉白名单/顶装集成）按回执原样保持 HOLD，由后续 Loop 承接。

## 7. 非声明

本报告不是最终原生基线、制造发布、飞行资质或发射合格结论；未修改/删除任何既有回执或受保护基线；探针均为内存操作，未保存任何探测文档；会话全程保持或恢复 document-empty。
