# 外部开源参考使用政策

## 1. 基本原则

OreSat、BIRDS、PyCubed、SpaceRobotEnv、SPOT 和 LibreCube Notes 均为外部参考。它们可以帮助本项目建立工程边界、接口语言和报告论据，但不能直接替代本项目原创设计。

本项目必须建立自己的 `servicer_12U_v0`、目标模型和机械臂安装适配器。任何外部 CAD 或几何文件如被查看、导入或改造，都必须在文档和竞赛报告中保留 attribution。

## 2. 各源使用边界

| source | allowed_use | forbidden_use | attribution |
|---|---|---|---|
| OreSat | 6U/12U 结构、frame、card stack、solar、backplane、ADCS、camera、antenna 的机械参考 | 直接把 OreSat CAD 改名为本项目服务星；声称为原创结构 | 必须标注 OreSat/PSAS 和对应仓库。 |
| BIRDSX-CAD | 2U 小卫星结构和目标星外观参考 | 把 BIRDS 2U 结构当成本项目服务星或目标星原创 CAD | 必须标注 BIRDS Project/Kyushu Institute of Technology。 |
| PyCubed | OBC/EPS/battery board 占位、板卡尺度和开放硬件流程参考 | 复制电路设计并称为自研 avionics；在 Stage 1 深挖软件 | 必须标注 PyCubed 和 CC BY-SA hardware 说明。 |
| SpaceRobotEnv | 自由漂浮空间机器人任务背景、基座扰动和视觉网格参考 | 运行环境；替代 `reBot-DevArm_fixend.urdf`；声称本项目使用其仿真结果 | 必须标注 SpaceRobotEnv 和 Apache 2.0 许可证。 |
| SPOT | 地面低摩擦试验台、气浮平台、motion capture 和实验组织参考 | 运行 Simulink/MATLAB 项目；声称本项目已完成 SPOT 级实验 | 需标注 SPOT 来源。 |
| LibreCube Notes | 模块化接口思想备注 | 当前阶段作为设计依据深挖 | 若使用需标注 LibreCube。 |

## 3. 原创贡献位置

本项目原创贡献应集中在：

- 面向未来飞行器大赛的系统布局。
- 12U 展示型服务星 `servicer_12U_v0` 的任务舱、平台舱、推进通信舱划分。
- reBot 等效空间机械臂安装、坐标系、转接座和 keepout 体积定义。
- 质量、质心、惯量接口预算，以及可写入 Stage 2 free-flyer/Pinocchio 模型的参数链路。
- GJM/RNS 反作用抑制对比图设计。
- VLA 高层任务决策闭环，且不直接输出关节力矩。
- reBot 地面样机验证与实物演示视频流程。

## 4. 报告写法要求

- 使用外部资产时，写“参考 OreSat/BIRDS/PyCubed 的结构/板卡/目标外观思路”，不要写“采用某外部模型作为本项目设计”。
- 若某图来自外部模型导入截图，应在图注标明来源和改造程度。
- 对外部资产的 license 和 README 状态进行说明；OreSat Structure 本地仓库 README 已声明该 SolidWorks 仓库 deprecated。
- 所有外部资产不得进入“本项目原创成果”表，只能进入“开源参考与工程约束来源”表。

## 5. Stage 1-C 前置门槛

- 明确 `servicer_12U_v0` 是重新建模，而不是 OreSat 复制件。
- 明确 Target-1/2/3 是本项目任务目标模型，而不是 BIRDS/OreSat 直接改名。
- 明确 reBot 机械臂使用本项目指定 URDF 链路，SpaceRobotEnv 只作背景参考。
- 明确 SPOT 不运行，只作地面验证方法参考。
