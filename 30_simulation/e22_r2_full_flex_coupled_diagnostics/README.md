# E22 — R2 全柔性捕获后耦合诊断

本目录闭合 CHECKPOINT-A 的当前 R2 耦合诊断层，但不授予任务放行。它把已确认的 C07/C08/C09 空间质量矩阵、B601 PREGRASP 位形和 Round3 五模态太阳翼 ROM 组合为自由漂浮锁臂 reduced model，并对两类目标执行有限接触窗、锁定及 40 s 自由振铃。

## 机器裁决边界

- 当前数值车道：`RIGID_R2_CURRENT` 与 `SOLAR_R2_FLEX_CURRENT`。
- `LEGACY_R1_FLEX_HISTORICAL_REFERENCE_ONLY` 只保留历史记录；Legacy 24 kg/0.348 kg 参数不会进入当前 R2 矩阵，也不允许把跨版本差值全部归因于柔性。
- 主 Gate 车道为 `UNDAMPED_CONSERVATION_GATE`，强制 `C=0`。Round3 的暂定 `Crom` 仅进入隔离的 `PROVISIONAL_DAMPED_SENSITIVITY`，无 Gate 信用，也不构成衰减资格声明。
- 五模态在文件中的存储顺序为 `[B1,B2,B3,T1,T2]`；嵌套截断固定采用频率顺序 `[B1,T1,T2,B2,B3]`，对应存储索引 `[0,3,4,1,2]`。
- C07 的 6×6 空间质量矩阵已经包含左右各 0.78 kg 的太阳翼刚性运输项。`Gamma/Mqq` 是相对柔性坐标块，不会再次增加 1.56 kg；重复加入会由负控判为 `DOUBLE_COUNT_SOLAR_R2`。
- 接触采用 6D Delassus、等冲量半正弦窗与窗后残余锁定。20 ms 为 `PROVISIONAL`，机器扫掠 5/10/20/50/100 ms。锁定修正分别报告力冲量比与力偶冲量比，锁后残差分别报告 m/s 与 rad/s，不构造混合量纲范数。
- 任务分级使用组合体质心角动量 `L_C` 和 C08/C09 完整惯量张量得到的 `||I_C^-1 L_C||`，基座瞬时角速度仅作为响应量。线动量 `P`（N·s）、角动量 `L`（N·m·s）和模态正则动量各自独立记账，绝不拼接不同量纲后求范数；每个 P/L Gate 同时检查相对误差与 1e-12 的绝对误差。
- 线性 ROM 的逐侧重构必须同时满足 0.05 rad 转角/斜率和 0.03 m 节点/翼尖位移界限；越界 fail-closed。

## 权威与质量装配

预检逐字节钉住并语义消费：最新 ODR-GPT-01..06 转录、confirmed bridge 与 bridge Gate、bridged mass ledger、C07/C08/C09 组合账本、完整目标 CAD 惯量张量、PREGRASP 轨迹与 accepted FK、sim11 半正弦实现、common capture tumble axis、Round3 Gate/ROM/183-DOF 数据/重构算子/有效域以及 live threshold registry。

目标 CAD 到 S 系采用 `R_flip=diag(-1,-1,+1)`。CAD 原始 `Ixz` 与变换后的 S 系 `Ixz` 分字段报告。C08/C09 通过 `C07 + target spatial inertia` 逐项重构；目标抓点位置由组合账本和 accepted FK 独立闭合。

sim10 的冻结参数卡仍钉旧 threshold-registry hash，因此本目录明确记录 `sim10_authority_inheritance=NOT_INHERITED_THRESHOLD_HASH_DRIFT`。诊断使用 integration spec 明文的 2 deg/s、0.045 N·m·s、0.300 N·m·s 档，但标为 `PROVISIONAL_E22_DIAGNOSTIC`，不冒充 sim10 Gate。

## 独立 HF→ROM 子集验证

`R2_HF_TO_ROM_DYNAMIC_VALIDATION_V1.json` 从 Round3 NPZ 的 183-DOF `M/K` 自行广义特征分解，在名义 20 ms 等冲量基座加速度激励下，对比嵌套 3/4/5 模态的节点位移、翼尖、斜率、铰链相对角、扭转角和模态能量，并执行 Radau/BDF 交叉。此项最多只能形成 `E15_R2_LINEAR_SUBSET_PASS/FAIL`；历史 ANCF 状态始终保持 `REPEAT_ANCF_CERTIFICATION / NOT_INHERITED`。

本轮已知 Round3 五模态对 183-DOF 的最坏扭转峰值截断误差约 3.5%，高于 1% 预注册限。因此机器 Gate 应 fail-closed 为 HF→ROM 动态验证 HOLD；不得以有效质量覆盖率替代时域截断验证，也不得放宽阈值。Gate 直接钉住 CHECKPOINT-A 红队 `ROM5_DIMENSION_FALSIFIER_V1.json` 及其重算脚本，并逐字段对拍其 792 组合、最佳五维、最小六维和保留三弯曲七维结论；字段突变负控必须被拒绝。该 falsifier 表明最佳五维组合仍为 1.0829638%（失败）；最小通过组合需要重选六维、误差 0.6575809%，而保留三阶弯曲则需要七维。P2 当前上限为每翼五模，因此根因登记为合同约束内 ROM 维数不足，不静默换基或扩模。

## 复现

在项目根目录运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -B 30_simulation/e22_r2_full_flex_coupled_diagnostics/src/build_e22.py
python -B -m pytest -q 30_simulation/e22_r2_full_flex_coupled_diagnostics/tests/test_e22.py
python -B 30_simulation/e22_r2_full_flex_coupled_diagnostics/tests/independent_recompute.py
python -B 30_simulation/e22_r2_full_flex_coupled_diagnostics/tests/replay_determinism.py
```

主构建器串行使用单个求解器，先做权威预检，再生成案例矩阵、敏感度、HF→ROM 验证和机器 Gate。接触积分统一采用 `rtol=1e-10`、状态 `atol=1e-12`、更严格的 work/damping 账本 `atol=1e-15` 与 `max_step=T_c/50`；这避免低能量 BDF 案例的账本误差支配 1e-8 能量门。183-DOF 广义特征分解在调用内部固定 BLAS 单线程并显式采用 symmetric-definite `gvd` driver；比较对象是重构后的物理时域响应峰值，而不是近退化子空间内任意旋转的单个特征向量。五次隔离进程复算的字节哈希和物理指标由 `E22_DETERMINISM_REPLAY_V1.json` 冻结。任何 source hash、目标全张量、质量重构、矩阵 SPD、线性有效域或必要数值字段异常都会停止科学分级。

Gate 因自引用规则不钉后生成的 independent 报告。独立重算完成后生成 `E22_PACKAGE_MANIFEST_V1.json`，反向钉住 Gate、independent 和五次确定性复算报告；manifest 自身哈希由 CHECKPOINT-A 外层记录，从而避免 Gate↔independent 循环。

G07 只机器绑定 bounded-window 的 Radau/BDF implicit-ODE 交叉，并不把 40 s `PROJECTED_EXPONENTIAL` 的 P/H/E 投影当作独立算法验证。只读 0.5 s projected-versus-implicit witness 约为 `1.59e-5`，本轮记录为后续需机器绑定的诊断，不据此扩张 Gate 声明。

无论内部数值结果如何，本目录固定 `review_status=PENDING_OWNER_REVIEW`、`next_stage_authorized=false`、`release_credit=false`，且 harness `UNSAFE` 是独立事实。
