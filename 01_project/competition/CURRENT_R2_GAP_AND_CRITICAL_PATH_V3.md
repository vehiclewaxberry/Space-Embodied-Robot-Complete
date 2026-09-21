# CURRENT R2 缺口与单点汇合关键路径 V3

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH_V2.md`，SHA-256 `EF2790B9F29396047C4CE4B70104628AE8F1B966B2D1BFA3CC54F56FF66D7976`。  
更新方式：append-only；V1、V2、第一/第二汇合回执和任何历史 Gate 均未原位改写。

## 第三个实际收敛增量

新增包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1/`

机器 Gate：

```text
3_OF_3_LOCAL_STEP_FIRST_GEOMETRY_CANDIDATES_PASS__
60_OF_60_BREP_SOLIDS__INDEPENDENT_VALIDATION_PASS__
NEGATIVE_20_OF_20_44_OF_44__
PENDING_OWNER_24_BODY_MOTION_OWNERSHIP_AND_NAMED_STATE_MAP__
ZERO_SYSTEM_PAIR_EDGE_PATH_CONTACT_RELEASE_CREDIT
```

本增量关闭 CP-1B 的“本地 STEP-first 几何构建、frame/单位链与独立验证”子项：

- `gripper_link` 使用 R1 palm 主 STEP，12 个 solid，主文件字节保持一致。
- `gripper_left` 与 `gripper_right` 分别从冻结 B50 中性几何和既有成员分配重建 24 个 solid；包装层对象不计入实体成员。
- 两指严格使用 accepted URDF 的字面 `±1.5708 rad` 和 q=0 变换，各自只执行一次逆变换并输出到 child-link local frame；没有把 `π/2` 理想值替代字面真值。
- 三个 STEP 容器独立重开为 `12+24+24=60` 个 valid、closed、positive-volume BRep solid。两指 q=0 回组 bbox 最大差约 `9.9e-11 mm`。
- 主 BRep 对 M5 q=0 fingerprint 的 bbox 端点差为 left `0.000681070737 mm`、right `0.000682261976 mm`，均小于 `0.001 mm`；runtime mesh 对 M5 约 `3.4e-6 mm`。
- STEP 原生单位为 mm；运行时 PLY/NPZ/STL 为 owning-link-local m。主 BRep 每对象数值 derate 为 `1e-6 mm`，runtime pair lower-bound debit 为 `0.100002 mm`；制造/实物误差仍为 `null`。
- 独立验证未导入 builder/core，28/28 source pins、60/60 solids 和 13/13 独立负控通过；合同负控 20/20、44/44 变异子例通过；fresh-process replay、pytest 29/29、ruff、55/55 manifest 和 56/56 inventory 均通过。
- CAD refs/planes/positioning 和九视图审查通过。CAD Viewer 缺少 `agent:start`，已作为展示工具故障如实记录，未伪造 viewer PASS。

## 局部 PASS 没有解决的两个 Owner 事实

1. 左、右各 24 个实体是否全部随对应的单一 prismatic link 刚性运动，尚无 Owner 明示。几何成员配准不能替代运动所有权裁决。
2. accepted URDF 只给出 `0–0.0715 m` 数值限位；九个命名构型中的 `gripper_joint1/gripper_joint2` 数值仍为 null。q=0 只用于 frame 注册，不得被重命名为 OPEN、CLOSED 或 CAPTURE。

因此这三个对象仍是 `PENDING_OWNER_REVIEW` 本地候选，不得写入当前 system operational registry。制造/实物公差、接触、强度、执行器动态、生产 pair、SAFE、edge、path、TMG-4/G12、父级和 release 均未获得信用。

## 当前系统状态保持不变

- 已知 active object：150。
- system operational geometry authority：1/150。
- 本地待 Owner 几何候选：原 link1–link6 六个，加本轮 palm/left/right 三个，共 9；其中本轮系统新增行数为 0。
- per-pair clearance policy：0/11,166。
- 生产 pair query：0/11,166；system SAFE certificate：0；edge：0。
- stage instance：0/3；path search 未授权、未执行。
- TMG-4=`HOLD`，G12=`FAIL`；mechanical/control/joint-system/non-ABORT/next-stage/release 均为 false。

## 更新后的最短关键路径

| 顺序 | 工作包 | V3 状态 | 下一机器完成判据 |
|---|---|---|---|
| CP-1A | base + link1–link6 operational promotion | 1 个 system + 6 个 Owner-review candidate | Owner 接受后用新 registry revision 精确变为 7/150；不得改旧 registry |
| CP-1B1 | gripper 三对象 local geometry | **本轮完成，3/3 local candidate** | 保持本 Gate immutable；不得重复计为 system credit |
| CP-1B2 | gripper Owner decision + system bind | **HOLD** | Owner 明示 24+24 motion membership，并签发九命名构型的 joint1/joint2 SI 数值；随后新 registry revision 才可计数 |
| CP-1C | 其余 Route-C、Solar/HDRM、M3R、bus protrusion、target | 未闭合 | 每对象 STEP-first narrowphase、frame/motion/derate authority、独立验证与负控完整 |
| CP-2 | PRE_RELEASE / RELEASE_EVENT / POST_RELEASE | 0/3 | 3/3 scene、ACM、HDRM、solar、arm、harness、mount 和 selector 全绑定 |
| CP-3A | pair-oracle 软件资格 | synthetic-only PASS | 旧 Gate 保持 immutable；不得作为 production pair credit |
| CP-3B | production backend admission + batch completeness | 未授权 | exact 11,175 行：9 EXEMPT + 11,166 GEOMETRIC；无重漏，任一 UNKNOWN/FAIL 均 batch abort |
| CP-4 | 连续边 + bounded M01 path | 0 edge / no search | 当前语义适配的 edge certificate 后才允许 bounded search |
| CP-5 | Route-C TMG-4/G12 重评 | HOLD/FAIL | 新路径与当前几何绑定后重评 75 个任务样本；旧 V9F 负结果保留 |
| CP-6 | 目标相对 MuJoCo V2 | 隔离并行、未创建 | 自由目标、相对 SE(3)/twist、碰撞/接触关闭、DOP853 对拍；不得绕过 M01 |

## 下一项可执行增量

最短 Owner 接口是一个只含显式选择与 SI 数值的决策包：

1. 确认或拒绝 `gripper_left` 的 24-member motion membership；
2. 确认或拒绝 `gripper_right` 的 24-member motion membership；
3. 为九个命名构型逐行给出 `gripper_joint1_m`、`gripper_joint2_m`，每项必须在 `[0, 0.0715] m`，禁止继承、默认和 null→0。

在 Owner 回答前，自主内部线可以继续 CP-1C 的下一对象包，但不得借此把本轮三个候选提升为 system asset。Owner 决策一旦到位，必须由新的 append-only registry/prebind Gate 完成 system promotion，而不是改写旧 M01 registry。

内存继续按 monitor-only 执行；本轮没有修改 legacy memory Gate，也没有把 Owner override 伪装成 `MEMORY_GATE_PASS`。
