# V22-B601-GEOMETRY-AND-POSEMAP-02 独立对抗评审

评审日期：2026-07-27（UTC）　评审性质：以推翻为目标的独立对抗审查（只读，唯一写入=本文件）
被审对象：`V22_B601_GEOMETRY_AND_POSEMAP_02_REPORT.md` 及其 design/cad/staging/validation/src/views 全链
独立验算脚本：`%TEMP%…\scratchpad\adv_check_a1.py`（自 URDF 原始数值手工转录重实现 FK，未 import 任何项目代码）

## 0. 结论

**UPHELD_WITH_CORRECTIONS**

核心科学主张（F1 不可达性、F2 走廊违规、F3 双限位饱和、q6 纯自旋调平、全部 FK 数值）经独立
重推导**逐位复现**；收拢向量 CANDIDATE_HOLD 纪律贯穿；无任何伪造原生 SolidWorks 产物；冻结区
零写入；EE 单一表示成立。未发现任何足以推翻裁决的 HIGH 缺陷。但存在 3 项 MEDIUM 文档/校验链
缺陷（报告 MC10 数值陈旧、报告引用的 machine_verdict.json 不存在、MC11 构造上不可能 FAIL），
须在归档前修正；另有 7 项 LOW。

发现计数：**HIGH 0 / MEDIUM 3 / LOW 7**

## 1. 攻击面裁定表

