# CURRENT R2 缺口与单点汇合关键路径 V4

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH_V3.md`，SHA-256 `EADB50DB624938989BE10BE8FB54E0985875BC75AFE24EC9DD566C40B1EC5A64`。  
更新方式：append-only；Phase0、V2、V3、前三份汇合回执及所有历史 Gate 均未原位改写。

## 第四个实际收敛增量

新增包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_FIXED_PLATFORM_OPERATIONAL_COLLISION_CANDIDATE_V1/`

机器 Gate：

```text
3_OF_3_LOCAL_FIXED_PLATFORM_STEP_CANDIDATES_PASS__
INDEPENDENT_OCP_PASS__NEGATIVE_24_OF_24_47_OF_47__
PYTEST_45_OF_45__CAD_REVIEW_PASS__
SYSTEM_REMAINS_1_OF_150_AND_0_OF_11166__NO_RELEASE_CREDIT
```

本增量关闭 CP-1C 中三个固定平台对象的“本地 STEP-first 几何、frame/单位链、runtime 派生和独立验证”子项：

- `F::LOAD_BRIDGE`：源 STEP 已直接写在根坐标系 `S`，输出保持源文件 24,855 bytes / SHA-256 `545FE62A...221B`，变换次数严格为 0。
- `F::M3R_STAGE_A`：源在 `M3R_LOCAL`，只应用一次完整精度 `T_S_M3R_LOCAL`，输出为 96,941 bytes / SHA-256 `E49CAC62...F386`。
- `F::M3R_STAGE_B`：同样只应用一次 `T_S_M3R_LOCAL`，输出为 120,573 bytes / SHA-256 `48B7BF9B...D173`。
- 三件主 STEP 均在 `S`、单位 mm；分别为一个 valid、closed、positive-volume BRep solid。体积为 `260072.391934165`、`127784.800332951`、`161966.032227670 mm³`。
- 每件均从重开的主 STEP 派生 PLY/NPZ/STL，运行时单位为 m、内部 S-frame transform 为 identity；mm→m 仅执行一次。
- 主 BRep 数值 derate 为每对象 `1e-6 mm`；runtime tessellation derate 为每对象 `0.05 mm`；制造与 as-built 不确定度仍为 `null / MEASUREMENT_PENDING`。
- 21/21 source pins、独立 OCP 3/3、24/24 合同负控与 47/47 变异子例、fresh-process replay、pytest 45/45、14/14 Local Gate 全部通过。
- CAD refs/facts/planes/positioning 以 UTF-8 模式复跑 3/3 通过；首次 GBK 编码故障发生在扫描无关既有脚本、未进入模型解析，已如实记录。三件各自 ISO/FRONT/TOP 共九图已逐图审查。
- CAD Viewer 缺少文档要求的 `agent:start`，已记录为展示工具故障，没有伪装成 Viewer PASS。

## 本地 PASS 没有升级系统 Authority

本包没有修改当前 M01 registry、prebind、pair ledger、父级 Gate 或历史负结果。三个对象仍为 `PENDING_OWNER_AND_SYSTEM_BINDING`：

1. Load Bridge 的物理 fit-up、航天器侧锚点和结构载荷连续性仍为 HOLD。
2. M3R A/B 的 as-built/飞行资格鉴定仍为 HOLD；不得从名义 STEP 反推 L0 质量、COM 或惯量。
3. 三件尚未进入新的 append-only system registry revision，故仍不具备生产 pair eligibility。
4. 接触、强度、制造、生产窄相、SAFE、edge、path、TMG-4/G12、父级、控制和 release 均未获得信用。

## 当前系统状态保持不变

- 已知 active object：150。
- system operational geometry authority：1/150。
- 本地待 Owner/系统绑定候选：link1–link6 六个、gripper 三个、fixed-platform 三个，共 12；本轮 system 新增行为 0。
- per-pair clearance policy：0/11,166。
- 生产 pair query：0/11,166；system SAFE certificate：0；edge：0。
- stage instance：0/3；path search 未授权、未执行。
- TMG-4=`HOLD`，G12=`FAIL`；mechanical/control/joint-system/non-ABORT/next-stage/release 均为 false。

