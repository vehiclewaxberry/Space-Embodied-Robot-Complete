# 12U 服务星 R4 独立布局评审

日期：2026-09-20。阶段：地面数字样机安装/功能布线增量独立复验。评审者：独立 hardware-reviewer agent。

**结论：PASS_WITH_OBSERVATIONS__R4_BOUNDED_STATIC_LAYOUT_AND_NATIVE_BINDING。** 1037 项检查通过。此结论只覆盖 R4 有界数字增量与已完成原生装配收据，不代表完整 PCBA、可上电样机或飞行设计完成。

评审只写本文件和 `results/INDEPENDENT_LAYOUT_REVIEW.json`。未编辑 CAD/原理图/PCB/输入/构建工具，未启动 SolidWorks 或控制硬件。原生引擎执行结果由构建者完成；评审者核对其完成收据、源绑定、逐实例实体计数及磁盘哈希。

## 复核覆盖与结果

- 独立重组 R1 canonical STEP＋对应 S 系变换、R2 路线替换、R3 接口替换与 R4 增量。718 个相关 STEP 源文件哈希匹配；现行变换仅应用一次。未将历史世界坐标 STEP 配上 canonical-local 变换。
- 26 个增量 STEP：6 个替换件、20 个新增安装件。独立读取实体数、有效性、体积和尺寸；8 实体接口模块保持功能预留性质。
- 服务、停放、释放三状态各 1130 实例；各 127 对候选，其中 6 对属于已声明共享功能路线/既有端点，剩余各 121 对、合计 363 对精确检查。复算覆盖与构建收据一致，没有新增穿透；跨状态共 124 个不同源/变换几何配对。
- 宽相位使用已绑定 R1 map SHA 的 R2 局部包围盒；对本次实际加载的 60 个 STEP 源另核精确尺寸及缓存保守性。没有声称对全宿主所有源重新读取包围盒，也没有重新检查全部旧件之间的配对。
- 四安装点 XY：(-125,-63)、(-75,-63)、(-125,-33)、(-75,-33) mm。直径 3.4 mm 孔贯穿 PCB、转接板、设备层板；TIM 直径 6.4 mm 避让孔及支撑接触独立验证。转接板/层板/TIM 仅切除，分别移除 72.633622、108.950433、64.339818 mm³，新增材料为零。
- 20 件五金为四套柱、螺钉、上下垫圈、螺母；杆部与孔名义径向间隙 0.2 mm。两前排插头到对应螺钉头最小 2.3490195 mm；接口模块到夹具 2.0000000 mm。
- 两释放路线公共起点 (65,-80,118) mm、终点 (-115,-80,118) 和 (-40,-80,118) mm 保持不变。OD4/R14 仅为功能通道参数，长度分别 193.399932969 和 118.399932969 mm；不是下料长度。最大切向误差 2.9894e-16；独立弧长×截面积与 STEP 体积差均小于 1.4e-10 mm³。
- 释放路线到当前障碍最小距离 2.625653251 mm（ROOT_BUSH_LEFT），到 M3RB 为 2.865439343 mm。2 mm 是名义几何筛查目标，不含制造、热变形、振动与动态裕量。
- 原生冷复验：1130 实例、697 个活动原生零件文件、1540 实体、14 组；全部 fixed、resolved 状态 2，总变换最大误差 6.6613e-16，冷开 0 错误/0 警告，重建成功且 NeedsRebuild2=0。独立对 758 个旧/新原生文件核哈希，并按全部实例重新累加实体数。评审未独立目视审查原生预览。

## 发现与修复

**已修复 R4-OBS-03：尺寸合同可能静默漂移。** 初版构建脚本读取 PCB_mount 后继续使用硬编码尺寸；当前尺寸吻合，但修改 JSON 不会驱动模型或拒绝失配。现加入入口逐项校验，12 个安装尺寸/型号加 3 个布局约束保持冻结。独立在内存逐项扰动 15 个字段，全部拒绝；另审阅构建者真实入口扰动收据：非零退出、合同字节恢复、26 个 STEP 哈希不变。本轮没有重建几何。合同明确为冻结尺寸合同，不能单改 JSON 驱动全部 CAD。

