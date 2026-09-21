# CURRENT R2 缺口与单点汇合关键路径 V6

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH_V5.md`，SHA-256 `B95AC148F3B4BFA75FEEDC06AC9286FE81D54D83E1E2E516EEAADABF85B2472F`。  
更新方式：append-only；Phase0、V2、V3、V4、V5、前五份汇合回执及全部历史 Gate 均未原位改写。

## 第六个实际收敛增量

新增包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_R101_LINK1_B6_OPERATIONAL_COLLISION_CANDIDATE_V1/`

机器 Gate：

```text
LINK1_B6_LOCAL_CANDIDATE_GATE_24_OF_24_PASS__SYSTEM_REMAINS_1_OF_150_AND_FAIL_CLOSED
```

本增量只关闭 R101 首个安全批次，即六个 `parent_frame=link1` 普通对象的本地 host-frame STEP-first 几何、运行时派生、姿态适配与独立验证：

- 冻结对象精确为一个支架、三个夹具、一个 J2 mandrel 和一个 liner；6/6 主 STEP 位于 `link1@q1=0`、单位 mm，均为单 root、单个 valid/closed/positive-volume BRep solid。
- 源 `Shape` 位于 `A0@q0`、mm，且已经包含 FreeCAD `Object.Placement`；本轮没有再次应用 Placement。主 STEP 只应用一次 `inv(T_A0_link1(0))`。
- 18/18 PLY/NPZ/STL 从冷重开的主 STEP 派生到 m 一次；主 STEP 仍是局部几何 authority。
- 动态姿态合同为 `p_S_m = T_S_A0_m · T_A0_link1(q1)_m · p_link1_m`。适配器直接读取 accepted URDF 原始 joint1 数字和当前 12 位 `T_S_A0`，不使用历史 D6 mount，也不由 25° 重新计算 mount。
- `q1=-2.8, 0, +2.8 rad` 三点由独立实现复核；`q0` 的 `A0→link1→S` 闭合最大绝对残差为 `2.7755575615628914e-17`。这些是变换实现检查，不是连续路径或生产 pair 查询。
- 独立验证 6/6，双向 BRep difference 6/6，运行网格 closed/oriented two-manifold 6/6；验证器不导入 builder。
- 负控 44/44；两次 fresh builder check 加两次 fresh independent validation 保持 28/28 核心字节；pytest 10/10；Local Gate 24/24。
- CAD inspect 6/6、六张等轴测图与 root 独立视觉抽查通过局部外观检查。`01_cad/` 仅有 6 个 STEP，其他文件 0，包内 `__pycache__` 为 0。
- CAD Viewer 已真实尝试，但安装包缺少 `agent:start`；该工具失败由 CLI inspection 与已审阅快照补充，不伪装成 Viewer PASS，也不改变几何或 Authority。

## 局部 PASS 没有升级系统 Authority

Link1-B6 六件的分类仍为 `PENDING_OWNER_AND_SYSTEM_BINDING`。本包没有改写 current registry、prebind、pair ledger、父级 Gate 或历史负结果：

1. 六件 host-local STEP 没有自动成为 `system operational_geometry`；新的 append-only Owner/system registry revision 尚未签发。
2. 姿态适配器的三个 q1 校验点不等于 11,166 个生产 pair query，也不证明任一连续无碰路径。
3. R101 仅从 101 件本地待构建对象收敛六件，剩余 R95 仍为 `FAIL_CLOSED_HOST_AND_SPECIAL_MOTION_ADAPTER_HOLD`。
4. C9 九个逻辑线束对象仍未获得 system binding；J3 连续形变律、P11 半径/偏置谱系、dual-host union Owner 接受仍保持 `UNKNOWN/HOLD`。
5. as-built、制造偏差、物理敷设与硬件资格鉴定仍为 `null / MEASUREMENT_PENDING / UNKNOWN / HOLD`，禁止零填充。
6. 接触、强度、生产窄相、SAFE、edge、stage、path、TMG-4/G12、父级、控制和 release 均未获得信用。

