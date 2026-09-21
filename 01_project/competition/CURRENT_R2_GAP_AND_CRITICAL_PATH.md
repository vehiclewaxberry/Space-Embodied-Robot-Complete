# CURRENT R2 缺口与单点汇合关键路径

日期：2026-08-28  
范围：12U 服务航天器 + B601 6R/2P 机构 + M01 三段路径 + 目标相对动力学/控制 + 接触后捕获 + SAFE/Sim13 + 具身智能物理否决。

## 当前总裁决

当前项目不是“机械、动力学和控制都没做”，而是已经形成了较强的候选资产与局部证据，但尚未完成系统级运行绑定：

- 机械父 Gate 仍为 `NO_RELEASE_CREDIT`，TMG-4/TMG-6 未闭合。
- M01 当前仍为 150 个对象、11,166 个必查碰撞对、0 个 SAFE 对、0 条连续边证书、0/3 三段实例；系统运行几何仍只登记 1/150。
- R2 dynamics 为 1/6 候选满足，DG1–DG5 保持 HOLD；R2 control 和 13 项系统汇合 Gate 均保持 HOLD。
- MuJoCo V1 的 6/6 是“刚性、自由漂浮、捕获前、无接触”的交叉求解诊断，不是机械、控制、接触或释放授权。
- SAFE-00 与 Sim13 后端分别有局部 PASS，但仍待审查，且不能绕过当前机械、路径、控制和 non-abort 条件。

本轮新增的六个 B601 刚性链节碰撞代理已经通过本地几何 Gate，但它们仍是 `PENDING_OWNER_REVIEW` 候选；M01 的系统计数没有从 1/150 伪升为 7/150。

## 本轮已完成的第一个实际收敛增量

