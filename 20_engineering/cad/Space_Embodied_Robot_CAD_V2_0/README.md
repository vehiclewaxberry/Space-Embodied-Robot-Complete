# Space_Embodied_Robot_CAD_V2_0 — V2 System Mechanical Prototype

> `GATE: COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD`（人工授权记录：
> `evidence/b3_00/HUMAN_APPROVAL_RECORD.yaml`）
> `PROFILE: COMPETITION_DISPLAY_V0`（340.5×226.3×226.3 mm，NON_FLIGHT_DISPLAY_ONLY）
> `MAXIMUM_EXIT: V2_SYSTEM_MECHANICAL_CAD_COMPLETE_WITH_PHYSICAL_LIMITATIONS`

## 这是什么

12U 服务航天器 **系统机械 CAD 原型**（Top-Down Skeleton 驱动，全自动 COM 构建）：
主/次结构职责、B601 六维反力路径表达、三舱 volume owner、维护/线束 reference、
具名配置与范围化干涉、机器证据链。**不是**飞行资格或制造定型设计。

## 它不能回答什么（保持 UNKNOWN/BLOCKED）

强度/刚度/模态/热、材料与板厚、真实质量/质心/惯量（CAD 零质量权威）、
T_SB、physical TCP、相机数值 FOV、发射合规（standard_12U_claim BLOCKED）、
全局碰撞安全（V1 十处 q0 静态干涉 NEGATIVE_RESULT 继承，global_collision_safety
BLOCKED）。V2-UNK-001..017 全部未闭合。

## 结构

- `00_Master_Skeleton/` 唯一几何驱动源（参数合同：`automation/b3_build_spec.yaml`）
- `01_Primary_Structure/` 4框(FRM_*)+4纵梁(LNG_*)+2甲板+4侧板（截面=显示提案）
- `02/03/04_*` 三舱：volume owner 零实体锚点（无来源尺寸不发明）+ 访问板
- `05_Robot_Mount_Module/` 法兰/板/boss/肋条 + 虚拟F/T面 + 符号六维载荷（无数值）
- `06_B601_Visual_Arm/` accepted URDF/STL 的 q0 轴对齐包络代理（10L/9J 冻结，
  哈希 11/11，见 `source_hash_and_topology_register.yaml`）
- `07_Solar_Array_Interface_Module/` 根部 owner（铰链 UNKNOWN）+ SSOT 冻结尺寸翼板
- `09_Service_Access_and_Harness_References/` 维护/线束/keepout reference（不入 BOM）
- `10_Review_Overlays/` 15 张评审视图（raw+annotated）+ 独立 target 场景（NO_CONTACT）
- `Assembly/Spacecraft_Service_Vehicle_V2_0.SLDASM` 顶装，6 具名配置
- `automation/` 全部构建/校验脚本（可重入、fail-closed、日志在 `evidence/build_logs/`）
- `evidence/` 机器裁决链：b3_00 入口哈希、b3_02/03 几何对拍、b3_08 scoped 干涉、
  digital_thread 16 项清单、b3_10 重开全检+V2-CAD-01..20+退出 Gate

## 复现

依次运行 `automation/` 下：`b3_00_entry_verifier.py` → `sw_skeleton_builder.py` →
`b3_02_verify.py` → `sw_structure_builder.py` → `b3_03_verify.py` →
`sw_mount_builder.py` → `sw_bays_builder.py` → `sw_b601_builder.py`(先
`b3_06_compute_b601_boxes.py`) → `sw_solar_builder.py` → `sw_service_refs_builder.py`
→ `sw_top_assembly_builder.py` → `b3_08_interference.py` → `sw_inventory_exporter.py`
→ `b3_10_views.py` → `b3_10_exit_gate.py`。
需 SolidWorks 2024 + pywin32（先 makepy `sldworks.tlb`/`swconst.tlb`）。

## 已知偏差

见 `evidence/digital_thread/v1_to_v2_deviation_manifest.csv`（D-EQ-01 方程引擎不可用、
D-V2-01 B601 bbox 代理、D-V2-02 框环分段表达、D-V2-03 零实体 owner）。

## 禁止

修改 V1.0 / accepted B601 URDF/STL / 冻结 Gate；FEA/动力学/制造/A5；Git 提交
（除非另行授权）。科学结论只认各 `*_gate_check.json`，本目录不构成科学 Gate。
