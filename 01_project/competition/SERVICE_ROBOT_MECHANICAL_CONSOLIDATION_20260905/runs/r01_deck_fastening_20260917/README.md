# R01 甲板—角材—剪力板紧固 run（r01_deck_fastening_20260917）

WP03 服务星结构 R01 票唯一构建者 run。授权范围：仅 digital_geometry / nominal_digital_assembly 子项；父票不关闭。

## 目录

- `inputs/` — 改前输入快照 + `INPUT_MANIFEST.json`（sha256）
- `scripts/` — s00 快照 → s01 参数插入 → s02 聚焦构建导出 → s03 验收1 → s04 验收2+32 组表 → s05 BOM/质量 → s06 验收5 builder 自检 → s07 验收3/4+边车 → s08 build() 烟测
- `exports/` — 44 个 STEP（2 甲板、8 角材、2 剪力腹板、32 紧固包络，S 系世界坐标，mm）+ `EXPORT_MANIFEST.json`
- `evidence/` — 机器证据 JSON/CSV，全部带 `.sha256` 边车（LF）
- `logs/` — 构建/烟测原始日志
- `PATCH_NOTES.md` — 补丁说明（改前/改后哈希、变更范围）
- `ACCEPTANCE_SUMMARY.json` — 七项验收逐项状态

## 七项验收速览

1. 16/16 闭孔、破边消除、孔到柱避口最小 9.8 mm — **PASS**
2. 32/32 组基准/孔轴/方向/单位/夹层一致 — **PASS**
3. 承压区完整、柱避口保留（12 壁/深 12.5）— **PASS（结构许用边距 UNKNOWN）**
4. 32 行紧固叠层可审查，材料/啮合/预紧/防松 UNKNOWN — **PASS_WITH_UNKNOWNS_PRESERVED**
5. 具名检查集合 108 项、0 违规、46 条装序约束 — **PASS_BUILDER_SELF_CHECK**
6. 独立复验 — **NOT_RUN（审阅者）**
7. 同源 PASS；图纸与全装重建 NOT_RUN；R07 未触碰 — **PARTIAL**
