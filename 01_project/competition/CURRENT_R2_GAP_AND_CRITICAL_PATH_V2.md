# CURRENT R2 缺口与单点汇合关键路径 V2

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH.md`，SHA-256 `320818C03F28D8ACE02168CFDA6E89A31DA8A2C190D796C59CA8A7FEE42E3147`。  
更新方式：append-only；V1、第一汇合回执和任何历史 Gate 均未原位改写。

## 第二个实际收敛增量

新增包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/`

机器 Gate：

`PAIR_ORACLE_BACKEND_SYNTHETIC_GATE_PASS__18_OF_18_NEGATIVE_CONTROLS__INDEPENDENT_5_OF_5__ZERO_CURRENT_SYSTEM_PAIR_QUERIES__TMG4_G12_M01_EDGE_PATH_PARENT_RELEASE_HOLD`

本增量实际关闭的是 CP-3 的“软件后端存在性与 fail-closed 语义资格”子项：

- OCP `BRepExtrema_DistShapeShape` 单-pair backend 已实现；只接受本包 `FIXTURE::` 哈希绑定 BRep，拒绝生产几何路径。
- BRep 原生 mm；S 系位姿平移输入 m，只在 OCP transform 边界显式乘 `1000.0`；q 为 rad；distance、witness、clearance、derate、margin 全为 mm。
- 合成数值工况：10 mm 间隙为 SAFE；2 mm 间隙在 5 mm requirement 下由认证上界证明 UNSAFE；5.0000005 mm 的跨阈值区间为 UNKNOWN；接触为 UNSAFE；精确 adjacent exception 为 EXEMPT 且不带几何字段。
- pytest 29/29、适用负控 18/18、独立 OCP 复算 4+1/4+1、Gate 25/25、manifest 15/15 和 SHA inventory 16/16 均通过；builder 与 independent validator 均通过 byte-identical replay。
- 8 个属于动力学 plant、接触、weld 或 M01 path 的负控明确记为 `NOT_APPLICABLE`，没有伪装成 PASS。

最高合法主张是：

```text
PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__
ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__
NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT
```

## 系统状态为何没有随局部 PASS 改变

当前生产 admission 仍缺：

- 149/150 对象的 operational geometry authority；link1–link6 仍是 6 个 `PENDING_OWNER_REVIEW` 本地候选，未入 registry。
- 三阶段实例 0/3，权威场景值 0/30。
- per-pair clearance policy 0/11,166；禁止 default、继承、caller override 和零填充。
- 完整 exact exception-set、逐对象 motion/derate、mount/frame/scene 与 backend production binding。
- 11,166 个真实几何结果、连续边证书和 bounded path search。

因此系统计数保持：运行 authority 1/150，pair query 0/11,166，system SAFE pair 0，edge 0，path search=false。TMG-4 HOLD、G12 FAIL、父机械/控制/系统/SAFE/Sim13/non-ABORT/next-stage/release 均未重发或解锁。

## 更新后的最短关键路径

| 顺序 | 工作包 | V2 状态 | 下一机器完成判据 |
|---|---|---|---|
| CP-1A | base + link1–link6 operational promotion | 1 个 system + 6 个 Owner-review candidate | Owner 明确接受后用新 registry revision 精确变为 7/150；不得改旧 registry |
| CP-1B | B601 gripper/2P operational geometry | 尚无 state-bound narrowphase BRep | palm/left/right 三个 STEP-first 闭合实体、runtime m 制资产、独立 frame/单位/哈希/状态验证；Owner state-map 未签前只得 local candidate |
| CP-1C | 其余 Route-C、Solar/HDRM、M3R、bus protrusion、target | 未闭合 | 每对象 narrowphase 资产与 frame/motion/derate authority 完整 |
| CP-2 | PRE_RELEASE / RELEASE_EVENT / POST_RELEASE | 0/3 | 3/3 scene、ACM、HDRM、solar、arm、harness、mount 和 selector 全绑定 |
| CP-3A | pair-oracle 软件资格 | **本轮完成，synthetic only** | 本 Gate 保持 immutable；不得重复计算为 production credit |
| CP-3B | production backend admission + batch completeness | 未授权 | exact 11,175 行：9 EXEMPT + 11,166 GEOMETRIC；无重漏，任一 UNKNOWN/FAIL 均 batch abort |
| CP-4 | 连续边 + bounded M01 path | 0 edge / no search | 当前语义适配的 edge certificate；不得复用旧 `FAIL -> UNSAFE` 行为；随后才允许搜索 |
| CP-5 | Route-C TMG-4/G12 重评 | HOLD/FAIL | 新路径和当前几何绑定后重评 75 个任务样本；旧 V9F 负结果保留 |
| CP-6 | 目标相对 MuJoCo V2 | 可隔离并行，未创建 | 独立自由目标、相对 SE(3)/twist、碰撞/接触关闭、DOP853 对拍；不得绕过 M01 |

## 下一项可执行机械增量

只读审计表明，下一项最小且高价值的机械包是：

`ODR60_OPTION_A_B601_GRIPPER_2P_OPERATIONAL_PROXY_V1`

其设计边界为：

1. accepted URDF 是质量、惯量、frame、2P 轴和 `0–0.0715 m` 限位真值；不得改质量或用历史三指末端替换。
2. `gripper_link`、`gripper_left`、`gripper_right` 必须各有真正 state-local 的封闭 STEP BRep；full-stroke swept volume 只能作 broadphase。
3. 两指推荐存入各自 child-link frame，并在 q=0 与 M5 `gripper_link`-local screening surface 独立配准，防止 child transform 双应用。
4. 冲突的 named-state→travel map 未经 Owner 裁决前必须 HOLD；本地几何候选可做，但不得升 registry/system credit。
5. 负控至少覆盖 m/mm、link6 错绑、左右 signed axis 互换、状态缺失/越界、hash/NaN、transform 双应用。

该包的最大预期本地裁决只能是：

```text
3_OF_3_LOCAL_GEOMETRY_CANDIDATES_PASS__
PENDING_OWNER_STATE_MAP_AND_SYSTEM_BIND__
NO_PAIR_EDGE_PATH_RELEASE_CREDIT
```

## 权威导航增量

V1 authority index 保持不变；追加 `CURRENT_R2_AUTHORITY_DELTA_V2.json`：

- 补入汇总级 current `R5_INCREMENT_GATE.json`，同时保留 RUN6 candidate 为证据；两者均保持 R5 REPEAT/HOLD。
- 补入 `CTRL_R2_PRECONTACT_TRACKING_GATE_V1.json`，它是 CURRENT 子 Gate，但不替代 control parent HOLD。
- 补入本轮 pair-oracle backend Gate，分类 `PENDING_OWNER_REVIEW`，无 system/parent credit。

内存继续按 monitor-only 执行；本轮未修改 legacy memory Gate，也未把 owner override 伪装成 `MEMORY_GATE_PASS`。