## 当前系统状态保持不变

- 已知 active object：150。
- system operational geometry authority：1/150。
- 本地待 Owner/系统绑定候选：rigid-link proxy 六个、gripper 三个、fixed-platform 三个、Route-C root-static 二十个、Route-C link1 六个，共 38；本轮 system 新增行为 0。
- per-pair clearance policy：0/11,166。
- 生产 pair query：0/11,166；system SAFE certificate：0；edge：0。
- stage instance：0/3；path search 未授权、未执行，`path_exists=false`。
- `TMG-4=HOLD`，`G12=FAIL`；mechanical/control/joint-system/non-ABORT/next-stage/release 均为 false。
- V9F `-17.313396996697108 mm` 只保留为历史 straight-q 负见证；它不是当前 registry 下的 pair 结果，也没有被本轮局部 PASS 清除。

## R95 剩余适配边界

V5 冻结的 R101 映射中，84 件为普通 host-FK、8 件为 J3 carriage、9 件为 J4 travel。扣除本轮六件普通 link1 对象后，剩余 R95 为：

| 分组 | 剩余数量 | 当前合法状态 |
|---|---:|---|
| 普通 host-FK | 78 | 逐 host 建 STEP-first 候选和独立 FK 适配；不得继承 Link1-B6 PASS |
| J3 carriage | 8 | 使用冻结 `dx3=clip(32.5(q3+1.57),-55,+55) mm`；按名称显式冻结 |
| J4 travel | 9 | 使用 `dx4=-27.5q4 mm` 与 gain=`1/3,2/3,1`；follower 不得重复叠加 travel |
| 其中 FOLLOWER_LINK4 | 2（含于普通 78） | 普通 link4 FK，并单列 `1e-6 mm` follower 闭合复核 |
| 其中 J6 双 solid ring | 4（含于普通 78） | 一个 registry object 保留两个 solids，必须 compound-aware |

所有新适配器继续直接消费 current exact 12dp execution mount，保持 frame/单位单次变换、独立重算、负控、fresh-process 与 fail-closed 系统不变量。

## C9 并行线仍不计入 V6 Authority

C9 解析 capsule/Hausdorff 工作可以与 R95 并行，但在其独立包与机器 Gate 完成前，本 V6 不增加任何 C9 候选数。九个 `C::SEG-*` 仍与 ASM 的 `C09_CONTACT_HISTORY` 严格分离；固定线束探针 11/11 为 UNSAFE，其中 10/10 mandatory，不得改写为当前 C9 pair 结果。

## 单点汇合关键路径

```text
当前系统 Authority（1/150 operational，0/11166 pair）
  ├─ 已闭合的本地候选：既有 12 + Route-C R20 + Link1-B6 = 38 pending
  ├─ Route-C R95：逐 host / J3 / J4 / J6 构建与独立验证
  └─ Route-C C9：解析 capsule、Hausdorff、dual-host 与硬件谱系边界
          ↓
Owner 签发 append-only system registry / scene / clearance-policy revision
          ↓
production narrowphase + 11,166 pair ledger + 3 stage instances
          ↓
SAFE/edge/path 判定
          ↓
TMG-4 / G12 / M01 父级 Gate
          ↓
机械准入后才允许动力学—控制—具身智能单点汇合
```

## 本轮裁决

最高合法主张仅为：六件 Route-C link1 host-local STEP-first 碰撞候选及其独立姿态适配验证通过；本地 pending 候选从 32 增至 38。系统仍为 1/150、0/11,166、SAFE 0、edge 0、stage 0/3、path false、`TMG-4=HOLD`、`G12=FAIL`、next/release false。

下一实际增量：继续隔离构建 R95 的下一普通 host 批次，并行完成 C9 解析 capsule 包；两者均不得在新的 Owner/system Authority 前继承或宣称 system PASS。
