# R5 能源与热管理布局：中断接续入口

本轮已完成受控来源准备，尚未生成可验收的新布局或 R5 原生总装。现行装配仍为 R4，R1–R4 未修改。

已生成 V30 完整模块的组件分解与 V36 主输入板的 KiCad 原生 STEP 导出，见 inputs/V30_SOURCE_MAP.json、inputs/V36_SOURCE_MAP.json。导出所含三维实体尚未与全部43个封装完成覆盖绑定，不能称完整V36 PCBA。

必须处理的版本事项：

- 当前 V36 的 R202 为 WSLP2726L5000FEA，即0.5mΩ；旧V30三维源采用0.2mΩ模型，旧CF1热模型用两分流器合计2.2mΩ。R5应按R201 2mΩ + R202 0.5mΩ核对实际热源，不继承旧温度结果。原厂依据 https://www.vishay.com/docs/30179/wslp2726.pdf 。
- HANDOFF_LATEST与其入口匹配，但入口中的working_revision及旧MAIN检查锁的网表已有漂移。主板文件仍匹配旧检查哈希；当前网表与135焊盘/器件值对应关系需完成新的只读复验。
- V36导出的PCB基体厚度为1.51mm，应与1.6mm名义总板厚、铜层/阻焊分账核对，不能直接当成板厚错误或忽略差异。
- 分开四根长线尾可以缩小核心空间表示，但所有裸段和护套段必须重新形成有端点、切向与弯曲约束的线束；不得删除后宣布装配通过。

下一步先测试P60托架下方的紧凑核心布局，保留轮组、RRC电池包络、P60支柱、躯干线束支撑等障碍；保持Q201、分流器和端子电气相对位置，再改承载件和线尾路线。PCB/TIM、机壳电隔离、接地及新热路径均待闭合。

工具：tools/common.py 只读组合R4最终规范化STEP与对应变换；tools/extract_sources.py通过XDE分解来源并复合回读核验。初次逐零件体积相加与整体积分口径差异已保留于results/SOURCE_EXTRACTION_ATTEMPT_01_VOLUME_GRANULARITY.log；当前按重组compound对原compound核验通过，诊断差额保留在source map中。

详细当前状态见 INTERRUPTION_CHECKPOINT.json。本目录未封包、未独立验收，不可替代R4交付。
