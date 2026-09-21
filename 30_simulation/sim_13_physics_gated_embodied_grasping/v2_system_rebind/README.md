# Sim13 V2 全系统重绑定前置实现

## 当前裁决

本目录已经形成可执行的 **source-only prebind**：它能严格解析 Unified R2 的
19-link/18-joint/16-physical/3-frame-only/8-DOF 合同，生成 12 门只读权威快照，
验证零总动量下的自由漂浮基座反作用，并执行接触输入前检。

它不是已绑定的仿真环境。当前系统接口和系统 URDF 均不存在，Route-C 排除尚未获
Owner 接受，因此运行时永久施加 `PREBIND_SCOPE_LOCK`：任一非 ABORT 请求均由安全
屏蔽器改为 canonical ABORT。

## 已实现

- 固定路径、bytes、SHA-256、schema、verdict 和 `next_stage_authorized` 的证据解析；
- 8 个继承门 + 4 个机械 V2 门，调用方不能传入 gate 或制造 `all_pass()`；
- 严格系统模型：固定关节 `gripper_joint` 不进入 `q/dq`，D 与 M 数值变换相同但身份
  独立，物理载荷路径不经过 M；
- 通用 fixed/revolute/prismatic 树形质量矩阵、`Hbb/Hbm`、零动量基座速度、动量、
  动能和单链接质量/惯量敏感性；
- 非主轴自由刚体 Euler 方程 + 四元数 RK4；
- 单位接触法向、有限接触窗、双指 manifold、摩擦锥、压力、保持力和新鲜锁定回执
  的 fail-closed 前检；
- sim05/sim06/sim10/E19 历史产物的 bytes+SHA-256 锚定、存储精度对拍及当前重跑
  输入审计；历史 Gate 不继承为 Unified R2 PASS；
- Unified R2 16 个物理链接的服务星聚合与理想瞬时两刚体硬锁动量极限；该极限不提供
  接触力或接触时程；
- NC01--NC20 的机器注册表、单故障执行器和“不运行不得计 PASS”的汇总器；当前
  15 项正式前置执行 PASS、0 项 FAIL，NC15/NC16/NC18/NC19/NC20 因生产依赖缺失
  保持 `NOT_RUN_DEPENDENCY_HOLD`。

## 明确未实现／未授权

- 未生成或写入 `.urdf`；
- 未实例化 `MECH_RL_SYSTEM_INTERFACE_V2.yaml`；
- 未通过正式系统绑定门、运行时门、生产动力学门或接触抓取门；
- 动量后端是规定关节运动模型，不是力矩驱动正向动力学；
- 半正弦窗是等冲量解析夹具，不是持续接触求解器；20 ms 仍为 provisional；
- NC15/NC16/NC18/NC19/NC20 尚未形成可执行的合格生产基线，不能补写为 PASS；
- 当前 sim05/sim06/sim10 重新执行为 `HOLD_INPUT_PATH_OR_HASH_DRIFT`：REORG04 后旧默认
  输入路径不存在，且 sim10 冻结阈值注册表哈希与现行文件哈希不一致；
- 未授权训练、接触抓取、硬件运动、飞行或生产用途。

## 进入真实抓取仿真的剩余顺序

1. Owner 对本轮 Route-C 排除和低内存风险作新鲜、单次、run-specific 接受；
2. 由冻结生成器生成并验证 Unified R2 V2 URDF，再实例化系统接口；
3. 新建 action/context digest、新鲜度和防重放均闭合的生产运行时版本；
4. 修复并显式版本化 sim05/sim06/sim10 重跑输入，随后完成力矩驱动 8-DOF 正向
   动力学；历史产物只作哈希锚点；
5. 接入双指窄相接触、20 ms 实测替换、摩擦/压力/保持力和锁定回执；
6. 在对应生产基线形成后执行剩余 NC15/NC16/NC18/NC19/NC20；20/20 完成后才可
   评审抓取仿真入口。

运行本目录验证：

```powershell
python -B validate_prebind_v2.py
```

正式前置负对照证据可单独复现：

```powershell
python -B run_negative_controls_prebind_v1.py
```

机器裁决只认 `results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json`，其
`next_stage_authorized` 必须保持 `false`。