## 更新后的最短关键路径

| 顺序 | 工作包 | V4 状态 | 下一机器完成判据 |
|---|---|---|---|
| CP-1A | base + link1–link6 | base 1 个 system；link 6 个 local candidate | Owner 接受后以新 registry revision 精确绑定；不得改旧 registry |
| CP-1B | gripper 三对象 | 3/3 local candidate，Owner 运动成员与九命名状态仍 HOLD | Owner 明示 24+24 motion membership 与九状态 joint1/joint2 SI 数值 |
| CP-1C1 | fixed-platform 三对象 | **本轮完成，3/3 local candidate** | fit-up/as-built 边界保留；Owner/system 新 revision 后才可计数 |
| CP-1C2 | Route-C 固体 R121 | 设计候选存在，operational 0/121 | 逐对象 STEP/BRep、owning-frame adapter、runtime derate、独立验证；先做可独立失败批次 |
| CP-1C3 | Route-C 线束 C9 | 解析中心线存在，runtime capsule/Hausdorff 0/9 | deterministic capsule chain + 9/9 Hausdorff 上界 + side-effect-free pose adapter |
| CP-1C4 | Solar 6 | FCStd 有双状态 selector，system state/HDRM/latch 未绑定 | 分状态单叶提取；禁止把含 22 solid 的组合 STEP 当单状态 geometry |
| CP-1C5 | BUS 与当前 150 外缺件 | BUS narrowphase 与外突出物缺失；target/support/HDRM 不在 150 | 先签发对象/接口 authority，禁止静默扩充 pair universe |
| CP-2 | PRE_RELEASE / RELEASE_EVENT / POST_RELEASE | 0/3 | 3/3 scene、ACM、HDRM、solar、arm、harness、mount、selector 全绑定 |
| CP-3A | pair-oracle 软件资格 | synthetic-only PASS | 保持软件资格与 production evidence 分离 |
| CP-3B | production backend admission + batch completeness | 未授权 | exact 11,175 行：9 EXEMPT + 11,166 GEOMETRIC；任一 UNKNOWN/FAIL 即 batch abort |
| CP-4 | 连续边 + bounded M01 path | 0 edge / no search | 当前语义的 edge certificate 后才允许 bounded search |
| CP-5 | Route-C TMG-4/G12 重评 | HOLD/FAIL | 新路径与当前几何绑定后重评；V9F `-17.313396996697108 mm` 旧负见证保留 |
| CP-6 | 目标相对 MuJoCo V2 | 隔离并行、未创建 | 自由目标、相对 SE(3)/twist、碰撞/接触关闭、DOP853 对拍；不得绕过 M01 |

## 下一项自主执行增量

下一项最高覆盖率、仍可合法自主推进的内部包为 Route-C operational geometry 批次。建议拆成两个互不继承 PASS 的子批：

1. `R121`：从 V9F 主 STEP 与逐件 mesh manifest 按对象重开、owning-frame 配准并派生 runtime sidecar；必须保留 V9F 任务路径负结果，局部对象几何 PASS 不等于 Route-C 任务 PASS。
2. `C9`：从解析中心线生成 deterministic capsule chains，逐段建立 Hausdorff 上界、线径/数值 derate 和无副作用 pose adapter。

任何一个子批最多只能形成 local operational candidates；Owner scene、生产 pair、edge/path 和 G12 不得随包继承。Solar 双状态提取可作为隔离并行支线，但在 Owner state/latch/HDRM 绑定前不能激活到系统。

内存继续采用 monitor-only 策略；本轮没有修改 legacy memory Gate，也没有把 Owner override 或空闲内存阈值伪装成 `MEMORY_GATE_PASS`。
