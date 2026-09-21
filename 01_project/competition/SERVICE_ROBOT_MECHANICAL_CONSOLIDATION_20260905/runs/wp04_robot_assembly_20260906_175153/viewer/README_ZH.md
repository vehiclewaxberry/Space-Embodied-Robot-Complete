# 航天服务星 × B601 整机数字装配查看

打开本地页面 `http://127.0.0.1:8767/index.html`。所有显示资源在此目录，页面不访问外网。

可查看三种离散构型、开关结构/机械臂/设备/保持机构/太阳翼/功能包络、淡化遮挡查看内部、点击零件查证据、用滑块作示意分解。分解不是已验证的安装轨迹。

`scene.json` 是显示输入，`VIEWER_BUILD_RESULT.json` 是绑定检查。`development: true` 时只显示前一轮 R01 测试基线，页面顶部会有标记。最终交付必须由本轮 candidate 重新打包。

几何来源与单位：

- 非臂结构：本轮三态 STEP 的 CAD 缓存 GLB 与 `assembly.json`。GLB 顶点单位为米，occurrence 矩阵平移单位为 mm，页面将平移除以 1000。
- 部分 BRep 有内部位置/旋转，因此 occurrence 矩阵不总等于账本的外层 `T_S_local`。构建器采用真实缓存矩阵，校核变换后网格世界包围盒与实例账本的 S 系包围盒；2 mm 只作为粗三角化显示比例检查阈值，绝不用于碰撞或装配间隙判定。实际误差见结果 JSON。
- B601：直接复用项目 accepted URDF 引用的十个原始 STL，顶点为米。各连杆用最终完整回执的 `link_transforms`。这是 accepted STL 数字表示；没有重新生成或修复原始臂 BRep。
- 功能包络默认隐藏；代理件与实体、质量 UNKNOWN 和资格未验证状态可在零件详情查看。原始实例质量 UNKNOWN 与动力学数字质量分配口径不同，不能把此页计数当作质量预算裁决。

重新生成（纯文件/JSON/网格读取，不调用 CAD 内核）：

```powershell
& 'G:/Windows_program_file/Anaconda/python.exe' './build_viewer.py'
```

仅用于开发的旧基线选项为 `--candidate <旧候选目录> --development`；最终模式拒绝外部候选路径。

启动只读服务：

```powershell
& 'G:/Windows_program_file/Anaconda/python.exe' -u './serve_viewer.py' --port 8767
```

服务只监听 `127.0.0.1`，只读取此 viewer 目录。它独立于 3245 CAD Viewer，启动脚本不会终止既有进程。

`/deliverables/` 为已列明交付文件的只读白名单；构建器也将相同哈希的资料复制到 `viewer/deliverables/`，可用于静态服务和离线打包。白名单不接受任意工作区路径。

`export_complete_glb.py` 在最终 scene 绑定后将全部服务态实例合为单一 `complete_service_robot.glb`：保留六类组件、实例名称、真实米制变换及来源/资格元数据。只合并已有三角网格和 STL 数组，不调用 CAD 内核。`COMPLETE_GLB_EXPORT_RESULT.json` 记录独立回读后的实例覆盖、世界包围盒和源哈希；不复制原各零件的专用 STEP_topology 扩展，不提供 BRep/制造图意义上的整机实体。

Three.js r161 的源文件从本机已安装 CAD Viewer source map 中原样恢复；无新软件安装或网络依赖。见 `vendor/THIRD_PARTY_NOTICE.txt` 与 `vendor/three/LICENSE.txt`。

该页面是数字设计审阅工具。三态展示、缓存绑定和显示比例检查均不赋予连续动作、全机碰撞、实物装配或飞行制造放行结论。
