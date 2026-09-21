# Mechanical Embodiment Review

_不进行数值打分的 A3 Geometry Only 分层评审_

| 层 | 状态 | 本阶段证据 | 仍缺内容 |
|---|---|---|---|
| Geometry | `VERIFIED_FOR_GEOMETRY_ONLY` | 原生 skeleton、舱体、适配器、B601 q=0 参考装配 | 制造细节、收拢构型、精确 B601 表面 |
| Physical | `BLOCKED_FOR_DYNAMICS` | 唯一质量 owner 规则继承，CAD 标记禁止动力学使用 | 聚合 CoM、惯量、材料和载荷路径 |
| Robotics | `LIMITED_REFERENCE_ONLY` | 10-link/9-joint 身份与 q=0 frame 链 | 关节限位、工作空间、TCP、可达性 |
| Space | `LIMITED_DISPLAY_PROFILE` | 12U 显示包络与任务面 | rail、太阳翼、发射与热控合规 |
| Embodied semantics | `PLANNED_CONTRACT_ONLY` | 任务面、M/A0、末端区域语义和排除项 | 相机硬件、FOV、目标接触语义 |
| Evidence | `VERIFIED_FOR_FILE_TRACEABILITY` | 原生文件、哈希、属性、变换、截图与检查日志 | 下游 CAD/URDF round-trip |

## 结论

当前成果是可供人工评审和后续参数设计使用的数字机械主机，不是完成的空间具身智能系统。它实现了 Geometry、Semantic、Evidence 三层的可追溯入口；Physical 层仍被明确阻断，不能跨级进入动力学或任务性能声明。
