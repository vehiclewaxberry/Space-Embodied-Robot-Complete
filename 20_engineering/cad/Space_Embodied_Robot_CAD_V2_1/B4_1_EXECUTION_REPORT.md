# B4-1 V2.1 机械机构设计执行报告

## 结论

已建立独立的 `Space_Embodied_Robot_CAD_V2_1` 原生参考级 CAD，并完成来源准入、
主承力结构语义深化、左右太阳翼独立装配、七个任务状态、证据链和机器验收。

最终门禁不是“机构全部完成”，而是：

`B4_1_NATIVE_REFERENCE_CAD_BUILT_ACCEPTANCE_HOLD`

验收脚本最终输出 `B4_1_ACCEPTANCE_HOLD`，退出码 `2`，
`0 FAIL / 17 HOLD / 6 PASS`。因此当前模型可用于评审参考、后续参数签发和
物理机构深化入口，不可作为可制造、可部署、动力学、干涉安全或飞行合规模型发布。

## 已完成

- V2.0 最终封存只读复核：57/57 SHA-256 与字节数一致，缺失 0、额外原生文件 0。
- V2.1 原生库存：51 `SLDPRT` + 9 `SLDASM` = 60；顶层装配为
  `Assembly/Spacecraft_Service_Vehicle_V2_1.SLDASM`。
- 主结构采用框—纵梁—局部扩散的参考拓扑；B601 使用 V2.0 子装配，只读继承。
- 左右太阳翼保留独立对象、接口、装配和失败状态。
- 顶层七态：`STOWED`、`DEPLOYED_NOMINAL`、`DEPLOY_FAILED_BOTH`、
  `L_FAIL`、`R_FAIL`、`PARTIAL`、`SERVICE`。
- 机器检查 checkpoint：60/60 重开、12/12 bbox、18/18 零实体、
  7/7 状态匹配、0 failure。
- 来源链：37/37 FEATURE_ID 唯一，全部外部 source key 映射至
  commit/hash/license/adoption contract；禁止直接等比例放大。
- 装配依赖：120 条依赖记录，仅有 V2.1 内部路径与终封匹配的
  V2.0/B601 外部路径。
- 评审视图：8 张原图与 8 张带 claim-limit 注释图。

## 必须保留的 HOLD

- 18 个太阳翼根部对象是零实体具名 reference，不是实体根支座、铰链、扭簧、
  HDRM、止挡、线束或应变释放设计。
- 七态是表示/场景入口，不是部署运动学、故障分析或碰撞验证。
- C1 开口只有规则和登记，没有原生甲板开口。
- C5 收拢叠厚 `238.3 mm > 226.3 mm` 仍开放，不得宣称部署器包络合规。
- SpeedPak/性能配置 0；不能称已建立状态×性能矩阵。
- 原生 `SLDDRW` 0、发布 PDF 0；图纸登记表不等于工程图交付。
- 14 行紧固件登记均为占位/UNKNOWN；没有签发规格、数量、工具轴或可达性证据。
- `q0` 静态 B601 代理不是工作空间或轨迹扫掠；相机 frame/FOV 未签发。
- 材料、密度、质量覆盖、强度、刚度、模态、FEA、动力学、接触、控制、
  低冲击、寿命、制造和飞行合规均未评估。
- `System_Equations_V2_1.txt` 是文本权威，SolidWorks 原生外部方程链接因
  D-EQ-01 仍为 HOLD；当前以 `PARAM_*` 自定义属性镜像对拍。

## 权威入口

- `evidence/B4_1_GATE_STATUS.yaml`
- `evidence/acceptance/latest_run_state.json`
- `evidence/acceptance/acceptance_summary.json`
- `evidence/acceptance/native_file_hash_manifest_v2_1.csv`
- `evidence/acceptance/dependency_graph_check.json`
- `evidence/b4_1_verify/machine_check.json`
- `evidence/review_views/review_view_manifest.json`
- `V2_1_DEVIATION_MANIFEST.yaml`

B4-0 的权威来源清单和图纸登记只位于
`../../design_inputs/v2_1_reference_grounded/01_source_admission/` 与
`../../design_inputs/v2_1_reference_grounded/04_cad_preparation/` 子目录。
设计输入根目录的两个同名早期副本是 `NON_AUTHORITATIVE_STALE_COPY`；
详见
`../../design_inputs/v2_1_reference_grounded/CANONICAL_EVIDENCE_PATHS.yaml`。

## 下一人工 Gate

只有在以下证据签发后，才可继续物理机构释放：

1. 项目自有太阳翼根部机械 ICD、实体包络与轴/止挡/HDRM/线束参数；
2. B601 全解析任务姿态扫掠、相机 frame/FOV 和臂—翼动态避让；
3. C5 收拢边界与具体部署器接口裁决；
4. 紧固件、工具轴、维修顺序、连接器与弯曲半径；
5. SpeedPak/完整解析配置纪律；
6. 原生 `SLDDRW`、PDF、BOM 与逐件追溯；
7. 材料、载荷、连接、质量覆盖和后续 FEA/动力学独立 Gate。
