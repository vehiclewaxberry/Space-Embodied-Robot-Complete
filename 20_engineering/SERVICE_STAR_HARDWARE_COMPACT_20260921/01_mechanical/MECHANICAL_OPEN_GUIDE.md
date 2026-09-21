# 机械总装与查看入口

本目录以最新R6H后续集成机械总装为来源：机械臂、本体及水平电气安装均保留，原工程未删除或回退。受检计数15组、1153叶实例、1602哈希绑定实体；AUX/STOP的R7后续设计未安装。

已完成副本重链接及两处物理位置只读冷开：零打开错误、零警告、零外部原生引用。721个零件保留原字节，1602实体计数继承原R6H实读验证；本轮只重新检查身份、位姿、引用和文件哈希。此为原生装配可迁移验证，不是整星工程完成。

- 原生总装：`native/SERVICE_STAR_SERVICE_R6H.SLDASM`，SolidWorks 2024 SP5.0来源。要整体保留native目录中的全部737文件，不能只取SLDASM。
- 当前装配BOM：`docs/CURRENT_ASSEMBLY_BOM_1153.csv`。材料未知明确保留，不能据几何体积读取软件默认质量作为物理整星质量。
- 离线安装查看：`views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html`；静态图同目录PNG。它显示四个局部安装与接口场景，不是整星几何的替代物。
- 交换几何：`step/`中27个当前局部增量STEP；本包没有新导出的完整整星STEP。
- 最终复制与冷开状态：`MECHANICAL_DELIVERY.json`；来源到副本的784项映射见 `SOURCE_TO_TARGET.csv`。

`docs/source_R6H/`原样保留源状态与独立审查，其旧绝对路径只标识源工程；当前副本文件对应 `inputs/MECHANICAL_COPY_PLAN.json`。全体原件790项锁保存作来源证据，737项才是当前总装原生闭包。

`docs/source_materials/GROUND_CANDIDATE_MATERIALS.sldmat`为项目候选材料库的本地副本；整星材料未全部赋值。它不替代SolidWorks安装自带的商业材料库，也不签发公共再分发许可。

本目录可作为本地机械设计工作副本。所有公开发布、第三方模型和材料数据再分发仍需许可审查。固定姿态和可打开文件不代表运动/公差/强度/制造、上电或飞行验证通过。

整理工具和过程回执保留在来源项目的 `01_project/competition/HARDWARE_DESIGN_CURATION_20260921/`，不混入本设计主目录。原R6H工程总装完整保留；不需要使用早期WP03替代。
