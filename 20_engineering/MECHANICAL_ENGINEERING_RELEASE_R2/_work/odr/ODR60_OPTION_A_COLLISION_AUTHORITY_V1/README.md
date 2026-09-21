# ODR-60 Option-A collision authority aggregate V1

本目录根层只汇总两个只读子包，不运行 Route-C 轨迹或路径搜索，也不修改子包文件：

- `base_link_proxy_v2/`：B601 `base_link` STEP-first operational collision proxy；
- `base_link_proxy/`：首轮 67/69 BRep 负结果，只保留为不可变 lineage；
- `system_registry/`：M01 的 150-object、11,175-pair 静态碰撞宇宙账本。

## 双层裁决语义

`proxy_pass` 仅表示固定 STEP、receipt、validation、NPZ、STL 已由顶层 builder 独立验证：receipt schema/checks、artifact SHA/size、68 个代理实体 ID、binary STL 布局、NPZ/STL 三角几何、bbox/计数、两个局部保守 AABB 的源几何包含性、桌面底板排除和禁止原始 URDF mesh 均一致。缺任一文件、部分生成、hash 漂移、validation report 反证或解析异常都 fail-closed 为 HOLD。

首轮 `BASE_LINK_OPERATIONAL_COLLISION_HOLD_DIAGNOSTIC_V1.json` 仍保留 source/BRep 负证据，但不再是当前运行代理。V2 保留 66 个精确 BRep 实体，并以严格公差 AABB 分别替代 DM-J4340P 异常区和薄板异常实体；目录中的 step.parts `DM-J4340P-2EC` 只用于几何/安装包络对照，未被提升为运行碰撞权威。

`proxy_pass=true` 不等于完整系统碰撞通过。当前 registry 仅证明 11,175 对被逐一登记，其中 9 对为冻结的相邻运动学例外，剩余 11,166 对仍是 `UNASSESSED_FAIL_CLOSED/FORBID`。因此顶层固定保持：

```text
complete_system_collision_pass = false
pre_search_ready = false
path_search_executed = false
path_search_authorized = false
next_stage_authorized = false
release_credit = false
```

## 固定根层文件

- `build_odr60_collision_authority.py`：确定性只读汇总 builder；仅 `--write` 时可原子写根层 gate/manifest。
- `ODR60_OPTION_A_COLLISION_AUTHORITY_GATE_V1.json`：机器裁决。
- `ODR60_OPTION_A_COLLISION_AUTHORITY_SHA256_V1.csv`：SHA256 manifest；不包含自身，覆盖根层非缓存核心文件以及两个子包全部非缓存核心文件。
- `test_odr60_collision_authority.py`：确定性、覆盖和 fail-closed 回归测试。

## 复现

从本目录或工作区根目录运行：

```powershell
$env:PYTHONUTF8='1'
python build_odr60_collision_authority.py --check
python -m pytest -q test_odr60_collision_authority.py
```

只有在子包受控变化后重建根层输出时才使用：

```powershell
python build_odr60_collision_authority.py --write
```

manifest 排除 `__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`*.pyc`、`*.pyo`、`*.tmp`、`*.bak` 和 manifest 自身。它不把测试 PASS 升级为科学/飞行 Gate PASS。
