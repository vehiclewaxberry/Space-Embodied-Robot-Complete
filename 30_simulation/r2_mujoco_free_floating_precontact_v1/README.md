# R2 MuJoCo 自由漂浮捕获前跨求解器诊断 V1

本包是 CURRENT R2 的 **append-only、隔离、刚体、捕获前、非接触** MuJoCo 研究增量。它把哈希绑定的 Unified R2 URDF 转换为可追溯 MJCF，让 `spacecraft_bus` 通过 `servicer_free` 成为由 MuJoCo 独立积分的位置、四元数与 twist 状态，并与现行解析/自研后端进行运动学、质量、动力学、守恒量和 12 ms 控制重放交叉诊断。

唯一机器结论入口是：

```text
results/R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json
```

当前已执行结果为 6/6 Gate PASS；独立验证 48/48、定向单元测试 14/14。机器主张为：

```text
R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_PASS__PARENT_MECHANICAL_DYNAMICS_CONTROL_SAFE_SIM13_CONTACT_AND_RELEASE_HOLD
```

其中 `...HOLD` 是主张的一部分，不得省略。后续任何重建仍只能读取 Gate 中的 `gate_pass`、`achieved_claim` 与逐组检查；测试通过或场景可视化均不能替代机器 Gate。

## 权限边界

研究执行与父级授权必须分开读取：

```text
RESEARCH_EXECUTION_GO = true
PARENT_NEXT_STAGE_AUTHORIZED = false
```

只有本包 Gate 全部通过时，最高合法主张才是：

```text
R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_PASS__PARENT_MECHANICAL_DYNAMICS_CONTROL_SAFE_SIM13_CONTACT_AND_RELEASE_HOLD
```

若任一 Gate 失败，则只能使用合同中的 `...ATTEMPTED_REPEAT_REQUIRED__NO_AUTHORITY_UPGRADE`。无论本包 Gate 结果如何，以下权限均保持 `false`：父机械/动力学/控制 Gate 改写、`control_valid`、`hardware_valid`、`flex_valid`、`collision_valid`、`contact_valid`、`capture_success`、`target_attached`、`m01_path_bound`、`safe_credit`、`sim13_credit`、`non_abort_authorized`、`next_stage_authorized` 与 `release_credit`。

## 冻结模型

- 源模型：哈希绑定、只读的 19-link/18-joint Unified R2 URDF；accepted B601 URDF 同时作为子树真值绑定。
- 质量：`31.022864807342987 kg`；质量、质心和惯量来自源 URDF，不允许由 visual/collision geom 反算或替换。
- 构型：6 个转动关节、2 个夹爪移动关节，`qP*=[0.03575, 0.03575] m`。
- 根状态：`spacecraft_bus` 下的 `freejoint name="servicer_free" align="false"`。
- 环境：`gravity=[0,0,0]`；不添加根阻尼、摩擦、虚拟弹簧或人工姿态稳定外力。
- 接触：所有 V1 geom 均应为 `contype=0`、`conaffinity=0`，碰撞与接触关闭；目标和柔性附件动力学均不在本包中。
- 驱动：仅 6R 理想 direct-drive torque；没有电机、减速器、驱动器、轮组、饱和、带宽、延迟、热或故障信用。

## 三条 2P lane

| lane | 状态维数 | 锁止语义 | 合法解释 |
| --- | ---: | --- | --- |
| `LOCKED_2P_REDUCED_6R` | 6 | `EXACT_COORDINATE_REMOVAL` | 将 2P 从运动自由度移除并固定于 `qP*`，用于与现行约化 6R 模型做最严格对照；不输出 2P 约束反力 |
| `LOCKED_2P_EQUALITY_6R2P` | 8 | `MUJOCO_SOFT_EQUALITY_LOCK_DIAGNOSTIC` | 保留 2P 并使用 MuJoCo equality，记录漂移、约束力与约束功；这是软约束求解器诊断，**不是精确刚性 KKT** |
| `FREE_2P_ZERO_FORCE_NEGATIVE_CONTROL` | 8 | `UNLOCKED_TAUP_ZERO_IS_NOT_LOCK` | 保留 2P、`tauP=0` 且不锁止，用于验证“零驱动力不等于锁止”，并对照自由模式非零 2P 加速度机理 |

