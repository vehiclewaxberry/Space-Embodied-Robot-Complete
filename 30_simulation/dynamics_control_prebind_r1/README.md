# Dynamics & Control Prebind R1

本目录是 `DYNAMICS_CONTROL_PREBIND_R1` 的隔离候选胶囊。它只执行
PB-G0 权威预绑定审计与 PB-00 零控制自由漂浮诊断，不修改任何机械、
Sim13、E23、SAFE-00 或既有控制结果。

当前允许的最大主张是：

```text
DIAGNOSTIC_PREBIND_PARAMETER_MAPPING_AND_PB00_CHARACTERIZATION
```

当前禁止：正式控制性能信用、接触/捕获信用、Route-C 质量传播、
NMPC/RL/VLA 训练以及硬件发布。

复现：

```powershell
python -B 30_simulation/dynamics_control_prebind_r1/src/run_phase0.py --repo-root . --seed 260826
python -B -m pytest -p no:cacheprovider 30_simulation/dynamics_control_prebind_r1/tests
```

机器裁决入口：

- `10_verification/PB_G0_GATE.json`
- `10_verification/PB_G1_GATE.json`
- `10_verification/MOMENTUM_LEDGER.json`

测试通过不等于 Gate 通过；PB-G0/PB-G1 均按 fail-closed 规则裁决。

