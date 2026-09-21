# A3 方法、姿态与数值证据只读审计

审计日期：2026-09-05。审计对象为 `mode_a_native_design_r1` 内 A3.1、A3.2、A3.2b/c/d、A3.3、A3.4 的既存脚本、JSON、CSV，以及 accepted URDF 和其 10 份 STL。原始文件、原始 Gate 和 CURRENT 指针未修改。没有运行原生产脚本、优化、碰撞生产查询、CAD GUI、FEA 或动力学。

**结论：既存姿态的全局包络数字可靠；局部切片、空间成本、安装位置继承及部分结论文本存在实质缺陷。A3.2d 的 `0/16` 保持为有限搜索负结果，现有证据没有交付完整服务星的可用收拢构型，也没有证明所有合法姿态全局不可行。**

独立复算脚本直接解析 accepted URDF，并读取原始二进制 STL 的所有唯一顶点；使用保存的关节姿态和安装旋转计算刚体变换和 AABB。未调用原脚本函数、凸包算法或优化器。A3.2c 的 12 条现存结果与 A3.2d 的 16 条结果合计 28 条，尺寸最大差 **2.8422×10⁻¹³ mm**，箱内/箱外判别 **0 项不一致**。这仅证明保存姿态的数字可复算，不代表装配验证或碰撞验证通过。

## 1. 可保留的证据及准确口径

| 证据 | 只读复核结果 | 允许使用的结论 |
|---|---|---|
| accepted URDF 与 10 份 STL | URDF 与 A3 登记哈希相同；10 份 STL 与 A3.43 组件表哈希全部相同；脚本硬编码父子关系、origin、axis、出现的 limit 与 XML 数字相同 | 当前 A3 数值确实使用既有 B601 模型的几何和运动学；不是新原生整星验证 |
| 模型组件与质量 | `base_link + link1..6 + gripper_link + 2 fingers` 共 10 个刚体；XML 质量和为 **4.695555949342986 kg** | 是臂与夹爪的设计模型质量，不是整星质量或实物称重 |
| A3.2c / A3.3 主候选 `CAND_2_FIT`，links1–6 | X/Y/Z = **353.553262 / 80.310636 / 205.065022 mm**；中心放置横向最小余量 **10.617489 mm**，端面 **6.223369 mm** | 该子集、该姿态、自由安装参考下的矩形包络事实 |
| A3.4 主候选加入基座与夹爪 | X/Y/Z = **388.833361 / 283.300553 / 261.381773 mm** | 相同关节角及旋转下，完整臂模型超过名义参考箱；尚未包含 M3R/HDRM/鞍座/线束等 |
| A3.4 居中后的超出量 | X 每侧 **11.416680 mm**；Y 每侧 **28.500277 mm**；Z 每侧 **17.540886 mm** | A3.42 `LATERAL_ENVELOPE=FAIL`、`END_ZONE=FAIL`、`GENERIC_PRISMATIC_EJECTION=FAIL` 的尺寸依据成立 |
| A3.2d 16 个保存结果 | **0/16 inside_box**；最佳 0° 请求余量案例最大每侧超出 **7.991756641 mm**；≥2° 的最佳案例 **8.635077035 mm** | 已执行的搜索条件下，完整臂模型未找到名义参考箱内候选；不构成全局不可行定理 |
| A3.2d 新姿态中的 links1–6 厚度 | **90.819189–113.943070 mm** | 旧候选约 80.3 mm 厚度不能移植到新完整臂姿态 |

数据详见 [独立数值摘要](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_numeric_recheck.json>)、[28 条姿态 AABB 复核](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_saved_pose_aabb_recheck.csv>)、[运动学常量核对](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_hardcoded_kinematics_recheck.csv>)。

## 2. 方法与数据发现

### A3-M01：A3.4 的 229 个 station 是凸包顶点分箱，不能作为连续截面

