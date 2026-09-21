# ODR-60 Option-A 查询基础设施 V1

## 1. 工程定位

本包只关闭两个“方法/接口存在性”子项：

1. 在不改写冻结 `ROUTE_C_EXACT_SWEEP_V9F.py` 的前提下，提供一个受权限与内存门约束的单姿态只读适配器；
2. 提供一个 `SAFE / UNSAFE / UNKNOWN` fail-closed 的线性关节空间连续边证书内核。

它不签发系统碰撞、路径搜索、动力学仿真或发布权限。当前合法操作仅为静态审计与合成夹具测试。

## 2. 单姿态适配器的真实边界

`exact_q_trace_adapter.py` 在冻结 V9F 的 `main()` 内部闭包已经构造、但任务扫描和三个声明输出写入尚未发生的位置截获执行帧；对传入的六维 `q` 只调用一次局部 `eval_clearance`，并折叠姿态不变的 own-host 最小值。

该查询必须命名为：

```text
ROUTE_C_HARNESS_POINTWISE_MESH_CLEARANCE_ONLY
```

不能命名为“150 对象系统 exact-q”，原因包括：

- V9F 只返回线束中心线相对局部三角场的全局标量最小值，不返回 11,166 个非例外对象对的稳定 pair ID、逐对 lower bound 或最近点证据；
- 当前 V9F mesh pack 的 `vendor_base_link` 仍来自旧 raw URDF mesh，source SHA256 为 `22641C079014FE968702393F61E7F7F1A8F80C6C1DF45A61E31545F6EAFF3B65`，没有绑定现行 V2 operational proxy；
- 线束中心线间距为 1.5 mm，尚无 capsule-chain 或空间离散 Hausdorff 降额；
- V9F 的 `evaluated_continuous` 字段仅统计有限采样段，不能解释为连续碰撞证明。

实际当前几何查询不再接受调用者自报的 token 或 `memory_gate_passed` 布尔值。执行入口只读取本机实时可用物理内存，并要求构建时钉死的、项目内 Owner 单次授权回执；低于 6 GiB 时还必须存在同一 `run_id`、同一 nonce 的风险确认回执，且 `memory_gate_passed` 保持 `false`。每个 `run_id` 在导入 V9F 前原子写入一次消费记录，禁止复用。当前构建的授权回执钉扎故意为空，因此当前几何查询 fail-closed 不可执行；本包没有使用 override，也没有执行当前 V9F 几何。

适配器对副作用的证明仅限“从 `main()` 开始到截获点，V9F 三个声明输出工件未变化”。它不宣称导入期或未声明路径绝对零副作用；Python trace 与环境变量均恢复。若未来获得单次授权，唯一新增的声明写入是该 `run_id` 的消费/风险回执。

## 3. 连续边证书合同

对对象对 A/B，必须先有哈希绑定的全局运动上界：

```text
d_H(G_i(q), G_i(q')) <= sum_k L[i,k] * |q_k - q'_k|
```

实现接收的相对系数必须已经是两对象贡献之和 `L[A,k] + L[B,k]`。对区间 `[a,b]` 的中点 `c`，从中点到区间任意点的相对运动界为：

```text
B_AB = 0.5 * sum_k ((L[A,k] + L[B,k]) * |q_k(b) - q_k(a)|)
lower_bound = clearance(c) - B_AB
```

只有 `lower_bound` **严格大于** `required_clearance + numerical_reserve` 才能签发该叶区间 `SAFE_CERTIFIED`。`required_clearance` 不允许为负；oracle 返回 `FAIL` 时直接 UNSAFE，恰好等于门槛、负间隙或余量不足均不得 SAFE。无法证明时二分递归；缺系数、非数值/NaN、后端异常、场景离散状态改变、深度/分辨率耗尽一律 `UNKNOWN_ABORT`。

若 motion bound 宣称系统级权威，还必须同时绑定 pair ID、两侧对象 ID/几何哈希、场景状态哈希、ACM 哈希、oracle 实现哈希、关节单位与有效 q 域；只有 64 位字符串而无这些字段时返回 UNKNOWN。

## 4. 当前机器状态

```text
adapter static audit                 PASS
synthetic/adversarial pytest         17/17 PASS
current V9F geometry query           NOT EXECUTED
accepted run-authority hash pin      absent
binary64 golden parity               NOT EXECUTED
V2 base proxy bound into V9F         false
system pair exact/lower-bound API     absent
system object motion coefficients     absent
system edge evaluated                false
path search executed                  false
next stage authorized                 false
release credit                        false
method readiness                      STATIC_FIXTURES_PASS_ONLY / SYSTEM HOLD
```

当前系统 registry 仍是 150 对象、11,175 对；除 9 个相邻例外外，11,166 对保持 fail-closed 未评估。

## 5. 复现

在项目根目录运行：

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/build_query_infrastructure_gate.py
```

构建器只执行静态审计与合成测试，并确定性重建：

- `FROZEN_V9F_STATIC_ADAPTER_AUDIT_V1.json`
- `QUERY_INFRASTRUCTURE_GATE_V1.json`
- `QUERY_INFRASTRUCTURE_SHA256_V1.csv`

## 6. 系统绑定前的剩余输入

- 150 对象逐对 exact 或保守 lower-bound API，远场 pair 也不得以 NaN/跳过代替；
- V2 `base_link` operational proxy 的运行时绑定；
- 9 个 C 类线束对象的 capsule-chain，或显式中心线离散 Hausdorff 降额；
- 每对象、每关节、哈希绑定的全局运动系数；
- M01 的 Solar/HDRM/目标/夹爪离散状态与完整 ACM；
- 11,166 个非例外 pair 的覆盖；
- Owner 对 Option-A 与本次运行的明确授权，以及运行时内存准入。

这些条件满足后，才允许执行单姿态系统对拍；通过后再对候选边逐边发证，最后才允许路径搜索和动力学交接。
