# R3数字装配与干涉查看交付

本目录交付的是本工作区中的固定服务态SolidWorks装配增量，以及B601接口/局部线路空间预留。

- 原生入口：`native/SERVICE_STAR_SERVICE_R3.SLDASM`。依赖同级R1/R2原生目录，增量ZIP不是跨机Pack-and-Go。
- 装配复查现行依据：`results/NATIVE_ASSEMBLY_RECHECK_V4.json`。1110实例、677唯一零件、1520实体，完全解析，冷打开错误/警告0，重建成功。
- 局部干涉现行依据：`results/GEOMETRY_ASSEMBLY_RECHECK_V2.json`。三个固定姿态36对精确交叠检查，无R3新增外部穿透。
- 独立复查：`results/INDEPENDENT_ASSEMBLY_RECHECK_REVIEW.json`，47/47通过，限于声明的静态和收据核验范围。
- 可旋转查看：`views/ASSEMBLY_INTERFERENCE_VIEWER.html`；实际几何图：`views/ASSEMBLY_INTERFERENCE_LOCATIONS.png`。
- 完全解析后的SolidWorks实截图：`views/SERVICE_STAR_SERVICE_R3_RESOLVED.png`。较早的两张空白截图不用于交付展示。

需要查看的小间距是R3线路到支架0.50 mm、R2线路到M3RB 0.75 mm；它们不是制造/热变形/振动裕量验收值。图C所示CF1旧候选与电池底座交叠384.10 mm³，旧候选没有装入当前R3，重布局仍未完成。

`GEOMETRY_ASSEMBLY_RECHECK.json`是误将旧世界坐标STEP与规范化零件变换重复配对的诊断失败记录，由V2明确废止其装配碰撞信用。更早的中断与未解析收据同样只作为过程记录保留。检查方法已修正；没有基于坐标误报修改实体几何。

完整说明见项目目录的`装配复查与干涉查看_R3_20260920.md`。接口板仍为未选MPN的预留；真实线束、安装支撑、完整材料/质量与CF1热控模块尚待闭合。当前不能用作制造、上电或在轨实装放行。
