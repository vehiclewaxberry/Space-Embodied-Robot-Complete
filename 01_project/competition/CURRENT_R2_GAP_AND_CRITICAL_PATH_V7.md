# CURRENT R2 缺口与单点汇合关键路径 V7

日期：2026-08-28  
继承基线：`CURRENT_R2_GAP_AND_CRITICAL_PATH_V6.md`，SHA-256 `5377B7168A0A0D2D6627054A2C6F518F4ACAD94BB7CD157C39042AD86255E984`。  
更新方式：append-only；Phase0、V2–V6、前六份汇合回执及所有父级/历史 Gate 均未原位改写。

## 第七个实际收敛增量

新增并完成修复的局部包：

`20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_ROUTE_C_C9_ANALYTIC_CAPSULE_CANDIDATE_V1/`

现行机器 Gate：

```text
C9_LOCAL_CAPSULE_CANDIDATES_9_OF_9_PASS__ANALYTIC_HAUSDORFF_AND_SIDE_EFFECT_FREE_POSE_ADAPTER_VALIDATED__J3_PRODUCTION_UNION_ACCEPTANCE_UNKNOWN__ZERO_CURRENT_PAIR_EDGE_PATH_CREDIT__TMG4_HOLD
```

Gate 为 21/21，SHA-256 `6046847D0104177626FBBD0CBC3B66482224F8B3FEB5AA3A06AF2BBF8A121073`。本增量只关闭九个 C9 逻辑线束对象的本地解析中心线离散、保守半径、姿态适配和独立验证：

- 9 个对象、61 个解析 primitive、2355 个 capsule；静态和 posed 表达均保留设计半径、Hausdorff 上界和有效半径三项独立字段。
- 生产窄相唯一合法半径字段为 `effective_radius_mm = design_radius_mm + hausdorff_bound_mm`，且只能计一次。设计半径 5.0 mm 已包含名义半径至设计半径的 0.5 mm 裕量，不得再次叠加 0.5 mm。
- 全局静态最大 Hausdorff 上界为 `0.005112823031626079 mm`，最大有效半径为 `5.005112823031626 mm`。直接使用 5.0 mm 或二次扣减 Hausdorff 均由负控拒绝。
- J4 section 5 已由修复前的 71 段改为固定 139 段。q4=`-1.87/0/1.57 rad` 的最大动态弧长步长分别为 `1.4992706602297672/0.7593426026758103/0.13811958109307645 mm`，均不超过 1.5 mm；每个样本都重算全部 139 段。
- J4 最大 follower closure 残差为 `6.530958110121889e-10 mm`，最大 exchange-length 残差为 `2.2737367544323206e-13 mm`。
- 独立验证 16/16，负控 21/21，pytest 52/52；两轮 fresh replay、六个新进程、23 个核心产物逐字节不变。
- manifest、inventory 与实际 payload 38/38 一致；包内无 `__pycache__`、`.pyc` 或临时文件。

## 修复前结果永久保留为零信用负历史

第一版自报 18/18 PASS 的结果不能获得 Authority。独立审计发现三个缺陷：

1. 5.0 mm 设计半径和 Hausdorff 上界分开保存，但未强制窄相消费二者之和；
2. J4 section 5 的 71 段拓扑只在 q4=0 满足步长要求，在 q4=-1.87 时最大步长为 `2.935191855942784 mm`；
3. 系统状态来自合同拷贝/硬编码比较，没有由包自身读取当前机器 Gate。

旧 Gate/manifest/inventory 哈希和缺陷已冻结在 `07_reviews/C9_PRE_REPAIR_NOT_CLEAN_PASS_V1.json`，其裁决为：

```text
SUPERSEDED_PRE_AUTHORITY_NOT_CLEAN_PASS__ZERO_CREDIT
```

修复不是放宽阈值：现行包新增 `NC19`、`NC20`、`NC21`，分别阻断 raw 5 mm 查询、Hausdorff 双扣和旧 71 段全域复用。

## 当前系统状态由四个外部机器 Gate 重建