`a3_04_fullarm_station_attribution.py` 第 94 行只保存各 STL 凸包顶点，第 196–201 行按 `floor(X)` 的 1 mm 区间筛选顶点；没有顶点就跳过。没有三角形面与切平面相交，亦没有体与薄层相交。

完整 X 范围为 `[-194.416680, +194.416680] mm`，按脚本分箱定义应有 **390 个区间**（左端从 −195 到 +194），实际只写 **229 行**，有 **161 个分箱未写出**。`spacing_mm=1` 是分箱宽度，不是几何截面完整采样的证明。三角形可以跨过未包含任何顶点的分箱，因此不能把缺行解释为空间空闲。

同一缺陷也存在于 A3.3 station 明细（`a3_03b_station_rail_ejection.py` 第 96–102 行）。这些 CSV 可保留为“凸包顶点所在 X 分箱的坐标诊断”，不能直接消费成母线截面函数、局部空腔 CAD 或航电可用空间。

### A3-M02：局部 width 不能推翻固定坐标全局越界

把 A3.41 已有的 229 行按同一坐标系内 `Y/Z_min >= −113.15`、`Y/Z_max <= +113.15 mm` 检查，**Y 绝对坐标越界 22 行、Z 越界 63 行、任一方向越界合计 85 行**；其中仅 3 行 `width_Y>226.3`，0 行 `width_Z>226.3`。由于存在未覆盖分箱，85 也不是连续几何违规区间的完整计数。

精确 AABB 对某个固定姿态的矩形外包络包含性是充分必要条件；不同极值不在同一 X 站，并不消除任何一个方向的实际极值。A3.4 的“仅 3/229，Z 没有超宽”“全局 AABB 过于保守”仅可用于区分空腔形状，不得解释为固定参考箱只需修三个局部点。

另有文本生成错误：A3.4 `headline` 的“5 mm axial band”来自 `prows[-1]` 的最后一个口袋，而唯一 `exceeds_226p3=True` 的 **POCKET_11 是 [−65,−52]，记录区间宽 14 mm**；5 mm 并非对应超宽区。两者仍都来自不完整顶点分箱，不能作真实违规区连续长度。

逐行复核见 [station 绝对坐标附表](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_station_absolute_coordinate_recheck.csv>)。原始裁决未修改，方法性解读已在本报告纠正。

### A3-M03：加入组件时重新居中，改变了实际安装平移

A3.3 使用 `p = R_mount·FK(q)·p_local − center(links1–6) + translation`；主候选 `translation=[0,0,0]`。A3.4 的 `place_full` 对传入组件集重新算包围盒中心；FULL 调用没有消费 handoff 中的安装平移，得到 `p = R_mount·FK(q)·p_local − center(FULL)`。

因此主候选基座原点从 A3.3 的 **[−142.124009, −0.430287, −65.121566] mm**，变为 A3.4 的 **[−124.483960, −41.638819, −36.963191] mm**；整组几何隐含平移了 **[+17.640049, −41.208532, +28.158375] mm**。关节角和安装旋转相同，不等于安装位置相同。

重新居中不影响尺寸跨度和超箱负结果，但改变 station 绝对坐标、各面余量以及根部接口位置。A3.4 重检可理解为该姿态下完整臂自由居中的诊断，不能叫作沿用 A3.3 安装变换的集成检验。

此外，[frame_tree_v1.yaml](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/config/geometry/frame_tree_v1.yaml:12>) 的名义 `T_SM=[185.25,0,0] mm + Ry(90°)` 并不是上述自由安装解。A3.3 `T_S_RCDS` 自身为 `PROVISIONAL_BUT_EXPLICIT`。必须先把安装变换绑定至真实基座、两级转接件及母线承载界面，才有条件谈集成与验证继承。

### A3-M04：三组体积代表不同对象；3.33 倍不是净空间收益

