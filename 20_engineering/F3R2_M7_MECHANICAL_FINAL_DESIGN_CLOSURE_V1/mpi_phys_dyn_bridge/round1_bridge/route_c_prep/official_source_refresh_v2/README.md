# Route-C Official Source Refresh V2

本包把 2026-08-25 的官方制造商/官方标准检索结果收敛为 Route-C RFI-E/F/G 的候选证据与试验输入，不修改冻结的 C2-01 注册表，也不产生产品选择、采购释放或 CAD 权限。

## 机器结论

- 17 条一手官方来源记录；
- 20/20 fail-closed 判据与 20/20 pytest 负控通过；
- P01-P13 仍为 `13/13 null + HOLD`；
- 精确产品选择数为 0；
- `RFI-G08` 仍是 `HOLD_URL_PLUS_DOCUMENT_ID__NO_LOCAL_BYTE_ARCHIVE`；
- `ROUTE_C_CAD_AUTHORIZED=false`；
- `next_stage_authorized=false`。

## 文件

- `inputs/ROUTE_C_OFFICIAL_SOURCE_REFRESH_V2.yaml`：机器可读来源、候选集、字段影响与非等价护栏；
- `docs/ROUTE_C_RFI_EFG_ENGINEERING_SCREENING_V2.md`：工程比较与供应商/试验闭合清单；
- `src/validate_source_refresh_v2.py`：只读上游重算与 fail-closed 校验器；
- `tests/test_source_refresh_v2.py`：基线与篡改负控；
- `results/`：校验、Gate 与输出清单（由校验器生成）。

## 使用边界

目录值只能进入 `SCREENING_CANDIDATE`。必须在精确件号、安装态 BOM、Owner 接受、单位、公差/不确定度、受控来源和字段特定验证全部闭合后，才允许另行评估 C2-01；本包本身不提供该权限。
