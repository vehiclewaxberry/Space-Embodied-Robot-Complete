# A4-B1 Build Attempt 01

> `RESULT: FAIL_CLOSED_BEFORE_FIRST_ASSEMBLY_SAVE`  
> `A3_MUTATED: false`  
> `GATE_OR_SIMULATION_MUTATED: false`

首次运行已生成 master skeleton 与五个 12U 结构零件，但在创建 `12U_Structured_Bus_Visual.SLDASM` 时，SolidWorks `AddComponent5` 对已关闭的零件返回 null。

根因属于自动化装配加载顺序，不是几何或来源合同失败。修正方式：插入组件前使用原生 `OpenDoc6` 只读预加载对应 `.SLDPRT/.SLDASM`，然后再设置冻结变换并固定组件。

该失败尝试的半成品目录由本轮生成，不作为 A4-B1 交付；清理后从空的 V1.0 目标重新执行。

## Attempt 02 启动拦截

第二次启动在创建首个零件前 fail-closed。原因是 Attempt 01 留下了一份无路径的临时装配体 `装配体13`，导致 `NewDocument` 返回 null。已按以下条件确认后仅关闭该临时文档：

- SolidWorks PID 与构建会话一致；
- 文档总数为 1；
- 文档路径为空；
- 标题为自动临时装配体；
- 关闭后文档总数为 0。

Attempt 02 只产生一份 `builder_failure.log`，没有产生 CAD 文件。

## Attempt 03 性能中止

干净会话健康探针通过后，Attempt 03 能创建 master skeleton，但 SolidWorks 在用 20 次独立拉伸构建主框架时失去响应。该尝试被主动中止，未进入装配和视图阶段。

修正方式不改变几何语义：把四根纵梁合并为一次多轮廓拉伸，把每个横向框环的四根梁合并为一次多轮廓拉伸；外板、任务面和同舱占位体也采用同样批量策略，降低原生重建负担。

## Attempt 04 轮廓修正

批量策略显著缩短了启动时间，但四根框梁在角部形成重叠闭环，SolidWorks 拒绝 `TRANSVERSE_FRAME_RING_1` 的重叠轮廓拉伸。修正为一个外矩形加一个内矩形的标准环形截面；任务面框采用同一表达。该修正只消除无效重叠轮廓，不改变框架外形和舱段边界。
