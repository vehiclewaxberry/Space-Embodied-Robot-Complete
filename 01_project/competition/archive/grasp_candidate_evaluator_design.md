# grasp_candidate_evaluator 设计书（未实施）— 2026-07-11

定位：整个具身抓取项目的**关键软件中间层**。没有它，代理只能凭语言猜；有了它，
每个决策都物理接地。全部下层调用已验证求解器（证据见 existing_grasping_assets_audit.csv），
本层零新物理。

## 1. 接口规范

```python
@dataclass
class GraspCandidate:                      # 全部量在惯性系（捕获时刻对齐S系），SI单位
    grasp_point_id: str                    # 来自target JSON grasp_points（D-6唯一源）
    grasp_pose: SE3                        # frame C：位置+接近法线+工具滚转
    approach_direction: np.ndarray         # 单位矢量（默认=抓点法线，可偏置）
    capture_time: float                    # s；决定目标捕获瞬间姿态（torque-free传播）
    approach_velocity: float               # m/s 接触残速
    initial_joint_configuration: np.ndarray  # q0 ∈ R^6
    capture_mode: str                      # "point_3dof" | "rigid_6dof"（sim_07a已证其主导柔性激励）
    impedance_parameters: Optional[dict]   # v1: 记录透传，不进动力学（无接触模型，见§7）
    target_pose_covariance: Optional[np.ndarray]  # 6x6；v1经MC传播

@dataclass
class EvaluationResult:
    kinematic_feasibility: bool            # IK收敛+限位+可达
    ik_solution: np.ndarray                # q_c（后续全链复用）
    collision_margin: float                # m，全轨迹最小（B601胶囊链 vs 本体/帆板/目标keepout）
    manipulability: float                  # sqrt(det(J J^T)) @q_c + 最小奇异值
    base_attitude_change: float            # deg，接近轨迹积分峰值（sim_05动力学）
    capture_impulse: np.ndarray            # J_t (N·s) + 抓点力偶 L_grasp (N·m·s)
    post_capture_angular_velocity: float   # deg/s，|ω⁺|（rigidize按mode选解）
    flexible_modal_energy: float           # J（线性模态代理，ANCF抽检校准，见§4）
    wheel_momentum_required: float         # N·m·s = |H_c|
    propellant_required: float             # g（sim_08公式，lever/Isp取assumptions.yaml）
    uncertainty_risk: float                # P(违反任一安全门 | 协方差)，sigma点/MC
    overall_score: float                   # §5加权聚合
    provenance: dict                       # 各分量来源模块+版本+耗时（总控约束12）
```

## 2. 计算管线（单候选）
```
grasp_pose, capture_time
  → 目标捕获瞬姿态 R_T(t_c)         [rigid_body.propagate_torque_free — 已验证]
  → 抓点/法线转惯性系 → IK(q_c)      [新 evaluator/ik.py：阻尼最小二乘+限位]
  → 接近轨迹 q(t): q0→q_c           [新 approach_planner.py：任务空间min-jerk + J_g伪逆
                                     +（Case B成果落地后）3DOF零反作用QP]
  → 基座姿态积分、|H_bm·q̇|          [dynamics.FreeFloatingB601 — 22/22]
  → 碰撞裕度沿轨迹                   [新 collision.py：胶囊-盒距离，keepout来自JSON/SSOT]
  → 捕获冲量（mode分支）             [rigidize / rigidize_point_contact — 25/25]
  → ω⁺、|H_c|、J_t、L_grasp
  → 柔性能量                        [新 flex_surrogate.py：模态代理 ← ANCF标定]
  → 轮组/推进剂                     [新 actuator_cost.py ← sim_08公式函数化]
  → 不确定性风险                    [新 uncertainty.py：对(位姿,惯量,v_app)做sigma点重评]
  → overall_score                   [新 score.py + config/grasp_score_weights_v1.yaml]
```
性能预算：单候选确定性评价 <0.5 s（冲量微秒级、轨迹积分~百ms、代理~ms）；
sigma点13次重评 <5 s → G2全网格（6抓点×8相位×4速度×3构型≈600例）分钟级。

## 3. 模块与文件清单（全部新增，不改核心）
```
sim/sim_09_grasp_evaluator/
├── evaluator.py            # 编排层 evaluate(candidate)->EvaluationResult
├── ik.py                   # DLS-IK + 限位/收敛判据
├── approach_planner.py     # 任务空间min-jerk→qdot；Case B QP接口位
├── kinematics_metrics.py   # 可操作度/最小奇异值
├── collision.py            # 胶囊-盒最小距离（B601链几何来自URDF visual）
├── scenario.py             # 广义捕获场景（任意抓点/接近向/t_c）——扩展而非修改capture_impulse
├── flex_surrogate.py       # 线性模态代理 + ANCF抽检脚本
├── actuator_cost.py        # sim_08公式函数化
├── uncertainty.py          # sigma点/MC传播
├── score.py                # 聚合与归一化
├── tests/                  # 见§6
└── results/
config/grasp_score_weights_v1.yaml
```

## 4. 柔性能量代理的必要性声明
全ANCF每候选积分~20 s级（sim_07a实测124 s/6例），G2网格600例不可行。方案：
一次性用ANCF在(f₁×mode×激励幅值)网格上标定**线性模态响应面**（sim_07a已证响应主频=f₁、
近线性区：tip 5.2 mm=2.6%跨长），评价器查代理，终选前3名回ANCF精算复核。
代理误差目标<10%（对score排序不敏感性需在tests证明）。

## 5. 评分聚合
S = w_g·Q̂_geom − w_b·Δθ̂ − w_j·Ĵ − w_f·Ê_flex − w_a·Ĉ_act − w_u·R̂（^=按G0基线归一化）。
权重v1由G2帕累托前沿+层次分析给出并写入yaml（版本化）；报告中做权重敏感性分析
（±50%权重扰动下最优候选是否翻转）。

## 6. 测试计划（锚定回归——评价器必须复现已验证数字）
| 测试 | 锚点 |
|---|---|
| t1 评价器在"当前主抓点+固定+X接近+t_c=0"上运行 | ω⁺=3.063°/s、|H_c|=3.651 N·m·s、L_grasp≈0.122 N·m·s（C04/C06复现） |
| t2 IK往返：FK(IK(pose))=pose <1e-6 m/1e-6 rad；限位违反=0 | — |
| t3 接近轨迹动量守恒 <1e-10（复用sim_05测试器） | C10同级 |
| t4 柔性代理 vs ANCF 抽检≤10%（6点） | C12数据 |
| t5 uncertainty: 协方差→0 时 risk→0；3°位姿σ复现sim_04 POSE门统计趋势 | C01网格 |
| t6 score单调性：单变量恶化（杠杆↑/翻滚↑）score必须单调降 | — |

## 7. v1明确排除（防范围膨胀）
接触力学（峰值力/滑脱/抓取概率）——无接触模型，impedance_parameters仅透传记录，
接触烈度以|J_t|与L_grasp代理并在报告注明；真实Hunt-Crossley接触+变阻抗=硕士扩展。
视觉在线估计——协方差为输入参数，来源P1-1实验或文献值（引用出处）。
学习排序器（G4）——G0–G3闭合后再议。

—— 设计完毕，未写任何实现代码。批准后进入实施（预计1.5–2周，与P0-2/P0-3合并执行）。
