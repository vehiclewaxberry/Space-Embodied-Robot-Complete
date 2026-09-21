# 硬件数字样机精简整理交付

日期：2026-09-21。范围仅为服务星与B601机械结构总装、电气线束、能源热控、动力推进主设计。研究、控制与上层规划目录保持原样，没有上传GitHub或改写Git历史。

## 主要结果

- 精简工作入口：[SERVICE_STAR_HARDWARE_COMPACT_20260921](../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/README.md)。设计和随附说明约150 MB；最终总包检查覆盖958个文件（另加总状态与哈希清单），CLI产生的本机个人偏好文件已移出。
- 当前总装：[精简副本R6H总装](../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/01_mechanical/native/SERVICE_STAR_SERVICE_R6H.SLDASM)。737个原生文件支持15个子装配、1153叶实例；两处物理目录冷打开均零错误、零警告、零外部原生引用。1602实体通过721个原字节零件继承来源测量，并非本次重新计数。
- 原件：[原R6H总装](../../../20_engineering/SERVICE_STAR_CORE_INSTALLATION_R6H_20260920/native/SERVICE_STAR_SERVICE_R6H.SLDASM)及790项原生来源锁全部保持。没有用WP03替代后续集成。PROJECT_MAP与工程README已更新导航。
- 电气：15张原理图、三块PCB、必要库与模型、249行选型BOM、B601接口和线束；库/模型路径只在副本重定位。既有5个Molex三维模型缺项保持可见。
- 热控与推进：保留当前电热输入、模块电源接口、适用对象明确的TIM合同、B2候选、推进比较与OEM/安装输入；不把不同阶段参数当作已完成的同版设计。
- 原设计来源校验共1062条全部保持，主入口链接与本次限定凭据格式检查通过。[总包状态](../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/00_release/PACKAGE_STATUS.json)和[SHA256清单](../../../20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921/00_release/PACKAGE_SHA256.csv)位于包内。

## 实际本地删除

[删除回执](CLEANUP_EXECUTION.json)记录30个精确文件、1,005,499,308字节：已解包KiCad安装器1个、可再生COM缓存18个、具源码Python字节码11个。没有删除CAD、原理图、PCB、BOM、设计源程序或原始验证结果。KiCad运行时和再生成依据保留。

上述是删除字节数；本轮同时新增精简副本，因此不是净磁盘减少量。安装器仍存在于旧Git历史，本地删除不能使旧历史自动适合推送。

独立清理审查见[FINAL_CURATION_REVIEW.json](FINAL_CURATION_REVIEW.json)；核准路径/哈希见[CLEANUP_CANDIDATES.json](CLEANUP_CANDIDATES.json)。该独立审查的模块封装覆盖时间早于最终总包检查，不能代替后者。

## 保留边界

旧目录中仍被引用的文件、唯一设计证据与历史失败记录保留原位。本轮不按版本号、文件夹名称或日期成批删除。主设计副本已独立整理；不需要为使用精简包而复制整个原工作区。

整星材料/质量、AUX/STOP安装、功能电气ECO、制造线束、电热闭合及推进定型仍有待办，见包内OPEN_ITEMS。文件整理未新增制造、上电或飞行资格。

本轮没有上传网络。自有许可选择及第三方逐资产再分发范围仍待确认；精简包不携带原`.git`、凭据环境转储、安装器或私人协作附件。限定模式检查不等于原仓库全历史或CAD所有元数据隐私认证。

中间整理工具和日志存放在本治理目录，不放在主设计入口。需要复核来源时参阅MECHANICAL_SELECTION、SYSTEM_SELECTION、各模块来源映射和PROTECTED_SOURCE_RECHECK。
