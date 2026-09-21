# V2 System Mechanical Design Input Package

> `STATUS: B2_5_SYSTEM_MECHANICAL_DESIGN_INPUT_PACKAGE_COMPLETE`  
> `PHASE: COMP-PROT-03-A4-B2.5`  
> `DELIVERY_CLASS: PRE_CAD_DESIGN_INPUTS_ONLY`  
> `B3_CAD_AUTHORING_AUTHORIZED: false`  
> `NO_SIMULATION / NO_FEA / NO_URDF_CHANGE / NO_HARDWARE_ACTION`

## 目的

本包把 A4-B2 的机械架构合同转换为未来 V2 System Mechanical CAD 可以消费的设计输入。它回答：

1. V2 要满足哪些任务和机械系统需求；
2. 哪些构型、frame、接口和参数已经绑定；
3. 哪些对象只有 volume owner 或 reserved interface；
4. 每一项质量由谁拥有、能否进入 CAD/动力学；
5. 哪些未知量必须保持 null；
6. B3 获批后按什么顺序建立 Master Skeleton 和子装配。

本包不是 SolidWorks 模型，也不授权创建 V2 CAD。

## 读取顺序

1. [范围与状态](./00_governance/design_input_scope_and_status.md)
2. [系统需求冻结表](./01_mission_requirements/V2_system_requirements_baseline.md)
3. [机器可读系统需求](./01_mission_requirements/V2_system_requirements_baseline.yaml)
4. [构型基线](./02_spacecraft_configuration/V2_configuration_baseline.yaml)
5. [机械 ICD](./03_mechanical_interfaces/V2_mechanical_ICD.md)
6. [接口登记](./03_mechanical_interfaces/V2_interface_register.yaml)
7. [舱段与 volume owner](./04_subsystem_layout/V2_subsystem_volume_owner_register.yaml)
8. [维护与 keepout 计划](./04_subsystem_layout/V2_serviceability_and_keepout_plan.md)
9. [质量所有权表](./05_mass_budget/V2_mass_ownership_table.csv)
10. [质量使用说明](./05_mass_budget/V2_mass_ownership_notes.md)
11. [未知量登记](./06_unknown_register/V2_unknown_register.yaml)
12. [Master Skeleton 参数合同](./07_cad_preparation/V2_master_skeleton_parameter_contract.yaml)
13. [B3 CAD 建设计划](./07_cad_preparation/V2_B3_CAD_construction_plan.md)
14. [评审视图计划](./07_cad_preparation/V2_review_view_plan.yaml)
15. [预 CAD 结构审查](./08_review/pre_cad_structural_review_report.md)
16. [B2.5 退出裁决](./08_review/B2_5_exit_gate.yaml)
17. [机器验收报告](./08_review/verification_report.md)
18. [交付物 SHA-256 清单](./input_packet_hash_manifest.csv)

## 上游与知识入口

- A4-B2 架构合同：`10_research/space_embodied_robotics/comp_prot_03_a4_b2_v2_mechanical_architecture/`
- 机械设计知识库：`10_research/knowledge_base/spacecraft_mechanical_design/`
- CAD pattern library：`10_research/knowledge_base/spacecraft_mechanical_design/07_CAD_reference_patterns/`
- Spacecraft Mechanical Design Agent：`.codex/agents/spacecraft-mechanical-design-agent.md`
- Structural Review Agent：`.codex/agents/structural-review-agent.md`

## 当前裁决

```text
B2.5 design inputs: COMPLETE
B3 request package: READY_TO_REQUEST
B3 CAD authoring: NOT_AUTHORIZED
V1.0: UNMODIFIED
physical qualification: NOT_STARTED
```

下一人工 Gate：

`COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`