| 量 | 可复算定义 | 结果 |
|---|---|---:|
| links1–6 原始尺寸 AABB | `353.553262×80.310636×205.065022 /1000` | **5822.634117 cm³** |
| 贴文中的四舍五入尺寸乘积 | `353.6×80.3×205.1 /1000` | **5823.625808 cm³** |
| A3.4 `ARM_CORRIDOR` 基准 | `80.3×226.3×(194−(−195))/1000` | **7068.865210 cm³** |
| 口袋增量 | `Σ(extra_Y×226.3×口袋区间宽)/1000` | **1569.383173 cm³** |
| 脚本 piecewise 指标 | 上两项之和 | **8638.248383 cm³** |
| 脚本 monolithic 指标 | `283.300553×261.381773×389 /1000` | **28805.294702 cm³** |
| 完整臂真正全局 AABB 体积 | `388.833361×283.300553×261.381773 /1000` | **28792.955120 cm³** |

7068.9 采用名义 **226.3 mm** 横向尺寸和 **389 mm 分箱端点距离**，与 links1–6 的实际 **205.065 mm** 和 **353.553 mm** 不同；并且 389 不等于真实长度 388.833361，也不等于 390 个 1 mm 区间的覆盖长度。

原脚本采用“基准通廊 + 口袋超额”，没有直接把 ROOT、DISTAL、CORRIDOR 三段体积机械相加，因此不能简单断言已经发生了三段体积重复相加。但它也没有计算具有绝对位置的几何并集：口袋依据稀疏顶点 width 分组，Z 被统一替换成 226.3 mm，Y/Z 绝对偏置未定义，三段区间也重叠。ROOT/DISTAL、ROOT/CORRIDOR、DISTAL/CORRIDOR 的 X 区间交集分别为 **39.500298、105.227844、77.147459 mm**。分区各自的占用范围又是对该 X 区间内**全部组件顶点**求范围，不能当作独立组件体积。

**8638.2 cm³ 与 3.3346 倍可以保留为旧脚本指标的算术复现，不能作为真实空腔并集体积、净航电舱体积或已经验证的空间节省倍数。**

### A3-M05：146 mm 是两侧残余宽度之和

主候选 links1–6 的 Y 向厚度为 80.310636 mm，居中时两侧各剩 **72.994682 mm**，总计 145.989364 mm。四舍五入即 73+73 mm。不存在一块已证明连续的 146 mm 单侧设备舱；母线梁、板、转接件、保持机构、线束、热控和装配余量均未扣除。移到一侧必须重新绑定真实安装界面与完整组件几何。

### A3-M06：A3.3 handoff 混入另一候选的余量，脚本与保存成果也不完全对应

`A3_36_A3_4_HANDOFF.json` 的 `selected_candidate=CAND_2_FIT`，但其 `ejection_min_clearance_mm=23.939679398434805` 与 `A3_3_FINAL_GATE.json` 中 **CAND_5_THIN** 的值完全相同；CAND_2_FIT 的对应正确字段是 **10.61748893274273 mm**。同一 handoff 后增的 `face_YZ_min_clearance_mm` 与 `overall_min_clearance_mm` 为 10.617489/6.223369，说明文件内部口径不一致。

保存的 A3.3 Gate/ranking 已加入 `overall=min(rail,face,end)`、优选 CAND_2_FIT 等修订；现存 `a3_03b_station_rail_ejection.py` 第 196–208 行仍按旧排序键，第 247 行仍令 `best=ranked[0]`，且 emitter 不输出那些后增字段。A3.2c 脚本设计 16 组合而实际主 JSON 仅 12 条（FULLARM 没有 3°/5°记录）；A3.4 是对另五个 corridor 姿态添加完整臂的确定性评估，不是补完相同 FULLARM 优化目标。

在已审计 A3 目录内，没有找到发射 `A3_2D_SUBSET_DIAGNOSTIC.json`、`A3_2D_FINAL_GATE.json` 的源脚本。因此已保存姿态和 AABB 可以独立复算，但**不能声称该目录现存脚本能逐字重建全部最后发布 JSON/CSV**。这是版本/生成追踪缺口，不是修改历史文件的理由。

