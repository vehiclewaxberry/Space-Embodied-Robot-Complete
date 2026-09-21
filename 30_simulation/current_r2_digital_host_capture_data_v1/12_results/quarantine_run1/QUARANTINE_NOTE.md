# Run1 隔离说明
Run1（后台任务 bjuiojbng）在 S07 episode 写入阶段崩溃：terminal WAIT 被直接用作数据集标签，
被 EpisodeWriter 的标签校验硬拒（EpisodeWriteError: label 'WAIT' not in LABELS）。
这是 fail-closed 校验按设计工作的真实负结果，予以保留：
- episodes_QUARANTINED_run1_crash_wait_label/：崩溃前已写出的 6 个 episode（S00/S01/S02x3/S03）
- s03_QUARANTINED_run1/、_quarantine/*.parquet、s07_work_run1/
处置：LABEL_TAXONOMY.yaml 固化 decisions_vs_labels 条款（WAIT=决策非标签，终态 WAIT → NOT_EVALUATED+reason），
run_increment.py 修正后以 Run2 全量重跑。Run1 产物不参与任何 Gate 计数。
