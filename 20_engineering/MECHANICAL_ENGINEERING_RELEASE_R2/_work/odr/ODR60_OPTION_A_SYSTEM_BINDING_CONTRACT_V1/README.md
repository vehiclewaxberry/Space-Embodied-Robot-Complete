# ODR-60 Option A system-binding readiness contract V1

本目录把“已经有 150 个对象与 11,175 个 pair 的结构清单”推进到**可审计的系统 pair oracle 与连续边运动界合同**，但不执行任何现役几何加载、pair 距离查询、edge 查询或路径搜索。因此本目录只能给出 `HOLD`，不能继承 V9F、局部 base_link proxy 或合成测试的 PASS。

## 当前机器真值

- 活跃对象：150（A=10、C=9、F=4、R=121、S=6）。
- 无序 pair：`150×149/2 = 11,175`。
- 仅允许 9 个 accepted-URDF 相邻关节精确 ID 例外；无 wildcard、无人工临时例外。
- 非例外且必须查询：11,166；其中非 C pair 为 9,861，C 相关 pair 为 1,305。
- 每个 q 必须稳定输出全部 11,175 行：9 个精确例外行不得省略，11,166 个几何行不得缺失或重复；例外行不计作 SAFE。
- 当前系统级已认证 object motion bound：0；已执行 pair/edge/path：0；pair、edge、path、release authority 均为 `false`。
- 当前尚无哈希绑定的逐 pair clearance policy，不能由调用者自行给出更小甚至负的门槛。
- accepted URDF 的磁盘 CRLF 哈希 `1BC2B748...` 与 LF 规范化哈希 `408147DD...` 已证明属于同一内容；这里不存在旧/新 URDF 语义冲突。
- WP11 物理安装轨与 ODR-01 动力学轨之间的唯一显式桥 `0ACEB659...` 已由 ODR-45 确认；尚未闭合的是执行期数值拼写与当前碰撞资产 frame registration，而不是桥本身。

## 四阶段绑定计划（计划覆盖，不是 PASS）

1. `P1` 绑定 131 个核心对象：`A::base_link`、3 个 F 接口件（LOAD_BRIDGE、M3R_STAGE_A/B）、6 个 Solar 对象和 121 个 Route-C 固体。
2. `P2` 查询这 131 个对象内部的 `C(131,2)=8,515` 个 pair；该集合内没有 9 个 URDF 相邻例外。
3. `P3` 加入 9 个 C section/capsule 对象，新增 `9×131+C(9,2)=1,215`，累计 9,730 个非例外 pair。
4. `P4` 加入其余 9 个 A 对象和 `F::BUS`。它们触及 1,445 个 raw pair，其中恰含全部 9 个相邻例外，所以剩余必须查询 1,436 个；最终 `9,730+1,436=11,166`。

四阶段只定义覆盖顺序。任何“计划包含”都不得改写为“已经评估”或“已经 SAFE”。

## 运动分类

- 124 个 `DIRECT_RIGID_FK_CANDIDATE`：accepted URDF/FK 或固定场景变换的候选；其中 `FOLLOWER_LINK4` 两件按 link4 FK 直接候选处理。
- 8 个 `J3_HIDDEN_TRANSLATION`：严格采用 V9F `J3_CARRIAGE_PARTS`，附加 `clip(32.5(q3+1.57), -55, 55) mm` 平移。
- 9 个 `J4_TRAVEL_TRANSLATION`：只接受 `ONE_THIRD_TRAVEL`、`TWO_THIRDS_TRAVEL`、`FULL_TRAVEL` 三类，附加 `g·(-27.5 q4) mm` 平移。
- 9 个 `C_SECTION_CAPSULE`：必须从连续 section centerline 建 capsule chain，并给出 centerline-to-polyline Hausdorff 上界。缺失、非有限或未经哈希绑定时一律 `UNKNOWN_ABORT`。

四类必须互斥且并集精确等于 registry 的 150 个 object ID。

