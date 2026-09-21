# SolidWorks 打开与材料核对

以 `../results/BUILD_STATUS.json` 的实际读回状态为准。本包是地面集成候选数字样机；固定姿态和候选材料用于接口审查，不代表系统已经可上电或具备在轨服务能力。

## 原生装配

使用 SolidWorks 2024 或兼容较新版本，保留整个 `native` 文件夹。优先打开：

- `SERVICE_STAR_SERVICE_R1.SLDASM`：服务姿态。
- `SERVICE_STAR_PARKING_R1.SLDASM`：收拢/停放姿态。
- `SERVICE_STAR_RELEASED_R1.SLDASM`：释放姿态。

三态均为独立固定姿态；没有连续运动配合，不能拖动关节就认为已验证运动或线束活动范围。子装按资源批次分组，不是已冻结的系统工程分解。

打开时可先采用轻化模式；需要查看实体或测量时解析相应子装。内存紧张时一次只打开一个姿态。文件使用毫米几何；脚本与 API 的米制转换已单独核对，不要再次整体缩放。

`WP09D_*.SLDASM` 是本轮起点的873实例宿主副本，留作证据。不要把它当作1110实例集成结果。审查压缩包仅纳入新装配的依赖白名单。

## 材料

右击零件的材料节点可查看候选材料名称。材料库为 `native/GROUND_CANDIDATE_MATERIALS.sldmat`；如需在材料编辑器中选择同名材料，可将该文件所在目录添加到“文件位置 → 材料数据库”。无需为查看现有文件批量重新赋材。

本轮原生核验直接覆盖材料名称和密度。弹性、导热、比热等公开物性及适用温度见 `../inputs/REFERENCE_MATERIAL_BASIS.json`，未全部写入有限元材料卡。候选牌号不等于采购材证，也不证明空间适应性。

设备、机械臂复合 link、PCB、电池、太阳翼层合体及线束等无法合理按单一均质材料描述的对象保留 UNKNOWN。检查零件自定义属性 `DP_MATERIAL_STATUS`、`DP_DENSITY_KG_M3` 与 BOM；软件给出的默认密度和整星质量不得作为质量预算。整星可信质量、质心和惯量尚未闭合。

## STEP 与展示图

`neutral/SERVICE_STAR_*_R1.step` 是三态命名装配交换件，适用于其他 CAD 或较旧 SolidWorks 的几何导入。它保留实体与姿态，不承诺保留 SolidWorks 原生材料、参数化特征树或运动配合。

`views/INTEGRATED_1110_SERVICE.png` 来自实际交付 STEP。颜色只表示视觉角色，不代表材料赋值；少量历史 B601 面不能三角化，图中显示其边界，原始 BRep 仍保留。详细限制见 `results/NEUTRAL_ASSEMBLY.json`。

`views/INTEGRATED_NATIVE_SERVICE.png` 为实际SolidWorks原生总装视图；其默认外观与STEP展示图不同。打开、显示和截图通过不代替干涉、热或电气验收。

网页 CAD Viewer 启动被本机 `build123d` 的字体读取错误阻断；未改系统字体或外部依赖。请使用原生 SolidWorks、STEP 和已核验的静态图查看。

## 包迁移与研究使用

本机新目录的原生冷读与引用检查不等于跨电脑 Pack and Go 验收。转移文件时整包解压、保持 `native` 内文件同目录；不要只复制顶层 SLDASM。跨机首次打开仍须核对缺失引用、1110实例身份、姿态及材料状态。

下一阶段按 `NEXT_STAGE_ENGINEERING_CLOSURE.md` 完成对应工作包。可以继续有界布局和研究接口工作；涉及实际供电、热平衡、推进能力或新增整星动力学参数的研究，应先具备相应输入与证据。
