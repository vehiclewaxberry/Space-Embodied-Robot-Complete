# ASM-00 接口前检职责占位

> 本目录当前只包含职责说明，不包含科学模型、源码、配置、结果或新的 Gate。

Legacy path:

`30_simulation/asm_00_interface_preflight/`

Current role:

`Interface preflight`

## 当前裁决

- 历史路径名称中的 `interface_ssot` 不表示正式接口 SSOT 已经存在。
- 历史对象仍是 `LOCAL_ONLY_UNTRACKED + BLOCKED` 的 fail-closed 授权前检胶囊。
- 它不包含正式 ASM-00 资格化、HAG-A/HAG-B 批准、ASM-01/ASM-02 实施或装配科学结果。
- 历史路径及其中 Gate JSON、测试、哈希和输出保持原位且只读。

## 未来迁移条件

只有比赛冻结解除且另立迁移任务后，才可考虑把历史对象物理归并到本命名空间。该任务至少必须同时具备：

1. 完整旧路径到新路径 manifest；
2. 全库引用原子改写；
3. Gate JSON 与证据 manifest 的迁移前后 SHA-256 对拍；
4. 机器测试和链接完整性复验；
5. 明确的人类授权。

在这些条件满足前，本目录不得出现历史对象的平行副本。路径锁定说明见 [`../../PROJECT_MAP.md`](../../PROJECT_MAP.md)，装配状态边界见 [`../../10_research/00_project_architecture/experiment_roadmap.md`](../../10_research/00_project_architecture/experiment_roadmap.md)。
