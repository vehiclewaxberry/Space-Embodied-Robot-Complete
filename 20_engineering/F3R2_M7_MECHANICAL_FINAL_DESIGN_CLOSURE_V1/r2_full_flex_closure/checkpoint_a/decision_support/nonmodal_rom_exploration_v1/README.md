# Solar R2 非模态 ROM 探索 V1

## 裁决

本目录的唯一证据等级是：

`EXPLORATORY_DECISION_SUPPORT_ONLY`

它把 Checkpoint-A 后已经完成的只读探索正规化为可复现证据，**不生成 Round4，不修改 Round3/E22/Checkpoint-A/终局包，不授予组件 PASS、e15 继承、Owner 接受、后续阶段授权或任何释放信用**。

## 已重算结果

在冻结的 183-DOF `K_nominal`、零阻尼、同一诊断激励、双翼、5/10/20/50/100 ms 接触窗和六项全场指标下：

| 候选族 | 最坏相对误差 | 1% 口径 | 工程含义 |
|---|---:|---|---|
| 经 75 个权重/快照组合选优的 5D 加权 POD | 4.001049% | FAIL | 只是已检验 5D 族中的最好结果，不是 Grassmann 全局下界 |
| 3 个弯曲特征模态 + 6 个扭转质量 POD（9D） | 1.375734% | FAIL | 删去第 7 个扭转 POD 向量的负控能被评分器检出 |
| 3 个弯曲特征模态 + 7 个扭转质量 POD（10D） | 0.966518% | 探索性低于阈值 | 裕度很薄，不能作为盲验证或释放依据 |
| 10D 在 5 ms 的 post-contact 扭转峰密采 | 0.948126% | 探索性低于阈值 | 只加密控制性的扭转峰；六指标仍以官方离散网格计分 |

10D 的离散五窗最大误差依次为：

- 5 ms：0.966518%（内部留出，控制窗）
- 10 ms：0.214530%（训练窗）
- 20 ms：0.035118%（训练窗，铰链指标控制）
- 50 ms：0.030496%（训练窗）
- 100 ms：0.001868%（内部留出）

## 方法与数据边界

- 训练快照：仅 LEFT 翼，`Tc={10,20,50} ms`；每条位移轨迹每 5 点抽样并独立按 Frobenius 范数归一化。
- 内部留出：`Tc={5,100} ms` 与 RIGHT 翼；但 RIGHT 翼扭转载荷在本模型中是 LEFT 的符号镜像，并非强独立数据。
- 5D 权重、POD 方法和 10D 维数是在查看探索结果后选定的。因此内部留出不等于盲验证。
- 10D 基底为 B1/B2/B3 三个弯曲特征模态，加上从扭转模态坐标响应快照提取的 7 个质量 POD 向量。
- 评分为双翼、五窗、六指标的最大相对误差；六指标为 tip/node/slope/hinge/torsion 峰值与模态能量峰值。
- 现有 first-12 特征模态子集穷举的固定基底最小通过维数仍为 11D；本目录不改写该结果。

## 不能据此声称的内容

- 不能声称任意 5D 子空间都必然失败；这里只覆盖明示的候选族。
- 不能声称 10D 已独立认证；必须先冻结方法、维数和哈希，再使用新激励方向、LOW/HIGH 刚度角与离网接触窗盲验。
- 不能继承 e15；`REPEAT_ANCF_CERTIFICATION` 保持不变。
- 不能升级组件、耦合动力学、接触、任务、结构资格鉴定或飞行结论。
- 不能覆盖 ODR-21/ODR-32 的现行 3–5 模态合同；合同变更仍需 Owner 明示裁决。

## 复现

从项目根目录依次运行：

```powershell
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/nonmodal_rom_exploration_v1/recompute_nonmodal_rom_exploration.py
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/nonmodal_rom_exploration_v1/independent_recompute.py
python 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/nonmodal_rom_exploration_v1/build_decision_support_gate.py
python -m unittest discover -s 20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/decision_support/nonmodal_rom_exploration_v1/tests -v
```

主要输出：

- `R2_NONMODAL_ROM_EXPLORATION_RESULTS_V1.json`：完整候选族、网格、指标、结果、负控与限制。
- `INDEPENDENT_RECOMPUTE_V1.json`：不导入主脚本的关键结果独立复算。
- `R2_NONMODAL_ROM_EXPLORATION_DECISION_SUPPORT_GATE_V1.json`：仅验证本决策支持包的证据完整性。
- `NONMODAL_ROM_EXPLORATION_SHA256_MANIFEST_V1.json`：不包含自身哈希、且无其他文件依赖其哈希的无环清单。