不得把 Lane B 写成 `EXACT_KKT_LOCK_REPRODUCED`；只有 Lane A 的坐标移除可与现行理想消元模型做严格语义对照。

## 证据结构

```text
00_authority/   合同、源哈希锁、精确环境依赖
01_model/       三条确定性 MJCF 与 URDF→MJCF 映射
02_conversion/  转换、构建、跨后端复算与 Gate 生成器
03_controller/  控制重放语义说明
04_validation/  独立验证入口（如生成）
05_runs/        运行摘要
06_tests/       定向测试
07_reviews/     对抗审查
results/        环境、转换、证据、负控、Gate、manifest 与 SHA 表
```

机器 Gate 分为六组：

1. `MJ-G0_BASELINE_PROTECTION`：源 pin、环境、确定性转换、三 lane、自由根与非接触边界；
2. `MJ-G1_KINEMATICS_AND_MASS`：19/18 清单、B601 子树、逐 link 质量/惯量、FK 与映射；
3. `MJ-G2_STATIC_DYNAMICS_CROSS`：无量纲质量阵、Jacobian、bias、加速度及 2P 自由负控；
4. `MJ-G3_FREE_FLOATING_CONSERVATION`：独立逐 link 的 `P`、固定惯性原点 `H_O`、动能和做功账本；
5. `MJ-G4_TIME_DOMAIN_CONTROL_REPLAY`：5D/6D 四组 12 ms 运行、RK4 子步反馈重算及当前 DOP853 参考交叉；
6. `MJ-G5_NUMERICAL_SENSITIVITY_AND_NEGATIVE_CONTROLS`：步长加密、软 equality 边界及源锁/单位/轴向/质量/权限等负控。

混合 `rad` 与 `m` 的质量阵只允许按冻结 DG1 参考尺度无量纲化后比较。线动量 `P` 的单位是 `kg·m/s`，关于固定惯性原点的角动量 `H_O` 是 `kg·m²/s`，控制做功与动能是 `J`；三者不得混为一个标量残差。MuJoCo 的子树质心角动量不能替代固定惯性原点 `H_O` 账本。

## 隔离环境与复现

V1 精确冻结 Python 3.13、MuJoCo 3.12.0、NumPy 2.5.2、SciPy 1.16.3。使用 `uv` 临时隔离环境，不修改系统默认 Python，也不在项目目录创建 `.venv`：

```powershell
Set-Location 'F:\China Graduate Future Flight Vehicle Innovation Competition\30_simulation\r2_mujoco_free_floating_precontact_v1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:BLIS_NUM_THREADS='1'
$env:NUMEXPR_NUM_THREADS='1'

uv run --no-project --python 3.13 --with-requirements 00_authority/requirements-mujoco-v1.txt python -B 02_conversion/r2_mujoco_precontact_v1.py
uv run --no-project --python 3.13 --with-requirements 00_authority/requirements-mujoco-v1.txt python -B -m unittest discover -s 06_tests -p 'test_r2_mujoco_free_floating_precontact_v1.py'
uv run --no-project --python 3.13 --with-requirements 00_authority/requirements-mujoco-v1.txt python -B 04_validation/independent_validate_mujoco_v1.py
```

运行不要求 GPU 或渲染。环境收据只证明实际解释器和依赖与合同一致，不赋予科学或发布权限。构建后应先读机器 Gate，再核对 manifest/SHA；不得从控制曲线、XML 可加载或单元测试单独推断 PASS。

## 明确不在 V1 内

本包不执行 M01 路径搜索、clearance/pair universe、连续碰撞证书、接触/冲量/抓持、目标附着、AS_BUILT 接触参数、太阳翼 14 模态验证、硬件执行器或轮组验证、SAFE、Sim13、非 ABORT、RL/VLA 物理门控训练、下一阶段或发布。后续即使加入 weld，也只能表示 `ASSUMED_LATCHED_STATE_FOR_POST_CAPTURE_DYNAMICS`，不能表示机构已成功捕获。