现行 validator 与 finalizer 实际读取并哈希锁定：

- M01 registry Gate：`F5E91371648756D43FF7CF6C03028FA95174428D088BAAC08254FAD8D5DCC3FF`；
- M01 prebind Gate：`CDFADB08C3C93F9E380C41B232727E7D08750B2955411DF9E4AF894C550B7FC4`；
- terminal release Gate：`14D30FD40AC60253C0716A71BA46950E1DF6B8E69DCE3F12690319B970A48674`；
- G12 terminal handoff Gate：`42792057BD9FE08FDEABADEC23B5F2CFA06095A33D5A8F363633CE90BC6BE982`。

C9 合同中的系统状态只是 declaration-only，必须与上述外部文件重建值逐项相同。本轮四个 Gate pin 只证明“当前状态未升级”；C9 未直接绑定 `15_UNIFIED_R2_SYSTEM_INTERFACE.yaml`，因此没有 Unified R2 接口或 M01 scene binding 信用。

## 局部 PASS 没有升级系统 Authority

- known active object：150；system operational geometry authority：1/150。
- 本地待 Owner/系统绑定候选由 38 增至 47；本轮 system registry 新增 0 行。
- clearance policy：0/11,166；production pair query：0/11,166；SAFE certificate：0；edge：0。
- stage instance：0/3；path search 未授权、未执行，`path_exists=false`。
- `TMG-4=HOLD`，`G12=FAIL`；机械发布、控制、joint-system、non-ABORT、next-stage、release 均为 false。
- V9F `-17.313396996697108 mm` 仍只是历史 straight-q 负见证，不是当前 pair 结果，也未被 C9 局部 PASS 清除。

## 仍未闭合的 C9 工程边界

1. J3 已产生 169 个 dual-host 表达，但连续形变律和 production union Owner 接受仍为 `UNKNOWN`。
2. P11 中心线/半径谱系仍为 `UNKNOWN`。
3. J4 全硬件覆盖、as-built、制造偏差和物理敷设实测仍为 `HOLD/null/MEASUREMENT_PENDING`，禁止零填充。
4. 历史固定外线束探针 0/75 SAFE、11/11 forced UNSAFE 继续有效；它与本轮解析 C9 候选不是同一个生产 pair 证据。
5. C9 尚未被 Owner/system registry、clearance policy、stage instance 或 production narrowphase 接纳。

## 当前唯一主关键路径

```text
当前系统 Authority（1/150 operational，0/11166 pair）
  ├─ 已闭合本地候选：V6 的 38 + C9 的 9 = 47 pending
  └─ Route-C R95：
       Link2-B12（必须先完成 q1×q2 3×3 独立 FK 验证）
       → 剩余 R83 普通/J3 carriage/J4 travel/J6 compound 批次
          ↓
Owner 签发 append-only system registry / scene / clearance-policy revision
          ↓
M01 PRE_RELEASE / RELEASE_EVENT / POST_RELEASE 三阶段绑定
          ↓
11,166 个生产 pair oracle + continuous edge certificate
          ↓
仅在 M01 合法闭合后进入目标相对控制、接触、柔性、SAFE、Sim13 与具身智能单点汇合
```

Link2-B12 不得只在 q1=0 检查三个 q2 样本；必须验证 q1=`-2.8/0/2.8` 与 q2=`-3.14/-1.57/0` 的九点笛卡尔积，并用 q1 ignored、q1 sign-reversed 负控证明 joint1 贡献没有被遗漏。

## 当前裁决

```text
V7_C9_LOCAL_ANALYTIC_CAPSULE_INCREMENT_PASS__47_LOCAL_PENDING__SYSTEM_REMAINS_1_OF_150_ZERO_OF_11166_AND_FAIL_CLOSED__R95_AND_OWNER_M01_BINDING_REMAIN
```

这不是 `COLLISION_VALID`、`TMG4 PASS`、`G12 PASS`、`M01 PASS`、`NEXT_STAGE_AUTHORIZED` 或 `RELEASE_CREDIT`。
