# Post-capture spatial-inertia kernel external audit v1

本目录位于候选包之外，持有 `SOURCE_LOCK_V1.json` 中预先冻结的 10 个 bytes/SHA-256 期望值，覆盖 evaluator、包内 standalone validator、tests、contract、核心源码以及 evidence/gate/manifest/internal receipt。审计程序不在自身进程导入候选包，不从候选包当前内容动态生成期望哈希；它另在隔离子进程执行运行时伪造合同、伪造 receipt 文件和调用者额外 contract 参数负控。

本包证明“候选包与这份冻结锁一致”，并不自称是最终不可变信任根。更高层汇合包必须固定本包的 `SOURCE_LOCK_V1.json`、`audit_external.py` 和 external Gate SHA；该上层 pin 才是跨包审查入口。

审计独立重算两个合成 fixture 的 `T_B_T`、质量/质心/惯量、6×6 空间惯量、含数值 `origin_O_in_I_m` 的捕获后 twist，并验证参考点平移律 `H_O'=H_O-(r_O'-r_O)×P` 及相反叉乘符号 falsifier。

通过仅表示：合成刚性空间惯量内核与其 fail-closed 权限边界通过包外固定 pin 审计。C08/C09 仍为 `NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3`；不授予 contact、attachment、plant、hardware、SAFE、CAD、M01、parent、next-stage 或 release 信用。

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B 30_simulation/r2_dynamics_engineering_closure/post_capture_spatial_inertia_kernel_external_audit_v1/run_validation.py
```
