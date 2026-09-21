# R5E 电气候选选型与电热输入更新

日期：2026-09-20。目标：未采购的地面工程样机，沿用 B601 驱动和主机连接假设。

本包更新 **选型 BOM、器件参数、替代限制和电热输入**。现有装配仍为 R4；本包不声称增加了实际 PCBA、线缆或新 SolidWorks 装配。

45项历史问题现已分别处理为：32项单器件无源候选、7项IC参数补录、1项R305双串ECO候选、5项接口/铜盘分类；另恢复U301的原源精确料号。249行是本电源/STOP原理图的位号数，不能替代整星装配BOM。

先读 [本轮说明](docs/hardware/03-components.md)，再读 [约束与下一步](docs/hardware/04-constraints.md)。

- [249 行选型 BOM](bom/ELECTRICAL_SELECTION_BOM_R5E.csv)：保留原始值、原始封装与候选字段，区分已布板器件和待落地器件。
- [候选采购明细，未放行](bom/PROCUREMENT_CANDIDATES_NOT_RELEASED.csv)：219 个逻辑实物候选；若实施 R305 两串方案则为220件。不是全星 BOM 数量，不含模块内部或整星线束物料。
- [45 项逐项处置](results/GAP_DISPOSITION_45.json)：处置完成不等于工程验收完成。
- [ECAD 变更清单](bom/ECAD_ECO_R5E.csv)：新选型与 R305 拆分均明确标注实施状态。
- [电热输入](results/ELECTROTHERMAL_INPUT_UPDATE.json)：R202=0.5mΩ，20A 下 R201+R202=1W。
- [独立源复验](results/reviewer/SOURCE_REVIEW_FINDINGS.md)：三板实读与249-ref锁定网表匹配；旧 v36/xml 存在239-ref漂移。
- [KiCad候选原理图入口](ecad/selection_candidate/wp10_system.kicad_sch)：15张原理图，11张写入46个位号的278项候选属性；C301的新候选容量与原值分开记录。
- [原生网表复核](results/ECAD_CANDIDATE_VERIFICATION.json)：58/58，249位号和795个pin-net对保持一致，原Value/Footprint/连线未改；旧239-ref源的负控被拒绝。
- [最终交付范围与证据](results/RELEASE_STATUS.json)：构建检查与独立工程评审分别记录。
- [独立最终评审](results/reviewer/FINAL_REVIEW.json)：数字复算65/65、候选网表2047/2047；候选包可交付，工程HOLD保留。
- [下一步逐项工作单](results/NEXT_ELECTRICAL_WORK.json)：先处理有效电容/封装与R305，再进入紧凑PCB和电热布局。

`inputs/LOCKED_SYSTEM_249.xml` 是原网表的字节一致快照。禁止从239-ref旧别名生成新全量 BOM。未知负载、器件温度、接口电流和偏压后的有效电容均保持 UNKNOWN。

BOM的`ecad_applied_this_round=false`与ECO的`NOT_APPLIED`专指元件值、封装及拓扑的功能性变更；本轮已写入的是`R5E_`候选属性。原始Value和Footprint仍反映旧实现。候选工程不能直接生成用于生产的最终装配清单。

复现（工作目录不限）：

```powershell
& 'G:/Windows_program_file/Anaconda/python.exe' -B -X utf8 'F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_ELECTRICAL_UPDATE_R5E_20260920/tools/build_electrical_update.py'
```

本包不授予采购、上电、制造或在轨资格。R4/R5 布局、旧 HANDOFF 和历史 Gate 未改写。
