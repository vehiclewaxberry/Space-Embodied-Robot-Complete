# R6 外部工具链接入计划（只规划，未安装）

顺序候选为 SPART → Exudyn → MuJoCo → Basilisk → Pinocchio/CasADi。R5 不安装、不迁移 Linux、不把外部后端写成真值。R6 仍为规划态；在阈值 authority 和 R5 runner 失败生命周期获得独立授权前，不执行外部后端。获批后首项才是 SPART accepted-URDF 的 FK、Jacobian、浮动基座质量矩阵与 P/H 对拍；每个后端必须采用独立结果目录、输入哈希和 fail-closed 映射审计。

`R6_LOCAL_LIBRARY_INVENTORY.csv` 只反映本次本地探测；`R6_BACKEND_ACCEPTANCE_CRITERIA.csv` 是准入条件，不是授权。
