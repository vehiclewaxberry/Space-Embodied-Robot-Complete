# R2 内部线束与欠驱动状态集成

2026-09-20。近期目标：可装配、可上电的地面工程样机。本轮完成可复核的设计增量；整星电气制造、首次上电条件和在轨能力仍未完整闭合。

## 打开结果

- `native/SERVICE_STAR_SERVICE_R2.SLDASM`：SolidWorks 2024 整星服务态，1110实例，冷打开错误/警告均0、无需重建。沿用 R1 固定姿态，仅替换两条释放功能支路。
- `native/INTERNAL_HARNESS_DETAIL_R2.SLDASM`：20实例局部检视装配，已冷打开检查。
- `cad/INTERNAL_HARNESS_DETAIL_R2.step`：独立AP242局部模型，毫米/S坐标；可用于不带原生工程的几何检视。
- `views/INTERNAL_HARNESS_R2_COMPARISON.png`：实际STEP生成的修改前后图。

原生装配依赖本工作区同级 `SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/native`。R2增量ZIP不是完整跨计算机Pack-and-Go；复制原生工程时必须保留R1。局部STEP自含几何。两条新支路是复合线束功能包络，不赋予虚构均质材料或真实线束质量；R1已有材料保留，整星可信质量/质心/惯量仍为null。没有新增连续运动配合。

## 本轮交付与边界

| 工作 | 已完成 | 仍需输入 |
|---|---|---|
| 内部静态布线 | 两处M3RB穿透各456.336 mm³降至0；固定端点，R14/OD4；三固定态静态筛选，最小名义间距0.75 mm | 公差/热变形/振动裕量，真实线径/分叉/应力释放/动态走线；0.75不是工程裕量，+Y偏移0.76即出现穿透 |
| 电气接线 | 锁定249ref/795pin现行网表；86记录/84active；新增6根AUX、6根NTC的接线和物料候选 | 168端中144仍属逻辑/外部要求；工作电流、真实远端、切长、工艺与板卡宿主安装。制造发布为0 |
| 欠驱动/推进 | 静态分配与单故障检查器，9模式证据合同；区分轮组储动量、外力矩、正推力可达性 | 实装喷口数/r/d/COM、脉冲/并发/喷流；当前轮候选4×RW400 30档与研究3×100档不能混用 |
| 独立复验 | 电气、推进、路线各有独立回执；原生文件另有冷读回执 | 这些通过均不赋予可上电、整星完工或飞行资格 |

两条新中心线长度为191.645277和116.645277 mm，**不是下料长度**。两个逻辑记录共享几何走廊，未宣称两根物理电缆已经分开。近重合的两路线STEP交集布尔可能产生无效中间体，该共同体积保持UNKNOWN；每条STEP自身有效、33对结构/接口碰撞和独立复算结论有效。

## 逐项推进入口

先读 `docs/SYSTEM_COMPARISON.md`，其中对照NASA CPOD、ESA ClearSpace-1、NASA小航天器资料及线束工艺标准，给出10项按顺序推进的工作包。

1. 电气：`docs/ELECTRICAL_HARNESS_DESIGN.md`、`docs/ELECTRICAL_CONNECTION_MATRIX.csv`。将实际参数填写到 `inputs/ELECTRICAL_ACCEPTANCE_INPUTS.json` 的工作副本。
2. 推进：`docs/ORBIT_ACTUATION_REVIEW.md`、`docs/PROPULSION_GAP_ACTIONS.csv`。实际配置字段在 `inputs/ACTUATION_CURRENT.json`；数学12/24点对照未进入CAD/BOM。
3. 几何：`inputs/INTERNAL_ROUTE_PARAMETERS.json`、`results/RELEASE_ROUTE_STATIC_CHECK.json`。两个被拒绝的早期路径保留在 `results/RELEASE_ROUTE_ATTEMPT_*_REJECTED.json`。
4. 独立证据：`results/INDEPENDENT_ELECTRICAL_REVIEW.json`、`INDEPENDENT_ACTUATION_REVIEW.json`、`INDEPENDENT_ROUTE_REVIEW.json`。
5. 原生证据：`results/NATIVE_ROUTE_DELIVERY_V2.json`。首次保守包围盒口径失配及文档入口拦截均保留失败回执；改精确包围盒后复验，未放宽阈值。首次输入计划未单独封存的局限已在 `NATIVE_ROUTE_RECOVERY.json` 披露。

R1封存包、R1原生文件、旧HANDOFF/PCB/URDF和历史科学Gate保持原样。新增目录名沿用本轮开始日20260919，本文记录实际收尾日20260920。不要直接在交付目录重跑会覆盖输出的CAD构建命令；新迭代使用独立工作副本，并重新锁定来源与执行验收。
