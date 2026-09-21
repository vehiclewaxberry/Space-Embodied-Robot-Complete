# 理论图谱入口

本目录把标准动力学符号、项目模块接口和机器证据连接起来。它不是新的求解器，也不证明任何超出 Gate 的科学结论。

## 文件

- [Paper 1 理论链](paper1_theory_chain.md)：零基础可读的人类入口。
- [Q6 模块装配理论—证据链](q6_assembly_theory_chain.md)：把预制接口装配接入 Q1–Q5 和既有 Assembly Wave A；不授权实施。
- [机器可读关系图](theory_map.yaml)：问题、理论节点、仿真和候选贡献之间的关系。
- [假设登记](assumption_registry.yaml)：每项假设的状态、影响和解锁条件。

## 关键边界

当前冻结证据从**终端捕获状态**开始。`sim01` 的现有作用是全刚化退化/姿态传播对照，不是 Hill/CW 轨道交会 Gate。因此，完整轨道交会动力学仅保留为未来上游接口。

`last_verified_head: b75352c1c226c0f3e9a4bc9c469b766e06f41616`
