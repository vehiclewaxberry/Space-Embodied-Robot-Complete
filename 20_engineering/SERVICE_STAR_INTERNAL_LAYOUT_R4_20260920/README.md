# R4 内部布局数字设计增量

日期：2026-09-20。基于封存 R3，完成接口板四点支撑与两处功能布线路径调整。当前为地面样机的固定姿态数字设计候选；实物尚未采购。

- **SolidWorks 主入口**：`native/SERVICE_STAR_SERVICE_R4.SLDASM`。
- **可旋转查看页**：`views/R4_INTERNAL_LAYOUT_VIEWER.html`；浏览器当前地址 `http://127.0.0.1:8766/R4_INTERNAL_LAYOUT_VIEWER.html`。本地服务器退出后可直接打开 HTML，它内嵌绘图库。
- **局部查看图**：`views/R4_INTERNAL_LAYOUT.png`。
- **整星原生查看图**：`views/SERVICE_STAR_SERVICE_R4_RESOLVED.png`。
- **BOM 增量**：`inputs/BOM_DELTA.csv`，6 行替换、20 行新增。
- **安装与线束说明**：`docs/hardware/04-layout-and-mounting.md`。

原生总装中有 1130 个叶实例、697 个唯一零件文件、1540 个实体实例和 14 个直接子装配，含既有占位/功能包络。新增 20 个安装件，替换 6 个几何实例，生成 26 个 R4 原生零件及 4 个替换子装配。总装按固定姿态保存，没有新增运动配合。

**本地依赖**：主装配依赖同级 `SERVICE_STAR_DIGITAL_PROTOTYPE_R1_20260919/native/` 中的原生零件和未改子装配，请保留原工作区目录。R4 ZIP 为本地增量包，未执行 Pack and Go，不能单独移到其他电脑即称完整便携交付。R2/R3 保留作来源与复验依据。

`results/INCREMENT_STATIC_CHECK.json` 对服务、停放、释放三个固定状态进行增量检查。接口侧名义间隙 2.00 mm，释放线路到 M3RB 为 2.865439 mm，最近其他障碍为 2.625653 mm。新增与变更部分无检出的未声明穿透；旧模型相互之间的全部碰撞和连续运动未在本轮重新认证。

`results/NATIVE_ASSEMBLY_RECHECK.json` 完成原生冷打开、完整解析、身份/文件引用/总变换、逐零件实体数、固定状态与重建检查：0 打开错误、0 警告，NeedsRebuild2=0，758 个旧/新原生文件在复验前后哈希一致。

**仍未闭合**：CF1 电源/热控模块未装入；预留 PCB 到原 TIM 存在 4.5 mm 空隙，导热和绝缘/接地待设计；线束仍是功能走廊，非完成下料/端接的实物线束；紧固件型号、材料等级及预紧待定；全星材料、质量/质心/惯量和上电验收未闭合。

CF1 搜索保留完整 V30 来源（上游声明 56 个组件实例，STEP 冷读为 60 个实体出现项）。18 个有界旋转/平移候选均发生冲突，这不是全空间不可布置的证明。它不代表当前 V36 PCBA，且独立热路径不能继承旧位置的热结果。拒收候选只存放在 `cad/rejected/`，没有进入原生总装。

后续布置顺序与具体验收条件见 `inputs/NEXT_LAYOUT_WORK_ORDER.json`。当前数字设计和检查通过不授予整星可上电、飞行可用或科学 Gate 信用。
