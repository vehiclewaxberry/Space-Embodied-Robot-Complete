# SEI-PL1 Quarantine Plan (pending authorization)

`READ_ONLY_AUDIT` 产出;未获得 `AUTHORIZE_PL1_QUARANTINE_MOVE_20260828` 前不做任何移动。

## 分类汇总

| 动作 | 数量 | 字节 | 说明 |
|---|---:|---:|---|
| DELETE_EPHEMERAL | 535 | 9526643 | cache/tmp/pyc, untracked, no ref |
| QUARANTINE_EXACT_DUPLICATE | 220 | 331040589 | A内同哈希、无引用、canonical在A |
| HOLD_UNRESOLVED | 26361 | — | worktree/donor/rootB/archive/protected/引用检出 |

## QUARANTINE 候选构成(220)

| ext | count |
|---|---:|
| .json | 78 |
| .parquet | 75 |
| .sldprt | 20 |
| .sample | 19 |
| .md | 14 |
| .dcm | 3 |
| .yaml | 2 |
| .txt | 2 |
| .csv | 1 |
| .py | 1 |
| .bbl | 1 |
| .html | 1 |
| .lib | 1 |
| .hpp | 1 |
| .config | 1 |

## 执行前提(Phase E)

1. 复制到 `F:\_SEI_RETIREMENT_QUARANTINE_20260828\`(保留相对路径+属性);
2. 源/副本双 SHA-256 一致后删源;任一失败 fail-closed;
3. 隔离区最早硬删除日 = 2026-09-15,需 `AUTHORIZE_PL1_HARD_DELETE:<manifest-sha256>`;
4. 不移 HOLD/CURRENT/HISTORY 任何文件。
