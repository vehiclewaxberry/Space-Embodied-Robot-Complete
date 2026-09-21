# Route-C RFI-E/F/G 工程筛查 V2

日期：2026-08-25  
适用范围：B601 六关节安装态线束运动管理的供应商询证、样件和试验准备  
裁决：`SCREENING_COMPLETE_FOR_RFI_REFINEMENT / PRODUCT_SELECTION_NOT_AUTHORIZED`

## 1. 总裁决

本轮把官方公开资料从“泛供应商 URL”推进到“系列/件号、文档定位、单位、适用条件和明确缺口”。这允许精化 RFI-E/F/G 和台架试验，但不允许选择产品或填入 C2-01：

- P01-P13 仍为 `13/13 null + HOLD`；
- P08 没有恢复力矩/扭转刚度曲线；
- P10 没有精确衬材×精确护套材料对的真空摩擦/磨损/颗粒数据；
- P05/P13 没有项目安装坐标和沿受控路径的夹具站位表；
- `ROUTE_C_CAD_AUTHORIZED=false`。

## 2. RFI-E：微型载体与替代运动管理架构

| 候选 | 可用公开事实 | 关键缺口 | 当前状态 |
|---|---|---|---|
| RC-E-01 igus E2 Micro Series 06；例 `06.06.018.0` | 10.5×6 mm 内腔、15×12.5 mm 外形、20 mm 节距、R=18/28/38 mm、裸链约 0.13 kg/m；igumid G 有材料级真空低放气声明 | 无数值 TML/CVCM/WVR；无端支架/应变释放全组件资格；目录 K 不是硬止挡 | `SCREENING_CANDIDATE_ONLY` |
| RC-E-02 Tsubaki `TKP13H10-20W6R20` + PVDF 特规询证 | 标准件 10×6 mm 内腔、12.5×12 mm 外形、13 mm 节距、R=20/28/37 mm、1.0 m 标准最大行程；PVDF 特规声明用于降低真空放气 | 厂商未确认 TKP13H10 可做 PVDF；标准聚酰胺的质量、温度、寿命不可继承给 PVDF | `CONDITIONAL_SCREENING_CANDIDATE` |
| RC-E-03 KABELSCHLEPP MONO 0130 | 小包络和质量可作机械比较 | 官方材料表明确标准塑料拖链不适合真空 | `VACUUM_NEGATIVE_REFERENCE` |
| RC-E-04 GORE High Flex Flat | 真空/洁净环境、50 mm 弯曲半径、>20M 循环、500 mm 自支承行程 | 半导体真空产品不是航天 B601 线束；没有安装质量、六关节扭转或恢复力矩 | `ALTERNATE_ARCHITECTURE_SCREENING_ONLY` |

RFI-E 必须要求：精确订货号及修订；内/外包络和公差；裸链、端接、应变释放、紧固件的质量与公差；安装链长公式、有效行程和硬止挡；关节绕转/反弯限制；完整材料栈；批次级 TML/CVCM/WVR；真空热循环下寿命、磨耗、颗粒；辐照/AO/UV/发射振动后保持；实际填充率下的失效判据。

## 3. RFI-F：导向衬材×护套材料对

| 候选对 | 已有证据 | 不允许的拼接 | 当前状态 |
|---|---|---|---|
| RC-F-01 TECASINT 8591 grey × GORE SpaceWire PFA | 两侧材料身份、温度和放气筛查；8591 目录列 μ=0.14–0.22 与磨损率 | 8591 单材料目录系数不得登记成 8591×PFA 的材料对系数 | `COUPON_CANDIDATE_ONLY` |
| RC-F-02 TECASINT 2391 black × Axon ESCC 3901 012 XL-ETFE | 2391 有真空销盘趋势，Axon 明确 XL-ETFE 最外层 | 2391 的对偶体是 52100 钢；通用 ETFE 数据不得转给确切 XL-ETFE 护套 | `COUPON_CANDIDATE_ONLY` |

