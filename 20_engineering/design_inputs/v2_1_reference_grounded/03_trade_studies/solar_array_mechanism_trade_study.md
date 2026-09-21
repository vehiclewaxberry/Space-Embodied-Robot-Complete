# V2.1 太阳翼机构 Trade Study（B4-0 冻结稿）

> `PHASE: B4-0`
> `SELECTED_REFERENCE: SA-MECH-C01 / CONDITIONAL`
> `PHYSICAL_MECHANISM_DETAIL: HOLD`
> 机构参数全数保持 `UNKNOWN`；公开来源只继承原则，不继承数值、材料、资质或几何。

## 1. 证据边界

- Hyperion 支持“弹簧铰链、固定侧释放/状态检测、每翼两个保持/释放点、线束切口与部署失效构型”等原则级特征；其公开仓库未提供完整翼板或铰链 CAD，完整铰链设计所引用的 `TX2-MC-127` 未随仓库公开。
- Hyperion 的两个释放点只能称为“双保持/释放点”；在独立供电、独立触发和故障逻辑签发前，禁止称为“冗余释放”。
- OreSat Solar 主要提供 ECAD 和模块化电气组织，不能支撑展开铰链、弹簧、止挡或 HDRM 机械几何。
- CDS 只支撑展开物自约束、外包络和验收流程治理；本项目尚未证明任何部署器或发射接口合规。
- B601 的 `q=0` 轴对齐包络只是静态参考，不是可达工作空间。机械臂动态扫掠与相机视场均为
  `NOT_EVALUATED_UNKNOWN_PARAM`。

## 2. 候选机构比较

`HIGH/MEDIUM/LOW` 只表示当前候选之间的相对设计权衡；`BLOCKED` 表示证据不足。

| ID | 机构拓扑 | 可维护性 | 载荷隔离 | 收拢包络 | 扫掠复杂度 | 臂/视觉避让 | 证据成熟度 | 处置 |
|---|---|---|---|---|---|---|---|---|
| SA-MECH-C01 | 双离散铰链形成单一 X 向铰线；弹簧驱动 reference；MID2+REAR 双保持/释放点；独立止挡；柔性服务环 | HIGH：固定侧可达，根模块可整件拆换；消耗性释放件需地面复装 | HIGH（拓扑级）：铰链反力入 MID2 节点垫，收拢约束反力分送 MID2/REAR；不经过侧板和臂安装框 | BLOCKED：`238.3 mm` 叠厚语义与约 `87 mm` 外悬仍开放 | HIGH：单自由度旋转，但轴位和角度未知 | BLOCKED | HIGH，仅限原则级 | **PREFERRED_REFERENCE_ARCHITECTURE / CONDITIONAL** |
| SA-MECH-C02 | 双离散铰链 + 单中央保持/释放点；独立止挡和柔性线束 | HIGH：件数较少 | MEDIUM：单点约束可能引入宽翼扭转和集中载荷 | 相对有利，绝对包络仍 BLOCKED | HIGH | BLOCKED | MEDIUM-LOW，项目原创组合 | RESERVE；需证明扭转与单点故障可接受 |
| SA-MECH-C03 | 可更换柔性铰链/弹性片驱动 + 双保持点 + 独立硬止挡 | LOW-MEDIUM：柔性件寿命后可能需整件更换 | MEDIUM：载荷集中于柔性根部，热应变敏感 | 相对有利，绝对包络仍 BLOCKED | HIGH | BLOCKED | LOW；无已准入项目原始证据 | DEFER |
| SA-MECH-C04 | 偏置四连杆/离架铰链 + 双保持点，使翼板先平移后转动 | LOW：关节、装配和公差链最多 | MEDIUM-LOW：多关节扩大冲击和间隙传递链 | POTENTIALLY_HIGH，可针对 C5 调包络 | LOW：扫掠体最大、状态最多 | BLOCKED，且最易侵入臂/FOV keepout | LOW | CONTINGENCY；仅当 C01 无法闭合收拢包络时重开 |

## 3. 条件冻结的传力意图

以下均为 `LOAD_PATH_INTENT`，不是强度、刚度、冲击、应力或裕度结果。

```text
展开态：
Solar_Wing_[L/R]
  -> HINGE_BLOCK_A/B_REF
  -> ROOT_BRACKET_REF
  -> MID2_[L/R]_NODE_PADS
  -> MID2 frame ring
  -> four longerons / end frames

收拢态：
TIP_RESTRAINT_BAND
  -> HDRM_MID2_REF + HDRM_REAR_REF
  -> corresponding node pads
  -> MID2/REAR frame rings

展开终点：
Solar_Wing_[L/R]
  -> MECHANICAL_STOP_REF
  -> ROOT_BRACKET_REF
  -> MID2 frame nodes
```

