# M01 system pair-oracle backend V1

## 工程定位

本包实现当前 `SYSTEM_PAIR_ORACLE_CONTRACT_V1` 的隔离软件后端，并只用合成、哈希绑定的 10 mm BRep 立方体验证数值与 fail-closed 语义。它不加载现役 150 对象几何，不执行 11,166 个系统必查 pair，不签发连续边、路径、父机械 Gate 或 release credit。

最高合法主张固定为：

```text
PAIR_ORACLE_SCHEMA_AND_FAIL_CLOSED_BACKEND_IMPLEMENTED_AND_SYNTHETICALLY_VALIDATED__
ZERO_CURRENT_SYSTEM_PAIR_QUERIES__ZERO_SAFE_PAIRS__
NO_EDGE_PATH_PARENT_OR_RELEASE_CREDIT
```

## 当前语义

- `SAFE`：所有绑定完整，OCP 查询有限且完整，认证下裕量严格大于 0。
- `UNSAFE`：只能由认证上裕量不大于 0 或完整接触/相交见证签发。
- `UNKNOWN`：缺 authority/hash、几何读取或后端失败、空解、非有限后端结果、未认证降额或门槛歧义。
- `FAIL`：请求结构、单位、frame、policy、例外或确定性合同非法，执行必须中止。
- `EXEMPT_ADJACENT`：仅精确 exception-set 成员；不计作 SAFE，且禁止出现任何几何字段。

旧 `continuous_edge_certificate.py` 只保留为历史算法骨架。其旧 `FAIL -> UNSAFE` 和“样点未过阈值直接 UNSAFE”语义没有被复制到本包。

## 单位账本

| 边界 | 输入 | 内部/输出 | 规则 |
|---|---|---|---|
| BRep 资产 | native mm | OCP mm | 禁止自动猜测 |
| S 系位姿平移 | m | OCP mm | 仅在载入边界显式乘 `1000.0` |
| 位姿旋转 | 4×4 row-major binary64 | dimensionless | 必须为刚体变换 |
| q | rad, exact binary64 bytes | rad | hash 绑定，禁止重用漂移结果 |
| distance / witness / clearance / derate / margin | mm | mm | 禁止隐式 m/mm 转换 |

完整数值账本为：

```text
d_lower = (((d_raw - e_A) - e_B) - e_backend)
m_lower = d_lower - d_required
m_upper = d_upper - d_required
```

下界按 IEEE-754 binary64 左结合计算。`d_lower <= d_required` 只说明 SAFE 未证；若没有独立上界或接触见证，结果必须为 `UNKNOWN`。

## 文件角色

- `M01_SYSTEM_PAIR_ORACLE_BACKEND_CONTRACT_V1.json`：本包合同与最大主张。
- `SOURCE_AUTHORITY_LOCK_V1.json`：当前 M01、clearance、scene、parent Gate 的只读哈希锁。
- `SYNTHETIC_FIXTURE_SPEC_V1.json`：合成几何、位姿、阈值与预期状态。
- `pair_oracle_backend.py`：OCP BRep pair oracle 核心。
- `build_m01_system_pair_oracle_backend.py`：确定性构建、合成证据、负控、Gate 与清单。
- `validate_m01_system_pair_oracle_backend_independent.py`：不导入候选核心的独立 OCP 复算。
- `test_m01_system_pair_oracle_backend.py`：接口、数值、权限与确定性测试。
- `fixtures/`：合成 BRep 资产，不属于当前 M01 registry。
- `results/`：机器证据、独立验证、负控、Gate、manifest 与 SHA-256 inventory。

## 复现

从项目根目录运行：

```powershell
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/build_m01_system_pair_oracle_backend.py --write
python -m pytest -q 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/test_m01_system_pair_oracle_backend.py
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/validate_m01_system_pair_oracle_backend_independent.py --check
python 20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SYSTEM_PAIR_ORACLE_BACKEND_V1/build_m01_system_pair_oracle_backend.py --check
```

若 source lock、fixture BRep、证据、Gate 或清单任一字节漂移，`--check` 必须失败。当前 clearance policy 仍为 0/11,166、三阶段实例 0/3、系统 pair query 0、连续边 0、路径未执行。
