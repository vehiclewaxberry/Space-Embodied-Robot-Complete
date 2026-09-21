# Rail and Protrusion Overlay Review

_A3 Geometry Only，2026-07-23_

> `STATUS: DISPLAY_GEOMETRY_ONLY`  
> `DEPLOYER_RAIL_COMPLIANCE: NOT_VERIFIED`  
> `PANEL_CONFIGURATION: UNKNOWN_EXCLUDED`

## 已表达的轴向区间

以 `S` 为基准：

| 对象 | `x_S` 区间 | 说明 |
|---|---:|---|
| 12U 显示主体 | `-170.25 ... +170.25 mm` | `COMPETITION_DISPLAY_V0` |
| 适配器板 | `+158.25 ... +170.25 mm` | 嵌入主体前端凹槽 |
| 航天器法兰环 | `+170.25 ... +185.25 mm` | 160 × 160 mm 外包络 |
| 适配器 boss | `+170.25 ... +185.25 mm` | Ø100 mm，填入法兰中心间隙 |
| B601 | 从 `x_S=+185.25 mm` 的 `A0` 开始 | q=0 包围盒参考 |

12U 主体加法兰的静态轴向几何区间为 `-170.25 ... +185.25 mm`。这不代表部署器允许长度。

## 本阶段未建立

- CDS/部署器 rail 截面
- rail 接触面与导向长度
- 太阳翼收拢/展开构型
- 天线、相机、线束和热控突出物
- B601 收拢锁定构型
- 发射包络与载荷路径

## 裁决

当前 CAD 足以显示主体、嵌入式安装堆叠和机械臂参考包络，但不能通过发射包络或 rail 合规验收。进入工程 CAD 前，必须由 Spacecraft Configuration Owner 选择收拢构型并提供部署器约束。
