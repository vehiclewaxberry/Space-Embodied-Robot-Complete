# 873 实例增量的独立审查与质量结转

本次独立审查完成 **943/943** 项来源、算术和连续区间检查；质量结转完成 **1081/1081** 项身份、源哈希及分账检查。审查没有调用 CAD、OCC、COM，也没有改写父本 705 质量账、冻结装配或科学 Gate。

[独立机器审查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/results/INDEPENDENT_DELTA_REVIEW.json>)、[873 逐实例质量账](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/MASS_ASSIGNMENT_873.json>)、[逐实例 CSV](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/MASS_ASSIGNMENT_873.csv>)、[43 组汇总 CSV](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/MASS_OWNER_SUMMARY_873.csv>) 可直接复核。它们对应实际 STEP 增量和三态装配输入计划；原生装配的成功集成、冷读与图像审查以 CAD writer 的另行回执为准。

## 新发现和处置

仅发现一项新的来源元数据错误：R01 选型文件及生成器将 ISO 7092 垫圈资料写为 Rev0.1300、2025-10-10，已锁本地原厂 PDF 第 1 页实际为 **Rev0.1314、2026-08-03**。PDF SHA256 和几何/料号均一致，错误没有改变模型尺寸。已发布[版本勘误](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/SOURCE_REVISION_ERRATUM.json>)；为保留正在执行的 CAD 合同哈希，未修改原输入。后续主交付采用该勘误。

