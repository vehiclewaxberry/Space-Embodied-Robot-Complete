# WP04 数字身体与全系统接口合同

当前绑定：**FINAL_CURRENT_CANDIDATE**；来源 F:\China Graduate Future Flight Vehicle Innovation Competition\01_project\competition\SERVICE_ROBOT_MECHANICAL_CONSOLIDATION_20260905\runs\wp04_robot_assembly_20260906_175153\candidate。共有585个实例、585条逐实例挂载记录、11类系统合同和9条原始关节合同。

本包覆盖几何、物理属性、任务语义和证据四层。当前用户授权用于机械设计和数字装配；历史裁决保持原范围。合同字段完整不等于物理输入已落实。

- SYSTEM_INTERFACES.json：继承实例角色、质量owner和三态变换；挂载名准确命中实际实例才解析对端，否则保留逻辑接口。最终版并入R07具名多端连接、孔段、承压面、紧固件及指定装配阶段路径，绑定R07_REVIEW_FINAL.json；材料等级/预紧/螺纹/强度保持未知。其余未登记对偶、针脚和热阻仍为null。
- DIGITAL_BODY_CONSUMER_CONTRACT.json：原始关节范围/effort/velocity与物理限位分账。源velocity 50/200、夹指15没有可继承的物理单位权威；不自动转成硬件限幅。质量按唯一owner计一次，未知不得零填。
- RELEASE_STATE_CONTRACT.json：退销→开盖→下鞋退离→折退锁止→臂首动→翼展开→服务动作前置确认。传感器、阈值、时限、功耗及载荷未实选字段未知。
- release_logic.py：只做离线合同检查，不读硬件、不发命令、不替代SAFE-00或Sim13；合成样例满足时hardware_command_authorized仍为false。

整机图必须与收据实例集合、arm_link和三态变换一致。名义BRep、accepted STL、功能包络和爆炸示意有不同用途。全臂可见不等于拓扑、双指、包含、臂星体或连续路径通过。

设备/ADCS/推进、腕部F/T/TCP、线束、翼HDRM和发射接口有具名缺项。旧控制/接触PASS不移入本候选。静态整体惯量只用于锁定相对运动的该姿态；运动模型保留逐link自由度和未知项。

最终生成后依次运行 python -B contracts/bind_contracts.py --final；python -B review/digital_body_controls.py；python -B review/robot_actual_ledger.py。不带--final的合同明确来自R01开发基线，不是WP04最终证据。
