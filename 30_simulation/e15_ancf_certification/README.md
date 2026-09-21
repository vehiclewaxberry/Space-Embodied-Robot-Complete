# E1.5 ANCF 数值认证（独立专用树）

本目录只读调用冻结提交 `6c15395` 中的旧模型与证据，不修改旧 E1/E1.5、VIZ v0、CAD、`30_simulation/`、`src/` 或共享合同。

认证范围：

- 7 个历史 `RETRY_OK/FLEX_SOLVER_FAIL` 工况的逐 hash 独立重跑与类型化失败分类；
- Radau/BDF、容差、最大步长、ANCF 单元数和瞬时/有限时宽冲量的交叉检查；
- 位移坐标非线性 ANCF 对独立线性模态闭式参考的低振幅极限验证；
- 线性有限元 Newmark 平均加速度法的固定步长趋势；
- UNKNOWN fail-closed：无数值填零，不进入排序、训练或安全评价。

运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python 30_simulation/e15_ancf_certification/src/certify.py --mode all --workers 3
python 30_simulation/e15_ancf_certification/tests/run_tests.py
```

快速复核（不重跑历史长时程）：

```powershell
python 30_simulation/e15_ancf_certification/src/certify.py --mode finalize
python 30_simulation/e15_ancf_certification/tests/run_tests.py
```

`--mode finalize` 只重算表格、Gate、哈希清单和报告，不启动新的数值积分。

所有生成物仍写在 `30_simulation/e15_ancf_certification/results|tables|docs` 内。
