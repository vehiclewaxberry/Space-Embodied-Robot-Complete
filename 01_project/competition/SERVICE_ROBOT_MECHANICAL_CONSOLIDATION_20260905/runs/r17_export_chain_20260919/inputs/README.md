# WP03 航天服务星整星集成设计候选 R1

主产品是无地面高架的完整服务星候选：星体主框、根部承载链、设备舱、完整 B601、两侧三叶太阳翼、两站随星保持器及外部接口。地面装调装配另列。本目录是新候选，原 WP01/WP02、accepted URDF/STL、厂家源和历史研究裁决保持原样。

[打开本地三维服务态](http://127.0.0.1:3246/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/20_engineering/service_robot_wp03_spacecraft_body_r1?file=servicer_service.step.py)；其他8个模型/图纸入口见 [VIEWER_LINKS.md](VIEWER_LINKS.md)。本轮已导出8个总装/模块STEP和145份定制局部零件STEP；服务态361个实例按用途及表示分别登记。数量不代表制造或飞行完成度。

当前可用于机械接口评审、数字试装与带明确参数缺项的自由漂浮多体模型建设。**它还不是制造发布、发射鉴定或标准 12U 部署器适配结果。** OPEN_PARKING_REFERENCE 仍是开放停放参考，不能作为飞行收拢状态。完整集成结论和真实负结果见 [INTEGRATION_REPORT.md](INTEGRATION_REPORT.md)。

## 先看这几项

| 入口 | 内容 |
|---|---|
| [服务态总装 STEP](servicer_service.step) | 无 GSE；完整臂、双翼展开、保持器折退 |
| [开放停放参考 STEP](servicer_parking.step) | 完整臂不改变原根部变换；随星保持器接触候选 |
| [释放后 STEP](servicer_released.step) | 臂保持停车姿态，保持器退出，双翼仍折叠 |
| [结构与设备舱剖视 STEP](body_equipment_cutaway.step) | 隐去覆盖件、臂和翼/保持器，检查甲板、设备安装及根框关系 |
| [主体爆炸示意 STEP](body_exploded.step) | 说明拆装层次；人工显示位移不用于碰撞或惯量 |
| [双翼模块 STEP](wing_module.step) / [保持模块 STEP](retention_module.step) | 可独立审查的随星模块 |
| [地面装调 STEP](ground_ait.step) | 同一停放服务星 + 独立 GSE 底板/支脚；不是完整机械臂卸载工装 |
| [接口尺寸图 PDF](drawings/WP03_INTERFACE_DRAWINGS.pdf) / [DXF](wp03_interfaces.dxf) | 6 张实际 BRep 面投影；mm，候选尺寸，NOT_FOR_MANUFACTURE |
| [总体评审图册 PDF](drawings/WP03_ASSEMBLY_REVIEW.pdf) | 实际 CAD 总体、停放、剖视、爆炸及模块视图 |
| [分类 BOM](BOM.csv) / [接口表](INTERFACES.csv) | 用途、表示、质量来源、父装配及未验证连接明确分列 |
| [装配程序](ASSEMBLY_SEQUENCE.md) | 18 步数字/实物后续装配顺序；实物尚未执行 |
| [动力学参数摘要](results/DYNAMICS_SUMMARY_ZH.md) | 同源三配置质量小计、质心、惯量和未知账本 |

## 可编辑源和参数

[spacecraft_model.py](spacecraft_model.py) 是随星与 GSE 共用的主体生成器；8 个同名 `.step.py` 是显式导出入口。[design_parameters.json](design_parameters.json) 定义状态、设备配置、材料假设及关键接口。[wing_kinematics.py](wing_kinematics.py) 定义连续串联翼坐标；[root_structure.py](root_structure.py) 重建继承根结构；[kinematics.py](kinematics.py) 保留 accepted 关节树。

所有状态在同一 S 坐标：星体核心几何中心为原点，+X 为任务纵向，+Y 横向，+Z 指向屋顶。臂根变换固定为平移 **[90, 0, 125.15] mm，旋转 I**。实体根承载面 Z127.555 mm 与 URDF 原点不同。

几何增量包括：改正 12×12、壁厚 2 纵梁的端塞尺寸；纵梁新接口孔；两侧剪力板和夹块；双层设备甲板、绕柱角材、设备适配板；检修盖安装边；后端承力框与肋；线束夹座立柱和热接口；两站屋顶安装的可折退保持器；翼根外置叉座、翼边框和错开的铰链耳座。定制件逐件 STEP 位于 [parts/](parts/)。

共享参数中 `solar_panel_mm`、`solar_hinge_z_mm`、`solar_side_gap_mm` 与旧支承字段是 WP01 来源遗留，**不驱动当前三叶翼及保持器**。当前有效翼尺寸/根部位置见 `wing_source` 和 `wing_kinematics.py`；有效保持器参数见 `retention`。部分细部厚度、孔系仍在主体生成器中显式定义，改动后必须重新生成对应输出及验证。不要仅修改 JSON 的遗留字段后认为几何已改变。

## 表示、质量与验证的读法

`ONBOARD_CANDIDATE` 表示随星设计用途；`GSE` 表示地面装调设备。`PHYSICAL_GEOMETRY` 是名义实体，`SIMPLIFIED_PROXY` 是预算设备或标准件代理，`FUNCTIONAL_ENVELOPE` 是连接器、线路、机构或保留空间。三种表示均未自动获得环境资格。不能以 STEP 体积、颜色、外观相贴或零距离认定部件实选、连接承载或电气闭合。

新金属件按候选密度估计质量；B601 采用 accepted URDF 的逐 link 数字惯性，共 4.695555949342986 kg，不重复计入名义 BRep 密度质量。设备和翼叶片的预算与假设分布单列。未知质量保持 null；已分配小计不是完整飞行质量。GSE 和任务目标不进入随星质量。

最终随星已分配小计 **20.716839 kg**。BOM中的 `mass_kg` 保留原始几何记录，`allocated_dynamics_mass_kg` 显示交接账本的唯一质量分配（包括accepted数字臂），两列不可相加。保持器下鞋由30改为80 mm、导杆由70改为150 mm，消除了原路径在所测角度的臂材质碰撞；71状态复检仍有功能驱动包络待定项。每层甲板X150两孔与立柱缺口连通，不能按8个完整安装孔计承载，详见图注与装配流程。

验证入口：

- [GEOMETRY_CHECK.json](results/GEOMETRY_CHECK.json)：非臂物理实体静态 OCC 成对检查，排除设备/紧固件代理及功能空间；不覆盖完整臂或连续动作。
- [INTEGRATE_CHECKS.json](results/INTEGRATE_CHECKS.json)：accepted STL 与本轮名义边界的集成采样，区分候选碰撞与真实碰撞证据。
- [WING_KINEMATICS_CHECK.json](results/WING_KINEMATICS_CHECK.json)：91 个翼叶片采样，固定偏置运动学；不等于完整铰链硬件连续路径检查。
- [POSE_SCREEN.json](results/POSE_SCREEN.json)：有限现有姿态筛查；未找到可据此宣布紧凑飞行收拢的结果。
- [FRAME_STIFFNESS_SCREEN.json](results/FRAME_STIFFNESS_SCREEN.json)：理想梁骨架单位载荷柔度，区分发射端固定、地面固定、自由体边界；不是结构强度或全星有限元认证。
- [DELIVERY_RECEIPT.json](results/DELIVERY_RECEIPT.json)：最终文件、源哈希、实际导出/验证/快照范围；不是新科学 Gate。

完整臂名义 BRep 与 accepted STL 并非同一几何，继承的源拓扑问题保留。`*_refs.json` 中的 `ok` 只代表可解析，实体健全性需读取 `*_validate.json`。本轮自交检查按资源范围跳过，不能写成全部拓扑通过。早期构型发现的物理重叠和翼叶片重叠分别保存在 `GEOMETRY_R1_FINDINGS.json`、`WING_KINEMATICS_R1_FINDINGS.json`，不删除负结果。

官方完整服务态检查742个叶实例，6处 `invalidTopology` 均来自继承的B601名义源；新增非臂物理件三态各179件有效闭壳单实体，静态成对检查0正体积交叠。官方refs摘要受未三角化面的原点零盒和旋转局部盒影响，不能直接替代实形包络；[包围方法对照](results/BOUNDING_METHOD_COMPARISON.json)以两套实际网格顶点复核了源收据。inspect还会重新序列化STEP，最终交付哈希绑定其实际导出；四份完整配置收据的内容保持字节一致。

## 进入动力学与控制研究

先以当前逐原子质量、COM、惯量、accepted 关节树和固定根变换建自由漂浮刚体基线。姿态表中的整体惯量只适用于锁定相对运动的该构型；机械臂运动时保留逐 link 自由度和关节/基座耦合。随后明确设备未知质量的参数区间，加入基座执行器、关节驱动与释放时序，再引入经验证的太阳翼柔性参数。新几何不得直接继承旧仿真的 PASS。

下一轮优先落实三类实体输入：①发射/分离供应方接口与环境载荷，确定可接受的全整机收拢方向和边界；②B601 实装版本、允许支承区域、根连接及线束动态参数；③释放器/确认器、EPS/姿控/计算通信实选和质量分布。详细事项、边界和原始来源见 [DYNAMICS_AND_QUALIFICATION.md](DYNAMICS_AND_QUALIFICATION.md) 与 [SOURCE_AND_INTERFACE_NOTES.md](SOURCE_AND_INTERFACE_NOTES.md)。

## 本机复现

在本目录打开 PowerShell，使用现有 CAD 环境，串行运行：

```powershell
$env:PYTHONUTF8='1'
& 'G:/Windows_program_file/Anaconda/python.exe' 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/gen' servicer_service.step.py servicer_parking.step.py servicer_released.step.py --write --mesh-tolerance 0.3 --mesh-angular-tolerance 0.3 --json
& 'G:/Windows_program_file/Anaconda/python.exe' export_parts_and_bom.py
& 'G:/Windows_program_file/Anaconda/python.exe' geometry_checks.py
& 'G:/Windows_program_file/Anaconda/python.exe' dynamics_handoff.py
& 'G:/Windows_program_file/Anaconda/python.exe' integrate_checks.py
```

三态完整收据均完成后再运行参数交接；改动几何后重新导出并复核快照。原始 import/记录工具 `setup_candidate.py` 只用于首次建立候选，不作为日常重建入口。名义完整机械臂来源较大，请避免与其他 CAD 任务并行运行。
