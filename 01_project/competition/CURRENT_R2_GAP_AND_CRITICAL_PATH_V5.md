# CURRENT R2 缺口与单点汇合关键路径 V5

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH_V4.md`，SHA-256 `34A32BCF15990DBE9170ECB7A6F10576167D3C64FF7D32C456358DDB67BF6C67`。  
更新方式：append-only；Phase0、V2、V3、V4、前四份汇合回执及全部历史 Gate 均未原位改写。

## 第五个实际收敛增量

新增包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R121_OPERATIONAL_COLLISION_CANDIDATE_V1/`

机器 Gate：

```text
LOCAL_R20_CANDIDATE_GATE_PASS__R101_SYSTEM_PAIR_EDGE_PATH_AND_RELEASE_REMAIN_FAIL_CLOSED
```

本增量关闭 Route-C R121 中根部静态 R20 的本地 STEP-first 几何、frame/单位、runtime 派生和独立验证子项：

- R20 精确集合为 12 个 `base_link` 对象和 8 个 `bus` 对象；源几何存储在 `A0=B601 base_link@q0`、mm。
- 每个对象从冻结 V9F FCStd 只读取得已放置 `Shape`；禁止再次应用 FreeCAD `Object.Placement`。
- 每件只应用一次当前精确 `T_S_A0`，形成 `S`-frame、mm 主 STEP；20/20 均为单根、单个 valid/closed/positive-volume BRep solid。
- 60/60 PLY/NPZ/STL 仅从重开的主 STEP 派生，转换至 m 一次；主 STEP 仍是几何 authority。
- 全 R121 源审计为 121 对象、117 个单 solid、4 个合法双 solid J6 ring、125 solids；53 个对象具有非 identity Placement。
- 独立验证 20/20，双向 Boolean symmetric-difference 20/20；负控 33/33 加补充变异 4/4；两次 fresh-process 保持 83/83 核心字节；pytest 226/226；Local Gate 25/25。
- CAD inspect 20/20、二十张等轴测图和 contact sheet 通过局部视觉检查。CAD Viewer 因安装包缺少 `agent:start` 真实失败，没有伪装成 PASS。
- CAD 工具先后产生 20 和 10 个同名 GLB；重复文件字节数相同但哈希不同，已全部留证为 `NONDETERMINISTIC_DIAGNOSTIC`，排除于主 STEP、83 件确定性核心和 Gate。

## 本地 PASS 没有升级系统 Authority

本包没有改写当前 registry、prebind、pair ledger、父级 Gate 或历史负结果。R20 仍为 `PENDING_OWNER_AND_SYSTEM_BINDING`：

1. R101 的普通 host-FK、J3 carriage、J4 travel/follower 和 J6 compound 适配仍为 fail-closed HOLD。
2. C9 九个逻辑线束对象仍为 capsule-chain 0/9；新审计只证明其具备可实现的解析几何输入，不等于运行时资产已发射。
3. as-built、制造偏差、物理敷设与硬件资格鉴定仍为 `null / UNKNOWN / HOLD`，禁止零填充。
4. 二十件尚未进入新的 append-only system registry revision，故没有生产 pair eligibility。
5. 接触、强度、生产窄相、SAFE、edge、path、TMG-4/G12、父级、控制和 release 均未获得信用。

## 当前系统状态保持不变

- 已知 active object：150。
- system operational geometry authority：1/150。
- 本地待 Owner/系统绑定候选：link1–link6 六个、gripper 三个、fixed-platform 三个、Route-C root-static 二十个，共 32；本轮 system 新增行为 0。
- per-pair clearance policy：0/11,166。
- 生产 pair query：0/11,166；system SAFE certificate：0；edge：0。
- stage instance：0/3；path search 未授权、未执行。
- `TMG-4=HOLD`，`G12=FAIL`；mechanical/control/joint-system/non-ABORT/next-stage/release 均为 false。
- V9F `-17.313396996697108 mm` 仅是历史 straight-q 负见证，不是当前 registry 下的 pair 结果，也未被本轮局部 PASS 清除。

## R101 已冻结的适配分组

排除 R20 后，剩余 101 个物理对象已经完成只读四方映射审计：

| 分组 | 数量 | 本地适配语义 | 当前状态 |
|---|---:|---|---|
| 普通 host-FK | 84 | `T_S_A0 · T_A0_h(q) · inv(T_A0_h(0))` | 合同已明确，候选尚未全部构建 |
| J3 carriage | 8 | link2 FK 加 `dx3=clip(32.5(q3+1.57),-55,+55) mm` | registry 类别未显式编码，必须按名称冻结 |
| J4 travel | 9 | link3 FK 加 `gain·dx4`，`dx4=-27.5q4 mm`，gain=`1/3,2/3,1` | 候选与独立端点复核待做 |
| FOLLOWER_LINK4 | 2（含于普通 84） | 普通 link4 FK，不得叠加 travel | 需单列 `1e-6 mm` follower 闭合复核 |
| J6 双 solid ring | 4（含于普通 84） | 一个 registry object 保留两个 solids | compound-aware 构建/验证待做 |

