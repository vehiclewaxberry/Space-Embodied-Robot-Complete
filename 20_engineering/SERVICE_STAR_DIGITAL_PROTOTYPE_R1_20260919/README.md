# 服务星地面数字样机 R1：集成候选与真实完成边界

本包按“先形成可装配、可上电的地面工程样机”的近期目标推进。当前不能宣布整星机械、电气、热控、辐射及推进工程设计全部完成，也不能以 CAD 可打开代替上电、热试验或飞行验证。

## 本轮最终数字交付

`results/BUILD_STATUS.json` 当前裁决为 `SOURCE_BOUND_FIXED_POSE_ARTIFACTS_VERIFIED_ENGINEERING_OPEN`。服务、收拢、释放三态 **SolidWorks 原生 SLDASM 与 STEP 均已生成并重新打开核验**；每态1110实例，STEP各1513实体。原生顶层打开错误/警告均为0，外部几何引用0，重建需求0。

- 原生入口：`native/SERVICE_STAR_SERVICE_R1.SLDASM`、`SERVICE_STAR_PARKING_R1.SLDASM`、`SERVICE_STAR_RELEASED_R1.SLDASM`；保留整个native目录。
- 当前装配使用692个不同零件和23个不同子装；536个零件实际赋予候选物理材料并冷读名称/密度，156个复合/未知零件仅记录身份与UNKNOWN，未伪造均质材料。
- 按单态实例计，762实例的候选材料读回通过，348实例保留未知/复合身份。三份 `docs/BOM_*_1110.csv` 是来源绑定的实例/材料账，不能替代已冻结采购BOM。
- 231个新增原生零件全部有来源、实体、尺寸和体积比较证据；9处接口合并已纳入。1233个已绑定输入文件的哈希不变。
- 主效果图为 `views/INTEGRATED_1110_SERVICE.png`，直接渲染最终STEP；打开操作见 `docs/SOLIDWORKS_OPEN_GUIDE.md`，后续13项工程闭环见 `docs/NEXT_STAGE_ENGINEERING_CLOSURE.md`。
- `views/INTEGRATED_NATIVE_SERVICE.png` 是实际新总装在桌面SolidWorks中的截图，已检查主体、双翼、机械臂和保持器可见；截图过程没有保存CAD更改。

本包是固定姿态集成候选，未建立完整连续运动配合或全部原生参数化特征树。当前材料名称/密度读回不等于完整有限元材料卡或实物材证。

## 已落实的工作

- 从经过来源绑定的 873 叶件宿主建立独立原生副本：510 个零件、19 个子装、3 个状态总装；原历史文件不修改。原生副本的全部几何引用已转入本包 `native/`。
- 对 510 个原生零件逐件建立材料身份；434 件实际写入 SolidWorks 候选材料并完成保存、关闭、重新打开、材料名称及密度读回。76 件复合或未知对象保留未赋值状态，不把默认密度计入质量预算。
- 核验 F 盘参考库入口、注册表、资料索引，并独立核验 15 个 NASA/OEM 等公开来源，形成 11 类材料和代理规则。实际审阅范围见 `inputs/README_REFERENCE.md`，没有声称全库全文精读。
- 将 WP10 电控安装增量与 R17 机械增量对齐。三态集成均为 **1110 个实例，1513 个STEP实体**：873 − 18 + 119 + 136。22 项 R17 替换及九项冲突合并不另增加实例。
- 九项接口生成保留既有孔系的合并 STEP：单件闭实体、布尔保留检查、STEP 导出回读通过；已生成实际几何快照。保守合并没有恢复旧分支填料，R01 的承压边接受结论不能继承。
- 独立审查完成：来源/矩阵/身份与未知量处理在所审范围内通过，裁决为 `PASS_WITH_OBSERVATIONS`；全系统完成度仍为未完成。

## 使用顺序

1. 先读 `results/BUILD_STATUS.json`，以文件实际存在和实际读回证据区分“计划”“已生成”“已验证”。
2. 打开 `native/SERVICE_STAR_SERVICE_R1.SLDASM` 等1110实例新总装。`WP09D_*.SLDASM` 仅是873实例宿主副本历史，不混入最终审查压缩包。所有依赖零件与子装须随总装保留。
3. `inputs/INTEGRATED_ASSEMBLY_PLAN.json` 是三态构建清单；实际原生冷读证据为 `results/TOP_service.json`、`TOP_parking.json`、`TOP_released.json`。
4. `neutral/` 中生成的 STEP 是命名几何装配交换件。STEP 颜色、结构名称不等于 SolidWorks 物理材料赋值；材料依据与未赋值对象须同时查看 BOM 和材料计划。
5. `views/` 中只采用已经实际检查、可见真实几何的图片。`BASELINE_873_NATIVE.png` 的首轮背景空帧已判不接受，不作展示证据。

## 材料及质量解释

