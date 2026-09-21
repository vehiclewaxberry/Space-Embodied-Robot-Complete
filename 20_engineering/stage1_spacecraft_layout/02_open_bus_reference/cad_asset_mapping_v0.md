# CAD / 仿真资产映射 v0

> 文档角色：资产→交付物映射 ｜ 类型：reference / mapping
> 语言：中文；资源角色表见 [外部资产目录](external_onorbit_asset_catalog.md)。英文镜像已于 2026-09-06 归并。
> 版本：v0 ｜ 最后同步：2026-07-08
> 阶段原则：本轮仅新增；映射只给"参考/复用/仅参考"边界，不下载、不建模。

把 `external_onorbit_asset_catalog.md`（66 条）映射到项目自有的 5 个 CAD 交付物与相关仿真/验证环节。**目的：防止团队"看到开源模型就直接拿来用"。** 每条注明可借鉴（看思想）/可复用（可导入改造，须过许可闸门）/仅参考（不复制）。

许可等级引用 `license_gate_v0.md`：A=可用池，B=仅研究，C=隔离，D=待确认。

## 1. `servicer_6U_v0` / `servicer_12U_v0`（服务星结构）
| 资产 | 许可 | 用法 |
|---|---|---|
| OreSat（已有主参考） | — | 可借鉴：6U/12U 结构分层、板卡堆叠、结构接口 |
| UPSat 结构 | A- | 可借鉴：全开源在轨整星结构组织方式 |
| OSSAT/KISPE | A- | 可借鉴：**质量量级最贴近**（微卫星级）的总线布局 |
| bac-hardware | A- | 可借鉴：面板 + 机-电互连（bacBus）接口标准 |
> ⚠️ 无 300–500kg 级服务星整星制造 CAD（见风险 RA-001）。整星几何**须自研**，开源仅作子系统级堆叠/接口参考。

## 2. 服务星动力学 / GNC（喂 Basilisk / 自由飞行）
| 资产 | 许可 | 用法 |
|---|---|---|
| Basilisk | A | 可复用：整星姿轨动力学 + GNC 主仿真基座（显式设质量/惯量/质心） |
| NASA Astrobee | A | 可借鉴：自由飞行基座 RPO + 基座-臂协同软件架构 |
| 42 | A- | 可复用：多星相对动力学 + 星间接触力 |
| MuSCAT | A | 可借鉴：整星子系统预算 / trade study |

## 3. `target_satellite_v0`（失效卫星目标 Target-1）
| 资产 | 许可 | 用法 |
|---|---|---|
| NASA 3D（Agena 等） | A- | 可复用：Agena 圆柱对接目标 + 卫星几何（逐模型核对） |
| ESA SCIFLEET | A- | 可复用：大型卫星高保真几何（逐模型核对） |
| SwissCube（逐部件 CAD） | A | 可复用：立方星几何参考 |
| SATLLA（STL） | C | 隔离：可下载结构 STL（GPL，避免污染交付） |
> 惯量处理：**几何可导入，惯量须自定义**，禁止把"有几何"当"有实测惯量"（见风险 RA-003）。

## 4. `target_debris_v0`（圆柱碎片/上面级 Target-2）
| 资产 | 许可 | 用法 |
|---|---|---|
| 42 | A- | 可复用：翻滚刚体 + 接触动力学（自定义惯量/角速度） |
| SmallSatSim | A | 可复用：MuJoCo 接触/RPO 测试框架 |
| MMT/RoBo6/LCDC | A | 可借鉴：上面级**真实翻滚率**标定角速度量级 |
| space_robot（清华） | **D** | **仅线索**：可加载的翻滚目标 URDF，但无 LICENSE，不复用，须先授权 |

## 5. `robot_mount_adapter_v0` / reBot 机械臂
| 资产 | 许可 | 用法 |
|---|---|---|
| SPART | A-（LGPL） | 可复用：URDF→GJM/RNS 动力学（reBot 主工具） |
| SpaceDyn | **B** | **仅研究**：GJM/RNS 理论交叉验证（禁商用，不进交付） |
| OpenManipulator-X | A | 可借鉴：臂 + 夹爪 CAD/URDF 工程组织 |
| Space ROS Canadarm2 | A | 可借鉴：飞行级抓捕臂运动学/末端几何 |
> 转接座本体**自研**；机械臂基座系 `B` 必须与 `reBot-DevArm_fixend.urdf` 一致（见 `coordinate_frame_definition_v0.md`）。

## 6. cooperative_interface（合作接口 Target-3）
| 资产 | 许可 | 用法 |
|---|---|---|
| IDSS | A（ICD） | 可借鉴：软捕获环/对接接口权威几何与载荷基准 |
| AstraTag | A | 可复用：在轨专用合作靶标 |
| AprilTag / AprilCube | A | 可复用：标记检测 + 可打印立体靶 CAD |
| OpenCV ArUco/ChArUco | A | 可复用：标记生成/检测/位姿 |
> ⚠️ 无制造级软捕获/对接环 CAD（见风险 RA-002）；对接环用 IDSS 做接口包络 + 自建占位体。

## 7. 工作空间 / 视觉 / 避让（05 目录 + 感知）
| 资产 | 许可 | 用法 |
|---|---|---|
| SPEED / SPEED-UE-Cube / URSO | A | 可复用：非合作位姿数据集（优先许可宽松者） |
| SPEED+ / SHIRT | **B** | **仅研究**：域适应 / 翻滚接近段（不进交付） |
| SPIN | **C** | 隔离：按 reBot 构型定制生成数据（GPL，独立运行） |

## 8. 地面样机 / 气浮验证（reBot + SPOT 补充）
| 资产 | 许可 | 用法 |
|---|---|---|
| ATMOS/DISCOWER 飞控代码 (PX4) | A | 可复用：气浮台飞控蓝本（BSD-3） |
| ATMOS/DISCOWER 气浮台 CAD (w3_atmos) | **C** | 隔离：气浮台机械 CAD 为 GPL-3.0，仅参考思想、**不复用不并入交付**（2026-07-09 逐仓核验由 A- 下调） |
| bsk-ros2-bridge | A | 可复用：Basilisk↔气浮台 HIL 桥 |
| SmallSatSim | A | 可复用：MuJoCo 接触仿真 |
| The Slider | **D** | **仅线索**：完整 2D 气浮台 CAD，无 LICENSE 须确认 |
| OSF 球面气浮台 | C | 隔离：三轴姿态台 CAD（GPL） |
| open-air-bearings / reaction_wheel | A | 可复用：气浮轴承 / 反作用轮子件 |

---

## 使用总原则

1. **几何来源、质量来源、惯量来源、坐标系、可信度、许可状态**六者必须分开记录（进入 `simulation_input_matrix`，见 stage2 输入需求）。
2. "有几何模型" ≠ "有真实质量惯量"；估算值不得写成实测。
3. 任何资产进入 CAD/交付前，回 `license_gate_v0.md` 确认闸门等级；**D 类不得复制**。
4. 真实缺口（无整星 CAD、无对接环 CAD、无实测惯量、无空间级末端）已转为风险，见 `external_asset_gap_risks_v0.md`，不再靠继续盲搜解决。
