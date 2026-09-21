# writers

Episode 写入器实现位于 [`../../src/dh_v1/episode_writer.py`](../../src/dh_v1/episode_writer.py)（单一实现，避免双写盘路径）。

- 合同：[`../EPISODE_SCHEMA.json`](../EPISODE_SCHEMA.json)（writer 内置 `MANIFEST_REQUIRED` 与 schema required 字段一致，pytest 校验）
- 不可变性：episode 目录存在即拒绝写入（重跑 = 新 `episode_id`）
- 硬校验：`EXECUTE`+`T_E_T=MISSING/UNKNOWN`、`EXECUTE`+接触权威缺失 → `EpisodeWriteError`
- 输出：12 个固定文件 + `HASH_MANIFEST.csv`（全部产物 SHA-256）