| # | 攻击面 | 裁定 | 关键证据 |
|---|---|---|---|
| A1 | F1 不可达性 | **CONFIRMED**（主张成立） | 独立 FK：大臂 J2→J3 向量 X_S 分量 ≡ -264·sin(q2) mm（网格实测恒等，误差 1.8e-9 mm）；q2∈[-3.14,0]⇒sin≤0⇒X 倾恒≥0，对 29×41 限位内网格最小值=0.0；joint2 轴 X_S 分量对任意 q1 恒 ≈0（3.7e-6，源于 rpy=-1.5708 对 π/2 的截断）；见证值 dJ3=[-132,0,-35.4] 与 JSON [-132,0,-35] 一致。全部 6 关节心+EE 与交付 JSON 差 ≤0.006 mm；q_deg 六元组、限位判定、走廊 70.89、越顶 158.3、X 包络 338.6、EE 残差 50.58、方向误差 69.25/23.45/16.07 全部逐位复现；q6 双端 ±3rad 扫描 EE 位移=0.0（纯自旋证明成立）。另注：q2=-3.14 **恰在下限上**（裕度 0.000°），q1 距上限 0.428°——F3"双限位饱和"如实甚至保守 |
| A2 | 收拢向量纪律 | **CONFIRMED**（纪律贯穿） | 全目录 grep：CANDIDATE_HOLD 出现于 stow JSON / manifest fk_source / state policy（STOWED 态 status=CANDIDATE_HOLD_STOW_VECTOR）/ 三个生成器 / 报告；"accepted" 仅用于 accepted URDF（权威指称）与禁止性条款本身；无任何文件把拟合角写成 accepted |
| A3 | 数字一致性 | **PARTIAL — 两处失配** | 逐位一致：118.62、110.0、226.0、±310.0、382.69、156.45、140.02、q_deg 六元组、EE/残差/方向误差、Q0 461.98/-269.2 与源盒 467.45（link4 s_box 实在 b601_q0_boxes.json）、钳口 1.2mm、URDF 质量和 4.695555949342986 kg（十链节求和精确复现）。**失配**：报告 MC10 行 min_z=120.96/余量 7.81 vs 机器 JSON 128.53/15.38（见 M1）；报告"安装模块 14 实体" vs STEP 内 MANIFOLD_SOLID_BREP=13 且 registry n_solids=13（见 L1）；报告"另钉…6 项输入哈希" vs precheck 实钉 7 项附加哈希（见 L2） |
| A4 | 伪造检查 | **REFUTED**（无伪造） | 120_ 全树 SLDPRT/SLDASM 计数=0；全部 10 个 STEP 头部如实声明 `Open CASCADE STEP processor 7.8` / `build123d`，无冒充 SolidWorks 原生产物的字段；报告明示"未伪造任何 SLDPRT/SLDASM"。注：cad/、staging/ 下存在隐藏 `.{name}.step.glb` 查看器缓存（非 STEP 文件，见 L4），属工具缓存而非伪造 |
| A5 | 冻结区 | **CONFIRMED**（零越界写入） | 仓库根 `git status --short` 51 条与本轮开始前快照完全一致（全部为既有修改/未跟踪项）；全仓 mtime 扫描（2026-07-27 00:00–02:00 本地=本轮执行窗，precheck 00:15:58 → 末件 00:52）在 120_ 之外命中 **0 个文件**；110_ 最后写入 22:53（上一轮收口）；URDF 权威 mtime=2026-07-11，且本评审独立复算 sha256=1bc2b748…e471c164 与 precheck 逐位一致 |
| A6 | 单一表示纪律 | **CONFIRMED** | 五个 state STEP 文本扫描：`CAP_`（泛化前缀，比 MC8 更严）0 命中、`FIDELITY_CAPTURE_` 0 命中、`G8_PALM` 每态恰 1 次——EE 表示唯一=LOD2 夹爪 |
| A7 | MC 链完备性 | **UPHELD WITH GAPS** | 任务冻结约束全部有对应检查：臂中央 MC1、支承 MC2、翼宽 MC3、翼尖 MC4、L≠R MC5、质量排除 MC6、权威哈希 MC7、EE 互斥 MC8，另加 MC9/10/11。MC2–MC10 为真实比较（阈值→状态可翻转）。**但**：MC1 状态硬编码 FAIL_RECORDED（记录器而非判定器，见 L3）；MC11 构造上**不可能 FAIL**（`"PASS_WITH_COARSE_REVIEW" if pairs else "PASS"`，注释所称"钳口 vs 非夹持件=违规"无任何代码路径产生违规状态，见 M3）；MC6/MC8 grep 面窄（见 L6）；MC7 把 scratch_native 权威钉在会话 Temp scratchpad 易失路径（见 L5） |
| A8 | 视图与几何吻合 | **CONFIRMED** | v01/v07：基座在 +X 端、大臂近垂直（+Z）、前臂越顶回折、夹爪（橙）悬于 -X 端舱面上方且可见净空——与 F1 可达族叙述及 MC10 余量一致；v06 整星收拢态无明显悬空错位。v04 支承：3mm 接触垫横向悬挑超出 46mm 鞍塔宽（LOD2 占位表达）；鞍塔/HDRM 与臂件的 AABB 侵入与 MC11 登记的 28 对粗判一致，未见登记之外的粗大穿模 |
| A9 | 诚实负结果保留 | **CONFIRMED（一处引用缺陷）** | MC1 FAIL_RECORDED 在报告表格顶格如实呈现；六项 HOLD 全数在案且无消解措辞；"运动学事实非建模缺陷"定性经本评审独立复核成立（F1/F2 数学成立；掌板 154mm 与厂商 q0 盒 gripper_link y=±92.035 相容且 LOD2 反而偏窄）。**但**报告 §8 引用"见 machine_verdict.json"——该文件在交付内**不存在**（见 M2） |

## 2. 发现列表

### HIGH（0）

无。

### MEDIUM（3）

- **M1｜报告 MC10 行为陈旧数值，与机器 JSON 失配**
  文件：`V22_B601_GEOMETRY_AND_POSEMAP_02_REPORT.md` 第 82 行（"min_z=120.96（余量 7.81mm，q6 调平后）"）
  vs `validation/machine_checks.json` MC10（`measured_min_z_mm=128.53, margin_mm=15.38`）。
  同源污染：`src/build_staging_states.py` 第 9 行 docstring"z_bottom 156.45/120.96"与
  `design/stow_contact_registry.json` WRIST `z_bottom_mm=140.02` 矛盾。120.96 为 q6 调平前某代
  产物残留，而报告却把"q6 调平后"标注附在旧值上。失配方向保守（真实余量更大），不推翻 PASS，
  但按"科学结论以机器裁决 JSON 为准"的项目约定，报告数字必须改为 128.53/15.38 并清理 docstring。

- **M2｜报告引用的 machine_verdict.json 不存在**
  文件：`V22_B601_GEOMETRY_AND_POSEMAP_02_REPORT.md` 第 97 行（"见 machine_verdict.json"）。
  120_ 全树检索命中 0；validation/ 仅有 machine_checks.json 与 frozen_zone_precheck.json。
  裁决建议目前只存在于报告散文中，无机器可读裁决文件——断链引用。须二选一：补齐
  machine_verdict.json（裁决建议+HOLD 清单机器化）或将报告改为指向 machine_checks.json。

