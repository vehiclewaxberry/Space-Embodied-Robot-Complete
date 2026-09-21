# e19：B601 任务分支隔离诊断执行

本模块把 e18 已冻结的 M01、M05、M06、M07 非发布输入分支变成可复现的离线数值诊断，但**不**把四条分支串成任务时间线，也不产生任务、接触、硬件、生产动力学或飞行放行。

## 本轮实际计算

- **M01**：复算 11.5 s / 0.01 s 六关节五次轨迹，并通过显式 REORG 路径适配器调用历史 sim_05 刚性自由漂浮算法，输出基座反作用与零动量残差。该模型质量栈是隔离诊断模型，不是已发布整星质量属性。
- **M05**：单独传播 Sim13 的 22 kg、0.5 deg/s 常角速运动学分支；另行校核静态展示坐标变换。两分支不可合并。
- **M06**：对 4 个接近速度 × 5 个求解器接触窗执行 20 例半正弦等冲量数值积分；波形幅值不是实测或允许接触力。
- **M07**：复算 4.5 s arm-only 恢复轨迹的基座反作用；独立重跑 Sim15 四个 22 kg 刚塑捕获代数案例。目标未附着到 arm-only 轨迹。

## 复现

在项目根目录运行：

```powershell
python -B 30_simulation/e19_b601_mission_branch_diagnostic_evaluation/src/build_e19_diagnostics.py
python -B 30_simulation/e19_b601_mission_branch_diagnostic_evaluation/tests/validate_e19_diagnostics.py
```

机器裁决入口：`results/E19_DIAGNOSTIC_EVALUATION_GATE_V1.json`。测试通过只说明本模块的隔离数值闭合与证据完整性，不授予科学、机械设计、任务、接触、硬件、生产或飞行权威。

## 强制边界

- accepted URDF 只读，SHA-256 必须保持 `1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164`。
- 历史 sim_05 默认路径仍指向 REORG 前命名空间；e19 仅在内存中显式注入现行 URDF 与质量表路径，不修改 sim_05 或其历史 Gate。
- 所有缺失的释放、历元、公共帧、接触、锁定、锁定变换、发布质量属性和恢复容差保持 `null/HOLD`；不得以零替代。
- M05 两分支、M06 标量波形、M07 刚塑捕获与 arm-only 轨迹之间不传递状态。