[原厂垫圈资料](https://marketplacemedia.witglobal.net/source/marketplace/stmedia/wuerth/documents/documents/std.lang.all/29208728.pdf) 支持 M3、内径 3.2、外径 6、厚 0.5 mm 和料号 515005013；当前网页缓存版本可能与本地锁定版不同，因此以 SHA 绑定的本地文件作为本次复现版本。另已逐页检查本地 Würth 螺钉/螺母 PDF：00843 10/12 为 ISO 4762 8.8 级螺钉，0324903 为 ISO 4032 10 级螺母，名义 AF5.5、高2.4 mm。

## 有限范围内已核实的设计

- R01 四种规格合计 128 个实例：M3×10/12 各 16，垫圈 64，螺母 32。2.52 mm AF 六角孔是明示的名义代理，2.5 mm AF 驱动工具的外接圆直径为 2.886751 mm；不能继承旧 Ø2.5 mm 圆柱工具的路径结论。每侧 0.01 mm 平面间隙只针对理想对正六角代理，不是工具、圆角、磨损或安装公差的保证。
- R01 原 128 件均采用烘焙整星 S 坐标与单位装配变换。新几何使用 128 个源坐标 STEP 替换；4 个 canonical 参考实体不计成额外装配件，也不加入质量。
- 原厂 CIC 的 40.15×80.15 mm 对应玻璃外形。成形互连片可能伸出，现有 84 层采用 `GLASS_FOOTPRINT_CIC_LAYER_PROXY`，完整包络仍未知。[原厂 General Information 第 7 页](https://www.azurspace.com/media/uploads/file_links/file/bdb_00010890-01-00_generalinformationazur.pdf) 对应 81442 的图号为 ZP0004289，完整 STEP 需索取。
- 独立按串联机构公式重算 776 个已认证区间，在每个区间重新检查全部 15 对板包络、分离轴与旋转位移上界。最小间隙下界 **0.3006434925831589 mm**，与原回执最大差 8.88×10⁻¹⁶ mm。4.5 mm 间距下的折叠厚度合同净缝为 0.82 mm。
- 连续证明只覆盖指定四段路径中的六块矩形板及最大面层；叉耳、销轴、机械臂、星体、焊片、布线、柔性、热变形和任意其他动作路径均不在证明内。不能写成“整机连续无碰撞”。

## 质量结转

质量数值采用源生成器记录的 **build123d `shape.volume` 默认体积积分×候选密度**。其调用链为 `Solid.volume → Shape.compute_mass → BRepGProp.VolumeProperties_s(shape, properties)`，没有显式设置 Eps。本账不是 SolidWorks `GetMassProperties` 的原生质量属性，也不是精确目录质量。当前8件边框的源体积来自生成形体并绑定STEP文件；构建回执不等于原生冷读确认。历史父本的同类默认体积模型继续保留，未把一侧替换成高精度积分、另一侧留默认积分。数值积分误差未给出严格界，因此边框差值是该计算模型内的增量。

CAD回读发现默认源体积与SW体积积分之间有差异。唯一CAD writer已完成8件边框的“源STEP→native→STEP”同OCC自适应积分和双向布尔差检验：8件均在内核容差内等价、相对体积差≤1e−7；`native_GetMassProperties_scalar_equivalence=false` 仍明确保留。旧8个源STEP也用同一自适应积分复算，其新旧材料质量差为0.000118906323448 kg，仅作诊断。账本保留默认方法差0.000118914850491 kg，不用算法口径变化伪造机械增减质量。32个源/原生/往返STEP/旧源文件SHA及8个身份已由索引复核；最终对拍/整机冷读绑定状态见[质量交付索引](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/results/MASS_ROLLFORWARD_873.json>)。

873 个实例在三个状态中是同一套硬件，质量只计算一套。责任归属 873/873，共 43 组；物理或代表硬件为 872 个，另 1 个为纯预留空间。306 个有材料模型，94 个由整模块厂商参考值覆盖，合计 400/872；**472 个数值未闭合，涉及 30 组**。责任覆盖与数值覆盖分开报告。

| 项目 | 本次结转 |
|---|---:|
| 父本 705 已绑定材料模型小计 | 7.820206000189 kg |
| R01 128 个新代理的钢材模型 | +0.051978452357 kg |
| 8 个太阳翼边框新旧体积对应质量差 | +0.000118914850 kg |
| 当前材料模型部分小计 | **7.872303367396 kg** |
| B601 整臂厂家名义参考，独立列示 | 4.5 kg，整臂一次 |
| 84 个整 CIC 平均重量参考，独立列示 | 0.3024 kg，84×3.6 g |
| 84 层外部安装胶体积 | 27031.389 mm³ |
| 84 层外部安装胶质量 | 未知，密度/材料未选 |

R01 原705账中的质量是 null。因此不能只加“新旧几何差”0.000195382813 kg；正确做法是先绑定原几何钢材模型 0.051783069543 kg，再加该差，等价于直接加入新几何的 0.051978452357 kg，且仅一次。边框旧质量已存在，必须作替换差量。CIC 3.6 g 对应厂商整体平均重量参考，不是玻璃代理密度法质量，也不是实测单件值；其内部盖玻璃、原厂胶层、旁路二极管与原厂互连片不重复相加。外部板上安装胶是独立新增的正体积、未知质量。

原六片叶板各 0.18 kg 的历史预算是否包含 CIC 尚未绑定；它只留在非加和历史栏中。未将设备预算、材料估算和厂家名义数相加形成“整星总质量”。整星总质量、质心、惯量、实测质量及严格实物质量下界均保持 null。

## 保留的工程边界

标准料号选择和实体有效性不能替代真实螺纹、预紧/锁紧、圆角承压、扭矩、强度、完整工具通路和制造公差验证。板材铺层、嵌件、胶种、CIC 成形焊片及其串接线尚未形成完整接口。质量账仅覆盖当前装配计划中的实例；后续真实推进模块、高功率供电/充电、停机驱动、再生吸收器和阻断/布线等硬件若纳入整机，需要正式新增或替换实例及对应质量，不能以当前 873 数量宣称硬件齐套。

复现脚本为[独立区间审查](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/independent_review.py>)和[质量结转](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp09_interfaces_20260907_1525/system_completion/review/mass_rollforward_873.py>)。全机详细机电设计完成、制造放行和物理验证信用均未授予。
