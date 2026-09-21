# Route‑C 视觉范围声明 V1

## 工程裁决

当前整机方案没有被 Route‑C V8 替换。项目仍是 **12U 服务航天器 + 展开式太阳翼 + 侧挂 B601 六自由度机械臂 + 末端执行器**。

Route‑C V8 的 `FCStd/STEP` 只用于检查 B601 外置线束、夹具、导向件和局部通道；它没有导出完整航天器，也没有把 B601 供应商本体作为可发布实体导出。因此，单独打开该 STEP 时看见的“环形/弯曲零件集合”不是整星造型。

## 正确的整机视图

- 当前机器选定、待人工复核的原生总装：`20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.SLDASM`
  - SHA‑256：`19D85E9C703BEC107396AE84DAB7B12DE5722434FC7D5474B3A5A144A1B590D0`
- 同几何的部署名义 STEP 评审件：`20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step`
  - SHA‑256：`A7549D0E913584FA4AF894A710F5CE9DF363722FD7F4F863B1C3B3FF2B4653C2`
  - 诚实标签：这是哈希绑定的同一装配树部署名义导出，不是本轮重新导出的 F3R2 STEP。
- 总装等轴测图：`20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/11_screenshots/RAW/S01_DEPLOYED_NOMINAL_ISO.png`
- 系统任务场景参考图：`40_evidence/artifacts/visualization/figures/fig_v01_system_assembly_isometric.png`
  - 该图只证明冻结几何场景；图中文字已经明确动力学可容许性尚未建立，不得把它当作动力学 Gate PASS。

## Route‑C 局部图的正确标签

以下图像只允许标为“**被拒绝的 Route‑C V8 局部线束/导向子组件评审图**”：

- `40_evidence/artifacts/mechanical_terminal_closure/route_c_v8_rejected_local_subassembly/V8_REJECTED_ISOMETRIC_20260826T072910Z.png`
- `40_evidence/artifacts/mechanical_terminal_closure/route_c_v8_rejected_local_subassembly/V8_REJECTED_FRONT_20260826T072917Z.png`
- `40_evidence/artifacts/mechanical_terminal_closure/route_c_v8_rejected_local_subassembly/V8_REJECTED_TOP_20260826T072922Z.png`

禁止将这些图标为“整星总装”“机械臂+卫星最终方案”“已集成 Route‑C”或“机械发布构型”。

## 当前 V8 处置

- 10/10 个强制关键状态为 `UNSAFE`。
- 两个 J4 位置在加入裕量折减前已经发生实体穿透；V8 候选 3 已淘汰。
- J3 归属假碰撞已通过实体边界夹具和截面归属拆分消除。
- D2、D3 只取得局部早筛 PASS，尚不构成完整任务 Gate PASS。
- 四轮 BUILD→SWEEP 预算已耗尽，但没有完成三类真正异构的技术候选，故不能声称局部外置引导架构不可行，也不能签发架构升级 Gate。
- 在 Owner 选择并授权新的异构物理方案前，Route‑C、TMG‑4、系统绑定和发布均保持 fail‑closed。
