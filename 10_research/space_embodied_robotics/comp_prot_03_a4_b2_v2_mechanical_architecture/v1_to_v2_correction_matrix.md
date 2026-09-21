# V1.0 → V2.0 机械架构修正矩阵

> `STATUS: DESIGN_DELTA_BASELINE`  
> 本表只定义下一版的合法增量，不表示 V2.0 CAD 已完成。

## 修正原则

V1.0 已完成工程视觉闭环，V2.0 不以“重新画一遍”作为进步。每项修正必须增加系统职责、接口或可审查性，同时保持证据边界。

| 对象 | V1.0 已有事实 | V2.0 应新增 | 禁止的伪修正 | 未来验收证据 |
|---|---|---|---|---|
| 总体包络 | `COMPETITION_DISPLAY_V0`、`340.5×226.3×226.3 mm` | 顶层 skeleton 参数与发布接口 | 静默换成另一套 12U 尺寸并称标准合规 | master parameter inventory |
| 坐标系 | `S/M/A0/G/E_virtual`；`T_SM` 已钉住 | 每个一级模块绑定 frame owner | 把 `T_SB` 继续写成机械臂 mount transform | frame inventory + SSOT link |
| 外框 | 纵梁、端框/框环和外板可识别 | 主/次结构分类、连接和载荷路径 owner | 用“看起来更厚”宣称承载更强 | structure-class inventory |
| 三舱 | 两个边界 deck 与三舱视觉层级 | 每舱功能、设备安装面、volume owner、维护方向 | 只换颜色或加标签 | bay interface register |
| 前任务模块 | mount、sensor reference、任务面存在 | 工具访问、线缆过孔、keepout、mission interface owner | 添加无来源相机/FOV/照明实体 | mission-module review |
| 中平台舱 | 设备占位存在 | OBC/EPS/PMAD/battery/RW/IMU 的独立 volume owner 和抽取方向 | 给占位块写型号、质量、热功耗 | equipment-volume register |
| 后服务舱 | visual placeholder 存在 | propulsion/comm/thermal/service 分区和隔离 owner | 画储箱/喷管后宣称推进系统完成 | service-zone register |
| robot mount | 160 mm plate/boss、视觉加强和走线存在 | 反力输入—局部加强—任务面框—纵梁的闭合链路 | 以加强筋外观宣称刚度/强度通过 | load-path diagram + unknown loads |
| B601 | 10-link/9-joint、q0 与来源哈希闭合 | 作为受控子装配接入，不改拓扑 | 改 URDF、合并 link、从壳体反推质量 | topology/hash comparison |
| gripper/末端 | existing gripper、`G`、`E_virtual` | 仅增加接口资格审查占位 | 建 physical TCP、接触垫或 F/T 并称已实现 | disabled-interface check |
| 太阳翼 | `F_L/F_R` 展开参考和 safe display proposal | root/hinge/interface、状态槽、扫掠 owner | 把静态展开/收拢称部署验证 | configuration register |
| 传感器 | 零实体语义 reference | mount reserve、遮挡检查责任和未来 `T_SC` 字段 | 猜相机型号、FOV、标定 | zero-solid + unknown check |
| target | 独立场景、无 contact/mate | 保持隔离，新增任务接口需求占位 | 把 target 拉入 active assembly 或制造“已捕获” | assembly exclusion test |
| 干涉 | q0 部署参考 10 处静态干涉负结果 | 设计新收拢/安全提案并限定范围复核 | 隐藏组件、改配置后宣称全局安全 | named-scope interference report |
| 服务性 | 爆炸/剖切展示 | 面板拆卸、托盘抽取、工具访问、线束路径 | 只做动画爆炸视图 | service-access matrix |
| 物性 | CAD 无质量/惯量权威 | 质量 owner 和待填接口，不填无证据数值 | 用 SolidWorks 默认材料/质量覆盖 SSOT | zero-authority audit |
| 证据 | 43/43 seal，V1 哈希闭合 | V1 seal 前置核验 + V2 独立 manifest | 覆盖 V1 或删除失败/负结果 | two-version hash report |

## V2.0 的定义性变化

V2.0 应当让评审者能回答：

1. 哪些零件属于主结构，哪些属于次结构？
2. 机械臂反力通过哪些接口传回星体主结构？
3. 每个舱段承载哪些系统体积和维护动作？
4. 哪些接口已被证据绑定，哪些只是设计提案，哪些仍阻塞？
5. 修改总体包络、mount、太阳翼或设备布局时，哪一层 skeleton 是唯一驱动者？
6. V1.0 证据、V2.0 提案与未来物理资格之间是否被清楚隔离？

若只能回答“模型更漂亮了”，则 V2.0 不合格。