**保留热缺口。** PCB 底面 z=-1.5 mm，TIM 顶面 z=-6.0 mm，存在 4.5 mm 空隙。现有 TIM 没有直接接触 PCB；经柱/热带/专用导热件的路径、电隔离/接地和实测热导仍未闭合。

**共享路线诊断。** 两条逻辑分支有相同路线段，同一内部小探针在两个 STEP 内均有 π mm³ 实体交集。直接对两共形扫掠做 Common 会返回 invalid 形状及 0 体积；该结果保留为不可用诊断，不能用零体积认定它们是两根分离电缆。原有共享功能路线排除合理，不赋予物理线缆分隔信用。

**评审探针修正保留。** 最初把整颗螺钉到上垫圈距离预期设为 0.2 mm，忽略螺钉头的设计接触；改为仅杆部后得到 0.2 mm。此项属于评审测试口径修正，不是设计缺陷。历史短支路回转反向也被独立重算检出，切向单位向量误差为 2；现行版本已消除该反向。

## 五轮评审

1. **Completeness — PASS。** 已通过 Gate 的项：无编号 Gate 继承；既有未变化 R3 电气/OEM 选型不重复认证。R4 有界安装、功能布线、受控源与原生绑定覆盖完整。
2. **Risk Identification — CONCERN。** 已通过 Gate 的项：无。发现：4.5 mm 热路径间隔及共享功能通道仍开放。建议：绑定真实导热/绝缘接口与物理线缆分配，保留 Common 数值退化诊断。
3. **Implementability — CONCERN。** 已通过 Gate 的项：无。发现：板及插头仍是占位，螺纹圆柱不能证明强度、啮合、预紧与防松；完整插入和工具路径未检。建议：冻结 PCB/连接器及紧固件 MPN、材料、公差、预紧和装配顺序。尺寸合同漂移已修复。
4. **Cost Reasonableness — CONCERN。** 已通过 Gate 的项：无。发现：新增件质量和成本未冻结。建议：实物/目录质量、供应商与采购成本形成独立增量；不得再次叠加旧 0.8 kg 接口预算。
5. **Validation Coverage — CONCERN。** 已通过 Gate 的项：无。发现：仅三个固定状态的增量检查；材料赋值、全星质量惯量、完整运动、结构/热试验、上电及在轨适用性未验证。建议：沿下一阶段验收闭合，不能由此继承完整工程 PASS。

| Area | Status | Key Finding |
|---|---|---|
| Completeness | PASS | R4 有界增量和原生绑定覆盖完整 |
| Risk Identification | CONCERN | 热路径、物理线缆分配仍开放 |
| Implementability | CONCERN | 实物选型、公差、预紧、插入路径待定 |
| Cost Reasonableness | CONCERN | 新增质量、物料与成本待冻结 |
| Validation Coverage | CONCERN | 无全运动、上电、结构/热试验或飞行信用 |

CF1 未装入 R4。旋转搜索即使另有完成收据，也不进入本次安装或电气/热控信用；其 V30 空间模块不等同于现行 V36 完整 PCBA。现有电池包络与结构障碍未因 R4 改动删除。

## 证据入口

- `results/INDEPENDENT_LAYOUT_REVIEW.json`：逐项检查、实际几何结果、来源哈希和修复前后诊断。
- `inputs/MOUNT_LAYOUT.json`、`inputs/PASSAGE_LAYOUT.json`、`inputs/NATIVE_ASSEMBLY_PLAN.json`。
- `results/INCREMENT_STATIC_CHECK.json`、`results/MOUNT_STATIC_CHECK.json`。
- `results/DIMENSION_CONTRACT_NEGATIVE_CONTROL.json`、`tools/check_dimension_contract.py`。
- `results/NATIVE_ASSEMBLY_DELIVERY.json`、`results/NATIVE_ASSEMBLY_RECHECK.json`。
- 上游 R1 `inputs/NEUTRAL_SOURCE_MAP.json`、R2 `inputs/NATIVE_ROUTE_PLAN.json` 与 `SOURCE_LOCAL_BOUNDS.json`、R3 `inputs/NATIVE_ASSEMBLY_PLAN.json`。

原生顶层 `native/SERVICE_STAR_SERVICE_R4.SLDASM` SHA256：`1f78c56680ee704c77a73ba8a461be257533bfb898eb7021242133f99eb53b92`。
