# 当前可查看候选：V30（2026-09-11）

端接、绝缘盖与局部导线已纳入本候选和总 BOM。查看 [V30 报告](coupled_closure/REVIEW_V30.html)。整机热、布局及推进接口仍开放；旧 V29 选型 BOM 已留存历史，不将旧包哈希套用到现行追加 BOM。

> 当前工作入口：[V29 端接与载板改件](coupled_closure/REVIEW_V29.html)。211位号/677针脚记录，整机仍未闭环；下列旧版发布信息按其原版本理解。

# WP10 最新联合候选（2026-09-10）

从[电气—热控—推进联合查看页](coupled_closure/REVIEW.html)、[完整报告](coupled_closure/README.md)与[候选增量包](coupled_closure/WP10_COUPLED_CANDIDATE.zip)进入。输入来自V26电气/PCB与V21的974实例计划；43个决定性来源文件锁定。已统一207位号/673针脚网络，完成跨相位电热预算、有限推进脉冲边界检查和两套局部参数化STEP，35项针对性测试通过。

局部机械设计共8种项目零件、17个有效实体；候选整机位置经25份真实STEP的窄相位检查三态各18处交叠，已拒绝，尚未装入974实例整机。连续运行热分析发现超限，实际推进ICD、任务工况与整机逐link物性仍待绑定。[本次机器状态](coupled_closure/DELIVERY_STATUS.json)明确保留整机未闭环；未制造、上电或授予飞行信用。下方V18说明为历史入口，不代表最新版本。

---

# WP10 V18 历史：CHB 输入端接板与固定实体

同一候选新增5个安装实例，三态源清单970行，原965行保持。新板DRC0错误/0警告，铜路6检查/7反例和3项实体参数扰动通过；11件局部装配可查看。

- [查看本轮设计与图像](REVIEW.html)
- [原生CHB PCB](ecad/wp10_chb_input.kicad_pcb) / [实际铜图PDF](review/CHB_INPUT_LAYOUT_V18.pdf)
- [11件局部STEP](mechanical/chb_input_assembly.step) / [970行源清单](mechanical/CHB_INPUT_INSTANCE_PLAN.json)
- [设计说明与剩余工作](docs/hardware/CHB_INPUT_V18.md) / [独立只读复核](results/CHB_INPUT_READONLY_REVIEW_V18.json)
- [原37行责任表](SYSTEM_CLOSURE_MATRIX.csv) / [机器裁决](results/DELIVERY_DECISION.json)

整机设计仍开放。C203原板12项DRC、实际配对导线/保持、主馈和使能回线、保护配合、电池/PMM、停止回生/热动态及推进ICD未完成。本轮没有生成970件完整原生SolidWorks总装，也未获制造、上电或飞行放行。
