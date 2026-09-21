# Target Models v0 参考输入

## 1. 建模定位

本项目需要建立三类目标模型：失效小卫星、圆柱碎片/适配器、合作服务接口对象。外部资产只提供几何层级和报告叙事参考，目标模型必须由本项目重新定义。

## 2. Target-1: `failed_6U_or_12U_satellite`

| field | content |
|---|---|
| reference_source | BIRDSX-CAD 2U STEP parts; OreSat frame/solar/antenna assets; CDS CubeSat envelope constraints |
| geometry_parts | 主体盒体、导轨/框架、太阳板、天线、外表面小部件、AprilTag 平面 |
| grasp_features | 预设把手、结构边框、抓取环或标准接口；不得默认抓取太阳板/天线 |
| visual_marker_location | 前向可见面或抓取接口附近；应避开太阳板遮挡 |
| collision_envelope | 主体盒体、太阳板薄板包络、天线细长包络、禁抓取区域、允许抓取区域 |
| report_usage | 展示非合作失效小卫星捕获任务；用于“视觉识别 -> 接近 -> 抓取 -> RNS 抑制基座扰动”叙事 |
| adaptation_needed | 不直接复制 BIRDS/OreSat；按 6U/12U 目标重新建立简化模型和质量惯量字段 |
| priority | P0 |

## 3. Target-2: `cylindrical_adapter_or_debris`

| field | content |
|---|---|
| reference_source | NASA SmallSat SOA active debris removal text; 本地未发现适合直接引用的圆柱碎片 CAD |
| geometry_parts | 圆柱主体、端面环、加强筋/法兰、可选抓取带、AprilTag 小支架 |
| grasp_features | 圆柱外表面指定抓取带、端面环、加强筋或夹持区域 |
| visual_marker_location | 圆柱端面平面支架，或外圆柱面附加小平面；需记录标记法向 |
| collision_envelope | 圆柱主体、端面、法兰、禁碰非抓取区、允许夹持区 |
| report_usage | 展示碎片清除任务，强调非合作目标、低速接近、碰撞包络和禁碰区域 |
| adaptation_needed | 由本项目建立原创简化圆柱模型；质量惯量按薄壁/厚壁圆柱估算并标注来源 |
| priority | P0 |

## 4. Target-3: `cooperative_service_interface_object`

| field | content |
|---|---|
| reference_source | SOA servicing/debris removal examples; OreSat/BIRDS 结构接口作为外观层级参考 |
| geometry_parts | 服务对象主体、把手、环、对接接口、视觉标记板、禁碰边界 |
| grasp_features | 标准把手、抓取环、对接接口或夹持杆 |
| visual_marker_location | 把手/接口附近的正向可见面；保证机械臂接近前相机能看到 |
| collision_envelope | 主体包络、接口包络、允许接触面、禁碰边缘 |
| report_usage | 展示合作目标在轨服务任务，突出 VLA 高层任务选择和传统控制执行的分工 |
| adaptation_needed | 本项目原创建立把手/环/接口几何；不能直接从外部模型声称已有接口 |
| priority | P0 |

## 5. 通用输出字段

- target coordinate frame `T`。
- grasp frame `G`。
- AprilTag frame `A`。
- collision primitives。
- visual mesh or report geometry。
- mass, center of mass, inertia estimate source。
- allowed contact surface and forbidden contact region。

## 6. 不适合直接采用的内容

- BIRDS 2U 不应直接作为失效 6U/12U 目标星。
- OreSat 结构不应改名为本项目目标星原创模型。
- SpaceRobotEnv 的 `cube.stl` 不应直接作为目标星模型。
- 本阶段不生成真实 CAD，仅定义参考输入。