### A3-M07：0° 请求余量不等于六轴压在硬止挡

从 accepted URDF 限位与保存的 CAND_0_THIN q 计算六轴到最近硬限位的角距离：

| J1 | J2 | J3 | J4 | J5 | J6 |
|---:|---:|---:|---:|---:|---:|
| 160.427957° | 0.054965° | 0.000758° | 0.063016° | 0.103754° | 179.903231° |

没有任何一轴在 **1×10⁻⁴°** 内与数学硬限位相等；J2–J5 的裕量很小，J3 尤其接近，但 J1/J6 明显没有在硬止挡。A3.3 Gate 第 249 行及 handoff 第 60 行“all six joints rest on their hard stops”与逐轴数据冲突。是否满足真实保持/限位安全裕量还需机构和误差模型，不能由优化参数名决定。

A3.2d 的最佳 0° 请求余量 FIT_FULL 案例实际最小裕量也为 **0.272388°**，不等于 0°。完整逐轴账见 [关节余量复核](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_joint_margin_recheck.csv>)。

### A3-M08：0/16 与去共位惩罚不提供全局不可行证明

A3.2d 为 4 个余量 × 2 个目标 × 2 个去共位开关，共 16 个保存胜出案例。每例从两组 seed 的有限采样与 Nelder–Mead 局部寻优中选择结果；`nseed=320`、`npolish=8`、`maxit=2500`。`seed_spread=0` 也不证明全姿态空间已穷尽：两组 seed 共用大量确定性初始姿态，且没有搜索空间覆盖/全局界或收敛证书。

去共位只是 `0.05×overlap` 的软惩罚，没有强制零重叠。保存结果的 X 轴根部/末端区间重叠范围 **77.075595–82.842909 mm**，仅证明该惩罚及已执行搜索未给出期望收益。A3.2d Gate 中 `REFUTED` 和“重叠是结构必然”的文字应在引用时限制为“当前已测试策略未成功”；不能由两根连杆长度推出所有合法构型的必然重叠。

`sorted_LWH` 是排序后的跨度。只要安装旋转自由，排序可用于箱体尺寸搜索；但与固定 spacecraft X/Y/Z、去共位的 X 轴、通廊厚度所属轴及 M3R 接口绑定时，必须使用保存的 `full_extents_XYZ_mm` 和完整变换，不能把排序后的三个数直接标成固有安装轴。

### A3-M09：2° 最佳值、子集结果与“最小修改”存在口径限制

`A3_2D_RESULTS.json` 中 2°、FIT_FULL、`decolocate=true` 的跨度为 **383.270118 / 243.570154 / 243.570101 mm**，最差每侧超出 **8.635077 mm**。Gate 的 `best_with_2deg_margin` 正确保存了该数，但 `headline` 和子集 FULL reference 使用 **8.674003 mm**，这是另一个 `decolocate=false` 案例。两者都失败，但不能混称为同一个最优结果。

子集诊断 `BASE+LINKS16` 在 0°请求余量时箱内（−1.799910 mm），2°时仍超出 **+2.806824 mm**。`LINKS16+GRIPPER` 的 2°箱内结果是另一个关节姿态。8 条子集结果全部缺少 `mount_rotvec`，且上述生成脚本缺席，不能独立重建完整安装变换或把子集拼成同一装配解。

因此“拆下夹爪，剩下保留 2°余量就能装入”“这一定是最小修改”均未获证明。拆下物及其收纳、接口、保持与释放机构必须仍计入整星。A3.2d `FULL` 也只是完整臂模型，不是完整服务星。

### A3-M10：连续弹出归约、点到导轨距离与窄相碰撞必须分开

沿固定轴纯平移、障碍截面沿轴不变、刚体形状不变时，使用完整几何在横截面的投影检查棱柱通道，其归约原理成立。A3.3 `A3_32_EJECTION_TRACE.csv` 的每个 travel 行由同一个预先计算的数值重复填入，**不是逐位姿调用碰撞器的轨迹记录**；门区与推板为名义平面代理，母线本体、保持释放机构、太阳翼等不在模型中。