- **M3｜MC11 构造上不可判 FAIL，且"垫接触=预期"无证据支撑**
  文件：`src/run_validation.py` 第 159–182 行。状态表达式
  `"PASS_WITH_COARSE_REVIEW" if pairs else "PASS"` 两分支皆 PASS 族；代码注释宣称
  "钳口 vs 非夹持件=违规"但不存在任何产生违规/FAIL 状态的路径，`intended` 分类计算后仅用于计数。
  又因接触垫按切贴构造（垫顶=臂底），AABB 重叠恒为 0，输出 28 对中 INTENDED_CONTACT 为 0 条——
  报告 MC11 行"垫接触=预期"在机器输出中无对应条目。MC11 实为登记器而非校验器，应在报告中
  如实降格表述（现有 HOLD 4 部分覆盖，但表格将其与真实 Gate 并列呈现）。

### LOW（7）

- **L1｜安装模块实体数：报告"14 实体"，实为 13**。`cad/B601_MOUNT_MODULE.step` 内
  MANIFOLD_SOLID_BREP=13，`design/stow_contact_registry.json` n_solids=13（1 板+1 环+1 载体+
  1 扩载板+4 桥+4 撑+1 预留=13）。报告笔误。
- **L2｜输入哈希计数：报告"6 项"，precheck 实钉 7 项附加哈希**（swap01×2、stage100_brief、
  stage110_gate/armstow/solar90/solar00）。`validation/frozen_zone_precheck.json`。
- **L3｜MC1 状态硬编码**。`src/run_validation.py` 第 62–66 行 status 恒为 "FAIL_RECORDED"，
  不对 40mm 阈值做比较——当前值 118.62 下如实，但该检查无判定功能（几何改动后仍会打印 FAIL）。
- **L4｜cad/、staging/ 非 STEP 杂物**。隐藏 `.{name}.step.glb` 查看器缓存 ×9 与
  `src/__pycache__/`。不属伪造（A4 已裁定），但违反"staging/cad 下应只有 STEP"的字面交付纪律，
  建议清理或入 .gitignore。
- **L5｜MC7 将 scratch_native 权威钉在会话 scratchpad 易失路径**
  （`C:/Users/stude/AppData/Local/Temp/claude/.../b601_import.SLDASM`）。scratchpad 清理后
  MC7 复跑必 FAIL——权威快照应移至仓内 evidence 区或声明其易失性。
- **L6｜MC6/MC8 扫描面窄**。MC6 仅 grep "DENSITY"+总质量数字（单链节质量如 0.8366 不在扫描面）；
  MC8 仅扫 CAP_INTERFACE_RING/FIDELITY_CAPTURE_ 两标记（CAP_HOUSING 等不在面上）。本评审用泛化
  `CAP_` 前缀复扫为 0 命中，当前交付实际干净，属理论性缺口。
- **L7｜LOD2 夹爪 Y 半宽 77mm < 厂商网格 92.035mm**（`b601_q0_boxes.json` gripper_link
  s_box y=±92.035）。MC1 的 118.62 与各 Y 包络数字相对厂商真实几何为**下界**；HOLD 5 精神上
  已覆盖，但走廊违规幅度在 P-C 精细几何下将进一步恶化，建议在 F2 后果栏显式注明。

## 3. 对裁决建议的意见

**同意** `B601_GEOMETRY_POSEMAP02_ACCEPT_WITH_ENGINEERING_HOLDS`，**附修正条件**：

1. 报告 MC10 行改为机器值 128.53/15.38，并修正 `build_staging_states.py` docstring（M1）；
2. 补齐 machine_verdict.json 或修改报告 §8 引用（M2）；
3. MC11 在报告中如实标注"登记器（不可判 FAIL），干涉真伪待 L3 精判"（M3）；
4. 顺手修正 L1/L2 两处计数笔误。

上述均为文档/校验链层面缺陷，不触及几何、映射、FK 或任何科学主张；六项工程 HOLD 应原样随
裁决存续，不得因本评审通过而消解。核心发现 F1–F4 经独立重推导全部成立，本轮交付的运动学
诚实度与冻结区纪律经受住了对抗审查。
