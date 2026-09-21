# WP03 最终 CAD 与图纸视觉复核

对象：冻结主体源 `11bd80a667505fc5fd0cf9bc79f7a892bcab5424ae16997de4fd0f163f53a2e9`，80 mm 下鞋退让、150 mm 导杆。实际 CAD snapshot 输出存于 `../snapshots/`，共 13 张 PNG，覆盖全部 8 个主交付入口。所有截图均已逐张打开检查。

| 入口 | 已看视图 | 观察和适用范围 |
|---|---|---|
| servicer_service | iso、opposite、top | 完整臂和夹爪、双侧三叶翼、屋顶根接口及折退保持器同装配；未出现 GSE底板。保持器折退后外伸仍明显，不能声称紧凑。橙色线路为未注册端点的功能代理，不是悬空实线缆已装配。 |
| servicer_parking | iso、front | 根部不变，双翼折叠，两站保持器位于星体屋顶；上方臂/保持器外伸显著，标签保持 OPEN_PARKING_REFERENCE。 |
| servicer_released | iso | 臂仍停放，保持器折退后保留在随星系统，没有删除质量。这里只是释放后关键帧。 |
| body_equipment_cutaway | iso、opposite、internal | 前两视图显示剪力板与背部发射接口保留区；两侧剪力板遮挡内部设备，因此增加 internal 显示隐藏 `#o1.1.38` 和 `#o1.1.57` 后的视图。隐藏仅作用于渲染，实体、BOM和质量不变。甲板、设备盒及根柱可见；设备底脚/线路/实际紧固的未定接口保留。 |
| body_exploded | iso | 覆盖件和设备层被显示移开，明确是装配说明；不将图中间距或人工位移用于可达性、惯量或碰撞。 |
| wing_module | iso | 六叶片、板端外置叉耳/轴销与固定根候选可见。橙色孤立盒属于从整星分出的释放/线束功能预算，不作为实体安装已完成。 |
| retention_module | iso | 两套独立屋顶安装、上盖/锁带/下鞋/导杆可见；驱动器与确认件仍包含功能代理。 |
| ground_ait | iso | 仅该主视图增加绿色GSE底板和四脚；与无GSE停车星体一致。 |

截图生成与参数见 `CAD_SNAPSHOT_RUNS.json`、各 `*_snapshot.json`。internal 补充视图为官方snapshot命令：`--input body_equipment_cutaway.step.py --hide '#o1.1.38' '#o1.1.57' --camera iso --width 1920 --height 1440 --view-labels`。这是针对原剖视遮挡设备的有因补图；未更改物理几何。

两份PDF经独立审查者逐页直接 PDFium 渲染：接口图6页、总装图9页，全部15页未见截断/遮挡，可提取字符越界数0。前三张总装页的全显示尺寸与最终同源收据一致。第4页明确“显示隐藏剪力板，真实装配与质量保留”；第8页顺序26 mm/100°/80 mm/90°正确。接口第1页已修订为6闭孔+X150两处破边孔，17 mm宽×12.5 mm深实际边口；两处孔边距/角材匹配须重设计。中文标题视觉正常，但部分字体以图形字形记录，不保证文本检索。

最终PDF哈希：

- `WP03_INTERFACE_DRAWINGS.pdf`: `782a5af1a7aebfe614db2d09ee79c8f6c2301419c1b208de6368fae057ee3bc0`
- `WP03_ASSEMBLY_REVIEW.pdf`: `0653d679907b4708d18ca7af9f9e808e39979b55fe2f44862c8338698e686b4d`

视觉检查不代替工程验证。实体结果以三态 `GEOMETRY_CHECK.json`、完整服务态 `servicer_service_validate.json` 为准；完整臂来源的6处拓扑问题仍在。官方 refs 摘要包围盒含空面零盒及旋转保守盒扩张，不用于精确总体尺寸；具体反证见 `BOUNDING_METHOD_COMPARISON.json`。连续全路径、包容碰撞、实际驱动/线束、连接预紧、载荷及环境资格尚未完成。