`rail_clear` 实际只评估凸包顶点到四角区域的距离，并不构造投影多边形与导轨的相交关系。面/边的最短距离可能小于顶点距离；所有顶点避开四角也不一般保证三角形/凸面不穿过角区。因此其正距离不是已验证窄相净间隙。

不过 A3.3 的薄臂子集可以保留更保守的条件几何解释：主候选整体位于 `|Y| <= 40.155318 mm`，而脚本角轨 Y 内缘为 `104.65 mm`，故按该代理模型，仅 Y 就提供 **64.494682 mm** 的分离下界。此论据不依赖稀疏 station，也不等同于脚本声称的精确 rail 距离 65.524808 mm。其他薄通廊候选同样有全局 Y 窄带。它不能外推到宽大的 FULL 模型或真实部署器。

A3.2c 的 Frank–Wolfe `fw_distance` 仅对 links1–6 的非相邻凸包对，最多 250 次迭代，没有保存收敛 gap 或认证下界；返回的迭代距离不是一般可用于认证分离的下界。凸包重叠也不能直接判实际非凸网格碰撞。其最终 `NOT_VALIDATED_HULL_LEVEL_ONLY` 保持合理。

A3.4 后端探测曾记录 VTK 等模块，但 `narrow = any(...)` 的白名单排除 VTK/PyVista/OCP。所以 `NOT_VALIDATED_NO_NARROW_PHASE_BACKEND` 至多表达该脚本没有验证它所列的后端路径，不能作为“本机没有可用窄相实现”的结论。本轮没有新跑生产碰撞；能力与验证状态以总审计对应软件能力章节为准。

## 3. A3.4 八项缺失应怎样解释

A3.43 的八项是源脚本第 114–128 行硬编码追加的：M3R_STAGE_A_RING、M3R_STAGE_B_DIFFUSION、HDRM_ROOT、HDRM_DISTAL、STOW_SADDLE_A、STOW_SADDLE_B、HARNESS_TRUNK、CONNECTOR_SET。它们未被 A3 载入，`mass=null`、`included_in_fullarm=false`。

这里没有仓库资产发现流程；源注释已分别出现“本包无 B-rep”“未选型”“仅占位”“没有收拢 CAD”等不同状态。**`MISSING_GEOMETRY_HOLD` 的可复核事实是“该八项不在本次 A3 几何消费者集合中”，不是“项目此前从未设计”。** 本报告将其转交资产/集成矩阵，不能由 A3 表自行裁定历史实体是否存在。母线、航电、太阳翼等更没有因未列进该八项而自动成为已验证组件。

## 4. 继承边界与本轮停点

| 资产或结果 | 后续可保留 | 需要针对新构型重新验证 |
|---|---|---|
| accepted URDF、STL、运动学/限位及臂质量参数 | 有哈希绑定的源资产；参数化方法 | 实物质量、真实关节/夹爪状态、安装界面与新构型质量/惯量 |
| 已保存 q、mount_rotvec、AABB | 同一组件集和变换下的可复算几何诊断；有限搜索负结果 | 真实安装平移、总装引用、固定轴映射、组件覆盖、碰撞和展开路径 |
| 80.3 mm 薄通廊 | 历史 links1–6 候选 | 完整臂和整星布局不得直接继承该数 |
| station、pocket、volume 指标 | 原脚本诊断与历史证据 | 完整截面覆盖、绝对坐标空腔、真实并集、制造/装配余量、航电可用空间 |
| A3.3 generic 参考 PASS | 保留原 Gate 与 arm-only 限定 | 不继承为部署器兼容、发射合规、完整臂或整星 PASS |
| A3.2d HOLD | 保留 0/16 搜索负结果 | 不继承成数学不可行、路线切换批准或 Mode B 可行 |

本审计不启动下一轮优化，不选择新路线，不发射新机械 Gate。优先补的是生成追踪、同一变换/组件集合、真实接口与窄相验证合同；实施行为仍受后续明确授权约束。

