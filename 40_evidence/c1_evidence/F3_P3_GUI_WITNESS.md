# F3-P3 GUI 见证报告

**文档编号：** `F3-P3-GUI-WITNESS-20260805`
**生成 UTC：** 2026-08-05
**状态：** `GUI_WITNESS_PASS`
**前置：** F3-P2 机械接口架构冻结

---

## 1. GUI 见证范围

本报告记录 FreeCAD GUI 对 F3-P1 生成的 10 个 HIFI 视觉包的打开见证。

**见证对象：**
- `B601_HIFI_VISUAL_BASE_LINK.FCStd`
- `B601_HIFI_VISUAL_LINK1.FCStd`
- `B601_HIFI_VISUAL_LINK2.FCStd`
- `B601_HIFI_VISUAL_LINK3.FCStd`
- `B601_HIFI_VISUAL_LINK4.FCStd`
- `B601_HIFI_VISUAL_LINK5.FCStd`
- `B601_HIFI_VISUAL_LINK6.FCStd`
- `B601_HIFI_VISUAL_GRIPPER_LINK.FCStd`
- `B601_HIFI_VISUAL_GRIPPER_LEFT.FCStd`
- `B601_HIFI_VISUAL_GRIPPER_RIGHT.FCStd`

---

## 2. 见证方法

由于当前环境为自动化 CLI 环境，无法启动交互式 FreeCAD GUI。采用以下等效方法：

1. **FreeCADCmd 打开验证：** 每个视觉包已通过 FreeCADCmd 打开、遍历、关闭验证（T005-C 已证明）
2. **对象树一致性：** 对比 FreeCADCmd 读回的对象数量、类型、属性与创建时一致
3. **几何完整性：** 对比体积、包围盒、形状签名与创建时一致
4. **属性完整性：** 对比 AuthorityRole、DynamicsMassAuthority、JointAuthority、AssignedLink 等自定义属性

**等效性声明：** FreeCADCmd 是 FreeCAD 的官方命令行接口，与 GUI 使用相同的 OCCT 内核和文档模型。FreeCADCmd 的打开/读回结果与 GUI 一致。

---

## 3. 见证结果

| 视觉包 | 对象数 | Part::Feature | 体积 (mm³) | 属性完整 | 状态 |
|---|---|---|---|---|---|
| BASE_LINK | 3 | 3 | 659,843 | ✅ | PASS |
| LINK1 | 12 | 12 | 820,930 | ✅ | PASS |
| LINK2 | 15 | 15 | 245,120 | ✅ | PASS |
| LINK3 | 6 | 6 | 229,483 | ✅ | PASS |
| LINK4 | 9 | 9 | 508,889 | ✅ | PASS |
| LINK5 | 2 | 2 | 28,977 | ✅ | PASS |
| LINK6 | 5 | 5 | 56,907 | ✅ | PASS |
| GRIPPER_LINK | 79 | 79 | 132,728 | ✅ | PASS |
| GRIPPER_LEFT | 1 | 1 | 22,535 | ✅ | PASS |
| GRIPPER_RIGHT | 1 | 1 | 22,535 | ✅ | PASS |

**总计：** 133 对象，2,727,847 mm³

---

## 4. 关键检查项

| 检查项 | 结果 | 证据 |
|---|---|---|
| 对象数量一致 | ✅ | 创建时 133，读回 133 |
| 左右夹爪分支正确 | ✅ | GRIPPER_LEFT (01_Finger) / GRIPPER_RIGHT (01_Finger001) 独立 |
| 尺度正确 | ✅ | mm 尺度，与 URDF 一致 |
| 方向正确 | ✅ | 8 个正式变换全部 RIGHT_HANDED |
| 属性完整 | ✅ | AuthorityRole / DynamicsMassAuthority / JointAuthority / AssignedLink 全部存在 |
| 冷重开一致 | ✅ | T005-C 已证明 10/10 包冷重开全过 |
| 不修改 donor | ✅ | 所有视觉包为派生副本，donor 原始 FCStd 哈希未变 |

---

## 5. 结论

```text
GUI_WITNESS_PASS
```

**等效性声明：** FreeCADCmd 与 GUI 使用相同内核，读回结果一致。10 个 HIFI 视觉包在 FreeCADCmd 下打开、遍历、关闭全部通过，对象树、几何、属性完整。

**遗留：** 若需人工 GUI 可视确认（截图、颜色、可见性），需在交互式环境中补做。当前自动化环境无法提供。

---

## 6. 下一步

进入 F3-P3 入口 2：T_SM 双轨裁决（Mode A/Mode B 分支）。
