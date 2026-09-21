# V4 SOLIDWORKS attach-only 安全门

`mfinal_solidworks_v4_attach.py` 是 F3R2 V4 后继路径中的安全门和证据结构，不是 CAD 生成器。

当前版本有意保持以下边界：

- 只附着当前用户已经人工启动的 SOLIDWORKS；没有运行实例时返回 `ATTACH_REQUIRED`。
- 只接受 SOLIDWORKS 2024（Revision major `32`）。
- 不启动、关闭或隐藏 SOLIDWORKS，也不改变用户会话控制状态。
- 不打开、保存或修改 CAD 文档。
- 默认构建模式只做预检、排他创建 run-id 目录并写入 `NATIVE_BUILD_NOT_IMPLEMENTED_HOLD` 回执；创建 CAD 数始终为 0。
- `--verify-only` 只检查已有包的文件、哈希和闭文档依赖；即使静态验证 PASS，也不宣称原生重建、干涉、工程图/BOM 内容或制造放行已经通过。
- 既有 F3R1、F3R2、M2、M3R、donor 和历史回执均不在本工具写入范围内。

## 强制操作条件

1. 先关闭其他高内存程序，人工观察一段时间，确认可用物理内存稳定在 **6 GiB 以上**。脚本只记录一次内存快照，不能替代人工的“稳定”判断。
2. 人工交互启动 **SOLIDWORKS 2024 SP05**，等待界面完全可用；脚本不会代为启动。
3. 使用 64 位 Python，并安装与 SOLIDWORKS 位数匹配的 `pywin32`。
4. 构建和冷验证必须使用两个独立 Python 进程：
   - 进程 A：未来完整 native builder 生成并关闭所有 V4 文档，然后人工退出 SOLIDWORKS。
   - 人工重新启动一个干净的 SOLIDWORKS 会话。
   - 进程 B：运行本工具 `--verify-only`。如果任何目标 SLDPRT/SLDASM/SLDDRW 已在内存，本工具立即失败。
5. 当前脚本尚未实现进程 A 的 native builder，因此默认模式永远是 HOLD；不要把 HOLD 回执改名或解读为 PASS。

## 固定写入位置

脚本位置决定后继根：

```text
20_engineering/F3R2_V4_COMPETITION_MECHANICAL_CANDIDATE_20260809/
```

run-id 只能写入：

```text
03_native_cad/V4_ATTACH_RUNS/<run_id>/
```

构建预检使用排他目录创建。只要 `<run_id>` 已存在，就失败并拒绝重用。验证模式不会创建 run-id 目录，只能验证已经存在的目录。

## JSON manifest

manifest 必须使用 UTF-8，且只有一个顶层 JSON 对象。相对的输入/模板路径以 manifest 所在目录为基准；输出路径一律相对 package root。

```json
{
  "schema": "F3R2_V4_SOLIDWORKS_ATTACH_INPUT_V1",
  "run_id": "MF01_B601_20260809_R01",
  "package_relative_root": "package",
  "inputs": [
    {
      "role": "REV_B_RING_STEP",
      "path": "F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/M3_interface_authority/cad/B601_BASE_INTERFACE_RING_F3R2.step",
      "bytes": 35879,
      "sha256": "581D81236EE58FE7E457A9BB61DB3EBCC32B7780D12F5F272CE5E674D23CE36F"
    }
  ],
  "templates": [
    {
      "role": "ASSEMBLY_TEMPLATE",
      "path": "F:/Windows_profile/solidworks/DocumentTemplates/装配体.asmdot",
      "bytes": 35532,
      "sha256": "C0B857D584F7D651104BF560F3BE1C98F5604ADA191630DB724B05DBBDA3D058"
    }
  ],
  "expected_outputs": [
    {
      "role": "V4_PRIMARY_ASSEMBLY",
      "relative_path": "native/B601_NATIVE_INTERFACE_V4.SLDASM",
      "bytes": 123456,
      "sha256": "0000000000000000000000000000000000000000000000000000000000000000"
    },
    {
      "role": "V4_RING_PART",
      "relative_path": "native/B601_BASE_INTERFACE_RING_V4.SLDPRT",
      "bytes": 12345,
      "sha256": "1111111111111111111111111111111111111111111111111111111111111111"
    }
  ],
  "primary_document": "native/B601_NATIVE_INTERFACE_V4.SLDASM",
  "minimum_dependency_count": 1
}
```

示例中的输出字节数和哈希是占位值：

- 默认构建预检允许输出 `sha256` 和 `bytes` 暂缺，因为它不会制造 CAD。
- `--verify-only` 要求每一项 `expected_outputs` 都有真实的 64 位 SHA-256；如提供 `bytes`，也必须精确匹配。
- 主文档必须同时列入 `expected_outputs`。
- SOLIDWORKS 返回的每个依赖必须位于 package root 内、实际存在，并在 `expected_outputs` 中声明；这样每个依赖都有哈希证据。

## 命令

默认构建预检：

```powershell
python mfinal_solidworks_v4_attach.py F:\path\to\v4_input_manifest.json
```

预期成功完成安全预检后的结果仍是：

```text
NATIVE_BUILD_NOT_IMPLEMENTED_HOLD
exit code = 3
native_files_created = 0
```

第二进程静态包验证：

```powershell
python mfinal_solidworks_v4_attach.py F:\path\to\v4_verify_manifest.json --verify-only
```

静态 PASS 名称严格限定为：

```text
V4_PACKAGE_STATIC_VERIFY_PASS
```

它不等于 `COLD_REOPEN_REBUILD_PASS`，因为当前验证器不会打开或重建 CAD。未来只有另行实现只读冷重开、重建、配置、mate、干涉、净距、图纸和 BOM 内容检查后，才能增加相应 Gate。

## 退出码

| 退出码 | 含义 |
|---:|---|
| 0 | 仅 `V4_PACKAGE_STATIC_VERIFY_PASS` |
| 1 | 输入、文件、哈希、依赖、内存中文档或回执写入失败 |
| 2 | manifest / Python 环境错误 |
| 3 | 明确 HOLD，例如版本不符、资源不足或 native build 未实现 |
| 4 | `ATTACH_REQUIRED`，需要人工启动 SOLIDWORKS |

## 当前明确未覆盖

- 原生 SLDPRT/SLDASM/SLDDRW 创建；
- STEP 外链解除和实际材料赋值；
- mate、配置和完全约束检查；
- 冷重开重建；
- 原生干涉与连续净距；
- Pack-and-Go 的实际生成；
- 工程图尺寸、BOM 行、质量和属性内容验收；
- 制造、发射或飞行放行。