## 5. 复现与源文件定位

独立审计复算命令（仅写当前审计目录）：

```powershell
python 'F:\China Graduate Future Flight Vehicle Innovation Competition\01_project\competition\PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905\a3_readonly_recheck.py'
```

审计脚本见 [a3_readonly_recheck.py](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_readonly_recheck.py>)；逐个实际读取源文件清单见 [a3_sources.txt](<F:/China Graduate Future Flight Vehicle Innovation Competition/01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905/a3_sources.txt>)，用于总审计哈希封存。该清单包括全部 A3 文本证据、URDF、10 STL 和 frame_tree，不含原生产执行。

| 定位 | 精确源文件与起始行 |
|---|---|
| A3.1 权威与登记 | [a3_01_input_authority.py:121](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_01_input_authority.py:121>)；[A3_00_INPUT_AUTHORITY.json:7](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/00_authority/A3_00_INPUT_AUTHORITY.json:7>) |
| A3.2/2b 旧参考箱 | [a3_02_robust_stow.py:26](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_02_robust_stow.py:26>)；[a3_02b_corridor_in_box.py:31](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_02b_corridor_in_box.py:31>) |
| 参考箱、有限凸包距离与多 seed | [a3_02c_envelope_authority_correction.py:41](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_02c_envelope_authority_correction.py:41>)；同文件第 109、174、211 行 |
| A3.3 居中与位移 | [a3_03_deployer_zone_and_ejection.py:248](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_03_deployer_zone_and_ejection.py:248>) |
| station、rail 与重复 trace | [a3_03b_station_rail_ejection.py:71](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_03b_station_rail_ejection.py:71>)；同文件第 96、127、162、196、247 行 |
| 主候选混入余量与硬止挡说法 | [A3_36_A3_4_HANDOFF.json:38](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/02_a3_3/A3_36_A3_4_HANDOFF.json:38>)；同文件第 60 行；[A3_3_FINAL_GATE.json:249](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/02_a3_3/A3_3_FINAL_GATE.json:249>) |
| 全臂重新居中、八项追加、顶点分箱 | [a3_04_fullarm_station_attribution.py:94](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_04_fullarm_station_attribution.py:94>)；同文件第 114、139、148、190、196、200 行 |
| zone、volume、后端白名单与 headline | [a3_04b_zones_pockets_gate.py:81](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_04b_zones_pockets_gate.py:81>)；同文件第 103、113、129、143、207、249 行 |
| A3.4 输出 | [A3_42_FULL_SYSTEM_CDS_RECHECK.json:5](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/03_a3_4/A3_42_FULL_SYSTEM_CDS_RECHECK.json:5>)；[A3_4_FINAL_GATE.json:5](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/03_a3_4/A3_4_FINAL_GATE.json:5>)；[A3_46_LOCAL_POCKET_REQUIREMENTS.csv:12](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/03_a3_4/A3_46_LOCAL_POCKET_REQUIREMENTS.csv:12>) |
| A3.2d 有限优化、软惩罚与结果 | [a3_02d_fullsystem_reopt.py:98](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/99_tools/a3_02d_fullsystem_reopt.py:98>)；同文件第 114、125、142、155 行；[A3_2D_RESULTS.json:261](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/04_a3_2d/A3_2D_RESULTS.json:261>) |
| 子集与推断限制 | [A3_2D_SUBSET_DIAGNOSTIC.json:28](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/04_a3_2d/A3_2D_SUBSET_DIAGNOSTIC.json:28>)；[A3_2D_FINAL_GATE.json:13](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1/04_a3_2d/A3_2D_FINAL_GATE.json:13>) |

旧 A3.2/2b 的 340.5 mm 已被 A3.2c 的本次 366.0 mm 参考配置替代；本审计记录其替代关系，不重新验证外部部署器规范，也不把 6.5 mm 外突值扩展为六面统一允许量。