连续边运动证书中的 `B_i_cert` 是真实几何运动的**上界**：`sup d_H <= B_i_cert`。最终 `global_L_mm_per_rad` 必须在完整关节域、完整 J3/J4 隐藏行程和全部受权场景状态上证明，并已经包含父链、几何轴距和隐式运动贡献；q=0 半径、推导用几何半径或隐藏平移项不得在运行时漏扣或重复扣减。

## pair 记录与数值防火墙

- `GEOMETRIC_RESULT` 仅用于 11,166 个 Q 对；`EXCEPTION_RESULT` 仅用于 9 个 E 对。例外行强制回显 exact-pair/ACM 与规则哈希，禁止以 0、`null` 或空 witness 伪填几何字段。
- `SAFE` 只由严格正的认证下裕量签发；保守下界 `<=0` 只能说明 SAFE 未证明。`UNSAFE` 必须由认证上裕量 `<=0` 或闭合集合交叠/接触见证证明。
- `required_clearance_mm >= authorized_pair_min_mm >= 0`；所有实际消费的 Hausdorff/数值降额必须有限且非负；认证下界不得大于认证上界；完整结果的 comparison set 必须为正整数。
- builder 内的纯元数据验证器覆盖负门槛、低于 policy、负/NaN 降额、倒置区间、零/布尔比较集、错误姿态维数和“只有下界非正却宣称 UNSAFE”等反例。它不是几何 oracle，也不授予任何运行权限。

## mount 双轨绑定与剩余 HOLD

冻结 mount/pose YAML（`D6E33CB...`）内嵌的 `408147DD...` 是 accepted URDF 的 LF 规范化哈希；现磁盘原始 CRLF 哈希为 `1BC2B748...`。292 个 CRLF 被逐一替换为 LF 后可精确复算 `408147DD...`，因此 `semantic_delta=false`。

该 YAML 的 208 mm / 25° 矩阵属于 WP11 物理安装轨的历史 6 位小数拼写；185.25 mm + `Ry(+90°)` 属于 ODR-01 动力学参考轨。项目已有经 ODR-45 确认的唯一桥：

```text
B = inv(T_S_A0_dynamics) · T_S_A0_physical
  = Trans(z_A0,+0.02275 m) · Rot(z_A0,+25.000014°)
```

因此本包不再要求“因 URDF 冲突重发 mount”。但系统运行仍必须 fail-closed，直到：

- 明确绑定 D6 6 位或 ODR-43 12 位/full 精度为执行矩阵，并全链一致；若消费 6 位拼写，必须显式计入 `WP11-F-03` 已登记偏差；
- 将 V2 base proxy、各 link/D_i、Route-C 附件与场景对象的 collision geometry 哈希注册到 accepted URDF frame；
- 每个 system object motion certificate 同时绑定上述执行拼写、frame registration、scene state 与几何资产。

## 文件

- `SYSTEM_PAIR_ORACLE_CONTRACT_V1.json`：pair universe、四阶段覆盖、oracle 输入/输出、SAFE/UNSAFE/UNKNOWN/FAIL 规则。
- `OBJECT_MOTION_BOUND_CONTRACT_V1.json`：150 对象的互斥运动分类、J3/J4 严格运动律、连续 edge bound 公式和 C capsule Hausdorff 降额。
- `build_system_binding_readiness.py`：只读元数据与源码文本；不导入/加载 mesh、STEP、FCStd、NPZ/NPY，不构造 pair 距离，不搜索路径。
- `test_system_binding_readiness.py`：正例、集合错配、J3/J4 错分、非法例外、合同内/外 source-pin 交叉绑定、readiness 越权、URDF EOL 双哈希漂移、桥确认、数值防火墙、确定性与 fail-closed 负例。
- `SYSTEM_BINDING_READINESS_GATE_V1.json`：生成的机器 Gate，固定为 HOLD。
- `SYSTEM_BINDING_READINESS_SHA256_V1.csv`：本目录及关键外部输入的哈希清单；manifest 不自包含自身哈希。

## 复现

在仓库根目录执行：

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/build_system_binding_readiness.py --write
python -m pytest -q 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/test_system_binding_readiness.py
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/build_system_binding_readiness.py --check
```

`--write` 只写本目录的 Gate 与 manifest。`--check` 不写文件，并要求现有输出与确定性重建结果逐字节一致。
