# CDS Appendix B 12U 人工目视复核记录

*Candidate-input evidence record; not a launch compliance certificate*

---

> `REVIEW_SCOPE: 12U rail-reference drawing only`<br>
> `REVIEW_STATUS: REVIEWED_FOR_CANDIDATE_INPUT`<br>
> `LAUNCH_OR_DEPLOYER_CONFORMANCE: not assessed`<br>
> `DB-BLK-005: CLOSED_WITH_EVIDENCE_FOR_12U_A2_SCOPE_ONLY`

## 📄 来源

| 字段 | 值 |
|---|---|
| 本地 PDF | `20_engineering/stage1_spacecraft_layout/01_standards/CubeSat_Design_Specification_Rev14_1_2022-02-09.pdf` |
| SHA-256 | `221fbbbd4f632b16f3e219d1a5e2c2b04e1998c12025b793e6dfc6181af66b5d` |
| 页数 | 34 |
| 人工查看页 | PDF 第 34 页 |
| 图号 | `CDS-14-008` |
| 图名 | `12U CUBESAT` |
| sheet | `1 of 1` |
| 复核日期 | 2026-07-23 |
| 复核方式 | 直接渲染并人工目视第 34 页；正文第 10–12 页交叉核对 |

## 📐 已复核字段

| ID | 字段 | 复核值 | 来源位置 | A2 用法 |
|---|---|---:|---|---|
| `APPB-12U-001` | 12U overall length | `366.0 mm` | p.34, `CDS-14-008` | 新候选 12U rail-reference 长度 |
| `APPB-12U-002` | 12U cross-section X | `226.3 mm` | p.34, cross-section view | 候选横截面 |
| `APPB-12U-003` | 12U cross-section Y | `226.3 mm` | p.34, cross-section view | 候选横截面 |
| `APPB-12U-004` | coordinate origin | geometric center | p.34 drawing note; p.10 text | frame `S` 的候选几何原点 |
| `APPB-12U-005` | rail end contact surface | minimum `6.5 mm × 6.5 mm` | p.12 text; p.34 `6.5 MIN` detail | rail/contact keepout 检查输入 |
| `APPB-12U-006` | rail-to-first-protrusion distance | minimum `8.5 mm` | p.11–12 text; p.34 detail | 首突出物检查输入 |
| `APPB-12U-007` | rail contact fraction | at least `75%` | p.12 text | fit-check 条件 |
| `APPB-12U-008` | yellow-face protrusion normal to rail plane | maximum `6.5 mm` | p.11 text | 收拢状态突出物检查输入 |
| `APPB-12U-009` | typical 12U maximum mass | `24 kg` | p.12, Table 1 | 仅作为警戒/参考，不是当前组合质量上限证明 |
| `APPB-12U-010` | 12U CoG range from geometric center | X `±4.5 cm`, Y `±4.5 cm`, Z `±7 cm` | p.12, Table 2 | 后续质量布局检查，不代表已满足 |

## ⚠️ 明确保留的未知

- 本轮没有复核 1U、3U、6U 图纸；旧 TODO 中相应条目保持 open。
- 没有把图纸中难以可靠辨认的公差、倒角、表面处理或 standoff 细节升级为 CAD 硬值。
- 没有选择特定商业部署器，也没有核对其 CIFP 或最终 fit-check 要求。
- 没有证明当前 `servicer_12U_v0` CAD/STEP/URDF 满足上述尺寸。相反，当前 block-model 的 `340.5 mm` 长度与复核的 `366.0 mm` 不同，必须视为 legacy placeholder。
- 没有证明适配器、B601、相机、帆板或线缆满足突出物和 rail keepout。

因此，本记录只关闭“12U 候选设计缺少人工图纸复核”这一 A2 子问题，不关闭发射合规、部署器兼容或现有 CAD 合规问题。

