# R2 内部线束与欠驱动状态移交

本轮承接 R1 数字样机，按“可装配、可上电的地面工程样机”目标补充实际设计并核对公开服务星/立方星案例。目录名沿用开工日20260919，收尾日为20260920。

## 当前入口

- [总入口与使用边界](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/README.md>)
- [系统对照与10项逐项工作表](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/docs/SYSTEM_COMPARISON.md>)
- [R2整星SolidWorks服务态](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/native/SERVICE_STAR_SERVICE_R2.SLDASM>)
- [局部独立STEP](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/cad/INTERNAL_HARNESS_DETAIL_R2.step>)
- [本轮增量包](<F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/SERVICE_STAR_INTERNAL_HARNESS_ORBIT_R2_20260919/SERVICE_STAR_R2_LOCAL_INCREMENT.zip>)

增量包64项、1,169,859字节，SHA256 `03e4e50f5919e0b201ec7ab3f34c39a0e993a72d6ab65bfa4ac22caaf2588891`。ZIP逐项读回已核验；其中原生装配仍依赖同工作区R1/native，非独立Pack-and-Go。局部STEP自含几何。

## 已落实的设计

1. 当前R1已有ROOT分体护套/保持件，旧passage文件的缺件标记不再是现行事实。本轮保留承力结构，修正两条释放功能支路，各与M3RB的456.336 mm³穿透消失；三固定态静态筛选/独立复算通过。R14、OD4，最小名义间距0.75mm。两个逻辑记录仍共享走廊，真实分叉/双电缆排布与制造尚未设计完毕。
2. 现行网表沿HANDOFF逐级锁定，为249ref/795pin；V36目录旧XML/旧PIN_NET快照不作为现行。形成86记录/84active，新增6根AUX和6根NTC的接线与MPN候选。三PCB540有网编号焊盘，其中536源映射一致、MAIN4PORT板级引用另列；144/168接线端仍属逻辑/外部要求，制造发布0。
3. 推进检查器严格区分秩、单向可达域、力/力矩、单喷口失效，并建立九模式合同。实际喷口数、r/d和COM仍null；12/24点仅数学对照，不进CAD/BOM。当前轮候选4×RW400 30档与研究3×100档不一致，旧22kg WHEELS_ONLY不能自动迁移。
4. 原生R2整星1110实例、局部20实例，冷打开错误0/警告0、无需重建。旧R1封存ZIP以及其719个原生payload文件逐项比对未变。新线束包络没有虚构均质材料，整星可信质量/质心/惯量保持null。

## 独立验收与保留边界

电气、推进、路线均由独立审阅者复核，回执位于R2/results/INDEPENDENT_*_REVIEW.json。原生回执为NATIVE_ROUTE_DELIVERY_V2.json，总状态为R2_DELIVERY_STATUS.json。

两条早期绕行候选因引入其他碰撞被拒绝；首次原生导入因将保守包围盒与精确回读对比被拦截，改精确源包围盒后重验，原阈值未放宽。失败回执保留；首次输入计划未单独封存的局限已披露。路线STEP近重合交集布尔的无效中间体保留UNKNOWN，不影响每条有效实体及所声明33对碰撞检查。

最小0.75mm为名义值：独立+Y扰动0.76mm即产生穿透，不可宣称已含公差/热变形/振动裕量。当前ready_to_power=false、whole_design_complete=false、flight_ready=false，九模式物理执行许可false。没有改写旧科学Gate、旧URDF或R1真值。

## 接手顺序

先按系统工作表1–4冻结实际B601/驱动与电源型号和针脚，落实三PCBA安装、制造线束、保护/STOP/再生能量预算，再开展有界限能验收。轮组轴线/电源、相对导航和推进OEM/喷口/捕后COM可并行收集输入。

CF1重布局/B2热路径、R07第6边实测、地面失电保持、整星质量/分离器适配以及在轨热平衡/辐射/离轨仍是明确待办。F盘参考资料和NASA/ESA案例用于系统漏项检查，不能作为本项目实物参数或飞行能力的替代。后续在独立迭代目录工作，保留本轮封存文件不覆盖。
