# R121 / R20 工程裁决

裁决：`LOCAL_R20_CANDIDATE_GATE_PASS`。20 个 Route-C 根部静态对象已形成逐对象 STEP-first 的本地 S-frame 碰撞几何候选；这不是系统碰撞注册、pair/edge/path 认证或机械发布许可。

- 独立几何：20/20 STEP 均为单根、单闭合正体积 BRep；`T_S_A0` 每对象恰施加一次，STEP 保持 mm，运行时 sidecar 仅做一次 0.001 的 mm→m 缩放。
- 源审计：V9F R121 为 121 个对象、117 个单 solid、4 个双 solid、共 125 solids；53 个对象具有非 identity FreeCAD Placement，验证链确认没有二次施加 Placement。
- 运行时与复现：60/60 PLY/NPZ/STL 从重开 STEP 独立派生；两次 fresh-process `--check` 保持 83/83 确定性核心不变；pytest 226/226 PASS。
- 负控：33/33 合同负控及 4/4 补充负控被 fail-closed 捕获。
- CAD 审阅：20/20 inspect 与 20 张快照＋contact sheet 完整。CAD Viewer 因已安装包缺少 `agent:start` 而真实 FAIL；该工具失败未被伪装成 PASS，也不是本地几何 Gate 的来源。
- 诊断缓存：首轮 20 个 GLB 加尾部异步重放 10 个 GLB 已留证。重放文件同字节数但哈希不同，因此全部标为 `NONDETERMINISTIC_DIAGNOSTIC`，不属于主 STEP、83 件确定性核心或 Gate 判据。

系统状态保持：1/150 operational、0/11166 pair queries、0 SAFE、0 edges、0/3 stages、无 path；`TMG4=HOLD`、`G12=FAIL`、Gate A=false、release credit=false。R101 的 q-dependent host/special-motion adapter 仍为 fail-closed HOLD。

最高合法主张：`TWENTY_LOCAL_S_FRAME_STEP_FIRST_ROOT_STATIC_ROUTE_C_COLLISION_GEOMETRY_CANDIDATES_ONLY`。
