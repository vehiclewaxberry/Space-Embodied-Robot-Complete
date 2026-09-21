# WP06 四处侧连接机械整改交付

已完成四处旧侧连接的实体整改与局部数字验证，可进入该局部的样机试装准备。交付为 **53 个 SolidWorks 零件＋1 个局部装配**，其中八个结构件改动、十六件新紧固件、二十九件相邻结构。整星与 B601 主装配保持原版本；本次局部视图不代表整星全部设计完成。

四个侧孔由 X154 移到 X146，下孔轴由 Z−94 调至−93.5，上孔保持 Z94；夹块、柱梁原位置保留。四根裸杆替换为 ISO4762 M3×12 螺钉、DIN125 M3 双垫圈和 ISO4032 M3 螺母。下角材增加向顶边开放的 U 形工具槽，保留原剪力板承压面。实际螺钉—立柱距离由 **0 提高到5.5 mm**，横竖螺钉间距为1.0 mm；名义夹持厚度9 mm、穿出0.6 mm，完整牙啮合仍待实物规格确认。

首轮发现下层垫圈及套筒路径碰到两颗甲板螺钉头。采用已复核的 C02 工序：其余甲板连接保留，在给定支承条件下先完成侧接头，再补装 R01_D_lower_±1_140 两完整甲板接头的八件硬件。补装、上下工具及退出路径均重新检查。内工具到甲板名义间隙0.65 mm，到 U 槽0.20 mm。此结论以结构件已就位、位姿冻结为条件；工装及结构件本体装入未验证。

89项实体几何检查、20对真实承压面测量、3780项限定范围的静态与包络检查通过（含包围盒筛查）；旧源八件对拍、24件参数扰动及24件恢复通过。原生装配保存重开后，53件依赖、实体和位置通过；实际 SolidWorks STEP 回导也通过53/53项材料与位置对照。31个绑定源输入未变。原失败回执保留，历史扫掠文件的哈希恢复过程单独披露。

**待核定：** 1.3 mm 角材端部剩余边、1.05 mm 孔间薄壁的承载，材料与制造公差，实物螺纹、防松、预紧，真实工具及工装。现有 B601 几何 HOLD、整机连续动作和制造放行状态不变。SolidWorks 文件为导入实体及固定定位装配；可调参数保存在 Python/JSON 源中。

下一工包仍围绕这四处接头：绑定真实工具/工装和采购紧固件规格，完成公差、预紧与试装条件细化。

- [打开局部 SolidWorks 装配](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/native/WP06_SIDE_JOINT_C02.SLDASM>) · [零件目录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/native/parts>) · [BOM](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/results/LOCAL_BOM.csv>)
- [交互查看局部 CAD](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233?file=candidate/wp06_side_joint.step.py) · [内侧细节](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/results/snapshots/lower_inside_20260906T175759Z.png>)
- [机器回执](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/results/WP06_RESULT.json>) · [源参数](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/candidate/design_parameters.json>) · [源改动](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/results/SOURCE_CHANGES.diff>)

目录几何身份与校验值见[来源记录](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233/inputs/CATALOGUE_PROVENANCE.json>)。尺寸交叉依据：[Bossard M3 驱动规格](https://www.bossard.com/th-en/-/media/bossard-group/website/documents/technical-resources/en/f-077-en.pdf)、[Würth M3 螺母](https://eshop.wuerth.de/Hexagon-nut-ISO-4032-steel-6-8-plain-NUT-HEX-ISO4032-6-WS55-M3/031093.sku/en/US/EUR/)。几何目录与尺寸参考不构成采购或材料认证。

目录件交互查看：[din125_flat_washer_m3](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233?file=inputs/catalog/din125_flat_washer_m3.step) · [iso4032_hex_nut_m3](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233?file=inputs/catalog/iso4032_hex_nut_m3.step) · [iso4762_socket_head_cap_screw_m3x12](http://127.0.0.1:3245/F:/China%20Graduate%20Future%20Flight%20Vehicle%20Innovation%20Competition/01_project/competition/SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905/runs/wp06_side_joint_20260907_0233?file=inputs/catalog/iso4762_socket_head_cap_screw_m3x12.step)。