机构本体、HDRM、止挡和线束均集中在固定侧；活动翼只保留无源基板与接口语义。左、右根模块必须有独立
`OBJECT_ID`、`IF-SA-L/R`、配置驱动、故障状态和线束出口 owner。允许共用 master skeleton 或派生模板，
禁止共用抑制状态或证据记录。

## 4. 配置族与 claim limit

| canonical configuration | L | R | 允许结论 |
|---|---|---|---|
| `DEPLOYED_NOMINAL` | deployed reference | deployed reference | 展开参考构型，不是部署验证 |
| `STOWED` | stowed proposal | stowed proposal | 收拢提案，不是发射/部署器包络结论 |
| `L_FAIL` | stowed-failed | deployed reference | 场景入口，不是故障分析完成 |
| `R_FAIL` | deployed reference | stowed-failed | 同上 |
| `DEPLOY_FAILED_BOTH` | stowed-failed | stowed-failed | 与预发射收拢态几何相似，但任务语义不同 |
| `PARTIAL` | sweep/reference only | sweep/reference only | 无签发角度时不得伪造中间角 |
| `SERVICE` | service pose UNKNOWN | service pose UNKNOWN | 维修序列入口，姿态由维护规程签发 |

显示配置与任务状态是两个正交维度。缺失关键几何的 SpeedPak 或零实体 reference
不能用于得出干涉无冲突结论。

## 5. 收拢拓扑声明与当前冲突

- 绕根部 X 向铰线折叠，平贴 ±Y 侧面收拢。
- 冻结显示值推导叠厚为 `238.3 mm = 226.3 + 2×6`，大于本体 `226.3 mm`；该值只登记
  C5 冲突，不构成任何部署器包络结论。
- 翼展 `200 mm` 大于半高 `113.15 mm`，约 `86.85 mm` 外悬按人工裁决折向 `-Z`，
  并登记 `STOW_OVERHANG_KEEPOUT`。
- ±Y 侧面后段在收拢态被遮蔽；X=+56.75 前段保持独立可拆。C2、C3、C4 的人工裁决继续有效。

## 6. 必须保持 UNKNOWN

`hinge_pin_diameter`、`bearing_type`、`spring_count`、`spring_stiffness`、
`spring_preload_angle`、`release_wire_material`、`release_wire_diameter`、
`release_electrical_values`、`release_independence_logic`、`locking_or_latching_mechanism`、
`deployment_angle`、`hinge_axis_z`、`deployment_shock`、`stop_contact_count`、`stop_gap`、
`stop_compliance`、`stop_load_share`、`cable_bend_radius`、`harness_service_loop_length`、
`hinge_cycle_life`、`root_bracket_envelope`、`hinge_envelope`、`HDRM_envelope`、
`stop_envelope`、`panel_material`、`panel_layup`、`cell_thickness`、`wing_mass_properties`、
`electrical_bonding_path`、`thermal_interface`、`fasteners`、`preload`。

填值必须原子性附 `evidence_ref` 与 owner 签发，否则 gate FAIL。

## 7. B4-1 入口裁决

```yaml
semantic_reference_scaffold:
  verdict: PASS_CONDITIONAL
  allowed:
    - separate_L_R_assemblies_and_interface_ids
    - zero_solid_named_references
    - seven_configuration_names_and_suppression_logic
    - named_keepout_asset_placeholders

physical_mechanism_detail:
  verdict: HOLD
  release_conditions:
    - B4S-01: 至少三候选、比较准则、处置与异议均已记录
    - B4S-02: Hyperion 准入明确记录缺少完整铰链 CAD 与 TX2-MC-127
    - B4S-03: 选定架构只按原则级继承，并记录 commit/hash/license/adaptation
    - B4S-04: 左右模块的对象、接口、配置和故障状态完全独立
    - B4S-05: 铰链、收拢约束和止挡反力止于具名框架节点垫，不经过 NON_STRUCTURAL_PANEL
    - B4S-06: C5 由 owner 签发；此前所有收拢图保持 PROPOSAL/BLOCKED
    - B4S-07: 提供臂任务姿态扫掠及相机 frame/FOV；否则避让结论保持 NOT_EVALUATED
    - B4S-08: 独立性逻辑签发前不得把双释放点称为冗余
    - B4S-09: 止挡、线束和维修序列进入装配/图纸/配置寄存器
    - B4S-10: must_stay_unknown 通过 fail-closed lint
    - B4S-11: PARTIAL 仅使用 sweep/reference，除非有签发角度
    - B4S-12: 干涉检查使用 full-resolved 太阳翼和机械臂实体；零实体 reference 不得产生 CLEAR
```

sim_07 与帆板 ANCF 路线只提供后续动力学语境。本 trade study 不作质量、频率、展开动力学、
低冲击、可靠性或飞行资质声明。
