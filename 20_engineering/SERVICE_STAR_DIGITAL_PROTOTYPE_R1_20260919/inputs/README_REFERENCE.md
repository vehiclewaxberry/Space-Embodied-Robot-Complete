# 材料与物料参考核验（2026-09-19）

本轮交付是供新数字样机使用的**候选材料依据和表示规则**。没有运行 CAD，没有赋予采购、实物、真空或飞行验证信用。完整机器记录见 [REFERENCE_MATERIAL_BASIS.json](REFERENCE_MATERIAL_BASIS.json)。

实际查阅范围：F 盘参考库 START_HERE、20260917 HANDOFF、CAD_DONOR_REGISTER 全文；MASTER_INDEX 解析 48 行并选择性读记录；HASH_MANIFEST 头部和初始记录；WP03 材料/质量字段、BOM 样例、GAP_AUDIT 相关章节。没有声称全库或全部 PDF 精读。HANDOFF 的 49 行与现行索引解析 48 行有差异，本轮只登记；2026-08 的 donor“现行”标签不覆盖当前 WP03/WP10。

参考库用于导航、方法与来源身份，不复制 donor 几何、数据集动力学数值或外部代码进入交付，也不形成运行依赖。本轮物性优先从厂家原站独立核验。

| 对象 | 可用候选依据 | 使用边界 |
|---|---|---|
| 新加工铝件 | 6061-T6/T651，密度 2700 kg/m³；20°C 导热率 167 W/(m·K) | 材料产品形态、表处、实物牌号仍需逐件确定。[Kaiser 数据表](https://online.kaiseraluminum.com/depot/PublicProductInformation/Document/1015/Kaiser_Aluminum_6061_Sheet_Coil_and_Plate.pdf) |
| 通用钢件 | 保留 WP03 7850 kg/m³ 假设 | 不据密度猜测不锈钢牌号或紧固等级。 |
| 显式不锈钢候选 | 304/1.4301：密度 7900 kg/m³，E=200 GPa，20°C k=15 W/(m·K) | 来源为 Outokumpu 表7，可用于明确声明的新地面候选。A2-70另列紧固件性能等级，不能把304板材退火强度当作螺栓许用。[Outokumpu](https://www.outokumpu.com/en/products/product-ranges/-/media/files/products/core/outokumpu-core-range-datasheet.pdf?modified=20251117111909&revision=025e9931-a1d5-4c8f-8ff5-f881d38916da)、[Bossard](https://www.bossard.com/-/media/bossard-group/website/documents/technical-resources-old/stainless-steel-fasteners.pdf) |
| 导热带 / TIM | 铜材候选；TGP 1000VOUS 候选 k=1 W/(m·K) | 两项目前只有官方搜索索引内容，完整受控数据待归档；界面压紧和接触热阻另测。[Henkel 指南](https://dm.henkel-dam.com/is/content/henkel/lt-8116-brochure-thermal-interface-materials-selection-guidepdf) |
| 散热表面 | AZ-93：ε=0.91±0.02；α=0.15±0.02，后者要求干厚≥0.127 mm | 是涂层表面属性，不能替代基体材料或寿命末期光学值。[厂家参数](https://www.aztechnology.com/product/1/az-93) |
| PCB | 370HR FR-4 层压材料候选 k=0.4 W/(m·K) | 未核实密度保持 null；PCBA 是混合材料，不能整块赋予铝材。[Isola 参数](https://www.isola-group.com/pcb-laminates-prepreg/370hr-laminate-prepreg/) |
| 线束 | 铜导体与交联 ETFE 绝缘的 SPEC 55 系列候选 | 型号、AWG、端子、线长、动态弯曲适用性尚须确定。[TE 产品族](https://www.te.com/en/products/wire-cable/hook-up-wire.html) |
| 绝缘垫块 | PEEK 450G：密度1300 kg/m³、23°C拉伸模量4 GPa；平均导热0.29 W/(m·K)，沿流0.32 | 已读取2026-03-17版完整OEM网页；工艺、蠕变、真空和接触刚度仍须针对零件确定。[Victrex数据表](https://www.victrex.com/en/downloads/datasheets/victrex-peek-450g) |
| 电池 / 算力 / 驱动 / 设备盒 | 分开“壳体材料”与“内部设备质量代理” | 内部未知密度、热容保持 null，实物质量与旧数字分配质量分别登记。 |
| 推进地面表示 | 无推进剂的外包络 / 质量 / 接口模拟件 | 不能由外包络生成可信压力壳和阀路。 |

热控至少需要材料导热率、接触热阻、热源、外表面光学和环境边界；涂白色外观本身没有温度验证意义。[NASA 热控说明](https://www.nasa.gov/smallsat-institute/sst-soa/thermal-control/)

本轮发现一项可补证据：Dawn B1 官方 PDF 已公开 Isp、阀和点火功耗，可部分补旧 P9-03 的资料缺席。型号尚未选定；同一厂家网页与 PDF 的冷气最小冲量分别为 **1.4 与 0.59 mN·s**，已登记为 SOURCE_CONFLICT，禁止静默选择一个数值冻结执行器。[网页](https://www.dawnaerospace.com/thrusters)、[2025 July B1 PDF](https://www.dawnaerospace.com/_files/ugd/cfd301_5202e0fd24ab4ac198dcfd77b09e8a20.pdf)

数字交付应分别验收：①原生装配能打开和引用完整；②每件有材料或明确代理身份；③密度来源和质量账能追溯；④真实机械、电气、热和推进验证各有独立结论。前面三项完成后可开展有界布局、安装可达性、质量敏感性和算法接口研究。不能据此宣布整星工程设计完成。
