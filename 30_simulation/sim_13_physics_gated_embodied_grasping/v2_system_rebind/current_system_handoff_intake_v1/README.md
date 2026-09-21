# CURRENT_SYSTEM_HANDOFF_INTAKE_V1

本包是 M7 机械证据进入 Sim13 V2 之前的**只读、事务式、fail-closed intake 边界**。它不生成或运行 URDF，不创建或修改 CAD/STEP/FCStd/mesh，不实例化 MECH_RL 接口，不启动动力学、接触、抓取或强化学习。

机器上限仅为 `PASS_SOURCE_FREEZE_ONLY`；当前实际 intake 始终是 `HOLD_INCOMPLETE`。`INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION` 只是所有合格输入未来齐套后的理论上限，不是本包已经取得的状态。

## 冻结的工程事实

- 15 个当前权威源采用源码常量锁定的 `artifact_id → path/bytes/SHA-256` 映射；每个源只打开/读取一次，同一 bytes 同时用于长度、SHA-256 和格式/模式检查，跨 ID 置换同样失败。
- intake 除 `frozen_binding_digest` 自身以外的全部字段进入 canonical binding digest；当前源码常量为 `D6CC48E6EEF2112AC9CA4E1C2F0D97D59D9FF2B64880DC44DF95109CD6A01F33`。候选方修改内容并自行重算 digest 仍不能替换该源码常量。
- topology/mass/limits/collision/contact/material/flex/harness/targets 九域的当前分类被固定为 `OWNER_REQUIRED`、`CANDIDATE_ONLY`、`TEST_REQUIRED` 或 `MISSING`；源文件存在不等于该域可用于当前系统。
- C01 质量 31.022864807342987 kg 仍是设计模型，非 as-built；物理夹爪速度、接触刚度和目标接触面积保持 null，禁止补零。
- URDF 中的 `15.0 m/s` 仅是模型字面量，不是硬件额定速度。
- 全柔性 Checkpoint A 为 6/12 HOLD；E22 为 16/18，G11/G17 失败；e15 最大交叉求解差 5.637349419858036% > 5%，必须 `REPEAT_ANCF_CERTIFICATION`。
- 机械→具身 handoff 为 11/12，G12 harness 失败；10 个强制状态 0 SAFE，8 段轨迹 0 released。
- Route-C P01–P13 为 0/13 AVAILABLE、13/13 HOLD；Route-B seed 不得继承，Route-C CAD 未授权。
- 当前 Sim13 生产机械绑定已被 M7 新证据撤销；required-absent 合同精确锁定指定 system URDF 与 `MECH_RL_SYSTEM_INTERFACE_V2.yaml` 两条路径，两者均不存在。

## 输入与不确定度合同

每个物理量都带 `value`、`unit`、`frame`、`reference_point`、`uncertainty`、`authority`、`status`、`source_artifact` 和 `source_field`。`uncertainty` 必含标准不确定度、分布、自由度和相关性；源未给出的内容保持 null，不臆造相关性或自由度。只有完整满足不确定度语义的量才可能成为 `PASS`，而本轮无物理域获得该资格。

所有 intake、receipt、Gate、evidence 和 manifest 都是 strict JSON：拒绝重复键、NaN/Infinity 和额外字段。外部 YAML 仅按**不透明 bytes + 长度 + SHA-256 + 单一顶层 schema 标记**固定；这是 opaque pin，不是严格 YAML 结构解析，本包不会用 YAML 内部结构推断新权威。

## Route-C 与晋级顺序

Route-C 只允许 `INCLUDED` 或 `EXCLUDED_RESEARCH_CANDIDATE` 两值；当前 selection 为 null。两值都不能自动接受，均需独立、当前、外部 Owner authority。receipt 校验器精确检查 artifact ID、action/context digest、时间窗、nonce 和调用者提供的**进程内集合**；它没有持久化或跨进程 replay ledger，也不写入磁盘 authority。本包没有签名验证器或信任根，所以即使该内存预检成功也**不构成 Owner 授权或任何跨进程信用**。

冻结顺序为：Owner-authorized URDF execution → current-system binding → runtime fail-closed integration → dynamics backend → contact/grasp validation → full-flex 时重新通过 e15。六级全部是 `HOLD_NOT_EXECUTED`，本包不得自授予其中任何一级。

## 验证

```powershell
python -B -m pytest -p no:cacheprovider
python -B validate_current_system_handoff_intake_source_freeze.py
python -B independent_audit_current_system_handoff_intake.py --check
python -B verify_current_system_handoff_intake_read_only_replay.py
```

冻结证据在 `evidence/`，Gate/terminal 在 `results/`。source manifest 固定源码/合同/测试/文档；完整包 allowlist 另行精确冻结 manifest 24 项、4 份 evidence、Gate 与 terminal 的 30 个文件路径，任何目录中的第 31 个文件均 fail-closed，不受扩展名影响。Gate 固定全部 evidence 与合同 receipt；terminal 再固定 Gate，形成 manifest→evidence→Gate→terminal 的完整 DAG。validator、不导入生产 evaluator 的独立 audit 与 read-only replay 都重算文件集合和该 DAG。`freeze_current_system_handoff_intake.py` 默认只做内存预览；其显式 `--write` 使用同目录 staging 和 terminal-last commit 语义，部分发布没有 terminal 就不构成有效冻结。

本轮 31/31 负控只获得 source-freeze 测试信用；NC09 直接污染 Route-B→Route-C 源 lineage，NC22 对已固定 payload 做真实单字节/hash mutation，NC27–NC29 覆盖 artifact/action/context receipt 绑定，NC30–NC31 使用同一生产 allowlist 判定器注入 `evidence/results` 额外 JSON 与 SDF/XACRO/MJCF/MSH/VTK/NPY/H5 文件并确认拒绝。扩展黑名单只是纵深防御；完整文件 allowlist 才是权威边界。未产生几何或 URDF，因此 CAD snapshot、CAD Viewer 和 URDF consumer smoke test 均不适用。
