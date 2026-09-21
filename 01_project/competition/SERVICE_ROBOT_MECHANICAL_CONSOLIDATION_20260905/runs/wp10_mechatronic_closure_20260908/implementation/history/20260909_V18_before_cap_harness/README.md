# WP10 当前 V18：CHB 输入端接板与固定实体

同一候选新增5个安装实例，三态源清单970行，原965行保持。新板DRC0错误/0警告，铜路6检查/7反例和3项实体参数扰动通过；11件局部装配可查看。

- [查看本轮设计与图像](REVIEW.html)
- [原生CHB PCB](ecad/wp10_chb_input.kicad_pcb) / [实际铜图PDF](review/CHB_INPUT_LAYOUT_V18.pdf)
- [11件局部STEP](mechanical/chb_input_assembly.step) / [970行源清单](mechanical/CHB_INPUT_INSTANCE_PLAN.json)
- [设计说明与剩余工作](docs/hardware/CHB_INPUT_V18.md) / [独立只读复核](results/CHB_INPUT_READONLY_REVIEW_V18.json)
- [原37行责任表](SYSTEM_CLOSURE_MATRIX.csv) / [机器裁决](results/DELIVERY_DECISION.json)

整机设计仍开放。C203原板12项DRC、实际配对导线/保持、主馈和使能回线、保护配合、电池/PMM、停止回生/热动态及推进ICD未完成。本轮没有生成970件完整原生SolidWorks总装，也未获制造、上电或飞行放行。
