# Sim13 V4 Phase B3：合成分支双指接触与瞬态 soft-capture 诊断

本子包研究从 V4B2 单点摩擦接触向 B601 夹爪拓扑迈进的下一步：把原合成串联 `6R+2P` 明确改为“6R 臂端 palm + 两个并联独立 P 指”，在同一全浮动服务星—目标联合状态中计算左右两个接触点，并验证瞬态双边包络是否满足受限的 `SOFT_CAPTURE_TRANSIENT_CANDIDATE` 判据。

这不是当前 B601 接触模型。现行工程真值仍明确：左右接触框架、目标表面、静/动摩擦、接触刚度阻尼、允许接触压力、夹爪物理速度/时序和锁定变换全部为 null/HOLD。B3 的 pad、球、速度、摩擦和 soft-capture 阈值均为具名 synthetic provisional。

## URDF 拓扑消费边界

- 只读消费既有 B601 URDF 的拓扑事实：`gripper_link` 下有 `gripper_joint1/2` 两个独立 prismatic 子树，行程字面范围 `[0, 0.0715] m`。
- joint axis 在各自 joint frame 表达；按冻结 joint origin 旋转后，正运动分别沿 palm 的 `-Y/+Y`，即增大开口。
- URDF 的 `velocity=15 m/s` 只是一项未验证自动导出的 model limit，严禁用作物理闭合速度或时序。
- 不修改、不再生成、不落盘任何 URDF；实际左右接触框架仍为 null，B3 使用明确标记的合成 palm-frame pad。

## 预注册物理合同

- 服务星拓扑：free base + 6R serial arm + fixed palm + left/right independent P fingers。
- 每个指—球接触是 hard-finger frictional point contact：独立计算 `g_i, delta_i, n_i, F_ni, F_ti`，每点只传递三维力、不传递独立接触力矩；两物体在各自同一惯性公共点 `p_ci` 形成等大反向力。
- 服务星每个接触广义力包含公共点力矩移置；两点贡献线性叠加。
- 双指接触不得合并成一个平均法向、平均作用点或异量纲范数。
- 正常阻尼耗散与左右摩擦耗散分别积分；若后续加入 synthetic actuator，其功必须单独积分并以 `T+U+D-W_act` 审计。
- 线动量 `N·s`、角动量 `N·m·s`、作用反力 `N`、公共点搬移 `N·m`、虚功 `W`、左右 R/P 广义力和能量 `J` 分账，禁止把异量纲误差取同一标量最大值。

## 状态机

名义候选序列：

`PREGRASP_SEPARATED → BILATERAL_APPROACH → DUAL_CONTACT → SOFT_CAPTURE_TRANSIENT_CANDIDATE → BILATERAL_RELEASE`

允许存在短暂 `LEFT_ONLY_CONTACT` 或 `RIGHT_ONLY_CONTACT`，但单侧接触不得晋升 soft capture。`SOFT_CAPTURE_TRANSIENT_CANDIDATE` 至少要求：

- 左右接触同时为压缩非拉伸状态；
- 双接触连续保持达到 synthetic dwell；
- 两法向充分相对；
- 目标中心位于两 pad 的捕获走廊内；
- 侵入、相对速度和目标角速度均在合成阈值内；
- 左右接触法向/切向相对速度受限，且两个 P 指均未进入张开回弹；
- 两个接触账本、总 P/H 与 `T+U+D` 同时闭合。

候选状态只在同一段连续双接触区间内锁存；一旦单侧失联，连续 dwell 清零，若重新双边接触必须重新满足全部判据。双侧释放后再次接触直接 fail-closed。初始状态必须由左右实际 gap 证明为分离，禁止伪记 `PREGRASP_SEPARATED`。

## 抓取映射边界

在全部 qualifying 样本计算 `G=[[I,I],[skew(r_L),skew(r_R)]]`，并用 `L_ref=0.5‖p_R-p_L‖` 归一化力矩行。两个不同 hard-finger 力作用点的线性化映射秩应为 5；沿两接触点连线的纯力矩不可生成。因此 B3 必须保持 `full_6d_wrench_span=false`、`full_6d_force_closure=false`，双点接触不等于六维稳定抓取。

禁止状态与声明：`LOCKED`、`GRASP_SUCCESS`、`T_gripper_target_locked`、released attached target、current-system contact、formal NC19、production、release、next stage。

当前状态：`CONTRACT_FROZEN__IMPLEMENTATION_NOT_YET_AUDITED__NO_GATE_CREDIT`。
