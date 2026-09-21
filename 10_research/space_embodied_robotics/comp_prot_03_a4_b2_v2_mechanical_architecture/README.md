# COMP-PROT-03-A4-B2 — 12U 自主在轨服务航天器 V2.0 机械架构

> `STATUS: A4_B2_V2_MECHANICAL_ARCHITECTURE_CONTRACT_COMPLETE`  
> `DELIVERY_CLASS: TASKBOOK_AND_KNOWLEDGE_ONLY`  
> `SCIENTIFIC_GATE: false`  
> `V2_CAD_AUTHORING_AUTHORIZED: false`  
> `V1_0_MODIFIED: false`

## 本阶段完成了什么

本目录把 A4-B1 的工程视觉样机转成下一版机械系统设计的受控输入。交付的是任务书、V1→V2 修正矩阵、装配树、验收标准和进入下一阶段的人工 Gate；本阶段没有创建或修改任何 SolidWorks、URDF、仿真、控制或科学结果。

主入口：

- [12U 自主在轨服务航天器 V2.0 机械架构设计任务书](./12U_autonomous_servicing_spacecraft_v2_mechanical_architecture_taskbook.md)
- [V1.0 → V2.0 修正矩阵](./v1_to_v2_correction_matrix.md)
- [V2.0 装配树合同](./v2_assembly_tree.yaml)
- [V2.0 顶层建模与验收矩阵](./v2_review_and_acceptance_matrix.md)
- [阶段退出裁决](./v2_entry_gate.yaml)
- [本阶段核验报告](./verification_report.md)

配套知识入口：

- [Spacecraft Mechanical Design Knowledge Base](../../knowledge_base/spacecraft_mechanical_design/README.md)
- [Spacecraft Mechanical Design Agent](../../../.codex/agents/spacecraft-mechanical-design-agent.md)

## 当前合法结论

可以说：

- V2.0 机械架构、模块职责、证据状态和 CAD 顶层建模合同已经定义；
- A4-B1 V1.0 保持为可追溯的工程视觉基线；
- 下一阶段需要在独立 V2.0 目录中重新建模，并接受新的人工授权和退出审查。

不能说：

- V2.0 CAD 已建立；
- 已完成载荷、刚度、强度、模态、热、质量或惯量设计；
- 已完成发射适配、在轨捕获、碰撞安全、VLA、控制或数字孪生；
- OSAM-1、ETS-VII 或 DEOS 的成果证明本项目可飞行。

## 下一人工 Gate

`COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`

只有在人工批准后，才允许创建独立的：

`20_engineering/cad/Space_Embodied_Robot_CAD_V2_0/`

该 Gate 不自动授权 A5、动力学、URDF、Isaac/ROS、FEA、制造或硬件实施。
