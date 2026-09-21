# Unified R2 → Sim13 pre-execution binding security source freeze V1

本包把整机数字样机进入 Sim13 之前的接口与安全边界冻结为可机检源码，裁决上限严格为 `PASS_SOURCE_FREEZE_ONLY`。它没有创建 `MECH_RL_SYSTEM_INTERFACE_V2.yaml` 实例，没有生成或写出整机 URDF，没有导入或调用休眠的整机生成器，也没有创建、修改 CAD/STEP/FCStd、运行接触、动力学或抓取训练。

## 本轮闭合内容

- 严格 UTF-8 JSON 解析：拒绝重复键、额外字段、NaN/Infinity、BOM；以规范 JSON 计算 action/context digest。解析前先以迭代扫描冻结资源边界：262144 bytes、64 层容器、8192 complexity units（对应最多 8193 个域节点）、单字符串 16384 字符、字符串累计 131072 字符、数值字面量 256 字符；相邻上限有正向测试。
- 公共边界 totality：1200 层合法 JSON、5000 位整数字面量、超限 bytes/字符串/节点、非法 UTF-8，以及 JSON escaped 或内存 action/context 中的 lone surrogate 都在递归解析、大整数转换或规范 UTF-8 编码前归一化为 `StrictJSONError`/`ReceiptError`。合法 strict-JSON 中的超大整数（例如 400 位时间戳）即使在转为 binary64 时溢出，也只产生 `ReceiptError`；非 bytes receipt 同样显式拒绝。direct-admit/join 对这些输入稳定返回 `allowed=false + executed_strategy=ABORT`，不泄漏 `RecursionError`、`UnicodeEncodeError`、数字限制 `ValueError`、`OverflowError` 或 `TypeError`，nonce 消费为 0。受控捕获范围不包含 `BaseException`、`MemoryError` 或 `KeyboardInterrupt`。
- `MECH_RL_SYSTEM_INTERFACE_V2` 候选解析器：仅用内存合成 fixture 验证 19-link/18-joint、质量模式、B601 子树、12 个 Gate、15 个 artifact 记录以及 fail-closed authority 结构。解析结果递归不可变；路径显式拒绝 NUL、反斜杠、盘符、绝对路径、空段、`.`、`..`，artifact path 和 SHA-256 均须唯一。
- 高层 action 精确限定为 `grasp_candidate_id`、`capture_timing_id`、`strategy_id` 三字段；`target_class` 只属于 context。低层 torque 等额外字段一律拒绝，`requested_strategy` 必须等于 `action.strategy_id`；唯一规范 ABORT 为 `__ABORT__/__ABORT__/ABORT`。issue、verify、direct-admit 与 join 四类入口执行同一规则。
- receipt-bound join：system binding、12-Gate 快照、dynamics、contact、shield capability、150 kg 可行性、post-grasp 均须是 action/context/time/nonce/HMAC 绑定的 receipt。先完整校验所有已提供的已知 receipt，再判断 extra/missing/语义状态；bundle 内 nonce 全局唯一。任何缺失、过期、重放、摘要不符、签名无效、UNKNOWN/HOLD/FAIL 均执行 ABORT。
- 本版本所有非 ABORT 请求都被 `SOURCE_FREEZE_SCOPE_LOCK` 拒绝，因此公开 verify、语义拒绝和 scope-lock 拒绝均消费 **0** 个 nonce；`consume_many` 只冻结为未来“动作真正获准后”的原子提交原语。`ReplayStore` 仅是进程内合成状态，重启即丢失，不提供持久化或生产信用。
- HMAC 密钥仅为合成测试密钥，不构成生产密钥管理或生产安全证据；即使合成 attestation 校验成功，公开 direct-backend API 仍强制 `ABORT + SOURCE_FREEZE_SCOPE_LOCK`，只返回 `attestation_verified` 诊断。NC16 仅获得 source-only credit。
- 150 kg@3°/s 锚点严格保持 `post_capture_rate=3.0633°/s → INFEASIBLE_RATE`，伪造 PASS 会被拒绝。
- 整机 XML-byte 合同验证器：仅对内存合成 fixture 工作，冻结精确 robot name、19/18 拓扑、16 physical/3 frame-only、16 个 link 的质量/COM/完整惯量、18 个 joint 的 parent-child/origin/axis sign/limits、10F+6R+2P、8 DoF、31.022864807342987 kg、物理载荷路径，以及源静态账本逐 link 的 visual/collision broadphase box `origin/rpy/size` 或精确 no-geometry 类；mesh 数必须为 0。浮点采用解析后精确相等（零容差，`1e-30` 与 `1e9` 漂移均拒绝），总质量使用 `math.fsum`；所有元素、属性、子元素基数均 fail-closed。该几何只称 source-static broadphase，不构成 physical/narrowphase/contact 信用。
- 固定目标路径原子事务仅冻结声明和合成状态机：authority → run-id consume → lock → pins → in-memory build/validate → same-dir exclusive temp → fsync → atomic replace → output rehash → receipt → unlock。没有事务执行器。
- NC15、NC16、NC20 各执行两次单故障合成负控，父基线哈希前后不变。父正式账本仍是 15/20，本包不升级正式 credit；附加 source-only frontier 为 18/20，NC18/NC19 继续 HOLD。
- 证据 DAG 固定为 `contracts/sources → manifest+negative-controls+pytest → validation → independent audit → Gate → terminal`。Gate 对全部上游节点记录 path/bytes/SHA-256，terminal 再绑定 Gate 的规范字节摘要；默认 validator 会逐节点复算并拒绝游离 terminal。
- 完整包清单采用 exact allowlist：允许文件集合只能等于 source manifest 条目与 7 个固定 DAG 输出的精确并集，目录集合由这些路径唯一推导；`evidence/`、`results/`、`manifest/` 中即使注入普通 `.json` 也会失败。URDF/CAD/mesh 扩展与 cache 黑名单仅作为纵深防御。

## 复验

在本目录执行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider -q
python run_preexecution_security_negative_controls.py
python freeze_preexecution_security_sources.py
python validate_preexecution_security_source_freeze.py
python independent_audit_preexecution_security.py
```

所有脚本只向 stdout 输出；不会写生产路径。`validate_preexecution_security_source_freeze.py --evidence-node` 仅复算 DAG 中的 validation 节点，默认模式复算完整已提交 DAG。独立 stdlib 审计从每条 NC 记录、父哈希和上游 receipt 重新推导结论，不直接信任汇总布尔值。

## 保留边界

以下字段在 Gate、validation 和 audit 中必须全部为 `false`：`system_urdf_available`、`current_system_bound`、`interface_instantiated`、`physical_contact_ready`、`dynamics_backend_ready`、`contact_execution_authorized`、`grasp_training_authorized`、`next_stage_authorized`、`release`。

后续只有在独立 Owner 授权、真实接口/URDF 实例、生产密钥与可信时钟、动力学状态演化（NC18）以及权威窄相接触几何（NC19）分别闭合后，才能另起版本评估正式 Gate。此包不能被解释为整机绑定、接触就绪、动力学就绪、训练授权或发布。
