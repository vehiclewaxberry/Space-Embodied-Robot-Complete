# 项目目录与文件命名规则

## 1. 目录

- 使用小写 ASCII `snake_case`。
- 治理目录可以使用 `00_`、`10_`、`80_`、`90_` 表示阅读顺序。
- 科学模块沿用 `<kind>_<NN>_<short_name>`，例如 `sim_12_strategy_feasibility`、`control_02_base_attitude`。
- 不再新增 `final`、`new`、`latest2`、`最终版`、`临时` 等无法长期维护的目录名。

## 2. 文件

- 稳定入口不带日期：`README.md`、`current_state.md`、`system_architecture.md`。
- 不可变快照采用 `<topic>_YYYYMMDD.<ext>`。
- `v1/v2` 主要用于配置、接口和数据 schema；普通状态报告优先使用日期快照。
- 机器读取文件和代码使用 ASCII 名称；中文可作为报告标题或来源文件名。

## 3. 资产所有权

- 科学结果只进入对应模块的 `results/`。
- 测试与实现跟随模块，不建立新的全局 `src/` 或 `tests/` 分片。
- 跨模块配置进入 `20_engineering/config/`；模块私有配置放在模块内部。
- 生成媒体进入 `40_evidence/artifacts/`，不得作为唯一科学真值。
- 原始外来资料先进入 `01_project/inbox/`，经登记后再归档。

## 4. 副本规则

每项资产只允许一个 canonical source。确需发布镜像时，镜像清单必须记录 `generated_from`、源 SHA-256 和生成状态；不得把发布镜像误写成第二份真值。

## 5. 竞争期例外

已被 Gate、manifest、测试或冻结合同绑定的旧路径暂不物理改名。例外清单以仓库根目录 [`PROJECT_MAP.md`](../../PROJECT_MAP.md) 为准。