RFI-F 与试验必须冻结：衬材牌号/填料/批次/加工方向/Ra-Rz/清洗烘烤；线缆完整料号、护套 compound/交联/颜料/厚度/批次；真空度、温度、速度、法向载荷或接触压力、曲率、张力、行程、扭转、循环和辐照预处理。输出至少包含启动力、静/动摩擦、黏滑、滞回、两侧磨损、转移膜、颗粒质量/粒径、循环后绝缘/耐压/信号检查、不确定度和原始数据哈希。

在上述材料对试验前，`P10.guide_friction_candidate` 必须保持 null。

## 4. RFI-G：夹具与固定硬件

| 候选 | 公开包络 | 当前缺口 | 当前状态 |
|---|---|---|---|
| RC-G-01 TE THA-PDKG-XX | 3.18–34.93 mm 束径、12.7 mm 宽、Ø5.1 +0.1/−0.0 mm 孔、3.5–14.2 g、GF-PEEK+氯丁、−65～85 °C；#10/M5+垫圈，安装说明公开上限约 5.99 N·m | 无完整组件空间放气/辐照/AO；最终紧固件、基体和扭矩仍由客户定义；网页显示暂不可供货 | `RFI_SCREENING_CANDIDATE_ONLY` |
| RC-G-02 Amphenol 75P | 3.18–39.70 mm、1.95–15.83 g、PEEK、多衬垫选项、DO-160G 环境筛查 | DO-160G 不是空间资格；无公开完整材料栈放气和项目安装接口 | `RFI_SCREENING_CANDIDATE_ONLY` |
| RC-G-03 Amphenol Omega | PEEK+包覆硅橡胶、双安装腿、最大约 50.8 mm | 公开页缺精确尺寸表、质量、孔位、紧固件、扭矩和放气 | `RFI_SCREENING_CANDIDATE_ONLY` |

NASA-STD-8739.4A 的扎带/绑扎间距以及连接器至首个绑扎点距离只属于工艺约束，不能生成结构 P-clamp 站位。ECSS-Q-ST-20-30C 同样要求项目裁剪，没有提供可直接采用的结构夹具数值站距。

RFI-G 必须要求：完整料号/衬垫代码/修订/在产状态；束径与压缩公差；质量和质心；孔位、紧固件、垫圈、锁紧和扭矩；全材料栈与批次；完整组件放气报告；真空、热循环、辐照、AO、振动、冲击、滑移、压溃、冷流和疲劳边界；首夹距及弯头/分支/穿舱/运动区规则，或明确声明无厂商站距规则。

## 5. P08 恢复力矩试验入口

CFROBOT2 的 `±180°/m` 是允许扭转幅值，不是恢复力矩。P08 的唯一合法闭合路径是对最终安装态线束进行力/矩-位姿-速率-温度-真空-循环测试。

试验轴由 PRJ-05 任务寿命分配和 PRJ-06 允许恢复载荷预算给出；当前两者未受控，因此本包只冻结字段和原始数据合同，不赋数值试验级别：

```text
输入：joint_id, segment, angle, rate, temperature, vacuum, accumulated_cycles
输出：force_N, torque_Nm, hysteresis, uncertainty, calibration_record, raw_data_hash
```

## 6. 进入 Route-C CAD 前仍必须闭合

1. PRJ-01～PRJ-05：电流/负载、协议/EMC、针脚/导体、HN-00～HN-03 安装 ICD、任务寿命谱；
2. 精确线束安装 BOM、完成态 OD/质量及公差；
3. 精确载体/夹具/衬材件号、受控图纸、环境与寿命证据；
4. P08 恢复力矩与 P10 材料对试验；
5. P05 项目坐标、P11 受控导向曲率、P13 夹具站位；
6. Owner 独立接受与新的 Route-C CAD 授权记录。

当前不存在上述授权；任何目录数值只能用于 RFI 问题和试验夹具规划。
