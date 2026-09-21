# R2 MuJoCo 捕获前诊断对抗审查 V1

日期：2026-08-27  
对象：`R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_V1`  
审查边界：合同、源锁、三 lane 语义、非接触设置、单位/守恒账本、控制重放及权限边界。  
审查状态：**允许执行诊断；技术 PASS/REPEAT_REQUIRED 必须由机器 Gate 决定；Owner Review 仍待完成。**

本审查不是机器 Gate，也不授予父机械、动力学、控制、SAFE、Sim13、非 ABORT、下一阶段或发布信用。

## 对抗问题与处置

| ID | 对抗问题 | 失真风险 | V1 处置/判据 |
| --- | --- | --- | --- |
| AR-01 | URDF 转换是否静默改写质量、惯量、轴、限位或名字？ | 用 MuJoCo 自动推断替代 accepted 真值 | 源 URDF 哈希只读绑定；逐 link 质量/质心/惯量、全树 FK、轴、限位和 B601 子树逐项核对；禁止 inertia-from-geom authority |
| AR-02 | 静态体融合或坐标对齐是否改变 frame 语义？ | body/joint 映射失真 | 保留源名字和父子树，`fusestatic=false`；自由根显式 `align=false`；映射收据必须可追溯 |
| AR-03 | Lane B equality 是否被包装成理想刚性 KKT？ | 错误获得约束闭合信用 | 明确标记 `MUJOCO_SOFT_EQUALITY_LOCK_DIAGNOSTIC`；检查漂移和约束功；`exact_kkt_lock_reproduced_claim=false` |
| AR-04 | `tauP=0` 是否被误写为夹爪锁止？ | 隐藏 2P 自由运动 | Lane C 保留 2P 且无 equality；自由响应必须能区分于 Lane B，并对照非零加速度机理 |
| AR-05 | 根基座是否仍由零动量关系代数重构？ | MuJoCo 未形成独立 plant | `spacecraft_bus` 使用真实 freejoint，由 MuJoCo 积分位置、四元数与 twist；移除 freejoint 的负控应被抓获 |
| AR-06 | 是否用阻尼、摩擦、弹簧或外力“修好”守恒？ | 数值稳定掩盖物理错误 | 零重力，无根阻尼/摩擦/虚拟弹簧/姿态稳定外力；独立逐 link 复算 `P`、固定原点 `H_O` 和功—能量 |
| AR-07 | 是否把 `subtreeangmom` 当成固定原点角动量？ | 参考点混用 | 固定惯性原点 `H_O` 由包内独立账本逐 link 计算；子树质心量不得替代 |
| AR-08 | 是否直接对 `rad` 与 `m` 混合矩阵做范数 Gate？ | 无量纲不合法 | 质量阵交叉只使用冻结 DG1 尺度；线动量、角动量和能量分别按 SI 单位审计 |
| AR-09 | 6R 是否用位置伺服冒充力矩输入？ | 控制物理语义改变 | 只用 direct-drive torque motor；RK4 每个子步实时重算反馈；回调次数进入 Gate |
| AR-10 | 受控/无控比较是否跨 5D/6D 或硬编码旧比值？ | 伪改善结论 | 只比较同维配对；阈值按跨引擎和步长合同判断，旧 `0.3829.../0.6687...` 仅是参考，不是绝对硬编码真值 |
| AR-11 | XML 无接触是否被误称为碰撞安全？ | 提前取得 M01/capture 信用 | 所有 geom `contype=0`、`conaffinity=0`，并检查 `ncon=0`；合法结论仅是“V1 未启用接触”，不是 clearance/collision-free/capture success |
| AR-12 | 运行环境是否污染系统或漂移版本？ | 无法复现或依赖差异 | `uv --no-project` 隔离运行，精确固定 Python 3.13、MuJoCo 3.12.0、NumPy 2.5.2、SciPy 1.16.3；环境不符则 fail-closed |
| AR-13 | pytest、可视化或 XML 可编译是否被当成科学 PASS？ | 绕过机器裁决 | 唯一结果入口是 `results/R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json`；六组 Gate 必须全真 |
| AR-14 | 局部诊断是否改写父 Gate 或权限？ | 越权发布 | authority 边界逐项冻结为 false；权限升级负控必须被抓获；源锁声明 `mutation_authorized=false` |

## 本轮必须保持的事实

1. 三条 lane 都必须从同一哈希绑定 Unified R2 URDF 确定性生成。
2. Lane A 是坐标移除；Lane B 是 MuJoCo 软 equality；Lane C 是 `tauP=0` 的解锁负控，三者不得合并解释。
3. V1 无碰撞、无接触、无目标附着、无柔性验证、无硬件执行器信用。
4. 四组控制重放只审计 12 ms 捕获前 weighted-twist velocity servo，不证明位姿/姿态跟踪或稳定性。
5. `RESEARCH_EXECUTION_GO=true` 只批准研究运行；`PARENT_NEXT_STAGE_AUTHORIZED=false` 不因局部 Gate 结果改变。

## 对机器结果的裁决规则

- Gate 文件不存在：`RUN_NOT_YET_ADJUDICATED`。
- Gate 文件存在且 `gate_pass=false`：只能使用合同中的 `...ATTEMPTED_REPEAT_REQUIRED__NO_AUTHORITY_UPGRADE`，并保留失败检查。
- Gate 文件存在且 `gate_pass=true`：最多使用合同中的完整 `...CROSS_SOLVER_DIAGNOSTIC_PASS__...HOLD`；不得截断后缀造成父级已放行的错觉。
- 任一 authority 字段为 true：本审查直接判权限边界失败，即使数值检查通过也不得发布局部 PASS。

## 审查结论

该方案的模型分层、三 lane 设计和 fail-closed 权限边界足以支持**隔离诊断执行**。本审查不预判数值结果；最终技术结论、失败项与可引用主张必须逐字来自机器 Gate。Owner Review 之前，`next_stage_authorized=false`、`release_credit=false`。

