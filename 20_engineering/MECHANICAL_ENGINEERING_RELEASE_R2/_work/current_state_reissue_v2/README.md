# R2 Current-State Reissue V2

这是一个 **append-only 当前状态重发包**。它不修改
`MECHANICAL_ENGINEERING_RELEASE_R2` 的冻结父文件，也不把候选证据升级为机械、动力学、控制、Sim13、制造或飞行放行。

## 三层、无自引用

生成顺序固定为：

1. `R2_CURRENT_STATE_INPUT_MANIFEST_V2.json`：一次性读取并绑定 27 个当前源的相对路径、字节数、SHA-256、角色和权威上限；
2. `R2_CURRENT_STATE_GATE_V2.json`：只绑定第一层，登记当前事实和 28 项完整性判据；
3. `R2_CURRENT_STATE_PACKAGE_MANIFEST_V2.json`：绑定 builder、validator、README、pytest、第一层和第二层；明确排除自身。

第二层不引用第三层，第一层不引用第二、三层。所有生成层的
`next_stage_authorized` 与 `release_credit` 都保持 `false`。

## 当前重发所登记的关键事实

- 冻结 `01_BASELINE_MANIFEST.json` 实际字节数/哈希与其内部 self entry 不符；只登记，不修复父文件。
- ODR-60 Option A 已选择，执行安装拼写与 B601 子树 10/10 帧行已闭合；M01 三阶段实例仍为 0/3，clearance 0/11166、motion 0/150、pair oracle 0/11166、连续边 0，路径搜索未执行。
- Route-C V9F 在当前冻结 M01 直线关节插值的 0.5 位置存在精确负见证：raw `-10.729480331980062 mm`、gated `-17.313396996697108 mm`。这不是“所有替代路径均不可能”的证明。
- Sim13 `20/20` 只属于追加的后端负控子域；冻结终端快照仍是 `15/20`，full TMG-6 没有重发，最大运行态仍是 `ABORT_ONLY`。
- DG1/DG2、DG3、DG4、DG5 与 V3 分别是 15/15、30/30、15/15、16/16、19/19 的有界追加候选；父 Dynamics 仍为 1/6 HOLD。
- 控制预开发是 9/9 候选包装但技术闭环为 false；父 Control 为 false；Joint 为 4/13、`joint_system_ready=false`。历史 SAFE PASS 仍是待审且不授权下一阶段。
- L06 的 8 张图全部 `manufacturing_use=PROHIBITED`。D05/D06 仍标注 `AL6061-T6 CANDIDATE`，当前材料选择把 M3R Stage A/B 定为 `PMAT-AL7075-T651-SHEET-PLATE`；D05/D06/D08 与设计 BOM 的 `PENDING_SIBLING_HASH` 债务被逐文件计数。该包不替 Owner 做材料或图纸裁决。

## 复现

在本目录执行：

```powershell
python build_current_state_reissue.py --write
python build_current_state_reissue.py --check
python validate_current_state_reissue.py --json
python -m pytest -q -p no:cacheprovider tests/test_current_state_reissue.py
```

builder 使用严格 JSON 解析（重复键拒绝），validator 对三层做确定性字节复算、路径越界防护、27 源哈希复核、六个非自指包条目复核及至少 22 项独立检查。pytest 包含正向回放与来源、负见证、权威字段、路径、层级和 manifest 篡改负控。

## 权威边界

本 Gate 的 PASS 仅表示“当前状态重发完整性通过”。以下状态全部保持 false/HOLD：完整 CAD、M01 搜索、Route-C/G12、物理接触/附着、非 ABORT 抓取、完整动力学、完整控制、Sim13 系统放行、制造、资格鉴定与飞行发布。
