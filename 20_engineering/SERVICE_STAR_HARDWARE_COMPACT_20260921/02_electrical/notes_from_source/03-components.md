# 服务星 R5E｜2026-09-20｜阶段4：电气选型更新

本轮完成候选选型与证据整理，目标为未采购的地面样机。45项旧缺口已逐项处置：7项IC额定资料、32项单器件无源候选、1项R305复合候选、5项接口/板上结构分类。另将U301的既有LT3013EDE#PBF从Value回填到结构化候选料号。

以下候选均带实现条件。`CANDIDATE_SELECTED`不表示已经装在PCB上、采购完成或可上电。

| 位号/用途 | 本轮选型或处理 |
|---|---|
| U101 看门狗 | 保留 TPS3431SDRBR，补额定值及替代限制 |
| U311–U313 温度窗口比较器 | 保留 TLV6700DDCR，补原厂资料 |
| U303 / U304 制动控制 | 保留 MAX5048CAUT+T / MAX16053AUT+T，补供电和输出类型约束 |
| U207 AUX 保护 | 保留 TPS26600PWPR，补限流与热约束 |
| C204 | 50SVPF10M，10 µF / 50 V 聚合物电容 |
| C205 | CGA6L2X7R1H105K160AA，1 µF / 50 V |
| C206、C208 | C1210C104J1GACTU，100 nF / 100 V C0G |
| C207、C304、C308 | C0603C104K3RACTU，100 nF / 25 V |
| C209、C210 | CGA6P3X7S1H685M250AB，6.8 µF / 50 V；保留偏压校核 |
| C301 | MKS2D041501M00JSSD，1.5 µF / 100 V 薄膜候选；保留有效容量校核 |
| C302 | C3225X7R1H226M250AC，22 µF / 50 V；保留有效容量校核 |
| C303 | C0603C472J5GACTU，4.7 nF / 50 V C0G |
| C305 | C0805C225K3RACTU，2.2 µF / 25 V；保留有效容量校核 |
| C306 | C0603C101J5GACTU，100 pF / 50 V C0G |
| R301 | TNPW060386K6BEEA |
| R302、R306、R309 | TNPW060310K0BEEA |
| R303 / R308 | TNPW0603270KBEEA / TNPW0603200KBEEA |
| R304、R307、R313、R316、R319 | TNPW060310K0FEEA |
| R310 | TNPW0603100KFEEA |
| R311、R314、R317 | TNPW060310R0FEEA |
| R312、R315、R318 | TNPW06032R20FEEA |
| R305 | 665 kΩ + 11 kΩ 串联候选，须新增中间节点和封装 |
| J200–J203、J210 | 分开登记接口边界、测试点及板上铜盘，保留实际连接器落实项 |
| R201 / R202 | 保留 2 mΩ / 0.5 mΩ，修正发热输入 |

**器件选择依据。** IC沿用已经审查过的电源域及输出逻辑，避免换芯片改变STOP时序。特别是MAX16053的推挽输出不能替换成MAX16052的开漏输出。国产替代没有完成等效引脚、失效模式与时序证据，故本轮保留当前架构，替代料在采购前另做ECO验证。没有把未核验第二来源写成可直接替换。

电阻采用TNPW同一系列，按尺寸、阻值范围、标准阻值、容差和TCR的原厂订货规则选择。0.1%分压电阻保留精度；1%栅极/下拉电阻仍需脉冲能力校核。R305的676kΩ采用665kΩ的0805件与11kΩ的0603件串联方案，候选订货码为TNPW0805665KBEEA、TNPW060311K0BEEA，尚未形成实际新中间网与双封装。未核价格/现货。[原厂系列表](https://www.vishay.com/docs/28758/tnpw_e3.pdf)

电容优先复用项目已有系列；C301采用1.5µF薄膜保留初始容差余量，需重新核布局及上电瞬态。C302/C305的标称容量不能保证偏压后的有效容量。C209/C210选择的X7S器件需要把±22%温度系数引入滤波预算。AEC-Q200不等于航天鉴定。[WIMA](https://www.wima.de/wp-content/uploads/media/e_WIMA_MKS_2.pdf)、[TDK 6.8µF](https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=CGA6P3X7S1H685M250AB)、[TDK 22µF](https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=C3225X7R1H226M250AC)

**IC资料入口。** [TPS3431](https://www.ti.com/lit/ds/symlink/tps3431.pdf)、[TLV6700](https://www.ti.com/lit/ds/symlink/tlv6700.pdf)、[TPS2660](https://www.ti.com/lit/ds/symlink/tps2660.pdf)、[MAX5048C](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX5048C.pdf)、[MAX16053](https://www.analog.com/media/en/technical-documentation/data-sheets/MAX16052-MAX16053.pdf)。完整参数见JSON，不用“绝对最大额定”替代推荐工作范围。独立评审后，U207已修正为正向4.2–60V、可调限流0.1–2.23A；5.36kΩ时典型2.23A、上限2.35A。不能据此把支路持续允许电流直接设为2.35A。

**其他无源资料入口。** [Panasonic C204](https://industrial.panasonic.com/tw/products/pt/os-con/models/50SVPF10M)、[TDK C205](https://product.tdk.com/en/search/capacitor/ceramic/mlcc/info?part_no=CGA6L2X7R1H105K160AA)、[KEMET 100nF/100V](https://search.kemet.com/component-documentation/download/specsheet/C1210C104J1GACTU)、[KEMET 100nF/25V](https://search.kemet.com/component-documentation/download/specsheet/C0603C104K3RACTU)、[KEMET 4.7nF](https://yageogroup.com/download/specsheet/C0603C472J5GACTU)、[KEMET 2.2µF](https://search.kemet.com/component-documentation/download/specsheet/C0805C225K3RACTU)、[KEMET 100pF](https://search.kemet.com/component-documentation/download/specsheet/C0603C101J5GACTU)。本轮成功归档的原厂PDF带SHA256，未成功者保留网页核验等级。

**电热更新。** WSLP2726L5000FEA表示0.5mΩ；R201与R202在20A下合计名义1W，比旧0.2mΩ模型增加0.12W。成品TCR采用75ppm/K。6°C/W是元件到端子热阻，不是到环境。实际端温、安装散热和轨道边界未知，不能推算热控已通过。[Vishay WSLP2726](https://www.vishay.com/docs/30179/wslp2726.pdf)

采购参考页、封装下载页未完成精确核验的IC/模块，均在输入中标为需联网查证；现有项目封装作为设计参考。未给价格、库存、交期或航天等级推断。新采购前执行精确订货号/生命周期/替代料/焊盘复核。

数据文件：`bom/ELECTRICAL_SELECTION_BOM_R5E.csv`与JSON，`inputs/SELECTION_UPDATES.json`、`results/PRIMARY_SOURCE_ARCHIVE.json`。总体219个逻辑实物候选对应220件假定实施后的明细（仅因R305增加一件）；不是整星采购BOM，不能与487/497/1130装配实例数直接相加。
