# V2 B3 System Mechanical CAD Construction Plan

> `STATUS: CONSTRUCTION_PLAN_READY`  
> `EXECUTION_AUTHORIZED: false`  
> 本计划只有在 B3 人工 Gate 获批后才能执行。

## 1. 开工前检查

必须同时满足：

1. `COMP-PROT-03-A4-B3-V2-SYSTEM-MECHANICAL-CAD` 人工授权存在；
2. A4-B2 packet `21/21 HASH_MATCH`；
3. V1.0 native CAD `32/32 HASH_MATCH`；
4. V1.0 seal SHA-256 一致；
5. 本 B2.5 input packet hash manifest 全部匹配；
6. profile、`T_SM`、B601 topology 和 unknown register 未被改写；
7. V2.0 输出根不存在，或已有根经人工确认是本次合法续建对象。

任一失败即停止。

## 2. 预留文件树

```text
Space_Embodied_Robot_CAD_V2_0/
├── 00_Master_Skeleton/
├── 01_Primary_Structure/
├── 02_Front_Mission_Module/
├── 03_Avionics_EPS_ADCS_Bay/
├── 04_Rear_Service_Module/
├── 05_Robot_Mount_Module/
├── 06_B601_Visual_Arm/
├── 07_Solar_Array_Interface_Module/
├── 08_Payload_Perception_Interface/
├── 09_Service_Access_and_Harness_References/
├── 10_Review_Overlays/
├── Assembly/
└── evidence/
```

## 3. 建模顺序

### Phase 0 — Version and source lock

- 创建独立 V2 根；
- 复制输入 manifest，而不是复制 V1 原生零件；
- 记录 A4-B2、B2.5、SSOT、URDF/STL 和许可来源；
- 禁止活动引用 OreSat/vendor CAD。

### Phase 1 — Master Skeleton

- 建立 body envelope、分舱面、`S/M/A0`、solar root 和 interface planes；
- 建立 named equations/design table；
- 所有 unknown 参数为空或 suppressed；
- 导出 parameter/property inventory。

### Phase 2 — Primary Structure

- 建立 front/rear frames、4 个长向主构件、4 道框环和两道 bay boundary decks；
- 主结构和次结构使用不同 subassembly/object class；
- 不分配材料、真实截面、连接或强度属性；
- 生成结构闭合视图。

### Phase 3 — Robot Mount Module

- 继承 `T_SM`、flange 和 adapter reference geometry；
- 建立 adapter、局部加强提案和 task-face load-spreading frame；
- 显示 B601→mount→primary structure 反力链；
- bolt/locator/load/stiffness 保持 null；
- 不导入 vendor STEP。

### Phase 4 — Subsystem Packaging

- 按 volume-owner register 建立独立 placeholder；
- 不选择具体 OBC/EPS/电池/RW/推进/相机硬件；
- 记录 mount-plane/service-direction/harness-entry 未知字段；
- placeholder 不进入质量和材料权威。

### Phase 5 — Serviceability and deployables

- 建立可拆板、工具访问、托盘抽取和线束 corridor reference；
- 建立 solar root/interface、deployed reference 和 stowed proposal；
- 保留 rail/tab、plume、antenna、thermal、sensor keepout owner；
- 不声称真实维护或部署资格。

### Phase 6 — B601 and semantic interfaces

- 使用 accepted B601 10-link/9-joint visual identity；
- 检查 q0 transform 和 source hash；
- 保留 `G/E_virtual`；
- physical TCP、contact 和 target active assembly 继续禁用。

### Phase 7 — Native verification and evidence seal

- 重开、重建、引用和 missing component 检查；
- 导出 document/property/feature/component inventory；
- 按具名配置执行 scoped interference；
- 继承并解释 V1 的 10 处 q0 静态干涉负结果；
- 生成 raw/annotated review views；
- 核验 V1、Gate、config、URDF、simulation 未改；
- 形成 V2 evidence seal 和人工退出审查。

## 4. 一级对象属性

每个一级文档至少具有：

```text
OBJECT_ID
SYSTEM_OWNER
PARENT_ID
STRUCTURE_CLASS
REPRESENTATION_LAYER
EVIDENCE_STATE
SOURCE_REFERENCE
FRAME_ID
INTERFACE_IDS
MASS_OWNER
NO_DYNAMICS_USE
MANUFACTURING_AUTHORITY
EXECUTION_AUTHORITY
CLAIM_LIMIT
BLOCKED_CONSUMERS
```

## 5. 配置

- `STRUCTURAL_REVIEW`
- `SERVICE_ACCESS_REVIEW`
- `DEPLOYED_REFERENCE_Q0`
- `STOWED_PROPOSAL`
- `EVIDENCE_STATE_REVIEW`

每次 interference/clearance 截图和报告必须写明 configuration、joint state、solar state、suppressed components 和 claim limit。

## 6. 禁止用“视觉闭环”代替工程闭环

以下不构成 B3 完成：

- 增加蜂窝纹理、螺栓外观或更多颜色；
- 给 placeholder 分配默认材料；
- 通过 suppress 组件消除干涉；
- 把爆炸视图当装配/维护可达性；
- 把反力链箭头当强度验证；
- 把 target 放到夹爪中当捕获验证。

## 7. B3 退出

未来退出标准以 A4-B2 的 `v2_review_and_acceptance_matrix.md` 为准。本计划不降低任何 V2-CAD-01..20 条件，也不自动授权 B4、FEA、动力学或数字孪生。