最安全的下一实际批次为 link1 六件：只涉及普通 host-local 化和 joint1 FK，不含 J3/J4 特殊律或双实体。该批次已启动，但在自身机器 Gate 通过前不计入本 V5 Authority。

## C9 并行研究线的合法边界

C9 指 registry 中九个 `C::SEG-*` 逻辑线束对象，不是 ASM 的 `C09_CONTACT_HISTORY`。冻结 V9F 中心线已提供 line/arc/helix/fillet 解析参数、9 mm 名义直径和 10 mm 设计上界，可构建确定性 capsule chain：

- capsule 轴采用解析 primitive 的分段弦；曲线到弦的逐段误差使用精确 sagitta 或 `M Δt²/8` 上界。
- 在曲率半径不小于 54 mm、弧长步长不超过 1.5 mm 时，统一保守界为 `1.5²/(8·54)=0.005208333333... mm`，但 Gate 必须保存逐 capsule 精确界。
- 使用设计上界半径 5.0 mm 时，不得再重复加入 `(10-9)/2=0.5 mm`。
- 新 pose adapter 必须读取当前 12 位 execution mount 和 accepted URDF；不得原样执行使用历史 D6 mount 的 V9F 主程序。
- J4 有冻结形变律；J3 只有 primary/alternate 双宿主保守表示，连续 q3 形变律仍 UNKNOWN，不得发明。
- P11 物理导向件 `[50,63] mm` 与 V9F 中心线 R65/R66/R55.036 等数值之间缺少显式偏置谱系；可按 V9F 建本地候选，但硬件 lineage 保持 UNKNOWN。

现行固定线束探针应准确表述为：11 个探针状态全部 UNSAFE，其中 10 个 mandatory 状态全部 UNSAFE；`Q_AS_BUILT_REFERENCE` 是第 11 个非 mandatory 状态。这些不是新 C9 capsule 的 current pair 结果。

## 更新后的最短关键路径

| 顺序 | 工作包 | V5 状态 | 下一机器完成判据 |
|---|---|---|---|
| CP-1A | base + link1–link6 | base 1 个 system；link 6 个 local candidate | Owner 接受后以新 registry revision 精确绑定；不得改旧 registry |
| CP-1B | gripper 三对象 | 3/3 local candidate，Owner 运动成员与九状态仍 HOLD | Owner 明示 24+24 motion membership 与九状态 joint1/joint2 SI 数值 |
| CP-1C1 | fixed-platform 三对象 | 3/3 local candidate | fit-up/as-built 边界保留；新 registry 后才可计数 |
| CP-1C2a | Route-C root-static R20 | **本轮完成，20/20 local candidate** | Owner/system 新 revision 后才可计数 |
| CP-1C2b | Route-C moving R101 | 运动合同分组完成；local candidate 0/101 | link1 六件起按九批 STEP-first 构建、运动适配、独立验证 |
| CP-1C3 | Route-C 线束 C9 | 解析合同审计完成；runtime capsule 0/9 | analytic capsule + Hausdorff + side-effect-free adapter；J3 保留 dual-host UNKNOWN |
| CP-1C4 | Solar 6 | FCStd 有双状态 selector，system state/HDRM/latch 未绑定 | 分状态单叶提取；禁止把含 22 solid 的组合 STEP 当单状态 geometry |
| CP-1C5 | BUS 与当前 150 外缺件 | BUS narrowphase 与外突出物缺失；target/support/HDRM 不在 150 | 先签发对象/接口 authority，禁止静默扩充 pair universe |
| CP-2 | PRE_RELEASE / RELEASE_EVENT / POST_RELEASE | 0/3 | 3/3 scene、ACM、HDRM、solar、arm、harness、mount、selector 全绑定 |
| CP-3A | pair-oracle 软件资格 | synthetic-only PASS | 保持软件资格与 production evidence 分离 |
| CP-3B | production backend admission + batch completeness | 未授权 | exact 11,175 行：9 EXEMPT + 11,166 GEOMETRIC；任一 UNKNOWN/FAIL 即 batch abort |
| CP-4 | 连续边 + bounded M01 path | 0 edge / no search | 当前语义的 edge certificate 后才允许 bounded search |
| CP-5 | Route-C TMG-4/G12 重评 | HOLD/FAIL | 新路径与当前几何绑定后重评；历史负见证保留 |
| CP-6 | 目标相对 MuJoCo V2 | 隔离并行、未创建 | 自由目标、相对 SE(3)/twist、碰撞/接触关闭、DOP853 对拍；不得绕过 M01 |

内存继续采用 monitor-only 策略；本轮没有修改 legacy memory Gate，也没有把 Owner override 或空闲内存阈值伪装成 `MEMORY_GATE_PASS`。
