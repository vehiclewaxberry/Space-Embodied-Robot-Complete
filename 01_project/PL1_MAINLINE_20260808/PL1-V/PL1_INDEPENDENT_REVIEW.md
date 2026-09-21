# PL1_INDEPENDENT_REVIEW.md — PL1-V 独立复核

> Review date: 2026-08-08  
> Scope: `SEI-PL1-PROJECT-MAINLINE-RECONSTRUCTION / TWO-ROOT-CONSOLIDATION`  
> Method: 对当前磁盘、Git、冻结 hash/Gate、copy manifests、Root B 安装件与 CM health-check 做只读复算；不把报告自述当作唯一证据。  
> Important: 本复核接受“主线重建的完整性”，不替代 F3R2 人工工程审查，不授予 CAD 写入、HIL、dataset 或具身执行 authority。

## 1. 机器复核结果

执行：

```powershell
python "F:\China Graduate Future Flight Vehicle Innovation Competition\01_project\PL1_MAINLINE_20260808\PL1-V\validate_pl1.py"
```

结果：`PL1_VALIDATION = PASS_WITH_EXPLICIT_HOLDS`，26 PASS / 2 governance/DR HOLD / 0 FAIL。

主要直接证据：

- F:\ 39 个物理一级条目均在 discovery 中有精确分类；`I_UNKNOWN=0`。
- Two-root matrix 82 行，`UNKNOWN=0`。
- F3R1 363、F3R2 基线 482、EXTRAS 364 的 source/dest manifests 逐字节相同；ROOT A 的 F3R1 实体计数为 363，F3R2 当前物理计数为 537（482 个抢救基线文件 + 带 M3R 门禁的加性证据）。加性文件不改变原 482 行 manifest 的迁移证明。
- supplemental contract chain 15/15、CM3A 6/6 均逐文件 SHA-256 相同，源区保留。
- F3R2 top SHA-256 为 `19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0`。
- accepted B601 URDF raw SHA-256 为 `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`。
- ROOT B 四个安装入口/登记表与 PL1 source hash 同步；27 个 open-source rows 全部 `runtime_dependency=false`。
- 活动 B601 hardware STEP 指针为 ROOT A repo-relative path 且可解析；项目 executable/config 对 ROOT B 绝对路径命中 0。
- stable Archive 的四个 CM 控制文件与 `13_CM_CLOSURE` compatibility mirror hash 相同。
- health-check 除 `PRIMARY_CLEAN` 外全部 PASS；当前总结果为 `FAIL 1`，没有被伪装成健康 PASS。

## 2. PL1-G0–G12 Gate

| Gate | 要求 | 独立裁定 | 证据/限定 |
|---|---|---|---|
| **PL1-G0** | PROJECT DISCOVERY | **PASS** | 39 个 F:\ 一级条目全覆盖；discovery 52 data rows；UNKNOWN=0。 |
| **PL1-G1** | PROJECT BOUNDARY | **CLOSED** | ROOT A / ROOT B / Archive-bound-to-A / temp / tool / non-SEI 的边界可机读；general CAE 已排除。 |
| **PL1-G2** | MECHANICAL MAINLINE | **CLOSED_WITH_ENGINEERING_HOLDS** | 工程过程、版本谱系、状态、model map、P0/P1/P2 顺序均有唯一入口；“closed”只指重建闭合。 |
| **PL1-G3** | MECHANICAL BASELINE | **UNIQUE_MACHINE_SELECTED_CANDIDATE** | 唯一候选为 F3R2 operational package；11/14 + 4 HOLDs，`PENDING_HUMAN_REVIEW`，不是人工 accepted/manufacturing baseline。 |
| **PL1-G4** | DYNAMICS MAINLINE | **CLOSED_WITH_PROVISIONAL_PARAMS** | 唯一当前 top 为 sim_11 v1.1；`SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS`，刚性锚 sim_05。 |
| **PL1-G5** | B601 DIGITAL THREAD | **CLOSED_WITH_REFERENCE_REPAIR_HOLD** | L0 accepted URDF 唯一；L1/L2/L3 分层明确；10 条 native references 与 cold-reopen 仍未闭合。 |
| **PL1-G6** | REFERENCE / OPEN SOURCE | **CLOSED_WITH_LICENSE/LOCATION_HOLDS** | ROOT B 四入口已安装；27 项 source register；reference 永不拥有 project authority。 |
| **PL1-G7** | CAD DONOR | **CLOSED_WITH_RETIREMENT_HOLD** | donor/current 区分完成；FreeCAD 是 subset/reference；Robotic arm runtime=0，但 witness/backup 未齐，不能退役。 |
| **PL1-G8** | TWO ROOT MAPPING | **100%** | 82 行 matrix，UNKNOWN=0；Archive 是 A 的历史层，不是运行入口。 |
| **PL1-G9** | EXTERNAL RUNTIME DEPENDENCY | **0** | 27/27 `runtime_dependency=false`；活动 B601 vendor 指针 repo-relative；ROOT B absolute runtime/config hit=0。 |
| **PL1-G10** | PROJECT START HERE | **UPDATED** | HEAD、F3R1/F3R2、accepted URDF、Root B、Archive、health 与 PL1 map 均已重指。 |
| **PL1-G11** | MECHANICAL START HERE | **CREATED_AND_RECONCILED** | 候选、L0 truth、donor、禁止项、12 个机械 HOLD 与 scope-specific authorization 边界已列。 |
| **PL1-G12** | INDEPENDENT REVIEW | **PASS_WITH_EXPLICIT_HOLDS** | `validate_pl1.py`: 26 PASS / 2 HOLD / 0 FAIL；本文件给出人工可读裁定。 |

