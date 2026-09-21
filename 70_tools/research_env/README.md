# 科研环境工具层（TOOL 层，不含项目事实）

**建立**：2026-09-01
**范围**：Claude Code 在本项目中的 MCP 工具链与用户级 Skill
**层级定位**：本文件只描述**软件能力**（TOOL）。项目专有事实（B601 几何、坐标约定、
Hold）不得写入本文件，也不得写入任何通用 Skill —— 那属于 PROJECT AUTHORITY 层。

---

## 1. 现状

Owner 决策：从 Codex 全量迁移（17 个）→ 删除 6 个 `caehub-*` 路由、1 个重复的
`abaqus-mcp-server`、整个 Fluent 能力（见 §2）→ 收敛到 9 个 → 再按 Owner 批准
补入 `solidworks-agent`（见 §5）→ **当前 10 个**。

- **MCP**：`.mcp.json`（项目级）注册 **10 个** server，路径全部实测存在；
  其中 9 个已于 2026-09-01 连通验证，`solidworks-agent` 待下次会话重启后验证
- **Skill**：`C:\Users\stude\.claude\skills\` 装入 **202 个**（用户级，全项目可见，194 MB）
  - 来源 `F:\codex_skill\AgentSkills\codex-skills\`，用 `cp -rL` 解引用了 168 个
    指向 `F:\CAE-Agent-Hub\Skill\` 的符号链接，得到实体副本
  - frontmatter 校验 202/202 合法
  - **Codex 侧后续改动不会影响 Claude**（实体副本，非软链）

未安装的 2 个：`cua_repl`（Codex 中即 `enabled = false`，启动的是 ChatGPT.exe 桌面程序）、
`node_repl`（Codex 运行时内部组件，管道绑定特定 Codex 会话 GUID，跨宿主无法连接）。

---

## 2. 已删除的 8 个注册，及不要重新加回来的理由

以下是实测记录，不是推测。**若将来有人想"补全"这几个注册，先读完本节。**

### 2.1 删除：必然启动失败（2 个）

| Server | 失败原因 |
|---|---|
| `caehub-cst` | 51 个工具，但 `G:\Program Files\CST Studio Suite 2026` **不存在**。装了 CST 之后才有意义 |
| `caehub-comsol` | 37 个工具，但依赖的 `bridge\target\comsol-bridge-0.1.0.jar` **不存在** |

**COMSOL 用保留的 `comsol`** —— 走 `G:\academic\comsol_link`，是另一套独立实现，
10 个工具组（session / model / parameters / geometry / physics / mesh / study /
results / batch / knowledge）+ resources，不依赖那个 jar。

### 2.2 ⛔ Fluent 能力已整体废弃（`caehub-ansys-fluent` + `ansys-fluent` 均已删除）

**决策**：本项目（12U 服务星 + 空间机械臂，真空环境）不存在 CFD 需求；
而 Fluent 这条链有一个结构性陷阱，留着的净收益为负。**两个注册都已删除。**

#### 陷阱的根因（2026-09-01 读源码确认）

`server.py` 在模块级 import 了 `tools.fluent_bridge` 与 `tools.pyfluent_session`，
但真正的重型 import 藏在**函数体内部**：

```
tools/fluent_bridge.py:106       import ansys.fluent.core as pyfluent   # 函数内，缩进
tools/pyfluent_session.py:12     import ansys.fluent.core as pyfluent   # 函数内，缩进
```

FastMCP 的 stdio server 把 tool 函数体放在 **anyio worker 线程**里执行。
在 worker 线程首次触发 `import ansys.fluent.core` 会**死锁在 CPython 的 import
lock 上** —— `fluent_detect_tool` 永不返回，且不报错、不超时，表现为静默挂起。

**陷阱之所以是陷阱**：`server.py` 可以直接 `python server.py` 运行，看起来就是
正确入口，目录里也没有任何提示。唯一安全入口是
`mcp_server_pyfluent_preload.py` —— 它在主线程先 import 一次再 `runpy` 转交。
该文件的 docstring 记录：2026-07-28 实测，无 preload 挂死，有 preload 约 6 秒返回。

#### 两条可迁移的教训

1. **"优先用 launcher / 官方入口" 的通用直觉在这里是错的**——
   `caehub-ansys-fluent` 走的正是官方 `server.py`，恰恰是坏的那条。
   别把这条直觉照搬到其他 server。
2. **同形风险已排查**：AEDT 的 `pyaedt_backend.py:33,39` 有结构完全相同的
   函数内 `from ansys.aedt.core import ...`，但它通过**外部 broker 子进程**
   架构执行 PyAEDT，重型 import 不发生在 MCP 的 worker 线程里，因此不受影响
   （2026-09-01 `list_aedt_sessions` 实测正常返回）。
   Workbench / Abaqus / COMSOL 三者未发现函数内的重型 import。

#### 若将来真的需要 CFD

重新注册时**必须**指向 `mcp_server_pyfluent_preload.py`，绝不能指向 `server.py`：

```json
"ansys-fluent": {
  "type": "stdio",
  "command": "F:\\CAE-Agent-Hub\\MCP\\Ansys\\Fluent MCP\\.venv\\Scripts\\python.exe",
  "args": ["F:\\CAE-Agent-Hub\\MCP\\Ansys\\Fluent MCP\\mcp_server_pyfluent_preload.py"],
  "env": {
    "ANSYS_ROOT": "E:\\Program File\\Ansys Program\\Ansys Inc\\v231",
    "FLUENT_EXE": "E:\\Program File\\Ansys Program\\Ansys Inc\\v231\\fluent\\ntbin\\win64\\fluent.exe",
    "FLUENT_MCP_JOBS_DIR": "F:\\CAE-Agent-Hub\\MCP\\Ansys\\Fluent MCP\\jobs",
    "FLUENT_VERSION": "23.1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1"
  }
}
```

删除前实测环境是健全的（Fluent 23.1 + PyFluent 0.40.2 均在位），
所以这是**能力裁剪，不是故障**。

### 2.3 删除：同后端重复路由（3 个）

| 能力 | 删除 | 保留 | 说明 |
|---|---|---|---|
| Abaqus | `caehub-abaqus` | `abaqus` | 同一个 `F:\CAE-Agent-Hub\MCP\Abaqus\mcp_server.py`（13 工具） |
| AEDT | `caehub-ansys-aedt` | `ansys-aedt` | 同一 `mcp_server.py`（11 工具） |
| Workbench | `caehub-ansys-workbench` | `ansys-workbench` | 同一 `server.py`（18 工具） |

保留侧把 launcher 的环境变量展开进了 `.mcp.json` 的 `env`，能力完全等价。

### 2.4 删除：Abaqus 的第三条路由 `abaqus-mcp-server`

指向 `F:\codex_skill\mcp\CAE-Agent-Hub\MCP\Abaqus` —— **CAE-Agent-Hub 的第二份完整副本**。

删除的决定性理由：**它和 `abaqus` 硬编码同一个 socket 端口 `48152`**
（`F:\codex_skill\mcp\start_abaqus_mcp.cmd` 与 `start_caehub_abaqus.cmd` 都设
`ABAQUS_MCP_PORT=48152`）。两个 server 同时连同一个 Abaqus CAE 桥接端点，
行为未定义。2026-09-01 实测两者 `ping` 返回完全相同的错误，证实指向同一端点。

**Abaqus 现在只有 `abaqus` 一条路由。**

### 2.5 演示 stub，不是科研工具

`G:\academic\工具链\Aerospace_MCP_Skills\skills\` 全库仅 4 个 py 文件，最大 3.2 KB：

- `ancf-kinematics`（2 工具）：只返回线性形函数 `S1=0.5(1-2ξ/L)`、`S2=0.5(1+2ξ/L)`
  及其导数。源码注释自述"仅作演示，实际需要展开为针对 q=[r1, r1,η, r2, r2,η] 的矩阵"。
  **不做单元装配。** 本项目 `30_simulation/sim_11_coupled_dynamics/` 的自有 ANCF
  实现远强于它 —— 别因为名字对口就拿它的输出当结果。
- `vibration-control`（1 工具）：内容为 `np.linalg.eigvals(A)` + `ct.damp()`
- 同库还有个未注册的 `sympy_mechanics.py`，同为 stub

### 2.6 语义重叠

`skills-bridge` 的设计用途是把 `~/.claude/skills` 等**暴露给 Claude Desktop**。
Claude Code 原生读这些目录，所以它在这里是冗余的（不报错，只是没必要）。

---

## 3. 配置写法说明

`.mcp.json` 相对 Codex 的 `config.toml` 做了两处必要转换：

1. **`.cmd` 用 `cmd /c` 包一层** —— Node 的 spawn 不能直接执行 `.cmd`
2. **`%TEMP%` 展开为实际路径** —— Node 不做 cmd 风格的变量展开
   （`ABAQUS_MCP_LOG`、`AEDT_LOG_DIR` 两处）

直连型 server 把 launcher 的环境变量展开进了 `env` 块，配置自解释、可 diff。
**launcher 内容变更时，本文件与 `.mcp.json` 需同步。**

---

## 4. Abaqus / Workbench 是 socket bridge，不自动拉主程序

MCP 本身不抢 license，但主程序没起来时工具连不上。

**Abaqus 需要两步，只起 GUI 不够**（2026-09-01 实测 `ping` 报错原文确认）：

```bash
"F:/CAE-Agent-Hub/MCP/_launchers/start_abaqus_gui_with_caehub.cmd"
```

然后在 Abaqus/CAE 里手动执行 **Plug-ins → Abaqus MCP → Start Socket Bridge**，
桥接端点 `127.0.0.1:48152`。没做第二步时 `mcp__abaqus__ping` 返回
`WinError 10061 目标计算机积极拒绝`。

Workbench 对应 `start_workbench_gui_with_caehub.cmd`。

主程序安装状态（2026-09-01 实测）：Abaqus `D:\SIMULIA` ✅ / ANSYS v231 ✅ /
COMSOL 6.3 `D:\Comsol63` ✅ / MATLAB R2022b Update 10 ✅（107 个工具箱）/ CST ❌未安装

---

## 5. CAD 现状：`solidworks-agent` 已接入（2026-09-01，Owner 批准 A 路线）

SolidWorks 2024 SP05（`32.5.0.0048`）装在 **`F:\Windows_profile\solidworks\SOLIDWORKS\`**
（非标准位置，注册表 `HKLM:\SOFTWARE\SolidWorks\SOLIDWORKS 2024\Setup` 一致）。
`SolidWorks Flexnet Server` 常驻运行 = 浮动许可；`SolidWorks Licensing Service`
显示 Stopped/Manual 属正常。

### 5.1 ⚠️ 能力边界（2026-09-01 逐符号独立复核，不是引用外部审计）

**40 个工具全部是零件级。装配写入能力为零。**

对 10 个装配 COM 符号做穷尽 grep，**全部 0 命中**：

```
AddComponent  AddComponent5  InsertComponent  AddMate  AddMate5
IAssemblyDoc  AssemblyDoc    EditAssembly     asmdot   swDocASSEMBLY
```

| 维度 | 能力 |
|---|---|
| **写入** | 仅零件：建零件/参数化零件/球体/齿轮/阶梯轴、编辑草图、改尺寸、改特征参数、删特征、回滚、配置、材料 |
| **读取** | 可读**已打开**装配体的包围盒与质量属性（`inspection.py:122,145`）——只读，不能改 |
| **导出** | `solidworks_export_active` 支持 **STEP / IGES / STL / PDF / DXF / DWG**（`server.py:313-315`） |

**`SOLIDWORKS_ASSEMBLY_TEMPLATE` 是死配置** —— 它在 `config.py:18-21` 有声明，
但全代码库没有任何一处用它创建装配体。设了也不会让它获得装配能力。

### 5.2 ⚠️ 配置陷阱：默认模板路径写死成 2025

`config.py:21` 的 fallback 是
`C:\ProgramData\SolidWorks\SOLIDWORKS **2025**\templates\gb_assembly.asmdot`，
而本机是 **2024**。**必须在 `.mcp.json` 的 `env` 里显式给两个模板路径**，
否则指向不存在的目录。当前配置已显式设定并验证存在。

### 5.3 值得用的部分

- `solidworks_compile_feature_graph` / `execute_feature_graph` —— 特征图 DSL，
  比逐条 COM 调用更适合可复现建模
- `solidworks_get_mass_properties` / `get_bounding_box` —— 直接支撑质量预算核对
- `solidworks_inspect_active` / `inspect_relations` / `rebuild_diagnostics` —— 只读诊断
- `solidworks_export_active` —— **这是与 §5.4 STEP 路线的衔接点**：
  SolidWorks 建零件 → 导 STEP → 交给 `cad` / `step-parts` / `urdf` 处理装配与数字线程

### 5.4 装配仍然无解，别指望这条路

项目当前的机械阻塞点是**装配**，而 `solidworks-agent` 恰好在这一项上是空的。
接入它解决的是零件建模与质量属性，不是装配。

装配的现实路径仍是 Skill 侧的 STEP 路线（`cad` / `step-parts` / `cad-viewer` /
`urdf` / `srdf` / `sdf` / `dfam-check` / `dxf`），不碰 COM、不需要 broker。

### 5.5 ⛔ 治理缺口：这条路径当前没有任何兜底

- 无写租约、无路径策略、无证据落盘
- `com_runtime.py:115` 用 `GetActiveObject`，`:127-128` 有 `DispatchEx` 兜底
  → **它能自行拉起一个新的 SolidWorks 实例**
- `SOLIDWORKS_VISIBLE=true` + `SOLIDWORKS_INTERACTIVE_MODE=true`：会操作用户可见的会话
- 原先兜底的 `mechanical-cad-broker` 已随 `CAD_AGENT_STACK` 整体删除

**写入前请自行确认目标路径**；`.claude/settings.json` 的 deny 规则只拦
Bash 里的 `win32com` / `SldWorks.Application`，**拦不住 MCP 服务进程内部的 COM**。

### 值得注意：Skill 库里有不依赖 SolidWorks 的 CAD 路线

本次装入的 202 个 Skill 中包含一组**独立于 SolidWorks** 的 CAD 能力：

| Skill | 用途 |
|---|---|
| `cad` | STEP-first 参数化 CAD，自然语言/图纸建模，源码级 joint 与选择器 |
| `step-parts` | STEP 零件处理 |
| `cad-viewer` | 审阅 `.step` / `.stl` / `.3mf` / `.urdf` / `.sdf` |
| `urdf` / `srdf` / `sdf` | 机器人描述文件生成 —— 对 B601 数字线程直接相关 |
| `dfam-check` | 增材制造可打印性检查（悬垂、壁厚、支撑） |
| `dxf` | 2D 图纸生成 |

这条路线走 STEP，不需要 SolidWorks COM，也不受 deny 规则封锁。
**在 broker 重建之前，这可能是恢复 CAD 工作的现实路径。**

---

## 6. 维护规则

1. 新增 MCP 前先问：这个能力现在有没有别的 server 已经提供？17 → 9 的收敛过程中
   已删 8 个（§2.1–2.4）。**当前没有任何能力存在重复路由。**
2. 任何 MCP 的 `env` 里**只允许路径和开关，不允许密钥**。
3. 后端主程序安装路径变更时，本文件与 `.mcp.json` 必须同步，改后重新验证路径存在性。
4. 202 个 Skill 的 name+description 会进入**每个项目**的每次会话上下文。若上下文吃紧，
   把用不到的从 `~/.claude/skills/` 移走，或改放项目级 `.claude/skills/`。随时可调。
5. 本文件不记录任何项目专有事实。B601 / 12U / 坐标约定等属 PROJECT AUTHORITY 层。
