# WP10 V16：KiCad MCP 接入与 ERC 优化

日期：2026-09-09。范围：既有工程样机方案的电源声明、检查器和同版本证据；沿用已授权的快速执行方式、B601 DM 和单受保护电池/CHB/独立 THN 架构，未新增器件选型或物理装配。

当前原生 KiCad 10.0.6 检查为 **0 错误、0 警告**，MCP 独立调用同样为零。原四项 ignored 检查保持：single_global_label、four_way_junction、simulation_model_issue、footprint_filter；零结果仅覆盖已启用规则。

7 个报告错误对应 7 个网络，而不是仅有 7 个电源输入引脚。原有供电图已包含保险丝、开关、转换器、接触器和回流；采用有条件的标准 PWR_FLAG 声明。保留电源输入类型、共漏极 VS、负载侧 U301 和输入/次级隔离；201 实体位号、657 引脚网络及类型与 V15 完全相同。7 个非物料声明不进入采购 BOM，实际原理图从 11 页变为 12 页。

实现取舍：增加可审计的标准声明，保留真实器件属性。把引脚改为 passive、改接 VS 或合并隔离回流会破坏模型或设计意图；整体屏蔽 power_pin_not_driven 会丢失后续检查能力。正常声明符合 [KiCad 原厂说明](https://docs.kicad.org/10.0/en/eeschema/eeschema.html#power-pins-and-power-flags)，用户 WP09R 第108行及 WP10 第166行亦允许有实际依据的标记。

## 逐网依据

- `#FLG201` → `WP10_ARM_RETURN`：Intentional common isolated secondary reference. Positive outputs remain separate; no primary-secondary bridge.
- `#FLG202` → `WP10_MAIN_FUSED`：External protected source present at project J200 and F201 intact. Battery OEM cavity and Sys Detect remain unbound.
- `#FLG203` → `WP10_INPUT_RETURN`：External primary return boundary at project J200. This is not proof of an OEM-approved battery connection.
- `#FLG204` → `WP10_AUX_FUSED`：Protected source and F202 intact. Independent of Q201; not independent of the battery or AUX fuse.
- `#FLG205` → `WP10_PRECHARGED_PLUS`：F201/R201/R202/Q201 conductive with valid supply and appropriate latched/precharge state. ERC does not evaluate startup.
- `#FLG206` → `WP10_RB_COMMON_DRAIN`：CHB may feed through Q202 S-to-D body diode/channel. ARM regeneration may feed through closed K1 and Q203 S-to-D diode. Diode drops and dynamics unverified.
- `#FLG207` → `WP10_ARM_BUS_PLUS`：Forward path requires CHB, Q202/Q203 and closed K1. Motor regeneration can energize the load-side bus with K1 open; its energy and timing remain unverified.

## 实际修改和验证

KiCad MCP 创建了声明页、七个原厂库符号、网络标签和可见条件说明。其自动工程名和层级路径发生适配问题，已仅对新页元数据进行规范化；未改动原有实体。声明页以 MCP 生成的原生源文件和根层级节点存档，现有生成器每次重建都会导入，避免手工修图后重建丢失。新增工程内 power 库副本以保持路径可移植。

旧的 XML-only 禁旗标检查无法可靠发现 # 电源符号。本轮改为原理图源级白名单，校验实例、UUID、网络、原厂库、位置、BOM/板属性、源文件哈希以及 201/657 不变性。原生命令失败会停止；即使命令成功，空报告、错源文件、漏页或检查范围变化也不能判 ERC_clean。

本轮 436 项原有连通性与合同检查通过，声明审计 53 项通过，16 项回归通过。独立审阅以有向图核对 256 个布尔条件组合，与条件路径模型一致；这不是器件动态仿真。C203 同版本 CAD/ECAD 接口重新检查，三姿态局部几何检查通过；CAD 源和安装件未发生几何改动。

## 保留的工程边界

J200 仍是项目适配端，厂家电池腔位及 Sys Detect 未绑定。保险丝/电池 BMS/MOSFET/线材保护配合、C203 实际铜箔和 CHB 端接、预充稳定性、停止与回生动态及热设计、PMM 充电和同修订推进 ICD 仍需完成。原 37 行状态保持 13 个限定子项完成、19 个内部设计开放、4 个外部接口未绑定、1 个实物未执行。所有整机完成、制造、上电和飞行放行字段保持 false。

内存不足时先清理已识别的空闲 Codex 工具工作集；未终止用户应用。记录了被 2 GiB 启动保护拦截的尝试和清理后的成功重试。工作集可再次加载，释放量不构成持续可用内存保证。

复现：先运行 tools/build_input_passive_revision.py（通过 native_delta_guard 串行启动），再运行 tools/test_erc_source_contract.py；修改 XML 后按现有 C203 接口流程重新绑定。所有结果须与其 inputs 哈希匹配。