原生材料库为 `native/GROUND_CANDIDATE_MATERIALS.sldmat`。本轮物理读回直接验证的是材料名称和密度；其他物性、温度条件与适用边界列于参考 JSON。现行批次主要是密度模型，不是完备的有限元材料卡。

既有 2700/7850 kg/m³ 均匀材料假设保留；新 304（7900）及 PEEK 450G（1300）是地面设计候选。304 牌号不等于 A2-70 紧固性能等级；材料牌号候选不等于实物材证。

机械臂 link、太阳电池复合层、设备、电池、PCB、线束、胶层等不统一赋予铝材。SolidWorks 未赋材对象可能显示软件默认质量；这些数值没有预算信用。整星可信质量、质心和惯量仍为 UNKNOWN，旧 URDF 和科学 Gate 不修改。

历史宿主的早期材料赋值未单录每件写入前哈希；因此804个保留实例在BOM中明确标为旧链限制，而非新增的连续几何哈希证明。当前材料冷读、原始复制记录和源STEP对账各保留其范围，不冒称历史实体已重新认证。

CHB500W单件默认OCP体积积分不可靠，初次严格比较失败已保留。独立Gauss–Kronrod收敛、SolidWorks最高精度和原生STEP往返支持参考值修正，仍使用原1e-5容差。往返周期曲面拆分527→778面；额外布尔同一性计算未完成，明确UNKNOWN，不宣称完整几何布尔等价。详见 `VOLUME_CROSSCHECK_2883.json` 与 `IMPORT_35_36_volume_reconciled.json`。

## 阻止“全系统完成”的具体事项

| 领域 | 当前不能略过的闭环 | 最小可接受证据 |
|---|---|---|
| 机械装配 | 九接口合并后的孔边、承压面、紧固件全装复核；R07 第六边接触刚度/预紧输入 | 新版实体干涉与间隙报告；硬件输入或有界设计合同 |
| 电气 | 45 项选型/资料缺口；V36 MAIN/AUX/STOP 完整 PCBA 模型及宿主安装；线束端到端绑定 | 选型BOM、原理图/PCB版本锁、接插件pin-to-pin、保护与受控首上电记录 |
| 地面热控 | CF1 旧热模块位姿有实体碰撞，尚未回装；导热界面压紧与实际热负荷 | 新位置零干涉、TIM压紧设计、热源清单、限温/断电策略和地面热试验 |
| 轨道热/辐射 | 轨道与姿态边界、冷热瞬态、接触导热与涂层寿命、器件TID/SEE | 受控任务边界、热模型及相关试验/辐射适应性证据 |
| 推进 | OEM 型号/接口未冻结，现有代理不是储箱—阀—管路—推力器设计 | 冻结型号和ICD、安装/羽流/质心核验；地面可采用明确无推进剂模拟件 |
| 动力学/具身智能 | 固定姿态 CAD 没有连续配合运动，新增硬件质量未闭合 | 新版接口/惯量账、限定状态和不确定性、连续运动及线束验证 |

Dawn B1 官方资料可补部分 Isp/功率缺项，但官网与 PDF 的冷气最小冲量存在 1.4/0.59 mN·s 冲突；本包登记冲突，不据此冻结推进选型。

本包可以用于有界布局、接口核查、材料敏感性与后续研究接口设计。若后续研究依赖真实可上电、热平衡或推进能力，需先完成对应上述项目；不能以“结构都画出来”宣布进入全部硬件能力已知的阶段。

## 证据与复现入口

- `inputs/REFERENCE_MATERIAL_BASIS.json`：公开来源与材料候选。
- `inputs/NATIVE_MATERIAL_PLAN.json`、`inputs/INCREMENT_MATERIAL_PLAN.json`：材料逐件计划。
- `results/MATERIAL_NATIVE_0_1_r3.json`、`results/MATERIAL_NATIVE_1_510_r3.json`：实际原生材料冷读回。
- `results/INTERFACE_MERGE.json`、`results/INTERFACE_VISUAL_CHECK.json`：九接口几何与实际快照。
- `results/INDEPENDENT_INTEGRATION_REVIEW.json`、`docs/INTEGRATION_REVIEW.md`：独立审查。
- `tools/prepare_integrated.py`、`tools/build_integrated.py`：隔离构建及读回脚本。
- `results/SOURCE_PRESERVATION.json`：1233个绑定输入哈希未变。
- `results/FINAL_REQUIREMENTS_AUDIT.json`：工程闭环审查；其中S03指向保留的审查时状态快照，最终交付另看当前BUILD_STATUS。

`SERVICE_STAR_R1_REVIEW_PACKAGE.zip` 在严格白名单和当前文件证据通过后生成；是否已经生成及ZIP哈希以 `results/PACKAGE_DELIVERY.json` 为准。它保留新总装的全部CAD依赖和审查资料；没有宣称跨电脑重定位或Pack and Go验收，也不包含所有外部历史源文件。

不执行采购、设备通电、推进剂操作或任何旧科学结论升级。原始资料、既有 Gate 和实测 UNKNOWN 均保留。
