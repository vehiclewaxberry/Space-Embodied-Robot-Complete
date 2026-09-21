# Red Team Science Review — R1

> 审查角色：空间机器人、航天动力学与多体数值审稿人  
> 审查对象：`10_research/framework_convergence/` 初稿  
> 初审裁决：`MAJOR_REVISION / DO_NOT_AUTHORIZE_WAVE_A_YET`  
> 当前授权状态：`PLANNED_NOT_AUTHORIZED`

## 1. 初审统计

| 等级 | 数量 | 含义 |
|---|---:|---|
| FATAL | 1 | 会使禁止声明在机器解析后变成允许声明 |
| HIGH | 3 | 授权、scientific PASS 可达性或守恒合同不成立 |
| MEDIUM | 6 | 边界表达、DAG 或参考系需收紧 |
| PASS | 6 | 关键科学纪律经攻击后仍成立 |

## 2. FATAL

### F1 — `claim_evidence_matrix.csv` C21–C30 列错位

初稿表头为 13 列，但 C21–C30 只有 12 列，缺少独立 `result` 字段。标准 CSV
解析会把真正的禁止声明左移到 `allowed_claim`，并把证据路径左移到
`forbidden_claim`。受影响红线包括实时孪生、Physics Tools、VLA、B601、
ASM 与外部工具真值声明。

要求：

1. C21–C30 补齐独立 `result`；
2. 每行严格 13 列；
3. 用标准 CSV 解析器复核，不靠目检；
4. 对全部 `evidence_path` 做存在性检查。

## 3. HIGH

### H1 — Wave A 授权字段冲突

初稿 `next_research_plan.md` 使用
`AUTHORIZATION=CONDITIONAL_START_WITH_INTERFACE_BLOCKERS`，与 DAG、任务卡中的
`PLANNED_NOT_AUTHORIZED` 冲突。机器式字段可能被下游直接读取，因此在 HAG-A
之前必须统一为：

```text
AUTHORIZATION = PLANNED_NOT_AUTHORIZED
START_CONDITION = HAG_A_APPROVED
```

ASM-00 只能“开始资格化”；若 RF-1/2/3 无法闭合，必须输出 BLOCKED，不能预设
它会解除阻塞。

### H2 — `SCREENING_ONLY` 被错误上推为 scientific PASS

目标侧 FFR 尚未建立，AG4 也未闭合。初稿两周计划却允许
`ASSEMBLY_PHYSICS_PASS`，使 screening 水印替代缺失的柔性资格。正确边界是：

- 目标侧 FFR/AG4 未闭合时，scientific PASS 不可达；
- 可输出 screening、REPEAT 或 BLOCKED；
- 只有 FFR 建立且 AG4 PASS 后才允许 scientific PASS。

### H3 — ASM-01 动量/能量 Gate 合同不完整

初稿未冻结角动量参考点、系统边界、接触功/执行器功的角色和耗散项符号，可能让
错误账本“自洽 PASS”。开工前必须固定：

- `chaser + target + flex` 封闭组合系统；
- 关于惯性原点和系统质心的角动量分开报告，统一惯性表达系；
- 质心口径同时审计线动量与质心迁移；
- 组合系统接触力为内力，总能量外部输入只有 `W_ext + W_actuator`；
- 接触弹性、模态阻尼、接触阻尼、摩擦与 lockup 损失分项记账；
- 单侧 `W_contact` 只用于子系统能量转移；
- 零附近残差同时使用绝对和相对容差。

## 4. MEDIUM

1. `state_truth_report.md` 应把工作区描述限定为“交付生成前的审计输入快照”，并
   区分当前冻结数值链与旧 campaign 局部 DT2。
2. CTRL-02 必须携带 `review_status=PENDING_REVIEW`、
   `NOT_EVALUATED_NO_ACTUATOR_DYNAMICS`，以及“7/16 仅在 R5 PROVISIONAL
   执行器及时窗模型下稳定”的限定。
3. DAG 必须拆开 ASM-01 无参数骨架与正式运行，避免 HAG-A 后绕过 AG0/HAG-B。
4. sim_12 的 `J↓、H↑` 必须写清 `|J|`、关于系统质心的惯性系 `|H|`，且
   `|ΔH_vec|` 与 `|H|` 标量变化不得混用。
5. Pinocchio/Basilisk 对拍必须冻结角动量参考点；“Oracle”改为
   “cross-validator”。
6. 最终标签虽可保留接口阻塞表述，但摘要必须同时显式列出目标侧 FFR/AG4、
   W1-R12/W1-R13 与 HAG-A。

## 5. 经攻击仍成立

1. e15 ANCF `REPEAT_ANCF_CERTIFICATION`、e15 core 无安全候选、CTRL-01 和
   Wave1 的 `REPEAT` 均未伪装成“未完成”或 PASS。
2. sim_10/11/12 被列为冻结资产，没有被重建。
3. PROVISIONAL 总体未写成硬件认证。
4. SPART、Pinocchio、Basilisk、MuJoCo 等未被写成柔性或接触真值。
5. DT2 离线回放与 DT3/DT4 实时/硬件闭环区分成立。
6. 七个核心 Gate 哈希和关键数量与机器证据一致。

## 6. 回修与复核状态

| Finding | 回修 | 复核 |
|---|---|---|
| F1 CSV 列错位 | C21–C30 补齐 `result` | 标准解析：31 行均 13 列；0 个缺失证据路径；允许/禁止列抽查正确 |
| H1 授权冲突 | 统一为 `PLANNED_NOT_AUTHORIZED` + `HAG_A_APPROVED` | 与 DAG、四张任务卡一致 |
| H2 screening 上推 | FFR/AG4 前 scientific PASS 明确不可达 | 两周合法终态改为 screening/REPEAT/BLOCKED |
| H3 守恒合同 | 在 NW-02 增加系统边界、参考点、功与耗散账本合同 | 已成为开工前硬条件 |
| M1–M6 | 状态摘要、CTRL-02、DAG、J/H、外部对拍与阻塞摘要均收紧 | 文档交叉检查通过 |

## 7. 回修后裁决

初审缺陷已经回修，但这不构成 Wave A 授权。当前可接受的框架级裁决是：

**`FRAMEWORK_CONVERGED_WITH_INTERFACE_BLOCKERS`**

Wave A 仍为 `PLANNED_NOT_AUTHORIZED`；必须先由人工完成 HAG-A。
