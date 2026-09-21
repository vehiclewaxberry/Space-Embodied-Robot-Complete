# WP02 复现说明

单位为mm、N、N·m、kg；角度输入为deg，柔度矩阵明确区分rad及力矩单位。所有命令在本WP02目录执行。本机使用G:/Windows_program_file/Anaconda/python.exe，CAD工具位于F:/codex_skill/AgentSkills/codex-skills/cad/scripts。

```powershell
$env:PYTHONUTF8 = '1'
$wp02Python = 'G:/Windows_program_file/Anaconda/python.exe'
$wp02Cad = 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
```

正常复算不运行bootstrap.py：它是首次输入复制脚本。先按INPUT_PROVENANCE.json和厂家VENDOR_SOURCE_RECEIPT.json验证原始来源，避免静默替换输入。INPUT_PROVENANCE的COMPLETE_MACHINE_READ表示已读完整字节并计算哈希，不表示仅凭哈希即完成语义/拓扑审查。

## 参数和几何

design_parameters.json为本候选的设计参数；parts_model.py构造每个零件与命名局部连接基准。四个.step.py是主CAD入口。保持/释放只是同一参数化组合件的两个状态；STEP中的形状/标签不等同原生CAD求解器的可驱动装配配合。

```powershell
& $wp02Python contact_registration.py
& $wp02Python harness_analysis.py
& $wp02Python parts_model.py
& $wp02Python "$wp02Cad/gen" key_assembly_held.step.py --write
& $wp02Python "$wp02Cad/gen" key_assembly_released.step.py --write
& $wp02Python "$wp02Cad/gen" root_connection.step.py --write
& $wp02Python "$wp02Cad/gen" key_assembly_context.step.py --write
```

修改参数后，必须同步查看相应功能所使用的字段，不能只修改显示值。parts_model.py每次构建会重写对应build_receipt；后续依赖其哈希的检查应最后运行。12个原臂/M3R源BRep保持来源哈希，不重新写入源文件。检查使用的accepted STL按m→mm只缩放一次。

## 数字检查

```powershell
& $wp02Python vendor_geometry_probe.py
& $wp02Python root_compliance.py
& $wp02Python motion_analysis.py
& $wp02Python release_state_machine.py
& $wp02Python key_geometry_check.py
& $wp02Python fixed_gse_arm_path.py
& $wp02Python validate_outputs.py
```

validate_outputs.py运行四模型的refs --facts --planes --positioning和validate --skip-self-intersection，共8次CLI检查。每实体有效性、装配有限配对、状态逻辑和梁模型自检分别报告，不能合并解释为物理装配通过。根部柔度是理想下端夹固的梁试件筛查，未计算整星飞行边界下强度。

几何检查脚本存在分阶段写回，运行时不要消费半成品JSON；等进程退出后再核对source_changed_during_run与来源哈希。历史R1/R2结果为固定反例/过程证据，不重写其判定。

## 图纸、视觉和交付

```powershell
& $wp02Python "$wp02Cad/gen" key_interfaces.dxf.py --write
& $wp02Python render_drawings.py
```

DXF从真实BRep顶面投影；绘图用局部runtime_deps下Shapely2.1.2和Matplotlib，PDF为5页矢量尺寸图。没有完整公差、材料/热处理、防松和承载依据，所有图纸维持NOT_FOR_MANUFACTURE。

四主模型均经CAD snapshot生成并人工查看。results/SNAPSHOT_RECEIPT.json保存8张图片的原始工具回执。释放状态ISO图顶部裁切，选用完整front图作为该状态的交付审阅视图；context ISO与根部top均完整。DXF的3D snapshot工具需要preview.glb，而当前2D包只产生drawing.json/geometry.json，因此该预览未成功；PDF/PNG渲染及人工检查已完成。

最后运行finalize_packet.py。它只读取结果、复查源文件哈希、确认交付文件存在并写DELIVERY_RECEIPT.json及OUTPUT_SHA256.csv；不执行CAD或物理试验。清单排除缓存、运行库、临时日志及清单自身；历史反例单独保留。主模型几何修改后须重新完成相关数字检查与截图审阅，再运行收口脚本。