## 3. 未关闭的显式 HOLD

| HOLD | 当前事实 | 关闭条件 |
|---|---|---|
| CM / Git cleanliness | PL1、salvage 与 supplemental files 尚未整体纳入 Git/CM；health=`FAIL 1`。 | 人工选择 stage/commit/revert 范围；复跑 health 必须 clean。 |
| Disaster recovery | Git remote=0；F3R1/F3R2 与 gitignored reBot vendor 无独立冷备策略。 | 建立经 hash/cold-open 验证的备份，不得用未验证复制冒充 DR。 |
| F3R2 human ruling | Gate 11/14、C11/C12/C14 fail、四个 HOLD token，review pending。 | 人工签发接受/退回/限定适用域；不得由 `next_stage_authorized=true` 外推 V4 CAD 授权。 |
| Native CAD integrity | F3R2 仍有 10 条包外引用；Pack-and-Go 最终 verdict 为 R2A_FAIL。 | reference repair/waiver + 独立 cold reopen；保持冻结 hash 可追溯。 |
| Residual mechanics | wing-root、真实 saddles/stow、ARM HDRM、camera/harness、独立 fingers、service pose、pair attribution 未闭合。 | 严格按 P0→P1→P2，逐轮 scope-specific change authorization。 |
| Temporary lineage | WT 仍含 3,432-file/4.0 GB historical CAD 与 880-file stage3 closure。 | 每个 dependency island 单独 uniqueness/hash/semantic Gate；源区不得先删。 |
| Robotic arm donor root | runtime/build dependency=0，但 HPRA history、2 URDF、dirty diff 与小文本 witness 未归档。 | 完成 witness bundle、manifest、cold-open 与人工 retirement authorization。 |
| Reference governance | Basilisk commit skew；Chrono 实体仅 ROOT A；8 项许可未知；部分 reference clones 错置 A。 | 逐 repo 选 record-of-reference、补 license、更新 literature manifest 后再迁移。 |
| Scientific/physical parameters | system mass budget、panel modes、gripper `T_c`、actuator parameters 仍 provisional/unsourced。 | 实测/可追溯参数卡 + 受控重跑；旧冻结负结果保留。 |
| New domains | embodied AI 仅合同层；HIL、Dataset 为 NOT_STARTED。 | 分别建立 charter、authority、schema、Gate；不得把 reference repo 计为实现。 |

## 4. 最终裁决

```text
PL1_PROJECT_MAINLINE_RECONSTRUCTED
PL1_COMPLETE_WITH_EXPLICIT_ENGINEERING_HOLDS
```

这意味着：任何新 Agent 已能从两个项目入口在五分钟内唯一定位机械候选、B601 真值、动力学 top、控制/SAFE、donor/reference 和下一任务；它不意味着机械、仿真参数、HIL、数据集或灾备已经全部工程关闭。
