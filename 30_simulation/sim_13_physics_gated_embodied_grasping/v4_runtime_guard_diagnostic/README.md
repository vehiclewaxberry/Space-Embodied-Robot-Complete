# Sim13 V4 运行时防护合成预绑定诊断

## 裁决边界

本包只证明 NC15、NC16、NC18、NC20 所需的防护逻辑在受控合成夹具上可以实现，
范围固定为 `SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY`。它不加载、不生成也不绑定
Unified R2，不是当前系统运行时、生产动力学、接触抓取或发布基线。

V2 正式负对照状态保持原样：`15/20 PASS`，NC15/NC16/NC18/NC19/NC20 仍是
正式 Gate 的 HOLD。V4 的四项结果只能写成 `PASS_DIAGNOSTIC_LOGIC_ONLY`，不得直接
累加成 `19/20`；NC19 继续因权威窄相接触后端和发布几何缺失而 HOLD。

## 已实现的诊断

- **NC15**：capability 同时绑定 action、execution context 和 gate snapshot；采用有限
  有效窗、nonce 单次消费，过期、重放、签名篡改及三类绑定漂移都精确转为 ABORT。
  nonce 只在**单一规范 `sim13_v4.runtime_guard` 模块实例的生命周期内**由其所有
  Shield/ledger 视图共享，并由互斥锁执行原子消费；外部不能向 Shield 注入隔离 ledger，
  同一模块实例内跨 Shield 竞争 16 次只允许 1 次。`importlib.reload`、重复加载形成的另一
  模块实例、跨进程或解释器重启均不会继承该 nonce 域，因此 NC15 正式状态仍为 HOLD。
  HMAC 密钥是公开测试密钥，时钟是注入式确定性时钟，二者均明确为非生产设施。
- **NC16**：唯一高层执行入口是 diagnostic coordinator。任务策略与 Shield 检查通过后，
  coordinator 才在闭包私有登记表中登记一次性 opaque invocation；数值后端只兑换登记
  对象本体一次。直接构造、`object.__new__`、复制、对象身份克隆、旧对象重放以及导入
  模块私有名后直达公开后端均被拒绝；capability 本身不是 backend invocation。公开后端
  直调精确拒绝为 `BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR`。这只是合作式 Python
  API 诊断边界；同进程恶意 monkeypatch 或闭包反射不在本能力安全声明内。
- **NC18**：只读复用 V3 的公开合成 6R+2P 构造和零动量约化动力学。合法一次性
  capability 下，6 路转矩（N·m）与 2 路指端力（N）使关节、基座及末端状态发生
  真实数值变化；合成非碎片路径也必须使用同一个 coordinator，并显式绑定合成 target/
  policy fixture。仅改变 phase 的假后端被判为
  `DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY`。转动/移动坐标、速度、力矩/力分别
  记账；基座线速度（m/s）与角速度（rad/s）分开审核，不计算异量纲总范数。
- **NC20**：分别固定 sim10 Gate、summary、任务参数卡与 anchor source 四个文件的
  SHA-256；Gate/summary 证明 `INFEASIBLE_RATE` 与
  3.0633304945807067 deg/s，参数卡证明校准质量 150 kg，anchor source 则提供质量
  150 kg 与初始转速 3 deg/s。这里不声称每个字段都由四个来源共同证明。回执绑定
  action/snapshot/target；回执未知、动作漂移、
  快照漂移、目标漂移、锚点漂移、哈希漂移或已重签畸形数值均 ABORT，不能抛异常。
  对 150 kg@3 deg/s 的所有非 ABORT 请求，coordinator 都先执行 veto；回执缺失、有效
  `INFEASIBLE_RATE` veto 或任一漂移时，capability 不消费、backend 调用数保持 0，且
  q/qdot、基座、末端状态逐字段不变。历史 sim10 PASS 不继承为当前 R2、接触或生产 PASS。

## 明确没有发生的事项

- 未调用 Unified R2 私有构造器或生成器；
- 未产生 `.urdf`、`MECH_RL_SYSTEM_INTERFACE_V2.yaml`、
  `UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json` 或任何 Owner/run 授权文件；
- `owner_accepted`、`current_system_passed`、`current_system_binding_passed`、
  `system_binding_passed`、`runtime_fail_closed_gate_passed`、
  `runtime_production_gate_passed`、`production_dynamics_gate_passed`、
  `contact_grasp_gate_passed`、`release_credit`、`next_stage_authorized` 全部为 `false`；
- 未把 sim10 的刚体历史可行域结论包装成 Unified R2 或接触模型验证。

## 复现

在本目录依次执行：

```powershell
python -B -m pytest -q -p no:cacheprovider
python -B generate_runtime_guard_evidence.py
python -B independent_audit_runtime_guard.py
python -B validate_runtime_guard_v4.py
```

冻结测试账本为 `40/40 PASS`；pytest cache provider 被显式禁用，包内不得存在
`.pytest_cache`、`__pycache__`、`.pyc` 或 `.pyo`。

机器裁决只认
`results/SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_GATE_V1.json`。该 Gate 的
`diagnostic_gate_passed=true` 只描述本合成诊断；所有当前系统、生产、接触、发布和
下一阶段授权字段必须保持 `false`。