产物入口：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_B601_RIGID_LINK_OPERATIONAL_PROXY_V1/`

机器结论：

- `A::link1` 至 `A::link6` 共六个链节，各生成一个 STEP-first、12 段凸包截面 AABB 保守包络。
- 6/6 本地几何判据 PASS；六份 STEP 共 72/72 个 BRep 实体有效且为正体积。
- 72/72 个 NPZ/STL 分实体网格闭合、定向一致、watertight。
- 独立验证未导入候选 builder；NPZ 对独立凸包分片复算最大误差为 0，STEP 最大包围盒误差约 `1.0442e-10 mm`，STL–NPZ 最大坐标误差约 `7.4506e-09 m`。
- 18/18 单位、frame、hash、计数和 authority 越权负控全部被捕获；pytest 6/6 PASS；builder、独立验证和本地 Gate 均通过确定性回放。
- 六张必需 STEP 快照已生成并目视检查；可见阶梯状轮廓是 12 段保守碰撞包络的预期形式，不是机械臂外观模型。

合法最大主张是：

`6_OF_6_LOCAL_GEOMETRY_CRITERIA_PASS__PENDING_OWNER_REVIEW__TMG4_HOLD__G12_FAIL__NO_SYSTEM_PAIR_OR_PATH_AUTHORITY__NO_RELEASE_CREDIT`

## 单点汇合关键路径

| 顺序 | 工作包 | 当前状态 | 进入条件 | 完成判据 | 不得继承的信用 |
|---|---|---|---|---|---|
| CP-1 | 运行碰撞几何资产提升 | 1/150 系统运行；另有 base + 6 个本地候选 | Owner 审查、单位/frame/hash/selector 绑定 | 每个活动对象都有可重放的 narrowphase 运行表示和独立验证 | 本地几何 PASS 不等于 pair/path PASS |
| CP-2 | M01 三段场景实例化 | 0/3；30 个权威场景值为 0/30 | Owner 提供/签署 PRE、RELEASE_EVENT、POST 值与对象状态 | 三段实例 3/3，事件语义、位姿、几何选择器和 release 状态全绑定 | 设计级固定位姿 3/3 不等于运行场景 PASS |
| CP-3 | 系统 pair oracle 后端 | 合同存在，系统查询 0/11,166 | CP-1 的运行几何；clearance/derate 策略冻结 | SAFE/UNSAFE/UNKNOWN/EXEMPT 语义、hash/state/geometry 绑定、阈值 fail-closed、独立回放与负控 | 后端单元测试不等于真实 11,166 对已评估 |
| CP-4 | M01 连续三段路径搜索 | 未执行；连续边 0 | CP-1–CP-3，Option A 已选择 | 每条边有连续碰撞证书；找到路径或形成可复现实证负结果 | 旧 V9F 直线路径负结果不能外推到所有路径 |
| CP-5 | Route-C 与 TMG-4/G12 重评 | TMG-4 HOLD、G12 FAIL | CP-4 路径、线束/外包络和当前机械状态绑定 | 75 个任务样本中出现符合预注册覆盖要求的 SAFE 区，并由 exact validator 复算 | P01–P13 候选输入 13/13 不等于任务覆盖 PASS |
| CP-6 | 目标相对捕获前动力学与控制 | MuJoCo V1 无独立目标；控制父 Gate HOLD | 独立自由目标、目标相对 SE(3)/twist 状态与单位安全指标合同 | 新 V2 包实现目标相对跟踪、自由漂浮守恒、时间域闭环、独立求解对拍和负控 | MuJoCo V1 6/6 与 Increment V3 PASS 均不得继承为控制 PASS |
| CP-7 | 接触/抓取/捕获后混合系统 | 未实现/测量待定 | 夹爪接触 patch、摩擦/柔顺、执行器、22 kg/150 kg 目标质量惯量 | precontact→contact→attached plant 切换、冲量/能量/动量账本和失效模式闭环 | 20 ms 接触窗、占位帆板与 T4 bounded contract 不得冒充 as-built |
| CP-8 | 全耦合柔性与硬件资格 | 七模态 V3/E23 provisional | 真实太阳翼质量/模态、臂–翼时域耦合、执行器和轮组参数 | 刚化退化、跨求解器、全时域根载荷、硬件不确定度与资格试验闭环 | E23 18/18 不等于全系统硬件有效性 |
| CP-9 | SAFE + Sim13 系统 rebind | SAFE 局部 PASS；Sim13 ABORT_ONLY 后端 20/20 | CP-4–CP-8 的当前树与哈希绑定 | 当前树独立审查、UNKNOWN 永不 ALLOW、non-abort 仅在全部物理 Gate 满足时解锁 | 历史 SAFE PASS/后端负控 PASS 不等于 non-abort 授权 |
| CP-10 | 具身候选 + 独立物理否决 | 规划/合同态 | CP-9；动作、观测、可行域、失败标签冻结 | embodied candidate 与独立 physics veto 双通道；任何 UNKNOWN/UNSAFE 都 fail-closed | RL/VLA 成功率不得替代物理可行域或安全 Gate |
| CP-11 | 比赛与论文证据汇合 | 离线 demo 17/17 | CP-5–CP-10 中可合法交付的实证 | 数字线程、复现命令、负结果、视频/图表、论文 claim 均指向同一机器证据 | 离线 demo ready 不等于飞行/工程 release |

## 现在可并行且不扩大授权的工作

1. `M01_SYSTEM_PAIR_ORACLE_BACKEND_V1`：实现合同级、fail-closed 的 pair oracle 软件后端和负控，但保持真实 pair query 计数为 0，直到几何和场景 authority 完成。
2. `r2_mujoco_target_relative_precontact_v2`：新建隔离包，引入独立自由目标及目标相对状态/指标；不得修改 MuJoCo V1，也不得启用接触、碰撞或硬件信用。
3. 剩余活动对象运行几何台账：优先 B601 gripper/2P、总线外部突出物、太阳翼铰链/HDRM、M3R、目标与目标接口；每个对象均按 STEP/运行网格/单位/frame/hash/独立验证方式单独提升。

## 当前外部输入 HOLD

- M3R 装机测量及不确定度。
- B601 夹爪执行器力/速度/延迟、接触材料、摩擦、压力、目标表面、寿命和实测质量属性。
- Solar R2 的 HDRM、铰链、锁定、展开止挡和资格试验。
- 真实太阳翼质量/模态参数；现有 0.348 kg 和 20 ms 接触窗均为占位/PROVISIONAL。
- 22 kg/150 kg 目标的高置信接口几何、质量、质心和惯量。
- ASM00 的 HAG-A/HAG-B/HAG-I、guide radius、摩擦来源与 clearance 语义。

## 下一机器裁决点

下一次允许改变系统状态的最小裁决不是“再跑一次动画”，而是：

1. Owner 对 base_link 与 link1–link6 的运行碰撞代理作明确接受/拒绝；
2. 若接受，发布新的追加式 M01 registry revision，保持旧 registry 不变，并把系统运行资产计数从 1 精确更新为 7；
3. 同时完成 pair-oracle 后端合同验证，但在三段场景和全部相关几何未绑定前，真实 pair、edge 与 path 仍必须为 0、UNKNOWN/fail-closed。

上述三步完成后，项目才有资格从“局部运行几何候选”进入第一批真实 M01 pair 查询，而不是直接宣称完整机械 CDR、控制闭环或具身抓取完成。
