# Time-domain pre-contact tracking external audit v1

本目录是候选包与单点 rebind 包之外的固定来源外审。`SOURCE_LOCK_V1.json` 逐文件冻结原时域候选、父 Gate 单点 rebind、候选直接来源以及 plant / metric / control-parent 传递来源；库存采用严格集合相等，缺文件、额外文件、`__pycache__` 或 `.pyc` 均拒绝。

外审程序不导入 `time_domain_precontact_tracking.py` 或 `metric_parent_rebind.py`。它只把候选 evidence 的 4 个物理运行实例、两种求解器状态和做功 history 当作待审数据，并用已固定的上游刚体树与控制运动学独立重算：

- C0/C1/C2 三个逻辑标签与 4 条物理 history 的区别；
- 5D/6D 同维无控—受控 tracking 比值；
- RK4/DOP853 的 rad、m、rad/s、m/s、姿态 rad 与加权 `1/s` 分单位误差；
- 惯性系线动量 `P` 与关于固定惯性原点 `O` 的角动量 `H_O`；
- `0.5 v^T M v` 动能—控制做功残差；
- 四元数、关节限位、理想 2P 锁定、KKT 平衡、约束反力零功；
- 6 GiB 执行资源准入记录 `[6.17, 6.26, 6.26] GiB`，且明确它没有科学或发布权限。

原候选机器 Gate 必须原样保持 `19/20 FAIL`，唯一失败为旧父 Gate 精确字节锁漂移。单点 rebind 的 `16/16 PASS` 只证明当前父 Gate 仍为 HOLD 且数值输入不变；它不重发原候选、父 Dynamics/Control Gate，也不授予 pre-contact、位姿/姿态、硬件、碰撞、接触、柔性、SAFE、Sim13、非 ABORT、下一阶段或发布信用。

最高外审裁决严格限定为：

```text
EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE
```

复现（禁用 bytecode 与 pytest cache）：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'
python -B audit_external.py
python -B audit_external.py --check
python -B -m pytest -q -p no:cacheprovider tests/test_time_domain_external_audit.py
```
