# Space Embodied Robot CAD Geometry Prototype v0.1

> `STATUS: GEOMETRY_ONLY`  
> `PROFILE: COMPETITION_DISPLAY_V0`  
> `CLAIM_LIMIT: NON_FLIGHT_COMPETITION_DISPLAY`  
> `NO_DYNAMICS_USE: true`  
> `TARGET_INCLUDED: false`

## 使用入口

在 SOLIDWORKS 2024 SP5 中打开：

- `Assembly/12U_Master_Skeleton.SLDASM`

该总装由四个一级对象组成：

1. 隐藏的 `SER_Master_Skeleton.SLDPRT`
2. 参数化 12U 显示舱体
3. 参数化 B601 安装适配器
4. B601 10-link/9-joint 几何参考装配

## 本包回答什么

本包把上一阶段 Digital Mechanical Host 合同落成可打开、可编辑、可追溯的原生 SolidWorks 几何样机。它用于几何布局、接口表达和后续人工设计评审。

它不回答结构强度、发射合规、质量质心、惯量、动力学性能、机械臂可达性、抓取可行性或碰撞安全问题。

## 参数化方式

关键几何由 SolidWorks 原生命名尺寸驱动，并辅以文件自定义属性：

- 舱体：`BUS_WIDTH`、`BUS_HEIGHT`、`BUS_HALF_LENGTH_POS/NEG`
- 嵌入凹槽：`ADAPTER_RECESS_Y/Z/DEPTH`
- 航天器法兰：`SERVICER_FLANGE_Y/Z/DEPTH`
- 适配器：`ADAPTER_PLATE_X/Y/THICKNESS`
- 中心凸台：`ADAPTER_BOSS_DIAMETER/HEIGHT`
- B601 包络代理：每个 link 的 `BBOX_X/Y/Z`

本轮没有使用 SolidWorks Equation Manager 的 Global Variables；自动化接口在当前安装上未返回有效变量索引。因此，可编辑性由命名尺寸承担，不能把本包描述为“方程表驱动”的最终工程模型。

## 坐标与装配

- `S`：12U 显示包络几何中心
- `M`：B601 安装面参考
- `A0`：B601 插入参考；本阶段与 `M` 同位
- `T_SM = [185.25, 0, 0] mm + R_y(+90°)`
- `T_SB`：未知且禁用
- physical TCP：未知且禁用

嵌入式堆叠 v0.1：

- 舱体主包络：`x_S = -170.25 ... +170.25 mm`
- 适配器板：`x_S = +158.25 ... +170.25 mm`
- 法兰环与适配器 boss：`x_S = +170.25 ... +185.25 mm`
- B601 几何参考从 `A0=M` 向任务侧展开

这是一项 A3 几何设计决定，不是飞行接口签核。

## Service Bus 表示边界

`01_Service_Bus.SLDPRT` 当前包含主体包络和独立的参考法兰环两个实体，用于表达任务面与适配器堆叠。它不是结构载荷路径模型，不得用于强度、连接刚度、质量或惯量推断。

## B601 表示边界

未复制、未导入供应商 STEP。`03_B601_Interface/links/` 中的零件是从仓库既有 STL 读取最小/最大坐标后建立的原生长方体包络代理：

- 保留 accepted URDF 的 link/joint 名称和 q=0 拓扑
- 适合装配层级、朝向和保守包络审查
- 不等于供应商精确表面
- 不得用于制造、质量属性、关节间隙或接触计算

## 材料与质量警告

SolidWorks 文档模板可能显示默认材料。该模板材料不是本阶段批准的物理赋值，所有 CAD 文件均带有 `NO_DYNAMICS_USE=TRUE`。不得从本包读取或发布整机质量、质心、惯量。

## 目录

```text
00_Master_Skeleton/   S/M/A0 与总体包络骨架
01_Service_Bus/       12U 显示舱体、嵌入凹槽、法兰环
02_Robot_Mount/       B601 板/凸台几何与参考草图
03_B601_Interface/    accepted URDF 的包络参考装配
04_Sensor_Module/     仅保留未来入口，本阶段未建模
05_End_Effector/      仅说明虚拟任务 frame 与 TCP 边界
06_Target_Interface/  目标与接触分支明确排除
Assembly/             顶层原生装配体
evidence/             截图、构建日志与原生模型检查
```

## 复现

构建与检查入口：

- `70_tools/solidworks/run_ser_geometry_only_v0_1.ps1`
- `70_tools/solidworks/run_inspect_ser_geometry_only_v0_1.ps1`

构建器只创建本 CAD 包，不生成 URDF、USD、ROS、Isaac、Basilisk、控制器或仿真结果。
