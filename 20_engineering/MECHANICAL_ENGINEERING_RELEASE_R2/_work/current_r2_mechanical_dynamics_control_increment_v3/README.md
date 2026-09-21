# Current R2 Mechanical–Dynamics–Control Increment V3

本目录是 **append-only 证据聚合增量**，不是机械、动力学或控制父 Gate 的重发。它只做四件事：

1. 精确固定 V2 聚合包及其原有 HOLD 边界；
2. 如实保留时域候选的 `19/20` 与单点 G04 失败；
3. 聚合追加式 metric-parent rebind 的 `16/16` 局部 PASS，不改写原候选；
4. 精确固定不导入候选核心的时域外部审计包。

最高主张仅为追加证据自洽：时域根坐标系 twist-rate 研究诊断已执行，原候选仍须复跑；单点父 HOLD 指纹的内存副本重绑定可复算，但不构成 pre-contact tracking、control、hardware、contact、collision、SAFE、Sim13、non-abort、next-stage 或 release 许可。

## 复现

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -B build_increment_gate_v3.py --check
python -B validate_increment_gate_v3.py --check
python -B -m pytest -q -p no:cacheprovider test_increment_gate_v3.py
```

任一上游 bytes/SHA、严格 JSON、计数、结论或权限边界发生漂移时，本包必须 fail-closed；禁止在本目录内“修复”历史父 Gate。
