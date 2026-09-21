# round2_hf_model — R2 高保真三叶/翼全柔性模型（Full-Flex F1）

Wave：KIMI M7 机械终局接管 swarm Wave-4a (ODR-45..49 owner decisions + R2 full-flex closure)；角色：AGENT-B1。生成时间 2026-08-23T20:45:41.771960+08:00（宿主机本地钟）。

## 文件

| 文件 | 角色 |
|---|---|
| `build_r2_hf_model.py` | 构建器：装配 M_hf/K_hf、跑全部特征工况、自检、落盘全部产物（纯 numpy/scipy） |
| `R2_FULLFLEX_HF_MODEL_V1.yaml` | 模型卡（机器 SSOT；含 GJ 推导全文、阻尼带、MC-A 记账、HOLD 逐字） |
| `R2_FULLFLEX_HF_MODEL_V1.md` | 模型卡人读版 |
| `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.json` | 特征值证据（装配矩阵、10 工况、收敛、质量闭合、SPD、零空间、HF-vs-ROM 对比） |
| `R2_FULLFLEX_HF_EIGEN_EVIDENCE_V1.md` | 证据人读版 |
| `R2_FULLFLEX_HF_VALIDATION_GATE_V1.json` | fail-closed 验证门（机器裁决） |
| `R2_FULLFLEX_HF_VALIDATION_GATE_V1.md` | 验证门人读版 |

## 复现

```
python -B build_r2_hf_model.py
```

（工作目录任意；脚本只写本目录，上游文件只读并逐针复算 sha256。）

## 纪律要点

- HF-vs-ROM 对比 REPORT ONLY；禁止调参凑 ROM 见证。
- 独立 latch 刚度保持 null（HOLD_LATCH_GEOMETRY_NOT_MODELLED）；板间 kθ 带为含 latch 柔顺。
- 阻尼双车道：ζ=0 守恒审计 vs ζ≠0 耗散预测（report-only）。
- 遗留 R1 车道禁值黑名单由验证门机器扫描本目录全部产物。
- 本包不是 ROM、不是耦合评估；`r2_full_flexible_coupling` 保持 NOT_EVALUATED；
  e15 `REPEAT_ANCF_CERTIFICATION` 不变；`next_stage_authorized=false`、`release_credit=false`。
