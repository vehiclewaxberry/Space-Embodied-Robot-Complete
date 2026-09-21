from pathlib import Path
import shutil, json, hashlib

AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[2]
SOURCE=ROOT/'20_engineering/SERVICE_STAR_HARDWARE_COMPACT_20260921'
DEST=ROOT/'20_engineering/SERVICE_STAR_PUBLICATION_20260921'
assert not DEST.exists(), 'Publication workspace already exists; do not overwrite it'
shutil.copytree(SOURCE,DEST)
docs={
'README.md':'''# 航天服务星具身智能机械臂机器人

**Space Service Robot with Embodied Intelligence**

面向在轨服务与机器人操作研究的长期硬件项目：以服务星本体、B601六自由度机械臂及其主机接口为基础，协同设计机械结构、电气线束、能源热控和动力推进系统。

本项目从早期竞赛工程发展而来，现以可装配、可参数化、可验证的工程样机为目标，持续完善航天服务机器人所需的物理平台。当前近期目标是**可装配、可上电的地面工程样机**；任务环境适应性与飞行资格在后续阶段独立验证。

> 当前发布为 **R6H机械数字装配 + R5E电气候选 + 热控与推进接口设计**。原生CAD和ECAD文件随仓库提供；部分选型、材料、PCB、线束与推进接口仍待闭合。仓库名称中的 `Complete` 表示整套选定硬件资料的发布目标，不代表整星已经完成制造、上电或飞行验收。

## 系统组成

| 模块 | 仓库内容 | 当前主要工作 |
|---|---|---|
| [机械结构与总装](01_mechanical/MECHANICAL_OPEN_GUIDE.md) | 服务星本体、B601机械臂、R6H水平安装、支架与紧固、当前装配BOM、材料候选、SolidWorks原生依赖 | AUX/STOP安装、装配路径与公差、材料质量账及结构校核 |
| [电气、线束与机械臂接口](02_electrical/README.md) | 系统原理图、MAIN/AUX/STOP PCB、库与模型、候选BOM、线束表、接口与控制板预留 | 将候选器件落实到电路和PCB，冻结真实针脚、制造线束及保护逻辑 |
| [能源与热控](03_power_thermal/README.md) | 供电与负载候选、电热输入、热路径、界面材料、热阻和辐射热网资料 | 当前构型功耗/能量预算、接触热阻、模型与地面试验闭合 |
| [动力与推进](04_propulsion/README.md) | 候选筛选、空间与安装准备、机械/电气/流体接口需求、OEM输入表 | 冻结型号和厂家接口，完成真实储箱、阀、管路、喷口与热接口设计 |

系统连接关系：服务星能源模块向主机、机械臂驱动与辅助负载供电；主机经预留接口连接B601与其他分系统；结构安装面、线束和热路径共同约束各模块布局；推进模块通过独立的机械、电气、流体和热接口接入整星。

## 从哪里开始

1. 阅读[当前设计状态](DESIGN_STATUS.md)，了解已实现、候选和未完成项。
2. 打开[原生总装](01_mechanical/native/SERVICE_STAR_SERVICE_R6H.SLDASM)。请完整保留 `01_mechanical/native/` 的737个原生文件，勿单独下载SLDASM。来源版本为SolidWorks 2024 SP5.0。
3. 用KiCad 10.0.6打开[系统工程](02_electrical/kicad/wp10/wp10_system.kicad_pro)和[系统原理图](02_electrical/kicad/wp10/wp10_system.kicad_sch)。三块PCB与系统层级原理图分别提供，不把候选BOM当作已完成制造的板卡。
4. 根据[下一阶段路线图](ROADMAP.md)逐项完成装配、线束、供电保护和热验证。

下载当前分支即可取得随发布清单列出的设计文件。当前发布使用普通Git保存文件，保留原字节；当前树的CAD不依赖额外下载LFS对象。历史提交可能仍使用LFS。

```bash
git -c core.autocrlf=false clone --depth 1 https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete.git
cd Space-Embodied-Robot-Complete
python 00_release/verify_package.py
```

完整性校验验证文件是否与发布清单一致，不验证设计是否符合制造或任务要求。软件版本、可用模块和工程限制见各模块说明。

## 当前数字安装示例

下图为R6H MAIN水平安装的局部查看图，覆盖板卡支承和接口场景；它不替代整星原生总装。

![R6H MAIN水平安装局部查看图](01_mechanical/views/R6H_HORIZONTAL_INSTALLATION.png)

[下载离线安装查看器](01_mechanical/views/R6H_HORIZONTAL_INSTALLATION_VIEWER.html)后在本机浏览器打开。当前包提供27个局部增量STEP；完整整星以原生总装为入口，尚无新导出的完整整星STEP。

## 发布范围与工程边界

本仓库当前分支收录四个硬件系统及其已整理的设计依赖、来源说明和必要验证记录。原仓库中的动力学、控制、RL/VLA、文献全文、运行环境、私人记录及过程镜像不属于本次硬件发布树；本地原工程继续保留。

“具身智能”是项目长期研究方向。本次交付其机械电子物理平台，不声明已实现完整自主在轨操作能力。当前R6H含机械臂、本体与MAIN数字集成；R7的AUX/STOP后续布局尚未装入。热辐射散热、电子抗辐射与飞行环境资格分别管理，不互相替代。

详细缺口见[OPEN_ITEMS](00_release/OPEN_ITEMS.md)，文件范围见[发布清单](00_release/PUBLICATION_MANIFEST.csv)，第三方来源见[来源与许可](00_release/THIRD_PARTY_NOTICES.md)。未知材料、性能与接口继续保留为未知，不以默认值填满。

## 项目维护

设计更改同时更新CAD/ECAD、BOM、接口表、验证范围和发布清单。问题报告请注明文件路径、软件版本、构型、复现方法与预期行为；涉及实际几何或电气功能变化时附可检查的差异。改进流程见[CONTRIBUTING](CONTRIBUTING.md)。

当前资料按各自来源条款管理；不对所有第三方和自有文件统一套用MIT或其他许可证。自有内容未另行标注时不新增广泛再授权，第三方适用条款与待核验范围保留于[使用说明](00_release/PUBLICATION_NOTES.md)。

## English overview

This long-term project develops the physical hardware platform of a space service robot with a B601 manipulator. This release covers mechanical CAD, electrical and harness design, power and thermal engineering, and propulsion interfaces. It is an editable engineering candidate for a ground prototype; manufacturing, power-on acceptance and flight qualification remain open. See the design status and roadmap before reusing any model, BOM or interface.
''',
'CONTRIBUTING.md':'''# 设计协作与变更要求

以可追溯的硬件更改为单位协作。问题报告应包含文件路径、版本、所用软件、具体构型、复现步骤和结果；在说明中区分几何问题、电路问题、模型缺失、来源问题和工程未完成项。

提交更改时提供：更改目的与范围；受影响的CAD/ECAD/BOM/接口；验证对象与条件；仍未解决的输入或限制。只做说明修改不需要重新生成整个CAD或运行研究仿真。

机械更改核对原生引用、实体身份、位姿、装配和必要间隙；电气更改核对实际网表、器件封装、PCB和候选表；热控与推进更改记录真实输入和适用工况。候选选型不能自动升级为制造或飞行放行。

保留来源、版权及许可证。不要提交账户凭据、个人环境、商业软件安装器、未获授权的文献全文或无用途的大型过程副本。第三方数据的许可与项目设计状态分别审阅。

更新文件后重新生成并验证发布清单；保留历史验证记录，新增修订状态，勿将历史回执中的原始哈希改写为新文件哈希。
''',
'PROJECT_IDENTITY.json':json.dumps({'schema':'SPACE_SERVICE_ROBOT_PROJECT_IDENTITY_V1','name_zh':'航天服务星具身智能机械臂机器人','name_en':'Space Service Robot with Embodied Intelligence','repository':'https://github.com/vehiclewaxberry/Space-Embodied-Robot-Complete','purpose':'Long-term hardware development for a service spacecraft with an embodied robotic manipulator','release_scope':['mechanical','electrical_and_harness','power_and_thermal','propulsion_interfaces'],'near_term_acceptance':'Assemblable and powerable ground engineering prototype','competition_deadline_is_project_gate':False,'flight_ready':False},ensure_ascii=False,indent=2)+'\n',
'.gitattributes':'''# Preserve delivered bytes. Current release uses ordinary Git, not LFS pointers.
* -text -filter -diff -merge
*.md diff
*.py diff
*.json diff
*.csv diff
*.yaml diff
*.yml diff
*.kicad_sch diff
*.kicad_pcb diff
''',
}
for name,content in docs.items(): (DEST/name).write_text(content,encoding='utf-8')
for stem in ['DESIGN_STATUS','ROADMAP']:
    content=(AUDIT/(stem+'_DRAFT.md')).read_text(encoding='utf-8')
    content=content.split('\n',1)[1]
    (DEST/(stem+'.md')).write_text(content,encoding='utf-8')
identity=(DEST/'PROJECT_IDENTITY.json').read_bytes()
(AUDIT/'PROJECT_IDENTITY.json').write_bytes(identity)
nav=ROOT/'PROJECT_MAP.md'
(AUDIT/'PROJECT_MAP_BEFORE_RENAME.md').write_bytes(nav.read_bytes())
text=nav.read_text(encoding='utf-8').replace('# 项目总导航','# 航天服务星具身智能机械臂机器人 · 项目总导航',1)
text=text.replace('更新：2026-09-21。','更新：2026-09-21。项目英文名称：Space Service Robot with Embodied Intelligence。项目按长期硬件研发推进，比赛期限不作为工程验收门槛。',1)
nav.write_text(text,encoding='utf-8')
(AUDIT/'PREPARATION.json').write_text(json.dumps({'source':SOURCE.relative_to(ROOT).as_posix(),'publication_root':DEST.relative_to(ROOT).as_posix(),'source_modified':False,'physical_workspace_root_renamed':False,'project_display_name_updated':True,'files_initial':sum(p.is_file() for p in DEST.rglob('*'))},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'publication_root':str(DEST),'files':sum(p.is_file() for p in DEST.rglob('*'))},ensure_ascii=False))
