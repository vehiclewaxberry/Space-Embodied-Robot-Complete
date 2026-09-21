# 服务星地面数字样机 R1 移交（2026-09-19）

本轮已交付可在 SolidWorks 2024 打开的三态固定姿态集成候选。**电气、热控、推进与全系统工程设计仍未全部闭合，不能据此宣布可上电或飞行就绪。** 用户近期验收目标保持“可装配、可上电的地面工程样机”。

本文件是新增数字交付导航，不覆盖既有 `HANDOFF_LATEST.json`、阶段一移交、机械/科学 Gate 或 URDF。

## 交付入口

- [完整说明与完成边界](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/README.md)
- [服务姿态原生总装](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/native/SERVICE_STAR_SERVICE_R1.SLDASM)
- [收拢姿态原生总装](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/native/SERVICE_STAR_PARKING_R1.SLDASM)
- [释放姿态原生总装](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/native/SERVICE_STAR_RELEASED_R1.SLDASM)
- [打开指南](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/docs/SOLIDWORKS_OPEN_GUIDE.md)
- [当前机器状态](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/results/BUILD_STATUS.json)
- [13项后续闭环工作包](../../20_engineering/SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/docs/NEXT_STAGE_ENGINEERING_CLOSURE.md)

三态STEP在同目录 `neutral/`；逐态实例BOM在 `docs/BOM_*_1110.csv`；实际STEP图和SolidWorks原生图在 `views/`。审查压缩包 `SERVICE_STAR_R1_REVIEW_PACKAGE.zip` 的生成、字节数与哈希以 `results/PACKAGE_DELIVERY.json` 为准。应保留整套native文件，不单独传顶层SLDASM；跨电脑重定位/Pack and Go尚未验收。

## 已验证范围

- 三态各1110实例，STEP各1513实体；原生总装逐项冷读身份、位姿和本地引用通过。打开错误0、警告0、外部几何引用0、重建需求0。
- 三态共用692个不同零件、23个不同子装；当前692件均有材料决定冷读记录。536件已赋候选物理材料，156件为复合/未知。按单态实例为762候选物材读回与348未知/复合，整星可信质量、质心、惯量保持UNKNOWN。
- 231件新增原生零件全部完成来源、实体、尺寸和限定体积检查；九处冲突接口使用保守孔系合并。1233个已绑定输入哈希未改。
- 原生固定姿态不包含完整连续运动配合，也不是全原生参数化制造模型；实例BOM不等于采购BOM完成。

## 必须随包保留的观察

历史宿主材料写入前逐件哈希未单独记录，BOM中804个保留实例明确披露该旧链限制；不能把当前材料冷读当作历史实体重认证。CHB500W默认体积积分原失败保留，独立GK收敛及原生往返在原1e-5阈值内支持参考修正；额外布尔同一性未完成，保持UNKNOWN。B601少量曲面的展示三角化失败以边界线表示，STEP实体未删除。

F盘 `SPACE_ROBOTICS_REFERENCE_LIBRARY` 的入口、注册表、索引及相关资料已审阅；范围记录在 `inputs/README_REFERENCE.md`，未声称全库PDF精读。15个公开来源用于11类材料/表示规则，候选密度不替代材证、完整FE材料卡或空间资格。

## 建议接手顺序

1. 实物身份与输入：B601/驱动版本、电源回灌能力、K1/Q101参数、R07第六边接触刚度/预紧及地面工装。
2. 电气：45项选型/资料缺口、完整原理图/三块PCBA、逐针线束、保护/急停/再生能量闭合。
3. 热控：CF1热模块重新布置且无干涉，冻结热源与TIM压紧/接触热导，再完成B2模型和地面热验证。轨道热辐射和器件TID/SEE另需任务边界与证据。
4. 推进：冻结OEM型号与ICD，或明确地面无推进剂模拟件的质量/接口范围；现有包络模型不授予推力、压力和羽流能力。
5. 按被动装配→受限单板上电→代表负载故障验证→受控低速运动→声明最坏地面任务逐级验收。

布局、接口、软件算法与有界不确定性研究可继续；依赖真实供电、热平衡、推进或新增整星惯量的结论须先补齐对应证据。具体输入、实施和验收条件以13项工作包为准。
