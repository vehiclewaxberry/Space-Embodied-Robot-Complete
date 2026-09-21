# CTRL R2 integrated candidate — predevelopment only

本胶囊实现 `CTRL_R2_PREDEVELOPMENT`，用于把现有 Unified R2 数字身体、
CTRL-01/CTRL-02、E23 七模态柔性重认证和 SAFE-00 接口放入同一条可复算证据链。

当前最大主张：

```text
CONTROL_PREDEVELOPMENT_CANDIDATE_BUILT_WITH_DECLARED_LIMITS
MODEL_AND_NOMINAL_TRACKING_ONLY
NO_COLLISION_AWARE_EXECUTION_CREDIT
```

这是授权允许的候选级主张上限，不是“技术预开发完成”声明；机器 Gate 当前仍为
`technical_predevelopment_complete=false`。

本胶囊不会修改 accepted B601 URDF、Unified R2 URDF、机械 CAD、原控制 Gate、
E23 或 SAFE-00。ODR-60 Option A 仍无精确 Owner 选择 token，因此这里不执行
pair/edge/path search，不产生机械发布或 non-ABORT 抓取信用。

## 覆盖范围

- C0：R2 模型、质量、框架、运行时后端、URDF receipt、Round4 ROM/HF/包络与
  Gate 哈希绑定；
- C1：保留并分类 CTRL-01 `REPEAT` 负结果；REORG04 后配置哈希漂移，
  不宣称旧矩阵逐位复现；
- C2：对冻结 CTRL-01 模型运行单状态 DLS/resolved-rate 确定性探针；CTRL-01、
  Sim11、common 的实际本地导入源码和模型卡读取闭包均进入 source pins；
- C3：在 Unified R2 8DOF 后端上以 `qP=[0.03575,0.03575] m`、
  `qdotP=[0,0]` 执行静态 `Hbb/Hbm`、锁定 6R mechanical connection、约化质量
  与线/角动量分项探针；8DOF 构型逐关节核验哈希固定 URDF 限位并发布上下限余量，
  越界 fail-closed；不调用 `advance()`，并保留 CTRL-01 C3 无效负结果；
- C4：绑定 CTRL-02 的 provisional 姿态/动量结果；
- C5：只绑定 E23 的 provisional 诊断锚点（22 kg@0.5°/s、150 kg@3°/s）；
  不把它们等同于或继承 sim_10 的 22 kg@3°/s 刚体可行域锚点；
- C6：执行 LEFT→RIGHT 双翼 14 模态 LOW/NOMINAL/HIGH 静态基座加速度叠加筛查，
  使用两翼各自的 Gamma 与五类重构算子，越界一律 fail-closed；不继承 E23 PASS；
- C7：冻结 SAFE-00 消费接口，但不调用执行授权。
- C8：冻结 6R+2P 逐关节执行器最小测量 intake。所有缺失的力矩/力、速率、加速度、
  饱和、死区、延迟、电流和热参数保持 `null + MEASUREMENT_PENDING`，禁止零填充；
  齿轮/效率、摩擦/回差/柔顺、控制带宽/采样、电源与故障/热边界等语义需求仍显式开放。

静态适配已闭合，但 torque-level 传播所需的 2P 约束反力求解器、双翼 14 模态
全耦合任务时域模型和硬件执行器测量仍是显式 HOLD。

## 复现

```powershell
python -B 30_simulation/control_r2_integrated_candidate/src/build_predevelopment_gate.py --repo-root .
python -B -m pytest -p no:cacheprovider 30_simulation/control_r2_integrated_candidate/tests
```

机器入口：

- `results/CTRL_R2_PREDEVELOPMENT_GATE_V1.json`
- `results/CURRENT_FRONTIER_ODR60_CTRL_V1.json`
- `results/CTRL01_FAILURE_CLASSIFICATION_V1.json`
- `results/CTRL_R2_NOMINAL_DLS_PROBE_V1.json`
- `results/CTRL_R2_UNIFIED_8DOF_STATIC_PROBE_V1.json`
- `results/CTRL_R2_DUAL_WING_14MODE_STATIC_FLEX_SCREEN_V1.json`
- `results/CTRL_R2_ACTUATOR_DYNAMICS_INTAKE_AUDIT_V1.json`
