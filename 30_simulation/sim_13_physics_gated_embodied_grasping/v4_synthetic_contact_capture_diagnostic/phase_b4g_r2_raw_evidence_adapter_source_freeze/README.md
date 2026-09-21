# B4G R2 原始证据适配器源码冻结

本包冻结 `SIM13_V4B4G_R2_RAW_EVIDENCE_ADAPTER_V1` 的源码、合同、负控和只读复核链。它不运行 physics、solver、trajectory 或 campaign，不产生持久化 NPZ/CSV/URDF/STEP，也不授予数值、当前系统、NC19、科学、Owner、生产、发布或下一阶段信用。

最高允许状态仅为：

`PASS_R2_RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY`

## 当前工程边界

- 适配器只接受项目根相对、无路径别名、无 symlink/reparse、单硬链接的 strict JSON sidecar 与 immutable NPZ。
- sidecar 和 NPZ 均单次读取，并分别绑定 path、bytes、SHA256；数组从已哈希字节的 `BytesIO` 以 `allow_pickle=False` 解包。
- 暴露给消费者的 ndarray 以 immutable `bytes` 为底层缓冲区，不能重新打开 writeable；sidecar 递归冻结。
- R2 合同有 56 个 exact 数组，统一采用 little-endian float64/int64 或 bool，SI 单位和固定形状；旧 B4G 25/44-key raw 不兼容。
- mechanical stages 原生不含旧 code 0。RK4 每区间为 1/2/3/4，midpoint 为 1/5。
- finite removal 只允许末区间缩步；G06 使用实际末步长。no-event 必须完整保存 acquisition 后 80 ms。
- acquisition 必须是 active saved sample 0；removal 采用 0/1 cardinality raw event 数组，不使用 null、伪时间或伪索引。
- finite post 必须精确保存 5 ms，saved interval 等于注册 lane step；本包只重算明确列名的 **stored-array partial post checks**（work carry、zero command、array zero-jump、原生动量/能量漂移、阈值化 Hermite gap/rate 与已存 stage domain/P/Jac 一致性），不把这些子检查称作完整 G11 或独立 geometry replay。
- `registered_roles` 与冻结 78 行 matrix/schedule 逐行哈希绑定；同一 fine alpha16/10 ms raw 可同时进入 acquisition、alpha16 与 G12 分析视图，不复制 raw。
- 78 行结构审计要求原始顺序与 `schedule_index` 逐位一致，并形成 6 个 A0 pair、2 个 fresh-acquisition triplet、6 个 common triplet、18 个 alpha16 raw 接口和 18 个 G12 pair。

COMMON sidecar 的 `common_donor_hashes_before/after` 是 producer 声明；adapter 在**每次加载该 case 时**于 NPZ 解包前后各自重新读取、rehydrate 并哈希冻结 donor 来交叉核验。它不是历史 trajectory 执行时刻的 deep-copy provenance，也没有跨 case 的成功缓存。

## 重要 HOLD

现有最小 R2 schema 尚不足以完整、独立重放 G03/G05/G07/G08/G09/G10/G11/G16 的全部冻结谓词（例如注册 sin² command、完整 geometry replay 和 parent mapping）。因此 G12 只输出 raw-derived 子谓词，并固定：

- `full_raw_integrity_recomputed=false`
- `source_only_candidate_predicate_pass=false`
- `eligible=false`
- `HOLD_G12_FULL_RAW_INTEGRITY_BACKEND_NOT_IMPLEMENTED_SOURCE_FREEZE`

这意味着 adapter 的 raw P1 风险已被显著收窄，但尚未消灭，不能借本源码冻结宣称 R2 numerical preflight 已执行。

## 只读复核

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B -m pytest -q -p no:cacheprovider
python -B validate_phase_b4g_r2_raw_adapter_source_freeze.py
python -B independent_audit_phase_b4g_r2_raw_adapter_source_freeze.py
python -B verify_phase_b4g_r2_raw_adapter_read_only_replay.py
```

默认 validator/audit/replay 不改写冻结回执。预注册 vNext runner 的 consume/import/output/run 四条成功路径均无条件拒绝；只有未来直接 Owner source 与新的明确授权才可在另一个执行包中实现。
