# Unified R2 URDF 休眠源包回执

- 已冻结未来 C01 快照拓扑：15 links / 14 joints / 8 actuated DOF。
- B601 10-link/9-joint 子树继续从接受版 URDF 深复制；质量回算为 31.022864807342987 kg。
- Solar R2 当前只定义固定部署快照；连续三叶手风琴联动未伪造。
- 生成函数 `gen_urdf()` 已建立，但当前调用会 fail-closed，包内没有 `.urdf`。
- 当前 Sim13 loader 与系统模型不兼容，禁止修改历史 baseline 或宣称接触/RL 绑定。
